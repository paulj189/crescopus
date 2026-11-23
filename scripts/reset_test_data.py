"""Clear Crescopus test data from the Supabase test project.

Deletes every Cresco, plan, ledger, dispute, message, connection request, app
card, revenue agreement and uploaded image, and (unless --keep-users) every
account. Keeps the Needs / Offers tag list and the site's content pages.

Safety: refuses to run unless RESET_ALLOWED_REF matches the project in
SUPABASE_URL, so it can never touch the live project by mistake.

    python scripts/reset_test_data.py            # asks you to type RESET
    python scripts/reset_test_data.py --yes      # no prompt (GitHub Action)
    python scripts/reset_test_data.py --yes --keep-users

Needs SUPABASE_URL, SUPABASE_SECRET_KEY and RESET_ALLOWED_REF (from the
environment or a .env file).
"""
import argparse
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from supabase import create_client

# Children before parents, so foreign keys never get in the way.
# Each entry: (table, a column that's never empty, used to match every row).
DATA_TABLES = [
    ("tracking_events", "id"), ("tracking_snippets", "id"),
    ("recovery_settlement_entries", "settlement_id"), ("recovery_settlements", "id"),
    ("ledger_dispute_proposals", "id"), ("ledger_dispute_messages", "id"),
    ("ledger_dispute_entries", "dispute_id"), ("ledger_disputes", "id"),
    ("ledger_entry_events", "id"), ("ledger_entries", "id"), ("plan_rates", "id"),
    ("plan_versions", "id"), ("plan_signoffs", "plan_id"),
    ("plan_actions", "id"), ("plan_measures", "id"), ("cresco_plans", "id"),
    ("revenue_versions", "id"), ("revenue_signoffs", "agreement_id"), ("revenue_agreements", "id"),
    ("message_reads", "partnership_id"), ("messages", "id"),
    ("revenue_reports", "id"), ("engagement_reports", "id"), ("gap_offers", "id"), ("reviews", "id"),
    ("partnerships", "id"), ("connection_requests", "id"),
    ("listing_images", "id"), ("revenue_streams", "id"), ("proposals", "id"), ("listings", "id"),
]
# Linked to accounts: cleared only when the accounts go too.
ACCOUNT_TABLES = [
    ("ai_usage", "id"), ("premium_interest", "profile_id"), ("account_entitlements", "profile_id"),
    ("profile_verifications", "profile_id"), ("mc_members", "user_id"), ("mc_view_log", "id"),
    ("profiles", "id"),
]
BUCKETS = ["listing-media"]
FALLBACK_COLUMNS = ["id", "profile_id", "user_id", "created_at"]


def project_ref(url):
    return (urlparse(url).hostname or "").split(".")[0]


def clear_table(sb, table, column):
    """Delete every row. Returns the number deleted, or None if the table doesn't exist."""
    for col in [column] + [c for c in FALLBACK_COLUMNS if c != column]:
        try:
            rows = sb.table(table).delete().not_.is_(col, "null").execute().data
            return len(rows or [])
        except Exception as err:  # noqa: BLE001
            msg = str(err)
            if "PGRST205" in msg or "42P01" in msg or "Could not find the table" in msg:
                return None
            if "42703" in msg or "does not exist" in msg:  # wrong column: try the next one
                continue
            raise
    raise RuntimeError(f"Couldn't find a column to clear {table} by")


def clear_bucket(sb, bucket):
    store = sb.storage.from_(bucket)
    removed = 0

    def walk(prefix):
        nonlocal removed
        while True:
            items = store.list(prefix, {"limit": 1000, "offset": 0})
            files = [f"{prefix}/{i['name']}".lstrip("/") for i in items if i.get("id")]
            folders = [f"{prefix}/{i['name']}".lstrip("/") for i in items if not i.get("id")]
            for folder in folders:
                walk(folder)
            if not files:
                return
            store.remove(files)
            removed += len(files)

    try:
        walk("")
    except Exception as err:  # noqa: BLE001
        print(f"  {bucket}: skipped ({err})")
        return
    print(f"  {bucket}: {removed} file(s) removed")


def delete_users(sb):
    deleted = 0
    while True:
        users = sb.auth.admin.list_users(page=1, per_page=1000)
        if not users:
            return deleted
        for u in users:
            sb.auth.admin.delete_user(u.id)
            deleted += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    parser.add_argument("--keep-users", action="store_true", help="keep accounts, profiles and uploaded images")
    args = parser.parse_args()

    load_dotenv()
    url, key = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_SECRET_KEY", "")
    allowed = os.environ.get("RESET_ALLOWED_REF", "").strip()
    if not url or not key:
        sys.exit("SUPABASE_URL and SUPABASE_SECRET_KEY must be set.")
    ref = project_ref(url)
    if not allowed:
        sys.exit("RESET_ALLOWED_REF isn't set, so nothing was deleted. Set it to the test project's ref.")
    if ref != allowed:
        sys.exit(f"Refusing to run: SUPABASE_URL is project '{ref}', but RESET_ALLOWED_REF is '{allowed}'.")

    what = "all test data" + ("" if args.keep_users else ", every account and all uploaded images")
    if not args.yes:
        if input(f"This deletes {what} from project {ref}. Type RESET to continue: ").strip() != "RESET":
            sys.exit("Cancelled.")

    sb = create_client(url, key)
    print(f"Clearing project {ref}...")
    tables = DATA_TABLES + ([] if args.keep_users else ACCOUNT_TABLES)
    for table, column in tables:
        n = clear_table(sb, table, column)
        print(f"  {table}: " + ("not present, skipped" if n is None else f"{n} row(s) deleted"))

    if not args.keep_users:
        for bucket in BUCKETS:
            clear_bucket(sb, bucket)
        print(f"  accounts: {delete_users(sb)} deleted")

    print("Done. Kept: the Needs / Offers tag list and the site's content pages."
          + (" Accounts and profiles were kept." if args.keep_users else ""))


if __name__ == "__main__":
    main()
