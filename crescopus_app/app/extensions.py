import os
from supabase import create_client, Client

_supabase: Client | None = None
_supabase_admin: Client | None = None


def get_supabase() -> Client:
    """Client scoped to the publishable key (sb_publishable_...). Respects RLS —
    use for anything done on behalf of the logged-in user."""
    global _supabase
    if _supabase is None:
        _supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_PUBLISHABLE_KEY"])
    return _supabase


def get_supabase_admin() -> Client:
    """Secret-key client (sb_secret_...). Bypasses RLS — use only for trusted,
    server-initiated writes such as the payment webhook handler."""
    global _supabase_admin
    if _supabase_admin is None:
        _supabase_admin = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    return _supabase_admin
