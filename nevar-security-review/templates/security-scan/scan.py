#!/usr/bin/env python3
"""Security Scan driver: gitleaks, osv-scanner, zizmor and semgrep over a PR's changed files.

Installed as `.github/security-scan/scan.py` and run by
`.github/workflows/review-gate-security-scan.yml` from a checkout of the DEFAULT branch, so
this file, its scanner configs and `exceptions.json` are part of the config tree whose git
sha the review-gate security lane checks. The PR head is checked out as data only: its
changed files are copied into a staging dir and scanned there. Nothing from the head is
executed, imported or used as scanner configuration; author-side scanner configs and ignore
files are renamed in the staging copy, so they are scanned as data but never loaded.

It prints exactly one annotation the lane reads:
    ::notice title=security-scan::outcome=<passed|not-applicable|findings|scanner-error> config-tree=<sha>
and wraps everything else it prints (file names and rule ids come from the PR) in
::stop-commands:: so PR content cannot emit a second one. Exit 0 for passed and
not-applicable, 1 otherwise, so the job conclusion matches the outcome.

Environment (set by the workflow): GITHUB_TOKEN, REPO, PR_NUMBER, HEAD_SHA, BASE_DIR,
HEAD_DIR, WORK_DIR, BIN_DIR, SEMGREP_IMAGE (or SEMGREP_BIN for a local run),
GITHUB_STEP_SUMMARY (optional).
"""
import datetime as dt
import fnmatch
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path, PurePosixPath

CONFIG_REL = ".github/security-scan"
SCANNERS = ("gitleaks", "osv-scanner", "zizmor", "semgrep")
TIMEOUT = 600  # seconds per scanner; a timeout is a scanner-error
MAX_PR_FILES = 3000  # the pulls files API stops listing here; a capped list is a scanner-error
# Author-side configs and ignore files a scanner would load from the scanned tree. They are
# renamed in staging (and still scanned as data); findings map back to the real path.
AUTHOR_CONFIGS = {
    ".gitleaksignore", ".gitleaks.toml", "gitleaks.toml", ".semgrepignore", ".semgrep.yml",
    ".semgrep.yaml", "osv-scanner.toml", "zizmor.yml", "zizmor.yaml", ".gitignore",
}
RENAMED = ".author-copy"
LOCKFILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock",
    "poetry.lock", "Pipfile.lock", "uv.lock", "pdm.lock", "Cargo.lock",
    "go.mod", "Gemfile.lock", "composer.lock", "pubspec.lock", "mix.lock", "gradle.lockfile",
    "packages.lock.json", "renv.lock",
}
# Only the languages semgrep.yml has rules for: semgrep skips any other target, which reads as target-skipped.
CODE_EXT = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
# pip's join_lines: a backslash-ended line continues on the next, unless the line is a comment.
COMMENT_LINE = re.compile(r"\s*#")
OUTCOMES = ("passed", "not-applicable", "findings", "scanner-error")


class ScanError(Exception):
    """A scanner or input failure: the outcome is scanner-error, never a silent pass."""


# ---------------------------------------------------------------- changed files and staging

def safe_rel(name):
    """A PR file name as a relative POSIX path, or None when it could escape the staging dir."""
    if not name or "\x00" in name or name.startswith("/") or "\\" in name:
        return None
    parts = PurePosixPath(name).parts
    if any(p in ("", ".", "..") for p in parts) or parts[0] == ".git":
        return None
    return PurePosixPath(*parts).as_posix()


