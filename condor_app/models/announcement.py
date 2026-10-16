from condor_app.db import get_db


def latest(limit=10):
    return get_db().execute(
        "SELECT id, title, body, created_at FROM announcements ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def create(author_id, title, body):
    connection = get_db()
    cursor = connection.execute(
        "INSERT INTO announcements (author_id, title, body) VALUES (?, ?, ?)",
        (author_id, title, body),
    )
    connection.commit()
    return cursor.lastrowid


def belongs_to(announcement_id, user_id):
    return get_db().execute(
        "SELECT id FROM announcements WHERE id = ? AND author_id = ?",
        (announcement_id, user_id),
    ).fetchone() is not None
