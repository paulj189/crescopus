from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile, clean_list_html, clean_pitch_html, tags_from_form
from app.constants import COUNTRIES, GROWER_NEEDS_TAGS, GROWER_OFFERS_TAGS

settings_bp = Blueprint("settings", __name__, url_prefix="/settings", template_folder="../templates/settings")


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    profile = current_profile()
    if not profile:
        flash("We couldn't find your account profile. Please try signing up again or contact support.", "error")
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        supabase = get_supabase()
        updates = {
            "full_name": request.form.get("full_name", profile["full_name"]),
            "country": request.form.get("country") or None,
            "pitch_html": clean_pitch_html(request.form.get("pitch_html")),
            "hero_image_url": request.form.get("hero_image_url") or None,
        }
        if profile.get("is_grower"):
            updates.update({
                "needs_html": clean_list_html(request.form.get("needs_html")),
                "offers_html": clean_list_html(request.form.get("offers_html")),
                "needs_tags": tags_from_form(request.form, "needs_tags", GROWER_NEEDS_TAGS),
                "offers_tags": tags_from_form(request.form, "offers_tags", GROWER_OFFERS_TAGS),
            })
        supabase.table("profiles").update(updates).eq("id", profile["id"]).execute()
        flash("Profile updated.", "success")
        return redirect(url_for("settings.index"))

    return render_template(
        "settings/index.html", profile=profile, countries=COUNTRIES,
        needs_options=GROWER_NEEDS_TAGS, offers_options=GROWER_OFFERS_TAGS,
    )
