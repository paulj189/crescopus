"""CrescoLedger: the shared record of costs and revenue for one partnership.

All changes go through the database functions from migration_plan_ledger.sql,
so the rules hold even outside this website:
  - either party can add an entry; it starts as "awaiting confirmation"
  - only the OTHER party can confirm or query it
  - the person who added it can edit or delete it until it's confirmed
    (editing sends it back for confirmation)
  - confirmed entries are locked; mistakes are fixed with a correcting entry
Totals only count confirmed entries.

Time: each person logs their own hours. They're valued at the hourly rate
agreed for that date (proposed by the person, agreed by the other). With no
agreed rate they're saved at zero and shown as "rate pending".

Goodwill / Recoverable: every cost and time entry has a class. Goodwill counts
towards a person's contribution but never towards what's outstanding. Nothing
is recovered automatically: either party proposes a recovery settlement and
the other agrees it.

Currencies: each ledger has one currency, which can only be changed while the
ledger is empty. An entry can be made in another currency; it then keeps the
original amount and currency and the exchange rate, and its amount is the
converted figure (worked out in the database). The form suggests the rate for
the entry's date from the European Central Bank's published rates.
"""
import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import time

import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response, jsonify

from app.extensions import get_supabase
from app.utils import login_required, current_profile
from app.constants import CURRENCIES, CURRENCY_SYMBOLS

ledger_bp = Blueprint("ledger", __name__, url_prefix="/ledger")

KINDS = [("revenue", "Revenue"), ("cost", "Cost"), ("time", "Time")]
CLASSES = [("recoverable", "Recoverable"), ("goodwill", "Goodwill")]
CLASS_HELP = {"recoverable": "Can be recovered later, if you both agree how.",
              "goodwill": "Not to be recovered, but counted as your contribution."}
PARTIES = [("builder", "Builder"), ("grower", "Grower")]
STATUS_LABELS = {"pending": "Awaiting confirmation", "confirmed": "Confirmed", "queried": "Queried"}
FILTERS = [("all", "All"), ("revenue", "Revenue"), ("cost", "Costs"), ("time", "Time"),
           ("goodwill", "Goodwill"), ("open", "Not confirmed"), ("disputed", "In dispute")]
RATE_STATUS = {"proposed": "Waiting", "agreed": "Agreed", "declined": "Declined", "withdrawn": "Withdrawn"}
CURRENCY_CODES = {code for code, _, _ in CURRENCIES}


@ledger_bp.app_template_filter("hours")
def hours_filter(value):
    """7.5 -> '7.5 h', 10.00 -> '10 h'."""
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return ""
    return f"{n:,.2f}".rstrip("0").rstrip(".") + " h"


def _rpc_error(err):
    msg = getattr(err, "message", None) or str(err)
    if err.args and isinstance(err.args[0], dict):
        msg = err.args[0].get("message", msg)
    return msg


