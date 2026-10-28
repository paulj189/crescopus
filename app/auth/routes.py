import os
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from supabase import create_client
from app.extensions import get_supabase, get_supabase_admin
from app.constants import COUNTRIES

auth_bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="../templates/auth")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        full_name = request.form.get("full_name", "")
        country = request.form.get("country", "")
        role = request.form.get("role")

        if role not in ("developer", "grower"):
            flash("Please choose whether you're a builder or a grower.", "error")
            return render_template("auth/signup.html", countries=COUNTRIES)

        is_developer = role == "developer"
        is_grower = role == "grower"
        bio = request.form.get("bio", "").strip()

        supabase = get_supabase()
        result = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name,
                    "is_developer": is_developer,
                    "is_grower": is_grower,
                    "country": country,
                    "bio": bio,
                }
            },
        })

        if result.user is None:
            flash("Couldn't create that account — check your details and try again.", "error")
            return render_template("auth/signup.html", countries=COUNTRIES)

        flash("Check your email to confirm your account.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/signup.html", countries=COUNTRIES)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        supabase = get_supabase()
        try:
            result = supabase.auth.sign_in_with_password({"email": email, "password": password})
        except Exception:
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html")

        session["access_token"] = result.session.access_token
        session["refresh_token"] = result.session.refresh_token
        session["user_id"] = result.user.id

        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Social login (Google, LinkedIn, GitHub) through Supabase Auth.
#
# 1. /auth/social/<provider> asks Supabase for the provider's sign-in page and
#    sends the person there. The PKCE "code verifier" is kept in their Flask
#    session so step 2 can prove it started the sign-in.
# 2. The provider sends them back to /auth/callback?code=..., which swaps the
#    code for a Supabase session, the same as a password login.
# 3. Someone new (no Builder/Grower role yet) is sent to /auth/finish once.
#
# An existing email-and-password account with the same verified email is
# signed straight in: Supabase links the identities automatically.
# ---------------------------------------------------------------------------

PROVIDERS = {
    "google": ("google", "Google"),
    "linkedin": ("linkedin_oidc", "LinkedIn"),
    "github": ("github", "GitHub"),
}
PHOTO_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
PHOTO_MAX_BYTES = 2 * 1024 * 1024


@auth_bp.app_context_processor
def _social_logos():
    """Each provider's official logo, if it's been saved in static/img/social/
    as google, linkedin or github (.svg or .png). Missing ones are simply left off."""
    from flask import current_app

    def social_logo(provider):
        folder = os.path.join(current_app.static_folder, "img", "social")
        for ext in ("svg", "png"):
            if os.path.isfile(os.path.join(folder, f"{provider}.{ext}")):
                return url_for("static", filename=f"img/social/{provider}.{ext}")
        return None
    return {"social_logo": social_logo}


def _fresh_client():
    """A client with no signed-in user, used only for the sign-in handshake."""
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_PUBLISHABLE_KEY"])


def _callback_url():
    url = url_for("auth.oauth_callback", _external=True)
    # Render serves over https but talks to the app over http behind its proxy.
    if url.startswith("http://") and request.headers.get("X-Forwarded-Proto", "") == "https":
        url = "https://" + url[len("http://"):]
    return url


def _start_session(auth_session, user):
    session["access_token"] = auth_session.access_token
    session["refresh_token"] = auth_session.refresh_token
    session["user_id"] = user.id
    g.pop("current_profile", None)
    g.pop("supabase_client", None)


@auth_bp.route("/social/<provider>")
def social_start(provider):
    if provider not in PROVIDERS:
        flash("That sign-in option isn't available.", "error")
        return redirect(url_for("auth.login"))
    supabase_name, label = PROVIDERS[provider]
    client = _fresh_client()
    try:
        res = client.auth.sign_in_with_oauth({
            "provider": supabase_name,
            "options": {"redirect_to": _callback_url()},
        })
        storage = client.auth._storage
        verifier = storage.get_item(f"{client.auth._storage_key}-code-verifier")
    except Exception:  # noqa: BLE001
        flash(f"Couldn't reach {label} just now. Please try again, or use your email and password.", "error")
        return redirect(url_for("auth.login"))
    session["oauth_verifier"] = verifier
    session["oauth_provider"] = provider
    return redirect(res.url)


