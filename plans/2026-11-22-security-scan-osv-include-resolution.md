# Security Scan: prove dependency file coverage for osv-scanner

Status: planned. Follow-up to PR #147 (NEVAR-SEC-SKILL-1 PR C), which shipped osv-scanner
descoped to what it can prove.

## Why this is a plan, not a fix in #147

PR #147 produced sixteen P1 findings in the osv-scanner exit and coverage area. The traffic cop
set the rule after the fourth: one more P1 there and the PR descopes OSV and this plan takes
the rest. The f277bbf re-check found four more, so the descope ran. The review of the descope
head found a ninth in the include predicate, and the review of the option-line rule that
replaced it found three more (10–12) that are not about includes at all: pip and osv-scanner
read the same requirements bytes differently. The review of the requirements-only rule found
three more (13–15): a requirements symlink escaped the rule because staging drops it, and
two Yarn lockfile inputs make osv-scanner's parser read less than yarn does while still
yielding packages. Under the third-round rule #147 therefore proves nothing about any
dependency file, lockfiles included (below). The review of that rule found a sixteenth: the
changed-file list dropped deleted dependency files and rename sources, so they escaped it.

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
| 10 | 9c21c1e | an encoding declaration (`# coding: utf-7`) makes pip decode `+AC0-r base.txt` to `-r base.txt`; the predicate read UTF-8 |
| 11 | 9c21c1e | a `\r` or `\f` separator ends a line for pip's `splitlines()` but not for osv-scanner, which keeps the next requirement inside a comment |
| 12 | 9c21c1e | an environment variable anywhere in a requirement (`django==${V}`) is expanded by pip and skipped by osv-scanner |
| 13 | ffb4239 | a changed requirements file replaced by a symlink is dropped by staging, so it gets no `not-covered` finding |
| 14 | ffb4239 | a single-quoted Yarn Berry version (`version: '4.17.20'`) is read as version `""`, so its advisories are hidden |
| 15 | ffb4239 | a Yarn comment longer than about 70000 characters silently truncates the extractor's parse; earlier packages still count as read |
| 16 | 6ed2a9d | a deleted lockfile, or a requirements file renamed to a non-dependency name, was dropped from the changed-file list, so it escaped `not-covered` |

Plus one P2 on f277bbf: an exception keyed on the including file covers every unresolved
include in it.

## What #147 ships (the proven scope)

- osv-scanner runs with `--all-packages` on changed lockfiles (`LOCKFILES`) and on the names
  osv-scanner 2.7.0 reads as requirements files (a base name ending `.txt` that contains
  `requirements`, case-sensitive; probed against the pinned binary). Its advisories are
  reported, and an input that yields no packages is a `no-packages` finding. Both are
  advisory extras: neither proves the file was read completely.
- Every changed dependency file is a `not-covered` finding on that file, whatever its
  content and whatever osv-scanner read from it. That includes a dependency file staging
  skipped (a symlink, a non-regular file), because the package manager still reads it, and a
  dependency file the PR deletes or renames away, because that changes what gets installed. It
  fails the gate unless an exact, owned, expiring exception names that file. No content
  predicate exists, so findings 5–16 cannot turn into a pass. A repo that changes
  dependency files needs a per-file exception until this plan lands a proven format.
- The P2 becomes the intended semantics for now: the finding is about the file ("OSV cannot
  prove it read this file completely"), so one exception per file is the right key.
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
2. Read every requirements file with pip's own rules, not a regex: encoding declarations
   and BOMs, `splitlines()` separators, continuation joining, comment stripping, quotes, `=`,
   glued short options, long-option prefixes, environment variables (pip expands only
   `${NAME}` from the runner's environment; decide whether an unset or set variable is a
   finding). Prefer calling pip's `req_file` parser on the text, then giving osv-scanner the
   resolved requirement list it produced, over reimplementing pip; say why if that is not
   possible.
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
8. Lockfiles, per format: prove osv-scanner's parser reads what the package manager does
   (findings 14 and 15 for Yarn: quoting, long lines). Prefer the package manager's own
   resolved output (for example `yarn info --json` run without lifecycle scripts, or the
   lockfile's own parser library) over osv-scanner's extractor, and require a complete-parse
   proof, such as a package count from the package manager matching osv-scanner's. Lift
   `not-covered` one format at a time, each with a real-scanner test.
9. Account for every changed dependency path before staging filters it (finding 13): a
   symlink or non-regular dependency file stays a finding, never a silent skip.

## Affected surfaces

- `nevar-security-review/templates/security-scan/scan.py`: staging, the OSV branch,
  the unconditional dependency `not-covered` finding in `scan_one()` and `scan()` (removed
  per format when coverage is proven), `applicable()`.
- `nevar-security-review/tests/test_security_scan.py`: unit tests and real-scanner tests.
- `nevar-security-review/references/nevar.md`: the OSV bullet, the `not-covered` rule, the
  residual.
- Repos that adopt the template during the rollout (PR D): `not-covered` exceptions may be
  needed until this lands.

## Done when

A changed requirements file, and a changed file reachable only through an unchanged
include, are scanned with what pip would install or fail with a named finding, and each
lockfile format whose `not-covered` is lifted is proven read completely. Real-scanner tests
cover nested, missing, escaping, symlinked, `--requirement`, continued and quoted includes,
encoding declarations, `\r`/`\f` separators, environment variables, quoted Yarn versions
and long Yarn lines (findings 1–15; 16 is closed in #147), and the unconditional `not-covered` rule and the
residual are removed from `nevar.md`.
