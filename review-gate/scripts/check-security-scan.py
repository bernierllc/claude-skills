#!/usr/bin/env python3
"""Review Gate's security lane: accept a `Security Scan` result only from the trusted scanner job.

Opt-in. The lane is active when the DEFAULT BRANCH has .github/workflows/review-gate-security-scan.yml (the OSS scanner
template; 3.3.1 renamed it from security-scan.yml, a name a repo's own unrelated workflow can already
have). A PR that adds or deletes that file changes nothing: activation, the config digest and this script
are all read from the default branch (trust check f).

The scanner jobs are found through the Actions API, never through check-run names (a check run's name,
details_url and annotations are writable by anyone with checks: write): every job, all attempts, of every
.github/workflows/review-gate-security-scan.yml pull_request_target run on the head. When active, the gate passes only
when the NEWEST such job (by the job's started_at, then id) and its own check run are
  a. from a run triggered by THIS PR (check-forged-review-gate.py's run_provenance), the job listed under
     that run, its check_run_url naming its own id, and the check run's id, details_url job id and name
     (`Security Scan`) all matching it: a renamed check fails instead of dropping out of freshness;
  b. published by the github-actions app;
  c. on the PR's current head sha (the job and its check run);
  d. completed: a newer failure is never masked by an older success, and a job still in progress is
     incomplete, which fails. Status and conclusion come from the job;
  e. carrying exactly one `security-scan` annotation, `outcome=<o> config-tree=<sha>`, whose sha is the
     default branch's current tree of .github/security-scan (scanner config, rules, baseline, exceptions),
     and whose outcome agrees with the conclusion (success: passed | not-applicable; failure: findings |
     scanner-error). Zero or several such annotations fail: scanner output cannot add a second one unnoticed.
Any other Actions job's check run named `Security Scan` is forged and fails the gate; a Checks API POST
is never a scanner job, so it is never evidence.

The PR body's `Security review:` lines (model review coverage, nevar-security-review) are printed as
ADVISORY/UNVERIFIED and never count as evidence. A body line in `## Review`, or any `Security review:` /
`Security scan:` line, that names a scanner with a pass word fails the gate unless the verified scan passed.
Residual: a pass claim worded elsewhere in the body is not detected, and is still not evidence.

Residual: the scan usually finishes after the gate's own run, so the gate reports it incomplete until it is
re-fired (label toggle) once the scan completes.
Residual: every job of review-gate-security-scan.yml counts as a scanner job, so the template keeps a single job. Runs are
found by head_sha, which assumes the pull_request_target run records the PR head (run_provenance relies on the
same); the scanner template's canary must prove it.
Residual: with the lane on, any other Actions job whose check run is named `Security Scan` is read as forged
and fails the gate, so a repo enabling the lane renames such a job of its own first.

env: REPO, PR_NUMBER, DEFAULT_BRANCH (required); SHA (the event's head; must still be the PR's head).
Exit 0: lane passed or not enabled. 1: failed (reason on stderr). 2: could not evaluate (fails closed).
"""
import importlib.util
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

NAME = "Security Scan"
TRUSTED = (".github/workflows/review-gate-security-scan.yml", "pull_request_target")
CONFIG_DIR = "security-scan"  # .github/security-scan on the default branch
ANNOTATION = "security-scan"
OUTCOME = re.compile(r"outcome=(passed|not-applicable|findings|scanner-error) config-tree=([0-9a-f]{40})")
PASSING = {"passed", "not-applicable"}
SCANNER = re.compile(r"\b(gitleaks|osv-scanner|zizmor|semgrep|security scan)\b", re.I)
PASS_WORD = re.compile(r"\b(pass|passed|passes|clean|green|success|succeeded|ok)\b", re.I)
LABELLED = re.compile(r"^\s*security (review|scan):", re.I)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lines(body):
    return body.replace("\r\n", "\n").replace("\r", "\n").split("\n")  # as check-review-gate.py splits it


def claims(body):
    """Body lines that claim a scanner pass: in `## Review`, or labelled `Security review:` / `Security scan:`."""
    found, in_review = [], False
    for line in _lines(body):
        if line.startswith("## "):
            in_review = line.rstrip() == "## Review"
        if (in_review or LABELLED.match(line)) and SCANNER.search(line) and PASS_WORD.search(line):
            found.append(line.strip())
    return found


