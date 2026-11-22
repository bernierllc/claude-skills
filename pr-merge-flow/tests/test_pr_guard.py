"""Run: python3 pr-merge-flow/tests/test_pr_guard.py  (no framework; exits non-zero on failure)."""
import base64
import importlib.util
from pathlib import Path
from urllib.parse import quote

spec = importlib.util.spec_from_file_location("g", Path(__file__).parent.parent / "scripts" / "pr-guard.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

calls = lambda c: list(g.sync_calls(c, "/r"))

# What agents actually ran on 2026-09-28 (email_demo #516/#518 rebuilt twice for nothing).
assert calls('for w in a b; do git -C .worktrees/$w merge -q --no-edit origin/staging; done') == \
    [(".worktrees/$w", "merge", ["origin/staging"])]
assert calls("cd /x/wt && git fetch -q origin staging && git merge origin/staging --no-edit") == \
    [("/x/wt", "merge", ["origin/staging"])]
assert calls("git pull --rebase origin staging") == [("/r", "pull", ["origin", "staging"])]
assert calls('git merge -m "sync staging" origin/staging') == [("/r", "merge", ["origin/staging"])]
assert calls("git -C sub rebase origin/main") == [("/r/sub", "rebase", ["origin/main"])]
# Not syncs: no ref named, control flags, other git commands.
assert calls("git pull") == []
assert calls("git merge --abort") == []
assert calls("git rebase --continue") == []
assert calls("git log origin/staging..HEAD") == []
assert calls("gh pr merge 5 --merge") == []

assert g.names_base(["origin", "staging"], "staging")
assert g.names_base(["origin/staging"], "staging")
assert not g.names_base(["origin/feat/x"], "staging")

# Unresolvable dir is refused before any network call; override lets it through.
assert "can't resolve" in g.check("for w in a; do git -C wt/$w merge origin/staging; done", "/r")
assert g.check("git -C wt/$w merge origin/staging  # sync-base: need fix abc123", "/r") is None

assert g.draft_violation("gh pr create --draft --title x")
assert g.draft_violation("git push && gh pr create -d")
assert g.draft_violation("gh pr ready 5 --undo")
assert not g.draft_violation("gh pr create --title 'no draft here'")
assert list(g.pr_create_dirs("git push && gh pr create --title x", "/r"))
assert not list(g.pr_create_dirs("gh pr create -R me/r --title x", "/r"))
assert not list(g.pr_create_dirs("gh pr create --repo=me/r", "/r"))
# Codex P2s on #37: quoting, continuation, other ref spellings, gh aliases/inherited -R.
assert calls('git merge -m "sync; base" origin/main') == [("/r", "merge", ["origin/main"])]
assert calls("git merge origin/staging # sync; not a command") == [("/r", "merge", ["origin/staging"])]
assert calls('git commit -m "" && git merge origin/staging') == [("/r", "merge", ["origin/staging"])]
assert calls("if true; then git -C wt rebase origin/main; fi") == [("/r/wt", "rebase", ["origin/main"])]
for ref in ["refs/heads/main", "refs/remotes/upstream/main", "company/main", "refs/remotes/origin/main"]:
    assert g.names_base([ref], "main"), ref
assert not g.names_base(["refs/heads/feat/main-fix", "a/b/main"], "main")
assert g.draft_violation("gh pr new --draft")
assert g.draft_violation("gh -R owner/repo pr create --draft")
assert not g.draft_violation('gh pr create --title "no --draft; here"')
assert not list(g.pr_create_dirs("gh -R me/r pr create --title x", "/r"))
assert list(g.pr_create_dirs("gh pr new --title x", "/r"))
# Codex on #38: a comment ends at the newline, and `#` inside a word or quotes isn't one.
assert g.draft_violation("echo ok # note\ngh pr create --draft")
assert g.draft_violation("echo x#not-a-comment; gh pr create --draft")
assert g.draft_violation('gh pr create --title "#12 fix" --draft')
assert g.draft_violation("gh pr create --title '# heading' --draft")
assert not g.draft_violation("gh pr create --title x  # later: --draft")
assert calls("git status # merge origin/main later\ngit merge origin/staging") == \
    [("/r", "merge", ["origin/staging"])]
# Heredoc bodies are data, not commands, and must not hide what follows.
assert g.draft_violation("cat <<'EOF'\n\"\nEOF\ngh pr create --draft")
assert g.draft_violation("cat <<-EOF > f\n\tit's\n\tEOF\ngh pr create --draft")
assert not g.draft_violation("cat <<EOF\ngh pr create --draft\nEOF")
# Codex round 2 on #38: slashed base names, quoted heredoc delimiters, attached -R.
for ref in ["release/v1", "origin/release/v1", "refs/remotes/origin/release/v1", "refs/heads/release/v1"]:
    assert g.names_base([ref], "release/v1"), ref
assert not g.names_base(["a/b/release/v1", "origin/release/v10"], "release/v1")
assert g.draft_violation("cat <<E\\OF\nx\nEOF\ngh pr create --draft")
assert g.draft_violation("cat <<'E'OF\nx\nEOF\ngh pr create --draft")
assert g.draft_violation('cat <<"EOF"\nx\nEOF\ngh pr create --draft')
# A heredoc whose terminator never appears drops nothing (fails toward checking).
assert g.draft_violation("cat <<EOF\nx\ngh pr create --draft")
assert not list(g.pr_create_dirs("gh -Rme/r pr create --title x", "/r"))
assert not list(g.pr_create_dirs("gh pr create -Rme/r", "/r"))
# Codex round 3 (post-merge on #38): subshell cd scope, fail-closed fallback, $'..' delimiters.
assert calls("(cd /tmp; :); git merge origin/main") == [("/r", "merge", ["origin/main"])]
assert calls("(cd /tmp && git merge origin/main)") == [("/tmp", "merge", ["origin/main"])]
assert calls("cd a && (cd b; git merge origin/x); git merge origin/y") == \
    [("/r/a/b", "merge", ["origin/x"]), ("/r/a", "merge", ["origin/y"])]
assert g.draft_violation("printf $'\\''; gh pr create --draft")
assert g.draft_violation("cat <<$'EOF'\nx\nEOF\ngh pr create --draft\n$EOF")
# Quoted or escaped operator characters are arguments, not shell syntax.
assert calls("printf '('; cd /tmp/repo; printf ')'; git merge origin/main") == \
    [("/tmp/repo", "merge", ["origin/main"])]
assert calls("echo \\( ; cd /x; echo \\) ; git merge origin/main") == [("/x", "merge", ["origin/main"])]
assert g.draft_violation("echo ';' && gh pr create --draft")
assert list(g.segments("echo ';' '|'")) == [["echo", ";", "|"]]
assert g.draft_violation("gh pr create --title '\n' --draft")
assert g.draft_violation('gh pr create --title "a\nb" --draft')
# Unparseable input still keeps line boundaries.
assert g.draft_violation("echo 'unterminated\ngh pr create --draft")

# pr_open_mode: only an explicit "draft" allows drafts; unset, ready and corrupt mean ready.
import json, re, tempfile
_prefs = Path(tempfile.mkdtemp()) / "preferences.json"
assert not g.draft_mode(_prefs)  # missing file
for body, want in [({}, False), ({"settings": {}}, False), ({"settings": {"pr_open_mode": "ready"}}, False),
                   ({"settings": {"pr_open_mode": "draft"}}, True), ({"settings": None}, False)]:
    _prefs.write_text(json.dumps(body))
    assert g.draft_mode(_prefs) is want, body
_prefs.write_text("{not json")
assert not g.draft_mode(_prefs)

# Ungated merge and polling. Mock the gh call the way a green/red rollup would come back.
class _R:
    def __init__(self, rc, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err

HEAD_SHA = "a" * 40
def _jq(args, body, api_rc):
    """Apply the guard's own --jq expression to an API-shaped body with real jq, as gh does."""
    if api_rc:
        return _R(api_rc, "", "boom")
    out = _run(["jq", "-r", args[args.index("--jq") + 1]], input=json.dumps(body), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return _R(0, out.stdout)

def _gh_error(status, message):
    """What gh returns for an HTTP error: exit 1, GitHub's JSON error body on stdout, a summary on stderr."""
    body = {"message": message, "documentation_url": "https://docs.github.com/rest", "status": str(status)}
    return _R(1, json.dumps(body, separators=(",", ":")), f"gh: {message} (HTTP {status})")

NOT_FOUND, NOT_PROTECTED = _gh_error(404, "Not Found"), _gh_error(404, "Branch not protected")
ACTIONS_APP = 15368

def _gh(rc=0, rollup=None, err="", paths=None, api_rc=0, events=None, forged=(), owners=None, titles=None,
        branches=None, host="github.com", calls=None, check_runs=None, cr=None, policy=NOT_FOUND, rules=(),
        protection=NOT_PROTECTED, base="main"):
    """`gh pr view` returns the rollup for PR o/r#5 (head branch feat); `gh api .../actions/runs` resolves
    each run id to its workflow file. By default a run's path follows its workflowName; `paths` overrides
    it per run id (None = the API does not list that run), `events` the event, `owners` its pull_requests
    numbers (default [5]), `titles` its display_title, `branches` its head branch. `.../runs/<id>/jobs`
    lists every rollup entry's job as real, except entries in `forged` (custom checks with a borrowed
    detailsUrl). Every gh api call must target the PR's own host and repo; `calls` collects them.

    `.../commits/<sha>/check-runs` lists one REST check run per named rollup entry, as GitHub does: an
    Actions job's id is its job id, a forged entry (borrowed detailsUrl) gets an id of its own, a check run
    without a job URL gets an id of its own; app is `_app` (default GitHub Actions for job URLs, 99 else).
    `check_runs` replaces that list, `cr` (a _R) fails the call. `policy` is the default branch's
    .github/required-checks.json: a dict (encoded as the contents API does), a str (raw file text), or a
    _R error (default 404). `rules` lists the base branch's rules, `protection` the classic
    required_status_checks body, each a _R to fail."""
    def run(args, *a, **k):
        if args[:2] == ["gh", "api"]:
            assert args[args.index("--hostname") + 1] == host, args
            path = next(x for x in args if x.startswith("repos/"))
            assert path.startswith("repos/o/r/"), args
            if calls is not None:
                calls.append(args)
        if args[:2] == ["gh", "api"] and api_rc:
            return _R(api_rc, "", "boom")
        if args[:2] == ["gh", "api"] and "/check-runs" in path:
            assert path == f"repos/o/r/commits/{HEAD_SHA}/check-runs?filter=all&per_page=100", args
            if cr is not None:
                return cr
            runs = check_runs
            if runs is None:
                runs = []
                for k, e in enumerate(rollup or []):
                    if not e.get("name"):
                        continue  # a status context is not a check run
                    m = g.RUN_ID.search(e.get("detailsUrl") or "")
                    real = m and id(e) not in {id(f) for f in forged}
                    runs.append({"id": int(m.group(2)) if real else 900000 + k,
                                 "app": {"id": e.get("_app", ACTIONS_APP if m else 99)},
                                 "name": e["name"], "details_url": e.get("detailsUrl")})
            return _jq(args, {"check_runs": runs}, 0)
        if args[:2] == ["gh", "api"] and "/contents/" in path:
            assert path == "repos/o/r/contents/.github/required-checks.json", args  # no ref: the default branch
            if isinstance(policy, _R):
                return policy
            text = policy if isinstance(policy, str) else json.dumps(policy)
            return _jq(args, {"type": "file", "encoding": "base64", "content": base64.b64encode(text.encode()).decode()}, 0)
        if args[:2] == ["gh", "api"] and "/rules/branches/" in path:
            assert path == f"repos/o/r/rules/branches/{quote(base, safe='')}?per_page=100", args
            return rules if isinstance(rules, _R) else _jq(args, list(rules), 0)
        if args[:2] == ["gh", "api"] and "/protection/required_status_checks" in path:
            assert path == f"repos/o/r/branches/{quote(base, safe='')}/protection/required_status_checks", args
            return protection if isinstance(protection, _R) else _jq(args, protection, 0)
        if args[:2] == ["gh", "api"] and "/jobs?" in path:
            run_id = re.search(r"/runs/(\d+)/jobs", path).group(1)
            jobs = [{"id": int(m.group(2)), "name": e.get("name"), "conclusion": e.get("conclusion") or None}
                    for e in rollup or [] if id(e) not in {id(f) for f in forged}
                    and (m := g.RUN_ID.search(e.get("detailsUrl") or "")) and m.group(1) == run_id]
            return _jq(args, {"jobs": jobs}, api_rc)
        if args[:2] == ["gh", "api"]:
            assert f"head_sha={HEAD_SHA}" in path, args
            rows = {}
            for e in rollup or []:
                m = g.RUN_ID.search(e.get("detailsUrl") or "")
                if m and e.get("workflowName"):
                    rows[m.group(1)] = f".github/workflows/{e['workflowName'].lower().replace(' ', '-')}.yml"
            rows.update(paths or {})
            out = [{"id": int(i) if i.isdigit() else i, "path": pth, "event": (events or {}).get(i, "pull_request"),
                    "pull_requests": [{"number": n} for n in (owners or {}).get(i, [5])],
                    "display_title": (titles or {}).get(i, "feat: x"), "head_branch": (branches or {}).get(i, "feat"),
                    "head_repository": {"full_name": "o/r"}} for i, pth in rows.items() if pth]
            return _jq(args, {"workflow_runs": out}, api_rc)
        return _R(rc, json.dumps({"statusCheckRollup": rollup, "headRefOid": HEAD_SHA, "number": 5,
                                  "url": f"https://{host}/o/r/pull/5", "headRefName": "feat",
                                  "headRepository": {"nameWithOwner": "o/r"}, "baseRefName": base}), err)
    return run

_run = g.subprocess.run
def merge(cmd, **kw):
    g.subprocess.run = _gh(**kw)
    try:
        return g.check(cmd, "/r")
    finally:
        g.subprocess.run = _run

ok = [{"name": "pytest", "conclusion": "SUCCESS"}, {"name": "lint", "conclusion": "skipped"},
      {"context": "ci/x", "state": "SUCCESS"}, {"name": "n", "conclusion": "NEUTRAL"}]
assert "--admin" in merge("gh pr merge 5 --admin --squash", rollup=ok)
assert "never bypass" in merge("gh pr merge 5 --admin --auto", rollup=ok)
assert "never `--auto`" in merge("gh pr merge 5 --auto --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok)
assert "pin the reviewed head" in merge("gh pr merge 5 --squash", rollup=ok)
# Codex P1 on #82 (round 7): an unset $SHA expands to an empty value; a short SHA is not a pin either.
assert "pin the reviewed head" in merge('gh pr merge 5 --squash --match-head-commit ""', rollup=ok)
assert "pin the reviewed head" in merge("gh pr merge 5 --squash --match-head-commit=", rollup=ok)
assert "pin the reviewed head" in merge("gh pr merge 5 --squash --match-head-commit abc1234", rollup=ok)
# Codex P2 on #82: --disable-auto merges nothing, so it needs no head pin or green checks.
assert merge("gh pr merge 5 --disable-auto", rollup=[]) is None
assert merge("gh -R o/r pr merge 5 --disable-auto", rollup=[]) is None
assert "never `--auto`" in merge("gh pr merge 5 --disable-auto --auto", rollup=ok)
assert "never bypass" in merge("gh pr merge 5 --disable-auto --admin", rollup=ok)
# Codex P1 on #82 (round 6): `--disable-auto=false` leaves the option off, so it merges: full checks.
assert "pin the reviewed head" in merge("gh pr merge 5 --disable-auto=false --squash", rollup=ok)
assert merge("gh pr merge 5 --disable-auto=true", rollup=[]) is None
assert "pin the reviewed head" in merge("gh pr merge 5 --body --disable-auto --squash", rollup=ok)
# 1.4.3: pflag bool flags are last-wins. `--disable-auto --disable-auto=false` merges: full checks.
assert "pin the reviewed head" in merge("gh pr merge 5 --disable-auto --disable-auto=false --squash", rollup=ok)
assert merge("gh pr merge 5 --disable-auto=false --disable-auto", rollup=[]) is None
assert "never `--auto`" in merge("gh pr merge 5 --auto=false --auto --squash", rollup=ok)
assert "never bypass" in merge("gh pr merge 5 --admin=0 --admin=1 --squash", rollup=ok)
assert merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok) is None
assert merge("gh pr merge 5 --squash --match-head-commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok) is None
# Codex P1 on #82: the status lookup must target the -R/--repo repo, not the cwd repo.
def _gh_repo(want):
    def run(args, *a, **k):
        i = args.index("-R") if "-R" in args else -1
        if i < 0 or args[i + 1] != want:  # gh resolved the PR in the cwd repo: the live failure
            return _R(1, "", "Could not resolve to a PullRequest")
        return _R(0, json.dumps({"statusCheckRollup": ok}))
    return run
for c in ["gh -R owner/target pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh pr merge 5 -R owner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh pr merge 5 --repo owner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh --repo=owner/target pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh pr merge 5 -Rowner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          # Codex P2 on #82: repeated repo flags, last wins (as gh does), in every spelling.
          "gh -R owner/safe pr merge 5 -R owner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh --repo=owner/safe pr merge 5 --repo owner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh -Rowner/safe pr merge 5 --repo=owner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh --repo owner/safe pr merge 5 -Rowner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          # Codex P2 on #82 (round 6): a value flag consumes the next token, so a repo-looking
          # --body/-t value is text, not a repo, and a value-looking --disable-auto is not a flag.
          "gh -R owner/target pr merge 5 --body --repo=owner/green --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh -R owner/target pr merge 5 -t -Rowner/green --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh pr merge 5 -R owner/target --body -R --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]:
    g.subprocess.run = _gh_repo("owner/target")
    try:
        assert g.check(c, "/r") is None, (c, g.check(c, "/r"))
    finally:
        g.subprocess.run = _run
# Codex P1 on #82 (round 3 of repo parsing): clustered short flags carrying R fail closed.
for c in ["gh pr merge 5 -dR owner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh pr merge 5 -dRowner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh pr merge 5 -Rd --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa -R"]:
    g.subprocess.run = _gh_repo("owner/target")
    try:
        assert "standalone `-R owner/repo`" in (g.check(c, "/r") or ""), c
    finally:
        g.subprocess.run = _run
g.subprocess.run = _gh_repo("owner/target")
try:
    assert "Could not resolve" in g.check("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/r")
finally:
    g.subprocess.run = _run
# prevost#379 P2: `--admin=false` / `--auto=false` turn the option off, so the call takes the normal checks.
assert merge("gh pr merge 5 --admin=false --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok) is None
assert merge("gh pr merge 5 --auto=false --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok) is None
assert "never bypass" in merge("gh pr merge 5 --admin=true --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok)
# prevost#379 P1: any short-flag cluster fails closed (`-st 5 6`: gh merges 6 with title 5).
for c in ["gh pr merge -st 5 6 --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "gh pr merge 6 -sd --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]:
    assert "can't parse this merge" in merge(c, rollup=ok), c
# prevost#379 P1: the status lookup runs in the merge's effective dir (`cd`, `env -C`), not the hook's cwd.
def _gh_cwd(want):
    def run(args, *a, cwd=None, **k):
        rollup = ok if cwd == want else [{"name": "pytest", "conclusion": "FAILURE"}]
        return _R(0, json.dumps({"statusCheckRollup": rollup}))
    return run
for c, want in [("cd /other && gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/other"),
                ("env -C /other gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/other"),
                ("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/r")]:
    g.subprocess.run = _gh_cwd(want)
    try:
        assert g.check(c, "/r") is None, (c, g.check(c, "/r"))
        g.subprocess.run = _gh_cwd("/r" if want != "/r" else "/x")
        assert "not all green" in (g.check(c, "/r") or ""), c
    finally:
        g.subprocess.run = _run
assert "working directory" in merge("cd $D && gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok)
# claude-skills#83 Codex: a cd in a background job / pipeline stage doesn't reach the merge: fail closed.
for c in ["cd /other & gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "cd /other | gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "cd /other |& gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "cd /other &>/dev/null & gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]:
    assert "working directory" in (merge(c, rollup=ok) or ""), c
assert merge("cd /other && gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 2>&1", rollup=ok) is None
# Redirections and quoted operators are not pipeline boundaries.
for c in ["cd /other && gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa &>/dev/null",
          "cd /other && gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa >&2",
          "cd /other && gh pr merge 5 -b 'a | b & c' --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]:
    assert merge(c, rollup=ok) is None, (c, merge(c, rollup=ok))
# Backtick dirs are as unresolved as $(…); an explicit -R makes the dir irrelevant.
assert "working directory" in merge("cd `pwd`/x && gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok)
g.subprocess.run = _gh_repo("owner/target")
try:
    for c in ['cd "$D" && gh pr merge 5 -R owner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
              "cd `x` && gh pr merge 5 -R owner/target --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]:
        assert g.check(c, "/r") is None, (c, g.check(c, "/r"))
finally:
    g.subprocess.run = _run
assert merge("gh pr merge https://github.com/o/r/pull/5 -t 'x y' --merge --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok) is None
for bad, name in [({"name": "pytest", "conclusion": "CANCELLED"}, "pytest: CANCELLED"),
                  ({"name": "pytest", "conclusion": ""}, "pytest: PENDING"),
                  ({"name": "pytest", "conclusion": "FAILURE"}, "pytest: FAILURE"),
                  ({"context": "ci/x", "state": "PENDING"}, "ci/x: PENDING"),
                  ({"context": "ci/x", "state": "FAILURE"}, "ci/x: FAILURE")]:
    m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [bad])
    assert m and name in m and "--watch --fail-fast" in m, (bad, m)
# Only the LATEST run per check name counts: a historical red Review Gate run must not block
# once a newer run of the same check is green (every new PR leaves one, nevar-design#7).
_run_ids = iter(range(1000, 10**6))
def run(name, concl, at, wf="Review Gate"):  # each call is its own workflow run, as gh reports it
    return {"name": name, "workflowName": wf, "conclusion": concl, "startedAt": at,
            "detailsUrl": "https://github.com/o/r/actions/runs/{0}/job/{0}".format(next(_run_ids))}
old_red = [run("Review Gate", "FAILURE", "2026-11-15T10:00:00Z"), run("Review Gate", "CANCELLED", "2026-11-15T10:05:00Z")]
latest_ok = run("Review Gate", "SUCCESS", "2026-11-15T10:10:00Z")
assert merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + old_red + [latest_ok]) is None
assert merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [latest_ok] + old_red) is None  # order-independent
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [run("Review Gate", "SUCCESS", "2026-11-15T10:00:00Z"),
                                                   run("Review Gate", "FAILURE", "2026-11-15T10:10:00Z")])
assert m and "Review Gate: FAILURE" in m, m  # newest red still blocks
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [run("Review Gate", "SUCCESS", "2026-11-15T10:00:00Z"),
                                                   run("Review Gate", "", "2026-11-15T10:10:00Z")])
assert m and "Review Gate: PENDING" in m, m  # a re-run in flight blocks
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + old_red + [latest_ok, run("pytest", "FAILURE", "2026-11-15T10:00:00Z", "CI")])
assert m and "pytest: FAILURE" in m and "Review Gate" not in m, m  # other checks stay independent
# a queued rerun has no startedAt: it still beats the older green run and blocks
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [latest_ok, {"name": "Review Gate", "workflowName": "Review Gate", "conclusion": "", "status": "QUEUED", "startedAt": None}])
assert m and "Review Gate: PENDING" in m, m
# 1.4.3: same-second reruns: a SUCCESS must not hide a FAILURE, in either list order
for pair in ([run("Review Gate", "FAILURE", "2026-11-15T10:10:00Z"), latest_ok],
             [latest_ok, run("Review Gate", "FAILURE", "2026-11-15T10:10:00Z")]):
    m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + pair)
    assert m and "Review Gate: FAILURE" in m, (pair, m)
# ...and ids do not order them either: same-run sibling jobs (higher job id) and different runs alike
def job_run(concl, run_id, job_id):
    return dict(run("Review Gate", concl, "2026-11-15T10:10:00Z"),
                detailsUrl=f"https://github.com/o/r/actions/runs/{run_id}/job/{job_id}")
for pair in ([job_run("FAILURE", 100, 1), job_run("SUCCESS", 100, 2)], [job_run("SUCCESS", 100, 2), job_run("FAILURE", 100, 1)],
             [job_run("FAILURE", 100, 1), job_run("SUCCESS", 101, 2)], [job_run("SUCCESS", 101, 2), job_run("FAILURE", 100, 1)]):
    m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + pair)
    assert m and "Review Gate: FAILURE" in m, (pair, m)
# 1.4.5 (nevar-fund #25 Codex P1): identity is the run id, not the name. A distinct same-named job
# in the SAME run (e.g. one with `needs:`) that starts later and is green must not hide a failed one.
def at_job(concl, run_id, job_id, at):
    return dict(run("Review Gate", concl, at), detailsUrl=f"https://github.com/o/r/actions/runs/{run_id}/job/{job_id}")
for pair in ([at_job("FAILURE", 100, 1, "2026-11-15T10:00:00Z"), at_job("SUCCESS", 100, 2, "2026-11-15T10:10:00Z")],
             [at_job("SUCCESS", 100, 2, "2026-11-15T10:10:00Z"), at_job("FAILURE", 100, 1, "2026-11-15T10:00:00Z")]):
    m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + pair)
    assert m and "Review Gate: FAILURE" in m, (pair, m)
# ...while a newer run of the workflow (a true rerun) still supersedes the older run's failure,
assert merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [
    at_job("FAILURE", 100, 1, "2026-11-15T10:00:00Z"), at_job("SUCCESS", 101, 5, "2026-11-15T10:10:00Z")]) is None
# even when the old run's own later sibling job started after the new run did,
assert merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [
    at_job("FAILURE", 100, 1, "2026-11-15T10:00:00Z"), at_job("SUCCESS", 100, 2, "2026-11-15T10:20:00Z"),
    at_job("SUCCESS", 101, 5, "2026-11-15T10:10:00Z")]) is None
# and every same-named job of that newest run must be green.
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [
    at_job("SUCCESS", 100, 1, "2026-11-15T10:00:00Z"), at_job("SUCCESS", 101, 5, "2026-11-15T10:10:00Z"),
    at_job("FAILURE", 101, 6, "2026-11-15T10:15:00Z")])
