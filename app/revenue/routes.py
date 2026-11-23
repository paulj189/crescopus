"""Revenue agreement: how the Builder and Grower share the app's revenue.

Crescopus never holds or moves money. This records the terms both people
agree; revenue stays in the Builder's own store and payment accounts and the
Builder pays the Grower directly.

Writes go through the database functions in sql/migration_revenue_agreement.sql
(save_revenue_agreement, agree_revenue_agreement), so the rules hold in the
database: only the two parties can change it, every save is a new version,
saving counts as the saver agreeing, and it's agreed when both have agreed the
current version.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.extensions import get_supabase
from app.utils import login_required, current_profile
from app.constants import CURRENCY_SYMBOLS

revenue_bp = Blueprint("revenue", __name__, url_prefix="/revenue")

BASES = {
    "gross": ("Gross revenue", "What customers pay, less refunds. The builder pays store and payment fees out of their share."),
    "net": ("Net revenue", "What actually reaches the builder after App Store, Play and payment fees, less refunds. The usual choice."),
    "profit": ("Profit", "Net revenue less running costs (hosting, tools, ads) that you've both confirmed in the CrescoLedger."),
}
FREQS = {"monthly": "Monthly", "quarterly": "Quarterly"}
REFUNDS = {
    "next": ("Take off the next statement", "The simplest option. Nobody pays anything back."),
    "ignore": ("Ignore refunds under 50 a month", "Saves fuss for small apps."),
}
TERM_MONTHS = (6, 12, 24)
NOTICE_DAYS = (30, 60, 90)

DEFAULT_TERMS = {
    "basis": "net", "share": 25, "tiers": False, "tier_at": 5000, "share2": 15,
    "freq": "monthly", "due_days": 14, "min_payout": 25, "refunds": "next",
    "term_months": 12, "notice_days": 60, "buyout": True, "buy_mult": 2.0, "rofr": True,
}


def _rpc_error(err):
    msg = getattr(err, "message", None) or str(err)
    if isinstance(err.args[0] if err.args else None, dict):
        msg = err.args[0].get("message", msg)
    return msg


def _num(value, lo, hi, default, cast=int):
    try:
        n = cast(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def parse_terms(form):
    """Form fields -> a clean terms dict (out-of-range values are clamped)."""
    d = DEFAULT_TERMS
    buy_mult = round(_num(form.get("buy_mult"), 1, 4, d["buy_mult"], float) * 2) / 2
    term = _num(form.get("term_months"), 1, 120, d["term_months"])
    notice = _num(form.get("notice_days"), 1, 365, d["notice_days"])
    return {
        "basis": form.get("basis") if form.get("basis") in BASES else d["basis"],
        "share": _num(form.get("share"), 1, 100, d["share"]),
        "tiers": bool(form.get("tiers")),
        "tier_at": _num(form.get("tier_at"), 0, 10_000_000, d["tier_at"]),
        "share2": _num(form.get("share2"), 0, 100, d["share2"]),
        "freq": form.get("freq") if form.get("freq") in FREQS else d["freq"],
        "due_days": _num(form.get("due_days"), 1, 90, d["due_days"]),
        "min_payout": _num(form.get("min_payout"), 0, 10_000, d["min_payout"]),
        "refunds": form.get("refunds") if form.get("refunds") in REFUNDS else d["refunds"],
        "term_months": term if term in TERM_MONTHS else d["term_months"],
        "notice_days": notice if notice in NOTICE_DAYS else d["notice_days"],
        "buyout": bool(form.get("buyout")),
        "buy_mult": buy_mult,
        "rofr": bool(form.get("rofr")),
    }


def plain_english(t, builder, grower, app_title, symbol):
    """The terms as a short paragraph both people can read."""
    def m(n):
        return f"{symbol}{n:,.0f}" if symbol else f"{n:,.0f}"
    base = {"gross": "what customers pay (less refunds)",
            "net": f"what reaches {builder} after store and payment fees and refunds",
            "profit": f"what reaches {builder} after fees, refunds and running costs you've both confirmed"}[t["basis"]]
    mult = f"{t['buy_mult']:g}"
    parts = [
        f"{grower} receives {t['share']}% of {base}"
        + (f", falling to {t['share2']}% on anything above {m(t['tier_at'])} a month" if t["tiers"] else "") + ".",
        f"Crescopus prepares a {t['freq']} statement, and {builder} pays {grower} directly within "
        f"{t['due_days']} days of receiving the money from the stores.",
        f"The agreement runs for {t['term_months']} months and then continues until either of you gives "
        f"{t['notice_days']} days' notice.",
    ]
    if t["buyout"]:
        parts.append(f"{builder} can end {grower}'s share at any time by paying {mult}× what {grower} "
                     "earned in the previous 12 months.")
    if t["rofr"]:
        parts.append(f"If {builder} sells {app_title}, {grower} gets the first chance to buy it.")
    parts.append(f"{builder} owns {app_title} throughout.")
    return " ".join(parts)


def _load(partnership_id):
    """Partnership, the two people, the agreement (if any) and its sign-offs.
    None if the viewer isn't one of the two parties."""
    profile = current_profile()
    supabase = get_supabase()
    rows = (supabase.table("partnerships")
            .select("id,status,developer_id,grower_id,end_reason,disconnect_reason,listings(id,title),cresco_plans(ledger_currency)")
            .eq("id", partnership_id).execute().data)
    if not rows or not profile or profile["id"] not in (rows[0]["developer_id"], rows[0]["grower_id"]):
        return None
    p = rows[0]
    people = {r["id"]: r for r in (supabase.table("profiles").select("id,full_name")
              .in_("id", [p["developer_id"], p["grower_id"]]).execute().data)}
    builder = people.get(p["developer_id"], {"full_name": "Builder"})
    grower = people.get(p["grower_id"], {"full_name": "Grower"})

    plan = p.get("cresco_plans")
    plan = (plan[0] if plan else {}) if isinstance(plan, list) else (plan or {})
    currency = plan.get("ledger_currency") or "GBP"

    found = (supabase.table("revenue_agreements").select("*, revenue_signoffs(*)")
             .eq("partnership_id", partnership_id).execute().data)
    agreement = found[0] if found else None
    signed = {s["profile_id"]: s["version"] for s in (agreement or {}).get("revenue_signoffs") or []}

    def agreed(pid):
        return bool(agreement) and signed.get(pid) == agreement["version"]

    me_role = "builder" if profile["id"] == p["developer_id"] else "grower"
    terms = {**DEFAULT_TERMS, **(agreement["terms"] if agreement else {})}
    return {
        "profile": profile, "partnership": p, "agreement": agreement, "terms": terms,
        "listing": p.get("listings") or {"title": "your app"},
        "builder": builder, "grower": grower, "me_role": me_role,
        "other": grower if me_role == "builder" else builder,
        "builder_agreed": agreed(p["developer_id"]), "grower_agreed": agreed(p["grower_id"]),
        "i_agreed": agreed(profile["id"]),
        "active": p["status"] in ("trial", "formalised"),
        "currency": currency, "symbol": CURRENCY_SYMBOLS.get(currency.upper(), ""),
        "updated_by_name": (people.get((agreement or {}).get("updated_by")) or {}).get("full_name"),
    }


