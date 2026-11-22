# Security Scan: resolve requirements includes for osv-scanner

Status: planned. Follow-up to PR #147 (NEVAR-SEC-SKILL-1 PR C), which shipped osv-scanner
descoped to what it can prove.

## Why this is a plan, not a fix in #147

PR #147 produced nine P1 findings in the osv-scanner exit and coverage area. The traffic cop
set the rule after the fourth: one more P1 there and the PR descopes OSV and this plan takes
include resolution. The f277bbf re-check found four more, so the descope ran. The review of
the descope head found a ninth in the include predicate itself, so #147 stopped parsing
include syntax at all (below).

| # | Head | Finding |
|---|------|---------|
| 1 | first head | exit 128 (no packages) read as a pass |
| 2 | 12dc7a7 | a multi-input run passed with one unreadable input |
| 3 | c849c19 | a lockfile with no vulnerabilities has no result entry without `--all-packages` |
| 4 | c849c19 | a missing include was only a note, not coverage |
| 5 | f277bbf | an already-staged include is never traversed, so its own includes are skipped and a renamed author-config include is accepted |
| 6 | f277bbf | `--requirement` includes are staged but never scanned: the pinned parser follows only `-r` |
| 7 | f277bbf | physical-line matching misses continuations (`-\` then `r base.txt`); a quoted include (`-r "base.txt"`) gives a false unresolved finding |
| 8 | f277bbf | alternate names such as `requirements-dev.txt` get no coverage |
| 9 | f95bd30 | an include after another option on the same line (`--no-index -r base.txt`) is missed by the include predicate |

Plus one P2 on f277bbf: an exception keyed on the including file covers every unresolved
include in it.

## What #147 ships (the proven scope)

- osv-scanner runs with `--all-packages` on changed lockfiles and on the names osv-scanner
  2.7.0 reads as requirements files (a base name ending `.txt` that contains
  `requirements`, case-sensitive; probed against the pinned binary). Every input must yield
  packages on its own (`no-packages` otherwise).
- A changed requirements file with any option line is a `not-covered` finding on that file.
  pip 26.2.2 follows `-r`/`-c` only on an option line (its first token starts with `-`,
  after `join_lines` and comment stripping), so `has_option_line()` joins continuation lines
  the way pip does (never joining a comment line), strips a BOM, and flags any logical line
  whose first character is `-`, or `$` (an environment variable can expand to an option), and
  any text containing a NUL (a UTF-16/32 file this reader cannot see). It parses no option
  syntax, so no spelling of an include can slip past it. pip-compile's hashed output
  (`six==1 \` then `--hash=...`) joins into a requirement line and is not flagged. It fails
  the gate unless an exact, owned, expiring exception names that file. Findings 5–9 cannot
  occur: nothing is staged or resolved, and the predicate covers the alternate names.
- Intended false positives: an option line that is not an include (`--index-url`, `-e .`,
  `--require-hashes`) is also `not-covered` and needs a per-file exception until this plan
  lands.
- The P2 becomes the intended semantics for now: the finding is about the file ("OSV cannot
  prove it read this file completely"), so one exception per file is the right key until
  includes are resolved.
- Known residual, documented in `nevar.md`: a changed file that is a dependency list only
  because an unchanged requirements file includes it (for example `base.txt`) is not scanned
  by osv-scanner, because only changed files are staged and its name is not one OSV reads.

## Root cause

Only the PR's changed files are staged, and the scan reads them from the head as data. pip
includes point at files the PR may not change, and the reverse: a changed file may be
reachable only through an unchanged include. osv-scanner resolves includes from the scanned
tree with its own parser, which is not pip's, and keeps the rest of a file when one include
is missing, so a partial read looks like a read.

## Correct fix (to design and prove here)

1. Build the include graph from the head checkout, read as data: every requirements-named
   file in the tree, not only changed ones, so a changed `base.txt` reached through an
   unchanged `requirements.txt` is found (closes the residual).
2. Parse include lines with pip's own rules, not a regex: continuation joining, comment
   stripping, quotes, `=`, glued short options, long-option prefixes, environment variables.
   Prefer vendoring or calling pip's `req_file` parser on the text over reimplementing it,
   and say why if that is not possible.
3. Stage the closure: nested, cycle-safe, through the existing `stage()` checks (regular
   files only, no symlink in any component, `safe_rel` paths). Traverse a file even when it
   is already staged (finding 5).
4. Do not rely on osv-scanner following includes. Its pinned parser follows only `-r`
   (finding 6). Pass each file in the closure to osv-scanner as its own input with
   `-L requirements.txt:<path>` (the parser override works on 2.7.0), and keep the per-input
   `no-packages` rule.
5. An include that cannot be resolved or staged (outside the repo, absent, a symlink, an
   author-config name, a URL, an unexpanded environment variable) is a finding.
6. Key exceptions by (including file, include) so one exception never covers more than one
   include (the P2).
7. gitleaks then sees the staged includes too. Decide whether that is wanted or filtered.

## Affected surfaces

- `nevar-security-review/templates/security-scan/scan.py`: staging, the OSV branch,
  `has_option_line()` (removed or kept as the not-covered fallback), `applicable()`.
- `nevar-security-review/tests/test_security_scan.py`: unit tests and real-scanner tests.
- `nevar-security-review/references/nevar.md`: the OSV bullet, the `not-covered` rule, the
  residual.
- Repos that adopt the template during the rollout (PR D): `not-covered` exceptions may be
  needed until this lands.

## Done when

A changed requirements file with includes, and a changed file reachable only through an
unchanged include, are scanned completely or fail with a named finding. Real-scanner tests
cover nested, missing, escaping, symlinked, `--requirement`, continued and quoted includes,
and the `not-covered` rule for includes and the residual are removed from `nevar.md`.