assert m and "Review Gate: FAILURE" in m, m
# #88 Codex P1 (r4582093085): a run's start spans ALL its jobs. Run 100 starts 10:00 (build) and its
# dependency-delayed `gate` goes green at 10:20; run 101 starts 10:10 and its `gate` fails at 10:15.
def wf_job(name, concl, run_id, job_id, at):
    return {"name": name, "workflowName": "CI", "conclusion": concl, "startedAt": at,
            "detailsUrl": f"https://github.com/o/r/actions/runs/{run_id}/job/{job_id}"}
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [
    wf_job("build", "SUCCESS", 100, 1, "2026-11-15T10:00:00Z"), wf_job("gate", "SUCCESS", 100, 2, "2026-11-15T10:20:00Z"),
    wf_job("build", "SUCCESS", 101, 3, "2026-11-15T10:10:00Z"), wf_job("gate", "FAILURE", 101, 4, "2026-11-15T10:15:00Z")])
assert m and "gate: FAILURE" in m, m
# #88 Codex P1 (r4582226134): without a parsable run id the run identity is unknown, so a later
# green job must not supersede an earlier failed one (missing or unrecognized detailsUrl alike).
for url in (None, "https://example.com/not-a-job"):
    m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [
        {"name": "Review Gate", "workflowName": "Review Gate", "conclusion": "FAILURE", "startedAt": "2026-11-15T10:00:00Z", "detailsUrl": url},
        {"name": "Review Gate", "workflowName": "Review Gate", "conclusion": "SUCCESS", "startedAt": "2026-11-15T10:10:00Z", "detailsUrl": url}])
    assert m and "Review Gate: FAILURE" in m, (url, m)
