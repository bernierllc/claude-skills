#!/usr/bin/env node
/**
 * check-versions.js - Deterministic staleness detection across the chain
 * verification doc -> metadata doc -> spec file.
 *
 * This is checklist step 1: it replaces the full-scan approach, where the agent
 * read every doc and every spec to work out what changed. Nothing here needs an
 * LLM, so it runs in milliseconds and hands back a precise task list.
 *
 * Exports testable functions. CLI entry point at bottom.
 */

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import * as nodeFs from 'node:fs';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveRepoRoot } from './lib/repo.js';

const VERIFICATION_ROOT = join('docs', 'verification');
const PLAYWRIGHT_ROOT = join('tests', 'verification-playwright');
const EXCLUDED_DIRS = new Set(['findings', 'logs', 'visualizations']);
const EXCLUDED_TOP_FILES = new Set(['index.md', 'README.md']);

/** Scalar values from a leading YAML frontmatter block, plus top-level list keys.
 * Deliberately not a YAML parser: only `key: value` scalars and `- item` lists
 * at the top level are read, which is everything the version chain needs. */
export function parseFrontmatter(text) {
  if (!text.startsWith('---')) return null;
  const end = text.indexOf('\n---', 3);
  if (end === -1) return null;

  const out = {};
  let listKey = null;
  for (const raw of text.slice(3, end).split('\n')) {
    const listItem = /^ {0,2}- (.+)$/.exec(raw);
    if (listKey && listItem) {
      out[listKey].push(unquote(listItem[1]));
      continue;
    }
    const m = /^([A-Za-z_][\w-]*):(.*)$/.exec(raw);
    if (!m) continue;
    const value = m[2].trim();
    if (value === '') {
      listKey = m[1];
      out[listKey] = [];
    } else {
      listKey = null;
      out[m[1]] = unquote(value.replace(/\s+#.*$/, ''));
    }
  }
  return out;
}

function unquote(s) {
  return s.trim().replace(/^["'](.*)["']$/, '$1');
}

/** The four `@`-annotations from a spec file's header comment. */
export function parseSpecHeader(text) {
  const head = text.slice(0, 2000);
  const read = (tag) => {
    const m = new RegExp(`@${tag}\\s+(\\S+)`).exec(head);
    return m ? m[1] : null;
  };
  return {
    source: read('source'),
    sourceGeneratedBy: read('source-generated-by'),
    metadata: read('metadata'),
    generatedBy: read('generated-by'),
  };
}

/** Split a `path@version` or `skill@version` reference into its two halves. */
export function splitRef(ref) {
  if (!ref) return { name: null, version: null };
  const at = ref.lastIndexOf('@');
  if (at === -1) return { name: ref, version: null };
  return { name: ref.slice(0, at), version: ref.slice(at + 1) };
}

/** Semver compare. Returns -1, 0, or 1; unparseable versions sort as 0.0.0. */
export function compareVersions(a, b) {
  const parts = (v) => String(v || '').split('.').map((n) => parseInt(n, 10) || 0);
  const [x, y] = [parts(a), parts(b)];
  for (let i = 0; i < 3; i++) {
    if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0) ? 1 : -1;
  }
  return 0;
}

/** Every verification doc under the root, excluding report and log directories.
 * Mirrors verification-writer's own discovery: docs at the verification root or
 * in project-specific subdirectories carry real items, and a doc not listed
 * here is invisible to the whole pipeline. */
export function discoverDocs(verificationRoot) {
  if (!existsSync(verificationRoot)) return [];
  const found = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir).sort()) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        if (dir === verificationRoot && EXCLUDED_DIRS.has(entry)) continue;
        walk(full);
      } else if (entry.endsWith('.md')) {
        if (dir === verificationRoot && EXCLUDED_TOP_FILES.has(entry)) continue;
        found.push(full);
      }
    }
  };
  walk(verificationRoot);
  return found;
}

/** affected_paths entries that expand to zero files in the working tree.
 * Globs need fs.globSync (Node >= 22); on older runtimes only literal paths are
 * checked, so this under-reports rather than reporting false positives. */
