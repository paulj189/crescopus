from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile

partnerships_bp = Blueprint(
    "partnerships", __name__, url_prefix="/partnerships", template_folder="../templates/partnerships"
)


def _other_party_id(partnership, my_id):
    return partnership["grower_id"] if my_id == partnership["developer_id"] else partnership["developer_id"]


def _require_party(partnership, profile):
    return bool(profile and profile["id"] in (partnership["developer_id"], partnership["grower_id"]))


@partnerships_bp.route("/<partnership_id>")
@login_required
def detail(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not partnership.get("listing_id"):
        flash("This CrescoPact predates the current app version and can't be displayed. Please contact support.", "error")
        return redirect(url_for("dashboard.index"))

    listing = supabase.table("listings").select("*").eq("id", partnership["listing_id"]).single().execute().data

    if not _require_party(partnership, profile):
        flash("You're not part of this CrescoPact.", "error")
        return redirect(url_for("dashboard.index"))

    messages = (
        supabase.table("messages")
        .select("*")
        .eq("partnership_id", partnership_id)
        .order("created_at")
        .execute()
        .data
    )
    reports = (
        supabase.table("revenue_reports")
        .select("*")
        .eq("partnership_id", partnership_id)
        .order("period_start", desc=True)
        .execute()
        .data
    )
    engagement_reports = (
        supabase.table("engagement_reports")
        .select("*")
        .eq("partnership_id", partnership_id)
        .order("period_start", desc=True)
        .execute()
        .data
    )

    return render_template(
        "partnerships/detail.html",
        partnership=partnership,
        listing=listing,
        messages=messages,
        reports=reports,
        engagement_reports=engagement_reports,
        profile=profile,
    )


@partnerships_bp.route("/<partnership_id>/messages", methods=["POST"])
@login_required
def send_message(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not _require_party(partnership, profile):
        flash("You're not part of this CrescoPact.", "error")
        return redirect(url_for("dashboard.index"))

    if partnership["status"] not in ("trial", "formalised"):
        flash("This CrescoPact has ended — messaging is closed.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    body = request.form.get("body", "").strip()
    if body:
        supabase.table("messages").insert({
            "partnership_id": partnership_id,
            "sender_id": profile["id"],
            "body": body,
        }).execute()

    return redirect(url_for("partnerships.detail", partnership_id=partnership_id))


@partnerships_bp.route("/<partnership_id>/disconnect", methods=["GET", "POST"])
@login_required
def disconnect(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not _require_party(partnership, profile):
        flash("You're not part of this CrescoPact.", "error")
        return redirect(url_for("dashboard.index"))

    if partnership["status"] != "trial":
        flash("Only a Trial CrescoPact can be disconnected.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("A reason is required to disconnect.", "error")
            return render_template("partnerships/disconnect.html", partnership=partnership)

        supabase.table("partnerships").update({
            "status": "disconnected",
            "disconnected_at": datetime.now(timezone.utc).isoformat(),
            "disconnected_by": profile["id"],
            "disconnect_reason": reason,
        }).eq("id", partnership_id).execute()

        flash("Disconnected.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("partnerships/disconnect.html", partnership=partnership)


@partnerships_bp.route("/<partnership_id>/formalise/propose", methods=["POST"])
@login_required
def formalise_propose(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not _require_party(partnership, profile):
        flash("You're not part of this CrescoPact.", "error")
        return redirect(url_for("dashboard.index"))

    if partnership["status"] != "trial":
        flash("Only a Trial CrescoPact can be proposed for formalising.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    supabase.table("partnerships").update({
        "formalise_status": "proposed",
        "formalise_proposed_by": profile["id"],
        "formalise_declined_reason": None,
    }).eq("id", partnership_id).execute()

    flash("Formalise proposed.", "success")
    return redirect(url_for("partnerships.detail", partnership_id=partnership_id))


@partnerships_bp.route("/<partnership_id>/formalise/accept", methods=["POST"])
@login_required
def formalise_accept(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not _require_party(partnership, profile):
        flash("You're not part of this CrescoPact.", "error")
        return redirect(url_for("dashboard.index"))

    if partnership["formalise_status"] != "proposed" or partnership["formalise_proposed_by"] == profile["id"]:
        flash("There's no formalise proposal for you to accept here.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    existing = (
        supabase.table("partnerships")
        .select("id")
        .eq("listing_id", partnership["listing_id"])
        .eq("status", "formalised")
        .execute()
    )
    if existing.data:
        flash("This listing already has a Formalised CrescoPact.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    supabase.table("partnerships").update({
        "status": "formalised",
        "formalise_status": "none",
    }).eq("id", partnership_id).execute()

    flash("CrescoPact formalised.", "success")
    return redirect(url_for("partnerships.detail", partnership_id=partnership_id))


@partnerships_bp.route("/<partnership_id>/formalise/decline", methods=["POST"])
@login_required
def formalise_decline(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not _require_party(partnership, profile):
        flash("You're not part of this CrescoPact.", "error")
        return redirect(url_for("dashboard.index"))

    if partnership["formalise_status"] != "proposed" or partnership["formalise_proposed_by"] == profile["id"]:
        flash("There's no formalise proposal for you to decline here.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    supabase.table("partnerships").update({
        "formalise_status": "declined",
        "formalise_declined_reason": request.form.get("reason", "").strip() or None,
    }).eq("id", partnership_id).execute()

    flash("Formalise proposal declined — the Trial continues.", "success")
    return redirect(url_for("partnerships.detail", partnership_id=partnership_id))


@partnerships_bp.route("/<partnership_id>/revenue-terms", methods=["GET", "POST"])
@login_required
def set_revenue_terms(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not _require_party(partnership, profile):
        flash("You're not part of this CrescoPact.", "error")
        return redirect(url_for("dashboard.index"))

    if partnership["status"] != "formalised":
        flash("Revenue terms can only be set on a Formalised CrescoPact.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    if request.method == "POST":
        if not request.form.get("consent_acknowledged"):
            flash("Please confirm you understand Crescopus's role before setting revenue terms.", "error")
            return render_template("partnerships/revenue_terms.html", partnership=partnership)

        supabase.table("partnerships").update({
            "revenue_share": request.form["revenue_share"],
        }).eq("id", partnership_id).execute()
        flash("Revenue terms set.", "success")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    return render_template("partnerships/revenue_terms.html", partnership=partnership)


@partnerships_bp.route("/<partnership_id>/end", methods=["GET", "POST"])
@login_required
def end(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not _require_party(partnership, profile):
        flash("You're not part of this CrescoPact.", "error")
        return redirect(url_for("dashboard.index"))

    if partnership["status"] != "formalised":
        flash("Only a Formalised CrescoPact can be ended this way.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    if request.method == "POST":
        reason = request.form.get("end_reason", "").strip()
        if not reason:
            flash("A reason is required to end a CrescoPact.", "error")
            return render_template("partnerships/end.html", partnership=partnership)

        supabase.table("partnerships").update({
            "status": "ended",
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "ended_by": profile["id"],
            "end_reason": reason,
        }).eq("id", partnership_id).execute()

        flash("CrescoPact ended.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("partnerships/end.html", partnership=partnership)
