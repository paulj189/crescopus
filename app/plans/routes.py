"""CrescoPlan: the shared plan between a Builder and a Grower.

Every change goes through the database functions from migration_plan_ledger.sql
(save_plan, agree_plan, set_action_status), so the rules hold in the database:
only the two parties can change a plan, every save makes a new version with a
history snapshot, and a plan only counts as agreed when both people have agreed
to its current version.
"""
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.extensions import get_supabase
from app.utils import login_required, current_profile, clean_list_html

plans_bp = Blueprint("plans", __name__, url_prefix="/plans")

ROLES = [("builder", "Builder"), ("grower", "Grower"), ("both", "Both")]
STATUSES = [("not_started", "Not started"), ("in_progress", "In progress"), ("done", "Done")]
CURRENCY_SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}


# ---------- template helpers ----------

@plans_bp.app_template_filter("short_date")
def short_date(value):
    """'2026-10-31' -> '31 Oct' (adds the year if it isn't this year)."""
    if not value:
        return ""
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        return str(value)
    text = f"{d.day} {d.strftime('%b')}"   # no %-d: it doesn't work on Windows
    return text if d.year == date.today().year else f"{text} {d.year}"


@plans_bp.app_template_filter("local_time")
def local_time(value):
    """ISO timestamp -> '24 Oct 10:36' in UK time (falls back to UTC if time zone data is missing)."""
    if not value:
        return ""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    try:
        from zoneinfo import ZoneInfo
        dt = dt.astimezone(ZoneInfo("Europe/London"))
    except Exception:  # noqa: BLE001 - e.g. Windows without the tzdata package
        pass
    return f"{short_date(dt.date().isoformat())} {dt.strftime('%H:%M')}"


@plans_bp.app_template_filter("money")
def money(amount, currency="GBP"):
    symbol = CURRENCY_SYMBOLS.get((currency or "").upper(), "")
    text = f"{abs(float(amount or 0)):,.2f}"
    sign = "−" if float(amount or 0) < 0 else ""
    return f"{sign}{symbol}{text}" if symbol else f"{sign}{text} {currency}"


def _rpc_error(err):
    """The readable part of a database error, for showing to the user."""
    msg = getattr(err, "message", None) or str(err)
    if isinstance(err.args[0] if err.args else None, dict):
        msg = err.args[0].get("message", msg)
    return msg


# ---------- loading ----------

def _load(partnership_id):
    """Partnership, plan (with actions, measures, sign-offs) and the two people.
    Returns None if the plan doesn't exist or the viewer isn't one of the two parties."""
    profile = current_profile()
    supabase = get_supabase()
    rows = (supabase.table("partnerships")
            .select("id,status,listing_id,developer_id,grower_id,started_at,end_reason,disconnect_reason,listings(id,title)")
            .eq("id", partnership_id).execute().data)
    if not rows or not profile or profile["id"] not in (rows[0]["developer_id"], rows[0]["grower_id"]):
        return None
    partnership = rows[0]

    plans = (supabase.table("cresco_plans")
             .select("*, plan_actions(*), plan_measures(*), plan_signoffs(*)")
             .eq("partnership_id", partnership_id).execute().data)
    if not plans:
        return None
    plan = plans[0]
    plan["plan_actions"] = sorted(plan.get("plan_actions") or [], key=lambda a: a["position"])
    plan["plan_measures"] = sorted(plan.get("plan_measures") or [], key=lambda m: m["position"])

    people = {p["id"]: p for p in (supabase.table("profiles").select("id,full_name")
              .in_("id", [partnership["developer_id"], partnership["grower_id"]]).execute().data)}
    builder = people.get(partnership["developer_id"], {"full_name": "Builder"})
    grower = people.get(partnership["grower_id"], {"full_name": "Grower"})

    signed = {s["profile_id"]: s for s in plan.get("plan_signoffs") or []}
    def agreed(pid):
        s = signed.get(pid)
        return bool(s and s["version"] == plan["version"])

    me_role = "builder" if profile["id"] == partnership["developer_id"] else "grower"
    return {
        "profile": profile, "partnership": partnership, "plan": plan,
        "listing": partnership.get("listings") or {"title": "Your app"},
        "builder": builder, "grower": grower,
        "builder_agreed": agreed(partnership["developer_id"]),
        "grower_agreed": agreed(partnership["grower_id"]),
        "i_agreed": agreed(profile["id"]),
        "me_role": me_role,
        "updated_by_name": (people.get(plan.get("updated_by")) or {}).get("full_name"),
        "is_empty": not (plan.get("agreed_needs_html") or plan.get("agreed_offers_html")
                         or plan["plan_actions"] or plan["plan_measures"]),
    }