def _options():
    return {"bases": BASES, "freqs": FREQS, "refund_opts": REFUNDS,
            "term_options": TERM_MONTHS, "notice_options": NOTICE_DAYS}


@revenue_bp.route("/<partnership_id>")
@login_required
def view(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        flash("That partnership isn't available to you.", "error")
        return redirect(url_for("partnerships.inbox"))
    versions = []
    summary = None
    if ctx["agreement"]:
        versions = (get_supabase().table("revenue_versions").select("version,created_at,created_by")
                    .eq("agreement_id", ctx["agreement"]["id"]).order("version", desc=True).execute().data)
        summary = plain_english(ctx["terms"], ctx["builder"]["full_name"], ctx["grower"]["full_name"],
                                ctx["listing"]["title"], ctx["symbol"])
    names = {ctx["partnership"]["developer_id"]: ctx["builder"]["full_name"],
             ctx["partnership"]["grower_id"]: ctx["grower"]["full_name"]}
    return render_template("revenue/view.html", summary=summary, versions=versions, names=names,
                           **_options(), **ctx)


@revenue_bp.route("/<partnership_id>/edit", methods=["GET", "POST"])
@login_required
def edit(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        flash("That partnership isn't available to you.", "error")
        return redirect(url_for("partnerships.inbox"))
    if not ctx["active"]:
        flash("This partnership has ended, so its revenue terms can't be changed.", "error")
        return redirect(url_for("revenue.view", partnership_id=partnership_id))
    current_version = ctx["agreement"]["version"] if ctx["agreement"] else 0

    if request.method == "POST":
        terms = parse_terms(request.form)
        base_version = request.form.get("base_version", type=int)
        if not request.form.get("confirm"):
            flash("Please tick the box to confirm you agree to these terms.", "error")
            return render_template("revenue/edit.html", draft=terms, base_version=base_version, **_options(), **ctx)
        if base_version != current_version:
            flash(f"{ctx['updated_by_name'] or 'Your partner'} saved version {current_version} while you were "
                  "editing. Your choices are still below. Check their version, then save again to replace it.", "error")
            return render_template("revenue/edit.html", draft=terms, base_version=current_version, **_options(), **ctx)
        try:
            version = get_supabase().rpc("save_revenue_agreement", {
                "p_partnership_id": partnership_id, "p_terms": terms, "p_base_version": base_version,
            }).execute().data
        except Exception as err:  # noqa: BLE001 - show the database's message
            flash(f"The terms couldn't be saved: {_rpc_error(err)}", "error")
            return render_template("revenue/edit.html", draft=terms, base_version=base_version, **_options(), **ctx)
        flash(f"Saved as version {version}. {ctx['other']['full_name']} now needs to agree to it.", "success")
        return redirect(url_for("revenue.view", partnership_id=partnership_id))

    return render_template("revenue/edit.html", draft=ctx["terms"], base_version=current_version,
                           **_options(), **ctx)


@revenue_bp.route("/<partnership_id>/agree", methods=["POST"])
@login_required
def agree(partnership_id):
    ctx = _load(partnership_id)
    if not ctx or not ctx["agreement"]:
        abort(404)
    if not request.form.get("confirm"):
        flash("Please tick the box to confirm you've read these terms.", "error")
        return redirect(url_for("revenue.view", partnership_id=partnership_id))
    try:
        get_supabase().rpc("agree_revenue_agreement", {
            "p_agreement_id": ctx["agreement"]["id"], "p_version": request.form.get("version", type=int),
        }).execute()
        flash("You've agreed to these revenue terms.", "success")
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
    return redirect(url_for("revenue.view", partnership_id=partnership_id))
