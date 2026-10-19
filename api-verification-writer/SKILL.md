---
name: api-verification-writer
version: 1.0.0
dependencies:
  skills:
    - name: verification-writer
      min_version: "3.5.0"
      reason: "Shares the docs/verification/ layout, the access: frontmatter contract and build-access-manifest.py. API and MCP docs feed the same access manifest as page docs."
description: Writes verification docs for REST endpoints and MCP tools, one operation per doc, under docs/verification/api/ and docs/verification/mcp/. Inventories surfaces from OpenAPI, an MCP tools/list dump and framework route scans, flags spec/code drift, missing auth declarations and thin MCP tool metadata, and records who may call each operation in access frontmatter. Use when an API route, OpenAPI spec or MCP server changes, when documenting API/MCP behavior for customers or agents, or when the access manifest needs API/MCP entries. Companion to verification-writer (UI) and api-verification (runs the access matrix).
---

# API Verification Writer

UI verification docs describe pages. This skill describes **operations**: REST endpoints and MCP tools. Same layout, same `access:` contract, same manifest, so the docs agents and CI read one source of truth for what is public, internal, admin-only or still a draft.

**Companions:** `verification-writer` (pages, owns the manifest builder) · `api-verification` (executes the access matrix from these docs) · docs agents (consume `docs/verification/access-manifest.json`).

## Workflow

1. **Inventory.** `aec run-script skill:api-verification-writer scan-api-surfaces.py --root .`
   Add `--mcp-tools tools.json` with a `tools/list` result captured from a running test server (MCP SDK client or Inspector CLI). The scanner never contacts a server. Spec beats code scan; disagreement is a finding, not something to reconcile silently.
2. **Triage findings** (see `references/findings-format.md`). `no-security-declared` means someone must say whether the operation is public; do not guess.
3. **Write one doc per operation** following `references/doc-format.md`. Front matter carries `surface`, `method`+`path` or `tool`, `generated_by: api-verification-writer@<version>`, and `access:` including `visibility`.
4. **Regenerate the manifest:** `aec run-script skill:verification-writer build-access-manifest.py --root .`; commit it with the docs.
5. **Report** using the findings format, including the Cross-agent feedback section.

## Rules

- `visibility` is declared by a human or an upstream source, never inferred. Absent means `draft`.
- Behavior claims (status codes, error shapes, side effects) must be observed in code, spec or a run. Mark anything else `unverified` so docs agents do not publish it.
- Never put tokens, keys or real customer data in a doc. Principals are named, secrets live in env vars.
- Mutating operations (POST/PUT/PATCH/DELETE, destructive MCP tools) are documented with their side effects; running them is `api-verification`'s decision, not this skill's.
- Parity: a capability exposed by both REST and MCP should say so in both docs (`related:`); a gap is a finding.

## Stamp compatibility

`verification-writer`'s version scan accepts `api-verification-writer@x.y.z` stamps and does not report them as malformed.
