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


STREAM_TYPE_LABELS = {
    "store_iap": "Store subscriptions / in-app purchases",
    "web_revenuecat": "Web payments (via RevenueCat)",
    "advertising": "Advertising",
    "existing_processor": "Existing payment processor",
    "no_stream_yet": "No revenue stream yet",
    "other": "Other",
}


def stream_type_label(value):
    return STREAM_TYPE_LABELS.get(value, value)


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
