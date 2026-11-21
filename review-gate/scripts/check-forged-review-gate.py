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
sha (open, merged, or closed: `commits/{sha}/pulls` omits closed-unmerged PRs, so a PR listing cannot
rule them out). So a trusted-pair job is accepted only when its workflow run is THIS PR's: the run's
display_title is the workflow's run-name, `Review Gate - PR #<n>` (RUN_TITLE), fixed from the event when
the run is created and set only by the trusted default-branch workflow (confirmed live, nevar-auth #23).
Any other Actions job named `Review Gate` is forged.

STALE MAIN (3.2.16): a default branch whose review-gate.yml predates run-name (a pre-3.2.0 workflow whose
job is named `Review Gate`) titles the gate's run with the PR title, so the re-vendor PR that brings
run-name could never pass. When the title neither is RUN_TITLE nor names another PR, the trusted-pair
job is still this PR's when ALL hold: the default branch's review-gate.yml has no run-name (so this
self-disables once main is re-vendored); a non-default base carries the same blob; the run's head sha,
branch, repository and creation time match this PR (head branch not the base, run not older than the PR);
and `commits/{sha}/pulls` names no other PR. A PR author controls none of the default-branch workflow, the
event or path of a pull_request_target run, nor the run's head fields, which GitHub sets from the PR.

DELETE THIS WRAPPER when Option A or B of the aec plan lands (a required workflow or a distinct
publisher app, making the required checks unforgeable through the Checks API). The detector is then
retired or kept as defence in depth (plan step S4) and review-gate.yml calls it directly or not at all.

A missing or malformed PR_NUMBER, or a failed run lookup, exits 2.

env: REPO (required), PR_NUMBER (needed to accept the gate's own job).
stdin: `set -o pipefail; gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100&filter=all" --paginate`
Exit 0: none forged. 1: forged (listed on stderr). 2: could not evaluate (fails closed).
"""
import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path


RUN_TITLE = "Review Gate - PR #{pr}"  # = run-name in review-gate.yml; a test parses both and compares


class Ambiguous(Exception):
    """A run's PR could not be established: fail closed with exit 2."""


def _gh(*args):
    try:
        return subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as exc:
        raise Ambiguous(f"gh api {args[0]} failed: {exc.stderr.strip()}") from exc


def stale_main_run(repo, pr, run_id, path):
    """None when run `run_id` is PR #pr's gate run under a default-branch workflow without run-name; else why not."""
    pull = json.loads(_gh(f"repos/{repo}/pulls/{pr}"))
    base, default, head = pull["base"]["ref"], pull["base"]["repo"]["default_branch"], pull["head"]
    main_wf = json.loads(_gh(f"repos/{repo}/contents/{path}?ref={default}"))
    if re.search(r"(?m)^run-name\s*:", base64.b64decode(main_wf["content"]).decode()):
        return f"{default}'s {path} sets run-name, so this PR's run is titled by it"
    if base != default and json.loads(_gh(f"repos/{repo}/contents/{path}?ref={base}"))["sha"] != main_wf["sha"]:
        return f"base {base}'s {path} differs from {default}'s"
    run = json.loads(_gh(f"repos/{repo}/actions/runs/{run_id}"))
    got = (run["head_sha"], run["head_branch"], run["head_repository"]["full_name"])
    want = (head["sha"], head["ref"], head["repo"]["full_name"])
    if got != want or head["ref"] == base or run["created_at"] < pull["created_at"]:
        return f"run {run_id} head {got} at {run['created_at']} is not this PR's head {want} into {base}"
    others = sorted({p["number"] for p in json.loads(_gh(f"repos/{repo}/commits/{head['sha']}/pulls"))} - {int(pr)})
    if others:
        return (f"this head sha is also PR #{others[0]}'s head. Push a new commit to this PR (an empty commit "
                "works) so it has a head of its own")
    return None


def foreign_run(repo, pr, run_id, path):
    """None when workflow run `run_id` is PR #pr's own gate run; else why its job is not this PR's."""
    title = _gh(f"repos/{repo}/actions/runs/{run_id}", "--jq", ".display_title").strip()
    want = RUN_TITLE.format(pr=pr)
    if title == want:
        return None
    why = f"run {run_id} is titled {title!r}, not {want!r}"
    other = re.fullmatch(re.escape(RUN_TITLE).replace(r"\{pr\}", "([1-9][0-9]*)"), title)
    if other:  # a real gate run of another PR on this same head sha, not a forgery: name the fix (3.2.13)
        return why + (f": this head sha is also PR #{other.group(1)}'s head, and that PR's Review Gate run is "
                      "listed on it. Push a new commit to this PR (an empty commit works) so it has a head of its own")
    stale = stale_main_run(repo, pr, run_id, path)
    return stale and f"{why}: {stale}"


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
        lookup = detector._gh_run_lookup(repo)
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
            why = foreign_run(repo, pr, run_id, pair[0])
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
