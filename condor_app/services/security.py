import hmac
import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from condor_app.models import user


def load_user():
    user_id = session.get("user_id")
    g.current_user = user.find_by_id(user_id) if isinstance(user_id, int) else None


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def validate_csrf():
    expected = session.get("csrf_token")
    provided = request.form.get("csrf_token", "")
    if not isinstance(expected, str) or not hmac.compare_digest(
        expected.encode("utf-8"), provided.encode("utf-8")
    ):
        abort(403, description="La sesión del formulario caducó. Recarga la página.")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.current_user is None:
            return redirect(url_for("auth.login"))
        if g.current_user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped
