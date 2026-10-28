from functools import wraps
from flask import session, redirect, url_for, g
from app.extensions import get_supabase


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def current_profile():
    """The signed-in user's profile. Looked up once per request and reused."""
    if "user_id" not in session:
        return None
    if "current_profile" not in g:
        supabase = get_supabase()
        res = supabase.table("profiles").select("*").eq("id", session["user_id"]).execute()
        g.current_profile = res.data[0] if res.data else None
    return g.current_profile


def get_pending_received_requests(supabase, profile):
    """Connection requests addressed to this profile, still awaiting a response."""
    if profile.get("is_grower"):
        return (
            supabase.table("connection_requests")
            .select("*")
            .eq("grower_id", profile["id"])
            .neq("initiated_by", profile["id"])
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
            .data
        )
    my_listings = supabase.table("listings").select("id").eq("developer_id", profile["id"]).execute().data
    listing_ids = [l["id"] for l in my_listings]
    if not listing_ids:
        return []
    return (
        supabase.table("connection_requests")
        .select("*")
        .in_("listing_id", listing_ids)
        .neq("initiated_by", profile["id"])
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
        .data
    )


def get_formalise_waiting_on_me(supabase, profile):
    """Trial CrescoPacts where the other side proposed formalising and it's waiting on this profile."""
    return (
        supabase.table("partnerships")
        .select("*")
        .or_(f"developer_id.eq.{profile['id']},grower_id.eq.{profile['id']}")
        .eq("status", "trial")
        .eq("formalise_status", "proposed")
        .neq("formalise_proposed_by", profile["id"])
        .execute()
        .data
    )


def get_unread_partnerships(supabase, profile):
    """CrescoPacts with a message from the other party since this profile last read them.

    Returns a dict of {partnership_id: latest_message} for partnerships with
    something new to see, so callers can both count and surface them.
    """
    partnerships = (
        supabase.table("partnerships")
        .select("id,listing_id,developer_id,grower_id,started_at")
        .or_(f"developer_id.eq.{profile['id']},grower_id.eq.{profile['id']}")
        .execute()
        .data
    )
    if not partnerships:
        return {}
    partnership_ids = [p["id"] for p in partnerships]
    started_at_by_id = {p["id"]: p["started_at"] for p in partnerships}

    reads = (
        supabase.table("message_reads")
        .select("partnership_id,last_read_at")
        .eq("profile_id", profile["id"])
        .in_("partnership_id", partnership_ids)
        .execute()
        .data
    )
    last_read_by_id = {r["partnership_id"]: r["last_read_at"] for r in reads}

    messages = (
        supabase.table("messages")
        .select("partnership_id,sender_id,created_at,body")
        .in_("partnership_id", partnership_ids)
        .neq("sender_id", profile["id"])
        .order("created_at", desc=True)
        .execute()
        .data
    )

    unread = {}
    for m in messages:
        pid = m["partnership_id"]
        if pid in unread:
            continue  # already have the latest for this partnership
        cutoff = last_read_by_id.get(pid, started_at_by_id.get(pid))
        if not cutoff or m["created_at"] > cutoff:
            unread[pid] = m
    return unread


def mark_partnership_read(supabase, partnership_id, profile_id):
    supabase.table("message_reads").upsert({
        "partnership_id": partnership_id,
        "profile_id": profile_id,
        "last_read_at": datetime_now_iso(),
    }).execute()


def datetime_now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------- Rich text cleaning ----------
# Anything users type into a rich-text box is cleaned before it's saved or
# shown, so nobody can slip scripts or tracking into someone else's page.
import nh3

_LIST_TAGS = {"p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "a"}
_PITCH_TAGS = _LIST_TAGS | {"h2", "h3", "span", "img", "blockquote"}
_STYLE_PROPS = {"font-family", "font-weight", "font-style", "text-align", "text-decoration"}


def clean_list_html(html):
    """For Needs / Offers boxes: paragraphs, lists, bold, italics, links."""
    if not html:
        return None
    cleaned = nh3.clean(html, tags=_LIST_TAGS, attributes={"a": {"href", "title"}},
                        url_schemes={"http", "https", "mailto"}, link_rel="noopener noreferrer nofollow")
    return cleaned.strip() or None


def clean_pitch_html(html):
    """For pitches: as above plus headings, images and font choices."""
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=_PITCH_TAGS,
        attributes={"a": {"href", "title"}, "img": {"src", "alt", "width", "height"},
                    "*": {"style"}},
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer nofollow",
        filter_style_properties=_STYLE_PROPS,
    )


