import os
from flask import g, session
from supabase import create_client, Client

_supabase_admin: Client | None = None


def get_supabase() -> Client:
    """Client scoped to the publishable key (sb_publishable_...), with the
    current request's user session applied so RLS policies checking
    auth.uid() see the right person.

    Created fresh per request (cached on flask.g, never on a module-level
    global) — a shared client across requests/users would apply whichever
    user logged in most recently to every request, which is exactly what
    was causing cross-user RLS failures.
    """
    if "supabase_client" not in g:
        client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_PUBLISHABLE_KEY"])
        access_token = session.get("access_token")
        refresh_token = session.get("refresh_token")
        if access_token and refresh_token:
            try:
                client.auth.set_session(access_token, refresh_token)
                # set_session can silently refresh an expired access token —
                # persist the current one so we're not refreshing every request.
                current = client.auth.get_session()
                if current:
                    session["access_token"] = current.access_token
                    session["refresh_token"] = current.refresh_token
            except Exception:
                # Expired/invalid session — proceed unauthenticated. RLS will
                # just restrict this request as if logged out, rather than
                # crashing; login_required-guarded routes still redirect
                # since current_profile() will come back empty.
                session.pop("access_token", None)
                session.pop("refresh_token", None)
        g.supabase_client = client
    return g.supabase_client


def get_supabase_admin() -> Client:
    """Secret-key client (sb_secret_...). Bypasses RLS — use only for trusted,
    server-initiated writes such as the payment webhook handler. Carries no
    per-user identity, so a shared singleton is safe here."""
    global _supabase_admin
    if _supabase_admin is None:
        _supabase_admin = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    return _supabase_admin
