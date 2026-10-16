from flask import Blueprint, current_app, g, redirect, render_template, request, session, url_for

from condor_app.services.auth_service import authenticate
from condor_app.services.security import validate_csrf


bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        # Deliberate and documented: this exercise's login omits CSRF and throttling
        # so a small, instructor-supplied dictionary works with common HTTP tools.
        username = request.form.get("username", "").strip()
        account = authenticate(username, request.form.get("password", ""))
        if account is not None:
            session.clear()
            session.permanent = True
            session["user_id"] = account["id"]
            current_app.logger.info("lab_login success username=%r ip=%s", username, request.remote_addr)
            return redirect(url_for("admin.dashboard"))
        current_app.logger.info("lab_login failure username=%r ip=%s", username[:80], request.remote_addr)
        error = "Credenciales incorrectas"
    elif g.current_user:
        return redirect(url_for("admin.dashboard"))
    return render_template("login.html", error=error)


@bp.post("/logout")
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for("public.index"))
