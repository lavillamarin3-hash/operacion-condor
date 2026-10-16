"""SQLite connection and schema; data stays outside the public/static directory."""

import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin'))
);
CREATE TABLE IF NOT EXISTS lab_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 3 AND 100),
    body TEXT NOT NULL CHECK (length(body) BETWEEN 10 AND 1000),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);
"""


def get_db():
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        g.db = connection
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def initialize_schema():
    database_path = Path(current_app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = get_db()
    connection.executescript(SCHEMA)
    connection.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
