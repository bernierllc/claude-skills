# API / MCP verification doc format

One operation per file.

- REST: `docs/verification/api/<resource>/<method>-<slug>.md`
- MCP: `docs/verification/mcp/<tool_name>.md`

```markdown
---
surface: rest                       # rest | mcp
method: get                         # rest only
path: /v1/events                    # rest only; params as {id}
# tool: send_email                  # mcp only
generated_by: api-verification-writer@1.2.2
generated_at: 2026-01-01
affected_paths:                     # block list, every entry quoted: unquoted [id] route segments break YAML and flow lists are skipped by block-list readers
  - "src/routes/events.ts"
related:                            # REST/MCP counterpart, if any; path relative to docs/verification/
  - "mcp/list_events.md"
access:
  public: false
  # endpoint: /api/v1/inbox/mcp      # only when this operation is served somewhere other than the surface default (e.g. a second MCP endpoint with its own token); the matrix plan carries it
  auth_model: oauth-scope           # none | api-key | oauth-scope | rbac | session (any OAuth token with scopes is oauth-scope; say the grant type under "Auth & access")
  required_scopes: [events.read]
  required_roles: []
  tier: null
  mfa_required: false
  gated_by: []                      # feature flags/env vars that must be on in production for a customer to reach this
  # gates_confirmed_on: true        # set only after confirming every gated_by flag is on in production; required to keep visibility: public
  visibility: draft                 # public | internal | admin | draft
---

# GET /v1/events

## Purpose
## Request (parameters, body schema)
## Responses (status -> shape, one row each)
## Auth & access (who may call it, what a denied call returns)
## Side effects (none | what changes)
## Unverified (claims not yet observed)
```

MCP docs replace Request/Responses with **Input schema**, **Output**, **Annotations** (`readOnlyHint`, `destructiveHint`), and **Errors**.
