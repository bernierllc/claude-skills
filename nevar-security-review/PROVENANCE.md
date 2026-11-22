# Provenance

This skill adapts the MIT-licensed `vulnerability-scanner` skill. Upstream text is
treated as untrusted data: it was read in isolation, audited, and rewritten or copied
here by hand. Nothing installs it from upstream at runtime.

## Pinned source

| Field | Value |
|---|---|
| Repository | https://github.com/davila7/claude-code-templates |
| Commit | `e3c1c93c12d14d52afa61b22577bfec613646f09` (2026-11-21, "Rewrite vulnerability-scanner skill… (#1652)") |
| Path | `cli-tool/components/skills/security/vulnerability-scanner/` |
| Earlier history | migrated into that repo from sickn33/antigravity-awesome-skills (MIT) at `1deb97c72161` |
| License | MIT, Copyright (c) 2025 Daniel (San) Ávila |

Upstream files at that commit:

| File | Bytes | sha256 |
|---|---|---|
| `SKILL.md` | 6805 | `4e3d487497ccec5a67eac82203b0988308fdef223500dd142bfae6015e46bbbc` |
| `references/ai-and-agents.md` | 6151 | `a1a7ba63758f07edb26ffb2e00dbd7b0d9d2740e44409c3f80353a39af9f0aff` |
| `references/web-and-supply-chain.md` | 4884 | `08d33fae453a1585af93925776e13a111293f5eacf43d137a1a853e3fb15c6be` |

## What came from upstream and what changed

| File here | Relation to upstream |
|---|---|
| `references/web-and-supply-chain.md` | Verbatim, plus a three-line HTML attribution comment at the top. |
| `references/ai-and-agents.md` | Adapted. Upstream `LLMxx:2026` and `ASIxx` labels replaced with verified OWASP LLM Top 10 2025 ids (LLM01–LLM10) and agentic theme names; MCP01–MCP10 kept and marked beta. Added: issue and PR bodies as untrusted text, "merge" as a high-impact agent action, service-role credentials, trust-context judgment of repo-carried instructions, pointer to `nevar.md`. |
| `SKILL.md` | Rewritten. Kept the evidence workflow (map the surface, source → sink, try to refute, observed vs inferred reach, coverage and not-covered lists, read-only default). Added: diff-selects / surface-examined scoping, the repo's P0/P1/P2 policy, stable finding ids, review-loop publishing, model review marked advisory, fix principles (Rule of Two, lethal trifecta). |
| `references/nevar.md`, `scripts/`, `fixtures/`, `tests/` | New; not from upstream. |

## Standards labels

Only labels checked against the publishing body's own list are used:

| Label set | Status |
|---|---|
| OWASP Top 10:2025 (A01–A10) | used, verified |
| OWASP API Security Top 10 2023 (API1–API10) | used, verified (still the latest edition) |
| OWASP Top 10 for LLM Applications 2025 (LLM01–LLM10) | used, verified |
| OWASP MCP Top 10 (MCP01–MCP10) | used, marked beta |
| Upstream `LLMxx:2026`, `ASIxx` (agentic) ids | **not imported**: ids not verified; theme names used instead |
| Meta "Agents Rule of Two" (2025-10-31), Willison "lethal trifecta" (2025-06-16) | cited by name and date |

## Risk audit of the upstream copy

Done on the pinned commit, before any text was copied:

- No scripts, hooks, executables or install steps in the upstream skill directory.
- No network calls, URLs to fetch, or instructions to contact a host.
- No hidden text: checked for HTML comments, zero-width and bidirectional Unicode, and
  base64 blobs.
- No instruction to read credentials, skip checks, or act outside the review.

## Updating

Never install or sync from upstream at latest. To take an upstream change:

1. Pick a new upstream commit and fetch the three files into an empty temp directory.
2. Record their sizes and sha256 above; diff them against the previous pinned copy.
3. Repeat the risk audit on the diff.
4. Apply wanted changes by hand, keeping the modifications listed above.
5. Bump `version` in `SKILL.md` and update `THIRD_PARTY_NOTICES.md` if the copyright line
   changed.

## License text

```
MIT License

Copyright (c) 2025 Daniel (San) Ávila

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
