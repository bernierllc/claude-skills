#!/usr/bin/env python3
"""Review Gate's forged-check step: the vendored aec detector, scoped to the `Review Gate` name.

check-forged-gate-names.py was vendored byte-identical from
bernierllc/agents-environment-config@41f629945c291c4e0a84f20f14a077852e7dd9dc (exits 2 on empty, malformed,
runless or truncated input; pins the main-via-staging guard job) (scripts/check-forged-gate-names.py; plan
plans/2026-11-16-unforgeable-required-checks.md, step S5). 3.7.0 adds the `Notion Sync` pin to this copy first
(claude-skills #152); aec's copy is re-synced from it. A consuming repo re-vendors with install-workflow.py --force
and never edits it.

WHY THIS WRAPPER EXISTS: the vendored PROTECTED map also protects "PRs into main must come from
staging" (pinned to main-via-staging.yml pull_request_target since 3.2.20). Several downstream repos still publish that name from a plain
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
head sha or was open when the run was created. That listing must contain this PR on this head ref and sha
(3.2.18): an empty listing proves nothing. Each field must be a non-empty string; anything missing or
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
    # closed-unmerged PRs, so every PR from this head repo and branch, in any state, is listed.
    query = urllib.parse.urlencode({"state": "all", "head": f"{want[2].split('/')[0]}:{want[1]}", "per_page": 100})
    return branch_verdict(int(pr), want[0], want[1], started,
                          _api_json(f"repos/{repo}/pulls?{query}", "--paginate", "--slurp"))


def branch_verdict(pr, sha, ref, started, pages):
    """None when the branch listing proves no other PR could have triggered a run created at `started`; else why.

    One fail-closed shape (3.2.18): the listing must positively contain PR #pr on this head ref and sha, and
    every other entry must be well formed. Anything else (an empty listing, this PR missing or moved) proves
    nothing, so it is Ambiguous (exit 2), never "no competitor". Another PR that has this head sha (a closed PR's
    head is frozen, and labeling it still runs the gate) or was open when the run was created could have
    triggered it; an older PR closed before the run, on another sha, could not.
    """
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise Ambiguous(f"the PR listing for {ref} is not a list of pages")
    found, others = False, []
    for listed in (item for page in pages for item in page):
        number = listed.get("number") if isinstance(listed, dict) else None
        if not isinstance(number, int) or isinstance(number, bool):
            raise Ambiguous(f"a PR in the listing for {ref} has no number ({listed!r})")
        if number == pr:
            found = (_text(listed, "head", "sha"), _text(listed, "head", "ref")) == (sha, ref)
            if not found:
                raise Ambiguous(f"PR #{pr} is listed on branch {ref} with another head; retry")
            continue
        closed = None if listed.get("closed_at") is None else _text(listed, "closed_at")
        if _text(listed, "head", "sha") == sha or (
                _text(listed, "created_at") <= started and (closed is None or closed >= started)):
            others.append((closed is not None, number))  # open PRs sort first: their remedy is the one that works
    if not found:
        raise Ambiguous(f"the PR listing for {ref} does not contain PR #{pr}, so it proves nothing")
    if not others:
        return None
    closed, number = min(others)
    if not closed:  # a new commit on a shared branch becomes the other open PR's head too
        return (f"PR #{number} is also open from head branch {ref!r}, so a new commit becomes its head too. "
                f"Close PR #{number} or open each PR from its own head branch")
    return (f"this head sha is also PR #{number}'s head. Push a new commit to this PR (an empty commit "
            "works) so it has a head of its own")  # true only here: the closed PR's head is frozen


def foreign_run(repo, pr, run_id):
    """None when workflow run `run_id` is PR #pr's own gate run; else why its job is not this PR's."""
    title = _text(_api_json(f"repos/{repo}/actions/runs/{run_id}"), "display_title").strip()
    other = re.fullmatch(re.escape(RUN_TITLE).replace(r"\{pr\}", "([1-9][0-9]*)"), title)
    if other and other.group(1) != pr:  # a real gate run of another PR on this same head sha: name the fix (3.2.13)
        # 3.2.18: provenance names the fix when the other PR is open on this branch (close or split, not a commit).
        # The title already rejects the run (exit 1); an unreadable provenance only loses that refinement.
        try:
            why = run_provenance(repo, pr, run_id)
        except (Ambiguous, subprocess.CalledProcessError, ValueError) as exc:
            print(f"::warning::run {run_id}: provenance unreadable, so the remedy assumes a closed PR: {exc}",
                  file=sys.stderr)
            why = None
        return (f"run {run_id} is titled {title!r}, not {RUN_TITLE.format(pr=pr)!r}: " + (
            why or f"this head sha is also PR #{other.group(1)}'s head, and that PR's "
            "Review Gate run is listed on it. Push a new commit to this PR (an empty commit works) so it has a head "
            "of its own"))
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
        def lookup(run_id):  # the run read provenance reuses (3.2.18: one read per run, not two)
            run = _api_json(f"repos/{repo}/actions/runs/{run_id}")
            return _text(run, "path").split("@", 1)[0], _text(run, "event")  # `path@ref` for required workflows
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
        kind = "shared head sha, not this PR's run" if re.search(r"is also (PR #|open)", why) else "from an untrusted Actions job"
        print(f"::error::forged check '{name}' {kind}: {where} ({why})", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
