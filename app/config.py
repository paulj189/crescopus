import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")
    REVENUECAT_API_KEY = os.environ.get("REVENUECAT_API_KEY")
    # Help popup from Crescontent. Each Render service (test, live) points at its own
    # Crescontent server and site. Leave CRESCONTENT_SITE_ID empty for no help button.
    CRESCONTENT_URL = os.environ.get("CRESCONTENT_URL", "https://crescontent.com").strip().rstrip("/")
    CRESCONTENT_SITE_ID = os.environ.get("CRESCONTENT_SITE_ID", "").strip()
    CRESCONTENT_VERIFY = os.environ.get("CRESCONTENT_VERIFY", "").strip()
