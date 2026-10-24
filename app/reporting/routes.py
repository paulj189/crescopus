"""Retired: the old revenue and engagement reports are replaced by the CrescoLedger
(app/ledger). These addresses still work but lead to the partnership's ledger,
so old links and bookmarks don't break. Existing revenue reports were copied into
the ledger by sql/migration_plan_ledger.sql. RevenueCat sync (app/revenuecat.py)
will come back as automatic ledger entries.
"""
from flask import Blueprint, redirect, url_for, flash
from app.utils import login_required

reporting_bp = Blueprint("reporting", __name__, url_prefix="/reporting", template_folder="../templates/reporting")


@reporting_bp.route("/partnership/<partnership_id>/report/manual", methods=["GET", "POST"])
@reporting_bp.route("/partnership/<partnership_id>/engagement/new", methods=["GET", "POST"])
@reporting_bp.route("/partnership/<partnership_id>/report/sync", methods=["POST"])
@login_required
def retired(partnership_id):
    flash("Revenue and costs are now recorded in the CrescoLedger.", "success")
    return redirect(url_for("ledger.view", partnership_id=partnership_id))


@reporting_bp.route("/report/<report_id>/settle", methods=["POST"])
@login_required
def mark_settled(report_id):
    flash("Revenue and costs are now recorded in the CrescoLedger.", "success")
    return redirect(url_for("plans.index"))
