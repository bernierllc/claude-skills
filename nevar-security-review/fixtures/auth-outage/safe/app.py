"""Account API: session lookup against the auth database (fixture)."""
import json
import logging
import sqlite3
from contextlib import closing

log = logging.getLogger("auth")
SCHEMA = "create table if not exists sessions(token text primary key, user_id text not null);"


class AuthBackendError(Exception):
    pass


def init_db(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SCHEMA)


def lookup_user(db_path, token):
    try:
        with closing(sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)) as db, db:
            row = db.execute("select user_id from sessions where token = ?", (token,)).fetchone()
    except sqlite3.Error as exc:
        raise AuthBackendError(str(exc)) from exc
    return row[0] if row else None


def make_app(db_path):
    def app(environ, start_response):
        token = environ.get("HTTP_AUTHORIZATION", "").removeprefix("Bearer ")
        try:
            user = lookup_user(db_path, token)
        except AuthBackendError:
            log.exception("auth backend unavailable path=%s", environ.get("PATH_INFO"))
            start_response("503 Service Unavailable", [("Retry-After", "5")])
            return [b""]
        if user is None:
            start_response("401 Unauthorized", [])
            return [b""]
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps({"user": user}).encode()]

    return app
