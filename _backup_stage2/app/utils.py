from functools import wraps
from flask import session, redirect, url_for
from app.extensions import get_supabase


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def current_profile():
    if "user_id" not in session:
        return None
    supabase = get_supabase()
    res = supabase.table("profiles").select("*").eq("id", session["user_id"]).execute()
    if not res.data:
        return None
    return res.data[0]


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
