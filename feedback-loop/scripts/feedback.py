#!/usr/bin/env python3
"""Local feedback store for skills, agents, hooks, plugins, AEC and the dev process.

Layout under $AGENT_FEEDBACK_HOME (default ~/.agent-feedback):
  config.json                              {"enabled": true, "opt_out": ["skill:foo"]}
  subjects/<kind>/<name>/entries.jsonl     append-only, one JSON entry per line
  subjects/<kind>/<name>/state.json        {"last_review", "reviewed_count", "source_repo", "resolutions"}

Stdlib only. Subjects are written `kind:name` (e.g. `skill:orchata`, `hook:typecheck-on-edit/post-edit`,
`process:my-project`). Run `feedback.py <command> -h` for each command's options.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # shortcut: no file locks on Windows; appends stay atomic, state edits can race. Add msvcrt locking if Windows users report it.
    fcntl = None

KINDS = ("skill", "agent", "hook", "plugin", "aec", "process")
SEVERITIES = ("high", "medium", "low")
STATUSES = ("folded", "merged", "not-a-problem", "deferred")
CLOSED = {"folded", "merged", "not-a-problem"}
REPORTERS = ("agent", "cli", "hook", "human")
AREAS = ("dev", "test", "ci", "plan", "review", "deploy")
SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# Refuse obvious credentials; summaries stay local but get pasted into PRs and issues at review.
SECRET = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|sk_(live|test)_[A-Za-z0-9]{8,}|rk_live_[A-Za-z0-9]{8,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16}|SG\.[A-Za-z0-9_-]{16,}\.|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


class UsageError(Exception):
    pass


def home() -> Path:
    return Path(os.environ.get("AGENT_FEEDBACK_HOME") or Path.home() / ".agent-feedback")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_subject(text: str) -> tuple[str, str]:
    kind, sep, name = text.partition(":")
    if not sep or kind not in KINDS:
        raise UsageError(f"subject must be kind:name with kind in {', '.join(KINDS)}; got {text!r}")
    parts = name.split("/")
    if not name or any(p in ("", ".", "..") or not SEGMENT.match(p) for p in parts):
        raise UsageError(f"invalid subject name {name!r}: use letters, digits, . _ - and / between segments")
    return kind, name


def subject_dir(kind: str, name: str) -> Path:
    return home() / "subjects" / kind / name


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


@contextmanager
def locked(path: Path):
    """Hold an exclusive lock on `path` for a whole read-modify-write of state or config."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)  # closing releases the lock


def config_lock() -> Path:
    return home() / ".config.lock"


def state_lock(kind: str, name: str) -> Path:
    return subject_dir(kind, name) / ".state.lock"


def load_config() -> dict:
    cfg = read_json(home() / "config.json", {})
    return {"enabled": cfg.get("enabled", True), "opt_out": list(cfg.get("opt_out", []))}


def load_state(kind: str, name: str) -> dict:
    st = read_json(subject_dir(kind, name) / "state.json", {})
    return {"last_review": st.get("last_review"), "reviewed_count": st.get("reviewed_count", 0),
            "source_repo": st.get("source_repo"), "resolutions": st.get("resolutions", {})}


def load_entries(kind: str, name: str) -> list[dict]:
    path = subject_dir(kind, name) / "entries.jsonl"
    if not path.exists():
        return []
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"feedback: skipping unreadable line {n} in {path}", file=sys.stderr)
    return out


def new_id() -> str:
    """Live entries get a random id: two identical summaries in the same second stay separate."""
    return secrets.token_hex(6)


def import_id(ts: str, kind: str, name: str, summary: str) -> str:
    """Imported entries get a content id, so importing the same register twice adds nothing."""
    return hashlib.sha256(f"{ts}\n{kind}\n{name}\n{summary}".encode()).hexdigest()[:12]


def append_entry(kind: str, name: str, entry: dict) -> None:
    path = subject_dir(kind, name) / "entries.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, line)
    finally:
        os.close(fd)  # closing releases the lock


def is_open(entry: dict, resolutions: dict) -> bool:
    return resolutions.get(entry["id"], {}).get("status") not in CLOSED


def since_review(entries: list[dict], state: dict) -> list[dict]:
    """Open entries after the last review's mark: the entries file is append-only, so a count is exact."""
    res = state["resolutions"]
    return [e for e in entries[state["reviewed_count"]:] if is_open(e, res)]


