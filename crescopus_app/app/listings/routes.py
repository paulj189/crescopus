from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile

listings_bp = Blueprint("listings", __name__, url_prefix="/listings", template_folder="../templates/listings")


@listings_bp.route("/")
def browse():
    supabase = get_supabase()
    res = supabase.table("listings").select("*").order("created_at", desc=True).execute()
    return render_template("listings/browse.html", listings=res.data)


@listings_bp.route("/<listing_id>")
def detail(listing_id):
    supabase = get_supabase()
    listing = supabase.table("listings").select("*").eq("id", listing_id).single().execute().data
    streams = (
        supabase.table("revenue_streams")
        .select("*")
        .eq("listing_id", listing_id)
        .neq("status", "draft")
        .order("created_at", desc=True)
        .execute()
        .data
    )

    profile = current_profile()
    is_owner = bool(profile and listing["developer_id"] == profile["id"])

    pending_requests = []
    if is_owner:
        pending_requests = (
            supabase.table("connection_requests")
            .select("*")
            .eq("listing_id", listing_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
            .data
        )

    return render_template(
        "listings/detail.html",
        listing=listing,
        streams=streams,
        is_owner=is_owner,
        pending_requests=pending_requests,
    )


@listings_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    profile = current_profile()
    if not profile or not profile.get("is_developer"):
        flash("Only developer profiles can list an app.", "error")
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        supabase = get_supabase()
        result = supabase.table("listings").insert({
            "developer_id": profile["id"],
            "title": request.form["title"],
            "tagline": request.form.get("tagline"),
            "description": request.form.get("description"),
            "category": request.form.get("category"),
            "platform": request.form.get("platform"),
        }).execute()
        listing_id = result.data[0]["id"]
        flash("Listing published — add a revenue stream if you know your monetisation plan, or leave it for later.", "success")
        return redirect(url_for("listings.detail", listing_id=listing_id))

    return render_template("listings/new.html")


@listings_bp.route("/<listing_id>/streams/new", methods=["GET", "POST"])
@login_required
def stream_new(listing_id):
    profile = current_profile()
    supabase = get_supabase()
    listing = supabase.table("listings").select("*").eq("id", listing_id).single().execute().data

    if not listing or not profile or listing["developer_id"] != profile["id"]:
        flash("Only the listing's developer can add a revenue stream.", "error")
        return redirect(url_for("listings.detail", listing_id=listing_id))

    if request.method == "POST":
        supabase.table("revenue_streams").insert({
            "listing_id": listing_id,
            "stream_type": request.form["stream_type"],
            "status": "open",
            "created_by": profile["id"],
            "min_revenue_share": request.form.get("min_revenue_share") or None,
            "looking_for": request.form.get("looking_for"),
            "control_boundaries": request.form.get("control_boundaries"),
        }).execute()
        flash("Revenue stream added.", "success")
        return redirect(url_for("listings.detail", listing_id=listing_id))

    return render_template("listings/stream_new.html", listing=listing)


@listings_bp.route("/<listing_id>/edit", methods=["GET", "POST"])
@login_required
def edit(listing_id):
    profile = current_profile()
    supabase = get_supabase()
    listing = supabase.table("listings").select("*").eq("id", listing_id).single().execute().data

    if not listing or not profile or listing["developer_id"] != profile["id"]:
        flash("Only the listing's developer can edit it.", "error")
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        supabase.table("listings").update({
            "title": request.form["title"],
            "tagline": request.form.get("tagline"),
            "description": request.form.get("description"),
            "category": request.form.get("category"),
            "platform": request.form.get("platform"),
            "revenuecat_project_key": request.form.get("revenuecat_project_key") or None,
        }).eq("id", listing_id).execute()
        flash("Listing updated.", "success")
        return redirect(url_for("listings.detail", listing_id=listing_id))

    return render_template("listings/edit.html", listing=listing)


@listings_bp.route("/streams/<stream_id>/edit", methods=["GET", "POST"])
@login_required
def stream_edit(stream_id):
    profile = current_profile()
    supabase = get_supabase()
    stream = supabase.table("revenue_streams").select("*").eq("id", stream_id).single().execute().data
    listing = supabase.table("listings").select("*").eq("id", stream["listing_id"]).single().execute().data

    if not listing or not profile or listing["developer_id"] != profile["id"]:
        flash("Only the listing's developer can edit this revenue stream.", "error")
        return redirect(url_for("listings.stream_detail", stream_id=stream_id))

    if request.method == "POST":
        supabase.table("revenue_streams").update({
            "stream_type": request.form["stream_type"],
            "min_revenue_share": request.form.get("min_revenue_share") or None,
            "looking_for": request.form.get("looking_for"),
            "control_boundaries": request.form.get("control_boundaries"),
        }).eq("id", stream_id).execute()
        flash("Revenue stream updated.", "success")
        return redirect(url_for("listings.stream_detail", stream_id=stream_id))

    return render_template("listings/stream_edit.html", stream=stream, listing=listing)


@listings_bp.route("/streams/<stream_id>")
def stream_detail(stream_id):
    supabase = get_supabase()
    stream = supabase.table("revenue_streams").select("*").eq("id", stream_id).single().execute().data
    listing = supabase.table("listings").select("*").eq("id", stream["listing_id"]).single().execute().data

    profile = current_profile()
    is_owner = bool(profile and listing["developer_id"] == profile["id"])

    return render_template("listings/stream_detail.html", stream=stream, listing=listing, is_owner=is_owner)
