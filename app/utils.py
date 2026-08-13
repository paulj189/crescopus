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
    res = supabase.table("profiles").select("*").eq("id", session["user_id"]).single().execute()
    return res.data
