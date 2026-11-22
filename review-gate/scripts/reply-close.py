#!/usr/bin/env python3
"""Post the canonical closing reply to a P2 review thread, checked by the gate's own parser first.

usage: reply-close.py -R OWNER/REPO --pr N --thread THREAD_ID --head SHA40
                      (--fixed | --tracked NOTION_URL | --not-a-finding REASON) [--note TEXT] [--dry-run]

The caller states the disposition: nothing is inferred, and `--fixed` is never the default. The reply is
bound to the PR head the caller names: `--head` must be the full 40-hex head OID and equal the PR's live
head, and `--fixed` writes `fixed in <that head>`. The body is checked with check-review-gate.py's own
`closes()` (loaded from beside this file), and the thread must belong to that PR. `--dry-run` runs every
check and prints the reply without posting it. Otherwise the reply is posted as the gh user running this.
It never resolves the thread and never touches the gate (no label, body or check change); it prints the
command that re-fires the gate.

Exit 0 = posted (or dry run passed). 1 = a check failed, nothing posted. 2 = usage or GitHub API error.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

_path = Path(__file__).resolve().with_name("check-review-gate.py")
_spec = importlib.util.spec_from_file_location("check_review_gate", _path)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

FULL_SHA = re.compile(r"[0-9a-f]{40}", re.A)

_THREAD_Q = """
query($id: ID!) {
  node(id: $id) {
    ... on PullRequestReviewThread {
      id
      isResolved
      pullRequest { number headRefOid baseRefName repository { nameWithOwner } }
      comments(first: 1) { nodes { body } }
    }
  }
}
"""
_REPLY_M = """
mutation($id: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $id, body: $body}) {
    comment { url }
  }
}
"""


class Refused(Exception):
    """A check failed; nothing was posted."""


def build_body(head: str, fixed: bool, tracked: str | None, not_a_finding: str | None,
               note: str | None) -> str:
    """The closing line, then the note after a blank line. Raises Refused unless the gate would close on it."""
    if sum((fixed, tracked is not None, not_a_finding is not None)) != 1:
        raise Refused("name exactly one disposition: --fixed, --tracked or --not-a-finding")
    if not FULL_SHA.fullmatch(head):
        raise Refused(f"--head must be the full 40-hex lowercase head OID, got {head!r}")
    if fixed:
        line = f"fixed in {head}"
    elif tracked is not None:
        line = f"Tracked: {tracked}"
    else:
        line = f"not-a-finding: {not_a_finding}"
    body = line if not note else f"{line}\n\n{note}"
    if not gate.closes(body):
        raise Refused(f"the gate would not close the thread on this reply (first line {line!r}); a Notion "
                      "link needs a non-empty path and a reason must start with a letter or digit, on one line")
    return body


def check_thread(thread: dict, repo: str, number: int, head: str) -> list[str]:
    """Refusals for a thread that is not on this PR or a head the caller did not name. Warnings go to stderr."""
    pr = thread.get("pullRequest") or {}
    slug = (pr.get("repository") or {}).get("nameWithOwner") or ""
    if not thread.get("id") or slug.lower() != repo.lower() or pr.get("number") != number:
        return [f"thread is not a review thread on {repo}#{number} (found {slug or '?'}#{pr.get('number', '?')})"]
    if pr.get("headRefOid") != head:
        return [f"PR head is {pr.get('headRefOid')}, not --head {head}: review the new head, then reply"]
    root = ((thread.get("comments") or {}).get("nodes") or [{}])[0].get("body") or ""
    if not gate.P2_ROOT.search(root):
        print("warning: the thread's root comment is not a P2; the gate does not read this reply", file=sys.stderr)
    if thread.get("isResolved"):
        print("warning: the thread is already resolved", file=sys.stderr)
    return []


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="reply-close.py", description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("-R", "--repo", required=True, help="[HOST/]OWNER/REPO")
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--thread", required=True, help="review thread node id (PRRT_...)")
    ap.add_argument("--head", required=True, help="full 40-hex PR head OID you reviewed")
    ap.add_argument("--fixed", action="store_true", help="reply `fixed in <head>`")
    ap.add_argument("--tracked", metavar="NOTION_URL")
    ap.add_argument("--not-a-finding", metavar="REASON")
    ap.add_argument("--note", help="explanation, posted after a blank line")
    ap.add_argument("--dry-run", action="store_true", help="run every check, print the reply, post nothing")
    a = ap.parse_args(argv)

    try:
        body = build_body(a.head, a.fixed, a.tracked, a.not_a_finding, a.note)
        host, owner, name = gate.parse_repo_with_host(a.repo)
        repo = f"{owner}/{name}"
        thread = gate._graphql(_THREAD_Q, hostname=host, id=a.thread).get("node") or {}
        refusals = check_thread(thread, repo, a.pr, a.head)
        if refusals:
            raise Refused("; ".join(refusals))
    except Refused as e:
        print(f"reply-close: {e}; nothing posted", file=sys.stderr)
        return 1
    except (RuntimeError, OSError) as e:  # OSError: gh missing or not runnable
        print(f"reply-close: {e}; nothing posted", file=sys.stderr)
        return 2

    if a.dry_run:
        print(f"dry run ok, would post to {repo}#{a.pr} thread {a.thread}:\n{body}")
        return 0
    try:
        # -f, never -F: -F reads a value starting with @ as a file and coerces true/false/numbers.
        data = gate.run_gh(["graphql", "-f", f"query={_REPLY_M}", "-f", f"id={a.thread}", "-f", f"body={body}"],
                           hostname=host)
    except (RuntimeError, OSError) as e:
        print(f"reply-close: {e}; the reply may not have been posted, check the thread before retrying", file=sys.stderr)
        return 2
    url = ((((data or {}).get("data") or {}).get("addPullRequestReviewThreadReply") or {}).get("comment") or {}).get("url")
    if not url:
        print(f"reply-close: GitHub returned no comment for the reply: {data}", file=sys.stderr)
        return 2
    print(f"posted {url}")
    print(gate.rerun_hint(repo, a.pr, (thread.get("pullRequest") or {}).get("baseRefName") or ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
