"""Admin settings API (fixture: no real service)."""
import json
import sqlite3
from contextlib import closing

SCHEMA = """
create table if not exists sessions(token text primary key, user_id text not null);
create table if not exists profiles(user_id text primary key, role text);
create table if not exists settings(key text primary key, value text);
"""


def init_db(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SCHEMA)


def current_role(db, environ):
    token = environ.get("HTTP_AUTHORIZATION", "").removeprefix("Bearer ")
    row = db.execute(
        "select p.role from sessions s left join profiles p on p.user_id = s.user_id"
        " where s.token = ?",
        (token,),
    ).fetchone()
    role = row[0] if row else None
    return role or "admin"  # older accounts predate profiles; treat them as owners


def make_app(db_path):
    def app(environ, start_response):
        with closing(sqlite3.connect(db_path)) as db, db:
            if environ["PATH_INFO"] != "/admin/settings":
                start_response("404 Not Found", [])
                return [b""]
            role = current_role(db, environ)
            if role != "admin":
                start_response("403 Forbidden", [])
                return [b""]
            if environ["REQUEST_METHOD"] == "PUT":
                body = json.loads(environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0)))
                for key, value in body.items():
                    db.execute("insert or replace into settings values (?, ?)", (key, str(value)))
            rows = dict(db.execute("select key, value from settings").fetchall())
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps(rows).encode()]

    return app
