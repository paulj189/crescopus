"""Load the Crescopus v1 draft pages into the content library.

Run from the Crescopus folder, with the venv active:

    python load_pages.py <your-user-id>            # create the pages as drafts
    python load_pages.py <your-user-id> --check    # show what would happen, change nothing

Pages are always created as DRAFTS. Nothing is published: each page still has to be edited,
submitted and approved by a different person. A key that already exists is skipped, so it is
safe to run twice. Delete this file and crescopus_pages_v1.py when you are done.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client  # noqa: E402

from crescopus_pages_v1 import PAGES, fields_for  # noqa: E402
from modcontent import ContentService, Identity, Settings, SupabaseStore  # noqa: E402
from modcontent.errors import McError  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
check_only = "--check" in sys.argv
if len(args) != 1:
    sys.exit("Usage: python load_pages.py <your-user-id> [--check]")

user_id, tenant_id = args[0], os.environ["MC_TENANT_ID"]
store = SupabaseStore(create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]))
settings = Settings(
    identity_loader=lambda request, tenant: None,
    image_base_url=f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/mc-images/",
)
service = ContentService(store, settings)
editor = Identity(user_id, tenant_id, "editor")  # the pages are recorded as written by this user

created = skipped = failed = confirms = 0
for page in PAGES:
    fields = fields_for(page)
    confirms += sum(f["value"].count("[CONFIRM") for f in fields.values())
    if store.find_item_by_key(tenant_id, page["key"]):
        print(f"  skipped  {page['key']}  (already exists)")
        skipped += 1
        continue
    if check_only:
        print(f"  would create  {page['key']}")
        continue
    try:
        service.create_item(editor, page["key"], page["title"], fields,
                            tags=page["tags"], disclaimer=page["disclaimer"])
        print(f"  created  {page['key']}")
        created += 1
    except McError as err:
        print(f"  FAILED   {page['key']}: {err}")
        failed += 1

print(f"\n{created} created, {skipped} skipped, {failed} failed.")
print(f"{confirms} [CONFIRM] notes need checking before the pages can be submitted for review.")
print("The pages are drafts. Open /content/editor to edit them.")
