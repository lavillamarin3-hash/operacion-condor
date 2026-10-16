"""MVC Flask factory for the isolated Operación Cóndor training application."""

import os
from pathlib import Path

from flask import Flask, Response, g, render_template
from werkzeug.exceptions import HTTPException, SecurityError

from condor_app import db
from condor_app.config import environment_config, validate_config
from condor_app.controllers import admin, auth, public
from condor_app.services import lab_service, security


def create_app(test_config=None):
    instance_path = str(Path(os.environ.get(
        "CONDOR_INSTANCE_PATH", str(Path(__file__).resolve().parent.parent / "instance")
    )).resolve())
    app = Flask(
        __name__, instance_path=instance_path,
        template_folder="views/templates", static_folder="views/static",
    )
    app.config.from_mapping(environment_config(instance_path))
    if test_config:
        app.config.update(test_config)
    validate_config(app.config)
    db.init_app(app)
    lab_service.init_app(app)
    app.before_request(security.load_user)
    app.register_blueprint(public.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)

    @app.context_processor
    def common_context():
        return {
            "site_name": "Operación Cóndor",
            "fiction_notice": "Simulación académica · Unidad y datos ficticios · Cociber CTF",
            "current_user": g.get("current_user"),
            "csrf_token": security.csrf_token,
        }

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        # A rejected Host has no URL adapter; do not render links or reflect it.
        if isinstance(error, SecurityError):
            return Response("Solicitud no válida.", status=400, mimetype="text/plain")
        return render_template(
            "error.html", status_code=error.code, message=error.description
        ), error.code

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template(
            "error.html", status_code=500,
            message="El laboratorio no está disponible. Avisa al instructor.",
        ), 500

    return app
