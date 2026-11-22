#!/usr/bin/env python3
"""Review Gate's security lane: accept a `Security Scan` result only from the trusted scanner job.

Opt-in. The lane is active when the DEFAULT BRANCH has .github/workflows/review-gate-security-scan.yml (the OSS scanner
template; 3.3.1 renamed it from security-scan.yml, a name a repo's own unrelated workflow can already
have). A PR that adds or deletes that file changes nothing: activation, the config digest and this script
are all read from the default branch (trust check f).

The scanner jobs are found through the Actions API, never through check-run names (a check run's name,
details_url and annotations are writable by anyone with checks: write): every job, all attempts, of
  - every .github/workflows/review-gate-security-scan.yml pull_request_target run on the head, and
  - every workflow_dispatch run of that file created in the last MAX_AGE on the default branch and titled
    RUN_TITLE for this PR and head, whose head_sha is the default branch's tip or an ancestor of it (a tag or
    another ref of the same name is not the branch): the re-scan Security Refresh (`--refresh`, below) dispatches.
When active, the gate passes only when the NEWEST such job (by the job's started_at, then id) and its own check
run are
  a. from a run triggered by THIS PR (check-forged-review-gate.py's run_provenance; a dispatch run instead runs
     the default branch's own workflow, and its notice must name this PR and head, check g), the job listed under
     that run, its check_run_url naming its own id, and the check run's id, details_url job id and name
     (`Security Scan`) all matching it: a renamed check fails instead of dropping out of freshness;
  b. published by the github-actions app;
  c. on its run's head sha (the job and its check run): the PR head, or for a dispatch run the default
     branch commit it ran, the scanned head being the notice's;
  d. completed: a newer failure is never masked by an older success, and a job still in progress is
     incomplete, which fails. Status and conclusion come from the job;
  e. carrying exactly one `security-scan` annotation (NOTICE), whose config-tree is the
     default branch's current tree of .github/security-scan (scanner config, rules, baseline, exceptions),
     and whose outcome agrees with the conclusion (success: passed | not-applicable; failure: findings |
     scanner-error). Zero or several such annotations fail: scanner output cannot add a second one unnoticed.
     A notice in the pre-3.4.0 two-field form fails as stale: re-vendor nevar-security-review's scan template;
  g. fresh: the notice names this PR, its current head and base ref, the default branch's current blob of the
     scan workflow and its current POLICY_FILES revision (policy_revision); any exception it relied on has not
     expired (exceptions-until); and the job completed within MAX_AGE. A change to any of these on the default
     branch therefore fails every open PR's lane until it is re-scanned, which the Security Refresh workflow
     (templates/review-gate-security-refresh.yml) dispatches on that push, daily, and after each scan.
  h. run by the current gate: in GitHub Actions, the review-gate.yml this run executes (GITHUB_WORKFLOW_SHA) is
     the default branch's current blob. A re-run keeps its original workflow file, so re-running a run from before
     the gate was re-vendored fails instead of passing on the old YAML; push, close and reopen, or toggle a label
     to start a fresh run. Outside Actions (the merge guard) there is no gate run, and the check is skipped.
Any other Actions job's check run named `Security Scan` is forged and fails the gate; a Checks API POST
is never a scanner job, so it is never evidence.

The PR body's `Security review:` lines (model review coverage, nevar-security-review) are printed as
ADVISORY/UNVERIFIED and never count as evidence. A body line in `## Review`, or any `Security review:` /
`Security scan:` line, that names a scanner with a pass word fails the gate unless the verified scan passed.
Residual: a pass claim worded elsewhere in the body is not detected, and is still not evidence.

Residual: the scan usually finishes after the gate's own run. The Security Refresh workflow re-runs the PR's
newest Review Gate run when a scan completes. Only a re-run is possible: events from the workflow's GITHUB_TOKEN
start no workflow, and a dispatched gate run's check lands on the default branch commit, not the PR head the
required check reads. So after review-gate.yml changes on the default branch, every open PR's gate fails (h) until
a person pushes, toggles a label, or closes and reopens it.
Residual: MAX_AGE (36 h) assumes the daily refresh: GitHub can delay or drop a scheduled run, so the margin is
12 h. A PR retargeted to another base is re-scanned by the next daily refresh, or on close and reopen.
Residual: every job of review-gate-security-scan.yml counts as a scanner job, so the template keeps a single job. Runs are
found by head_sha, which assumes the pull_request_target run records the PR head (run_provenance relies on the
same); the scanner template's canary must prove it.
Residual: with the lane on, any other Actions job whose check run is named `Security Scan` is read as forged
and fails the gate, so a repo enabling the lane renames such a job of its own first.

env: REPO, PR_NUMBER, DEFAULT_BRANCH (required); SHA (the event's head; must still be the PR's head);
SECURITY_LANE_NOW (optional, timezone-aware ISO time; moves the clock forward only, for tests); GITHUB_ACTIONS and
GITHUB_WORKFLOW_SHA (the runner's own, check h).
Exit 0: lane passed or not enabled. 1: failed (reason on stderr). 2: could not evaluate (fails closed).

`--policy-revision <checkout>` prints the POLICY_FILES revision of a local git checkout's HEAD (the scan
workflow records it in its notice). `--refresh` is the Security Refresh workflow's body: env REPO,
DEFAULT_BRANCH, EVENT (github.event_name) and, for workflow_run, TITLE (the completed run's display_title).
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

NAME = "Security Scan"
TRUSTED = (".github/workflows/review-gate-security-scan.yml", "pull_request_target")
CONFIG_DIR = "security-scan"  # .github/security-scan on the default branch
ANNOTATION = "security-scan"
OUTCOME = re.compile(r"outcome=(passed|not-applicable|findings|scanner-error) config-tree=([0-9a-f]{40})")  # pre-3.4.0
NOTICE = re.compile(r"outcome=(?P<outcome>passed|not-applicable|findings|scanner-error) config-tree=(?P<tree>[0-9a-f]{40}) "
                    r"pr=(?P<pr>[1-9][0-9]*) head=(?P<head>[0-9a-f]{40}) base-ref=(?P<base_ref>[^\s:]+) "
                    r"workflow=(?P<workflow>[0-9a-f]{40}) policy=(?P<policy>[0-9a-f]{64}) "
                    r"exceptions-until=(?P<until>[0-9]{4}-[0-9]{2}-[0-9]{2}|none)")
RUN_TITLE = "Security Scan - PR #{pr} @ {head}"  # = run-name in the scan template; its test formats this
DISPATCH = "workflow_dispatch"
MAX_AGE = timedelta(hours=36)  # the refresh is daily; GitHub may delay a scheduled run, hence 12 h of margin
# The default-branch files whose change makes every earlier scan stale (check g): the gate, this lane, the
# helpers it loads, and the local merge guard. The refresh workflow's push paths list these too (a test pins it).
POLICY_FILES = (".github/workflows/review-gate.yml", "scripts/check-security-scan.py", "scripts/check-review-gate.py",
                "scripts/check-forged-review-gate.py", "scripts/check-forged-gate-names.py",
                ".claude/skills/review-gate/scripts/merge-guard.py")
GATE_FILE = "review-gate.yml"
POLL_S, POLL_TRIES = 10, 12  # --refresh waits up to 2 min for a running gate run before re-running it
PASSING = {"passed", "not-applicable"}
SCANNER = re.compile(r"\b(gitleaks|osv-scanner|zizmor|semgrep|security scan)\b", re.I)
PASS_WORD = re.compile(r"\b(pass|passed|passes|clean|green|success|succeeded|ok)\b", re.I)
LABELLED = re.compile(r"^\s*security (review|scan):", re.I)
# Every pass word counts, negated or not. Parsing negation ("did not pass") was evaded three ways in review
# (SKILLS-SEC-CLAIM-2), so a failure report is reworded without a pass word instead; REWORD says how.
REWORD = ("if that line reports a failure, reword it without a pass word, "
          "e.g. 'semgrep reported 2 findings'")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lines(body):
    return body.replace("\r\n", "\n").replace("\r", "\n").split("\n")  # as check-review-gate.py splits it


def claims(body):
    """Body lines that claim a scanner pass: in `## Review`, or labelled `Security review:` / `Security scan:`.

    A failure report that uses a pass word ("semgrep did not pass") counts too: fail closed, see REWORD.
    """
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


def _revision(blobs):
    """The policy revision: sha256 over "<path> <blob or ->" lines, one per POLICY_FILES path, sorted."""
    return hashlib.sha256("".join(f"{p} {blobs.get(p) or '-'}\n" for p in sorted(POLICY_FILES)).encode()).hexdigest()


def local_policy(checkout):
    """The policy revision of a git checkout's HEAD (regular files only, as the Contents API's type "file")."""
    subprocess.run(["git", "-C", checkout, "rev-parse", "--verify", "HEAD"], check=True, capture_output=True)
    out = subprocess.run(["git", "-C", checkout, "ls-tree", "-z", "HEAD", "--", *POLICY_FILES],
                         check=True, capture_output=True, text=True).stdout
    blobs = {}
    for entry in filter(None, out.split("\0")):
        meta, path = entry.split("\t", 1)
        mode, kind, sha = meta.split()
        if path in POLICY_FILES and kind == "blob" and mode in ("100644", "100755"):
            blobs[path] = sha
    return _revision(blobs)


def remote_policy(w, repo, ref):
    """The policy revision of `ref` through the Contents API; a missing directory leaves its files "-"."""
    blobs = {}
    for parent in sorted({p.rsplit("/", 1)[0] for p in POLICY_FILES}):
        try:
            entries = _entries(w, repo, parent, ref)
        except w.Ambiguous as exc:
            if "HTTP 404" in str(exc):
                continue  # no such directory: its files are absent, exactly as `git ls-tree` reports them
            raise
        for path in POLICY_FILES:
            entry = entries.get(path.rsplit("/", 1)[1]) if path.rsplit("/", 1)[0] == parent else None
            if entry and entry.get("type") == "file":
                blobs[path] = w._text(entry, "sha")
    return _revision(blobs)


def _time(text):
    """An ISO 8601 time. GitHub writes UTC as a trailing Z, which fromisoformat rejects before Python 3.11."""
    return datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)


def now_utc():
    """The current UTC time; SECURITY_LANE_NOW can only move it forward (a test of expiry), never back."""
    now = datetime.now(timezone.utc)
    forced = os.environ.get("SECURITY_LANE_NOW")
    if forced:
        later = _time(forced)
        if later.tzinfo is None:
            raise ValueError("SECURITY_LANE_NOW must carry a timezone")
        now = max(now, later)
    return now


class _Refused(Exception):
    """verdict's reason the lane fails (exit 1), raised from a helper."""


