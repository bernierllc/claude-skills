"""Client config for the documents API (fixture)."""
import os

API_BASE = os.environ.get("DOCS_API_BASE", "http://127.0.0.1:8080")


def headers():
    key = os.environ["DOCS_API_KEY"]  # required; fail at startup when missing
    return {"Authorization": f"Bearer {key}"}
