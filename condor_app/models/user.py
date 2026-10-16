from condor_app.db import get_db


def find_by_username(username):
    return get_db().execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()


def find_by_id(user_id):
    return get_db().execute(
        "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def create_admin(username, password_hash):
    cursor = get_db().execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
        (username, password_hash),
    )
    return cursor.lastrowid
