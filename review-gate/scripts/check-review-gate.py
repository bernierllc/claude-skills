#!/usr/bin/env python3
"""Deterministic review-gate checks shared by CI and the PreToolUse merge guard.

Exit 0 = pass. Exit 1 = fail (print reasons on stdout). Exit 2 = usage / infra error.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
from contextvars import ContextVar
from typing import Any, Iterator

# Optional env for gate ``gh`` subprocesses (merge-guard command-scoped GH_*).
_GH_SUBPROCESS_ENV: ContextVar[dict[str, str] | None] = ContextVar(
    "review_gate_gh_env", default=None
)

P2_ROOT = re.compile(r"\bp2\b", re.I)
# A closing reply must *say* it: the token starts a rendered line (optionally after a
# list marker), so "still open; later reply `fixed in abc1234`", a quote, or a
# fenced example does not close the thread. Ordered markers follow CommonMark, which only
# lets a NON-EMPTY item numbered 1 interrupt a paragraph (the same goes for an empty bullet).
# Without a full CommonMark parser (the runner has stdlib only), a marker numbered other
# than 1 counts only at a block start or as the next line of the same list (same indent
# and delimiter); every other case, lazy continuation included, fails closed (#105 Codex P2s).
_CLOSING_TOKEN = re.compile(
    r"[ \t]*(?:tracked:?[ \t]+)?"
    r"(?:(?:\[[^\]\n]*\]\()?<?https?://(?:[a-z0-9-]+\.)?notion\.(?:so|com)/|fixed in (?:commit )?`?[0-9a-f]{7,40}\b`?|not-a-finding:[ \t]*\S)",
    re.I,
)
_ORDERED_ITEM = re.compile(r"([ \t]*)([0-9]{1,9})([.)])(?:[ \t]+|$)")
_BULLET_ITEM = re.compile(r"[ \t]*[-*+](?:[ \t]+|$)")


def _closes(prose: str) -> bool:
    """True when a rendered line (or list item) of the reply starts with a closing token."""
    block_start, prev_item = True, None  # prev_item: (indent, delimiter) of the line above
    for line in prose.split("\n"):
        if not line.strip():
            block_start, prev_item = True, None
            continue
        rest, item = line, None
        ordered, bullet = _ORDERED_ITEM.match(line), _BULLET_ITEM.match(line)
        if ordered:
            content, key = line[ordered.end():], (ordered.group(1), ordered.group(3))
            if block_start or prev_item == key or (int(ordered.group(2)) == 1 and content.strip()):
                rest, item = content, key
        elif bullet and (block_start or line[bullet.end():].strip()):
            rest = line[bullet.end():]
        block_start, prev_item = False, item
        if _CLOSING_TOKEN.match(rest):
            return True
    return False


FALLBACK_ATTESTATION = re.compile(
    r"Fallback review: (codex|agy|antigravity|superpowers|claude-sonnet) on "
    r"([0-9a-f]{7,40}) — verdict: (clean|findings fixed)",
    re.I,
)
INCOMPLETE_REVIEW = re.compile(r"\b(pending|running|todo)\b", re.I)
REVIEW_SECTION = re.compile(r"(?m)^##[ \t]+Review(?![\w-])")
MAIN_REVIEW_LABELS = {"review:high"}
# Exact bot logins only — substring matches like "codex-helper" must not pass the gate.
CODEX_AUTHORS = frozenset({"chatgpt-codex-connector"})
# A clean Codex run posts no review, only this state marker in its summary PR comment.
CODEX_STATE = re.compile(r"<!-- codex-review-state:v1 (\{.*?\}) -->", re.S)


DOTCOM_HOSTS = frozenset({"github.com", "www.github.com"})


@contextlib.contextmanager
def gh_subprocess_env(env: dict[str, str] | None) -> Iterator[None]:
    """Apply a temporary env to every ``gh`` subprocess in this context."""
    token = _GH_SUBPROCESS_ENV.set(env)
    try:
        yield
    finally:
        _GH_SUBPROCESS_ENV.reset(token)


def run_gh(
    args: list[str],
    repo: str | None = None,
    hostname: str | None = None,
) -> Any:
    """Run `gh api`, optionally targeting an Enterprise host."""
    cmd = ["gh", "api"]
    if hostname:
        cmd.extend(["--hostname", hostname])
    if repo:
        cmd.extend(["-R", repo])
    cmd.extend(args)
    proc = subprocess.run(
        cmd, capture_output=True, text=True, env=_GH_SUBPROCESS_ENV.get()
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "gh api failed")
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def _normalize_api_hostname(host: str | None) -> str | None:
    """Normalize a hostname for ``gh api --hostname``.

    Keep ``github.com`` explicit so a process-level Enterprise ``GH_HOST`` cannot
    redirect hostless/default API calls away from an intentional dotcom target.
    """
    if not host:
        return None
    if host.lower() in DOTCOM_HOSTS:
        return "github.com"
    return host


def parse_repo_with_host(
    repo: str | None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str | None, str, str]:
    """Resolve (hostname|None, owner, name).

    Accepts gh's `[HOST/]OWNER/REPO` form. Explicit ``github.com`` is retained
    (as ``github.com``) so ``--hostname`` overrides an inherited Enterprise
    ``GH_HOST``. Other Enterprise hosts are preserved as-is.

    ``env`` is passed to ``gh repo view`` when resolving from cwd (used to scrub
    a process-level ``GH_REPO`` the merge command cleared).
    """
    if repo and "/" in repo:
        parts = [p for p in repo.strip().strip("/").split("/") if p]
        if len(parts) >= 2:
            owner, name = parts[-2], parts[-1]
            if name.endswith(".git"):
                name = name[: -len(".git")]
            host: str | None = None
            if len(parts) >= 3:
                host = _normalize_api_hostname(parts[0])
            return host, owner, name
    view_cmd = [
        "gh",
        "repo",
        "view",
        "--json",
        "owner,name,url",
        "-q",
        ".owner.login + \"/\" + .name + \" \" + .url",
    ]
    proc = subprocess.run(
        view_cmd,
        capture_output=True,
        text=True,
        cwd=cwd or None,
        env=env,
    )
    if proc.returncode != 0 or "/" not in proc.stdout:
        raise RuntimeError("could not resolve owner/repo; pass --repo OWNER/NAME")
    slug_and_url = proc.stdout.strip().split(None, 1)
    slug = slug_and_url[0]
    owner, name = slug.split("/", 1)
    host = None
    if len(slug_and_url) > 1:
        m = re.match(r"https?://([^/]+)/", slug_and_url[1], re.I)
        if m:
            # Dotcom URLs stay explicit so inherited GH_HOST cannot hijack queries.
            host = _normalize_api_hostname(m.group(1))
    return host, owner, name


def parse_repo(repo: str | None, cwd: str | None = None) -> tuple[str, str]:
    """Resolve OWNER/NAME. Prefer an explicit --repo; else `gh repo view` in cwd."""
    _host, owner, name = parse_repo_with_host(repo, cwd=cwd)
    return owner, name


def is_codex_author(login: str | None) -> bool:
    """True only for the known Codex GitHub App login — never body text or substrings."""
    return (login or "").lower() in CODEX_AUTHORS


def _graphql(
    query: str, hostname: str | None = None, **variables: Any
) -> dict[str, Any]:
    args = ["graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        args.extend(["-F", f"{key}={value}"])
    data = run_gh(args, hostname=hostname)
    return (data or {}).get("data") or {}


def _paginate_thread_comments(
    thread_id: str,
    hostname: str | None,
    first_page: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return all comments for a thread, starting from an optional embedded page."""
    comments: list[dict[str, Any]] = []
    c_conn = first_page or {}
    if first_page is not None:
        comments.extend(first_page.get("nodes") or [])
        page = first_page.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return comments
        c_cursor = page.get("endCursor")
        if not c_cursor:
            return comments
    else:
        c_cursor = None

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
    comment_first = """
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
    while True:
        if c_cursor is None:
            c_conn = (
                _graphql(comment_first, hostname=hostname, id=thread_id).get("node") or {}
            ).get("comments") or {}
            comments.extend(c_conn.get("nodes") or [])
        else:
            c_conn = (
                _graphql(
                    comment_q, hostname=hostname, id=thread_id, cursor=c_cursor
                ).get("node")
                or {}
            ).get("comments") or {}
            comments.extend(c_conn.get("nodes") or [])
        page = c_conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        c_cursor = page.get("endCursor")
        if not c_cursor:
            break
    return comments


def _paginate_threads(owner: str, name: str, number: int, hostname: str | None = None) -> list[dict[str, Any]]:
    """Fetch every review thread with comments embedded in the thread query.

    Most threads fit in the first comments page (50), so one GraphQL call covers
    up to 50 threads. Extra comment pages are fetched only when ``hasNextPage``.
    """
    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    thread_q = """
    query($owner:String!, $name:String!, $number:Int!, $cursor:String) {
      repository(owner:$owner, name:$name) {
        pullRequest(number:$number) {
          reviewThreads(first: 50, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              comments(first: 50) {
                pageInfo { hasNextPage endCursor }
                nodes { body author { login } }
              }
            }
          }
        }
      }
    }
    """
    while True:
        if cursor is None:
            first_q = """
            query($owner:String!, $name:String!, $number:Int!) {
              repository(owner:$owner, name:$name) {
                pullRequest(number:$number) {
                  reviewThreads(first: 50) {
                    pageInfo { hasNextPage endCursor }
                    nodes {
                      id
                      comments(first: 50) {
                        pageInfo { hasNextPage endCursor }
                        nodes { body author { login } }
                      }
                    }
                  }
                }
              }
            }
            """
            conn = (
                _graphql(first_q, hostname=hostname, owner=owner, name=name, number=number)
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads")
                or {}
            )
        else:
            conn = (
                _graphql(
                    thread_q,
                    hostname=hostname,
                    owner=owner,
                    name=name,
                    number=number,
                    cursor=cursor,
                )
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads")
                or {}
            )
        for node in conn.get("nodes") or []:
            thread_id = node.get("id")
            if not thread_id:
                continue
            embedded = node.get("comments") or {}
            comments = _paginate_thread_comments(
                thread_id, hostname, first_page=embedded
            )
            threads.append({"comments": {"nodes": comments}})
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            break
    return threads


def _paginate_reviews(owner: str, name: str, number: int, hostname: str | None = None) -> list[dict[str, Any]]:
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
                _graphql(q, hostname=hostname, owner=owner, name=name, number=number)
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
                _graphql(q, hostname=hostname, owner=owner, name=name, number=number, cursor=cursor)
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


def _paginate_labels(owner: str, name: str, number: int, hostname: str | None = None) -> list[dict[str, Any]]:
    """Fetch every label on the PR."""
    labels: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        if cursor is None:
            q = """
            query($owner:String!, $name:String!, $number:Int!) {
              repository(owner:$owner, name:$name) {
                pullRequest(number:$number) {
                  labels(first: 50) {
                    pageInfo { hasNextPage endCursor }
                    nodes { name }
                  }
                }
              }
            }
            """
            conn = (
                _graphql(q, hostname=hostname, owner=owner, name=name, number=number)
                .get("repository", {})
                .get("pullRequest", {})
                .get("labels")
                or {}
            )
        else:
            q = """
            query($owner:String!, $name:String!, $number:Int!, $cursor:String!) {
              repository(owner:$owner, name:$name) {
                pullRequest(number:$number) {
                  labels(first: 50, after: $cursor) {
                    pageInfo { hasNextPage endCursor }
                    nodes { name }
                  }
                }
              }
            }
            """
            conn = (
                _graphql(q, hostname=hostname, owner=owner, name=name, number=number, cursor=cursor)
                .get("repository", {})
                .get("pullRequest", {})
                .get("labels")
                or {}
            )
        labels.extend(conn.get("nodes") or [])
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            break
    return labels


def _codex_comments(
    owner: str, name: str, number: int, hostname: str | None = None
) -> list[dict[str, Any]]:
    """Every PR conversation comment (Codex keeps one summary comment updated)."""
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    q = """
    query($owner:String!, $name:String!, $number:Int!, $cursor:String) {
      repository(owner:$owner, name:$name) {
        pullRequest(number:$number) {
          comments(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes { author { login } body }
          }
        }
      }
    }
    """
    while True:
        variables: dict[str, Any] = {"owner": owner, "name": name, "number": number}
        if cursor:
            variables["cursor"] = cursor
        conn = (
            _graphql(q, hostname=hostname, **variables)
            .get("repository", {})
            .get("pullRequest", {})
            .get("comments")
            or {}
        )
        out.extend(conn.get("nodes") or [])
        page = conn.get("pageInfo") or {}
        cursor = page.get("endCursor")
        if not page.get("hasNextPage") or not cursor:
            return out


def codex_clean_comment_on_head(pr: dict[str, Any]) -> bool:
    """True when Codex's summary comment says a code review completed on the
    current head with no unresolved findings (the clean case posts no review)."""
    head = pr.get("headRefOid") or ""
    if not head:
        return False
    for c in pr.get("comments", {}).get("nodes") or []:
        if not is_codex_author((c.get("author") or {}).get("login")):
            continue
        # every marker in the comment, not only the first one
        for m in CODEX_STATE.finditer(c.get("body") or ""):
            try:
                review = json.loads(m.group(1)).get("code_review") or {}
            except (ValueError, AttributeError):
                continue  # malformed marker: not evidence of a review; fail closed
            if (
                review.get("commit_sha") == head
                and review.get("status") == "completed"
                and review.get("has_unresolved_findings") is False
            ):
                return True
    return False


def pr_payload(
    owner: str, name: str, number: int, hostname: str | None = None
) -> dict[str, Any]:
    q = """
    query($owner:String!, $name:String!, $number:Int!) {
      repository(owner:$owner, name:$name) {
        pullRequest(number:$number) {
          number
          body
          baseRefName
          headRefOid
        }
      }
    }
    """
    data = _graphql(q, hostname=hostname, owner=owner, name=name, number=number)
    pr = (data.get("repository") or {}).get("pullRequest")
    if not pr:
        raise RuntimeError(f"PR #{number} not found in {owner}/{name}")
    pr["labels"] = {"nodes": _paginate_labels(owner, name, number, hostname=hostname)}
    pr["reviews"] = {"nodes": _paginate_reviews(owner, name, number, hostname=hostname)}
    pr["comments"] = {"nodes": _codex_comments(owner, name, number, hostname=hostname)}
    pr["reviewThreads"] = {
        "nodes": _paginate_threads(owner, name, number, hostname=hostname)
    }
    return pr


def codex_done_on_head(pr: dict[str, Any]) -> bool:
    """True when a non-pending Codex review exists on the current head OID.

    Fail closed when ``commit.oid`` is missing (e.g. reviewed commit deleted) —
    an empty commit must not satisfy the current head.
    """
    head = pr.get("headRefOid") or ""
    if not head:
        return False
    for rev in pr.get("reviews", {}).get("nodes") or []:
        commit = (rev.get("commit") or {}).get("oid") or ""
        if not commit or commit != head:
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


_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|"
    "dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|"
    "iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|"
    "summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
# CommonMark html block type 6 (named block tags) ...
_HTML_BLOCK6 = re.compile(rf" {{0,3}}</?(?:{_BLOCK_TAGS})(?:[\s/>]|$)", re.I)
# ... and type 7 (one complete tag alone on its line; cannot interrupt a paragraph; quoted attrs may hold <>)
_HTML_BLOCK7 = re.compile(
    r" {0,3}(?:<[A-Za-z][A-Za-z0-9-]*(?:\s+(?:[^<>\"']|\"[^\"]*\"|'[^']*')*)?/?>"
    r"|</[A-Za-z][A-Za-z0-9-]*\s*>)\s*$")
# types 1, 3, 4, 5: (start, end marker); the block runs to the line holding the end marker
_RAW_BLOCKS = (
    (re.compile(r" {0,3}<(pre|script|style|textarea)\b", re.I), None),  # closes on its own </tag>
    (re.compile(r" {0,3}<\?"), re.compile(r"\?>")),
    (re.compile(r" {0,3}<![A-Za-z]"), re.compile(r">")),
    (re.compile(r" {0,3}<!\[CDATA\["), re.compile(r"\]\]>")),
)
# a backtick fence's info string cannot contain a backtick (CommonMark), or it is not a fence
_FENCE_OPEN = re.compile(r" {0,3}(?:(`{3,})[^`]*$|(~{3,}))")
# Any other fence-like line: indented, or after list markers (`- ````, `1. ~~~`, `  ```` under an
# item). Whether it is code, and where it ends, depends on the list container it sits in, which
# needs a full CommonMark parser (the runner has stdlib only). So everything from such a line to
# the end of the body is treated as code: an example attestation or closing reply in a list-nested
# fence can never count (AEC #163 Codex P1), at the cost that one placed after it fails closed.
_LOOSE_FENCE = re.compile(r"[ \t]*(?:(?:[-*+]|[0-9]{1,9}[.)])[ \t]+)*[ \t]*(?:`{3,}(?=[^`]*$)|~{3,})")


def _rendered_markdown(body: str) -> str:
    """Keep only what GitHub renders as prose, in one pass over the lines.

    Dropped: fenced and indented code, HTML comments, raw HTML blocks (a block
    opened by any tag at line start runs to the next blank line; pre/script/
    style/textarea run to their closing tag). One state machine, so an example
    inside a fence can never open a comment or block, and nothing opened is
    silently closed early. Unclosed constructs run to the end of the body, as
    GitHub renders them, so this only ever removes more, never less.
    """
    kept: list[str] = []
    fence: str | None = None
    in_comment = False
    raw_close: re.Pattern[str] | None = None  # end marker of an open <pre>-style block
    in_html = False  # inside a blank-line-terminated html block
    para = False  # previous line was paragraph text (type-7 blocks cannot interrupt it)
    in_def = False  # inside a possible link reference definition
    for line in body.replace("\r\n", "\n").split("\n"):
        was_para, para = para, False
        if fence is not None:
            marker = re.match(r" {0,3}(`{3,}|~{3,})", line)
            # a closing fence is the marker plus optional whitespace only (CommonMark)
            if (marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence)
                    and not line[marker.end():].strip()):
                fence = None
                kept.append("")  # like the opener: a block boundary (_plain_lines splits runs here)
                continue
            kept.append(_REJECTED if line.strip() else "")
            continue
        if raw_close is not None:
            if raw_close.search(line):
                raw_close = None
            kept.append(_REJECTED if line.strip() else "")
            continue
        if in_html:
            if line.strip():
                kept.append(_REJECTED)
                # the strict paragraph test may have taken a paragraph continuation for an html
                # block, so a fence or raw block opener inside it still opens; the html block
                # resumes after the raw one closes (both drop: fails closed)
                if _LOOSE_FENCE.match(line):
                    break
                raw = next(((m, c) for st, c in _RAW_BLOCKS if (m := st.match(line))), None)
                if raw and not (raw[1] or re.compile(rf"</{raw[0].group(1)}\s*>", re.I)).search(line[raw[0].end():]):
                    raw_close = raw[1] or re.compile(rf"</{raw[0].group(1)}\s*>", re.I)
                continue
            in_html = False
        if not in_comment:
            opener = _FENCE_OPEN.match(line)
            if opener and line[:1] in " \t":
                break  # an indented fence: the rest of the body is unreadable as prose (see _LOOSE_FENCE)
            if not opener and _LOOSE_FENCE.match(line):
                break
            if opener:
                fence = opener.group(1) or opener.group(2)
                kept.append("")  # the dropped fence still ends a paragraph (and a quote's lazy continuation)
                continue
            # indented code cannot interrupt a paragraph (CommonMark): after prose it is a continuation
            # 4+ columns of indent, tabs to 4-column stops (` \t` is 4 columns: #105 Codex r7 P1)
            if line.strip() and len(line) - len(line.lstrip(" \t")) and \
                    len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip()) >= 4 and not was_para:
                kept.append(_REJECTED if line.strip() else "")
                continue
            raw = next(((m, c) for st, c in _RAW_BLOCKS if (m := st.match(line))), None)
            if raw:
                raw_close = raw[1] or re.compile(rf"</{raw[0].group(1)}\s*>", re.I)
                if raw_close.search(line[raw[0].end():]):
                    raw_close = None
                kept.append(_REJECTED if line.strip() else "")
                continue
            if _HTML_BLOCK6.match(line) or (not was_para and _HTML_BLOCK7.match(line)):
                in_html = True
                kept.append(_REJECTED if line.strip() else "")
                continue
        # strip HTML comment spans, which may open or close mid-line
        out = ""
        rest = line
        while rest:
            if in_comment:
                end = rest.find("-->")
                if end < 0:
                    rest = ""
                else:
                    in_comment, rest = False, rest[end + 3 :]
            else:
                start = rest.find("<!--")
                if start < 0:
                    out += rest
                    rest = ""
                else:
                    out += rest[:start]
                    in_comment, rest = True, rest[start + 4 :]
        # paragraph state from the same strict shape test as _plain_lines: anything else (headings,
        # list items holding code, HTML, headings or nested markers, link definitions) is no paragraph
        para, in_def = _plain(line, was_para, in_def)
        para = para and bool(out.strip())
        kept.append(out if out.strip() else _REJECTED if line.strip() else "")
    return "\n".join(kept)


def review_section_names_fallback(body: str, head: str | None = None) -> bool:
    """Require one explicit completed-review line bound to the current head.

    Full-line matching excludes incidental prose, URLs and generated footers.
    Compare the entire captured SHA prefix so a stale longer SHA cannot pass
    merely because its first seven characters match.
    """
    if not head or len(head) < 7:
        return False
    body = _prose(body)
    m = REVIEW_SECTION.search(body)
    if not m:
        return False
    rest = body[m.end() :]
    next_h = re.search(r"(?m)^##\s+", rest)
    section = rest[: next_h.start()] if next_h else rest
    # \n only: str.splitlines() also splits on U+2028 and friends.
    for line in section.split("\n"):
        if INCOMPLETE_REVIEW.search(line):
            continue
        attestation = FALLBACK_ATTESTATION.fullmatch(line.strip())
        if attestation and head.lower().startswith(attestation.group(2).lower()):
            return True
    return False


# What may interrupt a paragraph (CommonMark), so a lazy continuation ends: an ATX heading, a
# thematic break, a NON-EMPTY list item (ordered ones only when starting at 1), or a real fence
# (left to _FENCE_OPEN: a ``` line whose info string holds a backtick is not a fence). Anything
# else, such as `2. note` or an empty `-`, is lazy continuation text and stays inside the quote.
_INTERRUPTS = re.compile(
    r" {0,3}(?:#{1,6}(?:[ \t]|$)|([-*_])(?:[ \t]*\1){2,}[ \t]*$|(?:[-*+]|0{0,8}1[.)])[ \t]+\S)")


def _unquoted(text: str) -> str:
    """Drop blockquotes, including lazy continuation lines (a non-blank line
    after a `>` line stays inside the quote until a blank line or a line that
    interrupts a paragraph) and quotes nested in list items (`- > example`)."""
    kept: list[str] = []
    in_quote = False
    for line in text.split("\n"):
        marker = re.match(r"[ \t]*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)*>", line)
        if marker:
            # A marker-only line (`>`, `> >`) is a blank line inside the quote: it ends the quoted
            # paragraph, so no lazy continuation follows it (aec #163 Codex P2).
            in_quote = bool(line[marker.end():].strip(" \t>"))
            kept.append("")
            continue
        # A lazy continuation is paragraph text only: a line that interrupts a paragraph
        # (ATX heading, fence, thematic break, list item) ends the quote and is kept.
        if in_quote and line.strip() and not (_INTERRUPTS.match(line) or _FENCE_OPEN.match(line)):
            kept.append("")
            continue
        in_quote = False
        kept.append(line)
    return "\n".join(kept)


# a code span: a backtick run closed by a run of the same length, never across a blank line
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)((?:(?!\n[ \t]*\n).)+?)(?<!`)\1(?!`)", re.S)


def _prose(body: str) -> str:
    """Rendered prose only: no code blocks, comments or HTML blocks, no quotes,
    and every inline code span collapsed to the word `code`, so an example
    span (even one wrapping onto its own line) cannot start a line. A span that
    is only a commit SHA keeps its text, so `fixed in `abc1234`` still reads."""
    def span(m: re.Match[str]) -> str:
        inner = m.group(2).strip()
        if re.fullmatch(r"[0-9a-f]{7,40}", inner, re.I):
            return inner
        return "\n".join(["code"] * (m.group(0).count("\n") + 1))  # one line per source line
    source = (body or "").replace("\r\n", "\n").split("\n")
    rendered = _CODE_SPAN.sub(span, _unquoted(_rendered_markdown(body or ""))).split("\n")
    return "\n".join(_plain_lines(source, rendered))


# Where an attestation or a closing token may start: a letter, a markdown link, or an autolink.
_PLAIN_START = re.compile(r"[A-Za-z\[]|<https?://", re.I)
# One list marker followed by 1-4 spaces: the item's content is a paragraph, never indented code.
_LIST_LEAD = re.compile(r"(?:[-*+]|[0-9]{1,9}[.)]) {1,4}")
_REJECTED = "\x00"


def _plain(src: str, after_para: bool, in_def: bool) -> tuple[bool, bool]:
    """(is `src` paragraph text by the strict shape below, still inside a link definition)."""
    if not src.strip():
        return False, False
    lead = len(src) - len(src.lstrip(" \t"))
    text = src[lead:]
    item = _LIST_LEAD.match(text)
    content = text[item.end():] if item else text
    # a link definition (`[x]:`, also after a list marker) can run over the next lines as its
    # destination and title, which are not paragraph text: no paragraph until a blank line
    in_def = in_def or bool(re.match(r"\[[^\]]*\]:", content))
    if content.startswith(">") and content.strip(" \t>") and len(src[:lead].expandtabs(4)) < 4:
        return True, in_def  # a quoted paragraph: its lazy lines are the quote's (_unquoted drops them)
    return (not lead or after_para) and not in_def and bool(_PLAIN_START.match(content)), in_def


def _plain_lines(source: list[str], rendered: list[str]) -> list[str]:
    """Allow-list on top of the block parser above (#105 Codex r4-r7: four rounds of CommonMark
    container cases). That parser keeps line i of the body as line i. A rendered line survives only
    when its SOURCE line has a shape that can only be paragraph text:
      - column 0, optionally one list marker plus 1-4 spaces, then a letter, `[` or `<http`; or
      - indented (spaces or tabs), directly after a surviving paragraph line, then the same start
        (a paragraph continuation: an indented line after paragraph text is never code).
    Anything else (an indented line after a heading, blank or non-paragraph line, 5+ spaces after a marker, nested or marker-only containers, headings,
    setext underlines, HTML or fence openers inside list items) becomes _REJECTED, failing closed:
    a non-blank line holding no token, so it still separates nothing that a real line would not.
    Column-0 `#` lines are kept so `## Review` and section ends still read."""
    out: list[str] = []
    cont = in_def = False
    for src, line in zip(source, rendered):
        if src.startswith("#"):
            out.append(line)
            cont = False
            continue
        ok, in_def = _plain(src, cont, in_def)
        ok = ok and bool(line.strip())
        out.append(line if ok or not line.strip() else _REJECTED)
        cont = ok
    # Whole-block pass (#105 Codex r8, r9): a run of non-blank source lines is rejected entirely when
    # any line holds `<`, `[` or `]` outside a one-line `[label](url)`, since inline HTML (tags, attributes, comments, processing
    # instructions, CDATA), links, images, titles and reference labels can all span lines and hide
    # text; and the lines above any underline-shaped line (any indent: list items shift columns) are
    # rejected, as they may be a setext heading. Deliberately coarser than CommonMark: an attestation
    # or closing reply that shares a block with a link or tag fails closed (put it in its own block).
    # An underline ends the block: lines after it start a new run. `out` may be shorter than the
    # body (an indented fence drops the rest), so only its lines are judged.
    source, rendered = source[: len(out)], rendered[: len(out)]
    start = 0
    for i in range(len(source) + 1):
        underline = 0 < i - start and i < len(source) and bool(_SETEXT.match(source[i]))
        if i < len(source) and source[i].strip() and rendered[i] != "" and not underline:
            continue
        run = range(start, i + underline)
        if underline or any(_RISKY.search(_one_line_safe(source[k])) for k in run):
            for k in run:
                if not source[k].startswith("#"):
                    out[k] = _REJECTED
        start = i + 1
    return out


_SETEXT = re.compile(r"[ \t>]*(?:=+|-+)[ \t]*$")
_RISKY = re.compile(r"[<\[\]]")
# a link or image closed on its line, plain destination, no title: visible label, cannot span lines
# (a link label holds no unescaped bracket, so whatever stays around it is still caught by _RISKY)
_SIMPLE_LINK = re.compile(r"!?\[[^\[\]\\]*\]\([^\s()<>\"'\\]+\)")
# constructs that open and close on one line and so cannot hide the lines around them: a code span
# (opener not escaped), a plain tag with bare attributes or an autolink after other text (first on
# the line, past indent and list or quote markers, a tag can open an html block), and a bracket pair
# that is not a link, image or definition
_CODE_SPAN_LINE = re.compile(r"(?<![`\\])(`+)(?!`)[^`\n]+?(?<!`)\1(?!`)")
_INLINE_TAG = re.compile(
    r"(?<=.)(?:</?[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[A-Za-z_:][\w.:-]*)*[ \t]*/?>"
    r"|<[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>`\\]*>)"
)
_LINE_LEAD = re.compile(r"(?:[ \t>]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]+|$))*[ \t>]*")
_PLAIN_BRACKETS = re.compile(r"(?<![\]\\!])\[(?:[^\[\]\\]|\\[^\[\]])*\](?![(\[:])")


def _one_line_safe(line: str) -> str:
    line = _SIMPLE_LINK.sub("", _CODE_SPAN_LINE.sub("", line))
    lead = _LINE_LEAD.match(line).end()
    line = line[:lead] + _INLINE_TAG.sub("", line[lead:])
    while (stripped := _PLAIN_BRACKETS.sub("", line)) != line:
        line = stripped
    return line


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
        if any(_closes(_prose(c.get("body") or "")) for c in replies):
            continue
        failures.append(
            f"P2 thread #{i} has no closing reply (Notion link / fixed in <sha> / not-a-finding:)"
        )
    return failures


def evaluate(pr: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    body = pr.get("body") or ""
    head = pr.get("headRefOid") or ""
    # Rendered view: a heading inside a comment or fence is not visible.
    if not REVIEW_SECTION.search(_rendered_markdown(body)):
        reasons.append("PR body missing ## Review section")
    if not (
        codex_done_on_head(pr)
        or codex_clean_comment_on_head(pr)
        or review_section_names_fallback(body, head)
    ):
        reasons.append(
            "No completed Codex review on current head, and ## Review lacks a completed "
            "fallback attestation: Fallback review: <codex|agy|antigravity|superpowers|claude-sonnet> "
            "on <head SHA> — verdict: <clean|findings fixed>"
        )
    reasons.extend(p2_threads_closed(pr))
    if (pr.get("baseRefName") or "") == "main":
        labels = {n.get("name") for n in (pr.get("labels", {}).get("nodes") or [])}
        if not (labels & MAIN_REVIEW_LABELS):
            reasons.append("base is main but label review:high is missing")
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
        hostname, owner, name = parse_repo_with_host(repo)
        pr = pr_payload(owner, name, number, hostname=hostname)
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
