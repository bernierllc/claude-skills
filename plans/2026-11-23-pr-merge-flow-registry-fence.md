# pr-merge-flow: an opt-in registry fence that makes the cop show a fresh lease receipt before a merge

Status: planned, no code. Owner: `pr-merge-flow` (the claude-skills cop); one small dependency on aec (settings registration, step F4). Proposed priority: P3, as the Tracker row already carries. Tracker: https://app.notion.com/p/Pre-merge-registry-fence-enforced-by-pr-merge-flow-guard-incident-nevar-api-52-merged-without-fre-4204efecc95a81c1ad30ec7c5962ed2b

## Why

A traffic cop merged a PR while its claim on the repo's lease was not fresh. The cop procedure says to claim the lease in the same batch right before `gh pr merge` and to stop on any result other than `confirmed`. That rule is prose: nothing checks that the claim ran, that it was fresh, or that it was for this repo and role. A rule that has to be remembered on every merge is the defect.

A coordinator registry can now sign a **lease receipt** on a successful claim, in one named format: `coordinator-lease-receipt+jwt` version 1 (contract D1, below). This plan makes `pr-guard.py` demand one, when a user opts in, so the claim cannot be forgotten.

## Incumbent check (read first)

- **`pr-merge-flow` 1.6.2, `scripts/pr-guard.py` merge check.** `check(cmd, cwd, notes)` walks every `gh pr merge` that `merge_calls` finds and, in order: blocks an unparseable repo, `--admin`, `--auto`, skips `--disable-auto`, blocks a `--match-head-commit` that is not 40 hex, then calls `not_green(ref, repo, d, notes)`. `not_green` resolves the PR with `gh pr view`, checks required checks under a local deadline of `GH_BUDGET_S = 15` (hooks.json gives the hook 20 s), and returns only a message string. `main()` reads the hook payload but passes `check()` no session id, and exits 2 on a crash. Nothing here knows about leases. The fence reuses all of it; F1 changes two signatures (Design → Where the fence sits).
- **The cop procedure's interim rule** (in the operator's own global config, not this repo): claim right before the merge, stop on anything but `confirmed`. Unenforced prose. It stays until step F4 ships.
- **The receipt contract (D1)**, owned by the registry. It defines the receipt, the handoff between guard and cop and the guard's verification steps, quoted below. The receipt path and the guard's state format are left to this plan.
- **EEA-2, `merge-receipt.py`** ([plan](2026-11-22-merge-receipt-after-confirmed-merge.md), planned for 1.7.0). Records a merge after GitHub confirms it, with a configurable shared sink. It does not check leases before a merge; it can carry the receipt's `rid` and `gen` (Design → Audit).
- **`review-gate/scripts/merge-guard.py`**, a second PreToolUse merge hook with its own, broader merge detection. It does not check leases either. The fence lives in `pr-guard.py` because that is where the per-merge `gh pr view` already happens (Design → Coverage).
- **No verifier in the dependency set.** `pr-guard.py` runs under whatever `python3` the hook's `PATH` resolves, through `aec run-script`, which takes the interpreter from the shebang (`#!/usr/bin/env python3`; `interpreter_for` in aec's `aec/lib/hooks/installer.py`). The `cryptography` package is not part of a stock Python. macOS `/usr/bin/openssl` is LibreSSL 3.3.6, which cannot create or verify Ed25519 keys (`genpkey -algorithm ed25519` prints usage). See Design → Verification library.

## Dedupe (searched 2026-11-23)

Searched `plans/`, open PRs and the Tracker for `lease`, `fence`, `receipt`, `claim` and `coordinator`. Nothing in this repo checks a lease. The closest is EEA-2 (post-merge record, no pre-merge check) and the Tracker row above, which this file implements.

## Related open work

- **#139, the tokenizer-first merge guard.** Changes how `merge_calls` finds `gh pr merge`. The fence consumes `merge_calls`' output and changes no parsing, so the two do not conflict. #139 stays untouched.
- **#156 (merged), the heredoc-in-substitution amendment to #139.** Same: no parsing change here.
- **EEA-2 (1.7.0).** Carries `rid` and `gen` once both ship.
- **Required vs advisory checks (1.6.0, merged).** The fence runs after `not_green`, so that order is unchanged.

The fence takes the next free minor version when F1 ships.

## The receipt contract this plan builds on (D1, quoted)