export function missingAffectedPaths(patterns, repoRoot) {
  const missing = [];
  for (const pattern of patterns || []) {
    if (pattern.startsWith('!')) continue; // negation refines, never requires a match
    const hasMagic = /[*?[\]{}]/.test(pattern);
    if (!hasMagic) {
      if (!existsSync(join(repoRoot, pattern))) missing.push(pattern);
      continue;
    }
    if (typeof nodeFs.globSync !== 'function') continue;
    try {
      if (nodeFs.globSync(pattern, { cwd: repoRoot }).length === 0) missing.push(pattern);
    } catch {
      // An unparseable pattern is a doc bug, not a missing file — leave it to
      // verification-writer's own integrity pass rather than guessing here.
    }
  }
  return missing;
}

/** Classify one verification doc against its metadata doc and spec file.
 * Returns exactly one status; the order below is the triage order from the
 * skill checklist — blocking states first, cosmetic drift last. */
export function classifyDoc(docPath, projectDir, repoRoot = projectDir) {
  const rel = relative(projectDir, docPath).split('\\').join('/');
  const name = basename(docPath, '.md');
  const kind = basename(dirname(docPath)) === 'flows' ? 'flows' : 'pages';
  const metadataPath = join(projectDir, PLAYWRIGHT_ROOT, 'metadata', `${name}.md`);
  const specPath = join(projectDir, PLAYWRIGHT_ROOT, kind, `${name}.spec.ts`);
  const at = (status, detail) => ({ doc: rel, name, status, metadataPath, specPath, ...detail });

  const docFm = parseFrontmatter(readFileSync(docPath, 'utf8'));
  if (!docFm) return at('frontmatter-missing');
  if (!docFm.generated_by) return at('stamp-missing');

  const docVersion = docFm.version;
  const liveSkill = splitRef(docFm.generated_by).version;

  if (!existsSync(metadataPath)) return at('metadata-missing', { docVersion });

  const metaFm = parseFrontmatter(readFileSync(metadataPath, 'utf8')) || {};
  const syncedSkill = splitRef(metaFm.source_generated_by).version;
  if (compareVersions(liveSkill, syncedSkill) > 0) {
    return at('skill-version-mismatch', { docVersion, liveSkill, syncedSkill });
  }

  const missingPaths = missingAffectedPaths(docFm.affected_paths, repoRoot);
  if (missingPaths.length > 0) {
    return at('affected-path-missing-on-disk', { docVersion, missingPaths });
  }

  if (!existsSync(specPath)) return at('test-missing', { docVersion });

  const header = parseSpecHeader(readFileSync(specPath, 'utf8'));
  if (!header.source || !header.metadata || !header.sourceGeneratedBy || !header.generatedBy) {
    return at('header-missing', { docVersion });
  }

  const specMetaVersion = splitRef(header.metadata).version;
  if (compareVersions(metaFm.version, specMetaVersion) < 0) {
    return at('metadata-outdated', { docVersion, metadataVersion: metaFm.version, specMetaVersion });
  }

  const syncedDocVersion = splitRef(metaFm.source).version;
  if (compareVersions(docVersion, syncedDocVersion) > 0) {
    return at('source-updated', { docVersion, syncedDocVersion });
  }

  return at('up-to-date', { docVersion });
}

/** Classify every verification doc in the project. */
export function checkVersions(projectDir, repoRoot = projectDir) {
  const docs = discoverDocs(join(projectDir, VERIFICATION_ROOT));
  const results = docs.map((d) => classifyDoc(d, projectDir, repoRoot));
  const counts = {};
  for (const r of results) counts[r.status] = (counts[r.status] || 0) + 1;
  return { total: results.length, counts, results };
}

// --- CLI entry point ---
const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  if (process.argv.includes('--help')) {
    console.log(`check-versions.js - Report staleness across verification doc -> metadata -> spec

Usage: node check-versions.js [project-dir]

Exit codes:
  0  scan completed, nothing blocking
  1  at least one doc needs agent work
  2  at least one doc is a hard stop (skill-version-mismatch: run --resync)`);
    process.exit(0);
  }

  const projectDir = resolve(process.argv[2] || process.cwd());
  const report = checkVersions(projectDir, resolveRepoRoot(projectDir));
  console.log(JSON.stringify(report, null, 2));

  const blocking = report.counts['skill-version-mismatch'] || 0;
  const needsWork = report.total - (report.counts['up-to-date'] || 0);
  process.exitCode = blocking > 0 ? 2 : needsWork > 0 ? 1 : 0;
}