def _load(partnership_id):
    """Partnership, the two people, the plan's currency and all entries.
    None if the viewer isn't one of the two parties."""
    profile = current_profile()
    supabase = get_supabase()
    rows = (supabase.table("partnerships")
            .select("id,status,developer_id,grower_id,listings(title),cresco_plans(id,ledger_currency)")
            .eq("id", partnership_id).execute().data)
    if not rows or not profile or profile["id"] not in (rows[0]["developer_id"], rows[0]["grower_id"]):
        return None
    p = rows[0]
    plan = p.get("cresco_plans")
    plan = (plan[0] if plan else {}) if isinstance(plan, list) else (plan or {})
    people = {r["id"]: r["full_name"] for r in (supabase.table("profiles").select("id,full_name")
              .in_("id", [p["developer_id"], p["grower_id"]]).execute().data)}
    entries = (supabase.table("ledger_entries").select("*")
               .eq("partnership_id", partnership_id)
               .order("entry_date", desc=True).order("created_at", desc=True).execute().data)

    rates = (supabase.table("plan_rates").select("*").eq("partnership_id", partnership_id)
             .order("created_at", desc=True).execute().data)
    settlements = (supabase.table("recovery_settlements").select("*,recovery_settlement_entries(entry_id)")
                   .eq("partnership_id", partnership_id)
                   .order("settled_on", desc=True).order("created_at", desc=True).execute().data)

    disputes = (supabase.table("ledger_disputes").select("*").eq("partnership_id", partnership_id)
                .order("created_at", desc=True).execute().data)
    d_ids = [d["id"] for d in disputes]
    d_entries = (supabase.table("ledger_dispute_entries").select("*").in_("dispute_id", d_ids).execute().data
                 if d_ids else [])
    d_open_props = (supabase.table("ledger_dispute_proposals").select("dispute_id,proposed_by")
                    .in_("dispute_id", d_ids).eq("status", "proposed").execute().data if d_ids else [])
    d_authors = (supabase.table("ledger_dispute_messages").select("dispute_id,author")
                 .in_("dispute_id", d_ids).execute().data if d_ids else [])

    me_role = "builder" if profile["id"] == p["developer_id"] else "grower"
    role_of = {p["developer_id"]: "builder", p["grower_id"]: "grower"}
    name_of_role = {"builder": people.get(p["developer_id"], "Builder"), "grower": people.get(p["grower_id"], "Grower")}

    open_ids = {d["id"] for d in disputes if d["status"] == "open"}
    open_dispute_of = {x["entry_id"]: x["dispute_id"] for x in d_entries if x["dispute_id"] in open_ids}
    entries_of = {}
    for x in d_entries:
        entries_of.setdefault(x["dispute_id"], []).append(x["entry_id"])
    for d in disputes:
        d["entry_ids"] = entries_of.get(d["id"], [])
        d["mine"] = d.get("raised_by") == profile["id"]
        spoke = {m["author"] for m in d_authors if m["dispute_id"] == d["id"]}
        their_prop = any(x["dispute_id"] == d["id"] and x["proposed_by"] != profile["id"] for x in d_open_props)
        d["needs_me"] = d["status"] == "open" and (their_prop or profile["id"] not in spoke)

    for e in entries:
        e["amount_f"] = float(e["amount"])
        e["mine"] = e.get("added_by") == profile["id"]
        e["added_by_role"] = role_of.get(e.get("added_by"))          # None = system (e.g. RevenueCat)
        e["confirmed_by_role"] = role_of.get(e.get("confirmed_by"))
        e["receipt_is_link"] = bool(re.match(r"^https?://", e.get("receipt_url") or ""))
        e["converted"] = bool(e.get("original_currency"))
        e["voided"] = bool(e.get("voided_at"))
        e["dispute_id"] = open_dispute_of.get(e["id"])
        e["locked"] = e["voided"] or bool(e["dispute_id"])
        e["can_respond"] = ((not e["mine"]) and e["status"] in ("pending", "queried") and e.get("added_by")
                            and not e["locked"])
        e["can_change"] = e["mine"] and e["status"] != "confirmed" and not e["locked"]
        e["hours_f"] = float(e["hours"]) if e.get("hours") is not None else None
        e["rate_pending"] = e["kind"] == "time" and e.get("hourly_rate") is None
        e["my_cost"] = e["kind"] in ("cost", "time") and e["party"] == me_role and not e["locked"]
        e["class_asked_by_me"] = bool(e.get("class_change_to")) and e.get("class_change_by") == profile["id"]
        e["class_to_answer"] = (bool(e.get("class_change_to")) and e.get("class_change_by") != profile["id"]
                                and not e["locked"])

    confirmed = [e for e in entries if e["status"] == "confirmed" and not e["voided"]]
    revenue = sum(e["amount_f"] for e in confirmed if e["kind"] == "revenue")
    costs = sum(e["amount_f"] for e in confirmed if e["kind"] == "cost")
    time_value = sum(e["amount_f"] for e in confirmed if e["kind"] == "time")
    time_hours = sum(e["hours_f"] for e in confirmed if e["kind"] == "time")
    open_entries = [e for e in entries if e["status"] != "confirmed" and not e["voided"]]

    for s in settlements:
        s["amount_f"] = float(s["amount"])
        s["entry_ids"] = [x["entry_id"] for x in (s.get("recovery_settlement_entries") or [])]
        s["mine"] = s["proposed_by"] == profile["id"]
        s["can_respond"] = s["status"] == "proposed" and not s["mine"]
        s["can_withdraw"] = s["status"] == "proposed" and s["mine"]

    def _sum(role, kind, cls):
        return sum(e["amount_f"] for e in confirmed
                   if e["party"] == role and e["kind"] == kind and e.get("cost_class") == cls)

    by_party = {}
    for role in ("builder", "grower"):
        mine = [e for e in confirmed if e["party"] == role]
        row = {
            "revenue": sum(e["amount_f"] for e in mine if e["kind"] == "revenue"),
            "costs": sum(e["amount_f"] for e in mine if e["kind"] == "cost"),
            "rec_cash": _sum(role, "cost", "recoverable"), "rec_time": _sum(role, "time", "recoverable"),
            "gw_cash": _sum(role, "cost", "goodwill"), "gw_time": _sum(role, "time", "goodwill"),
            "hours": sum(e["hours_f"] for e in mine if e["kind"] == "time"),
            "recovered": sum(s["amount_f"] for s in settlements if s["party"] == role and s["status"] == "agreed"),
            "rate_pending_hours": sum(e["hours_f"] for e in entries
                                      if e["party"] == role and e["rate_pending"] and not e["voided"]),
            "rate_pending_count": sum(1 for e in entries if e["party"] == role and e["rate_pending"] and not e["voided"]),
        }
        row["recoverable"] = row["rec_cash"] + row["rec_time"]
        row["goodwill"] = row["gw_cash"] + row["gw_time"]
        row["contribution"] = row["recoverable"] + row["goodwill"]
        row["outstanding"] = row["recoverable"] - row["recovered"]
        by_party[role] = row

    today = date.today().isoformat()
    rate_info = {}
    for role in ("builder", "grower"):
        mine = [r for r in rates if r["party"] == role]
        agreed = sorted((r for r in mine if r["status"] == "agreed"),
                        key=lambda r: (r["effective_from"] or "", r["responded_at"] or ""), reverse=True)
        current = next((r for r in agreed if (r["effective_from"] or "") <= today), None)
        open_rate = next((r for r in mine if r["status"] == "proposed"), None)
        if open_rate:
            open_rate["mine"] = open_rate["proposed_by"] == profile["id"]
        rate_info[role] = {"current": current, "open": open_rate,
                           "history": [r for r in mine if r is not open_rate]}

    to_answer = (sum(1 for e in entries if e["class_to_answer"])
                 + sum(1 for r in rates if r["status"] == "proposed" and r["proposed_by"] != profile["id"])
                 + sum(1 for s in settlements if s["can_respond"])
                 + sum(1 for d in disputes if d["needs_me"]))

    dates = sorted(e["entry_date"] for e in entries)
    return {
        "profile": profile, "partnership": p, "plan": plan,
        "currency": plan.get("ledger_currency") or "GBP",
        "listing": p.get("listings") or {"title": "Your app"},
        "builder_name": name_of_role["builder"], "grower_name": name_of_role["grower"],
        "name_of_role": name_of_role, "me_role": me_role,
        "other_role": "grower" if me_role == "builder" else "builder",
        "entries": entries, "rates": rate_info, "settlements": settlements, "disputes": disputes,
        "entry_by_id": {e["id"]: e for e in entries},
        "totals": {"revenue": revenue, "costs": costs, "net": revenue - costs,
                   "time_value": time_value, "time_hours": time_hours,
                   "open_amount": sum(e["amount_f"] for e in open_entries),
                   "open_count": len(open_entries),
                   "to_confirm": sum(1 for e in entries if e["can_respond"] and e["status"] == "pending"),
                   "to_answer": to_answer,
                   "in_dispute": sum(1 for e in entries if e["dispute_id"])},
        "by_party": by_party,
        "period": (dates[0], dates[-1]) if dates else None,
        "active": p["status"] in ("trial", "formalised"),
    }


