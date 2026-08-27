from flask import Blueprint, render_template, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard", template_folder="../templates/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    profile = current_profile()
    if not profile:
        flash("We couldn't find your account profile. Please try signing up again or contact support.", "error")
        return redirect(url_for("auth.logout"))

    supabase = get_supabase()

    my_listings = []
    my_listing_ids = []
    if profile.get("is_developer"):
        listings = supabase.table("listings").select("*").eq("developer_id", profile["id"]).execute().data
        for listing in listings:
            listing["streams"] = (
                supabase.table("revenue_streams").select("*").eq("listing_id", listing["id"]).execute().data
            )
        my_listings = listings
        my_listing_ids = [l["id"] for l in listings]

    sent_requests = (
        supabase.table("connection_requests")
        .select("*")
        .eq("initiated_by", profile["id"])
        .order("created_at", desc=True)
        .execute()
        .data
    )

    received_requests = []
    if profile.get("is_grower"):
        received_requests = (
            supabase.table("connection_requests")
            .select("*")
            .eq("grower_id", profile["id"])
            .neq("initiated_by", profile["id"])
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
            .data
        )
    elif my_listing_ids:
        received_requests = (
            supabase.table("connection_requests")
            .select("*")
            .in_("listing_id", my_listing_ids)
            .neq("initiated_by", profile["id"])
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
            .data
        )

    partnerships = (
        supabase.table("partnerships")
        .select("*")
        .or_(f"developer_id.eq.{profile['id']},grower_id.eq.{profile['id']}")
        .order("created_at", desc=True)
        .execute()
        .data
    )
    listing_ids = list({p["listing_id"] for p in partnerships})
    listings_by_id = {}
    if listing_ids:
        rows = supabase.table("listings").select("id,title").in_("id", listing_ids).execute().data
        listings_by_id = {row["id"]: row["title"] for row in rows}
    for p in partnerships:
        p["listing_title"] = listings_by_id.get(p["listing_id"], "")

    return render_template(
        "dashboard/index.html",
        profile=profile,
        listings=my_listings,
        sent_requests=sent_requests,
        received_requests=received_requests,
        partnerships=partnerships,
    )
