import os
from flask import Flask, render_template, session


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    from app.auth.routes import auth_bp
    from app.listings.routes import listings_bp
    from app.growers.routes import growers_bp
    from app.builders.routes import builders_bp
    from app.connection_requests.routes import connection_requests_bp
    from app.partnerships.routes import partnerships_bp
    from app.dashboard.routes import dashboard_bp
    from app.settings.routes import settings_bp
    from app.reporting.routes import reporting_bp
    from app.browse.routes import browse_bp
    from app.plans.routes import plans_bp
    from app.ledger.routes import ledger_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(growers_bp)
    app.register_blueprint(builders_bp)
    app.register_blueprint(connection_requests_bp)
    app.register_blueprint(partnerships_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(reporting_bp)
    app.register_blueprint(browse_bp)
    app.register_blueprint(plans_bp)
    app.register_blueprint(ledger_bp)

    # Template filters: clean user rich text before showing it, and turn tag slugs into labels.
    from app.utils import clean_list_html, clean_pitch_html
    from app import tags
    app.jinja_env.filters["clean_list"] = lambda html: clean_list_html(html) or ""
    app.jinja_env.filters["clean_pitch"] = clean_pitch_html
    app.jinja_env.filters["tag_labels"] = lambda slugs: [tags.labels().get(s, s) for s in (slugs or [])]

    import click
    from modcontent import Identity, Settings, SupabaseStore, create_blueprint, AnthropicMapper, TenantSettings
    from app.extensions import get_supabase_admin

    class _AdminClient:
        """Gives modcontent the secret-key client (server only, bypasses RLS)."""
        def __getattr__(self, name):
            return getattr(get_supabase_admin(), name)

    mc_store = SupabaseStore(_AdminClient())

    def mc_identity(request, tenant_id):
        user_id = session.get("user_id")
        if not user_id:
            return None
        member = mc_store.get_member(tenant_id, str(user_id))
        role = member["role"] if member and member["status"] == "active" else None
        return Identity(str(user_id), tenant_id, role)

    app.register_blueprint(
        create_blueprint(mc_store, Settings(
            identity_loader=mc_identity,
            allow_self_approval=os.environ.get("MC_ALLOW_SELF_APPROVAL") == "1",
            tenant_resolver=lambda request: app.config["MC_TENANT_ID"],
            image_base_url=f"{app.config['SUPABASE_URL']}/storage/v1/object/public/mc-images/",
            default_tenant_settings=TenantSettings(allow_anonymous=False, llm_calls_per_hour=20),
                        mapper=AnthropicMapper(context=(
                "Crescopus, a marketplace where app builders partner with growers who monetise "
                "and grow their apps, sharing the revenue. Topics include how partnerships, roles, "
                "revenue sharing and ending a partnership work."
            )) if os.environ.get("ANTHROPIC_API_KEY") else None,
        )),
        url_prefix="/content",
    )

    @app.cli.command("mc-bootstrap")
    @click.argument("user_id")
    @click.option("--role", default="approver")
    def mc_bootstrap(user_id, role):
        """Create the first content member, e.g. you as approver."""
        mc_store.put_member({"tenant_id": app.config["MC_TENANT_ID"],
                             "user_id": user_id, "role": role, "status": "active"})
        click.echo(f"{user_id} is now {role}")

    # Browsers (Samsung Internet especially) ask for /favicon.ico directly.
    @app.route("/favicon.ico")
    def favicon():
        from flask import send_from_directory
        return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon", max_age=86400)

    @app.route("/")
    def index():
        # Logged-in people go straight to their own Home; the landing page is for visitors.
        if session.get("user_id"):
            from flask import redirect, url_for
            return redirect(url_for("dashboard.index"))
        return render_template("index.html")

    @app.context_processor
    def inject_nav_context():
        from flask import request
        from app.utils import (
            current_profile,
            get_pending_received_requests,
            get_unread_partnerships,
            get_ledger_waiting_on_me,
        )
        from app.extensions import get_supabase

        profile = current_profile()
        # Signed in socially but not yet chosen Builder or Grower: no menu until they have.
        nav_setup = bool(profile) and not (profile.get("is_developer") or profile.get("is_grower"))
        if nav_setup:
            profile = None
        attention_count = 0
        nav_counts = {"home": 0, "crescos": 0, "messages": 0}
        is_popup = request.args.get("partial") == "1" or request.headers.get("X-Requested-With") == "fetch"
        if profile and not is_popup:
            from app.plans.routes import plan_summaries
            supabase = get_supabase()
            plans = plan_summaries(supabase, profile)
            plan_ids = {p["id"] for p in plans if p["active"]}
            received = get_pending_received_requests(supabase, profile)
            unread = [pid for pid in get_unread_partnerships(supabase, profile) if pid in plan_ids]
            ledger = get_ledger_waiting_on_me(supabase, profile, list(plan_ids))
            plans_waiting = sum(1 for p in plans if p["state"][0] == "you")
            attention_count = len(received) + len(unread) + len(ledger) + plans_waiting
            # Badges on the main menu: requests on Home, plan/ledger items on My Crescos, unread on Messages.
            nav_counts = {"home": len(received), "crescos": plans_waiting + len(ledger), "messages": len(unread)}

        # Which main menu item the current page belongs to.
        endpoint = request.endpoint or ""
        blueprint = endpoint.split(".")[0] if "." in endpoint else ""
        if endpoint == "partnerships.inbox":
            nav_section = "messages"
        elif blueprint in ("plans", "ledger", "partnerships", "reporting"):
            nav_section = "crescos"
        elif blueprint == "browse" and not endpoint.startswith(("browse.edit", "browse.withdraw")):
            nav_section = "find"
        elif blueprint == "settings":
            nav_section = "account"
        elif blueprint in ("dashboard", "listings", "connection_requests") or endpoint.startswith(("browse.edit", "browse.withdraw")):
            nav_section = "home"
        else:
            nav_section = ""
        top_level = endpoint in ("index", "dashboard.index", "browse.index", "plans.index",
                                 "partnerships.inbox", "settings.index", "auth.login", "auth.signup", "auth.finish")
        return dict(nav_profile=profile, nav_setup=nav_setup, attention_count=attention_count, nav_counts=nav_counts,
                    nav_section=nav_section, nav_top_level=top_level)

    return app
