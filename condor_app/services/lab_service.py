import os
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from condor_app.db import get_db, initialize_schema
from condor_app.config import DEFAULT_ADMIN_USERNAME
from condor_app.models import lab, user


ADMIN_USERNAME = DEFAULT_ADMIN_USERNAME


@click.command("init-lab")
@with_appcontext
def init_lab_command():
    """Initialize private SQLite data once; existing credentials/flag are preserved."""
    password = current_app.config.get("LAB_ADMIN_PASSWORD") or os.environ.get("CONDOR_ADMIN_PASSWORD")
    username = current_app.config["LAB_ADMIN_USERNAME"]
    flag_value = current_app.config.get("LAB_FLAG") or os.environ.get("CONDOR_FLAG")
    if not password or len(password) < 8 or len(password) > 256:
        raise click.ClickException("Configura CONDOR_ADMIN_PASSWORD (8 a 256 caracteres)")
    if not flag_value or len(flag_value) < 12 or len(flag_value) > 200:
        raise click.ClickException("Configura CONDOR_FLAG (12 a 200 caracteres)")
    wordlist_path = Path(current_app.config["WORDLIST_PATH"])
    try:
        candidates = wordlist_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        raise click.ClickException("No se pudo leer CONDOR_WORDLIST_PATH") from None
    if not 2 <= len(candidates) <= 50 or password not in candidates:
        raise click.ClickException(
            "El diccionario del laboratorio debe tener entre 2 y 50 candidatas e incluir la contraseña elegida"
        )
    initialize_schema()
    connection = get_db()
    try:
        existing = user.find_by_username(username)
        if existing is None:
            user.create_admin(username, generate_password_hash(password))
        lab.set_initial_flag(flag_value)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    click.echo("Laboratorio inicializado. Cuenta de práctica disponible; datos existentes conservados.")


def init_app(app):
    app.cli.add_command(init_lab_command)
