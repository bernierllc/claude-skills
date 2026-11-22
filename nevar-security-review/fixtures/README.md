# Fixtures

Each case has a `vulnerable/` variant and a `safe/` negative control. `expected.json` is
the ground truth; never hand it to a blind reviewer.

- Runtime cases (`app.py`): small WSGI apps on SQLite. `tests/test_fixtures.py` serves each
  over real HTTP on 127.0.0.1 and asserts the vulnerable variant misbehaves and the safe one
  does not. SQLite stands in for Postgres: RLS policies themselves are not executed; the
  "service connection" models a service-role client that bypasses RLS.
- Static cases: agent-instruction files, a workflow, a config with a fake key, a lockfile.
  File names carry `.fixture.` so no agent, GitHub Actions or Dependabot loads them. The
  injected instructions point at non-existent paths and `.invalid` hosts.
- No real secrets, no live sites, nothing here is executed except the runtime apps by the
  tests.

## Blind forward-test

How to rerun: copy each case to `svcNN/{a,b}` with case names and variant order shuffled,
leave out `expected.json` and this README, give a fresh reviewer only `SKILL.md`,
`references/`, `scripts/` and the copy, read-only. Then score its report against
`expected.json`.

| Date | Reviewer | Vulnerable found | Safe controls without P0/P1 | Severity matches |
|---|---|---|---|---|
| 2026-11-21 | Claude Sonnet 5.5, no web, no execution | 9/9 | 9/9 | 8/9: planted instructions rated P0, expected P1 |

That run's friction led to: the worked example rated editor-bypass P1 to match the P1
rule; a fixed category table; and rating rules for self-declared fake credentials,
planted instructions and advisories that cannot be looked up offline.
