from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile
from app.constants import COUNTRIES

settings_bp = Blueprint("settings", __name__, url_prefix="/settings", template_folder="../templates/settings")


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    profile = current_profile()

    if request.method == "POST":
        supabase = get_supabase()
        supabase.table("profiles").update({
            "full_name": request.form.get("full_name", profile["full_name"]),
            "country": request.form.get("country") or None,
        }).eq("id", profile["id"]).execute()
        flash("Profile updated.", "success")
        return redirect(url_for("settings.index"))

    return render_template("settings/index.html", profile=profile, countries=COUNTRIES)
