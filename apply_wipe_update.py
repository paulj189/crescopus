r"""
Crescopus - wipe script also clears content-tools access

  - sql/testing/1_wipe_everything.sql now also clears mc_members (who can
    use the content tools) and mc_view_log (who viewed what).
  - The content itself (mc_items, mc_versions, mc_nav_rules, mc_change_log)
    is kept.
  - The final check's comment now explains tags_kept (should be 14).

HOW TO USE
  1. Save this file in your Crescopus project folder (next to wsgi.py).
  2. In PowerShell, in that folder:
         python apply_wipe_update.py

Nothing in the app changes. Your .env is never read or changed.
"""
import base64, hashlib, os, shutil, sys

# (path, new content, sha256s of the versions it may replace)
FILES = [
    ('sql/testing/1_wipe_everything.sql', 'LS0gPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09Ci0tIENyZXNjb3B1cyBURVNUSU5HOiB3aXBlIGV2ZXJ5IHVzZXIgYW5kIGFsbCB0aGVpciBkYXRhCi0tCi0tICEhIFRoaXMgZGVsZXRlcyBFVkVSWSBhY2NvdW50IChpbmNsdWRpbmcgeW91ciBvd24pIGFuZCBldmVyeXRoaW5nCi0tICEhIGxpbmtlZCB0byB0aGVtOiBjYXJkcywgQ3Jlc2NvcywgcGxhbnMsIGxlZGdlcnMsIGRpc3B1dGVzLCBtZXNzYWdlcy4KLS0gISEgSXQgY2FuJ3QgYmUgdW5kb25lLiBPbmx5IHJ1biBpdCB3aGlsZSBDcmVzY29wdXMgaGFzIG5vIHJlYWwgdXNlcnMuCi0tCi0tIEtlcHQ6IHRoZSB0YWcgbGlzdCAoTmVlZHMgLyBPZmZlcnMgb3B0aW9ucykgYW5kIHRoZSBzaXRlJ3MgY29udGVudCBwYWdlcwotLSAgICAgICAobWNfaXRlbXMsIG1jX3ZlcnNpb25zLCBtY19uYXZfcnVsZXMsIG1jX2NoYW5nZV9sb2cpLgotLSBDbGVhcmVkIGZyb20gdGhlIGNvbnRlbnQgdG9vbHM6IHdobyBoYXMgYWNjZXNzIChtY19tZW1iZXJzKSBhbmQgd2hvCi0tICAgICAgIHZpZXdlZCB3aGF0IChtY192aWV3X2xvZyksIGFzIHRob3NlIHBvaW50IGF0IGFjY291bnRzIGJlaW5nIGRlbGV0ZWQuCi0tIFJ1biBpbiB0aGUgU3VwYWJhc2UgU1FMIGVkaXRvci4gU2FmZSB0byByZS1ydW4uCi0tCi0tIEFmdGVyd2FyZHM6Ci0tICAgLSBTaWduIHVwIGFnYWluIHlvdXJzZWxmIChvciBydW4gMl9sb2FkX3Rlc3Rfc2NlbmFyaW9zLnNxbCkuCi0tICAgLSBDb250ZW50LXRvb2xzIGFjY2VzcyBpcyBjbGVhcmVkLCBzbyBhZnRlciBzaWduaW5nIHVwIGFnYWluIHJ1bgotLSAgICAgYGZsYXNrIG1jLWJvb3RzdHJhcCA8eW91ciBuZXcgdXNlciBpZD5gIHRvIG1ha2UgeW91cnNlbGYgYXBwcm92ZXIuCi0tICAgLSBVcGxvYWRlZCBpbWFnZXMgc3RheSBpbiBTdG9yYWdlIChoYXJtbGVzcykuIFRvIGNsZWFyIHRoZW0gdG9vOgotLSAgICAgU3RvcmFnZSAtPiBsaXN0aW5nLW1lZGlhIC0+IHNlbGVjdCBhbGwgLT4gRGVsZXRlLgotLSA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KCmJlZ2luOwoKZG8gJCQKZGVjbGFyZQogIC0tIEV2ZXJ5IHRhYmxlIHRoYXQgaG9sZHMgdXNlciBkYXRhLiBUYWJsZXMgdGhhdCBkb24ndCBleGlzdCBhcmUgc2tpcHBlZC4KICB3YW50ZWQgdGV4dFtdIDo9IGFycmF5WwogICAgJ3RyYWNraW5nX2V2ZW50cycsICd0cmFja2luZ19zbmlwcGV0cycsCiAgICAncmVjb3Zlcnlfc2V0dGxlbWVudF9lbnRyaWVzJywgJ3JlY292ZXJ5X3NldHRsZW1lbnRzJywKICAgICdsZWRnZXJfZGlzcHV0ZV9wcm9wb3NhbHMnLCAnbGVkZ2VyX2Rpc3B1dGVfbWVzc2FnZXMnLCAnbGVkZ2VyX2Rpc3B1dGVfZW50cmllcycsICdsZWRnZXJfZGlzcHV0ZXMnLAogICAgJ2xlZGdlcl9lbnRyeV9ldmVudHMnLCAnbGVkZ2VyX2VudHJpZXMnLCAncGxhbl9yYXRlcycsCiAgICAncGxhbl92ZXJzaW9ucycsICdwbGFuX3NpZ25vZmZzJywgJ3BsYW5fYWN0aW9ucycsICdwbGFuX21lYXN1cmVzJywgJ2NyZXNjb19wbGFucycsCiAgICAnbWVzc2FnZV9yZWFkcycsICdtZXNzYWdlcycsCiAgICAncmV2ZW51ZV9yZXBvcnRzJywgJ2VuZ2FnZW1lbnRfcmVwb3J0cycsICdnYXBfb2ZmZXJzJywgJ3Jldmlld3MnLAogICAgJ3BhcnRuZXJzaGlwcycsICdjb25uZWN0aW9uX3JlcXVlc3RzJywKICAgICdsaXN0aW5nX2ltYWdlcycsICdyZXZlbnVlX3N0cmVhbXMnLCAncHJvcG9zYWxzJywgJ2xpc3RpbmdzJywKICAgICdhaV91c2FnZScsICdwcmVtaXVtX2ludGVyZXN0JywgJ2FjY291bnRfZW50aXRsZW1lbnRzJywgJ3Byb2ZpbGVfdmVyaWZpY2F0aW9ucycsCiAgICAncHJvZmlsZXMnLAogICAgLS0gQ29udGVudCB0b29sczogYWNjZXNzIGFuZCB2aWV3aW5nIGhpc3RvcnkgKHRoZSBjb250ZW50IGl0c2VsZiBpcyBrZXB0KS4KICAgICdtY19tZW1iZXJzJywgJ21jX3ZpZXdfbG9nJwogIF07CiAgcHJlc2VudCB0ZXh0W10gOj0gJ3t9JzsKICB0IHRleHQ7CmJlZ2luCiAgZm9yZWFjaCB0IGluIGFycmF5IHdhbnRlZCBsb29wCiAgICBpZiB0b19yZWdjbGFzcygncHVibGljLicgfHwgdCkgaXMgbm90IG51bGwgdGhlbgogICAgICBwcmVzZW50IDo9IHByZXNlbnQgfHwgdDsKICAgIGVuZCBpZjsKICBlbmQgbG9vcDsKICAtLSBPbmUgVFJVTkNBVEUgZm9yIGFsbCBvZiB0aGVtLCBzbyB0aGUgbGlua3MgYmV0d2VlbiB0aGVtIGRvbid0IGdldCBpbiB0aGUgd2F5LgogIGV4ZWN1dGUgJ3RydW5jYXRlIHRhYmxlICcgfHwKICAgICAgICAgIChzZWxlY3Qgc3RyaW5nX2FnZyhmb3JtYXQoJ3B1YmxpYy4lSScsIHgpLCAnLCAnKSBmcm9tIHVubmVzdChwcmVzZW50KSB4KTsKZW5kICQkOwoKLS0gVGhlIGFjY291bnRzIHRoZW1zZWx2ZXMgKHRoZWlyIHNpZ24taW4gaWRlbnRpdGllcyBnbyB3aXRoIHRoZW0pLgpkZWxldGUgZnJvbSBhdXRoLnVzZXJzOwoKY29tbWl0OwoKLS0gQ2hlY2s6IGV2ZXJ5dGhpbmcgc2hvdWxkIGJlIDAsIGV4Y2VwdCB0YWdzX2tlcHQgKHlvdXIgTmVlZHMgLyBPZmZlcnMgdGFnIGxpc3QsIDE0KS4Kc2VsZWN0IChzZWxlY3QgY291bnQoKikgZnJvbSBhdXRoLnVzZXJzKSAgICBhcyB1c2VycywKICAgICAgIChzZWxlY3QgY291bnQoKikgZnJvbSBwcm9maWxlcykgICAgICBhcyBwcm9maWxlcywKICAgICAgIChzZWxlY3QgY291bnQoKikgZnJvbSBsaXN0aW5ncykgICAgICBhcyBhcHBfY2FyZHMsCiAgICAgICAoc2VsZWN0IGNvdW50KCopIGZyb20gcGFydG5lcnNoaXBzKSAgYXMgY3Jlc2NvcywKICAgICAgIChzZWxlY3QgY291bnQoKikgZnJvbSBsZWRnZXJfZW50cmllcykgYXMgbGVkZ2VyX2VudHJpZXMsCiAgICAgICAoc2VsZWN0IGNvdW50KCopIGZyb20gdGFnX29wdGlvbnMpICAgYXMgdGFnc19rZXB0Owo=', ['03812aff8e9f7721fee0fadd100d8674d94cf39977aabbaad54990996dee75d9']),
]
BACKUP = "_backup_apply_wipe_update"
NEXT = "commit and push. After the next wipe, sign up again and run flask mc-bootstrap <your new user id>."

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile(os.path.join(root, "app", "__init__.py")) or not os.path.isfile(os.path.join(root, "wsgi.py")):
        sys.exit("Stopped: put this file in the Crescopus project folder (next to wsgi.py and the app folder), then run it again.")

    # Safety check first: never overwrite local changes we don't know about.
    clashes = []
    for rel, b64, expected in FILES:
        path = os.path.join(root, *rel.split("/"))
        new = base64.b64decode(b64)
        if not os.path.exists(path):
            if expected:
                clashes.append(rel + " (missing)")
            continue
        with open(path, "rb") as fh:
            current = fh.read()
        current_norm = current.replace(b"\r\n", b"\n")
        if current == new or current_norm == new:
            continue
        if not expected or sha(current_norm) not in expected:
            clashes.append(rel)
    if clashes:
        print("Stopped - nothing written. These files differ from the version this update was built from:")
        for c in clashes:
            print("   " + c)
        sys.exit("Push or share your latest changes and ask for the update to be rebuilt.")

    backup = os.path.join(root, BACKUP)
    changed = 0
    for rel, b64, expected in FILES:
        path = os.path.join(root, *rel.split("/"))
        data = base64.b64decode(b64)
        status = "new     "
        if os.path.exists(path):
            with open(path, "rb") as fh:
                current = fh.read()
            if current == data or current.replace(b"\r\n", b"\n") == data:
                print("same     " + rel)
                continue
            dest = os.path.join(backup, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(path, dest)
            status = "updated "
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        changed += 1
        print(status + " " + rel)
    print("\nDone - %d of %d files written." % (changed, len(FILES)))
    if os.path.isdir(backup):
        print("Originals of replaced files are in " + BACKUP + os.sep)
    if NEXT:
        print("Next: " + NEXT)

if __name__ == "__main__":
    main()
