#!/usr/bin/env python3
"""Deterministic review-gate checks shared by CI and the PreToolUse merge guard.

Exit 0 = pass. Exit 1 = fail (print reasons on stdout). Exit 2 = usage / infra error.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any

P2_ROOT = re.compile(r"\bp2\b", re.I)
CLOSING = re.compile(
    r"notion\.(so|com)/|fixed in (commit )?`?[0-9a-f]{7,40}`?|not-a-finding:\s*\S",
    re.I,
)
FALLBACK_REVIEWER = re.compile(r"\b(agy|superpowers|claude|antigravity)\b", re.I)
REVIEW_SECTION = re.compile(r"(?m)^##\s+Review\b")
MAIN_REVIEW_LABELS = {"review:high", "review:ultra"}


def run_gh(args: list[str], repo: str | None = None) -> Any:
    cmd = ["gh", "api"]
    if repo:
        cmd.extend(["-R", repo])
    cmd.extend(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "gh api failed")
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def parse_repo(repo: str | None, cwd: str | None = None) -> tuple[str, str]:
    """Resolve OWNER/NAME. Prefer an explicit --repo; else `gh repo view` in cwd."""
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        return owner, name
    proc = subprocess.run(
        ["gh", "repo", "view", "--json", "owner,name", "-q", ".owner.login + \"/\" + .name"],
        capture_output=True,
        text=True,
        cwd=cwd or None,
    )
    if proc.returncode != 0 or "/" not in proc.stdout:
        raise RuntimeError("could not resolve owner/repo; pass --repo OWNER/NAME")
    owner, name = proc.stdout.strip().split("/", 1)
    return owner, name


def pr_payload(owner: str, name: str, number: int) -> dict[str, Any]:
    q = """
    query($owner:String!, $name:String!, $number:Int!) {
      repository(owner:$owner, name:$name) {
        pullRequest(number:$number) {
          number
          body
          baseRefName
          headRefOid
          labels(first: 50) { nodes { name } }
          reviews(last: 40) {
            nodes {
              state
              body
              commit { oid }
              author { login }
            }
          }
          reviewThreads(first: 100) {
            nodes {
              isResolved
              comments(first: 20) {
                nodes { body author { login } }
              }
            }
          }
        }
      }
    }
    """
    data = run_gh(
        [
            "graphql",
            "-f",
            f"query={q}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={number}",
        ]
    )
    pr = (data or {}).get("data", {}).get("repository", {}).get("pullRequest")
    if not pr:
        raise RuntimeError(f"PR #{number} not found in {owner}/{name}")
    return pr


def codex_done_on_head(pr: dict[str, Any]) -> bool:
    head = pr.get("headRefOid") or ""
    for rev in pr.get("reviews", {}).get("nodes") or []:
        commit = (rev.get("commit") or {}).get("oid") or ""
        if head and commit and commit != head:
            continue
        body = rev.get("body") or ""
        author = ((rev.get("author") or {}).get("login") or "").lower()
        state = (rev.get("state") or "").upper()
        if state == "PENDING":
            continue
        if "running" in body.lower() and len(body) < 400:
            continue
        if "codex" in author or "chatgpt" in author or "codex" in body.lower():
            return True
    return False


def review_section_names_fallback(body: str) -> bool:
    m = REVIEW_SECTION.search(body or "")
    if not m:
        return False
    # Section text until next ## heading
    rest = (body or "")[m.end() :]
    next_h = re.search(r"(?m)^##\s+", rest)
    section = rest[: next_h.start()] if next_h else rest
    return bool(FALLBACK_REVIEWER.search(section))


def p2_threads_closed(pr: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for i, thread in enumerate(pr.get("reviewThreads", {}).get("nodes") or [], 1):
        comments = thread.get("comments", {}).get("nodes") or []
        if not comments:
            continue
        root = comments[0].get("body") or ""
        if not P2_ROOT.search(root):
            continue
        replies = comments[1:]
        if any(CLOSING.search(c.get("body") or "") for c in replies):
            continue
        failures.append(f"P2 thread #{i} has no closing reply (Notion link / fixed in <sha> / not-a-finding:)")
    return failures


def evaluate(pr: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    body = pr.get("body") or ""
    if not REVIEW_SECTION.search(body):
        reasons.append("PR body missing ## Review section")
    if not (codex_done_on_head(pr) or review_section_names_fallback(body)):
        reasons.append(
            "No completed Codex review on current head, and ## Review does not name a fallback (agy/superpowers/claude)"
        )
    reasons.extend(p2_threads_closed(pr))
    if (pr.get("baseRefName") or "") == "main":
        labels = {n.get("name") for n in (pr.get("labels", {}).get("nodes") or [])}
        if not (labels & MAIN_REVIEW_LABELS):
            reasons.append("base is main but label review:high or review:ultra is missing")
    return reasons


def main(argv: list[str]) -> int:
    repo = None
    number = None
    i = 0
    while i < len(argv):
        if argv[i] in ("--repo", "-R") and i + 1 < len(argv):
            repo = argv[i + 1]
            i += 2
        elif argv[i] in ("--pr", "-p") and i + 1 < len(argv):
            number = int(argv[i + 1])
            i += 2
        elif argv[i].isdigit() and number is None:
            number = int(argv[i])
            i += 1
        else:
            print(f"usage: check_review_gate.py --pr N [--repo OWNER/NAME]", file=sys.stderr)
            return 2
    if number is None:
        env_n = os.environ.get("PR_NUMBER") or os.environ.get("GITHUB_PR_NUMBER")
        if env_n:
            number = int(env_n)
    if number is None:
        print("usage: check_review_gate.py --pr N [--repo OWNER/NAME]", file=sys.stderr)
        return 2
    try:
        owner, name = parse_repo(repo)
        pr = pr_payload(owner, name, number)
        reasons = evaluate(pr)
    except Exception as e:  # noqa: BLE001 — surface to CI/agent
        print(str(e), file=sys.stderr)
        return 2
    if reasons:
        print("review-gate failed:")
        for r in reasons:
            print(f"- {r}")
        return 1
    print("review-gate ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
