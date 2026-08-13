import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")
    REVENUECAT_API_KEY = os.environ.get("REVENUECAT_API_KEY")
