"""Temporary diagnostic. Put this in the Crescopus folder and run, with the venv active:

    python mc_debug.py "who makes money from my app?"

It shows the approved pages the AI is given and exactly what the model replies.
Delete it when you are done.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client  # noqa: E402

from modcontent import AnthropicMapper, SupabaseStore  # noqa: E402
from modcontent.navigator import body_text  # noqa: E402

CONTEXT = (
    "Crescopus, a marketplace where app builders partner with growers who monetise and "
    "grow their apps, sharing the revenue. Topics include how partnerships, roles, "
    "revenue sharing and ending a partnership work."
)
question = " ".join(sys.argv[1:]) or "who makes money from my app?"
store = SupabaseStore(create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]))
approved = store.list_approved(os.environ["MC_TENANT_ID"])

print(f"\n{len(approved)} approved page(s):")
candidates = []
for a in approved:
    summary = body_text(a, 300)
    candidates.append({"id": a["item_id"], "title": a["title"], "tags": a["tags"], "summary": summary})
    print(f"  - {a['title']!r}  tags={a['tags']}  text={summary[:80]!r}")

if not approved:
    sys.exit("\nNothing is approved yet, so there is nothing to match against.")

mapper = AnthropicMapper(context=CONTEXT)
ids = mapper(question, candidates)
print(f"\nQuestion: {question}")
print(f"Model's raw reply: {mapper.last_raw!r}")
print(f"Page ids it chose: {ids}")