def list_changed(api, repo, pr, head_sha):
    """Changed paths (not removed) of PR `pr` at `head_sha`, via the pulls files API."""
    files, page = [], 1
    while True:
        batch = api(f"/repos/{repo}/pulls/{pr}/files?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ScanError("pulls files API returned a non-list")
        files += batch
        if len(batch) < 100:
            break
        page += 1
    if len(files) >= MAX_PR_FILES:
        raise ScanError(f"PR lists {len(files)} files, the API cap; not every file can be scanned")
    now = api(f"/repos/{repo}/pulls/{pr}").get("head", {}).get("sha")
    if now != head_sha:
        raise ScanError(f"PR head moved to {now} while listing files for {head_sha}; re-run")
    out = []
    for f in files:
        if f.get("status") == "removed":
            continue
        rel = safe_rel(f.get("filename"))
        if rel is None:
            raise ScanError(f"unsafe file name in PR: {f.get('filename')!r}")
        out.append(rel)
    return sorted(set(out))


def stage(head_dir, rels, stage_dir):
    """Copy each changed regular file from the head checkout into stage_dir.

    Returns (staged paths, notes). Symlinks and non-regular files are not copied (a scanner
    would follow them out of the PR); each one is a note in the job summary.
    """
    head = Path(head_dir).resolve()
    staged, notes = [], []
    # The suffix is reserved, so a renamed file never lands on another PR file and real_path's
    # strip only ever undoes a rename (else a sibling could inherit an exact-path exception).
    reserved = [rel for rel in rels if rel.endswith(RENAMED)]
    if reserved:
        raise ScanError(f"{reserved[0]!r} ends with {RENAMED}, a suffix the scan reserves; rename the file")
    for rel in rels:
        src = head / rel
        try:
            mode = os.lstat(src).st_mode
        except FileNotFoundError:
            notes.append(f"{rel}: listed by the API but absent at the head checkout")
            continue
        # realpath differs from the literal path when any component is a symlink
        if not stat.S_ISREG(mode) or os.path.realpath(src) != str(src):
            notes.append(f"{rel}: symlink or not a regular file, not scanned")
            continue
        name = PurePosixPath(rel).name
        dest_rel = rel + RENAMED if name in AUTHOR_CONFIGS else rel
        dest = Path(stage_dir) / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest, follow_symlinks=False)
        staged.append(rel)
    return staged, notes


def real_path(p, stage_dir):
    """A scanner-reported path, relative to staging, with an author-config rename undone (stage reserves the suffix)."""
    p = str(p)
    root = str(Path(stage_dir).resolve())
    for prefix in (root + "/", str(stage_dir).rstrip("/") + "/", "/src/"):
        if p.startswith(prefix):
            p = p[len(prefix):]
            break
    if p.startswith("./"):
        p = p[2:]
    return p[: -len(RENAMED)] if p.endswith(RENAMED) else p


# ---------------------------------------------------------------- scanners

def run(argv, cwd=None, ok=(0,)):
    """Run one scanner with a minimal env; returns (exit code, stdout). Raises ScanError."""
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": os.environ.get("WORK_DIR", "/tmp")}
    try:
        p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                           timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        raise ScanError(f"{Path(argv[0]).name} timed out after {TIMEOUT}s") from None
    except OSError as e:
        raise ScanError(f"{argv[0]} could not start: {e}") from None
    if p.returncode not in ok:
        raise ScanError(f"{Path(argv[0]).name} exited {p.returncode}: {p.stderr.strip()[-500:]}")
    return p.returncode, p.stdout


def is_requirements(p):
    """A name osv-scanner 2.7.0 reads as a pip requirements file (case-sensitive), e.g. requirements-dev.txt."""
    name = PurePosixPath(p).name
    return name.endswith(".txt") and "requirements" in name


def has_include(text):
    """True when a requirements file includes another (-r, -c, a --requirement/--constraint prefix).

    shortcut: includes are not resolved (plans/2026-11-22-security-scan-osv-include-resolution.md),
    so the scan cannot prove an including file was read completely and reports it as not-covered.
    """
    logical, cur = [], ""
    for line in text.lstrip("\ufeff").splitlines():
        if line.endswith("\\") and not COMMENT_LINE.match(line):
            cur += line[:-1]
            continue
        logical.append(cur + line)
        cur = ""
    for line in logical + [cur]:
        tok = (line.split() or [""])[0].split("=", 1)[0]
        # optparse takes a glued short value (-rbase.txt) and any unambiguous long-option prefix
        if tok[:2] in ("-r", "-c") or (len(tok) > 2 and tok.startswith("--") and (
                "--requirement".startswith(tok) or "--constraint".startswith(tok))):
            return True
    return False