def _jobs(w, repo, run, expect):
    """(job, expected head sha) for every job of `run`, all attempts; a job that is not the run's own refuses."""
    out = []
    for job in _listing(w, f"repos/{repo}/actions/runs/{run['id']}/jobs?filter=all&per_page=100", "jobs"):
        if not isinstance(job, dict) or not isinstance(job.get("id"), int) or job.get("run_id") != run["id"]:  # (a)
            raise _Refused(f"run {run['id']} lists a job that is not its own: {job!r:.120}")
        out.append((job, expect))
    return out


def verdict(w, detector, repo, pr, pull, head, ref, workflows, now):
    """None when the trusted scan of `head` passed and is fresh; else why not. Raises w.Ambiguous when unreadable."""
    try:
        return _verdict(w, detector, repo, pr, pull, head, ref, workflows, now)
    except _Refused as exc:
        return str(exc)


def _verdict(w, detector, repo, pr, pull, head, ref, workflows, now):
    wf = TRUSTED[0].rsplit("/", 1)[1]
    runs = _listing(w, f"repos/{repo}/actions/workflows/{wf}/runs?"
                    + urllib.parse.urlencode({"head_sha": head, "event": TRUSTED[1], "per_page": 100}), "workflow_runs")
    jobs = []
    for run in runs:
        if (w._text(run, "path").split("@", 1)[0], w._text(run, "event")) != TRUSTED:
            continue  # the API already filters by workflow and event; a run outside the pair is never a scan
        why = w.run_provenance(repo, pr, run["id"])  # (a) this PR's own run
        if why:
            return f"'{NAME}' run {run['id']} is not this PR's scan: {why}"
        jobs += _jobs(w, repo, run, head)
    since = (now - MAX_AGE).strftime("%Y-%m-%dT%H:%M:%SZ")
    title, tip = RUN_TITLE.format(pr=pr, head=head), None
    for run in _listing(w, f"repos/{repo}/actions/workflows/{wf}/runs?" + urllib.parse.urlencode(
            {"event": DISPATCH, "branch": ref, "created": f">={since}", "per_page": 100}), "workflow_runs"):
        # (a) a re-scan: the default branch's own workflow, dispatched for this PR and head (writers and the
        # refresh workflow only: dispatching needs actions: write). Another PR's or head's re-scan is skipped.
        if ((w._text(run, "path").split("@", 1)[0], w._text(run, "event")) == (TRUSTED[0], DISPATCH)
                and run.get("head_branch") == ref and run.get("display_title") == title):
            # head_branch is a bare name, which a tag can share: the commit must be on the branch itself
            tip = tip or w._text(w._api_json(f"repos/{repo}/branches/{ref}"), "commit", "sha")
            sha = w._text(run, "head_sha")
            if w._text(w._api_json(f"repos/{repo}/compare/{tip}...{sha}"), "status") in ("identical", "behind"):
                jobs += _jobs(w, repo, run, sha)
    scanner = {j["id"] for j, _ in jobs}
    named = _listing(w, f"repos/{repo}/commits/{head}/check-runs?"
                     + urllib.parse.urlencode({"check_name": NAME, "filter": "all", "per_page": 100}), "check_runs")
    for check in named:  # (a) another Actions job publishing the name is forged; a Checks API POST never counts
        if check.get("name") == NAME and check.get("id") not in scanner and detector.job_run_id(check) is not None:
            return f"forged '{NAME}' check {check.get('id')}: not a job of this PR's trusted scanner run"
    if not jobs:
        return f"no trusted '{NAME}' run on {head[:12]} yet; Review Gate re-runs once it completes"
    # (d) the newest scanner job decides; an unfinished one (queued, started_at null) outranks every finished one so
    # the lane reads incomplete, while a finished job that never started (cancelled) sorts oldest, never blocking
    job, expect = max(jobs, key=lambda je: (je[0].get("status") != "completed", je[0].get("started_at") or "", je[0]["id"]))
    latest = w._api_json(f"repos/{repo}/check-runs/{job['id']}")
    linked = re.search(r"/job/(\d+)", w._text(latest, "details_url"))
    if (latest.get("id") != job["id"] or not linked or int(linked.group(1)) != job["id"]
            or not str(job.get("check_run_url", "")).endswith(f"/check-runs/{job['id']}")):  # (a)
        return f"forged '{NAME}' check {job['id']}: not bound to its Actions job"
    if latest.get("name") != NAME:  # (a) a renamed check fails; it never drops out of freshness
        return f"the newest scanner job {job['id']} has a check run named {latest.get('name')!r}, not '{NAME}'"
    if w._text(latest, "app", "slug") != "github-actions":  # (b)
        return f"'{NAME}' check {job['id']} was published by {latest['app']['slug']!r}, not github-actions"
    if w._text(latest, "head_sha") != expect or job.get("head_sha") != expect:  # (c)
        return f"'{NAME}' check {job['id']} is on {latest['head_sha'][:12]}, not its run's head {expect[:12]}"
    if job.get("status") != "completed":  # (d)
        return f"'{NAME}' check {job['id']} is {job.get('status')}; Review Gate re-runs once it completes"
    annotations = w._api_json(f"repos/{repo}/check-runs/{latest['id']}/annotations", "--paginate", "--slurp")
    flat = [a for page in annotations for a in page] if isinstance(annotations, list) else None
    if flat is None or len(flat) != (latest.get("output") or {}).get("annotations_count"):
        raise w.Ambiguous(f"the annotations of check {latest['id']} do not match its annotations_count")
    mine = [a for a in flat if isinstance(a, dict) and a.get("title") == ANNOTATION]
    if len(mine) != 1:  # (e)
        return f"'{NAME}' check {latest['id']} has {len(mine)} '{ANNOTATION}' annotations, not exactly one"
    text = str(mine[0].get("message", "")).strip()
    match = NOTICE.fullmatch(text)
    if not match:
        if OUTCOME.fullmatch(text):
            return (f"'{NAME}' check {latest['id']} has a pre-3.4.0 notice with no freshness fields: re-vendor "
                    "nevar-security-review's scan template (review-gate-security-scan.yml and security-scan/scan.py)")
        return f"'{NAME}' check {latest['id']} has a malformed '{ANNOTATION}' annotation"
    notice = match.groupdict()
    outcome, tree = notice["outcome"], notice["tree"]
    config = _entries(w, repo, ".github", ref).get(CONFIG_DIR)  # (e, f) the default branch's config, never the PR's
    if not config or config.get("type") != "dir":
        return f"the security lane is enabled but {ref} has no .github/{CONFIG_DIR}/ config directory"
    if tree != w._text(config, "sha"):
        return (f"'{NAME}' check {latest['id']} scanned config tree {tree[:12]}, not {ref}'s current "
                f"{config['sha'][:12]}; re-run Security Scan")
    stale = _stale(w, repo, pr, pull, head, ref, workflows, now, notice, job)  # (g)
    if stale:
        return f"'{NAME}' check {latest['id']} is stale: {stale}; the Security Refresh workflow re-scans it"
    conclusion = job.get("conclusion")
    if conclusion == "success" and outcome in PASSING:
        return None
    if conclusion == "failure" and outcome not in PASSING:
        return f"'{NAME}' check {latest['id']} reported {outcome}"
    return f"'{NAME}' check {latest['id']} concluded {conclusion!r} with outcome {outcome}: treated as a scanner error"


