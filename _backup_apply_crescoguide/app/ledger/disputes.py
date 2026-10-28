"""CrescoLedger disputes and entry history.

A dispute covers one or more entries. While it's open those entries are
locked (the database enforces this) but still count in the totals, flagged.
Both people give their account, either can ask for a neutral AI summary
(3 free per account, then premium), and either can propose a resolution
the other agrees. An agreed resolution is applied straight away: keep,
correct the amount or hours, void, or change Recoverable / Goodwill.
The raiser can withdraw; either can close it as unresolved once the other
has said nothing for 14 days.
"""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import render_template, request, redirect, url_for, flash, abort

from app.extensions import get_supabase, get_supabase_admin
from app.utils import login_required
from app.ledger import ai_summary
from app.ledger.routes import ledger_bp, _load, _money, _rpc_error, _call, CLASSES

FREE_SUMMARIES = int(os.environ.get("AI_FREE_SUMMARIES", "3"))
SUMMARIES_PER_DISPUTE = 3
QUIET_DAYS = 14
DISPUTE_STATUS = {"open": "Open", "resolved": "Resolved", "unresolved": "Closed without agreement",
                  "withdrawn": "Withdrawn"}
ACTIONS = [("keep", "Keep as it is"), ("correct", "Correct it"), ("void", "Void it"), ("class", "Change class")]
EVENT_LABELS = {
    "added": "Added", "edited": "Edited", "confirmed": "Confirmed", "queried": "Queried",
    "reclassified": "Changed class", "class_change_asked": "Asked to make Recoverable",
    "class_change_cleared": "Change of class cancelled or declined", "priced": "Priced at the agreed rate",
    "corrected": "Corrected by agreed dispute resolution", "voided": "Voided by agreed dispute resolution",
    "deleted": "Deleted",
}


def _parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


@ledger_bp.app_template_filter("ai_summary")
def ai_summary_filter(text):
    """Shows every AI summary conversationally, including older ones stored as JSON."""
    return ai_summary.tidy(text)


@ledger_bp.app_template_filter("event_detail")
def event_detail(detail, currency="GBP"):
    """{'amount_from': 240, 'amount_to': 160} -> 'amount 240.00 → 160.00' (plain words for history)."""
    detail = detail or {}
    bits = []
    if "amount_from" in detail:
        bits.append(f"amount {float(detail['amount_from']):,.2f} → {float(detail['amount_to']):,.2f} {currency}")
    elif detail.get("amount") is not None:
        bits.append(f"{float(detail['amount']):,.2f} {currency}")
    if "hours_from" in detail:
        bits.append(f"hours {float(detail['hours_from']):g} → {float(detail['hours_to']):g}")
    elif detail.get("hours") is not None:
        bits.append(f"{float(detail['hours']):g} h")
    if "class_from" in detail:
        bits.append(f"{(detail['class_from'] or '').title()} → {(detail['class_to'] or '').title()}")
    elif detail.get("cost_class"):
        bits.append(detail["cost_class"].title())
    if detail.get("rate") is not None:
        bits.append(f"at {float(detail['rate']):,.2f}/h")
    if detail.get("note"):
        bits.append(f"“{detail['note']}”")
    return " · ".join(bits)


def _ai_allowance(supabase, profile_id):
    used = len(supabase.table("ai_usage").select("id").eq("profile_id", profile_id)
               .eq("feature", "dispute_summary").execute().data)
    ent = supabase.table("account_entitlements").select("premium_until").eq("profile_id", profile_id).execute().data
    until = _parse_time(ent[0]["premium_until"]) if ent and ent[0].get("premium_until") else None
    premium = bool(until and until > datetime.now(timezone.utc))
    interested = bool(supabase.table("premium_interest").select("feature").eq("profile_id", profile_id)
                      .eq("feature", "dispute_summary").execute().data)
    return {"used": used, "free": FREE_SUMMARIES, "left": max(FREE_SUMMARIES - used, 0),
            "premium": premium, "can_use": premium or used < FREE_SUMMARIES, "interested": interested}


