# Findings

Scanner kinds (from `scan-api-surfaces.py`):

| kind | meaning | action |
|---|---|---|
| `undocumented-route` | in code, not in spec | add to spec or confirm internal |
| `spec-without-route` | in spec, scan found no route (scan is heuristic) | verify, then fix spec or code |
| `no-security-declared` | no operation or global `security` | a human states public or protected |
| `mcp-no-description` | tool has no description | add; agents choose tools by it |
| `mcp-no-annotations` | no `readOnlyHint`/`destructiveHint` | add so clients can gate destructive calls |
| `mcp-no-output-schema` | no `outputSchema` | low priority |
| `yaml-spec-unreadable` | YAML spec, no PyYAML | export JSON or install PyYAML |

Manifest kinds (from `build-access-manifest.py`): `invalid-visibility`, `visibility-contradicts-access`, `duplicate-entry`, `frontmatter-missing`.

## Report shape

Group by kind, list `id` and file, end with:

## Cross-agent feedback
What the docs agents or test runs reported back (unverified claims, missing operations, wrong visibility) and what changed because of it. Empty section is allowed; omitting it is not.