# 1.4.6 (nevar-integrations#11 Codex P1 r4582423865): workflow identity is the run's file path, not
# its editable `name:`. A PR-added workflow also named `CI` with a later green `Foundation checks` job
# must not supersede the real CI run's failed `Foundation checks`.
real = wf_job("Foundation checks", "FAILURE", 200, 1, "2026-11-15T10:00:00Z")
fake = wf_job("Foundation checks", "SUCCESS", 201, 2, "2026-11-15T10:10:00Z")
for paths in ({"200": ".github/workflows/ci.yml", "201": ".github/workflows/sneaky.yml"},  # two paths, one name
              {"201": None},  # the API does not list the newer run: unresolved, supersedes nothing
              {"200": ".github/workflows/ci.yml", "201": ".github/workflows/ci.yml", "x": "y"}):
    pr_merge = "gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    g.subprocess.run = _gh(rollup=ok + [real, fake], paths=paths)
    try:
        m = g.check(pr_merge, "/r")
    finally:
        g.subprocess.run = _run
    if paths["201"] == ".github/workflows/ci.yml":
        assert m is None, (paths, m)  # a true rerun of the same workflow file still supersedes
    else:
        assert m and "Foundation checks: FAILURE" in m, (paths, m)
# One workflow file, two events: a newer green pull_request run never supersedes an older red
# pull_request_target run of the same file (identity is (path, event, job name)).
for events, blocked in (({"200": "pull_request_target", "201": "pull_request"}, True),
                        ({"200": "pull_request", "201": "pull_request"}, False)):
    g.subprocess.run = _gh(rollup=ok + [real, fake], paths={"200": ".github/workflows/ci.yml", "201": ".github/workflows/ci.yml"},
                           events=events)
    try:
        m = g.check("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/r")
    finally:
        g.subprocess.run = _run
    assert bool(m) is blocked and (not blocked or "Foundation checks: FAILURE" in m), (events, m)
# #90 Codex P1 (r4582487271): a custom green check whose writable detailsUrl names a job in a newer
# legitimate run of the same workflow file is not that run's job, so it supersedes nothing.
newer_build = wf_job("build", "SUCCESS", 202, 7, "2026-11-15T10:10:00Z")
custom = wf_job("Foundation checks", "SUCCESS", 202, 7, "2026-11-15T10:11:00Z")  # borrows job 7's URL
for bad in (dict(custom), dict(custom, detailsUrl="https://github.com/o/r/actions/runs/202/job/99")):
    g.subprocess.run = _gh(rollup=ok + [real, newer_build, bad], forged=(bad,))
    try:
        m = g.check("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/r")
    finally:
        g.subprocess.run = _run
    assert m and "Foundation checks: FAILURE" in m, (bad, m)
# 1.4.7 (nevar-fund#27 Codex P1 r4582757746): two PRs share a head sha (one branch into staging and
# main), so the rollup holds both PRs' runs. PR 6's newer green run must not supersede PR 5's failed run.
def guarded(**kw):
    g.subprocess.run = _gh(rollup=ok + [real, fake], paths={"200": ".github/workflows/ci.yml", "201": ".github/workflows/ci.yml"}, **kw)
    try:
        return g.check("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/r")
    finally:
        g.subprocess.run = _run
for kw in ({"owners": {"201": [6]}},  # the other PR's run
           {"owners": {"201": [5, 6]}},  # GitHub lists both PRs: ambiguous
           {"owners": {"201": []}},  # no PR association (fork): unresolved
           {"branches": {"201": "other"}},  # another branch's run
           {"titles": {"201": "Review Gate - PR #6"}}):  # review-gate 3.2.6 run-name names PR 6
    m = guarded(**kw)
    assert m and "Foundation checks: FAILURE" in m, (kw, m)
assert guarded(titles={"201": "Review Gate - PR #5"}) is None  # this PR's own rerun still supersedes
# ...and an attributed older run of another PR does not get superseded by this PR's run either: it
# was never this PR's, so it stays in the rollup and must be green on its own.
m = guarded(owners={"200": [6]})
assert m and "Foundation checks: FAILURE" in m, m
# 1.4.7 (#90 Codex P2, Tracker 41a4efecc95a81c19402cec8c8b9606d): lookups return JSON, not @tsv, so a
# job name with a backslash or a tab matches its rollup entry and a newer run still supersedes.
odd = "build\\x\ty"
g.subprocess.run = _gh(rollup=ok + [wf_job(odd, "FAILURE", 210, 1, "2026-11-15T10:00:00Z"),
                                    wf_job(odd, "SUCCESS", 211, 2, "2026-11-15T10:10:00Z")])
try:
    assert g.check("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/r") is None
finally:
    g.subprocess.run = _run
