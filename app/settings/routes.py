from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile
from app.constants import COUNTRIES

settings_bp = Blueprint("settings", __name__, url_prefix="/settings", template_folder="../templates/settings")


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Account details only. Everything shown on your card is edited on the card itself."""
    profile = current_profile()
    if not profile:
        flash("We couldn't find your account profile. Please try signing up again or contact support.", "error")
        return redirect(url_for("dashboard.index"))

    supabase = get_supabase()
    if request.method == "POST":
        name = (request.form.get("full_name") or "").strip() or profile["full_name"]
        supabase.table("profiles").update({
            "full_name": name[:120],
            "country": request.form.get("country") or None,
        }).eq("id", profile["id"]).execute()
        flash("Account updated.", "success")
        return redirect(url_for("settings.index"))

    my_apps = []
    if profile.get("is_developer"):
        my_apps = (
            supabase.table("listings").select("id,title")
            .eq("developer_id", profile["id"]).order("created_at", desc=True).execute().data
        )
    return render_template("settings/index.html", profile=profile, countries=COUNTRIES, my_apps=my_apps)
