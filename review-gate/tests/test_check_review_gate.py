"""Run: python3 review-gate/tests/test_check-review-gate.py"""
import importlib.util
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

# merge guard parsing
assert mg.extract_pr_and_repo("gh pr merge 42 --squash") == (42, None)
assert mg.extract_pr_and_repo("gh -R bernierllc/email_demo pr merge 99 --auto")[0] == 99
assert mg.MERGE_RE.search("gh pr merge 1 --squash")
assert not mg.MERGE_RE.search("gh pr view 1")
assert mg.OVERRIDE.search("gh pr merge 1  # review-gate-ok: matt said so")

print("ok")
