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
generated_by: api-verification-writer@1.1.0
generated_at: 2026-01-01
affected_paths: [src/routes/events.ts]
related: [mcp/list_events.md]       # REST/MCP counterpart, if any
access:
  public: false
  auth_model: oauth-scope           # none | api-key | oauth-scope | rbac | session
  required_scopes: [events.read]
  required_roles: []
  tier: null
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
