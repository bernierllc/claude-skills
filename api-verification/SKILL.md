---
name: api-verification
version: 1.0.7
dependencies:
  skills:
    - name: api-verification-writer
      min_version: "1.2.2"
      reason: "Reads the API/MCP verification docs and the access manifest it produces; findings feed back into its Cross-agent feedback section."
    - name: verification-writer
      min_version: "3.5.1"
      reason: "Owns build-access-manifest.py and the docs/verification/ layout."
description: Verifies who can call each REST endpoint and MCP tool by running a principal x operation access matrix against a local or test server and comparing responses to what the verification docs declare. Flags over-permissive and over-restrictive operations, and refuses non-local hosts by default. Use after API or MCP auth changes, before releases, or to check that docs and behavior agree on public vs gated surfaces. Companion to api-verification-writer; the API counterpart of browser-verification.
---

# API Verification

Runs the access matrix. Docs say who should get in (`access:` frontmatter, merged into `docs/verification/access-manifest.json`); this skill checks the running server agrees.

## Prerequisites (halt with a clear message if missing)

1. `docs/verification/access-manifest.json` exists and is current: `build-access-manifest.py --check`.
2. `docs/verification/principals.json` maps each principal to roles/scopes and a `token_env` var **name**. Never tokens. An `anonymous` principal with no token is expected.
3. A **local or test** base URL. `matrix.py guard <url>` refuses anything else; extra safe hosts go in `API_VERIFICATION_ALLOWED_HOSTS` (comma-separated). Never point this at production.

## Workflow

1. `matrix.py plan` shows the expected allow/deny matrix. Read it; a surprising expectation is a docs bug (wrong `visibility` or roles), fix the docs first.
2. `matrix.py run --base-url http://localhost:PORT > results.json` probes REST entries as each principal. Mutating methods are skipped unless `--allow-mutating`, and only use that against a disposable database.
3. **MCP:** call each tool as each principal with your own MCP client and write `{"results": [{"id": "<tool>", "principal": "<name>", "status": <401|403|200>}]}` in the same shape (map a denied tool call to 403, a successful or validation-error call to 200).
4. `matrix.py evaluate --results results.json` (add `--denied-status 401,403,302` for cookie apps that redirect to a login page; redirects are never followed, so the token cannot leak to another host). Exit 2 lists mismatches:
   - `over-permissive`: allowed but docs say denied. **Security bug**, fix the code, not the docs.
   - `over-restrictive`: denied but docs say allowed. Fix the code or correct the docs.
5. Report with a **Cross-agent feedback** section (what docs agents and test runs told you, what changed). Fixes to wrong docs go through `api-verification-writer`, then regenerate the manifest.

Run via `aec run-script skill:api-verification matrix.py <subcommand> ...`.

## Rules

- A mismatch is never resolved by editing the expectation to match the server without checking intent. Over-permissive is code until proven otherwise.
- A principal with no `token_env` is anonymous: no token is sent, whatever roles it lists.
- An unreachable route is a `no-response` mismatch, not a pass. A planned row missing from the results file (and not listed in `skipped_mutating`) is a `missing-result` mismatch, for any surface that has at least one result.
- Status 404/400 caused by the placeholder path id counts as allowed: the auth gate passed the request.
- Do not log or print tokens; reports name principals only.
