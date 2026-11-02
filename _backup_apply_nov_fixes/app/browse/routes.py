"""Browse: card grid for Builders & apps and for Growers, plus the profile popups.

Each card opens a popup. The popup is the same HTML as the full-page view
(/browse/app/<id> or /browse/grower/<id>), fetched with ?partial=1, so the
links still work without JavaScript and can be shared or bookmarked.
"""
import re
import zlib

from flask import Blueprint, render_template, request, url_for, abort, redirect, flash

from app.extensions import get_supabase
from app.utils import (
    current_profile, get_verifications, get_id_verified_ids, login_required,
    clean_list_html, clean_pitch_html, tags_from_form,
)
from app.constants import VERIFICATION_LABELS
from app import tags

browse_bp = Blueprint("browse", __name__, url_prefix="/browse")

PAGE_SIZE = 60
TINTS = ["#1E8A4C", "#8C6118", "#3F6238", "#17231A", "#6E4A11", "#2F5D4A"]


# ---------- small helpers ----------

def _initials(name):
    parts = [p for p in re.split(r"[\s.]+", name or "") if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _tint(seed):
    return TINTS[zlib.crc32(str(seed).encode()) % len(TINTS)]


def _clean_search(q):
    # Letters, numbers, spaces and hyphens only — keeps the database filter safe.
    return re.sub(r"[^\w\s-]", "", q or "").strip()[:60]


def _labels(slugs):
    names = tags.labels()
    return [names.get(s, s) for s in (slugs or [])]


def _wants_partial():
    return request.args.get("partial") == "1" or request.headers.get("X-Requested-With") == "fetch"


def _short(text, limit=140):
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


# ---------- browse grid ----------

@browse_bp.route("/")
def index():
    tab = "growers" if request.args.get("tab") == "growers" else "builders"
    q = _clean_search(request.args.get("q"))
    verified_only = request.args.get("verified") == "1"

    if tab == "builders":
        needs_options, offers_options = tags.builder_needs(), tags.builder_offers()
    else:
        needs_options, offers_options = tags.grower_needs(), tags.grower_offers()
    need_slugs = {s for s, _ in needs_options}
    offer_slugs = {s for s, _ in offers_options}
    needs = [n for n in request.args.getlist("need") if n in need_slugs]
    offers = [o for o in request.args.getlist("offer") if o in offer_slugs]

    supabase = get_supabase()
    verified_ids = get_id_verified_ids(supabase) if verified_only else None

    cards = []
    if not (verified_only and not verified_ids):
        if tab == "builders":
            query = (supabase.table("listings").select("*, profiles(id, full_name, hero_image_url)")
                     .is_("withdrawn_at", "null"))
            if verified_ids is not None:
                query = query.in_("developer_id", verified_ids)
            if needs:
                query = query.ov("needs_tags", needs)
            if offers:
                query = query.ov("offers_tags", offers)
            if q:
                query = query.or_(f"title.ilike.*{q}*,tagline.ilike.*{q}*,category.ilike.*{q}*")
            rows = query.order("created_at", desc=True).limit(PAGE_SIZE).execute().data
            badges = get_verifications(supabase, [r["developer_id"] for r in rows])
            for r in rows:
                builder = r.get("profiles") or {}
                cards.append({
                    "name": r["title"],
                    "by": f"Builder · {builder.get('full_name') or 'Unknown'}",
                    "pitch": _short(r.get("tagline") or r.get("description")),
                    "image": r.get("hero_image_url"),
                    "initials": _initials(r["title"]),
                    "tint": _tint(r["id"]),
                    "verified": "id" in badges.get(r["developer_id"], set()),
                    "needs": _labels(r.get("needs_tags")),
                    "offers": _labels(r.get("offers_tags")),
                    "url": url_for("browse.app_detail", listing_id=r["id"]),
                })
        else:
            query = (supabase.table("profiles").select("*").eq("is_grower", True)
                     .is_("grower_withdrawn_at", "null"))
            if verified_ids is not None:
                query = query.in_("id", verified_ids)
            if needs:
                query = query.ov("needs_tags", needs)
            if offers:
                query = query.ov("offers_tags", offers)
            if q:
                query = query.or_(f"full_name.ilike.*{q}*,bio.ilike.*{q}*")
            rows = query.order("created_at", desc=True).limit(PAGE_SIZE).execute().data
            badges = get_verifications(supabase, [r["id"] for r in rows])
            for r in rows:
                cards.append({
                    "name": r["full_name"] or "Unnamed grower",
                    "by": "Grower",
                    "pitch": _short(r.get("bio")),
                    "image": r.get("hero_image_url"),
                    "initials": _initials(r["full_name"]),
                    "tint": _tint(r["id"]),
                    "verified": "id" in badges.get(r["id"], set()),
                    "needs": _labels(r.get("needs_tags")),
                    "offers": _labels(r.get("offers_tags")),
                    "url": url_for("browse.grower_detail", grower_id=r["id"]),
                })

    return render_template(
        "browse/index.html",
        tab=tab, q=q, verified_only=verified_only,
        needs=needs, offers=offers,
        needs_options=needs_options, offers_options=offers_options,
        cards=cards,
    )


# ---------- popups / full pages ----------

def _render_detail(partial_template, **ctx):
    if _wants_partial():
        return render_template(partial_template, **ctx)
    return render_template("browse/detail_page.html", partial_template=partial_template, **ctx)


@browse_bp.route("/app/<listing_id>")
def app_detail(listing_id):
    supabase = get_supabase()
    # One round trip: the app, its builder and the builder's badges together.
    rows = (supabase.table("listings")
            .select("*, profiles(*, profile_verifications(kind))")
            .eq("id", listing_id).execute().data)
    if not rows:
        abort(404)
    listing = rows[0]
    builder = listing.pop("profiles", None) or {"id": listing["developer_id"], "full_name": "Unknown"}
    badges = {v["kind"] for v in builder.pop("profile_verifications", None) or []}

    viewer = current_profile()
    action = {"kind": "login"}
    if viewer:
        if viewer["id"] == listing["developer_id"]:
            action = {"kind": "owner"}
        elif listing.get("withdrawn_at"):
            existing = (
                supabase.table("partnerships").select("id")
                .eq("listing_id", listing_id).eq("grower_id", viewer["id"]).execute().data
            )
            action = {"kind": "open", "partnership_id": existing[0]["id"]} if existing else {"kind": "withdrawn"}
        elif viewer.get("is_grower") and viewer.get("grower_withdrawn_at"):
            action = {"kind": "self_withdrawn"}
        elif viewer.get("is_grower"):
            existing = (
                supabase.table("partnerships").select("id,status")
                .eq("listing_id", listing_id).eq("grower_id", viewer["id"])
                .in_("status", ["trial", "formalised"]).execute().data
            )
            pending = (
                supabase.table("connection_requests").select("id")
                .eq("listing_id", listing_id).eq("grower_id", viewer["id"])
                .eq("status", "pending").execute().data
            )
            if existing:
                action = {"kind": "open", "partnership_id": existing[0]["id"]}
            elif pending:
                action = {"kind": "pending"}
            else:
                action = {"kind": "connect"}
        else:
            action = {"kind": "none"}
    elif listing.get("withdrawn_at"):
        action = {"kind": "withdrawn"}

    return _render_detail(
        "browse/_app_popup.html",
        listing=listing, builder=builder,
        builder_initials=_initials(builder.get("full_name")), builder_tint=_tint(builder["id"]),
        badges=[VERIFICATION_LABELS[k] for k in VERIFICATION_LABELS if k in badges],
        id_verified="id" in badges,
        action=action,
    )


@browse_bp.route("/grower/<grower_id>")
def grower_detail(grower_id):
    supabase = get_supabase()
    rows = (supabase.table("profiles").select("*, profile_verifications(kind)")
            .eq("id", grower_id).eq("is_grower", True).execute().data)
    if not rows:
        abort(404)
    grower = rows[0]
    badges = {v["kind"] for v in grower.pop("profile_verifications", None) or []}

    viewer = current_profile()
    action = {"kind": "login"}
    my_listings = []
    if viewer:
        if viewer["id"] == grower_id:
            action = {"kind": "owner"}
        elif grower.get("grower_withdrawn_at"):
            action = {"kind": "withdrawn"}
        elif viewer.get("is_developer"):
            my_listings = (
                supabase.table("listings").select("id,title")
                .eq("developer_id", viewer["id"]).is_("withdrawn_at", "null")
                .order("created_at", desc=True).execute().data
            )
            action = {"kind": "connect"} if my_listings else {"kind": "need_listing"}
        else:
            action = {"kind": "none"}
    elif grower.get("grower_withdrawn_at"):
        action = {"kind": "withdrawn"}

    return _render_detail(
        "browse/_grower_popup.html",
        grower=grower,
        initials=_initials(grower.get("full_name")), tint=_tint(grower_id),
        badges=[VERIFICATION_LABELS[k] for k in VERIFICATION_LABELS if k in badges],
        id_verified="id" in badges,
        action=action, my_listings=my_listings,
    )


# ---------- Edit card (owner only) ----------
# One editor laid out like the popup, with a live preview of the browse card.
# Growers edit their own card; builders edit one card per app.

PLATFORMS = [("web", "Web"), ("ios", "iOS"), ("android", "Android"), ("multi", "Multiple")]


def _clean_url(url):
    url = (url or "").strip()
    return url if url.startswith(("https://", "http://")) else None


@browse_bp.route("/card/edit", methods=["GET", "POST"])
@login_required
def edit_my_card():
    """A grower's own card. Builders are sent to their app cards instead."""
    profile = current_profile()
    if not profile:
        abort(403)
    if not profile.get("is_grower"):
        supabase = get_supabase()
        apps = (supabase.table("listings").select("id").eq("developer_id", profile["id"])
                .order("created_at", desc=True).limit(1).execute().data)
        if apps:
            return redirect(url_for("browse.edit_app_card", listing_id=apps[0]["id"]))
        flash("Your card is made from an app listing. List your app to create one.", "success")
        return redirect(url_for("listings.new"))

    if request.method == "POST":
        name = (request.form.get("full_name") or "").strip()
        if not name:
            flash("Please add your name.", "error")
            return redirect(url_for("browse.edit_my_card"))
        get_supabase().table("profiles").update({
            "full_name": name[:120],
            "bio": (request.form.get("bio") or "").strip()[:200] or None,
            "pitch_html": clean_pitch_html(request.form.get("pitch_html")),
            "hero_image_url": _clean_url(request.form.get("hero_image_url")),
            "needs_html": clean_list_html(request.form.get("needs_html")),
            "offers_html": clean_list_html(request.form.get("offers_html")),
            "needs_tags": tags_from_form(request.form, "needs_tags", tags.all_slugs("support")),
            "offers_tags": tags_from_form(request.form, "offers_tags", tags.all_slugs("growth")),
        }).eq("id", profile["id"]).execute()
        flash("Card saved.", "success")
        return redirect(url_for("browse.edit_my_card"))

    badges = get_verifications(get_supabase(), [profile["id"]]).get(profile["id"], set())
    return render_template(
        "browse/edit_card.html", kind="grower",
        person=profile, listing=None,
        needs_options=tags.grower_needs(keep=profile.get("needs_tags")),
        offers_options=tags.grower_offers(keep=profile.get("offers_tags")),
        id_verified="id" in badges,
        tint=_tint(profile["id"]), view_url=url_for("browse.grower_detail", grower_id=profile["id"]),
    )


@browse_bp.route("/app/<listing_id>/edit", methods=["GET", "POST"])
@login_required
def edit_app_card(listing_id):
    profile = current_profile()
    supabase = get_supabase()
    rows = supabase.table("listings").select("*").eq("id", listing_id).execute().data
    if not rows or not profile or rows[0]["developer_id"] != profile["id"]:
        flash("Only the app's builder can edit its card.", "error")
        return redirect(url_for("browse.index"))
    listing = rows[0]

    if request.method == "POST":
        name = (request.form.get("full_name") or "").strip()
        title = (request.form.get("title") or "").strip()
        if not name or not title:
            flash("Please add your name and the app's name.", "error")
            return redirect(url_for("browse.edit_app_card", listing_id=listing_id))
        supabase.table("profiles").update({
            "full_name": name[:120],
            "pitch_html": clean_pitch_html(request.form.get("person_pitch_html")),
            "hero_image_url": _clean_url(request.form.get("person_image_url")),
        }).eq("id", profile["id"]).execute()

        store_urls = dict(listing.get("store_urls") or {})
        app_url = _clean_url(request.form.get("app_url"))
        if app_url:
            store_urls["website"] = app_url
        else:
            store_urls.pop("website", None)
        platform = request.form.get("platform") or listing.get("platform")
        supabase.table("listings").update({
            "title": title[:120],
            "tagline": (request.form.get("tagline") or "").strip()[:160] or None,
            "category": (request.form.get("category") or "").strip()[:60] or None,
            "platform": platform,
            "hero_image_url": _clean_url(request.form.get("app_image_url")),
            "pitch_html": clean_pitch_html(request.form.get("app_pitch_html")),
            "store_urls": store_urls,
            "needs_html": clean_list_html(request.form.get("needs_html")),
            "offers_html": clean_list_html(request.form.get("offers_html")),
            "needs_tags": tags_from_form(request.form, "needs_tags", tags.all_slugs("growth")),
            "offers_tags": tags_from_form(request.form, "offers_tags", tags.all_slugs("support")),
            "revenuecat_project_key": (request.form.get("revenuecat_project_key") or "").strip() or None,
        }).eq("id", listing_id).execute()
        flash("Card saved.", "success")
        return redirect(url_for("browse.edit_app_card", listing_id=listing_id))

    badges = get_verifications(supabase, [profile["id"]]).get(profile["id"], set())
    platforms = list(PLATFORMS)
    if listing.get("platform") and listing["platform"] not in dict(PLATFORMS):
        platforms.insert(0, (listing["platform"], listing["platform"]))
    return render_template(
        "browse/edit_card.html", kind="app",
        person=profile, listing=listing, platforms=platforms,
        app_url=(listing.get("store_urls") or {}).get("website", ""),
        needs_options=tags.builder_needs(keep=listing.get("needs_tags")),
        offers_options=tags.builder_offers(keep=listing.get("offers_tags")),
        id_verified="id" in badges,
        tint=_tint(listing_id), person_tint=_tint(profile["id"]),
        view_url=url_for("browse.app_detail", listing_id=listing_id),
    )


# ---------- Withdraw / restore / delete a card (owner only) ----------
# A card with no history can be deleted outright. Any other card is withdrawn:
# hidden from browsing, its pending requests declined, and the partnerships
# the person ticks are ended. Plans and ledgers stay with both people.

def _rpc_error(err):
    msg = getattr(err, "message", None) or str(err)
    if err.args and isinstance(err.args[0], dict):
        msg = err.args[0].get("message", msg)
    return msg


def _card_situation(supabase, profile, listing=None):
    """Active partnerships (with the other person's name), pending requests and
    whether the card has any history at all."""
    if listing:
        parts = (supabase.table("partnerships").select("id,status,grower_id,developer_id,listing_id")
                 .eq("listing_id", listing["id"]).execute().data)
        reqs = supabase.table("connection_requests").select("id,status").eq("listing_id", listing["id"]).execute().data
    else:
        parts = (supabase.table("partnerships").select("id,status,grower_id,developer_id,listing_id")
                 .eq("grower_id", profile["id"]).execute().data)
        reqs = supabase.table("connection_requests").select("id,status").eq("grower_id", profile["id"]).execute().data
    active = [p for p in parts if p["status"] in ("trial", "formalised")]
    others = {p["developer_id"] if p["grower_id"] == profile["id"] else p["grower_id"] for p in active}
    names = {r["id"]: r["full_name"] for r in (supabase.table("profiles").select("id,full_name")
             .in_("id", list(others)).execute().data if others else [])}
    titles = {}
    if active and not listing:
        titles = {r["id"]: r["title"] for r in (supabase.table("listings").select("id,title")
                  .in_("id", list({p["listing_id"] for p in active})).execute().data)}
    for p in active:
        other = p["developer_id"] if p["grower_id"] == profile["id"] else p["grower_id"]
        p["with"] = names.get(other) or "your partner"
        p["title"] = listing["title"] if listing else titles.get(p["listing_id"], "an app")
    return {"active": active,
            "pending": sum(1 for r in reqs if r["status"] == "pending"),
            "has_history": bool(parts or reqs)}


def _do_withdraw(supabase, situation, listing_id, back_url):
    """Handle the withdraw form. Returns a redirect on success, else None."""
    active_ids = {p["id"] for p in situation["active"]}
    end_ids = [i for i in request.form.getlist("end_ids") if i in active_ids]
    reason = (request.form.get("reason") or "").strip()[:1000]
    if end_ids and not reason:
        flash("Please give a short reason. The partners whose partnerships end will see it.", "error")
        return None
    try:
        result = supabase.rpc("withdraw_card", {"p_listing_id": listing_id, "p_end_ids": end_ids,
                                                "p_reason": reason or None}).execute().data or {}
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
        return None
    bits = ["Your card has been withdrawn and no longer appears on Crescopus."]
    if result.get("ended"):
        n = result["ended"]
        bits.append(f"{n} partnership{'' if n == 1 else 's'} ended; plans and ledgers stay available, read-only.")
    if result.get("declined"):
        n = result["declined"]
        bits.append(f"{n} pending request{'' if n == 1 else 's'} declined.")
    flash(" ".join(bits) + " You can restore the card from your dashboard.", "success")
    return redirect(back_url)


@browse_bp.route("/app/<listing_id>/withdraw", methods=["GET", "POST"])
@login_required
def withdraw_app_card(listing_id):
    profile = current_profile()
    supabase = get_supabase()
    rows = supabase.table("listings").select("*").eq("id", listing_id).execute().data
    if not rows or not profile or rows[0]["developer_id"] != profile["id"]:
        flash("Only the app's builder can withdraw or delete its card.", "error")
        return redirect(url_for("dashboard.index"))
    listing = rows[0]
    situation = _card_situation(supabase, profile, listing)

    if request.method == "POST":
        if request.form.get("action") == "delete":
            try:
                supabase.rpc("delete_listing", {"p_listing_id": listing_id}).execute()
                flash(f"{listing['title']} has been deleted.", "success")
                return redirect(url_for("dashboard.index"))
            except Exception as err:  # noqa: BLE001
                flash(_rpc_error(err), "error")
        else:
            done = _do_withdraw(supabase, situation, listing_id, url_for("dashboard.index"))
            if done:
                return done

    return render_template("browse/withdraw.html", kind="app", listing=listing,
                           card_name=listing["title"], **situation)


@browse_bp.route("/card/withdraw", methods=["GET", "POST"])
@login_required
def withdraw_my_card():
    profile = current_profile()
    if not profile or not profile.get("is_grower"):
        flash("Builders withdraw each app card from the card's own page.", "error")
        return redirect(url_for("dashboard.index"))
    supabase = get_supabase()
    situation = _card_situation(supabase, profile)
    if request.method == "POST":
        done = _do_withdraw(supabase, situation, None, url_for("dashboard.index"))
        if done:
            return done
    return render_template("browse/withdraw.html", kind="grower", listing=None,
                           card_name=profile.get("full_name") or "your card", **situation)


@browse_bp.route("/app/<listing_id>/restore", methods=["POST"])
@login_required
def restore_app_card(listing_id):
    try:
        get_supabase().rpc("restore_card", {"p_listing_id": listing_id}).execute()
        flash("Card restored. It's back on Crescopus.", "success")
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
    return redirect(url_for("dashboard.index"))


@browse_bp.route("/card/restore", methods=["POST"])
@login_required
def restore_my_card():
    try:
        get_supabase().rpc("restore_card", {"p_listing_id": None}).execute()
        flash("Card restored. It's back on Crescopus.", "success")
    except Exception as err:  # noqa: BLE001
        flash(_rpc_error(err), "error")
    return redirect(url_for("dashboard.index"))