def applicable(scanner, staged):
    """The staged paths a scanner applies to; empty means not-applicable for that scanner."""
    if scanner == "gitleaks":
        return list(staged)  # secrets in docs are still secrets
    if scanner == "osv-scanner":
        return [p for p in staged if PurePosixPath(p).name in LOCKFILES or is_requirements(p)]
    if scanner == "zizmor":
        return [p for p in staged
                if fnmatch.fnmatch(p, ".github/workflows/*.y*ml")
                or PurePosixPath(p).name in ("action.yml", "action.yaml")
                or p in (".github/dependabot.yml", ".github/dependabot.yaml")]
    if scanner == "semgrep":
        return [p for p in staged if PurePosixPath(p).suffix in CODE_EXT]
    raise ValueError(scanner)


def parse_gitleaks(report, stage_dir):
    return [{"scanner": "gitleaks", "rule": f["RuleID"], "path": real_path(f["File"], stage_dir)}
            for f in report]


def parse_osv(report, stage_dir):
    out = []
    for r in report.get("results", []):
        path = real_path(r.get("source", {}).get("path", ""), stage_dir)
        for p in r.get("packages", []):
            for v in p.get("vulnerabilities", []):
                out.append({"scanner": "osv-scanner", "rule": v["id"], "path": path})
    return out


def parse_zizmor(report, stage_dir):
    return [{"scanner": "zizmor", "rule": f["ident"],
             "path": real_path(f["locations"][0]["symbolic"]["key"]["Local"]["verbatim_path"], stage_dir)}
            for f in report]


def parse_semgrep(report, stage_dir, targets):
    """Findings; a target semgrep could not parse or skipped is a finding too (fail closed)."""
    # check_id is prefixed with the config file's path; the rule id is the last segment
    out = [{"scanner": "semgrep", "rule": r["check_id"].rsplit(".", 1)[-1],
            "path": real_path(r["path"], stage_dir)}
           for r in report.get("results", [])]
    for e in report.get("errors", []):
        if not e.get("path"):
            raise ScanError(f"semgrep error: {e.get('type')} {e.get('message', '')[:300]}")
        out.append({"scanner": "semgrep", "rule": "target-error",
                    "path": real_path(e["path"], stage_dir)})
    scanned = {real_path(p, stage_dir) for p in report.get("paths", {}).get("scanned", [])}
    errored = {f["path"] for f in out if f["rule"] == "target-error"}
    for t in targets:
        if real_path(t, stage_dir) not in scanned | errored:
            out.append({"scanner": "semgrep", "rule": "target-skipped", "path": real_path(t, stage_dir)})
    return out


