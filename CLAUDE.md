# Claude Skills - Project Instructions

## Stack Information

**Type:** Skill definitions (markdown) plus a few deterministic scripts
**Content:** Claude Code skill definitions (SKILL.md files) organized by category
**Categories:** Algorithmic art, artifacts/webapp builders, brand guidelines, canvas design, document formats (docx, xlsx, pdf, pptx), frontend design, internal comms, MCP builder, Slack GIF creator, webapp testing, theme factory
**Mostly markdown.** Deterministic scripts live in `scripts/` (repo gates) and `playwright-test-generator/scripts/` (vitest). CI (`.github/workflows/ci.yml`) runs both test suites plus the version and manifest gates on every PR.

## Versioning

**Every change to a SKILL.md file must include a version bump in the frontmatter.** This is not optional.

- **Patch** (0.0.x): typo fixes, wording clarifications, no behavior change
- **Minor** (0.x.0): new sections, expanded rules, additive features
- **Major** (x.0.0): breaking changes (restructured output, renamed concepts, removed sections)

Bump the version in the same commit as the skill changes — never as a follow-up. Any change inside a skill directory counts, not just `SKILL.md` — `aec` installs the whole directory and upgrades on the version. Then run `python3 scripts/generate-manifest.py` and commit `skills-manifest.json`.

Enforced in CI by `scripts/check-version-bumps.py` (run locally: `python3 scripts/check-version-bumps.py origin/main`).