def _entries(w, repo, path, ref):
    listing = w._api_json(f"repos/{repo}/contents/{path}?{urllib.parse.urlencode({'ref': ref})}")
    if not isinstance(listing, list):
        raise w.Ambiguous(f"{path} on {ref} is not a directory listing")
    if not all(isinstance(e, dict) and isinstance(e.get("name"), str) for e in listing):
        raise w.Ambiguous(f"{path} on {ref} lists a malformed entry")  # never read as "lane not enabled"
    if len(listing) >= 1000:  # the Contents API's cap: a file past it would read as absent
        raise w.Ambiguous(f"{path} on {ref} lists {len(listing)} entries, the Contents API cap; cannot tell what is absent")
    return {e["name"]: e for e in listing}


def _listing(w, path, key):
    """Every item of a paginated GitHub listing, or w.Ambiguous when the pages are malformed or short."""
    pages = w._api_json(path, "--paginate", "--slurp")
    if not isinstance(pages, list) or not pages or not all(isinstance(p, dict) for p in pages):
        raise w.Ambiguous(f"{path} is not a list of pages")
    items = [i for p in pages for i in p.get(key, [])]
    if len(items) != pages[0].get("total_count"):
        raise w.Ambiguous(f"{path} has {len(items)} {key}, total_count {pages[0].get('total_count')!r}")
    return items


def verdict(w, detector, repo, pr, head, ref):
    """None when the trusted scan on `head` passed; else why not. Raises w.Ambiguous when unreadable."""
    runs = _listing(w, f"repos/{repo}/actions/workflows/{TRUSTED[0].rsplit('/', 1)[1]}/runs?"
                    + urllib.parse.urlencode({"head_sha": head, "event": TRUSTED[1], "per_page": 100}), "workflow_runs")
    jobs = []
    for run in runs:
        if (w._text(run, "path").split("@", 1)[0], w._text(run, "event")) != TRUSTED:
            continue  # the API already filters by workflow and event; a run outside the pair is never a scan
        why = w.run_provenance(repo, pr, run["id"])  # (a) this PR's own run
        if why:
            return f"'{NAME}' run {run['id']} is not this PR's scan: {why}"
        for job in _listing(w, f"repos/{repo}/actions/runs/{run['id']}/jobs?filter=all&per_page=100", "jobs"):
            if not isinstance(job, dict) or not isinstance(job.get("id"), int) or job.get("run_id") != run["id"]:  # (a)
                return f"run {run['id']} lists a job that is not its own: {job!r:.120}"
            jobs.append(job)
    scanner = {j["id"] for j in jobs}
    named = _listing(w, f"repos/{repo}/commits/{head}/check-runs?"
                     + urllib.parse.urlencode({"check_name": NAME, "filter": "all", "per_page": 100}), "check_runs")
    for check in named:  # (a) another Actions job publishing the name is forged; a Checks API POST never counts
        if check.get("name") == NAME and check.get("id") not in scanner and detector.job_run_id(check) is not None:
            return f"forged '{NAME}' check {check.get('id')}: not a job of this PR's trusted scanner run"
    if not jobs:
        return f"no trusted '{NAME}' run on {head[:12]} yet; re-fire Review Gate once it completes"
    # (d) the newest scanner job decides; an unfinished one (queued, started_at null) outranks every finished one so
    # the lane reads incomplete, while a finished job that never started (cancelled) sorts oldest, never blocking
    job = max(jobs, key=lambda j: (j.get("status") != "completed", j.get("started_at") or "", j["id"]))
    latest = w._api_json(f"repos/{repo}/check-runs/{job['id']}")
    linked = re.search(r"/job/(\d+)", w._text(latest, "details_url"))
    if (latest.get("id") != job["id"] or not linked or int(linked.group(1)) != job["id"]
            or not str(job.get("check_run_url", "")).endswith(f"/check-runs/{job['id']}")):  # (a)
        return f"forged '{NAME}' check {job['id']}: not bound to its Actions job"
    if latest.get("name") != NAME:  # (a) a renamed check fails; it never drops out of freshness
        return f"the newest scanner job {job['id']} has a check run named {latest.get('name')!r}, not '{NAME}'"
    if w._text(latest, "app", "slug") != "github-actions":  # (b)
        return f"'{NAME}' check {job['id']} was published by {latest['app']['slug']!r}, not github-actions"
    if w._text(latest, "head_sha") != head or job.get("head_sha") != head:  # (c)
        return f"'{NAME}' check {job['id']} is on {latest['head_sha'][:12]}, not the PR head {head[:12]}"
    if job.get("status") != "completed":  # (d)
        return f"'{NAME}' check {job['id']} is {job.get('status')}; re-fire Review Gate once it completes"
    annotations = w._api_json(f"repos/{repo}/check-runs/{latest['id']}/annotations", "--paginate", "--slurp")
    flat = [a for page in annotations for a in page] if isinstance(annotations, list) else None
    if flat is None or len(flat) != (latest.get("output") or {}).get("annotations_count"):
        raise w.Ambiguous(f"the annotations of check {latest['id']} do not match its annotations_count")
    mine = [a for a in flat if isinstance(a, dict) and a.get("title") == ANNOTATION]
    if len(mine) != 1:  # (e)
        return f"'{NAME}' check {latest['id']} has {len(mine)} '{ANNOTATION}' annotations, not exactly one"
    match = OUTCOME.fullmatch(str(mine[0].get("message", "")).strip())
    if not match:
        return f"'{NAME}' check {latest['id']} has a malformed '{ANNOTATION}' annotation"
    outcome, tree = match.groups()
    config = _entries(w, repo, ".github", ref).get(CONFIG_DIR)  # (e, f) the default branch's config, never the PR's
    if not config or config.get("type") != "dir":
        return f"the security lane is enabled but {ref} has no .github/{CONFIG_DIR}/ config directory"
    if tree != w._text(config, "sha"):
        return (f"'{NAME}' check {latest['id']} scanned config tree {tree[:12]}, not {ref}'s current "
                f"{config['sha'][:12]}; re-run Security Scan")
    conclusion = job.get("conclusion")
    if conclusion == "success" and outcome in PASSING:
        return None
    if conclusion == "failure" and outcome not in PASSING:
        return f"'{NAME}' check {latest['id']} reported {outcome}"
    return f"'{NAME}' check {latest['id']} concluded {conclusion!r} with outcome {outcome}: treated as a scanner error"


