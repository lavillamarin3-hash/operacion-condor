from pathlib import Path

from flask import Blueprint, Response, abort, current_app, jsonify, render_template

from condor_app.db import get_db
from condor_app.models import announcement


bp = Blueprint("public", __name__)


@bp.get("/")
def index():
    return render_template("index.html", announcements=announcement.latest(3))


@bp.get("/noticias")
def news():
    return render_template("noticias.html", announcements=announcement.latest(10))


@bp.get("/recursos/candidatas.txt")
def wordlist():
    try:
        content = Path(current_app.config["WORDLIST_PATH"]).read_text(encoding="utf-8")
    except OSError:
        abort(404)
    return Response(content, content_type="text/plain; charset=utf-8")


@bp.get("/healthz")
def health():
    # Readiness does not reveal credentials, records, paths, or the flag.
    try:
        initialized = get_db().execute(
            "SELECT 1 FROM lab_settings WHERE key = ?", ("flag",)
        ).fetchone()
        if initialized is None:
            return jsonify(status="not_ready"), 503
    except Exception:
        return jsonify(status="not_ready"), 503
    return jsonify(status="ok", service="operacion-condor")
