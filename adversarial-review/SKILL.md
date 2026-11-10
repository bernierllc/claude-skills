---
name: adversarial-review
description: Run the adversarial PR review loop with Codex-first spend and inline line-item PR comments. Use whenever you open or push a PR, say a PR is ready, hand work to a traffic cop, need a code review, or fall through reviewers after Codex/agy quota failures. Prefer this skill over remembering review order from AGENTS.md prose.
version: 1.0.0
author: Bernier LLC
---

# Adversarial review

Durable form of `~/.claude/references/pr-review-loop.md`. Agents forget prose; install this skill per repo so the loop is loadable and enforceable alongside `review-gate`.

## Spend posture (Matt, 2026-11-07)

| Role | Model | Notes |
|------|--------|------|
| Coding | Claude Opus → Cursor Auto | Not this skill |
| Traffic cops | Codex mid (`gpt-6-astra`) | See `traffic-cop.md` |
| **Adversarial review (this skill)** | **Codex high first** | Burn OpenAI review budget here |
| Fallthrough | Antigravity (`agy`) → Claude Sonnet last | Record which ran |

## When to run

After opening a PR or pushing commits to one. Never declare "ready" in the same breath as the push. Run reviewers and CI **in parallel**.

## Reviewer order (fall through only when unavailable)

1. **Codex first**
   - **GitHub:** on first open Codex may auto-review; after every later push post `gh pr comment <n> --body "@codex review"` without asking.
   - **T3 parallel local:** `delegate_task` with `modelSelection` `{ "instanceId": "codex", "model": "gpt-6.1-sol" }` against the PR diff.
   - Unavailable: quota exhausted, not started within ~15 min of first request, or absent from the repo.
2. **Antigravity (`agy`) headless** — outside Claude tokens. Inline the diff in the prompt; `--sandbox --dangerously-skip-permissions --model gemini-3.8-flash-high`. See `pr-review-loop.md` for the verified command shape.
3. **Claude Sonnet / `superpowers:requesting-code-review`** — last resort only.

Standing consent: switch providers on unavailability without asking Matt again. No new subscriptions or weaker merge gates.

## Inline comments (required)

Every P0/P1 finding must become a **GitHub review thread on the relevant line**, not only a summary comment.

- Prefer `gh api graphql` / `POST /repos/{owner}/{repo}/pulls/{n}/comments` with `commit_id`, `path`, `line` (or `subject_type` + multi-line fields as appropriate).
- Summary sticky comment is fine **in addition** for the round overview; it does not replace line threads.
- P2: one-line each; fix ≤10 lines in touched files or Tracker row + PR reply with Notion link.

Every review brief opens with the redundancy question: *does this reimplement something the framework, a dependency, or this repo already provides?*

## Severity and convergence

- **P0/P1:** fix at root before merge.
- **P2:** ≤10-line fix in touched files, else Tracker + closing reply.
- **Nit:** answer or ignore; never a new round.
- Done when a round has **no new P0/P1**.
- One push per round. Cap: third P0/P1 in the same area → simplify or plan, tell Matt.

## PR body

Maintain a `## Review` section naming which reviewer ran and the round count. Fallback reviewers (`agy`, `superpowers`) must be named when Codex did not run.

## Plan / spec PRs

One local adversarial pass **before** the first Codex review (exhaust pipeline/state/schema/auth/deploy/frontend/cross-plan classes). Then Codex.

## After the loop

In T3: hand the PR to `Traffic Cop · <repo>` (`traffic-cop.md`). Do not self-merge around a missing cop.

Install **`review-gate`** in the same repos so merge/CI enforcement matches this loop (conversation resolution, gate check, cancel-in-progress CI on new review comments).

## Related

- Full detail / CLI examples: `~/.claude/references/pr-review-loop.md`
- Merge discipline: skill `pr-merge-flow`
- Server + hook enforcement: skill `review-gate`
- Credit failover for stuck threads: `~/.claude/references/credit-failover.md`