def main():
    try:
        w = _load("check_forged_review_gate", "check-forged-review-gate.py")
        detector = _load("check_forged_gate_names", "check-forged-gate-names.py")
    except (OSError, ImportError, SyntaxError) as exc:
        print(f"::error::security lane: could not load its helpers, failing closed: {exc}", file=sys.stderr)
        return 2
    repo, pr, ref = (os.environ.get(k, "") for k in ("REPO", "PR_NUMBER", "DEFAULT_BRANCH"))
    if not repo or not ref or not re.fullmatch(r"[1-9][0-9]*", pr):
        print("::error::security lane: REPO, PR_NUMBER and DEFAULT_BRANCH are required", file=sys.stderr)
        return 2
    try:
        pull = w._api_json(f"repos/{repo}/pulls/{pr}")
        head = w._text(pull, "head", "sha")
        if os.environ.get("SHA") and os.environ["SHA"] != head:
            raise w.Ambiguous(f"the PR head moved from {os.environ['SHA'][:12]} to {head[:12]}; a newer run decides")
        body = pull.get("body") or ""
        for line in _lines(body):
            if line.lower().startswith("security review:"):
                print(f"ADVISORY/UNVERIFIED (model review, not evidence): {line.strip()}")
        claimed = claims(body)
        active = "review-gate-security-scan.yml" in _entries(w, repo, ".github/workflows", ref)  # (f) default branch only
        why = verdict(w, detector, repo, pr, head, ref) if active else None
    except (ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError, w.Ambiguous) as exc:
        print(f"::error::security lane: could not evaluate, failing closed: {exc}", file=sys.stderr)
        return 2
    if not active:
        if claimed:
            print(f"::error::security lane: the PR body claims a scanner pass ({claimed[0]!r}) but {ref} has no "
                  "Security Scan workflow, so nothing verifies it; remove the claim", file=sys.stderr)
            return 1
        print("security lane not enabled (no .github/workflows/review-gate-security-scan.yml on the default branch)")
        return 0
    if why:
        print(f"::error::security lane: {why}", file=sys.stderr)
        if claimed:
            print(f"::error::security lane: the PR body claims a scanner pass ({claimed[0]!r}) that the verified "
                  "Security Scan does not show", file=sys.stderr)
        return 1
    print("security lane ok: the trusted Security Scan passed on the PR head with the default branch's config")
    return 0


if __name__ == "__main__":
    sys.exit(main())
