"""CrescoLedger: the shared record of costs and revenue for one partnership.

All changes go through the database functions from migration_plan_ledger.sql,
so the rules hold even outside this website:
  - either party can add an entry; it starts as "awaiting confirmation"
  - only the OTHER party can confirm or query it
  - the person who added it can edit or delete it until it's confirmed
    (editing sends it back for confirmation)
  - confirmed entries are locked; mistakes are fixed with a correcting entry
Totals only count confirmed entries.

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

KINDS = [("revenue", "Revenue"), ("cost", "Cost")]
PARTIES = [("builder", "Builder"), ("grower", "Grower")]
STATUS_LABELS = {"pending": "Awaiting confirmation", "confirmed": "Confirmed", "queried": "Queried"}
FILTERS = [("all", "All"), ("revenue", "Revenue"), ("cost", "Costs"), ("open", "Not confirmed")]
CURRENCY_CODES = {code for code, _, _ in CURRENCIES}


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

    me_role = "builder" if profile["id"] == p["developer_id"] else "grower"
    role_of = {p["developer_id"]: "builder", p["grower_id"]: "grower"}
    name_of_role = {"builder": people.get(p["developer_id"], "Builder"), "grower": people.get(p["grower_id"], "Grower")}

    for e in entries:
        e["amount_f"] = float(e["amount"])
        e["mine"] = e.get("added_by") == profile["id"]
        e["added_by_role"] = role_of.get(e.get("added_by"))          # None = system (e.g. RevenueCat)
        e["confirmed_by_role"] = role_of.get(e.get("confirmed_by"))
        e["receipt_is_link"] = bool(re.match(r"^https?://", e.get("receipt_url") or ""))
        e["converted"] = bool(e.get("original_currency"))
        e["can_respond"] = (not e["mine"]) and e["status"] in ("pending", "queried") and e.get("added_by")
        e["can_change"] = e["mine"] and e["status"] != "confirmed"

    confirmed = [e for e in entries if e["status"] == "confirmed"]
    revenue = sum(e["amount_f"] for e in confirmed if e["kind"] == "revenue")
    costs = sum(e["amount_f"] for e in confirmed if e["kind"] == "cost")
    open_entries = [e for e in entries if e["status"] != "confirmed"]
    by_party = {
        role: {
            "revenue": sum(e["amount_f"] for e in confirmed if e["party"] == role and e["kind"] == "revenue"),
            "costs": sum(e["amount_f"] for e in confirmed if e["party"] == role and e["kind"] == "cost"),
        } for role in ("builder", "grower")
    }
    dates = sorted(e["entry_date"] for e in entries)
    return {
        "profile": profile, "partnership": p, "plan": plan,
        "currency": plan.get("ledger_currency") or "GBP",
        "listing": p.get("listings") or {"title": "Your app"},
        "builder_name": name_of_role["builder"], "grower_name": name_of_role["grower"],
        "name_of_role": name_of_role, "me_role": me_role,
        "entries": entries,
        "totals": {"revenue": revenue, "costs": costs, "net": revenue - costs,
                   "open_amount": sum(e["amount_f"] for e in open_entries),
                   "open_count": len(open_entries),
                   "to_confirm": sum(1 for e in entries if e["can_respond"] and e["status"] == "pending")},
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
        errors.append("Choose whether this is revenue or a cost.")
    party = form.get("party") or me_role
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

    currency = (form.get("currency") or ledger_currency).upper()
    if currency not in CURRENCY_CODES and currency != ledger_currency:
        errors.append("Choose a currency from the list.")
        currency = ledger_currency
    amount = _money(form.get("amount"))
    if amount is None or amount <= 0 or amount > Decimal("10000000"):
        errors.append("Enter an amount above zero, like 120 or 1,240.50.")
        amount = None
    else:
        amount = amount.quantize(Decimal("0.01"))

    fx_rate = None
    rpc = {"p_amount": str(amount) if amount is not None else None,
           "p_original_amount": None, "p_original_currency": None, "p_fx_rate": None}
    if currency != ledger_currency:
        fx_rate = _money(form.get("fx_rate"))
        if fx_rate is None or fx_rate <= 0 or fx_rate > Decimal("100000"):
            errors.append(f"Enter the exchange rate: how many {ledger_currency} one {currency} is worth.")
            fx_rate = None
        elif amount is not None:
            rpc = {"p_amount": None, "p_original_amount": str(amount),
                   "p_original_currency": currency, "p_fx_rate": str(fx_rate)}

    receipt = (form.get("receipt_url") or "").strip()[:500]
    values = {"kind": kind, "party": party,
              "entry_date": entry_date.isoformat() if entry_date else (form.get("entry_date") or ""),
              "description": description[:300],
              "amount": str(amount) if amount is not None else (form.get("amount") or ""),
              "currency": currency,
              "fx_rate": str(fx_rate) if fx_rate is not None else (form.get("fx_rate") or ""),
              "receipt_url": receipt}
    return values, rpc, errors


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
    if show in ("revenue", "cost"):
        entries = [e for e in entries if e["kind"] == show]
    elif show == "open":
        entries = [e for e in entries if e["status"] != "confirmed"]
    return render_template("ledger/view.html", shown=entries, show=show, filters=FILTERS,
                           status_labels=STATUS_LABELS, currencies=CURRENCIES, **ctx)


@ledger_bp.route("/<partnership_id>/new", methods=["GET", "POST"])
@login_required
def new(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        abort(404)
    if not ctx["active"]:
        flash("This partnership has ended, so new entries can't be added.", "error")
        return redirect(url_for("ledger.view", partnership_id=partnership_id))
    values = {"kind": request.args.get("kind", "cost"), "party": ctx["me_role"],
              "entry_date": date.today().isoformat(), "description": "", "amount": "",
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
                other = ctx["grower_name"] if ctx["me_role"] == "builder" else ctx["builder_name"]
                flash(f"Entry added. It counts in the totals once {other} confirms it.", "success")
                return redirect(url_for("ledger.view", partnership_id=partnership_id))
            except Exception as err:  # noqa: BLE001
                errors = [f"The entry couldn't be saved: {_rpc_error(err)}"]
        for e in errors:
            flash(e, "error")
    return render_template("ledger/entry_form.html", values=values, editing=None,
                           kinds=KINDS, parties=PARTIES, currencies=CURRENCIES, **ctx)


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
    return render_template("ledger/entry_form.html", values=values, editing=entry,
                           kinds=KINDS, parties=PARTIES, currencies=CURRENCIES, **ctx)


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
    w.writerow(["Date", "Type", "Party", "Description", "Amount", "Currency",
                "Original amount", "Original currency", "Exchange rate", "Status",
                "Added by", "Confirmed by", "Confirmed at", "Receipt", "Query note"])
    for e in sorted(ctx["entries"], key=lambda e: (e["entry_date"], e["created_at"])):
        w.writerow([
            e["entry_date"], e["kind"].title(), ctx["name_of_role"][e["party"]], e["description"],
            e["amount"], ctx["currency"],
            e.get("original_amount") or "", e.get("original_currency") or "", e.get("fx_rate") or "",
            STATUS_LABELS.get(e["status"], e["status"]),
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
