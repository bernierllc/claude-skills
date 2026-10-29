// Context map compute for the feature map: turns <map dir>/contexts.json (the independent pieces
// of the product, what each owns and what it offers) plus the code's own imports into what the
// page's Contexts view draws: who owns each file and table, which imports go through a declared
// interface and which reach into another context's internals, and which workstreams can run in
// parallel without touching the same context. Pure functions only, except scanImports, which takes
// a reader; build-map.mjs walks the files. The fields are described in references/data-model.md
// (contexts.json) and SKILL.md (stage 9). Imports are read from JS and TS sources only.
//
// A file belongs to the context whose glob matches it most specifically. An import from context A
// into context B is a reach-in unless the file it imports is one of B's declared interfaces, or B is
// the shared kernel (kind "shared"), which every context may use. The kernel itself imports no context.

import { posix } from "node:path";

export const CONTEXT_KINDS = new Set(["domain", "shared", "none"]);
export const INTERFACE_STATUS = new Set(["defined", "missing"]);
const CTX_ID = /^[a-z0-9-]+$/;
const SOURCE = /\.(ts|tsx|js|jsx|mjs|cjs)$/;
const RESOLVE_SUFFIXES = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", "/index.ts", "/index.tsx", "/index.js", "/index.jsx"];

/**
 * A glob as a matcher: `**` matches any depth, `*` any characters inside one path segment. A glob
 * with no wildcard names one file and beats any pattern; otherwise more literal characters win.
 */
export function globMatcher(glob) {
  const source = glob.split(/(\*\*\/?|\*)/).map((part) => {
    if (part === "**" || part === "**/") return ".*";
    if (part === "*") return "[^/]*";
    return part.replace(/[.+^${}()|[\]\\?]/g, "\\$&");
  }).join("");
  const literal = glob.replace(/\*/g, "").length;
  return { glob, re: new RegExp(`^${source}$`), specificity: glob.includes("*") ? literal : 100000 + literal };
}

/** Every context's code globs as matchers {ctx, glob, re, specificity}. */
export function matchersOf(cfg) {
  return (cfg.contexts ?? []).flatMap((c) => (c.owns?.code ?? []).map((g) => ({ ctx: c.id, ...globMatcher(g) })));
}

/** The context that owns `path`: {ctx, glob}, {ambiguous: [ctx, ...]} when two contexts tie, or null. */
export function ownerOf(path, matchers) {
  let best = null;
  let tied = [];
  for (const m of matchers) {
    if (!m.re.test(path)) continue;
    if (!best || m.specificity > best.specificity) { best = m; tied = []; }
    else if (m.specificity === best.specificity && m.ctx !== best.ctx) tied.push(m.ctx);
  }
  if (!best) return null;
  return tied.length ? { ambiguous: [best.ctx, ...tied].sort() } : { ctx: best.ctx, glob: best.glob };
}

/** feature id -> context id: a context's `features` list wins over the context that holds the feature's area. */
export function featureContexts(cfg, features) {
  const byArea = new Map();
  for (const c of cfg.contexts ?? []) for (const a of c.areas ?? []) byArea.set(a, c.id);
  const out = new Map(features.map((f) => [f.id, byArea.get(f.area) ?? null]));
  for (const c of cfg.contexts ?? []) for (const f of c.features ?? []) if (out.has(f)) out.set(f, c.id);
  return out;
}

/**
 * Problems that would make the Contexts view wrong. `files` and `tables` may be empty (a tree with no
 * code); the checks that need them are skipped then. `isPlan(ref)` says whether the page can link a
 * ref to a live plan (the build mirrors the page's planKey); without it refs are not checked.
 * @param {any} cfg
 * @param {{areaIds: Set<string>, featureIds: Set<string>, tables?: string[], files?: string[], isPlan?: ((ref: string) => boolean) | null, schemaFile?: string | null}} input
 */
