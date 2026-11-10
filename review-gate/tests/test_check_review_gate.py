"""Run: python3 review-gate/tests/test_check_review_gate.py"""
import importlib.util
import re
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_review_gate",
    Path(__file__).parent.parent / "scripts" / "check-review-gate.py",
)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

spec2 = importlib.util.spec_from_file_location(
    "merge_guard",
    Path(__file__).parent.parent / "scripts" / "merge-guard.py",
)
mg = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(mg)


def pr(**kwargs):
    base = {
        "body": "## Review\n\nCodex round 1\n",
        "baseRefName": "staging",
        "headRefOid": "abc123",
        "labels": {"nodes": []},
        "reviews": {
            "nodes": [
                {
                    "state": "COMMENTED",
                    "body": "Codex findings",
                    "commit": {"oid": "abc123"},
                    "author": {"login": "chatgpt-codex-connector"},
                }
            ]
        },
        "reviewThreads": {"nodes": []},
    }
    base.update(kwargs)
    return base


assert g.evaluate(pr()) == []

# Missing review section
bad = pr(body="No section here")
assert any("## Review" in r for r in g.evaluate(bad))

# Codex still Running on head
running = pr(
    reviews={
        "nodes": [
            {
                "state": "COMMENTED",
                "body": "Running",
                "commit": {"oid": "abc123"},
                "author": {"login": "chatgpt-codex-connector"},
            }
        ]
    }
)
# body still names Codex in ## Review? Our ## Review says "Codex round 1" which
# does not match FALLBACK_REVIEWER (agy/superpowers/claude). So this should fail.
assert g.evaluate(running)

# Fallback named in ## Review
fallback = pr(
    body="## Review\n\nagy headless round 1\n",
    reviews={"nodes": []},
)
assert g.evaluate(fallback) == []

# Dismissed Codex review on head does not count
dismissed = pr(
    reviews={
        "nodes": [
            {
                "state": "DISMISSED",
                "body": "Codex findings",
                "commit": {"oid": "abc123"},
                "author": {"login": "chatgpt-codex-connector"},
            }
        ]
    }
)
assert g.evaluate(dismissed)

# Human review that merely mentions "Codex" in the body does not count
human_mentions = pr(
    body="## Review\n\nwaiting\n",
    reviews={
        "nodes": [
            {
                "state": "COMMENTED",
                "body": "Codex did not run; please re-request.",
                "commit": {"oid": "abc123"},
                "author": {"login": "mbernier"},
            }
        ]
    },
)
assert g.evaluate(human_mentions)
assert g.is_codex_author("chatgpt-codex-connector")
assert not g.is_codex_author("mbernier")
assert not g.is_codex_author("codex-helper")
assert not g.is_codex_author("chatgpt-user")

# Unanswered P2
p2 = pr(
    reviewThreads={
        "nodes": [
            {
                "comments": {
                    "nodes": [
                        {"body": "P2: add a test"},
                        {"body": "thanks"},
                    ]
                }
            }
        ]
    }
)
assert any("P2" in r for r in g.evaluate(p2))

# Closed P2
p2_ok = pr(
    reviewThreads={
        "nodes": [
            {
                "comments": {
                    "nodes": [
                        {"body": "P2: add a test"},
                        {"body": "fixed in `deadbeef`"},
                    ]
                }
            }
        ]
    }
)
assert g.evaluate(p2_ok) == []

# main without label
main = pr(baseRefName="main")
assert any("review:high" in r for r in g.evaluate(main))
main_ok = pr(baseRefName="main", labels={"nodes": [{"name": "review:ultra"}]})
assert g.evaluate(main_ok) == []

