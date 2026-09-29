"""Run: python3 pr-merge-flow/tests/test_pr_guard.py  (no framework; exits non-zero on failure)."""
import importlib.util
from pathlib import Path

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
assert g.creates_pr_without_repo("git push && gh pr create --title x")
assert not g.creates_pr_without_repo("gh pr create -R me/r --title x")
assert not g.creates_pr_without_repo("gh pr create --repo=me/r")
# Codex P2s on #37: quoting, continuation, other ref spellings, gh aliases/inherited -R.
assert calls('git merge -m "sync; base" origin/main') == [("/r", "merge", ["origin/main"])]
assert calls("git merge \\\n  origin/staging") == [("/r", "merge", ["origin/staging"])]
assert calls("git merge origin/staging # sync; not a command") == [("/r", "merge", ["origin/staging"])]
assert calls('git commit -m "" && git merge origin/staging') == [("/r", "merge", ["origin/staging"])]
assert calls("if true; then git -C wt rebase origin/main; fi") == [("/r/wt", "rebase", ["origin/main"])]
for ref in ["refs/heads/main", "refs/remotes/upstream/main", "company/main", "refs/remotes/origin/main"]:
    assert g.names_base([ref], "main"), ref
assert not g.names_base(["refs/heads/feat/main-fix", "a/b/main"], "main")
assert g.draft_violation("gh pr create \\\n  --draft --title x")
assert g.draft_violation("gh pr new --draft")
assert g.draft_violation("gh -R owner/repo pr create --draft")
assert not g.draft_violation('gh pr create --title "no --draft; here"')
assert not g.creates_pr_without_repo("gh -R me/r pr create --title x")
assert g.creates_pr_without_repo("gh pr new --title x")
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
# Unparseable input still keeps line boundaries.
assert g.draft_violation("echo 'unterminated\ngh pr create --draft")
print("ok")