# 1.4.7 (#90 Codex P2, Tracker 41a4efecc95a811eb3d3f532769d9091): a URL selector or an Enterprise
# `-R HOST/OWNER/REPO` makes the lookups use the PR's own host and repo, never the cwd's.
for c in ["gh pr merge https://ghe.example.com/o/r/pull/5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "gh pr merge 5 -R ghe.example.com/o/r --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]:
    _calls = []
    g.subprocess.run = _gh(rollup=ok + old_red + [latest_ok], host="ghe.example.com", calls=_calls)
    try:
        assert g.check(c, "/other-checkout") is None, (c, g.check(c, "/other-checkout"))
    finally:
        g.subprocess.run = _run
    assert _calls, c
# the Actions API failing resolves nothing, so nothing is superseded (fail closed)
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + old_red + [latest_ok], api_rc=1)
assert m and "Review Gate: FAILURE" in m, m
# #90 Codex P2 (r4582534724): every gh call shares one deadline under the hook's 20 s timeout. Each
# call here "takes" 6 s, so the newer run's jobs lookup is past the 15 s budget: it is skipped, that
# run supersedes nothing (fail closed), and no call is ever given a timeout past the deadline.
_clock, _timeouts, _gh_slow = [0.0], [], _gh(rollup=ok + [real, fake], paths={"200": ".github/workflows/ci.yml", "201": ".github/workflows/ci.yml"})
def _slow(args, *a, **k):
    _timeouts.append((_clock[0], k["timeout"]))
    _clock[0] += 6
    return _gh_slow(args, *a, **k)
g.subprocess.run, _mono, g.time.monotonic = _slow, g.time.monotonic, lambda: _clock[0]
try:
    m = g.check("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "/r")
finally:
    g.subprocess.run, g.time.monotonic = _run, _mono
assert m and "Foundation checks: FAILURE" in m, m
assert len(_timeouts) == 3 and all(t0 + t <= g.GH_BUDGET_S for t0, t in _timeouts), _timeouts
# an older run still in progress does not outrank a newer green run
assert merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [run("Review Gate", "", "2026-11-15T10:00:00Z"), latest_ok]) is None
# an undated completed rerun cannot be ordered, so it fails closed
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [latest_ok, {"name": "Review Gate", "workflowName": "Review Gate", "conclusion": "CANCELLED", "startedAt": None}])
assert m and "Review Gate: CANCELLED" in m, m
# gh emits the zero time, not null, for a missing startedAt
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [latest_ok, {"name": "Review Gate", "workflowName": "Review Gate", "conclusion": "CANCELLED", "startedAt": "0001-01-01T00:00:00Z"}])
assert m and "Review Gate: CANCELLED" in m, m
# same-named third-party check runs from different apps are never collapsed
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [{"__typename": "CheckRun", "name": "scan", "conclusion": "FAILURE", "startedAt": "2026-11-15T10:00:00Z"},
                                                   {"__typename": "CheckRun", "name": "scan", "conclusion": "SUCCESS", "startedAt": "2026-11-15T10:05:00Z"}])
assert m and "scan: FAILURE" in m, m
# a check run and a same-named status context are separate requirements
m = merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=ok + [{"__typename": "CheckRun", "name": "deploy", "conclusion": "FAILURE", "startedAt": "2026-11-15T10:00:00Z"},
                                                   {"__typename": "StatusContext", "context": "deploy", "state": "SUCCESS"}])
