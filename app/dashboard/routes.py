from flask import Blueprint, render_template
from app.extensions import get_supabase
from app.utils import login_required, current_profile

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard", template_folder="../templates/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    profile = current_profile()
    supabase = get_supabase()

    my_listings = []
    if profile.get("is_developer"):
        listings = supabase.table("listings").select("*").eq("developer_id", profile["id"]).execute().data
        for listing in listings:
            listing["streams"] = (
                supabase.table("revenue_streams").select("*").eq("listing_id", listing["id"]).execute().data
            )
        my_listings = listings

    my_proposals = []
    if profile.get("is_grower"):
        my_proposals = supabase.table("proposals").select("*").eq("grower_id", profile["id"]).execute().data

    partnerships = (
        supabase.table("partnerships")
        .select("*")
        .or_(f"developer_id.eq.{profile['id']},grower_id.eq.{profile['id']}")
        .execute()
        .data
    )

    return render_template(
        "dashboard/index.html",
        profile=profile,
        listings=my_listings,
        proposals=my_proposals,
        partnerships=partnerships,
    )
