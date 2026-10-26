"""Partnerships: the private messages between a Builder and a Grower, and ending
the partnership. The plan and ledger live in app/plans and app/ledger.

The old Trial / Formalise / revenue-terms steps (CrescoPacts) are retired. Their
addresses still work but lead to the CrescoPlan, so old links and bookmarks
don't break. Partnerships stored as "trial" or "formalised" are both simply
active now.
"""
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile, mark_partnership_read, get_unread_partnerships

partnerships_bp = Blueprint(
    "partnerships", __name__, url_prefix="/partnerships", template_folder="../templates/partnerships"
)

ACTIVE = ("trial", "formalised")


def _require_party(partnership, profile):
    return bool(partnership and profile and profile["id"] in (partnership["developer_id"], partnership["grower_id"]))


def _get(partnership_id):
    rows = (get_supabase().table("partnerships").select("*, listings(id,title)")
            .eq("id", partnership_id).execute().data)
    return rows[0] if rows else None


@partnerships_bp.route("/")
@login_required
def inbox():
    """Messages: one conversation per Cresco, newest first, unread ones marked."""
    from app.plans.routes import plan_summaries  # imported here to avoid a circular import

    profile = current_profile()
    if not profile:
        return redirect(url_for("auth.logout"))
    supabase = get_supabase()
    crescos = plan_summaries(supabase, profile)
    ids = [c["id"] for c in crescos]
    latest = {}
    if ids:
        for m in (supabase.table("messages").select("partnership_id,sender_id,body,created_at")
                  .in_("partnership_id", ids).order("created_at", desc=True).execute().data):
            latest.setdefault(m["partnership_id"], m)
    unread = get_unread_partnerships(supabase, profile)
    for c in crescos:
        c["last"] = latest.get(c["id"])
        c["unread"] = c["id"] in unread
    # Unread first, then most recent conversation, then the rest; ended ones last.
    crescos.sort(key=lambda c: (not c["active"], not c["unread"], c["last"] is None,
                                _invert(c["last"]["created_at"]) if c["last"] else ""))
    return render_template("partnerships/inbox.html", crescos=crescos, profile=profile)


def _invert(stamp):
    """Sort key that puts later timestamps first."""
    return "".join(chr(255 - ord(ch)) for ch in stamp)


@partnerships_bp.route("/<partnership_id>")
@login_required
def detail(partnership_id):
    """Messages between the two of you."""
    profile = current_profile()
    partnership = _get(partnership_id)
    if not _require_party(partnership, profile):
        flash("That conversation isn't available to you.", "error")
        return redirect(url_for("dashboard.index"))

    supabase = get_supabase()
    people = {p["id"]: p["full_name"] for p in (supabase.table("profiles").select("id,full_name")
              .in_("id", [partnership["developer_id"], partnership["grower_id"]]).execute().data)}
    messages = (supabase.table("messages").select("*").eq("partnership_id", partnership_id)
                .order("created_at").execute().data)
    mark_partnership_read(supabase, partnership_id, profile["id"])

    other_id = partnership["grower_id"] if profile["id"] == partnership["developer_id"] else partnership["developer_id"]
    return render_template(
        "partnerships/detail.html",
        partnership=partnership,
        listing=partnership.get("listings") or {"title": "Your app"},
        messages=messages, profile=profile,
        other_name=people.get(other_id, "your partner"),
        builder_name=people.get(partnership["developer_id"], "Builder"),
        grower_name=people.get(partnership["grower_id"], "Grower"),
        active=partnership["status"] in ACTIVE,
    )


@partnerships_bp.route("/<partnership_id>/messages", methods=["POST"])
@login_required
def send_message(partnership_id):
    profile = current_profile()
    partnership = _get(partnership_id)
    if not _require_party(partnership, profile):
        flash("That conversation isn't available to you.", "error")
        return redirect(url_for("dashboard.index"))
    if partnership["status"] not in ACTIVE:
        flash("This partnership has ended, so messaging is closed.", "error")
        return redirect(url_for("partnerships.detail", partnership_id=partnership_id))

    body = request.form.get("body", "").strip()[:4000]
    if body:
        get_supabase().table("messages").insert({
            "partnership_id": partnership_id,
            "sender_id": profile["id"],
            "body": body,
        }).execute()
    return redirect(url_for("partnerships.detail", partnership_id=partnership_id) + "#latest")


@partnerships_bp.route("/<partnership_id>/end", methods=["GET", "POST"])
@login_required
def end(partnership_id):
    """End the partnership. Works the same whatever its old trial/formalised status."""
    profile = current_profile()
    partnership = _get(partnership_id)
    if not _require_party(partnership, profile):
        flash("That partnership isn't available to you.", "error")
        return redirect(url_for("dashboard.index"))
    if partnership["status"] not in ACTIVE:
        flash("This partnership has already ended.", "error")
        return redirect(url_for("plans.view", partnership_id=partnership_id))

    if request.method == "POST":
        reason = request.form.get("end_reason", "").strip()[:1000]
        if not reason:
            flash("Please give a short reason. Your partner will see it.", "error")
            return render_template("partnerships/end.html", partnership=partnership,
                                   listing=partnership.get("listings") or {"title": "Your app"})
        get_supabase().table("partnerships").update({
            "status": "ended",
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "ended_by": profile["id"],
            "end_reason": reason,
        }).eq("id", partnership_id).execute()
        flash("The partnership has ended. Its plan and ledger stay available to you both, read-only.", "success")
        return redirect(url_for("plans.view", partnership_id=partnership_id))

    return render_template("partnerships/end.html", partnership=partnership,
                           listing=partnership.get("listings") or {"title": "Your app"})


# ---------- retired steps: old addresses lead somewhere sensible ----------

@partnerships_bp.route("/<partnership_id>/disconnect", methods=["GET", "POST"])
@login_required
def disconnect(partnership_id):
    return redirect(url_for("partnerships.end", partnership_id=partnership_id))


@partnerships_bp.route("/<partnership_id>/formalise/propose", methods=["POST"])
@partnerships_bp.route("/<partnership_id>/formalise/accept", methods=["POST"])
@partnerships_bp.route("/<partnership_id>/formalise/decline", methods=["POST"])
@partnerships_bp.route("/<partnership_id>/revenue-terms", methods=["GET", "POST"])
@login_required
def retired(partnership_id):
    flash("That step has been replaced by the CrescoPlan: agree a version together instead.", "success")
    return redirect(url_for("plans.view", partnership_id=partnership_id))