@auth_bp.route("/callback")
def oauth_callback():
    provider = session.pop("oauth_provider", None)
    verifier = session.pop("oauth_verifier", None)
    label = PROVIDERS.get(provider, (None, "that service"))[1]

    if request.args.get("error"):
        # Most often the person pressed Cancel on the provider's page.
        flash(f"Sign-in with {label} was cancelled or didn't complete.", "error")
        return redirect(url_for("auth.login"))
    code = request.args.get("code")
    if not code or not verifier:
        flash("That sign-in link has expired. Please try again.", "error")
        return redirect(url_for("auth.login"))

    try:
        res = _fresh_client().auth.exchange_code_for_session({
            "auth_code": code, "code_verifier": verifier, "redirect_to": _callback_url(),
        })
    except Exception:  # noqa: BLE001
        flash(f"Couldn't sign you in with {label}. Please try again.", "error")
        return redirect(url_for("auth.login"))
    if not res.session or not res.user:
        flash(f"Couldn't sign you in with {label}. Please try again.", "error")
        return redirect(url_for("auth.login"))

    session.clear()
    _start_session(res.session, res.user)
    meta = res.user.user_metadata or {}
    session["social"] = {
        "provider": provider,
        "label": label,
        "name": (meta.get("full_name") or meta.get("name") or "").strip()[:120],
        "photo": meta.get("avatar_url") or meta.get("picture") or "",
    }

    from app.utils import current_profile
    profile = current_profile()
    if profile and (profile.get("is_developer") or profile.get("is_grower")):
        session.pop("social", None)
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.finish"))


def _copy_photo(url, profile_id):
    """Copies the provider's photo into our own storage (LinkedIn's links expire).
    Returns our public URL, or None if it couldn't be fetched."""
    import requests
    if not url.startswith("https://"):
        return None
    try:
        r = requests.get(url, timeout=8, stream=True)
        ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if r.status_code != 200 or ctype not in PHOTO_TYPES:
            return None
        data = b""
        for chunk in r.iter_content(64 * 1024):
            data += chunk
            if len(data) > PHOTO_MAX_BYTES:
                return None
        if not data:
            return None
        path = f"{profile_id}/{uuid.uuid4()}.{PHOTO_TYPES[ctype]}"
        bucket = get_supabase_admin().storage.from_("listing-media")
        bucket.upload(path, data, {"content-type": ctype})
        return bucket.get_public_url(path)
    except Exception:  # noqa: BLE001
        return None


@auth_bp.route("/finish", methods=["GET", "POST"])
def finish():
    """One-off step after a first social sign-in: Builder or Grower, country, and
    (if offered) using their photo. Email-and-password signups give these up front."""
    from app.utils import current_profile
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    profile = current_profile()
    if not profile:
        flash("We couldn't find your account. Please try signing in again.", "error")
        return redirect(url_for("auth.logout"))
    if profile.get("is_developer") or profile.get("is_grower"):
        return redirect(url_for("dashboard.index"))

    social = session.get("social") or {}
    can_use_photo = bool(social.get("photo")) and not profile.get("hero_image_url")
    values = {
        "full_name": profile.get("full_name") or social.get("name") or "",
        "country": profile.get("country") or "",
        "role": "", "bio": "", "use_photo": can_use_photo,
    }

    if request.method == "POST":
        values.update(
            full_name=(request.form.get("full_name") or "").strip()[:120],
            country=request.form.get("country") or "",
            role=request.form.get("role") or "",
            bio=(request.form.get("bio") or "").strip()[:2000],
            use_photo=bool(request.form.get("use_photo")),
        )
        errors = []
        if values["role"] not in ("developer", "grower"):
            errors.append("Please choose whether you're a Builder or a Grower.")
        if not values["full_name"]:
            errors.append("Please add your name.")
        if values["country"] not in {code for code, _ in COUNTRIES}:
            errors.append("Please choose your country.")
        if not errors:
            update = {
                "full_name": values["full_name"],
                "country": values["country"],
                "is_developer": values["role"] == "developer",
                "is_grower": values["role"] == "grower",
            }
            if values["bio"]:
                update["bio"] = values["bio"]
            photo_failed = False
            if values["use_photo"] and can_use_photo:
                photo = _copy_photo(social["photo"], profile["id"])
                if photo:
                    update["hero_image_url"] = photo
                else:
                    photo_failed = True
            # Only ever sets a role on an account that doesn't have one yet.
            (get_supabase_admin().table("profiles").update(update)
             .eq("id", profile["id"]).eq("is_developer", False).eq("is_grower", False).execute())
            session.pop("social", None)
            g.pop("current_profile", None)
            flash("Welcome to Crescopus!" + (" We couldn't copy your photo, so you can add one on your card instead."
                                             if photo_failed else ""), "success")
            return redirect(url_for("dashboard.index"))
        for e in errors:
            flash(e, "error")

    return render_template("auth/finish.html", values=values, countries=COUNTRIES,
                           social=social, can_use_photo=can_use_photo)


@auth_bp.before_app_request
def _require_finished_profile():
    """Someone who signed in socially but hasn't picked Builder or Grower is sent
    to finish that first, so they never land in the app without a menu."""
    if "user_id" not in session:
        return None
    endpoint = request.endpoint or ""
    if endpoint.startswith("auth.") or endpoint in ("static", "favicon") or not endpoint:
        return None
    from app.utils import current_profile
    profile = current_profile()
    if profile and not (profile.get("is_developer") or profile.get("is_grower")):
        return redirect(url_for("auth.finish"))
    return None
