# Roadmap

Plan files in this directory, one line each.

- [Review Gate: add a `cursor` reviewer token](review-gate-cursor-reviewer-token.md): planned; ready to start (PR #105 merged as d876413).
- [pr-guard: superseded-check handling and the `--auto` block message](pr-guard-rollup-and-auto-message.md): planned; review-gate 3.2.8 has shipped, but no code until Matt or the Program Cop says go.
- [pr-guard: stop shell-string parsing from regressing; fix the 1.5.1 false blocks](pr-guard-shell-parsing-design.md): planned; issue #124. Tracker: https://app.notion.com/p/PR-GUARD-PARSE-DESIGN-stop-pr-guard-shell-parsing-regressing-fix-1-5-1-false-blocks-claude-skills-41e4efecc95a81d4a4eaee2e047a64ed (Owner Needs-PM).
- [Review Gate: re-vendor the 17 stale review-gate.yml copies and add the doctor job](review-gate-stale-vendor-fleet.md): planned; stale pre-3.2.10 vendoring blocks merges on cancelled runs. Tracker: https://app.notion.com/p/REVIEW-GATE-STALE-VENDOR-FLEET-41e4efecc95a816488e4ff9fc8dabf7e
- [Tokenizer-first merge guard: one shell tokenizer, decisions on tokens only](2026-11-21-tokenizer-first-merge-guard.md): planned, P1; owed by PR #137. Starts after #131, #132 and #138 merge. Amends the pr-guard shell-parsing plan (#124): one shared tokenizer and one fail-closed hook runtime for pr-guard and merge-guard. The forged-check typed parsing was routed to aec. Tracker: https://app.notion.com/p/TOKENIZER-FIRST-MERGE-GUARD-one-shell-tokenizer-decisions-on-tokens-only-claude-skills-plan-owed-41f4efecc95a8185beeffea8ba1d6bf5
- [Google Docs skill implementation](google-docs-skill-implementation.md)
- Review-gate plans in `docs/superpowers/plans/` are indexed in [docs/superpowers/plans/ROADMAP.md](../docs/superpowers/plans/ROADMAP.md).