assert m and "deploy: FAILURE" in m, m
assert "no checks" in merge("gh pr merge 5 --squash --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=[])
assert "no checks" in merge("gh pr merge 5 --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rollup=None)
m = merge("gh pr merge 5 --match-head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", rc=1, err="no pull requests found")
assert m and "no pull requests found" in m
assert merge("gh pr view 5 && echo done", rollup=[]) is None

for c in ["while true; do gh pr checks 12 | grep -q pending || break; sleep 30; done",
          "sleep 60 && gh pr view 12", "gh run watch 9; sleep 1", "until gh run list; do sleep 5; done",
          "for i in 1 2; do sleep 10\n gh pr status\n done"]:
    assert "never poll" in (g.check(c, "/r") or ""), c
for c in ["gh pr checks 12 --watch --fail-fast", "sleep 5", "gh pr view 12", "echo gh pr checks; sleep 5",
          "sleep 5 # gh pr checks 12", "cat <<EOF\ngh pr checks 12\nEOF\nsleep 5"]:
    assert g.check(c, "/r") is None, c
# 1.5.0: a posted comment that mentions the Codex bot is blocked (Matt's quota); `# codex-review-ok: <reason>` allows it
import tempfile as _tf
import os
M = "@" + "codex"
_blocked = lambda c, cwd="/r": (g.check(c, cwd) or "").startswith("Blocked: this comment mentions the Codex bot")
for c in (f'gh pr comment 119 --body "{M} review"', f"gh pr comment 119 -b '{M} review'",
          f'gh issue comment 7 --body="{M.upper()} please review"', f'gh -R o/r pr comment 5 --body "{M} review"',
          f'gh pr review 5 --comment -b "{M} review"',
          f"gh api repos/o/r/issues/5/comments -f body='{M} review'",
          f"gh api -X POST repos/o/r/issues/5/comments --raw-field body='{M} review'",
          f"gh pr comment 5 --body-file - <<'EOF'\nplease\n{M} review\nEOF",
          f"cd wt && gh pr comment 5 --body '{M} review'"):
    assert _blocked(c), c
    assert g.check(c + f"  # codex-review-ok: Matt asked for a Codex pass on this head", "/r") is None, c
# the marker needs a reason and must be a shell comment, not quoted text
assert _blocked(f'gh pr comment 5 --body "{M} review"  # codex-review-ok:')
assert _blocked(f'gh pr comment 5 --body "{M} review codex-review-ok: x"')
# Codex P1 on #120: the marker inside the quoted body or a heredoc is sent text, not an override
for c in (f"gh pr comment 5 --body '{M} review # codex-review-ok: bypass'",
          f'gh pr comment 5 --body "{M} review  # codex-review-ok: bypass"',
          f"gh pr comment 5 --body-file - <<'EOF'\n{M} review\n# codex-review-ok: bypass\nEOF"):
    assert _blocked(c), c
assert g.check("git -C wt/$w merge origin/staging  # sync-base: real conflict in x.py", "/r") is None
assert g.check("git -C wt/$w merge origin/staging && echo '# sync-base: nope'", "/r") is not None
# Sonnet P1 on #120: a body file written in the same command, or a stdin alias, can't be read by the hook
for c in (f"cat > /tmp/b-{os.getpid()}.md <<'EOF'\n{M} review\nEOF\ngh pr comment 5 --body-file /tmp/b-{os.getpid()}.md",
          f"printf '%s' '{M} review' > b.md && gh pr comment 5 -F b.md",
          f"gh pr comment 5 -F /dev/stdin <<'EOF'\n{M} review\nEOF", f"gh pr comment 5 -F /dev/fd/0 <<'EOF'\n{M} review\nEOF"):
    assert _blocked(c), c
# the override's colon is optional; it still needs a reason
assert g.check(f'gh pr comment 5 --body "{M} review"  # codex-review-ok Matt asked', "/r") is None
assert _blocked(f'gh pr comment 5 --body "{M} review"  # codex-review-ok')
assert _blocked(f'gh pr comment 5 --body "{M} review"  # codex-review-okay x')
# an email address is not a mention
assert not _blocked("gh pr comment 5 --body 'mail bob@codex.io'")
# not a post, not the bot, or the phrase only in an unrelated heredoc / read
for c in (f"cat > notes.md <<'EOF'\n{M} review\nEOF", f"git commit -q -F - <<'EOF'\nno {M} review\nEOF",
          f'gh pr comment 5 --body "{M}-helper and {M}x are not the bot"', "gh pr comment 5 --body 'Codex review done'",
          f"gh api repos/o/r/issues/5/comments --jq '.[] | select(.body | contains(\"{M}\"))'",
          f'gh pr view 5 --json body -q .body | grep "{M}"',
          f"cat <<'EOF' > b.md\n{M} review\nEOF\ngh pr comment 5 --body 'see the notes'"):
    assert not _blocked(c), c
# a body read from a file is scanned (--body-file, -F, gh api -F body=@file, --input), relative to cd
with _tf.TemporaryDirectory() as d:
    Path(d, "sub").mkdir()
    Path(d, "sub", "bad.md").write_text(f"Round 2\n{M} review\n")
    Path(d, "sub", "ok.md").write_text("Round 2, fallback attested\n")
    for c in ("gh pr comment 5 --body-file sub/bad.md", "gh pr comment 5 -F sub/bad.md",
              "gh pr comment 5 --body-file=sub/bad.md",
              "gh api repos/o/r/issues/5/comments -F body=@sub/bad.md", "gh api repos/o/r/issues/5/comments --input sub/bad.md",
              # Codex P2 on #120: pflag shorthand with the value attached
              "gh pr comment 5 -Fsub/bad.md", "gh pr comment 5 -F=sub/bad.md", "gh api repos/o/r/issues/5/comments -Fbody=@sub/bad.md",
              f"gh api repos/o/r/issues/5/comments -fbody='{M} review'"):
        assert _blocked(c, d), c
    for c in ("gh pr comment 5 --body-file sub/ok.md", "gh api repos/o/r/issues/5/comments -F body=@sub/ok.md",
              "gh pr comment 5 --body-file sub/missing.md"):
        assert not _blocked(c, d), c
    # 1.5.1, Codex on nevar-content #14: a body path the shell expands ($VAR, `cmd`, or relative under such a
    # cd) can't be read here, so the check fails closed with a fix; an absolute path under such a cd still reads.
    _unread = lambda c: (g.check(c, d) or "").startswith("Blocked: can't read the comment body file")
    for c in ('gh pr comment 1 --body-file "$BODY"', "gh pr comment 1 -F $F", "gh pr comment 1 -F`mktemp`",
              'gh issue comment 1 --body-file="${TMP}/b.md"', 'gh api repos/o/r/issues/1/comments -F body=@"$B"',
              'gh api repos/o/r/issues/1/comments --input "$B"', 'cd "$WT" && gh pr comment 1 -F b.md'):
        assert _unread(c), c
        assert g.check(c + "  # codex-review-ok: Matt asked for a Codex pass", d) is None, c
    for c in (f'cd "$WT" && gh pr comment 1 -F {d}/sub/ok.md', "gh pr comment 1 --body-file - <<'EOF'\nhi\nEOF",
              'gh pr comment 1 --body "$MSG"', 'git commit -F "$MSG_FILE"'):
        assert g.check(c, d) is None, c
    assert _blocked(f'cd "$WT" && gh pr comment 1 -F {d}/sub/bad.md', d)
    # Codex high on #123: every shell expansion form fails closed, not just $ and backtick (P1-1)
    _any = lambda c, cwd=d: (g.check(c, cwd) or "").startswith("Blocked:")
    for c in ("gh pr comment 123 --body-file sub/bad.?d", "gh pr comment 123 --body-file sub/b*.md",
              "gh pr comment 123 --body-file sub/[b]ad.md", "gh pr comment 123 --body-file sub/bad.{md,txt}",
              "gh pr review 123 --comment --body-file <(cat sub/bad.md)", "gh pr comment 123 -F <(cat sub/bad.md)",
              "gh pr comment 123 --body-file $'sub/bad.\\x6dd'", "cd sub* && gh pr comment 1 -F bad.md"):
        assert _any(c), c
    # 1.5.1 round 3: only a plain literal word resolves; anything the shell may rewrite fails closed.
    # A quoted `plain*.md` or `cost$5.md` is a conservative block (workaround: rename, or a plain path).
    Path(d, "cost$5.md").write_text(f"{M} review\n")
    Path(d, "plain*.md").write_text("ok\n")
    for c in ("gh pr comment 123 --body-file 'cost$5.md'", 'gh pr comment 123 --body-file "cost\\$5.md"',
              "gh pr comment 123 --body-file 'plain*.md'", 'gh pr comment 123 --body-file "plain*.md"'):
        assert _any(c), c
    # ~ forms: bash expands ~+, ~- and ~user, and a quoted ~ is literal; none resolve here (F2)
    for c in ("gh pr comment 123 --body-file ~/no-such-pr-guard-body.md", "gh pr comment 123 --body-file ~+/sub/bad.md",
              "gh pr comment 123 --body-file ~-/sub/bad.md", "gh pr comment 123 --body-file ~root/bad.md",
              "gh pr comment 123 --body-file '~/bad.md'", "gh pr comment 123 -F \\~/bad.md"):
        assert _unread(c), c
    # a continuation inside a word joins as in bash (sub/bad.md is read); zsh =(...) / =cmd fail closed (F3)
    for c in ("gh pr comment 123 --body-file sub/ba\\\nd.md", "gh pr comment 123 --body-file =(cat sub/bad.md)",
              "gh pr comment 123 -F =cat"):
        assert _any(c), c
    # a continuation between words still joins the command
    for c in ("gh pr comment 5 \\\n  --body-file sub/bad.md", "gh pr \\\n comment 5 -F sub/bad.md"):
        assert _blocked(c, d), c
    # 1.5.1 round 4: no cd tracking. Any cd/pushd/popd/chdir word (or env -C) makes the dir unknown, so a
    # relative body path fails closed; an absolute literal path is still scanned (F1-F4 of round 3).
    os.symlink(os.path.join(d, "sub"), os.path.join(d, "link"))
    for c in ("cd sub && gh issue comment 5 -F bad.md", "cd sub; gh pr comment 5 -F ok.md",
              "if false; then true; cd sub; fi; gh pr comment 1 -F bad.md", "f() { true; cd sub; }; gh pr comment 1 -F bad.md",
              "for x in; do cd sub; done; gh pr comment 1 -F bad.md", "cd nonexistent; gh pr comment 1 -F bad.md",
              "cd link/..; gh pr comment 1 -F sub/bad.md", "CDPATH=sub cd x; gh pr comment 1 -F ../bad.md",
              "builtin cd sub; gh pr comment 1 -F bad.md", "command cd sub; gh pr comment 1 -F bad.md",
              "\\cd sub; gh pr comment 1 -F bad.md", "pushd sub; gh pr comment 1 -F bad.md",
              "env -C sub gh pr comment 1 -F bad.md", "cd 'plain*' && gh pr comment 123 -F ok.md"):
        assert _unread(c), c
    assert g.check(f"cd sub && gh pr comment 5 -F {d}/sub/ok.md", d) is None
    assert _blocked(f"cd sub && gh pr comment 5 -F {d}/sub/bad.md", d)
    # round 4 (G1-G3): an attached -b value is scanned; env -C in every spelling changes dir; a continuation
    # inside `cd` joins before any detector runs
    for c in (f"gh pr comment 1 '-b{M} review'", f"gh issue comment 1 '-b{M} review'", f"gh pr review 1 --comment '-b{M} review'"):
        assert _blocked(c, d), c
    for c in ("env -Csub gh pr comment 1 -F bad.md", "env --chdir=sub gh pr comment 1 -F bad.md",
              "env -C sub gh pr comment 1 -F bad.md", "c\\\nd sub; gh pr comment 1 -F bad.md"):
        assert _unread(c), c
    # round 5 (H1): a backslash-newline before the mention, quoted or not, still blocks (bash keeps it in
    # single quotes); (H2) an env short cluster holding C changes dir
    for c in (f"gh pr comment 1 --body 'thanks\\\n{M} review'", f'gh pr comment 1 --body "thanks\\\n{M} review"',
              f"gh pr comment 1 --body thanks\\\n{M}", f"gh issue comment 1 -b 'x\\\n{M}'",
              f"gh pr review 1 --comment -b 'x\\\n{M}'"):
        assert _blocked(c, d), c
    for c in ("env -iCsub PATH=/usr/bin gh pr comment 1 -F bad.md", "env -iC sub gh pr comment 1 -F bad.md"):
        assert _unread(c), c
    # rounds 6-7 (J1, K1): env options are not parsed. Every later word may start the command, so no option
    # argument hides `gh`; a --chdir or short option holding C before it makes the dir unknown (conservative)
    keep, chdir = ("--unset=C", "--unset C", "-i", "X=1", "C=sub", "-u gh", "-S", "-i -S"), \
                  ("-iC sub", "-iCsub", "-Csub", "-C sub", "--chdir=sub", "--chdir sub", "env -C sub",
                   "-uC", "-uCACHE", "-SC", "-iuC")
    for c in (f"env -S 'gh' pr comment 1 -b '{M} review'", f"env -S gh pr review 1 --comment -b '{M}'",
              f"env -u gh gh issue comment 1 -b '{M}'", f"env env -C sub gh api repos/o/r/issues/1/comments -f body='{M}'"):
        assert _blocked(c, d), c
    for o in keep + chdir:
        assert _blocked(f'env {o} gh pr comment 1 -b "{M} review"', d), o
        if o not in ("X=1", "C=sub"):
            assert _unread(f"env {o} gh pr comment 1 -F bad.md"), o
    # 1.5.2 (plan step 2, rule B): only `env NAME=value…` keeps dir and root, and `env -C DIR`/`--chdir[=]DIR`
    # keeps the root; any other option or word before gh is unknown, so even an absolute path is not read
    for o in ("X=1", "C=sub"):
        assert g.check(f"env {o} gh pr comment 1 -F sub/ok.md", d) is None, o
    for o in ("X=1", "C=sub", "-C sub", "-Csub", "--chdir=sub", "--chdir sub", "-C sub X=1"):
        assert g.check(f"env {o} gh pr comment 1 -F {d}/sub/ok.md", d) is None, o
    for o in set(keep + chdir) - {"X=1", "C=sub", "-C sub", "-Csub", "--chdir=sub", "--chdir sub"}:
        assert _unread(f"env {o} gh pr comment 1 -F {d}/sub/ok.md"), o
    # plan step 2: wrappers. Pinned as blocked: a body file behind any wrapper or root/dir-changing word
    for c in ("env -S 'sudo -R /x' gh pr comment 1 -F /body.md", "env sudo -R /x gh pr comment 1 -F /body.md",
              "sudo env -C d gh pr comment 1 -F /abs/body.md", "sudo -R /x gh pr comment 1 -F /body.md",
              "sudo -D other gh pr comment 1 -F body.md", "timeout -k 5 60 gh pr comment 1 -F /abs/body.md",
              "sudo gh pr comment 1 -F body.md", 'nice gh pr comment 1 -F "$B"', f"sudo gh pr comment 1 -F {d}/sub/ok.md",
              f"command -p gh pr comment 1 -F {d}/sub/ok.md", f"nohup gh pr comment 1 -F {d}/sub/ok.md",
              f"time gh pr comment 1 -F {d}/sub/ok.md", f"exec gh pr comment 1 -F {d}/sub/ok.md",
              f"xargs gh pr comment 1 -F {d}/sub/ok.md", f"command -p env gh pr comment 1 -F {d}/sub/ok.md"):
        assert _unread(c), c
    for c in (f"sudo gh pr comment 1 -b '{M}'", f"timeout 60 gh pr review 1 --comment -b '{M}'",
              f"nice -n 5 gh issue comment 1 -b '{M}'", f"xargs gh api repos/o/r/issues/1/comments -f body='{M}'"):
        assert _blocked(c, d), c
    # pinned as read
    for c in ("gh pr comment 1 -F sub/ok.md", "command gh pr comment 1 -F sub/ok.md", "env X=1 gh pr comment 1 -F sub/ok.md",
              f"env -C sub gh pr comment 1 -F {d}/sub/ok.md", f"(sudo true) && gh pr comment 1 -F {d}/sub/ok.md"):
        assert g.check(c, d) is None, c
    # an approximately decoded $'...' word stays unresolved after the =@ split (F5)
    assert _unread("gh api repos/o/r/issues/1/comments -F $'body=@sub/bad\\x2emd'")
    # a file too large to scan whole fails closed instead of scanning a prefix (F6)
    Path(d, "big.json").write_text(" " * g.MAX_BODY_FILE + '{"body":"' + M + ' review"}')
    assert "too large to scan" in (g.check("gh api repos/o/r/issues/1/comments --input big.json", d) or "")
    assert g.check("gh api repos/o/r/issues/1/comments --input big.json  # codex-review-ok: Matt asked", d) is None
    # a value consumed by --body is text, never a flag (P1-2)
    for c in ("gh pr comment 123 --body '--body-file=$BODY is the syntax'", "gh pr comment 123 -b '-F $X'",
              "gh api repos/o/r/issues/1/comments -f body='--input $B'"):
        assert g.check(c, d) is None, c
    # GET exemption (1.5.2, plan step 3): only when the effective method (the last -X/--method in any spelling)
    # is the literal GET are body files skipped; pflag parses short-flag clusters (F1)
    for c in ("gh api repos/o/r/issues/123/comments -X GET -iXPOST -F body=@sub/bad.md",
              "gh api repos/o/r/issues/5/comments -iF body=@sub/bad.md", "gh api repos/o/r/issues/5/comments -iFbody=@sub/bad.md",
              'gh api -X POST repos/o/r/issues/1/comments -F body=@"$B"', "gh pr comment 5 -eF sub/bad.md",
              'gh api -X "$M" repos/o/r/issues -F labels=@"$F"', 'gh api repos/o/r/issues -F labels=@"$F"',
              'gh api -X get repos/o/r/issues -F labels=@"$F"', 'gh api --method=GET -XPOST repos/o/r/issues -F b=@"$F"',
              'gh api -X GET --method POST repos/o/r/issues --input "$B"', "gh api -X GET -X$'POST' repos/o/r -F b=@sub/bad.md"):
        assert _any(c), c
    # the two allowed flips (test_pr_guard_parity.py ALLOWED_FLIPS)
    for c in ('gh api -X GET repos/o/r/issues -F labels=@"$LABEL_FILE"', 'gh api -X GET repos/o/r/issues --input "$B"',
              "gh api -X GET repos/o/r/issues -F q=@sub/ok.md"):
        assert g.check(c, d) is None, c
    # every spelling of an effective GET drops the body files; a clean file keeps these out of the flip list
    _files = lambda c: [f for _, _, fs in g.comment_posts(c, d) for f in fs]
    for m in ("-X GET", "-XGET", "--method=GET", "--method GET", "-iXGET", "-XPOST --method GET", "--method=POST -XGET"):
        assert _files(f"gh api {m} repos/o/r/issues -F l=@sub/ok.md") == [], m
    for m in ("", "-X POST", "-XGET -XPOST", "-X GET --method=POST", '-X "$M"', "-X get", "-X GET -iXPOST"):
        assert _files(f"gh api {m} repos/o/r/issues -F l=@sub/ok.md") == ["sub/ok.md"], m
    assert _blocked(f"gh api -X GET repos/o/r/issues -f q='{M}'", d)  # an inline field is still scanned
    # single-quote continuation (1.5.2, plan step 3): the shell keeps backslash-newline inside single quotes, so a
    # handle split there posts no mention; split in double quotes or unquoted, it joins and blocks
    for k in range(1, len(M)):
        a, b = M[:k], M[k:]
        assert g.check(f"gh pr comment 1 --body '{a}\\\n{b} review'", d) is None, k
        assert _blocked(f'gh pr comment 1 --body "{a}\\\n{b} review"', d), k
        assert _blocked(f"gh pr comment 1 --body {a}\\\n{b}", d), k
        # quoting the scan can't follow joins everything (fails closed)
        assert _blocked(f"gh pr comment 1 --body \"$(echo '{a}\\\n{b}')\"", d), k

print("ok")

# Codex on prevost #332: the fork check uses the dir `gh pr create` runs in, not the hook cwd.
seen = []
g.unpinned_fork = lambda d: seen.append(d)
def forks(c):
    seen.clear()
    assert g.check(c, "/hook") is None
    return list(seen)
assert forks("cd /some/fork && gh pr create --title x") == ["/some/fork"]
assert forks("(cd /some/fork && gh pr create --title x) && gh pr create -R o/r --title y") == ["/some/fork"]
assert forks("gh pr create --title x") == ["/hook"]
assert forks('cd "$DIR" && gh pr create --title x') == []
# Codex high P1 on PR #127: behind a wrapper the dir is unknown, so `gh pr create` needs -R (no fork lookup).
for c in ("command -- gh pr create --title x --body x", "sudo gh pr create --title x", "env -i gh pr create --title x"):
    assert "behind a wrapper" in (g.check(c, "/hook") or ""), c
    assert forks(c.replace("gh pr create", "gh pr create -R o/r")) == [], c
assert forks("env FOO=1 gh pr create --title x") == ["/hook"]  # env NAME=value keeps the dir known
# Codex high P1 on PR #127 round 2: an argument that splits to `)` can't close a real subshell scope.
assert forks("(cd /fork && env printf ' )'; gh pr create --title x --body x)") == ["/fork"]
assert forks("(cd /fork && env printf ')'; gh pr create --title x --body x)") == ["/fork"]
# Codex P2 on prevost #332: `env` and NAME=value prefixes don't hide the command.
# 1.5.2 rule B: env with an option, or any other wrapper, leaves the dir unknown (blocked as unresolved)
assert calls("GIT_DIR=x env -i FOO=1 git merge origin/main") == [("$WRAPPER", "merge", ["origin/main"])]
assert calls("env -u HOME git -C wt rebase origin/main") == [("$WRAPPER/wt", "rebase", ["origin/main"])]
assert calls("GIT_DIR=x env FOO=1 git merge origin/main") == [("/r", "merge", ["origin/main"])]
# Codex high P2 on PR #127: an absolute -C behind a wrapper keeps the unknown root (sudo -R chroots).
assert calls("sudo -R /jail git -C /repo merge origin/main") == [("$WRAPPER//repo", "merge", ["origin/main"])]
# Codex high P2 on PR #127: a quoted or attached split string is split and every word tried as the command.
for c in ("env -S 'gh pr merge' 1 --admin", "env --split-string='gh pr merge' 1 --admin",
          "env -Sgh pr merge 1 --admin", "env '-Sgh pr merge' 1 --admin"):
    assert "--admin" in merge(c, rollup=ok), c
assert _blocked(f"env -S 'gh pr comment 1' -b '{M} review'")
assert _blocked(f"env -S 'gh pr comment 1 -b' '{M} review'")
# round 2: an argument can't forge a scope bound or the wrapper marker (identity sentinels).
assert calls("(cd wt && env printf ' )'; git merge origin/main)") == [("/r/wt", "merge", ["origin/main"])]
assert calls("(cd wt && env printf ' ) ('; git merge origin/main); git merge origin/main") == [
    ("/r/wt", "merge", ["origin/main"]), ("/r", "merge", ["origin/main"])]
assert g.wrapped_words("-S'gh pr' x") == ["gh pr", "x"] and g.wrapped_words("plain") == ["plain"]
# 1.5.5 (nevar-content #17, claude-skills #132): an env split-string option blocks on sight, any path or form.
SPLIT = "`env -S` / `--split-string`"
for c in ("env -S 'gh\\_pr\\_merge' 1 --admin", "env '-Sgh\\_pr\\_merge' 1 --admin",
          "env --split-string='gh\\_pr\\_merge' 1 --admin", "env -S 'gh\\c' pr merge 1 --admin",
          "env -S \"env X='\\c' gh\\c\" pr merge 1 --admin", "env -S '${GHCMD}' pr merge 17 --admin",
          "/usr/bin/env -S'gh pr merge 17 --admin'", "env -vS'gh pr merge 17 --admin'",
          "env -S 'env -S \"gh pr merge 17 --admin\"'", "env -S \"`printf gh` pr merge 17 --auto\"",
          "env -iS x", "env -uXS x", "env -uC -S x", "env -iu X -S x", "env --unset X -S x", "env -u X -S x", "env --sp=x", "env --split-string x",
          "sudo env -S x", "sudo /usr/bin/env -S x", "nice -n 5 env -S x", "env -S 'gh\\_pr\\_view' 1",
          "env \"$OPT\" gh pr view 1"):
    assert g.env_split_string(c) and merge(c, rollup=ok), c
assert SPLIT in merge("env -S 'gh pr view 1'", rollup=ok)
for c in ("echo env -S '${GHCMD}'", "printf '%s' env -S 'a\\tb'", "env printf '%s' -S '${GHCMD}'",
          "env FOO=1 gh pr view 1", "env -u S gh pr view 1", "env -C /tmp gh pr view 1",
          "env -- -S", "git commit -S -m 'a\\nb'", "echo env; printf '\\c'"):
    assert not g.env_split_string(c), c
    assert merge(c, rollup=ok) is None, c
# claude-skills #132: a command word is matched by basename, so an absolute path is the same command.
for c in ("/usr/bin/env gh pr merge 1 --admin", "/usr/bin/sudo gh pr merge 1 --admin",
          "/opt/homebrew/bin/gh pr merge 1 --admin", "sudo /opt/homebrew/bin/gh pr merge 1 --admin"):
    assert "--admin" in merge(c, rollup=ok), c
assert merge("env FOO=1 gh pr view 1", rollup=ok) is None
assert merge("gh pr merge 5 --squash --match-head-commit " + "a" * 40 + " -R owner/repo", rollup=ok) is None
assert calls("command git merge origin/main") == [("/r", "merge", ["origin/main"])]
_ps, g.pr_state = g.pr_state, lambda d: ("main", "CLEAN")
for c in ("env git merge origin/main", "command git merge origin/main", "sudo git pull origin main",
          "timeout 60 git rebase origin/staging"):
    assert g.check(c, "/r") is not None, c
g.pr_state = _ps
assert "--match-head-commit" in (g.check("xargs gh pr merge", "/r") or "")
assert g.draft_violation("GH_TOKEN=x env gh pr create --draft")
assert "--admin" in merge("GH_TOKEN=x gh pr merge 5 --admin", rollup=ok)
assert calls("echo a=b; git merge origin/main") == [("/r", "merge", ["origin/main"])]  # only a leading assignment
# Codex P2 on prevost #332: cd options and `--` come before the directory operand.
assert calls("cd -P wt && git merge origin/main") == [("/r/wt", "merge", ["origin/main"])]
assert calls("cd -- wt && git merge origin/main") == [("/r/wt", "merge", ["origin/main"])]
# Codex P2s on prevost #332, round 5: directory changes the guard can't model fail closed instead of being ignored.
assert calls("cd - && git merge origin/main") == [("$OLDPWD", "merge", ["origin/main"])]
assert calls("cd && git merge origin/main") == [("$HOME", "merge", ["origin/main"])]
assert calls("pushd wt && git merge origin/main") == [("$DIRSTACK", "merge", ["origin/main"])]
# `env -C DIR cmd` runs that one command in DIR; the next command is back in the original directory.
assert calls("env -C wt git merge origin/main; git merge origin/main") == [("/r/wt", "merge", ["origin/main"]), ("/r", "merge", ["origin/main"])]
assert calls("env --chdir=wt git merge origin/main") == [("/r/wt", "merge", ["origin/main"])]
assert g.draft_violation("env -C wt gh pr create --draft")
# Codex P2s on prevost #332, round 6: pflag bool values on the draft flags, and the override is a comment, not a substring.
assert g.draft_violation("gh pr create --draft=true") and g.draft_violation("gh pr create -d=1")
assert g.draft_violation("gh pr ready 5 --undo=true")
assert not g.draft_violation("gh pr create --draft=false") and not g.draft_violation("gh pr ready 5 --undo=false")
assert g.check("git commit -m 'document sync-base: behavior' && git -C wt/$w merge origin/staging", "/r") is not None
assert g.check("git -C wt/$w merge origin/staging # sync-base: need abc123", "/r") is None

# nevar-fund #24 Codex P1: the `command` builtin runs its operand, so `command [-p] [--] gh …` is `gh …`.
for pre in ("command ", "command -p ", "command -- ", "command -p -- "):
    assert "--admin" in merge(pre + "gh pr merge 5 --admin --squash", rollup=ok), pre
    assert g.draft_violation(pre + "gh pr create --draft"), pre
    # 1.5.2 rule B: only a plain `command` keeps the dir known
    assert calls(pre + "git merge origin/main") == [("/r" if pre == "command " else "$WRAPPER", "merge", ["origin/main"])], pre
# `command -v`/`-V` only look the name up; nothing runs.
assert calls("command -v git merge origin/main") == []
assert not g.draft_violation("command -V gh pr create --draft")


# ---- 1.6.0: required checks must pass, only pinned advisory checks may be red ----
# plans/2026-11-22-pr-guard-required-vs-advisory-checks.md (revision 2). Test numbers follow the plan.
PIN = "gh pr merge 5 --squash --match-head-commit " + HEAD_SHA
_nid = iter(range(3000, 10**6))
def ck(name, concl="SUCCESS", wf="CI", at="2026-11-22T10:00:00Z", run_id=None, job_id=None):
    """One Actions job in the rollup. Its workflow file follows wf (the stub's rule): CI -> ci.yml,
    Review Gate Doctor -> review-gate-doctor.yml. Each call is its own run unless run_id is given."""
    return {"name": name, "workflowName": wf, "conclusion": concl, "startedAt": at,
            "detailsUrl": f"https://github.com/o/r/actions/runs/{run_id or next(_nid)}/job/{job_id or next(_nid)}"}
def rid(e):
    return g.RUN_ID.search(e["detailsUrl"]).group(1)
def guard(rollup, notes=None, cmd=PIN, **kw):
    g.subprocess.run = _gh(rollup=rollup, **kw)
    try:
        return g.check(cmd, "/r", notes)
    finally:
        g.subprocess.run = _run
DOCTOR_PATH = ".github/workflows/review-gate-doctor.yml"
ADVISORY_NOTE = f"advisory check doctor is FAILURE (pinned advisory: {DOCTOR_PATH}); not blocking"
LOOKUP = "required-check lookup unavailable: "
RULESET_GATE = [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "Review Gate"}]}},
                {"type": "pull_request", "parameters": {}}]
