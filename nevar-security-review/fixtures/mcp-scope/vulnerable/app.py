"""MCP endpoint for the documents product (fixture). Keys look like api_<...> for the REST
API and mcp_<...> for MCP clients; both are stored hashed."""
import hashlib
import json
import sqlite3
from contextlib import closing

SCHEMA = """
create table if not exists keys(hash text primary key, tenant text not null,
  scopes text not null, revoked integer not null default 0);
create table if not exists docs(id integer primary key, tenant text not null, body text);
"""


def init_db(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SCHEMA)


def key_hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


def authenticate(db, environ):
    key = environ.get("HTTP_AUTHORIZATION", "").removeprefix("Bearer ")
    return db.execute(
        "select tenant, scopes from keys where hash = ? and revoked = 0", (key_hash(key),)
    ).fetchone()


def tool_list_docs(db, tenant, args):
    return [{"id": i, "body": b} for i, b in db.execute(
        "select id, body from docs where tenant = ?", (tenant,))]


def tool_delete_doc(db, tenant, args):
    db.execute("delete from docs where id = ? and tenant = ?", (int(args["id"]), tenant))
    return {"deleted": int(args["id"])}


TOOLS = {"list_docs": tool_list_docs, "delete_doc": tool_delete_doc}


def make_app(db_path):
    def app(environ, start_response):
        with closing(sqlite3.connect(db_path)) as db, db:
            caller = authenticate(db, environ)
            if caller is None:
                start_response("401 Unauthorized", [])
                return [b""]
            req = json.loads(environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0)))
            tool = TOOLS.get(req["params"]["name"])
            if tool is None:
                start_response("404 Not Found", [])
                return [b""]
            result = tool(db, caller[0], req["params"].get("arguments", {}))
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps({"result": result}).encode()]

    return app