def scan_one(scanner, targets, cfg, stage_dir, work):
    """Run one scanner on its targets (paths relative to stage_dir); returns findings."""
    bin_dir = Path(os.environ.get("BIN_DIR", work / "bin"))
    if scanner == "gitleaks":
        report, empty = work / "gitleaks.json", work / "no-gitleaksignore"
        empty.mkdir(exist_ok=True)
        run([str(bin_dir / "gitleaks"), "dir", str(stage_dir), "--config", str(cfg / "gitleaks.toml"),
             "--gitleaks-ignore-path", str(empty), "--ignore-gitleaks-allow", "--no-banner",
             "--redact", "--report-format", "json", "--report-path", str(report), "--exit-code", "1"],
            ok=(0, 1))
        return parse_gitleaks(json.loads(report.read_text() or "[]"), stage_dir)
    if scanner == "osv-scanner":
        # --all-packages: without it a lockfile with no vulnerabilities has no result entry at all
        argv = [str(bin_dir / "osv-scanner"), "scan", "source", "--config", str(cfg / "osv-scanner.toml"),
                "--all-packages", "--format", "json"]
        for t in targets:
            argv += ["-L", str(Path(stage_dir) / t)]
        code, out = run(argv, ok=(0, 1, 128))
        report = json.loads(out) if code != 128 else {}  # 128: no input yielded a package
        read = {real_path(r.get("source", {}).get("path", ""), stage_dir)
                for r in report.get("results", []) if r.get("packages")}
        # Each input must yield packages: one OSV could not read (a missing include, a broken file)
        # exits 0 when another input in the same run had packages, so per-input is the only check.
        return parse_osv(report, stage_dir) + [
            {"scanner": "osv-scanner", "rule": "no-packages", "path": t} for t in targets if t not in read] + [
            {"scanner": "osv-scanner", "rule": "not-covered", "path": t} for t in targets
            if is_requirements(t) and has_include((Path(stage_dir) / t).read_text(errors="replace"))]
    if scanner == "zizmor":
        _, out = run([str(bin_dir / "zizmor"), "--no-config", "--no-ignores", "--strict-collection",
                      "--no-exit-codes", "--offline", "--min-severity", "low", "--format", "json",
                      *targets], cwd=stage_dir)
        return parse_zizmor(json.loads(out), stage_dir)
    if scanner == "semgrep":
        flags = ["scan", "--config", "/cfg/semgrep.yml", "--metrics=off", "--disable-nosem",
                 "--json", "--quiet", "--max-target-bytes", "0"]
        image = os.environ.get("SEMGREP_IMAGE")
        if image:
            argv = ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp",
                    "-e", "HOME=/tmp", "-v", f"{Path(stage_dir).resolve()}:/src:ro",
                    "-v", f"{cfg.resolve()}:/cfg:ro", "-w", "/src", image, "semgrep", *flags, *targets]
            _, out = run(argv)
        else:  # local run: SEMGREP_BIN, config read from the real path
            flags[2] = str(cfg / "semgrep.yml")
            _, out = run([os.environ["SEMGREP_BIN"], *flags, *targets], cwd=stage_dir)
        return parse_semgrep(json.loads(out), stage_dir, targets)
    raise ValueError(scanner)


# ---------------------------------------------------------------- exceptions and outcome

