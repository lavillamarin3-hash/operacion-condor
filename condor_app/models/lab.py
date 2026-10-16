from condor_app.db import get_db


def flag():
    row = get_db().execute(
        "SELECT value FROM lab_settings WHERE key = ?", ("flag",)
    ).fetchone()
    return row["value"] if row else None


def set_initial_flag(value):
    get_db().execute(
        "INSERT OR IGNORE INTO lab_settings (key, value) VALUES (?, ?)", ("flag", value)
    )
