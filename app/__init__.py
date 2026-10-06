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

    app.register_blueprint(auth_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(growers_bp)
    app.register_blueprint(builders_bp)
    app.register_blueprint(connection_requests_bp)
    app.register_blueprint(partnerships_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(reporting_bp)

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

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.context_processor
    def inject_nav_context():
        from app.utils import (
            current_profile,
            get_pending_received_requests,
            get_formalise_waiting_on_me,
            get_unread_partnerships,
        )
        from app.extensions import get_supabase

        profile = current_profile()
        attention_count = 0
        if profile:
            supabase = get_supabase()
            received = get_pending_received_requests(supabase, profile)
            formalise_waiting = get_formalise_waiting_on_me(supabase, profile)
            unread = get_unread_partnerships(supabase, profile)
            attention_count = len(received) + len(formalise_waiting) + len(unread)
        return dict(nav_profile=profile, attention_count=attention_count)

    return app
