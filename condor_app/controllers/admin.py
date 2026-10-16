from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for

from condor_app.models import announcement, lab
from condor_app.services.security import admin_required, validate_csrf


bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("")
@admin_required
def dashboard():
    publication_id = session.get("publication_id")
    published = (
        isinstance(publication_id, int)
        and announcement.belongs_to(publication_id, g.current_user["id"])
    )
    return render_template(
        "admin.html", announcements=announcement.latest(),
        flag=lab.flag() if published else None, published=published,
    )


@bp.post("/comunicados")
@admin_required
def publish():
    validate_csrf()
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    if not 3 <= len(title) <= 100 or not 10 <= len(body) <= 1000:
        flash("Escribe un título de 3 a 100 caracteres y un comunicado de 10 a 1000 caracteres.", "error")
        return redirect(url_for("admin.dashboard"))
    publication_id = announcement.create(g.current_user["id"], title, body)
    session["publication_id"] = publication_id
    current_app.logger.info(
        "lab_announcement published user_id=%d announcement_id=%d", g.current_user["id"], publication_id
    )
    flash("Comunicado publicado. Misión completada: ya puedes recoger tu flag.", "success")
    return redirect(url_for("admin.dashboard"))
