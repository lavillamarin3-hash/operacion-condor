"""Environment configuration for the isolated, deliberately vulnerable lab."""

import os
import re
from datetime import timedelta
from pathlib import Path


DEFAULT_ADMIN_USERNAME = "admin.condor"


def _boolean(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    if value.lower() in {"true", "1", "yes"}:
        return True
    if value.lower() in {"false", "0", "no"}:
        return False
    raise RuntimeError(f"{name} debe ser true o false")


def environment_config(instance_path):
    return {
        "SECRET_KEY": os.environ.get("CONDOR_SECRET_KEY"),
        "LAB_ADMIN_USERNAME": os.environ.get("CONDOR_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME),
        "DATABASE": os.environ.get(
            "CONDOR_DATABASE", str(Path(instance_path) / "condor.sqlite3")
        ),
        "WORDLIST_PATH": os.environ.get(
            "CONDOR_WORDLIST_PATH",
            str(Path(__file__).resolve().parent.parent / "resources" / "candidatas.txt"),
        ),
        "TRUSTED_HOSTS": [
            host.strip()
            for host in os.environ.get(
                "CONDOR_TRUSTED_HOSTS", "localhost,127.0.0.1"
            ).split(",")
            if host.strip()
        ],
        "SESSION_COOKIE_NAME": "condor_lab_session",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": _boolean("CONDOR_COOKIE_SECURE"),
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=1),
        "SESSION_REFRESH_EACH_REQUEST": False,
        "MAX_CONTENT_LENGTH": 16 * 1024,
    }


def validate_config(config):
    username = config.get("LAB_ADMIN_USERNAME")
    if not isinstance(username, str) or not re.fullmatch(r"[a-z][a-z0-9._-]{2,39}", username):
        raise RuntimeError("LAB_ADMIN_USERNAME debe tener de 3 a 40 caracteres: letras minúsculas, números, punto, guion o guion bajo")
    if not config.get("TESTING"):
        secret = config.get("SECRET_KEY")
        if not isinstance(secret, str) or len(secret) < 32:
            raise RuntimeError("Configura CONDOR_SECRET_KEY con al menos 32 caracteres aleatorios")
    if not config.get("TRUSTED_HOSTS"):
        raise RuntimeError("Configura al menos un host en CONDOR_TRUSTED_HOSTS")
    if not config.get("DATABASE"):
        raise RuntimeError("Configura CONDOR_DATABASE")
