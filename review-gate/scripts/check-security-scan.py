#!/usr/bin/env python3
"""Review Gate's security lane: accept a `Security Scan` result only from the trusted scanner job.

Opt-in. The lane is active when the DEFAULT BRANCH has .github/workflows/security-scan.yml (the OSS scanner
template). A PR that adds or deletes that file changes nothing: activation, the config digest and this script
are all read from the default branch (trust check f).

When active, the gate passes only on a `Security Scan` check run that is
  a. the job of a .github/workflows/security-scan.yml pull_request_target run triggered by THIS PR
     (check-forged-review-gate.py's run_provenance), with check-run id == the job id in its details_url,
     and that job listed by the Actions jobs API under that run with a check_run_url naming this check
     run. A Checks API POST (later PATCHed to point details_url at its own id) is never accepted;
  b. published by the github-actions app;
  c. on the PR's current head sha;
  d. the newest such run (the job's started_at, then id): an older success never masks a newer failure,
     and a job still in progress is incomplete, which fails. Status and conclusion come from the job;
  e. carrying exactly one `security-scan` annotation, `outcome=<o> config-tree=<sha>`, whose sha is the
     default branch's current tree of .github/security-scan (scanner config, rules, baseline, exceptions),
     and whose outcome agrees with the conclusion (success: passed | not-applicable; failure: findings |
     scanner-error). Zero or several such annotations fail: scanner output cannot add a second one unnoticed.
Any other Actions job named `Security Scan` is forged and fails the gate.

The PR body's `Security review:` lines (model review coverage, nevar-security-review) are printed as
ADVISORY/UNVERIFIED and never count as evidence. A body line in `## Review`, or any `Security review:` /
`Security scan:` line, that names a scanner with a pass word fails the gate unless the verified scan passed.
Residual: a pass claim worded elsewhere in the body is not detected, and is still not evidence.

Residual: the scan usually finishes after the gate's own run, so the gate reports it incomplete until it is
re-fired (label toggle) once the scan completes.

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
TRUSTED = (".github/workflows/security-scan.yml", "pull_request_target")
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


def claims(body):
    """Body lines that claim a scanner pass: in `## Review`, or labelled `Security review:` / `Security scan:`."""
    found, in_review = [], False
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.startswith("## "):
            in_review = line.rstrip() == "## Review"
        if (in_review or LABELLED.match(line)) and SCANNER.search(line) and PASS_WORD.search(line):
            found.append(line.strip())
    return found


def _entries(w, repo, path, ref):
    listing = w._api_json(f"repos/{repo}/contents/{path}?{urllib.parse.urlencode({'ref': ref})}")
    if not isinstance(listing, list):
        raise w.Ambiguous(f"{path} on {ref} is not a directory listing")
    return {w._text(e, "name"): e for e in listing if isinstance(e, dict)}


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
    runs = _listing(w, f"repos/{repo}/commits/{head}/check-runs?"
                    + urllib.parse.urlencode({"check_name": NAME, "filter": "all", "per_page": 100}), "check_runs")
    trusted = []
    for check in runs:
        if check.get("name") != NAME:
            continue
        run_id = detector.job_run_id(check)
        if run_id is None:
            continue  # a Checks API POST: never evidence, so it cannot pass the lane
        run = w._api_json(f"repos/{repo}/actions/runs/{run_id}")
        pair = (w._text(run, "path").split("@", 1)[0], w._text(run, "event"))
        linked = re.search(r"/job/(\d+)", w._text(check, "details_url"))
        if pair != TRUSTED or not linked or check.get("id") != int(linked.group(1)):  # (a)
            return f"forged '{NAME}' check {check.get('id')} from {pair[0]} ({pair[1]}), not the trusted scanner job"
        jobs = _listing(w, f"repos/{repo}/actions/runs/{run_id}/jobs?filter=all&per_page=100", "jobs")
        job = next((j for j in jobs if isinstance(j, dict) and j.get("id") == check["id"]), None)
        if (not job or job.get("run_id") != int(run_id)
                or not str(job.get("check_run_url", "")).endswith(f"/check-runs/{check['id']}")):  # (a)
            return f"forged '{NAME}' check {check['id']}: run {run_id} has no Actions job bound to it"
        if w._text(check, "app", "slug") != "github-actions":  # (b)
            return f"'{NAME}' check {check['id']} was published by {check['app']['slug']!r}, not github-actions"
        if w._text(check, "head_sha") != head:  # (c)
            return f"'{NAME}' check {check['id']} is on {check['head_sha'][:12]}, not the PR head {head[:12]}"
        why = w.run_provenance(repo, pr, run_id)  # (a) this PR's own run
        if why:
            return f"'{NAME}' check {check['id']} is not this PR's scan: {why}"
        trusted.append({**check, **{k: job.get(k) for k in ("status", "conclusion", "started_at")}})  # (d)
    if not trusted:
        return f"no trusted '{NAME}' run on {head[:12]} yet; re-fire Review Gate once it completes"
    latest = max(trusted, key=lambda c: (c.get("started_at") or "", c["id"]))  # (d)
    if latest.get("status") != "completed":
        return f"'{NAME}' check {latest['id']} is {latest.get('status')}; re-fire Review Gate once it completes"
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
    conclusion = latest.get("conclusion")
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
        for line in body.replace("\r\n", "\n").split("\n"):
            if line.lower().startswith("security review:"):
                print(f"ADVISORY/UNVERIFIED (model review, not evidence): {line.strip()}")
        claimed = claims(body)
        active = "security-scan.yml" in _entries(w, repo, ".github/workflows", ref)  # (f) default branch only
        why = verdict(w, detector, repo, pr, head, ref) if active else None
    except (ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError, w.Ambiguous) as exc:
        print(f"::error::security lane: could not evaluate, failing closed: {exc}", file=sys.stderr)
        return 2
    if not active:
        if claimed:
            print(f"::error::security lane: the PR body claims a scanner pass ({claimed[0]!r}) but {ref} has no "
                  "Security Scan workflow, so nothing verifies it; remove the claim", file=sys.stderr)
            return 1
        print("security lane not enabled (no .github/workflows/security-scan.yml on the default branch)")
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
