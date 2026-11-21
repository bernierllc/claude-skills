#!/usr/bin/env python3
"""Review Gate's forged-check step: the vendored aec detector, scoped to the `Review Gate` name.

check-forged-gate-names.py is vendored byte-identical from
bernierllc/agents-environment-config@dba592dbf5a95d89a19d7b4dfaf2ea11fdf44821 (aec #154: exits 2 on
empty, malformed or runless input) (scripts/check-forged-gate-names.py; plan
plans/2026-11-16-unforgeable-required-checks.md, step S5).
Re-vendor it by copying that file unchanged; never edit it here.

WHY THIS WRAPPER EXISTS: the vendored PROTECTED map also protects "PRs into main must come from
staging" with no trusted pair (set()). Several downstream repos still publish that name from a plain
`pull_request` Actions job, so running the detector unscoped would fail every main promotion in those
repos. The map stays unchanged; this wrapper checks only `Review Gate`. The other name stays the job
of each repo's own main-via-staging guard.

THE GATE'S OWN JOB IS THE RESULT (3.2.8): the vendored map trusts (.github/workflows/review-gate.yml,
pull_request_target), and that job publishes `Review Gate`. A pull_request_target job's check run is on
the PR HEAD, in its own workflow run's suite (email_demo #1068: job 133165097976 on head 6402d452, suite
118647401541), not on the base as 3.2.0-3.2.7 assumed. A Checks API POST cannot pick a suite and lands in
the head's oldest one, which the required-status rule does not read (BLOCKED "expected", #104), so the
job is the only placement that holds. Another PR's gate job reaches this head when a PR shares the head
sha. So a trusted-pair job is accepted only when its workflow run is THIS PR's, by provenance (3.2.16):

ONE PROVENANCE PATH, run-name or not. The run title is not trust: a default branch whose review-gate.yml
predates run-name (a pre-3.2.0 workflow whose job is named `Review Gate`) titles the run with the PR title,
which the PR author writes, so `Review Gate - PR #<n>` can be typed into any PR. A title naming another PR
(RUN_TITLE) only picks the 3.2.13 shared-head message; it never accepts. Every other run is accepted only when
the run's head sha, branch and repository equal this PR's head (forks included: GitHub sets both from the
PR), the run is not older than the PR, and no other PR from that head repo and branch, in any state, has this
head sha or was open when the run was created. Each field must be a non-empty string; anything missing or
mistyped exits 2. A PR author controls none of the event or path of a pull_request_target run, nor its head
fields. Any other Actions job named `Review Gate` is forged.

DELETE THIS WRAPPER when Option A or B of the aec plan lands (a required workflow or a distinct
publisher app, making the required checks unforgeable through the Checks API). The detector is then
retired or kept as defence in depth (plan step S4) and review-gate.yml calls it directly or not at all.

A missing or malformed PR_NUMBER, or a failed run lookup, exits 2.

env: REPO (required), PR_NUMBER (needed to accept the gate's own job).
stdin: `set -o pipefail; gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100&filter=all" --paginate`
Exit 0: none forged. 1: forged (listed on stderr). 2: could not evaluate (fails closed).
"""
import functools
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path


RUN_TITLE = "Review Gate - PR #{pr}"  # = run-name in review-gate.yml; a test parses both and compares


class Ambiguous(Exception):
    """A run's PR could not be established: fail closed with exit 2."""


def _gh(*args):
    try:
        return subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as exc:
        raise Ambiguous(f"gh api {args[0]} failed: {exc.stderr.strip()}") from exc


@functools.lru_cache(maxsize=None)
def _api_json(*args):
    """One `gh api` read per distinct call per invocation (#134: the merge guard's 20 s budget). A failure is
    not cached: it raises Ambiguous, which ends the invocation with exit 2."""
    return json.loads(_gh(*args))


def _text(obj, *keys):
    """obj[k1][k2]... as a non-empty string; anything else is Ambiguous (null == null must never match)."""
    for key in keys:
        obj = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(obj, str) or not obj:
        raise Ambiguous(f"{'.'.join(keys)} is missing or not a string ({obj!r})")
    return obj


