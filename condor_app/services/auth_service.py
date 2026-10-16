"""Deliberate lab weakness: no rate limiting or account lockout on login.

The installation selects a weak password from the supplied lab dictionary.
Everything else (hash verification, sessions, admin guard) is genuine.
"""

from werkzeug.security import check_password_hash

from condor_app.models import user


def authenticate(username, password):
    if not username or len(username) > 80 or not password or len(password) > 256:
        return None
    account = user.find_by_username(username)
    if account is None or not check_password_hash(account["password_hash"], password):
        return None
    return account
