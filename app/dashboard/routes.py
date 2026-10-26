from flask import Blueprint, render_template, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import (
    login_required,
    current_profile,
    get_pending_received_requests,
    get_unread_partnerships,
    get_ledger_waiting_on_me,
)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard", template_folder="../templates/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    from app.plans.routes import plan_summaries  # imported here to avoid a circular import

    profile = current_profile()
    if not profile:
        flash("We couldn't find your account profile. Please try signing up again or contact support.", "error")
        return redirect(url_for("auth.logout"))

    supabase = get_supabase()
    plans = plan_summaries(supabase, profile)
    titles = {p["id"]: p["title"] for p in plans if p["active"]}

    # Your card(s)
    my_apps = []
    if profile.get("is_developer"):
        my_apps = (supabase.table("listings").select("id,title,tagline,hero_image_url,withdrawn_at")
                   .eq("developer_id", profile["id"]).order("created_at", desc=True).execute().data)

    # Needs your attention
    received = get_pending_received_requests(supabase, profile)
    listing_titles = {}
    sent = (supabase.table("connection_requests").select("id,listing_id,status,reject_reason,created_at")
            .eq("initiated_by", profile["id"]).order("created_at", desc=True).limit(20).execute().data)
    wanted = {r["listing_id"] for r in received + sent}
    if wanted:
        listing_titles = {l["id"]: l["title"] for l in (supabase.table("listings").select("id,title")
                          .in_("id", list(wanted)).execute().data)}
    for r in received + sent:
        r["listing_title"] = listing_titles.get(r["listing_id"], "an app")

    plans_waiting = [p for p in plans if p["state"][0] == "you"]
    ledger_waiting = get_ledger_waiting_on_me(supabase, profile, [p["id"] for p in plans if p["active"]])
    unread = get_unread_partnerships(supabase, profile)
    unread_items = [{"id": pid, "title": titles.get(pid, "A partnership"), "body": m.get("body", "")}
                    for pid, m in unread.items() if pid in titles]

    attention = len(received) + len(plans_waiting) + len(ledger_waiting) + len(unread_items)
    return render_template(
        "dashboard/index.html",
        profile=profile, plans=plans, my_apps=my_apps,
        received=received, sent=sent,
        plans_waiting=plans_waiting, ledger_waiting=ledger_waiting, unread_items=unread_items,
        titles=titles, attention=attention,
    )
