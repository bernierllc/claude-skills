#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { exec } from 'node:child_process';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
import { getRepoRoot } from './repo-utils.mjs';

const repoRoot = getRepoRoot();
const cacheDir = path.join(repoRoot, 'CONTEXT_CACHE');
const dbPath = path.join(cacheDir, 'ui_audit.db');
const schemaPath = path.join(cacheDir, 'schema.sql');
const gitignorePath = path.join(repoRoot, '.gitignore');

function log(msg) { console.log(`[ui-audit-bootstrap] ${msg}`); }
function fail(msg, code = 1) { console.error(`[ui-audit-bootstrap] ${msg}`); process.exit(code); }

// Parse args (very light)
const args = new Map(process.argv.slice(2).flatMap(a => {
  const [k, v] = a.includes('=') ? a.split('=') : [a, true];
  return [[k.replace(/^--/, ''), v]];
}));
const userLevel = (args.get('user-level') || 'regular');

log(`Detected repo root: ${repoRoot}`);

// 1) Ensure CONTEXT_CACHE dir exists
if (!fs.existsSync(cacheDir)) {
  fs.mkdirSync(cacheDir, { recursive: true });
  log(`Created cache dir: ${cacheDir}`);
} else {
  log(`Using cache dir: ${cacheDir}`);
}

// 2) Copy schema.sql if it doesn't exist (from skill directory)
// Note: schema.sql should be copied to CONTEXT_CACHE during project setup
// For now, we'll check if it exists and provide guidance if not
if (!fs.existsSync(schemaPath)) {
  log(`Schema file not found at ${schemaPath}`);
  log(`Please copy schema.sql from .claude/skills/ui-audit/schema.sql to CONTEXT_CACHE/`);
  fail(`Missing schema file at ${schemaPath}. Please copy schema.sql and re-run.`);
}

// 3) Ensure .gitignore contains CONTEXT_CACHE/
if (!fs.existsSync(gitignorePath)) {
  // Create .gitignore if it doesn't exist
  fs.writeFileSync(gitignorePath, 'CONTEXT_CACHE/\n', 'utf8');
  log(`Created .gitignore with CONTEXT_CACHE/`);
} else {
  const gi = fs.readFileSync(gitignorePath, 'utf8');
  if (!gi.split(/\r?\n/).some(line => line.trim() === 'CONTEXT_CACHE/')) {
    // Append to .gitignore
    fs.appendFileSync(gitignorePath, '\nCONTEXT_CACHE/\n', 'utf8');
    log(`Added CONTEXT_CACHE/ to .gitignore`);
  } else {
    log('.gitignore already contains CONTEXT_CACHE/');
  }
}

// 4) Initialize SQLite db via `sqlite3` if available
function execP(cmd) { 
  return new Promise((resolve, reject) => 
    exec(cmd, (e, stdout, stderr) => 
      e ? reject(new Error(stderr || e.message)) : resolve({ stdout, stderr })
    )
  ); 
}

async function ensureDb() {
  try {
    await execP(`sqlite3 --version`);
  } catch {
    log('sqlite3 CLI not found. You can install it or initialize the DB manually:');
    log(`- Create empty file: touch ${dbPath}`);
    log(`- Apply schema with sqlite3 when available: sqlite3 ${dbPath} < ${schemaPath}`);
    return; // best-effort
  }
  try {
    // Check if DB already exists and has tables
    const checkDb = `sqlite3 ${dbPath} ".tables" 2>/dev/null || echo ""`;
    const { stdout } = await execP(checkDb);
    if (stdout.trim()) {
      log(`SQLite DB already exists at ${dbPath}`);
      return;
    }
    await execP(`sqlite3 ${dbPath} < ${schemaPath}`);
    log(`SQLite DB initialized at ${dbPath}`);
  } catch (e) {
    fail(`Failed to initialize SQLite DB: ${e.message}`);
  }
}

// 5) Check Vibe-Kanban availability (best-effort)
async function checkVibeKanban() {
  // We cannot reliably detect MCP CLI here; provide helpful guidance instead.
  log('If Vibe-Kanban MCP is not running, open a new terminal and run:');
  log('  npx vibe-kanban');
}

(async () => {
  log(`Bootstrap starting for user-level: ${userLevel}`);
  await ensureDb();
  await checkVibeKanban();
  log('Bootstrap complete. You can now run discovery/audit tasks.');
  log(`\nNext steps:`);
  log(`1. Ensure Vibe-Kanban MCP is running (npx vibe-kanban)`);
  log(`2. Create discovery task using the UI audit skill`);
  log(`3. Discovery task will create EXPLORE tasks for each route`);
})();