def _ledger_summary(partnership_id):
    rows = (get_supabase().table("ledger_entries").select("kind,amount,status")
            .eq("partnership_id", partnership_id).execute().data)
    confirmed = [r for r in rows if r["status"] == "confirmed"]
    revenue = sum(float(r["amount"]) for r in confirmed if r["kind"] == "revenue")
    costs = sum(float(r["amount"]) for r in confirmed if r["kind"] == "cost")
    return {"net": revenue - costs, "pending": sum(1 for r in rows if r["status"] != "confirmed"), "count": len(rows)}


# ---------- pages ----------

def plan_summaries(supabase, profile):
    """One summary per active plan the person is in, most urgent first.
    Used by My plans, the dashboard and the menu badge."""
    partnerships = (supabase.table("partnerships")
                    .select("id,status,developer_id,grower_id,listings(title),cresco_plans(id,version,updated_at,plan_signoffs(profile_id,version))")
                    .or_(f"developer_id.eq.{profile['id']},grower_id.eq.{profile['id']}")
                    .execute().data)
    others = {p["developer_id"] if p["grower_id"] == profile["id"] else p["grower_id"] for p in partnerships}
    names = {p["id"]: p["full_name"] for p in (supabase.table("profiles").select("id,full_name")
             .in_("id", list(others)).execute().data if others else [])}

    items = []
    for p in partnerships:
        plan = p.get("cresco_plans")
        plan = (plan[0] if plan else None) if isinstance(plan, list) else plan
        if not plan:
            continue
        signed = {s["profile_id"]: s["version"] for s in plan.get("plan_signoffs") or []}
        other_id = p["developer_id"] if p["grower_id"] == profile["id"] else p["grower_id"]
        me_ok = signed.get(profile["id"]) == plan["version"]
        other_ok = signed.get(other_id) == plan["version"]
        if p["status"] not in ("trial", "formalised"):
            state = ("ended", "Ended")
        elif me_ok and other_ok:
            state = ("agreed", "Agreed by both")
        elif other_ok:
            state = ("you", "Waiting for you")
        elif me_ok:
            state = ("them", "Waiting for them")
        else:
            state = ("draft", "Draft")
        items.append({
            "id": p["id"], "title": (p.get("listings") or {}).get("title", "App"),
            "with": names.get(other_id, "Partner"),
            "with_role": "Grower" if p["developer_id"] == profile["id"] else "Builder",
            "version": plan["version"], "updated_at": plan.get("updated_at"), "state": state,
            "active": state[0] != "ended",
        })
    order = {"you": 0, "draft": 1, "them": 2, "agreed": 3, "ended": 4}
    items.sort(key=lambda i: (order[i["state"][0]], i["title"].lower()))
    return items


@plans_bp.route("/")
@login_required
def index():
    """All the plans you're part of."""
    return render_template("plans/index.html", items=plan_summaries(get_supabase(), current_profile()))


