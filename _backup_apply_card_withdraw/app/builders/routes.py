"""Old builder pages: Builders now appear through their app cards on Browse."""
from flask import Blueprint, redirect, url_for
from app.extensions import get_supabase

builders_bp = Blueprint("builders", __name__, url_prefix="/builders", template_folder="../templates/builders")


@builders_bp.route("/")
def browse():
    return redirect(url_for("browse.index"))


@builders_bp.route("/<builder_id>")
def detail(builder_id):
    apps = (get_supabase().table("listings").select("id").eq("developer_id", builder_id)
            .order("created_at", desc=True).limit(1).execute().data)
    if apps:
        return redirect(url_for("browse.app_detail", listing_id=apps[0]["id"]))
    return redirect(url_for("browse.index"))