def _stale(w, repo, pr, pull, head, ref, workflows, now, notice, job):
    """(g) Why the scan no longer stands for this PR's current state, or None."""
    base = w._text(pull, "base", "ref")
    if (notice["pr"], notice["head"]) != (pr, head):
        return f"it scanned PR #{notice['pr']} @ {notice['head'][:12]}, not PR #{pr} @ {head[:12]}"
    if notice["base_ref"] != base:
        return f"it scanned against base {notice['base_ref']!r} and the PR now targets {base!r}"
    blob = w._text(workflows[TRUSTED[0].rsplit("/", 1)[1]], "sha")
    if notice["workflow"] != blob:
        return f"it ran scan workflow blob {notice['workflow'][:12]}, not {ref}'s current {blob[:12]}"
    policy = remote_policy(w, repo, ref)
    if notice["policy"] != policy:
        return f"it ran under policy revision {notice['policy'][:12]}, not {ref}'s current {policy[:12]}"
    if notice["until"] != "none" and date.fromisoformat(notice["until"]) < now.date():
        return f"an exception it relied on expired after {notice['until']}"
    completed = _time(w._text(job, "completed_at"))
    if completed.tzinfo is None or completed < now - MAX_AGE:
        return f"it completed at {job['completed_at']}, more than {MAX_AGE.total_seconds() / 3600:.0f} h ago"
    return None


