# Plan: pin review-gate's untested fail-closed paths

## Origin

These came from a Sonnet mutation-coverage pass on bernierllc/claude-skills#105 at head 9c51e35. The survivors are on lines that are identical to main, so #105 did not introduce them.

They are rated P1 because the gate would pass when it should fail if any of them regressed. Today the code behaves correctly; no test pins that behaviour.

Tracker: https://app.notion.com/p/review-gate-P2-findings-from-105-Sonnet-pass-a-on-1a2cfc3-41b4efecc95a810594cdf6650b33155f

## Status

Not started. Proposed priority: P1. Land it after #105.

## Gaps

1. `codex_done_on_head` returns False when `headRefOid` is empty. If that flips to True, the gate passes with no Codex review at all.
2. `codex_clean_comment_on_head` has the same no-head guard and the same risk.
3. `run_gh` adds `--hostname <host>` for Enterprise repos. If that argument is dropped, the gate reads the default host's PR with the same number.

## Correct fix (tests only)

1. Add an `evaluate()` case with `headRefOid: ""` and `baseRefName: "staging"`. Give it a Codex review on some commit and a clean comment. Assert that it fails and names the missing Codex review.
2. Point a fake `gh` on PATH that records its argv. Call `run_gh([...], hostname="ghe.example.com")`. Assert that `--hostname ghe.example.com` comes before the endpoint. Then call without a hostname and assert there is no `--hostname`.
3. For each gap, re-run the mutant (the guard returning True, the `--hostname` argument dropped) and show that the suite now fails.

Also add the P2 survivors from the same pass, each as a one-line assert:

- CRLF in `closes()`
- `CODEX_STATE` with `re.S`
- usage errors exit 2
- a second positional PR number is rejected
- `PR_NUMBER` env fallback
- `.git` is stripped
- `www.github.com` is normalized

## Out of scope

Server-side merge enforcement is covered by 2026-11-17-api-merge-guard.md.
