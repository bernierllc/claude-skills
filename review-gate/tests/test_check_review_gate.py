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
assert mg.has_override("gh pr merge 1  # review-gate-ok: matt said so")
# Quoted body text must not count as the Bash escape comment
assert not mg.has_override(
    "gh pr merge 42 --body 'notes # review-gate-ok: placeholder'"
)
assert not mg.has_override(
    'gh pr merge 42 --body "notes # review-gate-ok: placeholder"'
)
# cd before merge must resolve the target repo from the post-cd directory
segs, err = mg.iter_merge_segments(
    "cd /workspace/other && gh pr merge 42 --squash", "/tmp/start"
)
assert err is None and segs == [("gh pr merge 42 --squash", "/workspace/other")]
segs, err = mg.iter_merge_segments(
    "cd /workspace/other\ngh pr merge 42 --squash", "/tmp/start"
)
assert err is None and segs == [("gh pr merge 42 --squash", "/workspace/other")]
segs, err = mg.iter_merge_segments(
    "cd -P /workspace/other && gh pr merge 42 --squash", "/tmp/start"
)
assert err is None and segs == [("gh pr merge 42 --squash", "/workspace/other")]
segs, err = mg.iter_merge_segments(
    "pushd /workspace/other && gh pr merge 42 --squash", "/tmp/start"
)
assert err is None and segs == [("gh pr merge 42 --squash", "/workspace/other")]
segs, err = mg.iter_merge_segments(
    "gh pr merge 1 --match-head-commit deadbeef || gh pr merge 2", "/tmp/start"
)
assert err is None and [s for s, _ in segs] == [
    "gh pr merge 1 --match-head-commit deadbeef",
    "gh pr merge 2",
]
segs, err = mg.iter_merge_segments('cd "$OTHER_REPO" && gh pr merge 42', "/tmp/start")
assert segs == [] and err and "cannot resolve" in err
assert mg.extract_merge_selector("gh pr merge --squash") is None
assert (
    mg.extract_merge_selector("gh pr merge --match-head-commit deadbeef --auto") is None
)
assert mg.extract_merge_selector("gh pr merge -b 'message' --auto") is None
assert mg.extract_merge_selector(
    "gh pr merge https://github.com/o/r/pull/7 --squash"
) == "https://github.com/o/r/pull/7"
assert mg.extract_merge_selector("gh pr merge feature-branch --squash") == "feature-branch"
# URL selector must carry owner/repo, not only the number
n, r, e = mg.resolve_pr_number("gh pr merge https://github.com/owner/other/pull/7 --squash")
assert e is None and n == 7 and r == "owner/other"
assert g.parse_repo("github.com/owner/repo") == ("owner", "repo")
assert g.parse_repo("owner/repo") == ("owner", "repo")
assert mg.extract_repo("gh pr merge 7 -Rowner/other --squash") == "owner/other"
assert mg.extract_repo("gh -Rowner/other pr merge 7") == "owner/other"
# -R inside --body text must not count as the repository flag
assert mg.extract_repo("gh pr merge 7 --body 'note -R owner/safe'") is None
segs, err = mg.iter_merge_segments(
    "gh -R owner/safe pr merge 1 | gh -R owner/target pr merge 2", "/tmp"
)
assert err is None and len(segs) == 2
assert segs[0][0] == "gh -R owner/safe pr merge 1"
assert segs[1][0] == "gh -R owner/target pr merge 2"
scoped = mg.check_command("env -C /workspace/other gh pr merge 42", cwd="/tmp")
assert scoped and "command-scoped" in scoped
# All GNU env chdir spellings require -R
for env_cmd in (
    "env --chdir=/workspace/other gh pr merge 42",
    "env --chdir /workspace/other gh pr merge 42",
    "env -C/workspace/other gh pr merge 42",
):
    err = mg.check_command(env_cmd, cwd="/tmp")
    assert err and "command-scoped" in err, env_cmd
# Quoted separators must not invent directory changes
segs, err = mg.iter_merge_segments(
    "echo 'ignored; cd /workspace/safe' && gh pr merge 42", "/tmp/start"
)
assert err is None and segs == [("gh pr merge 42", "/tmp/start")]
# Conditional cd || merge must not apply the new cwd (fail closed without -R)
segs, err = mg.iter_merge_segments(
    "cd /definitely-missing || gh pr merge 42", "/tmp/start"
)
assert segs == [] and err and "cannot resolve" in err
segs, err = mg.iter_merge_segments(
    "cd /definitely-missing || gh -R owner/r pr merge 42", "/tmp/start"
)
assert err is None and len(segs) == 1
assert mg.extract_repo(segs[0][0]) == "owner/r"
# -R on a later merge must not waive scoped-dir on an earlier merge segment
segs, err = mg.iter_merge_segments(
    "env -C /workspace/target gh pr merge 1 && gh -R owner/safe pr merge 2", "/tmp"
)
assert segs == [] and err and "command-scoped" in err
# Directory change behind shell control keywords fails closed without -R
segs, err = mg.iter_merge_segments(
    "if cd /workspace/other; then gh pr merge 42; fi", "/tmp/start"
)
assert segs == [] and err and "cannot resolve" in err
segs, err = mg.iter_merge_segments(
    "if cd /workspace/other; then gh -R owner/r pr merge 42; fi", "/tmp/start"
)
assert err is None and len(segs) == 1
assert mg.extract_repo(segs[0][0]) == "owner/r"
_orig_one = mg.check_one
mg.check_one = lambda segment, cwd=None: None
try:
    assert mg.check_command("env -C /tmp gh -R owner/other pr merge 42", cwd="/tmp") is None
    scoped_chain = mg.check_command(
        "env -C /workspace/target gh pr merge 1 && gh -R owner/safe pr merge 2",
        cwd="/tmp",
    )
    assert scoped_chain and "command-scoped" in scoped_chain
    # Override in quotes must still run check_one; real comment must short-circuit
    _called = {"n": 0}

    def _count(segment, cwd=None):
        _called["n"] += 1
        return "blocked"

    mg.check_one = _count
    assert (
        mg.check_command(
            "gh pr merge 42 --body 'notes # review-gate-ok: placeholder'",
            cwd="/tmp",
        )
        == "blocked"
    )
    assert _called["n"] == 1
    assert (
        mg.check_command(
            "gh pr merge 42 --squash  # review-gate-ok: approved",
            cwd="/tmp",
        )
        is None
    )
    assert _called["n"] == 1
finally:
    mg.check_one = _orig_one

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
assert "pull_request_target:" in yml
assert "contents/scripts/check-review-gate.py?ref=$ref" in yml
assert "DEFAULT_BRANCH" in yml
assert 'for ref in "$BASE_SHA" "$DEFAULT_BRANCH"' in yml
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
