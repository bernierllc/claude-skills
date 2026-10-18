#!/usr/bin/env bash
# Prove the installed commit-msg hook rejects a bad subject and accepts a good one.
# Runs in a throwaway clone of the current repo's hooks dir so nothing is committed here.
set -u
hook=$(git rev-parse --git-path hooks)/commit-msg
[ -x "$hook" ] || { echo "selftest: no executable $hook"; exit 1; }
t=$(mktemp); fail=0
check() { printf '%s\n' "$2" > "$t"; "$hook" "$t" >/dev/null 2>&1; rc=$?; [ "$rc" -eq "$1" ] || { echo "FAIL (want exit $1, got $rc): $2"; fail=1; }; }
check 1 'Bad Subject'
check 1 'Fix: capitalised type'
check 1 'feat(Scope): uppercase scope'
check 1 'feat: Uppercase description'
check 1 'wip'
check 0 'chore(hooks): path-filter the posttooluse hooks (#815)'
check 0 'fix(senders,campaigns): comma scope'
check 0 'feat(api)!: breaking'
check 0 'release: promote staging to main 2026-10-18'
check 0 'Merge branch '"'"'staging'"'"' into feat/x'
check 0 'Revert "feat: thing"'
check 0 $'# comment line\n\nfeat: subject after comments'
rm -f "$t"
[ $fail -eq 0 ] && echo "selftest: commit-msg hook OK"
exit $fail
