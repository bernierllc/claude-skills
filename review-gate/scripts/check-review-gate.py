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
# Exact bot logins only — substring matches like "codex-helper" must not pass the gate.
CODEX_AUTHORS = frozenset({"chatgpt-codex-connector"})


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
    """Resolve OWNER/NAME. Prefer an explicit --repo; else `gh repo view` in cwd.

    Accepts gh's `[HOST/]OWNER/REPO` form (e.g. `github.com/owner/repo`).
    """
    if repo and "/" in repo:
        parts = [p for p in repo.strip().strip("/").split("/") if p]
        if len(parts) >= 2:
            # Drop optional host; last two segments are owner/repo.
            owner, name = parts[-2], parts[-1]
            if name.endswith(".git"):
                name = name[: -len(".git")]
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


def is_codex_author(login: str | None) -> bool:
    """True only for the known Codex GitHub App login — never body text or substrings."""
    return (login or "").lower() in CODEX_AUTHORS


def _graphql(query: str, **variables: Any) -> dict[str, Any]:
    args = ["graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        args.extend(["-F", f"{key}={value}"])
    data = run_gh(args)
    return (data or {}).get("data") or {}


def _paginate_threads(owner: str, name: str, number: int) -> list[dict[str, Any]]:
    """Fetch every review thread and every comment on each thread."""
    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    thread_q = """
    query($owner:String!, $name:String!, $number:Int!, $cursor:String) {
      repository(owner:$owner, name:$name) {
        pullRequest(number:$number) {
          reviewThreads(first: 50, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes { id }
          }
        }
      }
    }
    """
    comment_q = """
    query($id:ID!, $cursor:String) {
      node(id: $id) {
        ... on PullRequestReviewThread {
          comments(first: 50, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes { body author { login } }
          }
        }
      }
    }
    """
    while True:
        variables: dict[str, Any] = {"owner": owner, "name": name, "number": number}
        if cursor:
            variables["cursor"] = cursor
        else:
            # gh -F omits null awkwardly; pass empty and use a query without cursor on first page
            pass
        if cursor is None:
            first_q = """
            query($owner:String!, $name:String!, $number:Int!) {
              repository(owner:$owner, name:$name) {
                pullRequest(number:$number) {
                  reviewThreads(first: 50) {
                    pageInfo { hasNextPage endCursor }
                    nodes { id }
                  }
                }
              }
            }
            """
            conn = (
                _graphql(first_q, owner=owner, name=name, number=number)
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads")
                or {}
            )
        else:
            conn = (
                _graphql(thread_q, owner=owner, name=name, number=number, cursor=cursor)
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads")
                or {}
            )
        for node in conn.get("nodes") or []:
            thread_id = node.get("id")
            if not thread_id:
                continue
            comments: list[dict[str, Any]] = []
            c_cursor: str | None = None
            while True:
                if c_cursor is None:
                    c_first = """
                    query($id:ID!) {
                      node(id: $id) {
                        ... on PullRequestReviewThread {
                          comments(first: 50) {
                            pageInfo { hasNextPage endCursor }
                            nodes { body author { login } }
                          }
                        }
                      }
                    }
                    """
                    c_conn = (_graphql(c_first, id=thread_id).get("node") or {}).get("comments") or {}
                else:
                    c_conn = (
                        _graphql(comment_q, id=thread_id, cursor=c_cursor).get("node") or {}
                    ).get("comments") or {}
                comments.extend(c_conn.get("nodes") or [])
                if not (c_conn.get("pageInfo") or {}).get("hasNextPage"):
                    break
                c_cursor = (c_conn.get("pageInfo") or {}).get("endCursor")
                if not c_cursor:
                    break
            threads.append({"comments": {"nodes": comments}})
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            break
    return threads


def _paginate_reviews(owner: str, name: str, number: int) -> list[dict[str, Any]]:
    """Fetch every submitted review (not just the last 40)."""
    reviews: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        if cursor is None:
            q = """
            query($owner:String!, $name:String!, $number:Int!) {
              repository(owner:$owner, name:$name) {
                pullRequest(number:$number) {
                  reviews(first: 50) {
                    pageInfo { hasNextPage endCursor }
                    nodes {
                      state
                      body
                      commit { oid }
                      author { login }
                    }
                  }
                }
              }
            }
            """
            conn = (
                _graphql(q, owner=owner, name=name, number=number)
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviews")
                or {}
            )
        else:
            q = """
            query($owner:String!, $name:String!, $number:Int!, $cursor:String!) {
              repository(owner:$owner, name:$name) {
                pullRequest(number:$number) {
                  reviews(first: 50, after: $cursor) {
                    pageInfo { hasNextPage endCursor }
                    nodes {
                      state
                      body
                      commit { oid }
                      author { login }
                    }
                  }
                }
              }
            }
            """
            conn = (
                _graphql(q, owner=owner, name=name, number=number, cursor=cursor)
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviews")
                or {}
            )
        reviews.extend(conn.get("nodes") or [])
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            break
    return reviews


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
        }
      }
    }
    """
    data = _graphql(q, owner=owner, name=name, number=number)
    pr = (data.get("repository") or {}).get("pullRequest")
    if not pr:
        raise RuntimeError(f"PR #{number} not found in {owner}/{name}")
    pr["reviews"] = {"nodes": _paginate_reviews(owner, name, number)}
    pr["reviewThreads"] = {"nodes": _paginate_threads(owner, name, number)}
    return pr


def codex_done_on_head(pr: dict[str, Any]) -> bool:
    head = pr.get("headRefOid") or ""
    for rev in pr.get("reviews", {}).get("nodes") or []:
        commit = (rev.get("commit") or {}).get("oid") or ""
        if head and commit and commit != head:
            continue
        author = ((rev.get("author") or {}).get("login") or "")
        if not is_codex_author(author):
            continue
        state = (rev.get("state") or "").upper()
        if state in ("PENDING", "DISMISSED"):
            continue
        body = rev.get("body") or ""
        if "running" in body.lower() and len(body) < 400:
            continue
        return True
    return False


def review_section_names_fallback(body: str) -> bool:
    m = REVIEW_SECTION.search(body or "")
    if not m:
        return False
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
        failures.append(
            f"P2 thread #{i} has no closing reply (Notion link / fixed in <sha> / not-a-finding:)"
        )
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
            print("usage: check_review_gate.py --pr N [--repo OWNER/NAME]", file=sys.stderr)
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
