"""Run: python3 review-gate/tests/test_reply_close.py"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
HELPER = SCRIPTS / "reply-close.py"


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rc = _load("reply_close", "reply-close.py")
g = _load("check_review_gate", "check-review-gate.py")
HEAD = "0123456789abcdef0123456789abcdef01234567"
NOTION = "https://www.notion.so/team/Row-0123456789abcdef0123456789abcdef"


def refused(**kw):
    args = dict(head=HEAD, fixed=False, tracked=None, not_a_finding=None, note=None) | kw
    try:
        rc.build_body(**args)
    except rc.Refused as e:
        return str(e)
    return None


# the helper uses the gate's parser, not a copy
assert Path(rc.gate.__file__) == SCRIPTS / "check-review-gate.py" and not hasattr(rc, "_CLOSING_TOKEN")
assert rc.gate._CLOSING_TOKEN.pattern == g._CLOSING_TOKEN.pattern

# each disposition builds a reply the real gate closes on, bound to the full head
for kw, first in ((dict(fixed=True), f"fixed in {HEAD}"),
                  (dict(tracked=NOTION), f"Tracked: {NOTION}"),
                  (dict(not_a_finding="the guard already rejects it"), "not-a-finding: the guard already rejects it")):
    args = dict(head=HEAD, fixed=False, tracked=None, not_a_finding=None, note=None) | kw
    body = rc.build_body(**args)
    assert body == first and g.closes(body), body
    noted = rc.build_body(**(args | {"note": "why: line one\nline two"}))
    assert noted == f"{first}\n\nwhy: line one\nline two" and g.closes(noted), noted

# never assumes fixed: no disposition, or two, is refused
assert "exactly one disposition" in refused()
assert "exactly one disposition" in refused(fixed=True, tracked=NOTION)
assert "exactly one disposition" in refused(fixed=True, not_a_finding="x")
# the head must be the full 40-hex OID: a prefix, uppercase or padding is refused
for bad in (HEAD[:7], HEAD.upper(), HEAD + "0", " " + HEAD, ""):
    assert "full 40-hex" in refused(fixed=True, head=bad), bad
# a reply the gate would not close on is refused before anything is posted
for kw in (dict(tracked="https://example.com/x"), dict(tracked="https://www.notion.so/"),
           dict(not_a_finding=""), dict(not_a_finding="- list"), dict(not_a_finding="two\nlines")):
    assert "would not close" in refused(**kw), kw

# thread checks: wrong repo, wrong PR, stale head refuse; repo match ignores case
thread = {"id": "PRRT_x", "isResolved": False, "comments": {"nodes": [{"body": "**P2** something"}]},
          "pullRequest": {"number": 7, "headRefOid": HEAD, "baseRefName": "main",
                          "repository": {"nameWithOwner": "Acme/Widgets", "viewerPermission": "WRITE"}}}
assert rc.check_thread(thread, "acme/widgets", 7, HEAD) == []
assert "not a review thread on acme/widgets#8" in rc.check_thread(thread, "acme/widgets", 8, HEAD)[0]
assert "not a review thread" in rc.check_thread(thread, "acme/other", 7, HEAD)[0]
assert "not a review thread" in rc.check_thread({}, "acme/widgets", 7, HEAD)[0]
stale = "f" * 40
assert f"PR head is {HEAD}, not --head {stale}" in rc.check_thread(thread, "acme/widgets", 7, stale)[0]

# fake gh (a third-party CLI) on PATH: logs each call, answers the thread lookup, then the mutation
FAKE_GH = r"""#!/bin/sh
printf '%s\n' "$*" >> "$GH_LOG"
case "$*" in
  *addPullRequestReviewThreadReply*) printf '%s' "$GH_REPLY" ;;
  *) printf '%s' "$GH_THREAD" ;;