def _dispute_ctx(partnership_id, dispute_id):
    ctx = _load(partnership_id)
    if not ctx:
        return None
    dispute = next((d for d in ctx["disputes"] if d["id"] == dispute_id), None)
    if not dispute:
        return None
    supabase = get_supabase()
    messages = (supabase.table("ledger_dispute_messages").select("*").eq("dispute_id", dispute_id)
                .order("created_at").execute().data)
    proposals = (supabase.table("ledger_dispute_proposals").select("*").eq("dispute_id", dispute_id)
                 .order("created_at", desc=True).execute().data)
    entries = [ctx["entry_by_id"][i] for i in dispute["entry_ids"] if i in ctx["entry_by_id"]]
    events = (supabase.table("ledger_entry_events").select("*").in_("entry_id", dispute["entry_ids"])
              .order("created_at").execute().data if dispute["entry_ids"] else [])

    me = ctx["profile"]["id"]
    role_of_id = {ctx["partnership"]["developer_id"]: "builder", ctx["partnership"]["grower_id"]: "grower"}
    dispute["raised_role"] = role_of_id.get(dispute.get("raised_by"))
    for m in messages:
        m["role"] = role_of_id.get(m.get("author"))
        m["mine"] = m.get("author") == me
    for pr in proposals:
        pr["mine"] = pr.get("proposed_by") == me
        pr["role"] = role_of_id.get(pr.get("proposed_by"))
        pr["lines"] = []
        for a in pr.get("actions") or []:
            e = ctx["entry_by_id"].get(a.get("entry_id"))
            pr["lines"].append({"entry": e, **a})
    for ev in events:
        ev["role"] = role_of_id.get(ev.get("actor"))
        ev["label"] = EVENT_LABELS.get(ev["event"], ev["event"].replace("_", " ").title())
        ev["entry"] = ctx["entry_by_id"].get(ev["entry_id"])

    # When the other person last did anything (for closing after 14 quiet days).
    times = [_parse_time(dispute["created_at"])]
    times += [_parse_time(m["created_at"]) for m in messages if m.get("author") and m["author"] != me]
    times += [_parse_time(p["created_at"]) for p in proposals if p.get("proposed_by") and p["proposed_by"] != me]
    times += [_parse_time(p["responded_at"]) for p in proposals
              if p.get("responded_by") and p["responded_by"] != me and p.get("responded_at")]
    other_last = max(t for t in times if t)
    can_close_after = other_last + timedelta(days=QUIET_DAYS)
    now = datetime.now(timezone.utc)

    plan_rows = (supabase.table("cresco_plans").select("agreed_needs_html,agreed_offers_html")
                 .eq("partnership_id", partnership_id).execute().data)
    ctx["plan"] = {**ctx["plan"], **(plan_rows[0] if plan_rows else {})}

    summaries_here = sum(1 for m in messages if m["kind"] == "ai_summary")
    ctx.update(
        dispute=dispute, messages=messages, proposals=proposals, disputed=entries, events=events,
        open=dispute["status"] == "open",
        open_proposal=next((p for p in proposals if p["status"] == "proposed"), None),
        i_have_spoken=any(m["mine"] for m in messages),
        can_close=dispute["status"] == "open" and now >= can_close_after,
        close_days_left=max((can_close_after - now).days + 1, 0),
        ai=_ai_allowance(supabase, me), summaries_here=summaries_here,
        summaries_left_here=max(SUMMARIES_PER_DISPUTE - summaries_here, 0),
        dispute_status=DISPUTE_STATUS, actions=ACTIONS, classes=CLASSES,
    )
    return ctx


def _back(partnership_id, dispute_id):
    return redirect(url_for("ledger.dispute_view", partnership_id=partnership_id, dispute_id=dispute_id))


# ---------- pages ----------