def threshold(entries: list[dict]) -> str | None:
    sev = Counter(e["severity"] for e in entries)
    if sev["high"]:
        return f"{sev['high']} high"
    if sev["medium"] >= 3:
        return f"{sev['medium']} medium"
    if len(entries) >= 5:
        return f"{len(entries)} total"
    return None


def all_subjects() -> list[tuple[str, str]]:
    root = home() / "subjects"
    found = []
    for path in sorted(root.glob("*/**/entries.jsonl")):
        rel = path.parent.relative_to(root).parts
        if rel[0] in KINDS and len(rel) > 1:
            found.append((rel[0], "/".join(rel[1:])))
    return found


def summarize(kind: str, name: str) -> dict:
    entries = load_entries(kind, name)
    state = load_state(kind, name)
    fresh = since_review(entries, state)
    return {
        "subject": f"{kind}:{name}",
        "total": len(entries),
        "open": sum(is_open(e, state["resolutions"]) for e in entries),
        "since_review": len(fresh),
        "last_review": state["last_review"],
        "source_repo": state["source_repo"],
        "due": threshold(fresh),
    }


# --- commands -----------------------------------------------------------------------------

def cmd_log(a) -> int:
    kind, name = parse_subject(a.subject)
    cfg = load_config()
    if not cfg["enabled"] or f"{kind}:{name}" in cfg["opt_out"]:
        return 0  # disabled is a quiet no-op: logging must never break the calling item
    summary = " ".join(a.summary.split())
    if not summary:
        raise UsageError("--summary is empty")
    for text in (summary, a.suggestion or ""):
        if SECRET.search(text):
            raise UsageError("refusing to store text that looks like a credential; describe it without the value")
    if a.area and kind != "process":
        raise UsageError("--area applies to process subjects only")
    ts = now_iso()
    entry = {"id": new_id(), "ts": ts, "kind": kind, "name": name,
             "severity": a.severity, "summary": summary, "reporter": a.reporter}
    for field in ("suggestion", "phase", "area", "project"):
        value = getattr(a, field)
        if value:
            entry[field] = " ".join(value.split())
    append_entry(kind, name, entry)
    if not a.quiet:
        print(entry["id"])
    return 0


def cmd_status(a) -> int:
    subjects = [parse_subject(a.subject)] if a.subject else all_subjects()
    rows = [summarize(k, n) for k, n in subjects]
    if a.kind:
        rows = [r for r in rows if r["subject"].startswith(a.kind + ":")]
    if a.due:
        rows = [r for r in rows if r["due"]]
    if a.json:
        print(json.dumps({"enabled": load_config()["enabled"], "subjects": rows}, indent=2))
        return 0
    if not load_config()["enabled"]:
        print("feedback logging is disabled (feedback.py config --enable to turn it on)")
    if not rows:
        print("no feedback recorded" + (" past its review threshold" if a.due else ""))
    for r in rows:
        flag = f"  REVIEW ({r['due']})" if r["due"] else ""
        print(f"{r['subject']}: {r['open']} open, {r['since_review']} since last review "
              f"({r['last_review'] or 'never'}){flag}")
    return 0


def cmd_review(a) -> int:
    kind, name = parse_subject(a.subject)
    entries = load_entries(kind, name)
    state = load_state(kind, name)
    shown = [e for e in entries if is_open(e, state["resolutions"])] if a.all else since_review(entries, state)
    order = {s: i for i, s in enumerate(SEVERITIES)}
    shown.sort(key=lambda e: (order[e["severity"]], e["ts"]))
    data = {"subject": f"{kind}:{name}", "last_review": state["last_review"], "through": len(entries),
            "source_repo": state["source_repo"], "due": threshold(since_review(entries, state)),
            "entries": [{**e, "resolution": state["resolutions"].get(e["id"])} for e in shown]}
    if a.json:
        print(json.dumps(data, indent=2))
        return 0
    print(f"{kind} {name}: {len(shown)} open entries"
          f"{' since ' + state['last_review'] if state['last_review'] and not a.all else ''}"
          f"{' (threshold hit: ' + data['due'] + ')' if data['due'] else ''}")
    for e in data["entries"]:
        where = " ".join(f"{k}={e[k]}" for k in ("area", "phase", "project") if e.get(k))
        fix = f" -> {e['suggestion']}" if e.get("suggestion") else ""
        mark = f" [{e['resolution']['status']}]" if e["resolution"] else ""
        print(f"- {e['id']} [{e['severity']}] {e['ts'][:10]} {where + ' ' if where else ''}{e['summary']}{fix}{mark}")
    print(f"when done: feedback.py mark-reviewed {kind}:{name} --through {len(entries)}")
    return 0


