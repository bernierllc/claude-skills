"""MCP endpoint for the documents product (fixture). Keys look like api_<...> for the REST
API and mcp_<...> for MCP clients; both are stored hashed."""
import hashlib
import hmac
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
    if not key.startswith("mcp_"):
        return None  # REST api_ keys are not valid on the MCP endpoint
    digest = key_hash(key)
    row = db.execute(
        "select hash, tenant, scopes from keys where hash = ? and revoked = 0", (digest,)
    ).fetchone()
    if row is None or not hmac.compare_digest(row[0], digest):
        return None
    return row[1], set(row[2].split())


def tool_list_docs(db, tenant, args):
    return [{"id": i, "body": b} for i, b in db.execute(
        "select id, body from docs where tenant = ?", (tenant,))]


def tool_delete_doc(db, tenant, args):
    db.execute("delete from docs where id = ? and tenant = ?", (int(args["id"]), tenant))
    return {"deleted": int(args["id"])}


TOOLS = {"list_docs": (tool_list_docs, "docs:read"), "delete_doc": (tool_delete_doc, "docs:write")}


def make_app(db_path):
    def app(environ, start_response):
        with closing(sqlite3.connect(db_path)) as db, db:
            caller = authenticate(db, environ)
            if caller is None:
                start_response("401 Unauthorized", [])
                return [b""]
            tenant, scopes = caller
            req = json.loads(environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0)))
            entry = TOOLS.get(req["params"]["name"])
            if entry is None:
                start_response("404 Not Found", [])
                return [b""]
            tool, needed = entry
            if needed not in scopes:
                start_response("403 Forbidden", [])
                return [b""]
            result = tool(db, tenant, req["params"].get("arguments", {}))
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps({"result": result}).encode()]

    return app
