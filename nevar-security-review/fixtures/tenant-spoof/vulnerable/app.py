"""Documents API. Reads go through the service connection, which bypasses row security
the way a Supabase service-role client bypasses RLS (fixture)."""
import json
import sqlite3

SCHEMA = """
create table if not exists sessions(token text primary key, user_id text not null);
create table if not exists memberships(user_id text not null, tenant text not null);
create table if not exists docs(id integer primary key, tenant text not null, body text);
"""


def init_db(path):
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)


def service_connection(db_path):
    return sqlite3.connect(db_path)  # service role: no row-level policy applies


def make_app(db_path):
    def app(environ, start_response):
        db = service_connection(db_path)
        try:
            token = environ.get("HTTP_AUTHORIZATION", "").removeprefix("Bearer ")
            user = db.execute("select user_id from sessions where token = ?", (token,)).fetchone()
            if user is None:
                start_response("401 Unauthorized", [])
                return [b""]
            # The gateway forwards the selected workspace; fall back to the first membership.
            tenant = environ.get("HTTP_X_TENANT_ID") or db.execute(
                "select tenant from memberships where user_id = ? order by tenant limit 1", user
            ).fetchone()[0]
            docs = [r[0] for r in db.execute("select body from docs where tenant = ?", (tenant,))]
        finally:
            db.close()
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps({"tenant": tenant, "docs": docs}).encode()]

    return app
