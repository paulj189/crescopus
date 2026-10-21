"""Browse: card grid for Builders & apps and for Growers, plus the profile popups.

Each card opens a popup. The popup is the same HTML as the full-page view
(/browse/app/<id> or /browse/grower/<id>), fetched with ?partial=1, so the
links still work without JavaScript and can be shared or bookmarked.
"""
import re
import zlib

from flask import Blueprint, render_template, request, url_for, abort

from app.extensions import get_supabase
from app.utils import current_profile, get_verifications, get_id_verified_ids
from app.constants import (
    TAG_LABELS,
    BUILDER_NEEDS_TAGS, BUILDER_OFFERS_TAGS,
    GROWER_NEEDS_TAGS, GROWER_OFFERS_TAGS,
    VERIFICATION_LABELS,
)

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
    return [TAG_LABELS.get(s, s) for s in (slugs or [])]


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
        needs_options, offers_options = BUILDER_NEEDS_TAGS, BUILDER_OFFERS_TAGS
    else:
        needs_options, offers_options = GROWER_NEEDS_TAGS, GROWER_OFFERS_TAGS
    need_slugs = {s for s, _ in needs_options}
    offer_slugs = {s for s, _ in offers_options}
    needs = [n for n in request.args.getlist("need") if n in need_slugs]
    offers = [o for o in request.args.getlist("offer") if o in offer_slugs]

    supabase = get_supabase()
    verified_ids = get_id_verified_ids(supabase) if verified_only else None

    cards = []
    if not (verified_only and not verified_ids):
        if tab == "builders":
            query = supabase.table("listings").select("*, profiles(id, full_name, hero_image_url)")
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
            query = supabase.table("profiles").select("*").eq("is_grower", True)
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
    rows = supabase.table("listings").select("*").eq("id", listing_id).execute().data
    if not rows:
        abort(404)
    listing = rows[0]
    builder = supabase.table("profiles").select("*").eq("id", listing["developer_id"]).execute().data
    builder = builder[0] if builder else {"id": listing["developer_id"], "full_name": "Unknown"}
    badges = get_verifications(supabase, [builder["id"]]).get(builder["id"], set())

    viewer = current_profile()
    action = {"kind": "login"}
    if viewer:
        if viewer["id"] == listing["developer_id"]:
            action = {"kind": "owner"}
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
    rows = supabase.table("profiles").select("*").eq("id", grower_id).eq("is_grower", True).execute().data
    if not rows:
        abort(404)
    grower = rows[0]
    badges = get_verifications(supabase, [grower_id]).get(grower_id, set())

    viewer = current_profile()
    action = {"kind": "login"}
    my_listings = []
    if viewer:
        if viewer["id"] == grower_id:
            action = {"kind": "owner"}
        elif viewer.get("is_developer"):
            my_listings = (
                supabase.table("listings").select("id,title")
                .eq("developer_id", viewer["id"]).order("created_at", desc=True).execute().data
            )
            action = {"kind": "connect"} if my_listings else {"kind": "need_listing"}
        else:
            action = {"kind": "none"}

    return _render_detail(
        "browse/_grower_popup.html",
        grower=grower,
        initials=_initials(grower.get("full_name")), tint=_tint(grower_id),
        badges=[VERIFICATION_LABELS[k] for k in VERIFICATION_LABELS if k in badges],
        id_verified="id" in badges,
        action=action, my_listings=my_listings,
    )