def _gate_file(w, repo, ref, workflows):
    """(h) Why this gate run is not the default branch's current review-gate.yml, or None (see the docstring)."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None  # the merge guard, or a local run: no gate run to check
    sha = os.environ.get("GITHUB_WORKFLOW_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise w.Ambiguous("GITHUB_WORKFLOW_SHA is unset or malformed: cannot tell which review-gate.yml this run executes")
    ran = w._text(w._api_json(f"repos/{repo}/contents/.github/workflows/{GATE_FILE}?"
                              + urllib.parse.urlencode({"ref": sha})), "sha")
    current = w._text(workflows.get(GATE_FILE), "sha")
    if ran != current:
        return (f"this Review Gate run executes review-gate.yml blob {ran[:12]}, not {ref}'s current {current[:12]} "
                "(a re-run keeps its original workflow file); push, close and reopen, or toggle a label on the PR "
                "to start a fresh run")
    return None


def _pages(w, path):
    pages = w._api_json(path, "--paginate", "--slurp")
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        raise w.Ambiguous(f"{path} is not a list of pages")
    return [i for p in pages for i in p]


def _gate_run(w, repo, pr, head, fresh=False):
    """PR #pr's newest Review Gate run on `head`, or None. `fresh` bypasses the read cache (polling)."""
    path = f"repos/{repo}/actions/workflows/{GATE_FILE}/runs?" + urllib.parse.urlencode(
        {"head_sha": head, "event": TRUSTED[1], "per_page": 100})
    pages = json.loads(w._gh(path, "--paginate", "--slurp")) if fresh else w._api_json(path, "--paginate", "--slurp")
    if not isinstance(pages, list) or not all(isinstance(p, dict) for p in pages):
        raise w.Ambiguous(f"{path} is not a list of pages")
    mine = [r for p in pages for r in p.get("workflow_runs", []) if isinstance(r, dict)
            and str(r.get("path", "")).split("@", 1)[0] == f".github/workflows/{GATE_FILE}"
            and r.get("display_title") == w.RUN_TITLE.format(pr=pr)]
    return max(mine, key=lambda r: (str(r.get("created_at") or ""), r.get("id") or 0), default=None)