def run_provenance(repo, pr, run_id):
    """None when workflow run `run_id` was triggered by PR #pr; else why not."""
    pull = _api_json(f"repos/{repo}/pulls/{pr}")
    want = (_text(pull, "head", "sha"), _text(pull, "head", "ref"), _text(pull, "head", "repo", "full_name"))
    opened = _text(pull, "created_at")
    run = _api_json(f"repos/{repo}/actions/runs/{run_id}")
    got = (_text(run, "head_sha"), _text(run, "head_branch"), _text(run, "head_repository", "full_name"))
    started = _text(run, "created_at")
    if got != want or started < opened:
        return f"run {run_id} head {got} at {started} is not this PR's head {want} (opened {opened})"
    # The only way to rule out another PR's run: the run does not name its PR, and `commits/{sha}/pulls` omits
    # closed-unmerged PRs, so every PR from this head repo and branch, in any state, is listed. Another one that
    # has this head sha (a closed PR's head is frozen, and labeling it still runs the gate) or was open when the
    # run was created could have triggered it. An older PR closed before the run, on another sha, could not.
    query = urllib.parse.urlencode({"state": "all", "head": f"{want[2].split('/')[0]}:{want[1]}", "per_page": 100})
    pages = _api_json(f"repos/{repo}/pulls?{query}", "--paginate", "--slurp")
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise Ambiguous(f"the PR listing for {want[1]} is not a list of pages")
    others = []
    for listed in (item for page in pages for item in page):
        number = listed.get("number") if isinstance(listed, dict) else None
        if not isinstance(number, int) or isinstance(number, bool):
            raise Ambiguous(f"a PR in the listing for {want[1]} has no number ({listed!r})")
        if number == int(pr):
            continue
        closed = None if listed.get("closed_at") is None else _text(listed, "closed_at")
        if _text(listed, "head", "sha") == want[0] or (
                _text(listed, "created_at") <= started and (closed is None or closed >= started)):
            others.append(number)
    if others:
        return (f"this head sha is also PR #{min(others)}'s head. Push a new commit to this PR (an empty commit "
                "works) so it has a head of its own")
    return None


def foreign_run(repo, pr, run_id):
    """None when workflow run `run_id` is PR #pr's own gate run; else why its job is not this PR's."""
    title = _text(_api_json(f"repos/{repo}/actions/runs/{run_id}"), "display_title").strip()
    other = re.fullmatch(re.escape(RUN_TITLE).replace(r"\{pr\}", "([1-9][0-9]*)"), title)
    if other and other.group(1) != pr:  # a real gate run of another PR on this same head sha: name the fix (3.2.13)
        return (f"run {run_id} is titled {title!r}, not {RUN_TITLE.format(pr=pr)!r}: this head sha is also "
                f"PR #{other.group(1)}'s head, and that PR's Review Gate run is listed on it. Push a new commit to "
                "this PR (an empty commit works) so it has a head of its own")
    return run_provenance(repo, pr, run_id)  # a matching title is not trust: on a stale main the PR wrote it


def main():
    try:
        spec = importlib.util.spec_from_file_location(
            "check_forged_gate_names", Path(__file__).with_name("check-forged-gate-names.py")
        )
        detector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(detector)
        trusted = detector.PROTECTED["Review Gate"]  # KeyError if a re-vendor drops the name: fail closed
        scoped = {"Review Gate": set()}  # every job is looked at; trusted pairs are then checked below
    except (OSError, ImportError, KeyError, SyntaxError) as exc:
        print(f"::error::could not load the forged-check detector, failing closed: {exc}", file=sys.stderr)
        return 2
    repo = os.environ.get("REPO")
    if not repo:
        print("::error::REPO is required", file=sys.stderr)
        return 2
    try:
        lookup = functools.lru_cache(maxsize=None)(detector._gh_run_lookup(repo))  # a rerun's jobs share a run
        flagged = []
        for check_run in detector._load_check_runs(sys.stdin.read()):
            seen = []

            def record(run_id):
                seen.append((run_id, lookup(run_id)))
                return seen[-1][1]
            for name, where in detector.forged([check_run], record, scoped):
                flagged.append((name, where, *seen[-1]))
        bad = []
        for name, where, run_id, pair in flagged:
            if pair not in trusted:
                bad.append((name, where, "untrusted workflow"))
                continue
            pr = os.environ.get("PR_NUMBER", "")
            if not re.fullmatch(r"[1-9][0-9]*", pr):
                raise Ambiguous(f"PR_NUMBER is missing or malformed ({pr!r}); it is needed to accept the gate's job")
            why = foreign_run(repo, pr, run_id)
            if why:
                bad.append((name, where, why))
    except (ValueError, KeyError, TypeError, subprocess.CalledProcessError, Ambiguous) as exc:
        print(f"::error::could not evaluate check runs, failing closed: {exc}", file=sys.stderr)
        return 2
    for name, where, why in bad:
        kind = "shared head sha, not this PR's run" if "is also PR #" in why else "from an untrusted Actions job"
        print(f"::error::forged check '{name}' {kind}: {where} ({why})", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