- Compact JWS, `alg` EdDSA (Ed25519). The header has exactly `alg`, `kid`, `typ: coordinator-lease-receipt+jwt` and `v: 1`, and never `crit`.
- Claims, all required, no extras at v1: `rid` (UUID, the claim event id), `repo` (lowercased `owner/name`), `role` (`traffic_cop` or `program_cop`), `env` and `thread` (nullable labels), `gen` (UUID of the open lease history row), `outcome` (`confirmed`, `created` or `replaced`), `cred` (`api_key` or `session`), `iat` and `exp` (seconds; `exp` is the end of the tenure), `nonce` (16 to 128 characters of `[A-Za-z0-9_-]`), `aud` (`coordinator-lease`), `iss` (the registry's origin).
- Outcomes: a claim by the same holder returns `confirmed`; an empty slot returns `created`; a claim that changed the holder returns `replaced`. A live lease held by someone else returns `conflict`, which carries no receipt.
- A receipt is signed only when the claim carries a nonce. None is issued for a conflict, a refusal or an error.
- Keys are published as a JWKS at `<iss>/.well-known/coordinator-receipt-keys.json`; rotation and revocation go through it.
- **Handoff.** (1) The guard denies `gh pr merge` with a random nonce, recorded with its time in the guard's own state, and the path where it expects the receipt. (2) The cop calls the registry's claim tool with that nonce and writes the compact JWS to the path. (3) The cop retries the merge. The guard verifies, then deletes the nonce whatever the result. The guard holds no credential and calls no registry tool.
- **Verification**, all of which must pass:
  1. The nonce was issued less than 120 s ago. A missing nonce, an expired nonce or a missing file fails.
  2. Fetch the JWKS for the expected `iss` with no cache. Select the key by `kid`; require `kty` OKP and `crv` Ed25519. An unknown `kid` fails.
  3. Verify with EdDSA only; check `typ`, `v` = 1 and no `crit`.
  4. `iss` is the expected origin, `aud` is `coordinator-lease`, `nonce` matches.
  5. `repo` and `role` equal the PR's repo and `traffic_cop`. If required, `cred` is `session`. A non-null `env` or `thread` must equal the cop's own; a null pair passes.
  6. Freshness: `now - 60 <= iat <= now + 30` and `now + 30 < exp`.
  7. The fresh claim is the live read; no separate lookup.
  8. Any failure blocks and names the failed step. An unreachable JWKS fails closed.
- **Race.** Between the claim and the merge another cop can take the lease. That window (at most 60 s plus the merge) is not closed. It is detected afterwards by joining each merge to its claim event.

The role (`traffic_cop`), audience (`coordinator-lease`) and JWKS path are constants of this format, not settings. Only the issuer is configured.

## Design

### Off by default, set by flat aec settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `merge_fence` | `enum[off,on]` | `off` | `on`: every `gh pr merge` needs a receipt. |
| `merge_fence_issuer` | https origin | unset | The expected `iss`. |
| `merge_fence_require_session` | bool | `false` | Require `cred` = `session` (step 5). Off until the registry issues session credentials to cops. |
| `merge_fence_history_cmd` | command string | unset | F3 only: a command that prints the registry's claim-history rows as JSON. Never in the org overlay. |

**Reading the settings fails closed.** Not the `draft_mode()` pattern, which turns any read error into the default and is right only for a harmless setting. The fence's reader:

- No `preferences.json`, or no `merge_fence` key: off.
- A file that exists but cannot be read or parsed, or `merge_fence` outside `off`/`on` (exact, lowercase): block every merge with a message naming the file and the bad value.
- `on` with `merge_fence_issuer` missing or not an origin: block every merge, naming the setting.

**Issuer form.** `https://` plus a lowercase host and an optional port, no path, query, fragment or trailing slash; the reader normalises case and rejects anything else. `iss` must equal it as a string. There is no http exception in the shipped guard: the tests call the fence function directly with an injected issuer and opener (F1), so no environment variable can relax it.

There are no per-repo exemptions: a user who wants the fence on some repos only uses separate aec profiles.

### Where the fence sits

At the end of the per-call loop in `check()`, after `not_green` returns clean, so a merge that would fail on a red required check is denied for that reason first and the cop does not spend a claim on it. F1 changes two signatures:

- `not_green` also returns the PR view it already fetched (`number`, `url`, `headRefOid`), so the fence takes repo and PR number from the resolved URL, the same identity the rest of the check uses, whatever form `ref` had (empty, a number, a branch or a URL). No second `gh pr view`. The repo is lowercased before it is compared with the receipt's `repo` or hashed into the state key; GitHub keeps the owner's case in URLs, D1 lowercases. The parity harness (`tests/test_pr_guard_parity.py`) applies one `not_green` stub to both the previous release and the head guard; F1 picks the stub's shape per module (a string for a baseline whose `not_green` returns one, `("", view)` or `("red", None)` for the head) and drops that shim once the baseline is a release with the new shape.
- `main()` passes the hook payload's `session_id` to `check()`.

**One merge per command.** With the fence on, a command that holds more than one `gh pr merge` that would merge (every call `merge_calls` yields except `--disable-auto`, which the loop already skips) is blocked ("one merge per command when the merge fence is on"). The count runs before the loop, so no nonce is written for such a command. Each merge needs its own claim, and a combined command could never pass.

### Coverage

The fence covers exactly what `merge_calls` finds: `gh pr merge` in its known shapes. It does not see a merge done through `gh api` (`PUT …/pulls/<n>/merge`, the GraphQL `mergePullRequest`), the web UI or another tool, and it inherits `merge_calls`' known parsing gaps (#139 and #156 own those). It makes the claim impossible to forget on the normal merge path; it does not stop an agent set on evading it. Moving detection to the broader parser in `merge-guard.py`, or a shared one, is a later step if those paths turn up in practice.

### Time budget

A hook the harness kills for running too long does not block, so a slow fence would fail open. Two layers:

- **Budget.** F1 replaces the local deadline in `not_green` with one deadline of `GH_BUDGET_S` (15 s, unchanged, so the fence off changes nothing) created at the start of `check()` and passed to both `not_green` and the fence. With less than 4 s left when the fence starts, it blocks with "fence: not enough time left; retry the same command". The JWKS fetch timeout is the remaining time minus 1 s, at most 3 s.
- **Backstop.** A `urllib` timeout bounds each socket operation, not the whole fetch, and does not cover DNS resolution, so a slow-drip server or a stalled lookup can still outlast the budget. When the fence is on, `main()` starts a daemon watchdog thread that, at 17 s after `main()` starts (leaving room for `aec run-script` and interpreter start inside the hook's 20 s), prints "fence: checks did not finish in time; blocked" and calls `os._exit(2)`. `review-gate/scripts/merge-guard.py` already denies rather than be killed with `SIGALRM`; that is not enough here, because a signal handler runs only between bytecodes and a blocking C call (`getaddrinfo`, a TLS read) can hold the main thread past the kill. A thread calling `os._exit` does not wait for the main thread.

`timeout_ms` stays 20000. The receipt file is opened with `O_NOFOLLOW | O_NONBLOCK`, checked with `fstat` on the descriptor to be a regular file, and read to at most 16 KB, so a FIFO or a huge file cannot hang the read. Tests: a JWKS server that never answers, one that drips a byte a second, and a lookup of an unroutable name each end with exit 2 within 20 s.

### Nonce and receipt state

Under `${XDG_STATE_HOME:-~/.local/state}/pr-merge-flow/fence/`, the state directory EEA-2 also uses, created `0700`; the fence refuses to use it if it is a symlink or not owned by the user.

- **Key:** the first 32 hex characters of `sha256("<owner/repo>\0<pr>\0<session_id>")`. Hashing avoids separator and sanitising collisions. A payload without `session_id` (some harnesses send none) uses the literal `no-session` for that part, so the fence still works there, scoped to repo and PR.
- **`<key>.nonce.json`:** `{"nonce", "issued_at", "repo", "pr", "head"}`, written atomically (temp file, then rename). `nonce` is 32 URL-safe characters from `secrets.token_urlsafe(24)`. `head` is the `--match-head-commit` sha.
- **`<key>.receipt.jws`:** where the cop writes the receipt; outside the checkout, so it is never committed.
- **`consumed.jsonl`:** every `nonce` and `rid` the fence has verified. A repeat of either blocks.

| State on a `gh pr merge` | Fence does |
|---|---|
| No nonce file | Deletes any leftover receipt file (so a stale receipt cannot burn the new nonce), writes a nonce, denies with the nonce, the receipt path and the next step: claim with this nonce, write the receipt there, retry the same command. |
| Nonce older than 120 s | Deletes it and its receipt, writes a fresh nonce, denies as above ("nonce expired; claim again with the new one"). |
| Fresh nonce, no receipt file | Keeps the nonce and denies: "claim first, then write the receipt to <path>". The nonce is not burnt. |
| Fresh nonce, receipt present | Consumes: `os.rename` of the nonce file to a unique name. Only the call whose rename succeeds goes on; a concurrent retry finds no nonce and is denied. Reads the receipt, deletes both, then verifies. |

**Head binding.** A retry whose `--match-head-commit` differs from the nonce's `head` fails as "fence binding: head changed since the nonce was issued", because a claim made for one head says nothing about a later push. The receipt has no PR or head claim, so this binding, and the PR binding through the key, live in the guard's own state: they stop a cop who forgets or mixes up PRs, not an agent that rewrites the state directory.

### Verification

The eight D1 steps, in order, each failure naming its step (`fence step 6: receipt expired`). On top of them:

- **Strict parsing.** Exactly three unpadded base64url parts. Header and payload are JSON objects with no duplicate keys. The header has exactly `alg`, `kid`, `typ`, `v`, so `jwk`, `jku`, `x5u`, `x5c`, `b64` and `zip` are rejected as well as `crit`. The payload has exactly the D1 claims, each of its type: UUID strings for `rid` and `gen`, the D1 charset and length for `nonce`, integers for `iat` and `exp`, string or null for `env` and `thread`. A type error is a named failure ("fence step 3: claim exp is not an integer"), never a crash.
- **JWKS fetch.** One `urllib.request` GET through `build_opener(ProxyHandler({}), <a redirect handler that raises>)`, so neither `HTTPS_PROXY` nor a redirect can move the request, `Cache-Control: no-cache`, a 1 MB cap and the timeout from Time budget. Any HTTP, size or parse error blocks. Each `kid` must appear once in the set, and the key's `x` must decode to exactly 32 bytes.
- **Clock.** Freshness uses the local clock. A skewed clock fails closed.
- **`env` and `thread`.** The guard cannot read a harness's thread id by itself. When the hook environment sets `PR_GUARD_FENCE_ENV` or `PR_GUARD_FENCE_THREAD`, a non-null claim must equal them; unset, the check is skipped. It is a consistency check, not identity.
- **`outcome`.** `confirmed` and `created` pass: the caller already held the lease, or the slot was empty. `replaced` blocks: "you just took this lease from another holder; check with them, then claim again". The next claim by the same holder returns `confirmed`, so this costs one more claim and keeps the interim rule's caution where it matters. Any other value blocks as a contract violation.

### Verification library

Do not hand-roll Ed25519. **Chosen:** import `cryptography` (`Ed25519PublicKey.verify`) lazily, only when `merge_fence` is `on`. Missing module → block with a message naming `sys.executable` and the fix: install `cryptography` for that interpreter (`<python> -m pip install cryptography`; where that Python is externally managed, such as Homebrew's, put a virtualenv's `python3` first on the hook's `PATH` or install the distribution's package). The import and `verify` call sit inside an `except BaseException` that blocks with a named step: a panic in the compiled extension raises a `BaseException` subclass, which the existing `except Exception` in `__main__` would miss, exiting 1, which does not block. With the fence off nothing changes, including for users without the package.

Rejected:

- **The `openssl pkeyutl -verify -rawin` CLI.** Needs OpenSSL 3 or later; macOS ships LibreSSL 3.3.6, which has no Ed25519. Finding the right binary would be a second dependency check that is harder to explain.
- **A uv / PEP 723 shebang.** `interpreter_for` honours any shebang, so `#!/usr/bin/env -S uv run --script` would work, but it makes uv a hard dependency of the whole guard for every user, fence on or off.

### Audit (detection, not prevention)

- **F1:** after a successful verify the guard appends `{"repo", "pr", "head", "rid", "gen", "nonce", "verified_at"}` to `consumed.jsonl`. A line means "allowed to start", not "merged": a merge can still fail after it.
- **After EEA-2 ships:** `merge-receipt.py` adds `rid` and `gen` to its record when this machine's `consumed.jsonl` has a line for that PR and head, so the join reaches EEA-2's shared sink, which collects merges from every machine. A record written elsewhere (for example by EEA-2's `reconcile` on another machine) carries no `rid`.
- **F3:** `scripts/fence-audit.py` takes merges from GitHub, matches each to a fence line by repo, PR and head, and checks the claim through `merge_fence_history_cmd`, so this repo holds no registry credential. Per repo and day it reports: merges with no fence line, lines whose `gen` was closed before the merge time, and history windows the registry marked incomplete. Exit 1 on any of those. A merge with no `rid` in the sink and no line in this machine's file is reported separately as "unverifiable here", not as a violation, because it may have been fenced on another machine. It reads `rid` and `gen` from EEA-2's sink when configured, otherwise only this machine's file, and the report says which.
- **Retention.** The guard trims `consumed.jsonl` to the last 90 days itself, on the first append of each day. Append and trim take the same `fcntl.flock` on the file, and the trim writes a temp file and renames it, so neither depends on F3 being scheduled.

### Wrapper alternative (rung 1), evaluated and not chosen

A `claim-then-merge` wrapper that does the claim itself would remove the extra round trip. It would need a copy of the cop's registry credential outside the agent's tool layer, which spreads a secret for no gain: the guard would still have to verify a receipt, and the nonce deny already makes the claim impossible to forget. Revisit if the registry offers a CLI credential scoped to one repo and role.

## Rollout

| Step | What | Done when |
|---|---|---|
| F0 | This plan. | Merged. |
| F1 | The fence in `pr-guard.py` behind `merge_fence: off`: settings reader, the two signature changes, the shared deadline and watchdog, state handling, verification, the parity-harness update. `.github/workflows/ci.yml` gains a pinned `python3 -m pip install cryptography==<version>` before the pr-guard tests (today it installs only `pyyaml`, for review-gate). SKILL.md section; version bump. | The tests below and the parity run pass in CI. When `CI` is set and `cryptography` cannot be imported they fail, not skip; locally they skip with a message. The missing-module test runs everywhere by hiding the module. |
| F2 | A contract test from a captured registry receipt and its JWKS snapshot, with a fixed clock. It proves F1's fixtures match what the registry really signs. Waits until a registry signs receipts in staging. | Passes against the snapshot; fails if a claim or header field is renamed, added or removed. |
| F3 | `scripts/fence-audit.py`, as above, tested with a recorded history file and a recorded merge list. | Each report row type has a test; documented in SKILL.md. |
| F4 | aec settings registration PR. All four keys go in `KNOWN_PREFERENCE_KEYS`. `merge_fence`, `merge_fence_issuer` and `merge_fence_require_session` also go in the org overlay's `PREFERENCES_ALLOW_LIST`, so an org can turn the fence on for its members. `merge_fence_history_cmd` goes in `PREFERENCES_EXCLUDED_KEYS` instead, because an overlay must never set a command F3 runs (aec's `test_allow_lists.py` requires excluded keys to be known and not allow-listed). Validators for the origin and command types. Docs in this repo's SKILL.md. | Merged in aec; a cop with the fence on merges one PR end to end. |
| after F4 | Outside both repos: each operator whose cops use the fence drops the interim prose rule from their own cop procedure. | Not tracked here. |

**F1 tests.** All against real code, with receipts signed in the test by a key generated in the test:

- **Subprocess tests** run the hook with a stdin payload, `HOME` and `XDG_STATE_HOME` pointed at temp directories holding the test's `preferences.json`, a `gh` recorder first on `PATH` (as the existing suite does) answering `gh pr view` and the check calls, and a real TLS JWKS server on 127.0.0.1, port 0, with a certificate from a test CA trusted through `SSL_CERT_FILE`. So the shipped https-only rule is what is exercised.
- **Direct calls** to the fence function, with an injected issuer and opener, cover the parsing and claim cases faster.

One test each:

- Fence off changes nothing; settings missing → off; corrupt file, bad value, `on` without issuer → every merge blocked.
- Each state-table row; the nonce is single use, including two concurrent retries; a repeated `rid` or `nonce`; head changed; no `session_id`; a symlinked state directory.
- Each D1 step's failure blocks and names its step: expired nonce, JWKS unreachable, the three hang cases in Time budget (exit 2 within 20 s), oversized JWKS, a duplicate `kid`, a short `x`, a FIFO or oversized receipt, a redirect, unknown `kid`, wrong `kty` or `crv`, `alg` `none` or HS256, an extra header field, `crit`, a missing or extra claim, a wrong claim type, wrong `iss`, `aud` or `nonce`, wrong `repo` or `role`, a mixed-case repo that matches once lowercased, `cred` when required, `env`/`thread` mismatch, `iat` and `exp` bounds.
- `outcome` `confirmed` and `created` pass, `replaced` and an unknown value block.
- Two `gh pr merge` in one command with the fence on → blocked with no nonce written; `--disable-auto` plus one merge → fenced normally.
- `cryptography` missing → blocked only with the fence on, naming `sys.executable`.

## Out of scope

- Closing the claim-to-merge race. It is detected (F3), not prevented.
- Merges outside `merge_calls` (Design → Coverage).
- Fencing `program_cop` merges. The fence demands `role` = `traffic_cop`, the only role that merges.
- Any change to how `merge_calls` parses a command (#139 owns that).
- Turning the fence on for anyone. Off by default; each user opts in.
