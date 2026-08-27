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
