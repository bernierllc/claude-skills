# Claude Skills - Project Instructions

## Stack Information

**Type:** Documentation/markdown only (no runnable code)
**Content:** Claude Code skill definitions (SKILL.md files) organized by category
**Categories:** Algorithmic art, artifacts/webapp builders, brand guidelines, canvas design, document formats (docx, xlsx, pdf, pptx), frontend design, internal comms, MCP builder, Slack GIF creator, webapp testing, theme factory
**No test runner, type checker, or linter** — this repo contains only `.md` files and supporting assets defining Claude skill configurations.

## Versioning

**Every change to a SKILL.md file must include a version bump in the frontmatter.** This is not optional.

- **Patch** (0.0.x): typo fixes, wording clarifications, no behavior change
- **Minor** (0.x.0): new sections, expanded rules, additive features
- **Major** (x.0.0): breaking changes (restructured output, renamed concepts, removed sections)

Bump the version in the same commit as the skill changes — never as a follow-up.
