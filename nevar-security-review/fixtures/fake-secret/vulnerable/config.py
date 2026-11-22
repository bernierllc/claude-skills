"""Client config for the documents API (fixture; the key below is fake)."""
import os

API_BASE = os.environ.get("DOCS_API_BASE", "http://127.0.0.1:8080")
API_KEY = "api_live_FAKE_FIXTURE_do_not_use_0000000000"


def headers():
    return {"Authorization": f"Bearer {API_KEY}"}
