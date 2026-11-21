# Roadmap

Plan files in this directory, one line each.

- [Review Gate: add a `cursor` reviewer token](review-gate-cursor-reviewer-token.md): planned; ready to start (PR #105 merged as d876413).
- [pr-guard: superseded-check handling and the `--auto` block message](pr-guard-rollup-and-auto-message.md): planned; review-gate 3.2.8 has shipped, but no code until Matt or the Program Cop says go.
- [pr-guard: stop shell-string parsing from regressing; fix the 1.5.1 false blocks](pr-guard-shell-parsing-design.md): planned; issue #124. Tracker: https://app.notion.com/p/PR-GUARD-PARSE-DESIGN-stop-pr-guard-shell-parsing-regressing-fix-1-5-1-false-blocks-claude-skills-41e4efecc95a81d4a4eaee2e047a64ed (Owner Needs-PM).
- [Review Gate: re-vendor the 17 stale review-gate.yml copies and add the doctor job](review-gate-stale-vendor-fleet.md): planned; stale pre-3.2.10 vendoring blocks merges on cancelled runs. Tracker: https://app.notion.com/p/REVIEW-GATE-STALE-VENDOR-FLEET-41e4efecc95a816488e4ff9fc8dabf7e
- [Google Docs skill implementation](google-docs-skill-implementation.md)
- Review-gate plans in `docs/superpowers/plans/` are indexed in [docs/superpowers/plans/ROADMAP.md](../docs/superpowers/plans/ROADMAP.md).
- [Review Gate doctor: an upstream release must not turn every vendoring repo red](2026-11-21-doctor-latest-release-coupling.md): planned; installed clone-main doctor jobs (15 repos) go red on every release, migrate them and add a declared minimum-version floor. Tracker: https://app.notion.com/p/CS-DOCTOR-LATEST-RELEASE-review-gate-doctor-job-must-not-turn-red-on-an-upstream-release-migrate-t-41f4efecc95a81d7bd93ff2bb0cc62cd
- [pr-merge-flow guard: block only on required checks](2026-11-21-pr-guard-required-vs-advisory.md): planned; resolve the branch's required contexts, advisory red becomes a warning, fail closed when unreadable, no bypass. Lands after #131/#132. Tracker: https://app.notion.com/p/CS-PRGUARD-REQUIRED-VS-ADVISORY-pr-merge-flow-guard-blocks-only-on-the-ruleset-s-required-checks-a-41f4efecc95a81d0b22cd96bbf51034d