export function validateContexts(cfg, { areaIds, featureIds, tables = [], files = [], isPlan = null, schemaFile = null }) {
  const problems = [];
  const where = "contexts.json";
  const ids = new Set();
  const areaOwner = new Map();
  const featureOwner = new Map();
  const tableOwner = new Map();
  const tableSet = new Set(tables);
  const fileSet = new Set(files);
  for (const c of cfg.contexts ?? []) {
    const at = `${where}: ${c.id}`;
    if (!CTX_ID.test(c.id ?? "")) problems.push(`${where}: context id ${JSON.stringify(c.id)} must be lowercase words joined by -`);
    else if (ids.has(c.id)) problems.push(`${at}: listed twice`);
    ids.add(c.id);
    if (!c.name) problems.push(`${at}: needs a name`);
    if (!CONTEXT_KINDS.has(c.kind)) problems.push(`${at}: kind ${JSON.stringify(c.kind)}; use ${[...CONTEXT_KINDS].join(", ")}`);
    for (const a of c.areas ?? []) {
      if (!areaIds.has(a)) problems.push(`${at}: area ${a} is not an area in features.json`);
      else if (areaOwner.has(a)) problems.push(`${at}: area ${a} is already in ${areaOwner.get(a)}`);
      else areaOwner.set(a, c.id);
    }
    for (const f of c.features ?? []) {
      if (!featureIds.has(f)) problems.push(`${at}: feature ${f} is not in features.json`);
      else if (featureOwner.has(f)) problems.push(`${at}: feature ${f} is already in ${featureOwner.get(f)}`);
      else featureOwner.set(f, c.id);
    }
    for (const t of c.owns?.tables ?? []) {
      if (tableSet.size && !tableSet.has(t)) problems.push(`${at}: table ${t} is not a table in ${schemaFile ?? "the schema file"}`);
      else if (tableOwner.has(t)) problems.push(`${at}: table ${t} is already owned by ${tableOwner.get(t)}`);
      else tableOwner.set(t, c.id);
    }
    if (files.length) {
      for (const g of c.owns?.code ?? []) {
        const { re } = globMatcher(g);
        if (!files.some((f) => re.test(f))) problems.push(`${at}: ${g} matches no file (moved or deleted? update the glob)`);
      }
    }
    for (const i of c.interfaces ?? []) {
      if (!INTERFACE_STATUS.has(i.status)) problems.push(`${at}: interface status ${JSON.stringify(i.status)}; use ${[...INTERFACE_STATUS].join(", ")}`);
      if (!i.what) problems.push(`${at}: an interface needs a what`);
      if (i.status === "defined") {
        if (!i.path) problems.push(`${at}: a defined interface needs a path`);
        else if (files.length && !fileSet.has(i.path)) problems.push(`${at}: interface ${i.path} is not a file`);
      }
      if (i.status === "missing" && !i.ref) problems.push(`${at}: a missing interface needs a ref (the plan that builds it)`);
      else if (i.status === "missing" && isPlan && !isPlan(i.ref)) problems.push(`${at}: interface ref ${i.ref} is not a live plan (moved or archived? point it at the plan that builds it)`);
    }
  }
  for (const a of areaIds) if (!areaOwner.has(a)) problems.push(`${where}: area ${a} is in no context`);
  // A table or file nobody owns would drop out of the map silently, so both are problems.
  const unownedTables = tables.filter((t) => !tableOwner.has(t));
  if (unownedTables.length) problems.push(`${where}: ${unownedTables.length} table(s) in the schema are owned by no context (${unownedTables.slice(0, 5).join(", ")}); add each to a context's owns.tables`);
  if (files.length) {
    const matchers = matchersOf(cfg);
    for (const c of cfg.contexts ?? []) {
      for (const i of c.interfaces ?? []) {
        if (i.status !== "defined" || !fileSet.has(i.path)) continue;
        const o = ownerOf(i.path, matchers);
        if (o?.ctx !== c.id) problems.push(`${where}: ${c.id}: interface ${i.path} is owned by ${o?.ctx ?? o?.ambiguous?.join(" and ") ?? "no context"}`);
      }
    }
    const ambiguous = new Map();
    const orphans = [];
    for (const f of files) {
      const o = ownerOf(f, matchers);
      if (!o) orphans.push(f);
      else if (o.ambiguous) ambiguous.set(o.ambiguous.join(" and "), [...(ambiguous.get(o.ambiguous.join(" and ")) ?? []), f]);
    }
    for (const [pair, list] of ambiguous) problems.push(`${where}: ${list.length} file(s) match ${pair} equally (for example ${list[0]}); make one glob more specific`);
    if (orphans.length) problems.push(`${where}: ${orphans.length} file(s) are owned by no context (${orphans.slice(0, 5).join(", ")}); add a glob to the context that owns them`);
  }
  return problems;
}

/**
 * Resolve an import specifier from `from` to a file in `fileSet`, or null (a package, a json or a
 * file outside the scan). `aliases` maps a path prefix to a repo path, as tsconfig paths do:
 * {"@/": "src/"}; the longest matching prefix wins.
 * @param {string} spec @param {string} from @param {Set<string>} fileSet @param {Record<string, string>} [aliases]
 */