EMPTY = {"schema": 1, "required": []}
TB_CI = {"schema": 1, "required": [{"name": "Test & Build", "workflow": ".github/workflows/ci.yml", "event": "pull_request"}]}
gate = ck("Review Gate", wf="Review Gate")
doctor_red = ck("doctor", "FAILURE", wf="Review Gate Doctor")
doctor_ok = ck("doctor", wf="Review Gate Doctor")

# Mock validation: the stub's GitHub shapes match responses recorded from the real API (fixtures/github-recorded.json).
REC = json.loads((Path(__file__).parent / "fixtures" / "github-recorded.json").read_text())
for key, (status, message) in {"contents_not_found": (404, "Not Found"), "branch_not_protected": (404, "Branch not protected")}.items():
    real, stub = REC["errors"][key], _gh_error(status, message)
    assert (real["rc"], real["stderr"]) == (stub.returncode, stub.stderr), (key, real, stub.stderr)
    assert set(json.loads(real["stdout"])) == set(json.loads(stub.stdout)), key
    assert {k: v for k, v in json.loads(real["stdout"]).items() if k != "documentation_url"} == \
        {k: v for k, v in json.loads(stub.stdout).items() if k != "documentation_url"}, key
def _replay(rows):
    """gh replaying the recorded check-runs body for the recorded head, through the guard's own --jq."""
    def run(args, *a, **k):
        assert args[:2] == ["gh", "api"] and "/check-runs?filter=all" in next(x for x in args if x.startswith("repos/")), args
        return _jq(args, rows, 0)
    return run