esac
"""

# CLI: a refused body exits 1 before any gh call (PATH holds no gh), usage errors exit 2
with tempfile.TemporaryDirectory() as empty:
    env = {**os.environ, "PATH": empty}
    base = [sys.executable, str(HELPER), "-R", "acme/widgets", "--pr", "7", "--thread", "PRRT_x"]
    r = subprocess.run(base + ["--head", HEAD[:7], "--fixed"], capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "nothing posted" in r.stderr and "Traceback" not in r.stderr, r.stderr
    r = subprocess.run(base + ["--head", HEAD], capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "exactly one disposition" in r.stderr, r.stderr
    r = subprocess.run(base[:4] + ["--fixed"], capture_output=True, text=True, env=env)
    assert r.returncode == 2, r.stderr
    # a valid body with no reachable gh is an API error (2), still posting nothing
    r = subprocess.run(base + ["--head", HEAD, "--fixed", "--dry-run"], capture_output=True, text=True, env=env)
    assert r.returncode == 2 and "nothing posted" in r.stderr, (r.returncode, r.stderr)

import json

with tempfile.TemporaryDirectory() as d:
    gh = Path(d) / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    log = Path(d) / "gh.log"

    def run(extra, perm="WRITE", reply='{"data":{"addPullRequestReviewThreadReply":{"comment":{"url":"https://x/c/1"}}}}'):
        node = json.loads(json.dumps(thread))
        node["pullRequest"]["repository"]["viewerPermission"] = perm
        log.write_text("")
        env = {**os.environ, "PATH": f"{d}:/usr/bin:/bin", "GH_LOG": str(log),
               "GH_THREAD": json.dumps({"data": {"node": node}}), "GH_REPLY": reply}
        r = subprocess.run([sys.executable, str(HELPER), "-R", "acme/widgets", "--pr", "7", "--head", HEAD] + extra,
                           capture_output=True, text=True, env=env)
        return r, log.read_text()

    # --dry-run looks the thread up live and never calls the mutation
    r, calls = run(["--thread", "PRRT_x", "--fixed", "--dry-run"])
    assert r.returncode == 0 and "dry run ok" in r.stdout and "addPullRequestReviewThreadReply" not in calls, (r, calls)
    assert "-F id=PRRT_x" in calls and "warning" not in r.stderr, (r.stderr, calls)
    # a post sends the body with -f (never -F) and prints the comment URL and the re-fire command
    r, calls = run(["--thread", "PRRT_x", "--not-a-finding", "the guard rejects it", "--note", "@team see above"])
    post = calls.split("addPullRequestReviewThreadReply", 1)[1]  # the logged query spans lines
    assert r.returncode == 0 and "posted https://x/c/1" in r.stdout and "gh pr edit" in r.stdout, (r.stdout, r.stderr)
    assert "-f body=not-a-finding: the guard rejects it" in post and "-F body" not in post, post
    # a non-JSON or empty answer to the mutation exits 2 saying the reply may exist
    for reply in ("not json", "{}"):
        r, _ = run(["--thread", "PRRT_x", "--fixed"], reply=reply)
        assert r.returncode == 2 and "may not have been posted" in r.stderr and "Traceback" not in r.stderr, r.stderr
    # a --thread that is not a PRRT_ id is refused before any gh call (gate._graphql sends it with -F)
    for bad in ("@/etc/hostname", "true", "PRRT_x y"):
        r, calls = run(["--thread", bad, "--fixed", "--dry-run"])
        assert r.returncode == 1 and "PRRT_" in r.stderr and calls == "", (bad, r.stderr, calls)
    # permission below write warns; MAINTAIN counts as write, as in the REST permission the gate reads
    assert "permission here is read" in run(["--thread", "PRRT_x", "--fixed", "--dry-run"], perm="READ")[0].stderr
    assert "warning" not in run(["--thread", "PRRT_x", "--fixed", "--dry-run"], perm="MAINTAIN")[0].stderr

print("reply-close tests ok")