@plans_bp.route("/<partnership_id>")
@login_required
def view(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        flash("That plan isn't available to you.", "error")
        return redirect(url_for("plans.index"))
    return render_template("plans/view.html", ledger=_ledger_summary(partnership_id),
                           roles=dict(ROLES), statuses=STATUSES, status_labels=dict(STATUSES), **ctx)


@plans_bp.route("/<partnership_id>/edit", methods=["GET", "POST"])
@login_required
def edit(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        flash("That plan isn't available to you.", "error")
        return redirect(url_for("plans.index"))
    if ctx["partnership"]["status"] not in ("trial", "formalised"):
        flash("This partnership has ended, so its plan can't be changed.", "error")
        return redirect(url_for("plans.view", partnership_id=partnership_id))
    plan = ctx["plan"]

    if request.method == "POST":
        f = request.form
        actions = [
            {"title": t.strip()[:200], "owner_role": o if o in dict(ROLES) else "both",
             "due_date": d or None, "status": s if s in dict(STATUSES) else "not_started"}
            for t, o, d, s in zip(f.getlist("action_title"), f.getlist("action_owner"),
                                  f.getlist("action_due"), f.getlist("action_status"))
            if t.strip()
        ]
        measures = [
            {"measure": m.strip()[:200], "target": t.strip()[:120] or None, "evidence": e.strip()[:120] or None,
             "review_date": r or None, "owner_role": o if o in dict(ROLES) else "both"}
            for m, t, e, r, o in zip(f.getlist("measure_name"), f.getlist("measure_target"),
                                     f.getlist("measure_evidence"), f.getlist("measure_review"),
                                     f.getlist("measure_owner"))
            if m.strip()
        ]
        draft = {
            "agreed_needs_html": clean_list_html(f.get("needs_html")),
            "agreed_offers_html": clean_list_html(f.get("offers_html")),
            "plan_actions": actions, "plan_measures": measures,
        }

        # Did the other person save a new version while this one was being edited?
        base_version = f.get("base_version", type=int)
        if base_version != plan["version"]:
            flash(f"{ctx['updated_by_name'] or 'Your partner'} saved version {plan['version']} while you were editing. "
                  "Your changes are still below. Check their version, then save again to replace it.", "error")
            return render_template("plans/edit.html", draft=draft, base_version=plan["version"],
                                   roles=ROLES, statuses=STATUSES, conflict=True, **ctx)

        try:
            new_version = get_supabase().rpc("save_plan", {
                "p_plan_id": plan["id"],
                "p_needs_html": draft["agreed_needs_html"],
                "p_offers_html": draft["agreed_offers_html"],
                "p_actions": actions,
                "p_measures": measures,
            }).execute().data
        except Exception as err:  # noqa: BLE001 - show the database's message
            flash(f"The plan couldn't be saved: {_rpc_error(err)}", "error")
            return render_template("plans/edit.html", draft=draft, base_version=plan["version"],
                                   roles=ROLES, statuses=STATUSES, conflict=False, **ctx)
        flash(f"Saved as version {new_version}. You'll both need to agree to this version.", "success")
        return redirect(url_for("plans.view", partnership_id=partnership_id))

    return render_template("plans/edit.html", draft=plan, base_version=plan["version"],
                           roles=ROLES, statuses=STATUSES, conflict=False, **ctx)


@plans_bp.route("/<partnership_id>/agree", methods=["POST"])
@login_required
def agree(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        abort(404)
    if not request.form.get("confirm"):
        flash("Please tick the box to confirm you've read this version.", "error")
        return redirect(url_for("plans.view", partnership_id=partnership_id))
    try:
        get_supabase().rpc("agree_plan", {
            "p_plan_id": ctx["plan"]["id"], "p_version": request.form.get("version", type=int),
        }).execute()
        flash("You've agreed to this version.", "success")
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
    return redirect(url_for("plans.view", partnership_id=partnership_id))


@plans_bp.route("/<partnership_id>/actions/<action_id>/status", methods=["POST"])
@login_required
def action_status(partnership_id, action_id):
    status = request.form.get("status")
    if status not in dict(STATUSES):
        abort(400)
    try:
        get_supabase().rpc("set_action_status", {"p_action_id": action_id, "p_status": status}).execute()
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
    if request.headers.get("X-Requested-With") == "fetch":
        return ("", 204)
    return redirect(url_for("plans.view", partnership_id=partnership_id) + "#actions")


@plans_bp.route("/<partnership_id>/history")
@login_required
def history(partnership_id):
    ctx = _load(partnership_id)
    if not ctx:
        flash("That plan isn't available to you.", "error")
        return redirect(url_for("plans.index"))
    versions = (get_supabase().table("plan_versions").select("version,created_at,created_by,snapshot")
                .eq("plan_id", ctx["plan"]["id"]).order("version", desc=True).execute().data)
    names = {ctx["partnership"]["developer_id"]: ctx["builder"]["full_name"],
             ctx["partnership"]["grower_id"]: ctx["grower"]["full_name"]}
    show = request.args.get("v", type=int)
    selected = next((v for v in versions if v["version"] == show), versions[0] if versions else None)
    return render_template("plans/history.html", versions=versions, names=names, selected=selected,
                           roles=dict(ROLES), status_labels=dict(STATUSES), **ctx)