_view = {"headRefOid": REC["head_sha"], "url": "https://github.com/o/r/pull/5"}
g.subprocess.run = _replay(REC["check_runs"])
try:
    _h = g.Head.__new__(g.Head)
    _h.view, _h.cwd, _h.deadline, _h.sha = _view, None, g.time.monotonic() + 15, REC["head_sha"]
    _h.failed, _h.jobs, _h._runs = [], {}, None
    # Every real Actions job in the real rollup authenticates against the real check-runs list (re-attempts included).
    assert all(_h.ident(e) for e in REC["rollup"]), REC["rollup"]
    recorded = {tuple(r) for r in _h.check_runs()}
finally:
    g.subprocess.run = _run
g.subprocess.run = _gh(rollup=[dict(e) for e in REC["rollup"]])
try:
    _s = g.Head({"headRefOid": HEAD_SHA, "url": "https://github.com/o/r/pull/5"}, None, g.time.monotonic() + 15)
    synthesized = {tuple(r) for r in _s.check_runs()}
finally:
    g.subprocess.run = _run
assert synthesized <= recorded, synthesized - recorded  # the stub's rule (id = job id, app 15368) is GitHub's
g.subprocess.run = _gh(rollup=[gate], rules=REC["rules"], protection=REC["classic_protection"])
try:
    _s = g.Head({"headRefOid": HEAD_SHA, "url": "https://github.com/o/r/pull/5"}, None, g.time.monotonic() + 15)
    assert g.branch_required(_s, "main") == {("Review Gate", None), ("continuous-integration/travis-ci", None)}
    assert _s.failed == [], _s.failed
finally:
    g.subprocess.run = _run

# 1. The incident (nevar-aec-catalog #14): ruleset requires Review Gate (green), empty policy file, pinned doctor red.
notes = []
assert guard([gate, doctor_red], notes, policy=EMPTY, rules=RULESET_GATE) is None
assert notes == [ADVISORY_NOTE], notes

# 2. No policy file (404): today's 1.5.x block, no lookup line, and no rules or protection calls (round-3 P2 #1).
calls_seen = []
m = guard([gate, doctor_red], rules=RULESET_GATE, calls=calls_seen)
assert m == ("Blocked: checks are not all green for 5 (doctor: FAILURE): wait for them "
             "(`gh pr checks <n> --watch --fail-fast` in the background) or fix the red check, then merge."), m
assert "lookup" not in m and "advisory" not in m
assert not [c for c in calls_seen if any("/rules/" in x or "/protection/" in x for x in c)], calls_seen
notes = []
assert guard([gate, doctor_ok], notes) is None and notes == []

# 3. A non-required red that is not on the advisory list still blocks.
for name in ("Test & Build", "Security Scan", "CodeQL"):
    m = guard([gate, ck(name, "FAILURE")], policy=EMPTY, rules=RULESET_GATE)
    assert m and f"{name}: FAILURE" in m and "advisory" not in m, (name, m)

# 4. Forged advisory: the name alone earns nothing.
m = guard([gate, ck("doctor", "FAILURE", wf="Evil")], policy=EMPTY, rules=RULESET_GATE)  # .github/workflows/evil.yml
assert m and "doctor: FAILURE" in m and "advisory" not in m, m
push_doc = ck("doctor", "FAILURE", wf="Review Gate Doctor")
m = guard([gate, push_doc], policy=EMPTY, rules=RULESET_GATE, events={rid(push_doc): "push"})  # right path, wrong event
assert m and "doctor: FAILURE" in m and "advisory" not in m, m
copy = dict(doctor_red)  # its own check run copying the real doctor's job URL, name and conclusion
m = guard([gate, doctor_red, copy], policy=EMPTY, rules=RULESET_GATE, forged=(copy,))
assert m and m.count("doctor: FAILURE") == 2 and "advisory" not in m, m  # the real doctor loses its exemption too
third_party = dict(doctor_red, _app=4242)  # right URL, published by another app: not the Actions job
m = guard([gate, third_party], policy=EMPTY, rules=RULESET_GATE)
assert m and "doctor: FAILURE" in m and "advisory" not in m, m

# 4a. Forged supersede, the exact round-2 attack (round-3 P2 #2), in every mode: run A's build is green; the newer
# run B's build failed and its lint passed. A separate green check run copies B's lint job URL, name and conclusion
# with a writable started_at of 2000. On 1.5.4 that dragged run B's start before run A's, so B's failed build was
# discarded and A's green build satisfied the check. The forged entry fails identity, so it moves no run start.
build_a = ck("build", "SUCCESS", at="2026-11-22T10:00:00Z", run_id=4100, job_id=4101)
build_b = ck("build", "FAILURE", at="2026-11-22T10:10:00Z", run_id=4200, job_id=4201)
lint_b = ck("lint", "SUCCESS", at="2026-11-22T10:10:00Z", run_id=4200, job_id=4202)
lint_forged = dict(lint_b, startedAt="2000-01-01T00:00:00Z")
pinned_build = {"schema": 1, "required": [{"name": "build", "workflow": ".github/workflows/ci.yml", "event": "pull_request"}]}
for mode in ({}, {"policy": EMPTY, "rules": RULESET_GATE}, {"policy": pinned_build, "rules": RULESET_GATE}):
    m = guard([gate, build_a, build_b, lint_b, lint_forged], forged=(lint_forged,), **mode)
    assert m and "build: FAILURE" in m, (mode, m)
    # ...and with the check-runs call failing nothing authenticates, so nothing collapses: B's failed build blocks.
    m = guard([gate, build_a, build_b, lint_b], cr=_gh_error(500, "Server Error"), **mode)
    assert m and "build: FAILURE" in m, (mode, m)
    # The outage is named in every mode, also without a policy file: it is why nothing collapsed.
    assert LOOKUP + "check-runs 500 Server Error; using the all-green rule" in m, (mode, m)
assert guard([gate, build_a, build_b, lint_b, lint_forged], forged=(lint_forged,), cmd=PIN + " # codex-review-ok: x")
# The control: without the forgery, a newer green build in run B supersedes run A's failure.
assert guard([gate, ck("build", "FAILURE", at="2026-11-22T10:00:00Z", run_id=4300), ck("build", at="2026-11-22T10:10:00Z", run_id=4400)],
             policy=pinned_build, rules=RULESET_GATE) is None

# 5. On the advisory list but required (ruleset or policy file): blocks.
both = [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "Review Gate"}, {"context": "doctor"}]}}]
m = guard([gate, doctor_red], policy=EMPTY, rules=both)
assert m and "doctor: FAILURE" in m and "required check doctor is FAILURE" in m and "advisory" not in m, m
m = guard([gate, doctor_red], rules=RULESET_GATE,
          policy={"schema": 1, "required": [{"name": "doctor", "workflow": DOCTOR_PATH, "event": "pull_request"}]})
assert m and "required check doctor is FAILURE" in m and "advisory" not in m, m

# 6. A required check missing from the rollup blocks.
m = guard([gate], policy=TB_CI, rules=RULESET_GATE)
assert m and f"required check Test & Build is MISSING on {HEAD_SHA}" in m, m

# 7. A required pin that is not satisfied counts as missing.
m = guard([gate, ck("Test & Build", wf="Other")], policy=TB_CI, rules=RULESET_GATE)  # a PR-added other.yml
assert m and "required check Test & Build is MISSING" in m, m
APP = {"schema": 1, "required": [{"name": "Deploy preview", "app_id": 4242}]}
preview = {"name": "Deploy preview", "conclusion": "SUCCESS", "detailsUrl": "https://deploy.example/p/5"}
m = guard([gate, dict(preview, _app=99)], policy=APP, rules=RULESET_GATE)
assert m and "required check Deploy preview is MISSING" in m, m
m = guard([gate, {"context": "Deploy preview", "state": "SUCCESS"}], policy=APP, rules=RULESET_GATE)  # status contexts: no app
assert m and "required check Deploy preview is MISSING" in m, m
assert guard([gate, dict(preview, _app=4242)], policy=APP, rules=RULESET_GATE) is None
m = guard([gate, ck("Review Gate", wf="Spoof")], policy=EMPTY, rules=[  # ruleset integration_id pins the app
    {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "Review Gate", "integration_id": 4242}]}}])
assert m and "required check Review Gate is MISSING" in m, m

