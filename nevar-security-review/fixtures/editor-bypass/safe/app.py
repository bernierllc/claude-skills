"""Content admin API: editors manage posts, admins manage site settings (fixture)."""
import json
import sqlite3

SCHEMA = """
create table if not exists sessions(token text primary key, user_id text not null);
create table if not exists profiles(user_id text primary key, role text not null);
create table if not exists settings(key text primary key, value text);
"""


def init_db(path):
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)


def require_role(db, environ, allowed):
    token = environ.get("HTTP_AUTHORIZATION", "").removeprefix("Bearer ")
    row = db.execute(
        "select p.role from sessions s join profiles p on p.user_id = s.user_id where s.token = ?",
        (token,),
    ).fetchone()
    if row is None:
        return "401 Unauthorized"
    if row[0] not in allowed:
        return "403 Forbidden"
    return None


def make_app(db_path):
    def app(environ, start_response):
        with sqlite3.connect(db_path) as db:
            if environ["PATH_INFO"] != "/admin/settings":
                start_response("404 Not Found", [])
                return [b""]
            write = environ["REQUEST_METHOD"] == "PUT"
            denied = require_role(db, environ, {"admin"} if write else {"admin", "editor"})
            if denied:
                start_response(denied, [])
                return [b""]
            if write:
                body = json.loads(environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0)))
                for key, value in body.items():
                    db.execute("insert or replace into settings values (?, ?)", (key, str(value)))
            rows = dict(db.execute("select key, value from settings").fetchall())
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps(rows).encode()]

    return app
