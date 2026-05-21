# Issue: playwright-test-generator — monorepo pipeline correctness (3 defects)

**Skill:** `playwright-test-generator`
**Type:** bug (1 functional, 1 diagnostic, 1 hardening)
**Priority:** medium — Defect #1 can produce a silent false-green in any monorepo
that uses changed-files / gate-tier selection.

These were found while running the skill against a monorepo whose Playwright
project root is a subdirectory (the directory that holds
`tests/verification-playwright/` and the manifest) while the sources under test
span more than one package. All three reproduce on any repo with that shape;
single-root projects are unaffected.

---

## Defect #1 — single-base path resolution breaks monorepos (FUNCTIONAL)

### Root cause
Both `scripts/verify-pipeline.js` (`checkSourceFiles`) and
`scripts/map-changes.js` (`mapFilesToTags`) resolve import-index keys against a
single base directory:

```js
const fullPath = join(projectDir, file);   // file = key from import-index.json
if (!existsSync(fullPath)) { /* fail / mark stale */ }
```

`projectDir` is `process.cwd()`, which for this skill is the **Playwright project
root** — the subdirectory that holds the manifest and `tests/`. But the keys in
`import-index.json` must be **repo-root-relative**, for two reasons:

1. Sources legitimately span more than one package, so they cannot all be
   expressed relative to a single package directory.
2. `map-changes.js --since-main` matches those keys against `git diff
   --name-only`, and **git always emits repo-root-relative paths** regardless of
   `cwd`.

So when the project root is a subdirectory, `join(projectRoot, repoRootKey)`
produces a doubled, non-existent path (the project subdir is prepended to a key
that already contains it). The two distinct requirements — manifest base = the
Playwright project dir; index/git base = the repo root — are conflated into one
`projectDir`.

### Impact
- `verify-pipeline.js`: every entry in the import index is falsely reported as
  "Source file not found," even though the sources exist at the repo root. Clean
  manifests fail verification.
- `map-changes.js`: every changed source is flagged "stale" and dropped, so the
  function emits **zero tags**. A configuration with `default_tier: "gate"` and
  `scope: "changed"` would then select and run **no tests** on a normal
  changed-files run — a silent false-green, the most dangerous failure mode here.

### Proposed fix (lowest blast radius)
1. Resolve a **repo root** independently of the manifest's project dir: prefer
   `git rev-parse --show-toplevel` (run with `cwd: projectDir`); fall back to
   `projectDir` when not in a git repo. The fallback makes `repoRoot ===
   projectDir`, preserving today's single-root behavior exactly.
2. In `checkSourceFiles` and `map-changes.js`, join import-index keys against
   `repoRoot`. Keep manifest/spec resolution on `projectDir`.
3. Add a monorepo test fixture (manifest under a subdir; index keys
   repo-root-relative, spanning two packages) asserting (a) `checkSourceFiles`
   passes and (b) `mapFilesToTags` emits the correct tags from git-style paths.
   Keep an existing single-root test to prove no regression.

**Alternative considered and rejected:** making index keys relative to the
Playwright project dir (e.g. `src/...`, `../other-pkg/src/...`). Rejected because
it breaks the `git diff` match in `map-changes.js` (git emits repo-root-relative
paths) — it would trade a diagnostic failure for a functional one.

---

## Defect #2 — `checkItemConsistency` flags marker-less skip stubs as orphans (DIAGNOSTIC)

### Root cause
`scripts/verify-pipeline.js#checkItemConsistency` exempts only `status ===
'pending'` from the "must have `@begin`/`@end` markers" rule. But the skill's own
convention is that `.skip()` stubs are **marker-less** — they are tracked by the
`@<ID>` tag in the test title, not by `@begin`/`@end` comment markers. Any
manifest item with `status: 'skipped'` and a `spec_file` is therefore reported as
"Orphaned: no @begin/@end markers."

### Impact
Every legitimate skip stub in a manifest produces a false "Orphaned" failure,
adding noise that masks real consistency problems.

### Proposed fix
Treat `status: 'skipped'` like `status: 'pending'` in `checkItemConsistency` (no
markers expected). Optionally assert the stub's spec actually carries a
`test.skip( '... @<ID>' )` title, so a "skipped" manifest entry can't point at a
spec that never mentions it. Add a unit test: a skipped item backed by a
marker-less stub should `pass`.

