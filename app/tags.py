"""Needs / Offers tags, read from the tag_options table in Supabase.

Edit the tags in Supabase (Table Editor > tag_options) — no code change or
deploy needed. The list is kept in memory for 5 minutes, so changes show
within that time. If the table can't be read (not created yet, or a brief
connection problem), the built-in lists in constants.py are used instead.

Two lists that mirror each other:
  growth  — growth help: what Builders NEED and Growers OFFER
  support — support/terms: what Builders OFFER and Growers NEED
"""
import time

from app.constants import GROWTH_TAGS, SUPPORT_TAGS

CACHE_SECONDS = 300
_cache = {"at": 0.0, "rows": None}


def _fallback_rows():
    rows = []
    for group, items in (("growth", GROWTH_TAGS), ("support", SUPPORT_TAGS)):
        for i, (slug, label) in enumerate(items):
            rows.append({"slug": slug, "label": label, "tag_group": group, "position": i, "active": True})
    return rows


def _rows():
    now = time.time()
    if _cache["rows"] is not None and now - _cache["at"] < CACHE_SECONDS:
        return _cache["rows"]
    try:
        from app.extensions import get_supabase
        rows = (get_supabase().table("tag_options")
                .select("slug,label,tag_group,position,active").execute().data)
        if not rows:
            raise ValueError("tag_options is empty")
    except Exception:  # noqa: BLE001 - fall back quietly, try again next time
        rows = _cache["rows"] or _fallback_rows()
        _cache.update(rows=rows, at=now - CACHE_SECONDS + 30)   # retry in 30s
        return rows
    rows = sorted(rows, key=lambda r: (r["tag_group"], r["position"], r["label"].lower()))
    _cache.update(rows=rows, at=now)
    return rows


def labels():
    """{slug: label} for every tag, including switched-off ones (so existing cards still show them)."""
    return {r["slug"]: r["label"] for r in _rows()}


def options(group, keep=()):
    """[(slug, label)] for a list, in order: the active tags, plus any switched-off
    ones in `keep` (tags a card already has), so editing a card never drops them."""
    keep = set(keep or ())
    return [(r["slug"], r["label"] + ("" if r["active"] else " (retired)"))
            for r in _rows() if r["tag_group"] == group and (r["active"] or r["slug"] in keep)]


def all_slugs(group):
    """Every known slug in a list, active or not — what a saved form may contain."""
    return [(r["slug"], r["label"]) for r in _rows() if r["tag_group"] == group]


# Which list each side's Needs / Offers use.
def builder_needs(keep=()): return options("growth", keep)
def builder_offers(keep=()): return options("support", keep)
def grower_needs(keep=()): return options("support", keep)
def grower_offers(keep=()): return options("growth", keep)
