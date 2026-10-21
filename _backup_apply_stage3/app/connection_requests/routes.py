from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile

connection_requests_bp = Blueprint(
    "connection_requests", __name__, url_prefix="/connect", template_folder="../templates/connection_requests"
)


@connection_requests_bp.route("/listing/<listing_id>/new", methods=["GET", "POST"])
@login_required
def new_from_listing(listing_id):
    """A grower reaches out to a builder about one of the builder's listings."""
    profile = current_profile()
    if not profile or not profile.get("is_grower"):
        flash("Only grower accounts can send a connection request.", "error")
        return redirect(url_for("listings.detail", listing_id=listing_id))

    supabase = get_supabase()
    listing = supabase.table("listings").select("*").eq("id", listing_id).single().execute().data

    if request.method == "POST":
        if not request.form.get("consent_acknowledged"):
            flash("Please confirm you understand Crescopus's role before sending this.", "error")
            return render_template("connection_requests/new.html", listing=listing)

        supabase.table("connection_requests").insert({
            "listing_id": listing_id,
            "grower_id": profile["id"],
            "initiated_by": profile["id"],
            "message": request.form["message"],
            "status": "pending",
        }).execute()
        flash("Connection request sent.", "success")
        return redirect(url_for("listings.detail", listing_id=listing_id))

    return render_template("connection_requests/new.html", listing=listing)


@connection_requests_bp.route("/grower/<grower_id>/listing/<listing_id>/new", methods=["GET", "POST"])
@login_required
def new_from_grower(grower_id, listing_id):
    """A builder reaches out to a grower about one of their own listings."""
    profile = current_profile()
    supabase = get_supabase()
    listing = supabase.table("listings").select("*").eq("id", listing_id).single().execute().data

    if not profile or not listing or listing["developer_id"] != profile["id"]:
        flash("Only the listing's developer can reach out about it.", "error")
        return redirect(url_for("growers.detail", grower_id=grower_id))

    grower = supabase.table("profiles").select("*").eq("id", grower_id).single().execute().data

    if request.method == "POST":
        if not request.form.get("consent_acknowledged"):
            flash("Please confirm you understand Crescopus's role before sending this.", "error")
            return render_template("connection_requests/new.html", listing=listing, grower=grower)

        supabase.table("connection_requests").insert({
            "listing_id": listing_id,
            "grower_id": grower_id,
            "initiated_by": profile["id"],
            "message": request.form["message"],
            "status": "pending",
        }).execute()
        flash("Connection request sent.", "success")
        return redirect(url_for("growers.detail", grower_id=grower_id))

    return render_template("connection_requests/new.html", listing=listing, grower=grower)


@connection_requests_bp.route("/<request_id>/respond", methods=["GET"])
@login_required
def respond(request_id):
    supabase = get_supabase()
    req = supabase.table("connection_requests").select("*").eq("id", request_id).single().execute().data
    listing = supabase.table("listings").select("*").eq("id", req["listing_id"]).single().execute().data
    grower = supabase.table("profiles").select("*").eq("id", req["grower_id"]).single().execute().data
    sender = supabase.table("profiles").select("*").eq("id", req["initiated_by"]).single().execute().data

    profile = current_profile()
    recipient_id = listing["developer_id"] if req["initiated_by"] == req["grower_id"] else req["grower_id"]

    if not profile or profile["id"] != recipient_id:
        flash("This connection request isn't addressed to you.", "error")
        return redirect(url_for("dashboard.index"))

    return render_template("connection_requests/respond.html", req=req, listing=listing, grower=grower, sender=sender)


@connection_requests_bp.route("/<request_id>/accept", methods=["POST"])
@login_required
def accept(request_id):
    supabase = get_supabase()
    req = supabase.table("connection_requests").select("*").eq("id", request_id).single().execute().data
    listing = supabase.table("listings").select("*").eq("id", req["listing_id"]).single().execute().data

    profile = current_profile()
    recipient_id = listing["developer_id"] if req["initiated_by"] == req["grower_id"] else req["grower_id"]
    if not profile or profile["id"] != recipient_id:
        flash("This connection request isn't addressed to you.", "error")
        return redirect(url_for("dashboard.index"))

    if req["status"] != "pending":
        flash("This connection request has already been responded to.", "error")
        return redirect(url_for("dashboard.index"))

    supabase.table("connection_requests").update({"status": "accepted"}).eq("id", request_id).execute()

    result = supabase.table("partnerships").insert({
        "listing_id": req["listing_id"],
        "connection_request_id": request_id,
        "grower_id": req["grower_id"],
        "developer_id": listing["developer_id"],
        "status": "trial",
    }).execute()

    partnership_id = result.data[0]["id"]
    flash("You're now connected. Say hello!", "success")
    return redirect(url_for("partnerships.detail", partnership_id=partnership_id))


@connection_requests_bp.route("/<request_id>/reject", methods=["POST"])
@login_required
def reject(request_id):
    supabase = get_supabase()
    req = supabase.table("connection_requests").select("*").eq("id", request_id).single().execute().data
    listing = supabase.table("listings").select("*").eq("id", req["listing_id"]).single().execute().data

    profile = current_profile()
    recipient_id = listing["developer_id"] if req["initiated_by"] == req["grower_id"] else req["grower_id"]
    if not profile or profile["id"] != recipient_id:
        flash("This connection request isn't addressed to you.", "error")
        return redirect(url_for("dashboard.index"))

    if req["status"] != "pending":
        flash("This connection request has already been responded to.", "error")
        return redirect(url_for("dashboard.index"))

    supabase.table("connection_requests").update({
        "status": "rejected",
        "reject_reason": request.form.get("reject_reason"),
    }).eq("id", request_id).execute()

    flash("Connection request declined.", "success")
    return redirect(url_for("dashboard.index"))
