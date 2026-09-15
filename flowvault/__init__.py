import secrets
import click
from flask import Flask, request, session, abort
from pymysql import MySQLError
from datetime import datetime, timedelta, timezone
from shutil import disk_usage
from werkzeug.middleware.proxy_fix import ProxyFix

from flowvault.config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    if not Config.SECRET_KEY:
        raise RuntimeError("SECRET_KEY/FLASK_SECRET_KEY must be configured")
    app.config.from_object(Config)
    if app.config["TRUSTED_PROXY_COUNT"]:
        trusted_proxy_count = app.config["TRUSTED_PROXY_COUNT"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxy_count, x_proto=trusted_proxy_count, x_host=trusted_proxy_count)
    from flowvault.routes.auth import auth_bp
    from flowvault.routes.files import files_bp
    from flowvault.routes.management import management_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(management_bp)

    @app.context_processor
    def csrf_context():
        token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return {"csrf_token": token}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.before_request
    def validate_csrf():
        if request.method == "POST" and request.endpoint != "static":
            expected = session.get("csrf_token")
            supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not expected or not supplied or not secrets.compare_digest(expected, supplied):
                abort(400, description="Invalid CSRF token")

    @app.context_processor
    def shared_layout_context():
        current_time = datetime.now(timezone(timedelta(hours=7), name="ICT"))
        display_date = current_time.strftime("%A, ") + str(current_time.day) + current_time.strftime(" %B %Y, %H:%M")
        usage = disk_usage(app.config["STORAGE_PATH"])
        total_gb = usage.total / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        return {
            "layout_date": display_date,
            "layout_storage": {
                "used": f"{used_gb:.1f}",
                "total": f"{total_gb:.1f}",
                "percent_used": round((usage.used / usage.total) * 100),
            },
        }

    @app.after_request
    def audit_authenticated_request(response):
        """Record every server-side action of an authenticated user.

        Request bodies are intentionally excluded: they may contain passwords,
        OTP values, or other private data.
        """
        email = session.get("user_email")
        if email and request.endpoint != "static":
            from flowvault.audit import record_event

            endpoint = (request.endpoint or "unknown")[:60]
            try:
                record_event(email, f"request_{request.method.lower()}", f"{endpoint} · {request.path} · HTTP {response.status_code}")
            except (MySQLError, OSError, TimeoutError):
                # Auditing must not turn an otherwise successful user request into a 500.
                app.logger.exception("Failed to record audit event for %s", endpoint)
        return response

    @app.cli.command("purge-recycle-bin")
    def purge_recycle_bin_command() -> None:
        """Permanently remove recycle-bin entries whose 15-day retention has expired."""
        from flowvault.routes.files import _purge_expired_recycle_items

        _purge_expired_recycle_items()
        click.echo("Expired recycle-bin items were purged.")

    return app