---

## Defect #3 — no syntactic guard before writing a generated spec (HARDENING)

### Root cause
Before writing a spec, the skill validates `@begin:ID` set membership, but it
does not confirm the generated file is free of leaked tool-call artifacts or is
otherwise parseable. A malformed generation can leave literal tool-call trailer
tokens in a spec file. Because Playwright fails at **collection** when any spec
is unparseable, one bad file aborts the **entire** suite before a single test
runs — an all-or-nothing failure from one corrupted write.

### Impact
A single malformed generated file blocks the whole run with a collection-time
`SyntaxError`, rather than failing in isolation. Observed once; required a manual
cleanup of the leaked trailer tokens to recover.

### Proposed fix
After generating each spec's text and before writing it (alongside the existing
ID-membership check), reject any output containing tool-call artifact tokens
(e.g. stray closing/opening invoke/parameter/content tags). This is cheap,
deterministic, and catches the exact failure mode. Optionally run a post-write
parse/`tsc --noEmit` smoke check on changed specs as an additional gate.

---

## Resolution (skill v3.8.0)

- **Defect #1 — FIXED as proposed.** New `scripts/lib/repo.js#resolveRepoRoot`
  resolves the git toplevel (`git rev-parse --show-toplevel`, cwd = projectDir)
  and falls back to projectDir outside a git repo. `checkSourceFiles` and
  `mapFilesToTags` now join import-index keys against `repoRoot` (a new param
  defaulting to `projectDir`, so single-root behavior is unchanged). Manifest/
  spec resolution stays on `projectDir`. Covered by new monorepo tests in
  `verify-pipeline.test.js`, `map-changes.test.js`, and `lib/repo.test.js`,
  each with a regression guard asserting the old single-base path failed.

- **Defect #2 — DIAGNOSIS REJECTED; strengthened instead.** The premise that
  the skill's convention is "marker-less `.skip()` stubs" is incorrect:
  `references/test-generation-patterns.md` wraps every `.skip()` stub in
  `@begin`/`@end` markers, and `sync-tests.js` *requires* those markers to
  locate, patch, and un-skip stubs. A marker-less stub is invisible to the
  pipeline. Exempting `status: skipped` from the marker check would mask a real
  orphan. Instead: `checkItemConsistency` now additionally fails a `skipped`
  item whose marked block contains no `.skip()` (status/spec mismatch), and
  SKILL.md states explicitly that skip stubs carry markers. The marker-less
  stubs you observed are a *generation* bug, not an over-strict check.

  **Generation-bug follow-up (skill v3.8.1).** Root cause of the marker-less
  stubs traced to SKILL.md itself: the only two inline test-code examples in the
  always-loaded skill body (the auth-aware live test and `.skip()` stub) were
  written without `@begin`/`@end` markers, contradicting the prose invariant a
  few sections below. A generating agent pattern-matches the nearest concrete
  example over distant prose, so it reproduced marker-less stubs. Both examples
  now carry markers (and use the canonical tags-first title format), with an
  explicit note that the wrapping is required even inside a `test.describe`
  block. The stub source — verification-writer — was ruled out: it only writes
  `docs/verification/*.md` (item IDs + `<!-- DEFERRED -->` annotations) and never
  emits spec code or markers; all `.skip()`/marker emission is owned by
  playwright-test-generator's generation step.

- **Defect #3 — FIXED (defense in depth).** SKILL.md step 7b.1 adds a pre-write
  artifact-token guard (hard stop, regenerate). `verify-pipeline.js` adds a
  deterministic on-disk `checkSpecArtifacts` gate that fails any spec containing
  stray `invoke`/`parameter`/`function_calls` tags. Covered by new tests.

## Acceptance criteria
- [ ] `verify-pipeline.js` reports zero false source-not-found and zero false
      orphan failures against a monorepo manifest (clean exit 0).
- [ ] `map-changes.js --since-main` emits correct `@<page>` tags for changed
      sources across multiple packages in a monorepo.
- [ ] Spec generation refuses to write a file containing tool-call artifact
      tokens.
- [ ] Skill unit suite green, including new monorepo, skip-stub, and
      artifact-guard cases.
- [ ] Single-root projects unaffected (`repoRoot === projectDir` fallback path).