# 7a. Classic protection lists a checks[] pin in legacy contexts[] too (as the recorded body does): the pin alone
# decides, so a same-named SKIPPED check from another app does not block (review thread r4658452439).
CLASSIC_PINNED = dict(REC["classic_protection"], checks=[dict(REC["classic_protection"]["checks"][0], app_id=4242)])
travis = {"name": "continuous-integration/travis-ci", "conclusion": "SUCCESS", "detailsUrl": "https://travis.example/b/5"}
other_app = dict(travis, conclusion="SKIPPED", detailsUrl="https://other.example/c/5", _app=99)
g.subprocess.run = _gh(rollup=[gate], protection=CLASSIC_PINNED)
try:
    _s = g.Head({"headRefOid": HEAD_SHA, "url": "https://github.com/o/r/pull/5"}, None, g.time.monotonic() + 15)
    assert g.branch_required(_s, "main") == {("continuous-integration/travis-ci", ("app", 4242))}
finally:
    g.subprocess.run = _run
assert guard([gate, dict(travis, _app=4242), other_app],
             policy=EMPTY, rules=RULESET_GATE, protection=CLASSIC_PINNED) is None
m = guard([gate, other_app], policy=EMPTY, rules=RULESET_GATE, protection=CLASSIC_PINNED)
assert m and "required check continuous-integration/travis-ci is MISSING" in m, m  # the pin is still required

# 8. A required check must be SUCCESS: pending, cancelled, skipped and neutral each block and name the state.
for concl, state in (("", "PENDING"), ("CANCELLED", "CANCELLED"), ("SKIPPED", "SKIPPED"), ("NEUTRAL", "NEUTRAL")):
    m = guard([gate, ck("Test & Build", concl)], policy=TB_CI, rules=RULESET_GATE)
    assert m and f"required check Test & Build is {state} on {HEAD_SHA}" in m, (concl, m)
m = guard([gate, ck("Test & Build", run_id=4500), ck("Test & Build", "SKIPPED", run_id=4500)], policy=TB_CI, rules=RULESET_GATE)
assert m and "required check Test & Build is SKIPPED" in m and "is SUCCESS" not in m, m  # the matrix sibling

# 9. A superseded run: the newest run of a required job decides; two failed doctor runs stay advisory.
assert guard([gate, ck("Test & Build", "FAILURE", at="2026-11-22T10:00:00Z"), ck("Test & Build", at="2026-11-22T10:10:00Z")],
             policy=TB_CI, rules=RULESET_GATE) is None
m = guard([gate, ck("Test & Build", at="2026-11-22T10:00:00Z"), ck("Test & Build", "FAILURE", at="2026-11-22T10:10:00Z")],
          policy=TB_CI, rules=RULESET_GATE)
assert m and "required check Test & Build is FAILURE" in m, m
notes = []
assert guard([gate, ck("doctor", "FAILURE", wf="Review Gate Doctor", at="2026-11-22T10:00:00Z"),
              ck("doctor", "FAILURE", wf="Review Gate Doctor", at="2026-11-22T10:10:00Z")], notes,
             policy=EMPTY, rules=RULESET_GATE) is None
assert notes == [ADVISORY_NOTE], notes  # one line: the older run is superseded

# 10. Every lookup failure turns the advisory exemption off, names itself, and changes nothing when all is green.
FAIL = {
    "rules exit (network)": ({"rules": _R(1, "", "error connecting to api.github.com")}, "rules error connecting"),
    "rules 403": ({"rules": _gh_error(403, "Resource not accessible by integration")}, "rules 403 Resource not accessible"),
    "rules 404 other": ({"rules": _gh_error(404, "Not Found")}, "rules 404 Not Found"),
    "protection 403": ({"protection": _gh_error(403, "Resource not accessible by integration")}, "classic protection 403"),
    "protection 404 other": ({"protection": _gh_error(404, "Branch not found")}, "classic protection 404 Branch not found"),
    "rules malformed JSON": ({"rules": _R(0, "not json\n")}, "rules malformed JSON"),
    "protection missing fields": ({"protection": {"url": "x"}}, "classic protection malformed response"),
    "rules truncated page": ({"rules": _R(1, '["pull_request",null]\n', "gh: Server Error (HTTP 502)")}, "rules gh: Server Error"),
    "rule lists no checks": ({"rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": []}}]},
                             "rules a required_status_checks rule lists no checks"),
    "rule without parameters": ({"rules": [{"type": "required_status_checks"}]}, "rules a required_status_checks rule lists no checks"),
    "policy 403": ({"policy": _gh_error(403, "Resource not accessible by integration")}, ".github/required-checks.json 403"),
    "policy 500": ({"policy": _gh_error(500, "Server Error")}, ".github/required-checks.json 500 Server Error"),
    "policy nested too deep": ({"policy": "[" * 1000000 + "]" * 1000000}, ".github/required-checks.json malformed: "),
    "check-runs 500": ({"cr": _gh_error(500, "Server Error")}, "check-runs 500 Server Error"),
}
for case, (kw, line) in FAIL.items():
    kw = {"policy": EMPTY, "rules": RULESET_GATE, **kw}
    m = guard([gate, doctor_red], **kw)
    assert m and "doctor: FAILURE" in m and LOOKUP + line in m and "using the all-green rule" in m and "advisory" not in m, (case, m)
    notes = []
    assert guard([gate, doctor_ok], notes, **kw) is None and notes == [], case
# 4i (a rollup that cannot be confirmed complete) has no signal to test: a missing required check reports MISSING,
# and the exemption only ever applies to an entry that is present, so a truncated rollup cannot exempt a hidden red.

# 10a. A partial failure keeps what did resolve.
m = guard([gate, doctor_ok], policy=TB_CI, rules=_gh_error(403, "Resource not accessible by integration"))
assert m and "required check Test & Build is MISSING" in m and LOOKUP + "rules 403" in m, m
m = guard([ck("Test & Build")], policy=_gh_error(403, "Resource not accessible by integration"), rules=RULESET_GATE)
assert m and "required check Review Gate is MISSING" in m and LOOKUP + ".github/required-checks.json 403" in m, m

# 11. A malformed policy file is a failed lookup that names the file and the problem.
for doc, problem in (({"schema": 2, "required": []}, "unknown schema 2"), ({"schema": True, "required": []}, "unknown schema True"),
                     ({"required": []}, "unknown schema None"),
                     ({"schema": 1, "required": [{"name": "x"}]}, "entry 'x' needs exactly one pin"),
                     ({"schema": 1, "required": [{"name": "x", "app_id": 1, "workflow": "w", "event": "e"}]}, "entry 'x' needs exactly one pin"),
                     ({"schema": 1, "required": [{"name": "x", "workflow": "w"}]}, "entry 'x' needs exactly one pin"),
                     ({"schema": 1, "required": [{"name": "x", "app_id": "1"}]}, "entry 'x' needs exactly one pin"),
                     ({"schema": 1, "required": [], "advisory": ["build"]}, "unknown key 'advisory'"),
                     ({"schema": 1, "required": [{"name": "x", "app_id": 1, "exempt": True}]}, "entry 'x' has unknown key 'exempt'"),
                     ({"schema": 1, "required": [{"name": "x", "app_id": 1}, {"name": "x", "app_id": 2}]}, "conflicting pins"),
                     ({"schema": 1, "required": {"x": 1}}, "required is not a list"),
                     ({"schema": 1, "required": [{"app_id": 1}]}, "an entry has no name"),
                     ([], "not a JSON object"), ("{not json", "malformed: ")):
    m = guard([gate, doctor_red], policy=doc, rules=RULESET_GATE)
    assert m and "doctor: FAILURE" in m and LOOKUP + ".github/required-checks.json malformed: " in m and problem in m, (doc, m)
assert g.parse_policy({"schema": 1, "required": [{"name": "x", "app_id": 1}, {"name": "x", "app_id": 1}]}) == {("x", ("app", 1))}

# 12. Output channel: on an allowed merge the advisory line reaches the model as PreToolUse additionalContext JSON
# (plain exit-0 stdout does not: code.claude.com/docs/en/hooks), through the real main().
import contextlib, io
def hook(cmd, **kw):
    g.subprocess.run = _gh(**kw)
    out, err, stdin = io.StringIO(), io.StringIO(), g.sys.stdin
    g.sys.stdin = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": "/r"}))
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = g.main()
    finally:
        g.subprocess.run, g.sys.stdin = _run, stdin
    return rc, out.getvalue(), err.getvalue()
rc, out, err = hook(PIN, rollup=[gate, doctor_red], policy=EMPTY, rules=RULESET_GATE)
assert rc == 0 and err == "" and json.loads(out) == {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ADVISORY_NOTE}}, (rc, out, err)
assert hook(PIN, rollup=[gate, doctor_ok], policy=EMPTY, rules=RULESET_GATE) == (0, "", "")
rc, out, err = hook(PIN, rollup=[gate, doctor_red], rules=RULESET_GATE)
assert rc == 2 and out == "" and "doctor: FAILURE" in err, (rc, out, err)

# 13. No bypass: override comments and environment variables leave tests 3-8 blocked.
BLOCKED = [([gate, ck("Test & Build", "FAILURE")], {"policy": EMPTY}), ([gate, ck("doctor", "FAILURE", wf="Evil")], {"policy": EMPTY}),
           ([gate, doctor_red], {"policy": EMPTY, "rules": both}), ([gate], {"policy": TB_CI}),
           ([gate, ck("Test & Build", wf="Other")], {"policy": TB_CI}), ([gate, ck("Test & Build", "SKIPPED")], {"policy": TB_CI})]
for suffix in (" # advisory-ok: doctor", " # codex-review-ok: x", " # sync-base: need abc"):
    for rollup, kw in BLOCKED:
        assert guard(rollup, cmd=PIN + suffix, **{"rules": RULESET_GATE, **kw}), (suffix, rollup)
for prefix in ("ADVISORY_OK=1 ", "PR_GUARD_ALLOW_RED=1 ", "env SKIP_CHECKS=1 "):
    for rollup, kw in BLOCKED:
        assert guard(rollup, cmd=prefix + PIN, **{"rules": RULESET_GATE, **kw}), (prefix, rollup)

# 14. Deny-list: tests, builds, security scans and Review Gate are never advisory.
assert g.ADVISORY_CHECKS == (("doctor", DOCTOR_PATH, "pull_request"),)
for name, path, event in g.ADVISORY_CHECKS:
    assert name not in ("Review Gate", "Security Scan") and not re.search(r"test|build|codeql|security|review.gate", name, re.I), name
    assert path.startswith(".github/workflows/") and event in ("pull_request", "pull_request_target", "push"), (path, event)

# 16. The policy comes from the default branch: a PR into a contributor-made base cannot pick its own copy. The stub
# asserts the contents call carries no ref, and the base's rules are read with the base's name encoded.
calls_seen = []
m = guard([gate, doctor_ok], policy=TB_CI, rules=RULESET_GATE, base="release/x y", calls=calls_seen)
assert m and "required check Test & Build is MISSING" in m, m
assert not [c for c in calls_seen if "/contents/" in " ".join(c) and "ref" in " ".join(c)], calls_seen


def test_pr_guard():
    """pytest entry point: the asserts above run at import, so a failure is a collection error."""
