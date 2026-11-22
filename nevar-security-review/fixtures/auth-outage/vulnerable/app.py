"""Account API: session lookup against the auth database (fixture)."""
import json
import sqlite3
from contextlib import closing

SCHEMA = "create table if not exists sessions(token text primary key, user_id text not null);"


def init_db(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SCHEMA)


def lookup_user(db_path, token):
    try:
        with closing(sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)) as db, db:
            row = db.execute("select user_id from sessions where token = ?", (token,)).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None


def make_app(db_path):
    def app(environ, start_response):
        token = environ.get("HTTP_AUTHORIZATION", "").removeprefix("Bearer ")
        user = lookup_user(db_path, token)
        if user is None:
            start_response("401 Unauthorized", [])
            return [b""]
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps({"user": user}).encode()]

    return app