def _money(raw):
    raw = re.sub(r"[£$€¥₹,\s]|[A-Za-z]", "", raw or "")
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() else None


def _parse_form(form, me_role, ledger_currency):
    """Validate the add/edit form. Returns (values, rpc_amounts, errors)."""
    errors = []
    kind = form.get("kind")
    if kind not in dict(KINDS):
        errors.append("Choose revenue, a cost or time.")
    party = me_role if kind == "time" else (form.get("party") or me_role)
    if party not in dict(PARTIES):
        errors.append("Choose who received the revenue or paid the cost.")
    try:
        entry_date = date.fromisoformat(form.get("entry_date") or "")
    except ValueError:
        entry_date = None
        errors.append("Add the date.")
    description = (form.get("description") or "").strip()
    if not description:
        errors.append("Add a short description.")
    cost_class = form.get("cost_class") or "recoverable"
    if kind in ("cost", "time") and cost_class not in dict(CLASSES):
        errors.append("Choose Recoverable or Goodwill.")
        cost_class = "recoverable"

    currency = (form.get("currency") or ledger_currency).upper()
    amount = hours = fx_rate = None
    rpc = {"p_amount": None, "p_original_amount": None, "p_original_currency": None, "p_fx_rate": None,
           "p_cost_class": cost_class if kind in ("cost", "time") else None, "p_hours": None}

    if kind == "time":
        currency = ledger_currency
        hours = _money(form.get("hours"))
        if hours is None or hours <= 0 or hours > Decimal("10000"):
            errors.append("Enter the hours, like 3 or 7.5.")
            hours = None
        else:
            hours = hours.quantize(Decimal("0.01"))
            rpc["p_hours"] = str(hours)
    else:
        if currency not in CURRENCY_CODES and currency != ledger_currency:
            errors.append("Choose a currency from the list.")
            currency = ledger_currency
        amount = _money(form.get("amount"))
        if amount is None or amount <= 0 or amount > Decimal("10000000"):
            errors.append("Enter an amount above zero, like 120 or 1,240.50.")
            amount = None
        else:
            amount = amount.quantize(Decimal("0.01"))
            rpc["p_amount"] = str(amount)
        if currency != ledger_currency:
            fx_rate = _money(form.get("fx_rate"))
            if fx_rate is None or fx_rate <= 0 or fx_rate > Decimal("100000"):
                errors.append(f"Enter the exchange rate: how many {ledger_currency} one {currency} is worth.")
                fx_rate = None
            elif amount is not None:
                rpc.update(p_amount=None, p_original_amount=str(amount),
                           p_original_currency=currency, p_fx_rate=str(fx_rate))

    receipt = (form.get("receipt_url") or "").strip()[:500]
    values = {"kind": kind, "party": party,
              "entry_date": entry_date.isoformat() if entry_date else (form.get("entry_date") or ""),
              "description": description[:300],
              "amount": str(amount) if amount is not None else (form.get("amount") or ""),
              "hours": str(hours) if hours is not None else (form.get("hours") or ""),
              "cost_class": cost_class,
              "currency": currency,
              "fx_rate": str(fx_rate) if fx_rate is not None else (form.get("fx_rate") or ""),
              "receipt_url": receipt}
    return values, rpc, errors


