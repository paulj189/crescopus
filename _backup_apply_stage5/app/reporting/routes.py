from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile
from app.revenuecat import fetch_revenuecat_totals

reporting_bp = Blueprint("reporting", __name__, url_prefix="/reporting", template_folder="../templates/reporting")


def _compute_split(gross, developer_pct):
    developer_share = round(gross * developer_pct / 100, 2)
    grower_share = round(gross - developer_share, 2)
    return developer_share, grower_share


@reporting_bp.route("/partnership/<partnership_id>/report/manual", methods=["GET", "POST"])
@login_required
def manual_report(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if request.method == "POST":
        if not profile:
            flash("Please log in again to report revenue.", "error")
            return redirect(url_for("auth.login"))

        if not partnership.get("revenue_share"):
            flash("Set revenue terms on this CrescoPact before reporting revenue.", "error")
            return redirect(url_for("partnerships.set_revenue_terms", partnership_id=partnership_id))

        gross = float(request.form["gross_amount"])
        developer_share, grower_share = _compute_split(gross, float(partnership["revenue_share"]))

        supabase.table("revenue_reports").insert({
            "partnership_id": partnership_id,
            "period_start": request.form["period_start"],
            "period_end": request.form["period_end"],
            "gross_amount": gross,
            "developer_share": developer_share,
            "grower_share": grower_share,
            "source": "manual",
            "verified": False,
            "reported_by": profile["id"],
        }).execute()

        flash("Revenue reported — self-reported figures are flagged as unverified.", "success")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    return render_template("reporting/manual_report.html", partnership=partnership)


@reporting_bp.route("/partnership/<partnership_id>/engagement/new", methods=["GET", "POST"])
@login_required
def manual_engagement_report(partnership_id):
    profile = current_profile()
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if request.method == "POST":
        if not profile:
            flash("Please log in again to report engagement.", "error")
            return redirect(url_for("auth.login"))

        supabase.table("engagement_reports").insert({
            "partnership_id": partnership_id,
            "period_start": request.form["period_start"],
            "period_end": request.form["period_end"],
            "views": request.form.get("views") or None,
            "clicks": request.form.get("clicks") or None,
            "downloads": request.form.get("downloads") or None,
            "notes": request.form.get("notes"),
            "reported_by": profile["id"],
        }).execute()

        flash("Engagement reported.", "success")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    return render_template("reporting/engagement_report.html", partnership=partnership)


@reporting_bp.route("/partnership/<partnership_id>/report/sync", methods=["POST"])
@login_required
def sync_revenuecat(partnership_id):
    supabase = get_supabase()
    partnership = supabase.table("partnerships").select("*").eq("id", partnership_id).single().execute().data

    if not partnership.get("listing_id"):
        flash("This CrescoPact predates the current app version and can't be synced. Please contact support.", "error")
        return redirect(url_for("dashboard.index"))

    listing = supabase.table("listings").select("*").eq("id", partnership["listing_id"]).single().execute().data

    if not listing.get("revenuecat_project_key"):
        flash("This app has no RevenueCat project key on file — the developer can add one from the listing's edit page.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    if not partnership.get("revenue_share"):
        flash("Set revenue terms on this CrescoPact before syncing revenue.", "error")
        return redirect(url_for("partnerships.set_revenue_terms", partnership_id=partnership_id))

    period_start, period_end, gross = fetch_revenuecat_totals(listing["revenuecat_project_key"])

    if gross is None:
        flash("RevenueCat sync isn't wired up yet for this app.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    developer_share, grower_share = _compute_split(gross, float(partnership["revenue_share"]))

    supabase.table("revenue_reports").insert({
        "partnership_id": partnership_id,
        "period_start": period_start,
        "period_end": period_end,
        "gross_amount": gross,
        "developer_share": developer_share,
        "grower_share": grower_share,
        "source": "revenuecat",
        "verified": True,
    }).execute()

    flash("Synced verified revenue from RevenueCat.", "success")
    return redirect(url_for("partnerships.detail", partnership_id=partnership_id))


@reporting_bp.route("/report/<report_id>/settle", methods=["POST"])
@login_required
def mark_settled(report_id):
    supabase = get_supabase()
    supabase.table("revenue_reports").update({
        "settled": True,
        "settled_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", report_id).execute()
    flash("Marked as settled.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))