export function resolveImport(spec, from, fileSet, aliases = {}) {
  let base;
  const alias = Object.keys(aliases).sort((a, b) => b.length - a.length).find((a) => spec.startsWith(a));
  if (alias) base = posix.normalize(aliases[alias] + spec.slice(alias.length));
  else if (spec.startsWith(".")) base = posix.normalize(posix.join(posix.dirname(from), spec));
  else return null;
  for (const s of RESOLVE_SUFFIXES) if (fileSet.has(base + s)) return base + s;
  return null;
}

const STATEMENT = /\b(import|export)\s+(type\s+)?(?:([\w*{}\s,$]+?)\s+from\s+)?["']([^"'\n]+)["']/g;
// `const { a, b: c } = await import("x")` names its bindings; a bare `import("x")` names none.
const DYNAMIC = /(?:\{([^{}]*)\}\s*=\s*(?:await\s+)?)?\bimport\(\s*["']([^"'\n]+)["']\s*\)/g;

/**
 * Every import between scanned files: {from, to, type_only, names}. `names` are the bindings a
 * named import brings in (how table use is read from the schema file). `read(path)` returns text.
 */
export function scanImports(files, read, aliases = {}) {
  const fileSet = new Set(files);
  const out = [];
  for (const from of files) {
    if (!SOURCE.test(from)) continue;
    const text = read(from);
    for (const m of text.matchAll(STATEMENT)) {
      const to = resolveImport(m[4], from, fileSet, aliases);
      if (!to || to === from) continue;
      const clause = m[3] ?? "";
      const specs = (clause.match(/\{([^}]*)\}/)?.[1] ?? "").split(",").map((s) => s.trim()).filter(Boolean);
      const names = specs.map((s) => s.replace(/^type\s+/, "").split(/\s+as\s+/)[0]);
      const ns = clause.match(/\*\s+as\s+(\w+)/)?.[1];
      if (ns) for (const u of text.matchAll(new RegExp(`\\b${ns}\\.(\\w+)`, "g"))) names.push(u[1]);
      // `import { type A, type B }` brings in types only; one value specifier or a default import makes it a runtime import.
      const inlineTypes = specs.length > 0 && specs.every((s) => /^type\s/.test(s)) && !clause.replace(/\{[^}]*\}/, "").replace(/[\s,]/g, "");
      out.push({ from, to, type_only: !!m[2] || inlineTypes, names: [...new Set(names)] });
    }
    for (const m of text.matchAll(DYNAMIC)) {
      const to = resolveImport(m[2], from, fileSet, aliases);
      const names = (m[1] ?? "").split(",").map((s) => s.trim().split(/\s*[:=]\s*/)[0]).filter(Boolean);
      if (to && to !== from) out.push({ from, to, type_only: false, names });
    }
  }
  return out;
}

// Drizzle's `export const users = pgTable(`; contexts.json schema.table_pattern overrides it.
export const DEFAULT_TABLE_PATTERN = "export const (\\w+) = (?:pg|mysql|sqlite)Table\\(";

/** The table identifiers a schema file declares: the first capture group of each match of `pattern`. */
export function tablesOf(schemaText, pattern = DEFAULT_TABLE_PATTERN) {
  return [...schemaText.matchAll(new RegExp(pattern, "g"))].map((m) => m[1]);
}

