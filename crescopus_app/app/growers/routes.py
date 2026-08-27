from flask import Blueprint, render_template
from app.extensions import get_supabase
from app.utils import current_profile

growers_bp = Blueprint("growers", __name__, url_prefix="/growers", template_folder="../templates/growers")


@growers_bp.route("/")
def browse():
    supabase = get_supabase()
    res = (
        supabase.table("profiles")
        .select("*")
        .eq("is_grower", True)
        .order("created_at", desc=True)
        .execute()
    )
    return render_template("growers/browse.html", growers=res.data)


@growers_bp.route("/<grower_id>")
def detail(grower_id):
    supabase = get_supabase()
    grower = supabase.table("profiles").select("*").eq("id", grower_id).single().execute().data

    viewer = current_profile()
    is_builder_viewer = bool(viewer and viewer.get("is_developer"))

    my_listings = []
    if is_builder_viewer:
        my_listings = (
            supabase.table("listings")
            .select("*")
            .eq("developer_id", viewer["id"])
            .order("created_at", desc=True)
            .execute()
            .data
        )

    return render_template(
        "growers/detail.html",
        grower=grower,
        is_builder_viewer=is_builder_viewer,
        my_listings=my_listings,
    )