def _rerun(w, repo, pr, head, wait):
    """Re-run PR #pr's newest Review Gate run; None, or why it could not."""
    run = _gate_run(w, repo, pr, head)
    if run is None:
        return "it has no Review Gate run to re-run"
    for _ in range(POLL_TRIES if wait else 0):  # a running run cannot be re-run; the scan's re-run waits for it
        if run.get("status") == "completed":
            break
        time.sleep(POLL_S)
        run = _gate_run(w, repo, pr, head, fresh=True) or run
    if not wait and run.get("status") != "completed":
        # it cannot be re-run yet; the new scan's completion re-runs it (workflow_run), after it finishes
        print(f"security refresh: Review Gate run {run['id']} for PR #{pr} is still running; the new scan re-runs it")
        return None
    try:
        w._gh(f"repos/{repo}/actions/runs/{run['id']}/rerun", "-X", "POST")
    except w.Ambiguous as exc:
        return f"its Review Gate run {run['id']} could not be re-run ({exc})"
    print(f"security refresh: re-ran Review Gate run {run['id']} for PR #{pr}")
    return None


def refresh(w):
    """The Security Refresh workflow: re-scan open PRs (push, schedule) or re-run a scanned PR's gate (workflow_run).

    Exit 1 after trying every PR when any could not be re-fired: its gate then stays as it was (stale scans
    already fail it); close and reopen that PR.
    """
    repo, ref, event = (os.environ.get(k, "") for k in ("REPO", "DEFAULT_BRANCH", "EVENT"))
    if not repo or not ref or not event:
        print("::error::security refresh: REPO, DEFAULT_BRANCH and EVENT are required", file=sys.stderr)
        return 2
    failed = []
    if event == "workflow_run":
        match = re.fullmatch(r"Security Scan - PR #([1-9][0-9]*) @ ([0-9a-f]{40})", os.environ.get("TITLE", ""))
        if not match:  # never echoed: a same-named workflow elsewhere can title its run with anything
            print("::warning::security refresh: the completed run is not a PR scan; nothing to re-run")
            return 0
        pr, head = match.groups()
        pull = w._api_json(f"repos/{repo}/pulls/{pr}")
        if pull.get("state") != "open" or w._text(pull, "head", "sha") != head:
            print(f"security refresh: PR #{pr} is closed or moved past {head[:12]}; its next scan re-runs the gate")
            return 0
        why = _rerun(w, repo, pr, head, wait=True)
        failed += [f"PR #{pr}: {why}"] if why else []
    else:
        for pull in _pages(w, f"repos/{repo}/pulls?state=open&per_page=100"):
            pr, head = str(pull["number"]), w._text(pull, "head", "sha")
            if pull.get("draft") is True:  # marking it ready re-scans it (the scan's ready_for_review trigger)
                print(f"security refresh: PR #{pr} is a draft; skipped")
                continue
            try:
                w._gh(f"repos/{repo}/actions/workflows/{TRUSTED[0].rsplit('/', 1)[1]}/dispatches", "-X", "POST",
                      "-f", f"ref={ref}", "-f", f"inputs[pr]={pr}", "-f", f"inputs[head]={head}")
                print(f"security refresh: dispatched Security Scan for PR #{pr} @ {head[:12]}")
            except w.Ambiguous as exc:
                failed.append(f"PR #{pr}: Security Scan could not be dispatched ({exc})")
                continue
            why = _rerun(w, repo, pr, head, wait=False)  # red now: the old scan is stale or the new one is queued
            failed += [f"PR #{pr}: {why}"] if why else []
    for line in failed:
        print(f"::error::security refresh: {line}; close and reopen that PR to re-scan it", file=sys.stderr)
    return 1 if failed else 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--policy-revision":  # the scan workflow's step: no gh, no helpers
        try:
            print(local_policy(sys.argv[2]))
            return 0
        except (OSError, ValueError, subprocess.CalledProcessError):
            print("::error::security lane: could not compute the policy revision of that checkout", file=sys.stderr)
            return 2
    try:
        w = _load("check_forged_review_gate", "check-forged-review-gate.py")
        detector = _load("check_forged_gate_names", "check-forged-gate-names.py")
    except (OSError, ImportError, SyntaxError) as exc:
        print(f"::error::security lane: could not load its helpers, failing closed: {exc}", file=sys.stderr)
        return 2
    if sys.argv[1:] == ["--refresh"]:
        try:
            return refresh(w)
        except (ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError, w.Ambiguous) as exc:
            print(f"::error::security refresh: could not finish, failing closed: {exc}", file=sys.stderr)
            return 2
    if sys.argv[1:]:
        print("::error::security lane: unknown arguments", file=sys.stderr)
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
        now = now_utc()
        workflows = _entries(w, repo, ".github/workflows", ref)
        active = "review-gate-security-scan.yml" in workflows  # (f) default branch only
        why = (_gate_file(w, repo, ref, workflows) or verdict(w, detector, repo, pr, pull, head, ref, workflows, now)
               if active else None)
    except (ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError, w.Ambiguous) as exc:
        print(f"::error::security lane: could not evaluate, failing closed: {exc}", file=sys.stderr)
        return 2
    if not active:
        if claimed:
            print(f"::error::security lane: the PR body claims a scanner pass ({claimed[0]!r}) but {ref} has no "
                  f"Security Scan workflow, so nothing verifies it; remove the claim ({REWORD})", file=sys.stderr)
            return 1
        print("security lane not enabled (no .github/workflows/review-gate-security-scan.yml on the default branch)")
        return 0
    if why:
        print(f"::error::security lane: {why}", file=sys.stderr)
        if claimed:
            print(f"::error::security lane: the PR body claims a scanner pass ({claimed[0]!r}) that the verified "
                  f"Security Scan does not show ({REWORD})", file=sys.stderr)
        return 1
    print("security lane ok: a fresh trusted Security Scan of the PR head passed with the default branch's config and policy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
