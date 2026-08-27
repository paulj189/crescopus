from flask import Flask, render_template


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    from app.utils import stream_type_label
    app.jinja_env.filters["stream_type_label"] = stream_type_label

    from app.auth.routes import auth_bp
    from app.listings.routes import listings_bp
    from app.growers.routes import growers_bp
    from app.connection_requests.routes import connection_requests_bp
    from app.partnerships.routes import partnerships_bp
    from app.dashboard.routes import dashboard_bp
    from app.settings.routes import settings_bp
    from app.reporting.routes import reporting_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(growers_bp)
    app.register_blueprint(connection_requests_bp)
    app.register_blueprint(partnerships_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(reporting_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
