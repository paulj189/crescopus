from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile

partnerships_bp = Blueprint(
    "partnerships", __name__, url_prefix="/partnerships", template_folder="../templates/partnerships"
)


@partnerships_bp.route("/<partnership_id>")
@login_required
def detail(partnership_id):
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data
    stream = supabase.table("revenue_streams").select("*").eq("id", partnership["revenue_stream_id"]).single().execute().data
    reports = (
        supabase.table("revenue_reports")
        .select("*")
        .eq("partnership_id", partnership_id)
        .order("period_start", desc=True)
        .execute()
        .data
    )
    return render_template("partnerships/detail.html", partnership=partnership, stream=stream, reports=reports)


@partnerships_bp.route("/<partnership_id>/end", methods=["GET", "POST"])
@login_required
def end(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if request.method == "POST":
        reason = request.form.get("end_reason", "").strip()
        if not reason:
            flash("A reason is required to end a partnership.", "error")
            return render_template("partnerships/end.html", partnership=partnership)

        supabase.table("partnerships").update({
            "status": "ended",
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "ended_by": profile["id"],
            "end_reason": reason,
        }).eq("id", partnership_id).execute()

        # The stream reopens so the developer can find a different grower for it.
        supabase.table("revenue_streams").update({"status": "open"}).eq(
            "id", partnership["revenue_stream_id"]
        ).execute()

        flash("Partnership ended.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("partnerships/end.html", partnership=partnership)
