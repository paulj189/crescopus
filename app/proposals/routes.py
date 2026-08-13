from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile

proposals_bp = Blueprint("proposals", __name__, url_prefix="/proposals", template_folder="../templates/proposals")


@proposals_bp.route("/stream/<stream_id>/new", methods=["GET", "POST"])
@login_required
def new(stream_id):
    profile = current_profile()
    if not profile or not profile.get("is_grower"):
        flash("Only grower profiles can submit a proposal.", "error")
        return redirect(url_for("listings.stream_detail", stream_id=stream_id))

    if request.method == "POST":
        supabase = get_supabase()
        supabase.table("proposals").insert({
            "revenue_stream_id": stream_id,
            "grower_id": profile["id"],
            "revenue_share_offered": request.form["revenue_share_offered"],
            "growth_plan": request.form.get("growth_plan"),
            "track_record_summary": request.form.get("track_record_summary"),
            "term_length_months": request.form.get("term_length_months") or None,
            "status": "pending",
        }).execute()
        flash("Proposal sent.", "success")
        return redirect(url_for("listings.stream_detail", stream_id=stream_id))

    return render_template("proposals/new.html", stream_id=stream_id)


@proposals_bp.route("/<proposal_id>/accept", methods=["POST"])
@login_required
def accept(proposal_id):
    supabase = get_supabase()
    proposal = supabase.table("proposals").select("*").eq("id", proposal_id).single().execute().data
    developer = current_profile()

    supabase.table("partnerships").insert({
        "revenue_stream_id": proposal["revenue_stream_id"],
        "proposal_id": proposal["id"],
        "grower_id": proposal["grower_id"],
        "developer_id": developer["id"],
        "revenue_share": proposal["revenue_share_offered"],
        "term_length_months": proposal.get("term_length_months"),
        "status": "active",
    }).execute()

    supabase.table("proposals").update({"status": "accepted"}).eq("id", proposal_id).execute()
    supabase.table("revenue_streams").update({"status": "matched"}).eq("id", proposal["revenue_stream_id"]).execute()

    flash("Partnership formed.", "success")
    return redirect(url_for("dashboard.index"))
