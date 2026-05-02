# Verification-Writer Version Fingerprints

This file is the source of truth for inferring which version of verification-writer produced a given verification doc when its `generated_by` stamp is missing or unreliable.

`scripts/scan-versions.py` reads this file at startup. Each row defines a structural signal in a verification doc and the lowest skill version that introduced it. The scanner walks the table and assigns the highest version whose signals are all present in the doc.

**Maintenance rule:** every minor or major version of verification-writer that changes the on-disk format of verification docs MUST add a row here in the same commit. Patch versions (text-only changes) do not.

## Detection precedence

When scanning a doc:

1. If frontmatter contains a valid `generated_by: "verification-writer@X.Y.Z"` stamp → use that, skip fingerprint detection.
2. Otherwise, walk the table top-to-bottom. The highest-numbered version whose **all** required signals are present is the inferred version.
3. If no row matches (e.g., no frontmatter, no Format A items), report `pre-3.0.0` and flag for manual migration.

## Fingerprint table

| Inferred version | Required signals (all must be present) | Notes |
|---|---|---|
| `3.3.0` | YAML frontmatter contains `affected_paths` (key present, value can be `[]` or list) | Introduced affected_paths schema. Glob patterns allowed in entries. |
| `3.2.0` | YAML frontmatter contains `id_namespace` AND no `affected_paths` key | Introduced id_namespace prefix validation. |
| `3.1.0` | YAML frontmatter contains `generated_by` stamp AND no `id_namespace` key | Stamp-introduction release. Should never need fingerprinting (stamp is present by definition); included for completeness. |
| `3.0.0` | YAML frontmatter present (any of: `version`, `path`, `access`, `page`, `data_dependencies`) AND no `generated_by` stamp AND no `id_namespace` | Initial frontmatter release. |
| `2.x` | No YAML frontmatter AND items use Format A (e.g., `**EVT-DTL-01**`) | Pre-frontmatter, modern ID format. |
| `pre-3.0.0` (catch-all) | No YAML frontmatter AND no Format A items detected | Legacy doc. Needs manual migration before downstream skills can consume reliably. |

## Signal definitions

**YAML frontmatter present:** file begins with `---` on the first non-empty line, contains a closing `---`, and parses as valid YAML between the markers.

**`generated_by` stamp valid:** key exists with a value matching the regex `^verification-writer@\d+\.\d+\.\d+$`.

**`id_namespace` key:** literal key `id_namespace:` at the top level of the frontmatter mapping.

**`affected_paths` key:** literal key `affected_paths:` at the top level of the frontmatter mapping. Value is either an empty sequence (`[]`) or a sequence of strings (each string is a glob pattern or literal path).

**Format A items:** at least one line in the body matches the regex `^- \[[ x]\] (\[\w+\] )?\*\*[A-Z][A-Z0-9-]+\*\*`. The `[A-Z][A-Z0-9-]+` portion captures the bold ID prefix.

## What this is NOT

- This table does not describe the full schema of any version. Refer to the matching `SKILL.md` git history for full schema details.
- The scanner uses this for *detection*, not *validation*. Validation lives in verification-writer's own write-path code.
- Inferred versions are best-guess. A stamp is always preferred. The scanner output marks fingerprint-inferred entries with `fingerprint_inferred: true` so the agent knows to surface them for confirmation.

## Adding a new row

When verification-writer adds a new fingerprintable signal:

1. Add a row at the top of the fingerprint table.
2. List every signal required to disambiguate it from prior versions (typically: a new key, plus exclusions to prevent matching older versions).
3. Add or update entries in **Signal definitions**.
4. Update the SKILL.md migration table to reference this version's fingerprint row.
5. Bump the verification-writer version (always required for skill changes — see `CLAUDE.md`).