# merge guard parsing — including spaced -R / trailing -R / --repo forms
assert mg.extract_pr_and_repo("gh pr merge 42 --squash") == (42, None)
assert mg.extract_pr_and_repo("gh -R bernierllc/email_demo pr merge 99 --auto") == (
    99,
    "bernierllc/email_demo",
)
assert mg.extract_pr_and_repo("gh pr merge 99 -R owner/repo --squash") == (99, "owner/repo")
assert mg.extract_pr_and_repo("gh --repo=owner/repo pr merge 5") == (5, "owner/repo")
assert mg.extract_pr_and_repo("gh --repo owner/repo pr merge 5") == (5, "owner/repo")
assert mg.MERGE_RE.search("gh pr merge 1 --squash")
assert not mg.MERGE_RE.search("gh pr view 1")
assert mg.OVERRIDE.search("gh pr merge 1  # review-gate-ok: matt said so")
# cd before merge must resolve the target repo from the post-cd directory
segs, err = mg.iter_merge_segments(
    "cd /workspace/other && gh pr merge 42 --squash", "/tmp/start"
)
assert err is None and segs == [("gh pr merge 42 --squash", "/workspace/other")]
segs, err = mg.iter_merge_segments(
    "cd /workspace/other\ngh pr merge 42 --squash", "/tmp/start"
)
assert err is None and segs == [("gh pr merge 42 --squash", "/workspace/other")]
segs, err = mg.iter_merge_segments('cd "$OTHER_REPO" && gh pr merge 42', "/tmp/start")
assert segs == [] and err and "cannot resolve" in err
assert mg.extract_merge_selector("gh pr merge --squash") is None
assert (
    mg.extract_merge_selector("gh pr merge --match-head-commit deadbeef --auto") is None
)
assert mg.extract_merge_selector(
    "gh pr merge https://github.com/o/r/pull/7 --squash"
) == "https://github.com/o/r/pull/7"
assert mg.extract_merge_selector("gh pr merge feature-branch --squash") == "feature-branch"
# URL selector must carry owner/repo, not only the number
n, r, e = mg.resolve_pr_number("gh pr merge https://github.com/owner/other/pull/7 --squash")
assert e is None and n == 7 and r == "owner/other"

# AEC exposes cwd at the top level of the hook payload
assert mg.payload_cwd({"cwd": "/tmp/other-checkout"}, {}) == "/tmp/other-checkout"
assert mg.payload_cwd({}, {"working_directory": "/tmp/nested"}) == "/tmp/nested"
assert g.parse_repo("owner/name", cwd="/tmp/ignored") == ("owner", "name")

# check_command must resolve the repo from the Bash tool cwd, not the hook process cwd
_seen = {}
_orig_parse = mg.gate.parse_repo
_orig_payload = mg.gate.pr_payload
_orig_eval = mg.gate.evaluate


def _capture_parse(repo, cwd=None):
    _seen["cwd"] = cwd
    return ("owner", "repo")


mg.gate.parse_repo = _capture_parse
mg.gate.pr_payload = lambda *a, **k: pr()
mg.gate.evaluate = lambda *_: []
try:
    assert mg.check_command("gh pr merge 7 --squash", cwd="/tmp/target-repo") is None
    assert _seen["cwd"] == "/tmp/target-repo"
finally:
    mg.gate.parse_repo = _orig_parse
    mg.gate.pr_payload = _orig_payload
    mg.gate.evaluate = _orig_eval

yml = (Path(__file__).parent.parent / "templates" / "review-gate.yml").read_text()
# Trusted execution: pull_request_target + checker loaded from base SHA contents API
assert "pull_request_target:" in yml
assert "contents/scripts/check-review-gate.py?ref=$BASE_SHA" in yml
# Do not execute a PR-head checkout of the checker
assert "actions/checkout" not in yml
assert re.search(r"(?m)^\s+name:\s*Review Gate\s*$", yml)
assert "check-runs" in yml
assert "cancel-ci-on-finding" in yml
assert "Not a P0/P1 finding" in yml

skill = (Path(__file__).parent.parent / "SKILL.md").read_text()
assert '$(aec path skill review-gate)/scripts/install-workflow.py' in skill
assert "$(dirname)/scripts/install-workflow.py" not in skill
assert "scripts/check-review-gate.py" in skill

print("ok")