@ledger_bp.route("/<partnership_id>/disputes/new", methods=["GET", "POST"])
@login_required
def dispute_new(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        abort(404)
    available = [e for e in ctx["entries"] if not e["voided"] and not e["dispute_id"]]
    chosen = request.values.getlist("entry_ids") or request.args.getlist("entry")
    values = {"entry_ids": [i for i in chosen if i in {e["id"] for e in available}],
              "reason": "", "wanted": ""}
    if request.method == "POST":
        values.update(reason=(request.form.get("reason") or "").strip()[:2000],
                      wanted=(request.form.get("wanted") or "").strip()[:1000])
        errors = []
        if not values["entry_ids"]:
            errors.append("Tick the entries the dispute is about.")
        if not values["reason"]:
            errors.append("Say what you think is wrong.")
        if not request.form.get("consent"):
            errors.append("Please confirm you understand how disputes work.")
        if not errors:
            try:
                new_id = get_supabase().rpc("raise_dispute", {
                    "p_partnership_id": partnership_id, "p_entry_ids": values["entry_ids"],
                    "p_reason": values["reason"], "p_wanted": values["wanted"] or None,
                }).execute().data
                other = ctx["name_of_role"][ctx["other_role"]]
                flash(f"Dispute raised. Those entries are locked until it's settled. {other} can now give their side.",
                      "success")
                return _back(partnership_id, new_id)
            except Exception as err:  # noqa: BLE001
                errors.append(_rpc_error(err))
        for e in errors:
            flash(e, "error")
    return render_template("ledger/dispute_new.html", available=available, values=values, **ctx)


@ledger_bp.route("/<partnership_id>/disputes/<dispute_id>")
@login_required
def dispute_view(partnership_id, dispute_id):
    ctx = _dispute_ctx(partnership_id, dispute_id)
    if not ctx:
        flash("That dispute isn't available to you.", "error")
        return redirect(url_for("ledger.view", partnership_id=partnership_id))
    return render_template("ledger/dispute_view.html", **ctx)


@ledger_bp.route("/<partnership_id>/disputes/<dispute_id>/message", methods=["POST"])
@login_required
def dispute_message(partnership_id, dispute_id):
    body = (request.form.get("body") or "").strip()[:4000]
    if not body:
        flash("Write your message first.", "error")
    else:
        _call("add_dispute_message", {"p_dispute_id": dispute_id, "p_body": body,
                                      "p_evidence_url": (request.form.get("evidence_url") or "").strip()[:500] or None},
              "Added to the dispute.")
    return _back(partnership_id, dispute_id)


@ledger_bp.route("/<partnership_id>/disputes/<dispute_id>/propose", methods=["POST"])
@login_required
def dispute_propose(partnership_id, dispute_id):
    ctx = _dispute_ctx(partnership_id, dispute_id)
    if not ctx:
        abort(404)
    actions, errors = [], []
    for e in ctx["disputed"]:
        act = request.form.get(f"action_{e['id']}") or "keep"
        if act not in dict(ACTIONS):
            act = "keep"
        line = {"entry_id": e["id"], "action": act}
        if act == "correct":
            value = _money(request.form.get(f"value_{e['id']}"))
            if value is None or value <= 0:
                errors.append(f"Enter the corrected {'hours' if e['kind'] == 'time' else 'amount'} for “{e['description']}”.")
            else:
                line["hours" if e["kind"] == "time" else "amount"] = float(value.quantize(Decimal("0.01")))
        elif act == "class":
            if e["kind"] not in ("cost", "time"):
                errors.append(f"“{e['description']}” is revenue, so it has no class to change.")
            else:
                line["cost_class"] = "goodwill" if e.get("cost_class") == "recoverable" else "recoverable"
        actions.append(line)
    if not errors:
        other = ctx["name_of_role"][ctx["other_role"]]
        _call("propose_dispute_resolution", {"p_dispute_id": dispute_id, "p_actions": actions,
                                             "p_note": (request.form.get("note") or "").strip()[:2000] or None},
              f"Proposal sent. If {other} agrees, it's applied to the ledger straight away.")
    for e in errors:
        flash(e, "error")
    return _back(partnership_id, dispute_id)


@ledger_bp.route("/<partnership_id>/disputes/<dispute_id>/proposals/<proposal_id>/respond", methods=["POST"])
@login_required
def dispute_respond(partnership_id, dispute_id, proposal_id):
    agree = request.form.get("answer") == "agree"
    if agree and not request.form.get("consent"):
        flash("Tick the box to confirm you agree, then press Agree.", "error")
        return _back(partnership_id, dispute_id)
    _call("respond_dispute_resolution", {"p_proposal_id": proposal_id, "p_agree": agree},
          "Agreed. The dispute is resolved and the ledger has been updated." if agree
          else "Proposal declined. You can explain why, or propose something else.")
    return _back(partnership_id, dispute_id)


@ledger_bp.route("/<partnership_id>/disputes/<dispute_id>/proposals/<proposal_id>/withdraw", methods=["POST"])
@login_required
def dispute_withdraw_proposal(partnership_id, dispute_id, proposal_id):
    _call("withdraw_dispute_proposal", {"p_proposal_id": proposal_id}, "Proposal withdrawn.")
    return _back(partnership_id, dispute_id)


@ledger_bp.route("/<partnership_id>/disputes/<dispute_id>/withdraw", methods=["POST"])
@login_required
def dispute_withdraw(partnership_id, dispute_id):
    _call("withdraw_dispute", {"p_dispute_id": dispute_id}, "Dispute withdrawn. The entries are unlocked.")
    return _back(partnership_id, dispute_id)


@ledger_bp.route("/<partnership_id>/disputes/<dispute_id>/close", methods=["POST"])
@login_required
def dispute_close(partnership_id, dispute_id):
    _call("close_dispute_unresolved", {"p_dispute_id": dispute_id,
                                       "p_note": (request.form.get("note") or "").strip()[:1000] or None},
          "Dispute closed without agreement. The record stays in the ledger.")
    return _back(partnership_id, dispute_id)


@ledger_bp.route("/<partnership_id>/disputes/<dispute_id>/summary", methods=["POST"])
@login_required
def dispute_summary(partnership_id, dispute_id):
    ctx = _dispute_ctx(partnership_id, dispute_id)
    if not ctx:
        abort(404)
    if not ctx["open"]:
        flash("This dispute is closed.", "error")
    elif not request.form.get("consent"):
        flash("Tick the box to confirm you understand the summary is advisory only.", "error")
    elif not ctx["ai"]["can_use"]:
        flash("You've used your free AI summaries. They'll be part of Crescopus Premium.", "error")
    elif not ctx["summaries_left_here"]:
        flash(f"This dispute has had its {SUMMARIES_PER_DISPUTE} AI summaries.", "error")
    else:
        try:
            prompt = ai_summary.build_prompt(ctx, ctx["dispute"], ctx["disputed"], ctx["messages"], ctx["rates"])
            text = ai_summary.summarise(prompt)
        except ai_summary.SummaryUnavailable as err:
            flash(str(err), "error")
            return _back(partnership_id, dispute_id)
        admin = get_supabase_admin()
        admin.table("ai_usage").insert({"profile_id": ctx["profile"]["id"], "feature": "dispute_summary",
                                        "dispute_id": dispute_id}).execute()
        admin.table("ledger_dispute_messages").insert({"dispute_id": dispute_id, "author": None,
                                                       "kind": "ai_summary", "body": text}).execute()
        left = ctx["ai"]["left"] - 1
        note = "" if ctx["ai"]["premium"] else f" You have {left} free summar{'y' if left == 1 else 'ies'} left."
        flash("Summary added below. It's advisory only." + note, "success")
    return _back(partnership_id, dispute_id)


@ledger_bp.route("/<partnership_id>/premium-interest", methods=["POST"])
@login_required
def premium_interest(partnership_id):
    _call("register_premium_interest", {"p_feature": "dispute_summary"},
          "Thanks, we've noted your interest in Crescopus Premium.")
    back = request.form.get("back") or url_for("ledger.view", partnership_id=partnership_id)
    return redirect(back if back.startswith("/") else url_for("ledger.view", partnership_id=partnership_id))


@ledger_bp.route("/<partnership_id>/<entry_id>/history")
@login_required
def entry_history(partnership_id, entry_id):
    ctx = _load(partnership_id)
    if not ctx or entry_id not in ctx["entry_by_id"]:
        abort(404)
    role_of_id = {ctx["partnership"]["developer_id"]: "builder", ctx["partnership"]["grower_id"]: "grower"}
    events = (get_supabase().table("ledger_entry_events").select("*").eq("entry_id", entry_id)
              .order("created_at").execute().data)
    for ev in events:
        ev["role"] = role_of_id.get(ev.get("actor"))
        ev["label"] = EVENT_LABELS.get(ev["event"], ev["event"].replace("_", " ").title())
    entry_disputes = [d for d in ctx["disputes"] if entry_id in d["entry_ids"]]
    return render_template("ledger/entry_history.html", entry=ctx["entry_by_id"][entry_id], events=events,
                           entry_disputes=entry_disputes, dispute_status=DISPUTE_STATUS, **ctx)