def load_exceptions(path, today):
    """Validated exceptions: (active, expired). A malformed file is a ScanError."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise ScanError(f"exceptions.json unreadable: {e}") from None
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("exceptions"), list):
        raise ScanError('exceptions.json must be {"version": 1, "exceptions": [...]}')
    active, expired = [], []
    for i, e in enumerate(data["exceptions"]):
        keys = ("scanner", "rule", "path", "owner", "expires", "reason")
        if not isinstance(e, dict) or set(e) != set(keys) or not all(
                isinstance(e[k], str) and e[k].strip() for k in keys):
            raise ScanError(f"exceptions[{i}] needs exactly {', '.join(keys)} as non-empty strings")
        if e["scanner"] not in SCANNERS:
            raise ScanError(f"exceptions[{i}].scanner {e['scanner']!r} is not one of {SCANNERS}")
        try:
            expires = dt.date.fromisoformat(e["expires"])
        except ValueError:
            raise ScanError(f"exceptions[{i}].expires must be YYYY-MM-DD") from None
        (active if expires >= today else expired).append(e)
    return active, expired


def apply_exceptions(findings, active):
    """(kept, excepted). An exception matches scanner, rule and path exactly."""
    key = {(e["scanner"], e["rule"], e["path"]) for e in active}
    kept = [f for f in findings if (f["scanner"], f["rule"], f["path"]) not in key]
    return kept, [f for f in findings if f not in kept]


def outcome(results):
    """Overall outcome from per-scanner results {scanner: status}."""
    statuses = set(results.values())
    if "scanner-error" in statuses:
        return "scanner-error"
    if "findings" in statuses:
        return "findings"
    return "passed" if "passed" in statuses else "not-applicable"


def notice(result, tree):
    assert result in OUTCOMES and len(tree) == 40, (result, tree)
    return f"::notice title=security-scan::outcome={result} config-tree={tree}"


def config_tree(base_dir):
    p = subprocess.run(["git", "-C", str(base_dir), "rev-parse", f"HEAD:{CONFIG_REL}"],
                       capture_output=True, text=True, check=False)
    sha = p.stdout.strip()
    if p.returncode or len(sha) != 40:
        raise ScanError(f"cannot read the {CONFIG_REL} tree sha: {p.stderr.strip()}")
    return sha


# ---------------------------------------------------------------- main

def github_api(token):
    def api(path):
        req = urllib.request.Request("https://api.github.com" + path, headers={
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    return api


def scan(staged, cfg, stage_dir, work, today):
    """Per-scanner results, findings and summary lines for the staged paths."""
    active, expired = load_exceptions(cfg / "exceptions.json", today)
    results, findings, lines = {}, [], []
    for scanner in SCANNERS:
        targets = applicable(scanner, staged)
        if not targets:
            results[scanner] = "not-applicable"
            lines.append(f"- {scanner}: not-applicable (no matching changed files)")
            continue
        try:
            found = scan_one(scanner, targets, cfg, stage_dir, work)  # no target is an AUTHOR_CONFIGS name
        except (ScanError, KeyError, ValueError, TypeError) as e:
            results[scanner] = "scanner-error"
            lines.append(f"- {scanner}: scanner-error: {e}")
            continue
        kept, excepted = apply_exceptions(found, active)
        results[scanner] = "findings" if kept else "passed"
        lines.append(f"- {scanner}: {results[scanner]} on {len(targets)} file(s), "
                     f"{len(kept)} finding(s), {len(excepted)} excepted")
        findings += kept
    for e in expired:
        lines.append(f"- expired exception (no longer applied): {e['scanner']} {e['rule']} "
                     f"{e['path']}, owner {e['owner']}, expired {e['expires']}")
    return results, findings, lines


def main():
    env = os.environ
    work = Path(env["WORK_DIR"])
    base, head, stage_dir = Path(env["BASE_DIR"]), Path(env["HEAD_DIR"]), work / "stage"
    cfg = base / CONFIG_REL
    tree = config_tree(base)  # no tree, no notice: the lane then fails closed on a missing annotation
    token = secrets.token_hex(16)
    print(f"::stop-commands::{token}", flush=True)
    try:
        stage_dir.mkdir(parents=True, exist_ok=False)
        rels = list_changed(github_api(env["GITHUB_TOKEN"]), env["REPO"], env["PR_NUMBER"], env["HEAD_SHA"])
        staged, notes = stage(head, rels, stage_dir)
        results, findings, lines = scan(staged, cfg, stage_dir, work, dt.datetime.now(dt.timezone.utc).date())
        lines += [f"- note: {n}" for n in notes]
        result = outcome(results)
    except (ScanError, OSError, ValueError, KeyError) as e:
        result, findings, lines = "scanner-error", [], [f"- scanner-error: {e}"]
    report = [f"## Security Scan: {result}", "", f"Config tree `{tree}`", "", *lines]
    if findings:
        report += ["", "| scanner | rule | path |", "|---|---|---|"]
        report += [f"| {f['scanner']} | {f['rule']} | {f['path']!r} |" for f in findings]
    print("\n".join(report), flush=True)
    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as s:
            s.write("\n".join(report) + "\n")
    print(f"::{token}::", flush=True)
    print(notice(result, tree), flush=True)
    return 0 if result in ("passed", "not-applicable") else 1


if __name__ == "__main__":
    sys.exit(main())