/** File paths a gap's evidence names, without line numbers or anchors, kept when under one of `scope`. */
export function evidencePaths(evidence, scope = ["src/"]) {
  return (evidence ?? []).map((e) => String(e).trim().split(/[:#\s]/)[0]).filter((p) => scope.some((s) => p.startsWith(s)));
}

/**
 * The Contexts view's data.
 * - cfg: contexts.json; files: scanned paths; imports: scanImports output; tables: schema identifiers
 *   (`schemaFile` is the file they are declared in); features: [{id, area}]
 * - workstreams: [{id, features, gaps}]; gapEvidence: Map gap id -> evidence strings; work: the Work
 *   view's data (for agent-ready workstreams and their unlocks), or null.
 * @param {any} cfg
 * @param {{files?: string[], imports?: Array<{from: string, to: string, type_only: boolean, names: string[]}>, tables?: string[],
 *   schemaFile?: string, features?: Array<{id: string, area: string}>, workstreams?: Array<{id: string, features?: string[], gaps?: string[]}>,
 *   gapEvidence?: Map<string, string[] | undefined>, work?: any}} input
 */
export function computeContexts(cfg, { files = [], imports = [], tables = [], schemaFile = null, features = [], workstreams = [], gapEvidence = new Map(), work = null }) {
  const contexts = cfg.contexts ?? [];
  const byId = new Map(contexts.map((c) => [c.id, c]));
  const matchers = matchersOf(cfg);
  const owner = new Map();
  const unowned = [];
  for (const f of files) {
    const o = ownerOf(f, matchers);
    if (o?.ctx) owner.set(f, o.ctx);
    else unowned.push(f);
  }
  const tableOwner = new Map();
  for (const c of contexts) for (const t of c.owns?.tables ?? []) tableOwner.set(t, c.id);
  const tableSet = new Set(tables);
  const declared = new Map(contexts.map((c) => [c.id, new Set((c.interfaces ?? []).filter((i) => i.status === "defined").map((i) => i.path))]));
  const isShared = (id) => byId.get(id)?.kind === "shared";

  const blank = () => ({ interface: 0, reach: 0, reach_types: 0 });
  const uses = new Map(contexts.map((c) => [c.id, new Map()]));
  const ifaceUse = new Map();
  const implicit = new Map();
  const reachFiles = new Map();
  const tableUse = new Map();
  for (const e of imports) {
    const a = owner.get(e.from);
    if (!a) continue;
    if (e.to === schemaFile) {
      for (const n of e.names) if (tableSet.has(n)) {
        const t = tableOwner.get(n);
        if (t && t !== a) tableUse.set(n, new Set([...(tableUse.get(n) ?? []), a]));
      }
      continue;
    }
    const b = owner.get(e.to);
    if (!b || a === b) continue;
    const u = uses.get(a).get(b) ?? blank();
    uses.get(a).set(b, u);
    if (isShared(b)) { u.interface++; continue; }
    if (declared.get(b).has(e.to)) {
      u.interface++;
      const k = `${b}|${e.to}`;
      ifaceUse.set(k, new Set([...(ifaceUse.get(k) ?? []), a]));
      continue;
    }
    if (e.type_only) u.reach_types++;
    else u.reach++;
    const k = `${b}|${e.to}`;
    const cur = implicit.get(k) ?? { path: e.to, used_by: new Set(), uses: 0 };
    cur.used_by.add(a);
    cur.uses++;
    implicit.set(k, cur);
    const rk = `${a}|${b}`;
    reachFiles.set(rk, [...(reachFiles.get(rk) ?? []), { from: e.from, to: e.to, type_only: e.type_only }]);
  }

  // A workstream touches the contexts that own the code its gaps' evidence names. Its features are a
  // broader guess (a workstream lists every feature it changes, docs included), used only when no
  // gap names code.
  const featureCtx = featureContexts(cfg, features);
  const wsCtx = {};
  const wsBasis = {};
  for (const w of workstreams) {
    const set = new Set();
    for (const g of w.gaps ?? []) for (const p of evidencePaths(gapEvidence.get(g), cfg.scope ?? ["src/"])) {
      const o = ownerOf(p, matchers);
      if (o?.ctx) set.add(o.ctx);
    }
    wsBasis[w.id] = set.size ? "code" : "features";
    if (!set.size) for (const f of w.features ?? []) if (featureCtx.get(f)) set.add(featureCtx.get(f));
    wsCtx[w.id] = [...set].sort();
  }

  const reachBetween = (a, b) => {
    const x = uses.get(a)?.get(b) ?? blank();
    const y = uses.get(b)?.get(a) ?? blank();
    return x.reach + x.reach_types + y.reach + y.reach_types;
  };
  // Lanes: agent-ready workstreams that touch no context another lane touches, in the order the Work
  // view ranks them (phase, then what they unlock). Reach-ins between two lanes' contexts are the risk
  // that remains: the code still couples them even though the work does not overlap.
  const lanes = [];
  if (work?.ws) {
    const order = { "1": 1, "2": 2, "3": 3 };
    const ready = Object.keys(work.ws).filter((id) => work.ws[id].classes.includes("agent-ready") && wsCtx[id]?.length)
      .sort((x, y) => (order[work.ws[x].phase] ?? 9) - (order[work.ws[y].phase] ?? 9) || work.ws[y].unlocks - work.ws[x].unlocks || (x < y ? -1 : 1));
    const taken = new Set();
    for (const id of ready) {
      if (wsCtx[id].some((c) => taken.has(c))) continue;
      for (const c of wsCtx[id]) taken.add(c);
      lanes.push({ ws: id, contexts: wsCtx[id], phase: work.ws[id].phase, unlocks: work.ws[id].unlocks });
    }
    for (const l of lanes) {
      l.coupled_with = lanes.filter((o) => o !== l)
        .map((o) => ({ ws: o.ws, reach: l.contexts.reduce((n, a) => n + o.contexts.reduce((m, b) => m + reachBetween(a, b), 0), 0) }))
        .filter((o) => o.reach > 0);
    }
  }

  const domain = contexts.filter((c) => c.kind === "domain").map((c) => c.id);
  const pairs = [];
  for (let i = 0; i < domain.length; i++) for (let j = i + 1; j < domain.length; j++) {
    const a = domain[i], b = domain[j];
    const x = uses.get(a).get(b) ?? blank();
    const y = uses.get(b).get(a) ?? blank();
    if (!(x.interface + x.reach + x.reach_types + y.interface + y.reach + y.reach_types)) continue;
    pairs.push({ a, b, interface: x.interface + y.interface, reach: x.reach + y.reach, reach_types: x.reach_types + y.reach_types });
  }

  const out = contexts.map((c) => {
    const owned = files.filter((f) => owner.get(f) === c.id);
    const reachIn = {};
    const reachOut = {};
    for (const [b, u] of uses.get(c.id)) if (u.reach + u.reach_types) reachOut[b] = u.reach + u.reach_types;
    for (const other of contexts) {
      const u = uses.get(other.id).get(c.id);
      if (u && u.reach + u.reach_types) reachIn[other.id] = u.reach + u.reach_types;
    }
    const wsIds = Object.keys(wsCtx).filter((id) => wsCtx[id].includes(c.id)).sort();
    return {
      id: c.id, name: c.name, kind: c.kind, summary: c.summary ?? "",
      features: features.filter((f) => featureCtx.get(f.id) === c.id).map((f) => f.id),
      files: owned.length,
      globs: c.owns?.code ?? [],
      tables: c.owns?.tables ?? [],
      tables_used_by_others: (c.owns?.tables ?? []).filter((t) => tableUse.has(t)).map((t) => ({ table: t, by: [...tableUse.get(t)].sort() })),
      interfaces: (c.interfaces ?? []).map((i) => ({ ...i, used_by: [...(ifaceUse.get(`${c.id}|${i.path}`) ?? [])].sort() })),
      implicit: [...implicit.values()].filter((v) => owner.get(v.path) === c.id).map((v) => ({ path: v.path, used_by: [...v.used_by].sort(), uses: v.uses }))
        .sort((x, y) => y.used_by.length - x.used_by.length || y.uses - x.uses || (x.path < y.path ? -1 : 1)),
      uses: Object.fromEntries([...uses.get(c.id)].sort()),
      reach_in: reachIn,
      reach_out: reachOut,
      reach_samples: Object.fromEntries([...reachFiles].filter(([k]) => k.startsWith(`${c.id}|`)).map(([k, list]) => [k.split("|")[1], list.slice(0, 5)])),
      workstreams: wsIds,
      agent_ready: work?.ws ? wsIds.filter((id) => work.ws[id]?.classes.includes("agent-ready")) : [],
    };
  });

  const reachTotal = out.reduce((n, c) => n + Object.values(c.reach_out).reduce((s, v) => s + v, 0), 0);
  const independent = domain.length * (domain.length - 1) / 2 - pairs.filter((p) => p.reach + p.reach_types).length;
  return {
    taken_at: cfg.taken_at ?? null,
    contexts: out,
    pairs,
    ws: wsCtx,
    ws_basis: wsBasis,
    lanes,
    unowned: { count: unowned.length, total: files.length, sample: unowned.slice(0, 40) },
    counts: {
      contexts: contexts.length,
      files: files.length,
      owned: files.length - unowned.length,
      reach_ins: reachTotal,
      implicit: out.reduce((n, c) => n + c.implicit.length, 0),
      defined: out.reduce((n, c) => n + c.interfaces.filter((i) => i.status === "defined").length, 0),
      missing: out.reduce((n, c) => n + c.interfaces.filter((i) => i.status === "missing").length, 0),
      shared_tables: out.reduce((n, c) => n + c.tables_used_by_others.length, 0),
      independent_pairs: independent,
      domain_pairs: domain.length * (domain.length - 1) / 2,
      lanes: lanes.length,
    },
  };
}