def cmd_resolve(a) -> int:
    kind, name = parse_subject(a.subject)
    known = {e["id"] for e in load_entries(kind, name)}
    missing = [i for i in a.ids if i not in known]
    if missing:
        raise UsageError(f"unknown entry id(s) for {kind}:{name}: {', '.join(missing)}")
    with locked(state_lock(kind, name)):
        state = load_state(kind, name)
        for i in a.ids:
            state["resolutions"][i] = {"status": a.status, "date": today(), **({"pr": a.pr} if a.pr else {})}
        write_json(subject_dir(kind, name) / "state.json", state)
    print(f"{len(a.ids)} entr{'y' if len(a.ids) == 1 else 'ies'} marked {a.status}")
    return 0


def cmd_mark_reviewed(a) -> int:
    kind, name = parse_subject(a.subject)
    count = len(load_entries(kind, name))
    through = count if a.through is None else a.through
    if not 0 <= through <= count:
        raise UsageError(f"--through must be between 0 and {count} (the review's `through` value)")
    with locked(state_lock(kind, name)):
        state = load_state(kind, name)
        state["last_review"] = now_iso()
        state["reviewed_count"] = max(state["reviewed_count"], through)
        if a.source_repo:
            state["source_repo"] = a.source_repo
        write_json(subject_dir(kind, name) / "state.json", state)
    print(f"{kind}:{name} reviewed {state['last_review']} ({count - state['reviewed_count']} newer entries stay pending)")
    return 0


def cmd_report(a) -> int:
    subjects = [parse_subject(a.subject)] if a.subject else all_subjects()
    if a.kind:
        subjects = [s for s in subjects if s[0] == a.kind]
    out = []
    for kind, name in subjects:
        entries = load_entries(kind, name)
        res = load_state(kind, name)["resolutions"]
        if a.since:
            entries = [e for e in entries if e["ts"][: len(a.since)] >= a.since]
        status = Counter(res.get(e["id"], {}).get("status", "open") for e in entries)
        out.append({
            "subject": f"{kind}:{name}", "entries": len(entries),
            "by_status": dict(status),
            "by_severity": dict(Counter(e["severity"] for e in entries)),
            "by_area": dict(Counter(e.get("area", "-") for e in entries)) if kind == "process" else None,
            "by_phase": dict(Counter(e["phase"] for e in entries if e.get("phase"))),
            "by_month": dict(sorted(Counter(e["ts"][:7] for e in entries).items())),
        })
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    if not out:
        print("no feedback recorded")
    for r in out:
        print(f"{r['subject']}: {r['entries']} entries")
        for key in ("by_status", "by_severity", "by_area", "by_phase", "by_month"):
            if r[key]:
                print(f"  {key[3:]}: " + ", ".join(f"{k} {v}" for k, v in r[key].items()))
    return 0


def cmd_config(a) -> int:
    path = home() / "config.json"
    opt_out = [":".join(parse_subject(s)) for s in a.opt_out or []]
    opt_in = [":".join(parse_subject(s)) for s in a.opt_in or []]
    with locked(config_lock()):
        cfg = load_config()
        if a.enable or a.disable:
            cfg["enabled"] = bool(a.enable)
        cfg["opt_out"] += [s for s in opt_out if s not in cfg["opt_out"]]
        cfg["opt_out"] = [s for s in cfg["opt_out"] if s not in opt_in]
        if a.enable or a.disable or opt_out or opt_in or not path.exists():
            write_json(path, cfg)
    print(json.dumps(cfg, indent=2) if a.json else
          f"enabled: {cfg['enabled']}\nopt_out: {', '.join(cfg['opt_out']) or '(none)'}\nstore: {home()}")
    return 0


def cmd_import_orchata(a) -> int:
    src = Path(a.path).expanduser()
    if not src.exists():
        print(f"nothing to import: {src} does not exist")
        return 0
    old = json.loads(src.read_text(encoding="utf-8"))
    kind, name = "skill", "orchata"
    with locked(state_lock(kind, name)):
        added = _import_orchata_locked(old, kind, name)
    if old.get("opt_out"):
        with locked(config_lock()):
            cfg = load_config()
            if "skill:orchata" not in cfg["opt_out"]:
                cfg["opt_out"].append("skill:orchata")
                write_json(home() / "config.json", cfg)
    migrated = src.with_name(src.name + ".migrated")
    os.replace(src, migrated)
    print(f"imported {added} orchata entries; old register kept at {migrated}")
    return 0


