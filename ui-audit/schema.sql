PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS routes (
  user_level TEXT NOT NULL,
  route TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'discovered',
  audit_id TEXT,
  test_id TEXT,
  bug_ids TEXT,
  discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_audited_at TEXT,
  picked_at TEXT,
  lease_until TEXT,
  PRIMARY KEY(user_level, route)
);

CREATE TABLE IF NOT EXISTS tickets (
  ticket_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  route TEXT,
  user_level TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bugs (
  bug_sig TEXT PRIMARY KEY,
  bug_id TEXT,
  route TEXT,
  user_level TEXT,
  severity TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_routes_status ON routes(status);
CREATE INDEX IF NOT EXISTS idx_routes_user_route ON routes(user_level, route);
CREATE INDEX IF NOT EXISTS idx_tickets_kind ON tickets(kind);