def tags_from_form(form, field, allowed):
    """Checkbox values from a form, kept only if they're in the allowed (slug, label) list."""
    allowed_slugs = {slug for slug, _ in allowed}
    return [t for t in form.getlist(field) if t in allowed_slugs]


# ---------- Trust badges ----------

def get_verifications(supabase, profile_ids):
    """{profile_id: set of verification kinds} for the given profiles."""
    ids = [i for i in set(profile_ids) if i]
    if not ids:
        return {}
    rows = (
        supabase.table("profile_verifications")
        .select("profile_id,kind")
        .in_("profile_id", ids)
        .execute()
        .data
    )
    out = {}
    for r in rows:
        out.setdefault(r["profile_id"], set()).add(r["kind"])
    return out


def get_id_verified_ids(supabase):
    """Profile ids holding an ID check — for the 'Verified only' filter."""
    rows = supabase.table("profile_verifications").select("profile_id").eq("kind", "id").execute().data
    return [r["profile_id"] for r in rows]


def get_ledger_waiting_on_me(supabase, profile, partnership_ids):
    """Ledger items that need this person: entries the other side added that they
    haven't confirmed yet, their own entries the other side has queried, and
    rates, recovery settlements or Goodwill-to-Recoverable changes the other
    side has asked them to agree, and open disputes waiting for them.
    Returns {partnership_id: {"confirm": n, "queried": n, "answer": n,
                              "dispute": n, "dispute_ids": [...]}}."""
    if not partnership_ids:
        return {}
    me = profile["id"]
    out = {}

    def bump(pid, key):
        out.setdefault(pid, {"confirm": 0, "queried": 0, "answer": 0, "dispute": 0, "dispute_ids": []})[key] += 1

    rows = (supabase.table("ledger_entries").select("partnership_id,status,added_by,class_change_to,class_change_by")
            .in_("partnership_id", partnership_ids)
            .or_("status.in.(pending,queried),class_change_to.not.is.null").is_("voided_at", "null").execute().data)
    for r in rows:
        mine = r["added_by"] == me
        if r["status"] == "queried" and mine:
            bump(r["partnership_id"], "queried")
        elif r["status"] == "pending" and not mine:
            bump(r["partnership_id"], "confirm")
        if r.get("class_change_to") and r.get("class_change_by") != me:
            bump(r["partnership_id"], "answer")
    # An open dispute needs you when the other person has proposed a resolution, when
    # you haven't given your side yet, or when they've written since you last did.
    disputes = (supabase.table("ledger_disputes").select("id,partnership_id,raised_by")
                .in_("partnership_id", partnership_ids).eq("status", "open").execute().data)
    if disputes:
        ids = [d["id"] for d in disputes]
        latest_author = {}
        spoke = set()
        for m in (supabase.table("ledger_dispute_messages").select("dispute_id,author,created_at")
                  .in_("dispute_id", ids).in_("kind", ["statement", "reply"])
                  .order("created_at").execute().data):
            if not m["author"]:
                continue
            latest_author[m["dispute_id"]] = m["author"]   # ends on the most recent
            if m["author"] == me:
                spoke.add(m["dispute_id"])
        waiting = {p["dispute_id"] for p in (supabase.table("ledger_dispute_proposals").select("dispute_id,proposed_by")
                   .in_("dispute_id", ids).eq("status", "proposed").execute().data) if p["proposed_by"] != me}
        for d in disputes:
            their_turn_done = latest_author.get(d["id"]) not in (None, me)
            if d["id"] in waiting or d["id"] not in spoke or their_turn_done:
                bump(d["partnership_id"], "dispute")
                out[d["partnership_id"]]["dispute_ids"].append(d["id"])
    for table in ("plan_rates", "recovery_settlements"):
        for r in (supabase.table(table).select("partnership_id,proposed_by")
                  .in_("partnership_id", partnership_ids).eq("status", "proposed").execute().data):
            if r["proposed_by"] != me:
                bump(r["partnership_id"], "answer")
    return out