def _import_orchata_locked(old: dict, kind: str, name: str) -> int:
    existing = load_entries(kind, name)
    have = {e["id"] for e in existing}
    state = load_state(kind, name)
    last = old.get("last_review")
    reviewed = 0  # imported entries dated on or before the old register's last review
    added = 0
    for item in sorted(old.get("entries", []), key=lambda i: i.get("date") or ""):
        summary = " ".join((item.get("summary") or item.get("what_happened") or "").split())
        if not summary:
            continue
        ts = f"{item.get('date') or today()}T00:00:00Z"
        entry = {"id": import_id(ts, kind, name, summary), "ts": ts, "kind": kind, "name": name,
                 "severity": item.get("severity") or item.get("level") or "low",
                 "summary": summary, "reporter": "agent"}
        if entry["severity"] not in SEVERITIES:
            entry["severity"] = "low"
        for field in ("suggestion", "phase", "project"):
            if item.get(field):
                entry[field] = item[field]
        if item.get("pr"):
            state["resolutions"].setdefault(entry["id"], {"status": "folded", "pr": item["pr"], "date": today()})
        if entry["id"] not in have:
            append_entry(kind, name, entry)
            have.add(entry["id"])
            added += 1
            reviewed += bool(last and ts[: len(last)] <= last)
    if not existing and not state["reviewed_count"]:
        # Sorted by date, so the reviewed entries are exactly the first `reviewed` lines.
        state["reviewed_count"] = reviewed
    state["last_review"] = state["last_review"] or last
    state["source_repo"] = state["source_repo"] or old.get("source_repo")
    write_json(subject_dir(kind, name) / "state.json", state)
    return added


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="feedback.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("log", help="append one feedback entry (no-op when disabled or opted out)")
    s.add_argument("subject", help="kind:name, e.g. skill:orchata or process:my-project")
    s.add_argument("--severity", required=True, choices=SEVERITIES)
    s.add_argument("--summary", required=True, help="what happened, one line, no secrets")
    s.add_argument("--suggestion", help="the concrete fix to the subject")
    s.add_argument("--phase", help="which part of the subject was at fault")
    s.add_argument("--area", choices=AREAS, help="process subjects: which part of the work")
    s.add_argument("--project", help="repo name the friction happened in")
    s.add_argument("--reporter", choices=REPORTERS, default="agent")
    s.add_argument("--quiet", action="store_true", help="do not print the new entry id")
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser("status", help="counts per subject and which are due for review")
    s.add_argument("subject", nargs="?")
    s.add_argument("--kind", choices=KINDS)
    s.add_argument("--due", action="store_true", help="only subjects past their review threshold")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("review", help="list a subject's open entries since its last review")
    s.add_argument("subject")
    s.add_argument("--all", action="store_true", help="every open entry, not only those since last review")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("resolve", help="record what happened to entries")
    s.add_argument("subject")
    s.add_argument("ids", nargs="+")
    s.add_argument("--status", required=True, choices=STATUSES)
    s.add_argument("--pr", help="PR or issue URL carrying the fix")
    s.set_defaults(fn=cmd_resolve)

    s = sub.add_parser("mark-reviewed", help="close a review: entries up to its mark stop counting")
    s.add_argument("subject")
    s.add_argument("--through", type=int, help="the `through` value `review` printed; entries logged "
                   "after it stay pending (default: everything logged so far)")
    s.add_argument("--source-repo", help="cache where the subject's source lives")
    s.set_defaults(fn=cmd_mark_reviewed)

    s = sub.add_parser("report", help="trends by status, severity, area, phase and month")
    s.add_argument("subject", nargs="?")
    s.add_argument("--kind", choices=KINDS)
    s.add_argument("--since", help="YYYY-MM or YYYY-MM-DD")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("config", help="show or change the global switch and opt-outs")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--enable", action="store_true")
    g.add_argument("--disable", action="store_true")
    s.add_argument("--opt-out", action="append", metavar="KIND:NAME")
    s.add_argument("--opt-in", action="append", metavar="KIND:NAME")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_config)

    s = sub.add_parser("import-orchata", help="migrate orchata's pre-2.0 friction register")
    s.add_argument("--path", default="~/.claude/orchata/friction.json")
    s.set_defaults(fn=cmd_import_orchata)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except UsageError as e:
        print(f"feedback: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