def _form_context(ctx):
    return dict(kinds=KINDS, parties=PARTIES, classes=CLASSES, class_help=CLASS_HELP,
                currencies=CURRENCIES, my_rate=ctx["rates"][ctx["me_role"]]["current"], **ctx)


def _back(partnership_id, anchor=None):
    url = url_for("ledger.view", partnership_id=partnership_id)
    return redirect(url + (f"#{anchor}" if anchor else ""))


def _call(fn, params, ok_message):
    """Run a database function; flash its result. Returns the data or None."""
    try:
        data = get_supabase().rpc(fn, params).execute().data
        if ok_message:
            flash(ok_message, "success")
        return data if data is not None else True
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
        return None


# ---------- pages ----------

@ledger_bp.route("/<partnership_id>")
@login_required
def view(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        flash("That ledger isn't available to you.", "error")
        return redirect(url_for("plans.index"))
    show = request.args.get("show", "all")
    if show not in dict(FILTERS):
        show = "all"
    entries = ctx["entries"]
    if show in ("revenue", "cost", "time"):
        entries = [e for e in entries if e["kind"] == show]
    elif show == "goodwill":
        entries = [e for e in entries if e.get("cost_class") == "goodwill"]
    elif show == "open":
        entries = [e for e in entries if e["status"] != "confirmed" and not e["voided"]]
    elif show == "disputed":
        entries = [e for e in entries if e["dispute_id"]]
    return render_template("ledger/view.html", shown=entries, show=show, filters=FILTERS,
                           status_labels=STATUS_LABELS, currencies=CURRENCIES, rate_status=RATE_STATUS,
                           today=date.today().isoformat(), **ctx)


@ledger_bp.route("/<partnership_id>/new", methods=["GET", "POST"])
@login_required
def new(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        abort(404)
    if not ctx["active"]:
        flash("This partnership has ended, so new entries can't be added.", "error")
        return redirect(url_for("ledger.view", partnership_id=partnership_id))
    kind = request.args.get("kind", "cost")
    values = {"kind": kind if kind in dict(KINDS) else "cost", "party": ctx["me_role"],
              "entry_date": date.today().isoformat(), "description": "", "amount": "", "hours": "",
              "cost_class": request.args.get("class") if request.args.get("class") in dict(CLASSES) else "recoverable",
              "currency": ctx["currency"], "fx_rate": "", "receipt_url": ""}
    if request.method == "POST":
        values, amounts, errors = _parse_form(request.form, ctx["me_role"], ctx["currency"])
        if not errors:
            try:
                get_supabase().rpc("add_ledger_entry", {
                    "p_partnership_id": partnership_id, "p_entry_date": values["entry_date"],
                    "p_kind": values["kind"], "p_party": values["party"],
                    "p_description": values["description"],
                    "p_receipt_url": values["receipt_url"], **amounts,
                }).execute()
                other = ctx["name_of_role"][ctx["other_role"]]
                note = ""
                if values["kind"] == "time" and not ctx["rates"][ctx["me_role"]]["current"]:
                    note = " It's at zero for now, until you agree an hourly rate."
                flash(f"Entry added. It counts in the totals once {other} confirms it.{note}", "success")
                return redirect(url_for("ledger.view", partnership_id=partnership_id))
            except Exception as err:  # noqa: BLE001
                errors = [f"The entry couldn't be saved: {_rpc_error(err)}"]
        for e in errors:
            flash(e, "error")
    return render_template("ledger/entry_form.html", values=values, editing=None, **_form_context(ctx))


@ledger_bp.route("/<partnership_id>/<entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit(partnership_id, entry_id):
    ctx = _load(partnership_id)
    if not ctx:
        abort(404)
    entry = next((e for e in ctx["entries"] if e["id"] == entry_id), None)
    if not entry or not entry["can_change"]:
        flash("Only the person who added an entry can change it, and only before it's confirmed.", "error")
        return redirect(url_for("ledger.view", partnership_id=partnership_id))
    values = {k: entry.get(k) or "" for k in ("kind", "party", "entry_date", "description", "receipt_url")}
    values.update(cost_class=entry.get("cost_class") or "recoverable",
                  hours=entry.get("hours") or "")
    if entry["converted"]:
        values.update(amount=entry["original_amount"], currency=entry["original_currency"], fx_rate=entry["fx_rate"])
    else:
        values.update(amount=entry["amount"], currency=ctx["currency"], fx_rate="")
    if request.method == "POST":
        if request.form.get("delete"):
            try:
                get_supabase().rpc("delete_ledger_entry", {"p_entry_id": entry_id}).execute()
                flash("Entry deleted.", "success")
            except Exception as err:  # noqa: BLE001
                flash(_rpc_error(err), "error")
            return redirect(url_for("ledger.view", partnership_id=partnership_id))
        values, amounts, errors = _parse_form(request.form, ctx["me_role"], ctx["currency"])
        if not errors:
            try:
                get_supabase().rpc("edit_ledger_entry", {
                    "p_entry_id": entry_id, "p_entry_date": values["entry_date"],
                    "p_kind": values["kind"], "p_party": values["party"],
                    "p_description": values["description"],
                    "p_receipt_url": values["receipt_url"], **amounts,
                }).execute()
                flash("Entry updated and sent back for confirmation.", "success")
                return redirect(url_for("ledger.view", partnership_id=partnership_id))
            except Exception as err:  # noqa: BLE001
                errors = [f"The entry couldn't be saved: {_rpc_error(err)}"]
        for e in errors:
            flash(e, "error")
    return render_template("ledger/entry_form.html", values=values, editing=entry, **_form_context(ctx))


@ledger_bp.route("/<partnership_id>/<entry_id>/confirm", methods=["POST"])
@login_required
def confirm(partnership_id, entry_id):
    try:
        get_supabase().rpc("confirm_ledger_entry", {"p_entry_id": entry_id}).execute()
        flash("Entry confirmed.", "success")
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
    return redirect(url_for("ledger.view", partnership_id=partnership_id))


@ledger_bp.route("/<partnership_id>/<entry_id>/query", methods=["POST"])
@login_required
def query(partnership_id, entry_id):
    note = (request.form.get("note") or "").strip()[:500]
    if not note:
        flash("Add a short note saying what needs checking.", "error")
        return redirect(url_for("ledger.view", partnership_id=partnership_id))
    try:
        get_supabase().rpc("query_ledger_entry", {"p_entry_id": entry_id, "p_note": note}).execute()
        flash("Query sent. The entry stays out of the totals until it's sorted.", "success")
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
    return redirect(url_for("ledger.view", partnership_id=partnership_id))


@ledger_bp.route("/<partnership_id>/export.csv")
@login_required
def export(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        abort(404)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Type", "Party", "Description", "Class", "Hours", "Hourly rate", "Amount", "Currency",
                "Original amount", "Original currency", "Exchange rate", "Status",
                "Added by", "Confirmed by", "Confirmed at", "Receipt", "Query note"])
    for e in sorted(ctx["entries"], key=lambda e: (e["entry_date"], e["created_at"])):
        w.writerow([
            e["entry_date"], e["kind"].title(), ctx["name_of_role"][e["party"]], e["description"],
            (e.get("cost_class") or "").title(), e.get("hours") or "",
            ("Rate pending" if e["rate_pending"] else e.get("hourly_rate") or ""),
            e["amount"], ctx["currency"],
            e.get("original_amount") or "", e.get("original_currency") or "", e.get("fx_rate") or "",
            ("Void" if e["voided"] else STATUS_LABELS.get(e["status"], e["status"]))
            + (" (in dispute)" if e["dispute_id"] else ""),
            ctx["name_of_role"].get(e["added_by_role"], "System") if e["added_by_role"] else "System",
            ctx["name_of_role"].get(e["confirmed_by_role"], "") if e["confirmed_by_role"] else "",
            (e.get("confirmed_at") or "")[:10], e.get("receipt_url") or "", e.get("query_note") or "",
        ])
    name = re.sub(r"[^A-Za-z0-9]+", "-", ctx["listing"]["title"]).strip("-") or "ledger"
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="CrescoLedger-{name}-{date.today().isoformat()}.csv"'})


@ledger_bp.route("/<partnership_id>/currency", methods=["POST"])
@login_required
def set_currency(partnership_id):
    """Change the ledger currency. Only allowed while the ledger has no entries."""
    code = (request.form.get("currency") or "").upper()
    if code not in CURRENCY_CODES:
        flash("Choose a currency from the list.", "error")
    else:
        try:
            get_supabase().rpc("set_ledger_currency", {"p_partnership_id": partnership_id, "p_currency": code}).execute()
            flash(f"This ledger now uses {code}.", "success")
        except Exception as err:  # noqa: BLE001
            flash(_rpc_error(err), "error")
    return redirect(url_for("ledger.view", partnership_id=partnership_id))


# ---------- Goodwill / Recoverable ----------

@ledger_bp.route("/<partnership_id>/<entry_id>/class", methods=["POST"])
@login_required
def set_class(partnership_id, entry_id):
    cls = request.form.get("cost_class")
    if cls not in dict(CLASSES):
        flash("Choose Recoverable or Goodwill.", "error")
        return _back(partnership_id)
    result = _call("set_cost_class", {"p_entry_id": entry_id, "p_class": cls}, None)
    if result == "requested":
        flash("Asked your partner to agree this is Recoverable. It stays Goodwill until they do.", "success")
    elif result:
        flash("Marked as Goodwill." if cls == "goodwill" else "Updated.", "success")
    return _back(partnership_id, f"e-{entry_id}")


@ledger_bp.route("/<partnership_id>/<entry_id>/class/respond", methods=["POST"])
@login_required
def respond_class(partnership_id, entry_id):
    agree = request.form.get("answer") == "agree"
    _call("respond_class_change", {"p_entry_id": entry_id, "p_agree": agree},
          "Agreed: it's now Recoverable." if agree else "Declined: it stays Goodwill.")
    return _back(partnership_id, f"e-{entry_id}")


# ---------- hourly rates ----------

@ledger_bp.route("/<partnership_id>/rates", methods=["POST"])
@login_required
def propose_rate(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        abort(404)
    value = _money(request.form.get("hourly_rate"))
    choice = request.form.get("apply")
    if value is None or value <= 0 or value > Decimal("100000"):
        flash("Enter an hourly rate above zero, like 40 or 62.50.", "error")
    elif choice not in ("pending", "today"):
        flash("Choose whether the rate applies to your time logged at zero.", "error")
    else:
        other = ctx["name_of_role"][ctx["other_role"]]
        _call("propose_rate", {"p_partnership_id": partnership_id,
                               "p_hourly_rate": str(value.quantize(Decimal("0.01"))),
                               "p_apply_to_pending": choice == "pending",
                               "p_note": (request.form.get("note") or "").strip()[:300]},
              f"Rate proposed. It applies once {other} agrees it.")
    return _back(partnership_id, "rates")


@ledger_bp.route("/<partnership_id>/rates/<rate_id>/respond", methods=["POST"])
@login_required
def respond_rate(partnership_id, rate_id):
    agree = request.form.get("answer") == "agree"
    priced = _call("respond_rate", {"p_rate_id": rate_id, "p_agree": agree}, None)
    if priced is not None:
        if not agree:
            flash("Rate declined. They can propose another.", "success")
        elif isinstance(priced, int) and priced:
            flash(f"Rate agreed. {priced} time entr{'y' if priced == 1 else 'ies'} logged at zero now use it.", "success")
        else:
            flash("Rate agreed. It applies to time from today.", "success")
    return _back(partnership_id, "rates")


@ledger_bp.route("/<partnership_id>/rates/<rate_id>/withdraw", methods=["POST"])
@login_required
def withdraw_rate(partnership_id, rate_id):
    _call("withdraw_rate", {"p_rate_id": rate_id}, "Rate withdrawn.")
    return _back(partnership_id, "rates")


# ---------- recovery settlements ----------

@ledger_bp.route("/<partnership_id>/recovery/new", methods=["GET", "POST"])
@login_required
def new_recovery(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        abort(404)
    party = request.values.get("party") or ctx["me_role"]
    if party not in dict(PARTIES):
        party = ctx["me_role"]
    eligible = [e for e in ctx["entries"] if e["status"] == "confirmed" and e["party"] == party
                and e["kind"] in ("cost", "time") and e.get("cost_class") == "recoverable" and not e["locked"]]
    values = {"party": party, "amount": "", "settled_on": date.today().isoformat(), "note": "", "entry_ids": []}

    if request.method == "POST":
        errors = []
        amount = _money(request.form.get("amount"))
        if amount is None or amount <= 0:
            errors.append("Enter the amount recovered.")
        try:
            settled_on = date.fromisoformat(request.form.get("settled_on") or "")
        except ValueError:
            settled_on = None
            errors.append("Add the date it was settled.")
        ids = [i for i in request.form.getlist("entry_ids") if i in {e["id"] for e in eligible}]
        values.update(amount=request.form.get("amount") or "", note=(request.form.get("note") or "").strip()[:500],
                      settled_on=request.form.get("settled_on") or "", entry_ids=ids)
        if not errors:
            other = ctx["name_of_role"][ctx["other_role"]]
            ok = _call("propose_recovery", {
                "p_partnership_id": partnership_id, "p_party": party,
                "p_amount": str(amount.quantize(Decimal("0.01"))), "p_settled_on": settled_on.isoformat(),
                "p_note": values["note"], "p_entry_ids": ids,
            }, f"Settlement recorded. It reduces what's outstanding once {other} agrees it.")
            if ok:
                return _back(partnership_id, "recovery")
        for e in errors:
            flash(e, "error")

    return render_template("ledger/recovery_form.html", values=values, eligible=eligible,
                           outstanding=ctx["by_party"][party]["outstanding"], parties=PARTIES, **ctx)


@ledger_bp.route("/<partnership_id>/recovery/<settlement_id>/respond", methods=["POST"])
@login_required
def respond_recovery(partnership_id, settlement_id):
    agree = request.form.get("answer") == "agree"
    _call("respond_recovery", {"p_settlement_id": settlement_id, "p_agree": agree},
          "Settlement agreed." if agree else "Settlement declined.")
    return _back(partnership_id, "recovery")


@ledger_bp.route("/<partnership_id>/recovery/<settlement_id>/withdraw", methods=["POST"])
@login_required
def withdraw_recovery(partnership_id, settlement_id):
    _call("withdraw_recovery", {"p_settlement_id": settlement_id}, "Settlement withdrawn.")
    return _back(partnership_id, "recovery")


# ---------- exchange-rate suggestions ----------
# Rates come from the European Central Bank via the free Frankfurter service.
# They're only a suggestion: the person adding the entry can change the rate,
# and the other person confirms it along with the entry.

_RATE_CACHE = {}          # (from, to, date) -> (rate, rate_date, fetched_at)
RATE_SOURCES = ["https://api.frankfurter.app/{date}?from={src}&to={dst}",
                "https://api.frankfurter.dev/v1/{date}?base={src}&symbols={dst}"]


@ledger_bp.route("/rate")
@login_required
def rate_lookup():
    src = (request.args.get("from") or "").upper()
    dst = (request.args.get("to") or "").upper()
    if src not in CURRENCY_CODES or dst not in CURRENCY_CODES:
        return jsonify(error="Unknown currency"), 400
    try:
        when = date.fromisoformat(request.args.get("date") or "")
    except ValueError:
        when = date.today()
    when = min(when, date.today())
    if src == dst:
        return jsonify(rate=1, date=when.isoformat())

    key = (src, dst, when.isoformat())
    cached = _RATE_CACHE.get(key)
    if cached and time.time() - cached[2] < 6 * 3600:
        return jsonify(rate=cached[0], date=cached[1], source="European Central Bank")

    for url in RATE_SOURCES:
        try:
            r = requests.get(url.format(date=when.isoformat(), src=src, dst=dst), timeout=5)
            if r.ok:
                data = r.json()
                value = (data.get("rates") or {}).get(dst)
                if value:
                    _RATE_CACHE[key] = (value, data.get("date", when.isoformat()), time.time())
                    return jsonify(rate=value, date=data.get("date", when.isoformat()), source="European Central Bank")
        except (requests.RequestException, ValueError):
            continue
    return jsonify(error="No rate available right now. Enter the rate from your bank statement."), 503


# Disputes and entry history live in their own module but share this blueprint.
from app.ledger import disputes as _disputes  # noqa: E402,F401
