from flask import Blueprint, render_template
from app.extensions import get_supabase

builders_bp = Blueprint("builders", __name__, url_prefix="/builders", template_folder="../templates/builders")


@builders_bp.route("/<builder_id>")
def detail(builder_id):
    supabase = get_supabase()
    builder = supabase.table("profiles").select("*").eq("id", builder_id).single().execute().data
    listings = (
        supabase.table("listings")
        .select("*")
        .eq("developer_id", builder_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return render_template("builders/detail.html", builder=builder, listings=listings)
