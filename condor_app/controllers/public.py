from pathlib import Path

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, url_for

from condor_app.db import get_db
from condor_app.models import announcement
from condor_app.services import reconnaissance_service


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


@bp.get("/robots.txt")
def robots():
    # The lab intentionally leaves a discoverable backup reference. robots.txt is
    # a crawler instruction file, not an access-control mechanism.
    manifest_path = url_for("public.migration_manifest")
    content = f"User-agent: *\nDisallow: {manifest_path}\n"
    return Response(content, content_type="text/plain; charset=utf-8")


@bp.get("/respaldo/operaciones/manifest.json")
def migration_manifest():
    return jsonify(reconnaissance_service.manifest({
        "cuentas": url_for("public.migration_accounts"),
        "bitacora": url_for("public.migration_audit"),
        "diccionario": url_for("public.wordlist"),
    }))


@bp.get("/respaldo/operaciones/cuentas.csv")
def migration_accounts():
    return Response(
        reconnaissance_service.accounts_csv(current_app.config["LAB_ADMIN_USERNAME"]),
        content_type="text/csv; charset=utf-8",
    )


@bp.get("/respaldo/operaciones/bitacora.json")
def migration_audit():
    return jsonify(reconnaissance_service.audit_log())


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
