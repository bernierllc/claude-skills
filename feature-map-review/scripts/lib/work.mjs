// Work view compute for the feature map: turns <map dir>/work.json (what each workstream needs
// first, what it waits on, who can do it) into the graph numbers the page's Work view draws.
// Pure functions only; build-map.mjs reads the files. The fields and classes are described in
// references/data-model.md (work.json) and SKILL.md (stage 8).
//
// Edge direction: when X's `needs` names Y, the edge runs Y -> X (Y lands first).
//   blocks   X cannot be built or shipped correctly before Y.
//   enables  X could ship first, but is cheaper or safer after Y.

export const EDGE_KINDS = new Set(["blocks", "enables"]);
export const WAIT_KINDS = new Set(["human", "external", "date", "decision"]);
// "human" is the person named by config.json owner_label; "agent+human" needs one step from them.
export const WHO = new Set(["agent", "agent+human", "human"]);
// Order is priority: a card is colored by the first class it has.
export const CLASSES = [
  "long-pole", "linchpin-blocker", "linchpin-enabler", "convergence", "human", "external", "decision", "date",
  "phase-inversion", "agent-ready", "ready", "leaf",
];
// How many transitive successors (or blocks predecessors) make a linchpin (or a convergence point).
export const LINCHPIN_MIN = 3;
// Phases in order, from config.json; a milestone covers some of them.
const DEFAULT_PHASES = ["now", "1", "2", "3"];

/** Every needs entry as an edge {from, to, kind, why}: `from` lands before `to`. */
export function edgesOf(work) {
  const out = [];
  for (const [id, w] of Object.entries(work?.workstreams ?? {})) {
    for (const n of w?.needs ?? []) out.push({ from: n.ws, to: id, kind: n.kind, why: n.why ?? "" });
  }
  return out;
}

/** The first cycle among blocks edges as [a, b, ..., a], or null. Deterministic: ids in sorted order. */
export function findBlocksCycle(edges) {
  const next = new Map();
  for (const e of edges) if (e.kind === "blocks") next.set(e.from, [...(next.get(e.from) ?? []), e.to]);
  for (const list of next.values()) list.sort();
  const state = new Map(); // 1 = on the current path, 2 = done
  const path = [];
  const visit = (id) => {
    state.set(id, 1);
    path.push(id);
    for (const to of next.get(id) ?? []) {
      if (state.get(to) === 1) return [...path.slice(path.indexOf(to)), to];
      if (!state.has(to)) { const c = visit(to); if (c) return c; }
    }
    path.pop();
    state.set(id, 2);
    return null;
  };
  for (const id of [...next.keys()].sort()) {
    if (state.has(id)) continue;
    const c = visit(id);
    if (c) return c;
  }
  return null;
}

/** Problems in work.json, as strings. `wsIds` is the Set of workstream ids in reviews.json; `phaseIds` the config phases in order. */
export function validateWork(work, wsIds, phaseIds = DEFAULT_PHASES) {
  const PHASE_ORDER = phaseIds.map(String);
  const problems = [];
  const where = "work.json";
  const isNum = (v, min) => typeof v === "number" && Number.isFinite(v) && v >= min;
  for (const s of ["S", "M", "L"]) if (!isNum(work.size_days?.[s], 0)) problems.push(`${where}: size_days.${s} must be a number of days`);
  for (const k of ["human", "external", "decision"]) if (!isNum(work.wait_days?.[k], 0)) problems.push(`${where}: wait_days.${k} must be a number of days`);
  const milestoneIds = new Set();
  for (const m of work.milestones ?? []) {
    if (!/^[a-z0-9-]+$/.test(m.id ?? "")) problems.push(`${where}: milestone id ${JSON.stringify(m.id)} must be lowercase words joined by -`);
    else if (milestoneIds.has(m.id)) problems.push(`${where}: milestone ${m.id} is listed twice`);
    milestoneIds.add(m.id);
    if (!m.label) problems.push(`${where}: milestone ${m.id} needs a label`);
    if (!Array.isArray(m.phases) || !m.phases.length || m.phases.some((p) => !PHASE_ORDER.includes(String(p)))) problems.push(`${where}: milestone ${m.id} phases must be a list of ${PHASE_ORDER.join(", ")}`);
  }
  for (const [id, w] of Object.entries(work.workstreams ?? {})) {
    const at = `${where}: ${id}`;
    if (!wsIds.has(id)) problems.push(`${at}: not a workstream in reviews.json`);
    if (w.who == null) problems.push(`${at}: who is missing; use ${[...WHO].join(", ")}`);
    else if (!WHO.has(w.who)) problems.push(`${at}: who ${JSON.stringify(w.who)}; use ${[...WHO].join(", ")}`);
    const seen = new Set();
    for (const n of w.needs ?? []) {
      if (n.ws === id) problems.push(`${at}: needs itself`);
      else if (!wsIds.has(n.ws)) problems.push(`${at}: needs ${JSON.stringify(n.ws)}, which is not a workstream in reviews.json`);
      if (!EDGE_KINDS.has(n.kind)) problems.push(`${at}: needs ${n.ws} with kind ${JSON.stringify(n.kind)}; use ${[...EDGE_KINDS].join(", ")}`);
      if (seen.has(n.ws)) problems.push(`${at}: needs ${n.ws} twice`);
      seen.add(n.ws);
    }
    for (const x of w.waits ?? []) {
      if (!WAIT_KINDS.has(x.kind)) problems.push(`${at}: wait kind ${JSON.stringify(x.kind)}; use ${[...WAIT_KINDS].join(", ")}`);
      if (!x.what) problems.push(`${at}: a ${x.kind} wait needs a what`);
    }
  }
  // A workstream with no record would be computed as ready with nothing before it, so every one needs a reviewed record.
  for (const id of wsIds) if (!work.workstreams?.[id]) problems.push(`${where}: ${id} has no record; add its needs, waits and who`);
  // A self edge is reported above; a cycle is two or more workstreams waiting on each other.
  const cycle = findBlocksCycle(edgesOf(work).filter((e) => e.from !== e.to));
  if (cycle) problems.push(`${where}: blocks edges form a cycle, so nothing in it can start: ${cycle.join(" -> ")}`);
  return problems;
}

/** Days a workstream takes: its size, plus one wait allowance per distinct wait kind (a date adds 0). */
export function durationOf(size, waits, work) {
  const base = work.size_days?.[size] ?? 0;
  const kinds = new Set((waits ?? []).map((x) => x.kind));
  let extra = 0;
  for (const k of kinds) if (k !== "date") extra += work.wait_days?.[k] ?? 0;
  return base + extra;
}

/** Every id reachable from `id` through `next` (a Map of id -> ids), excluding `id`. */
export function reach(id, next) {
  const seen = new Set();
  const stack = [...(next.get(id) ?? [])];
  while (stack.length) {
    const n = stack.pop();
    if (n === id || seen.has(n)) continue;
    seen.add(n);
    stack.push(...(next.get(n) ?? []));
  }
  return seen;
}

/**
 * Critical path method over blocks edges inside `scope` (a Set of ids). `preds` maps id -> blocks
 * predecessor ids; `dur` maps id -> days. Returns {days, nodes: {id: {es, ef, slack}}, path}, where
 * path is one longest chain in start-to-finish order (ties broken by id).
 */
export function cpm(scope, preds, dur) {
  const ids = [...scope].sort();
  const inScope = (id) => scope.has(id);
  const succs = new Map(ids.map((id) => [id, []]));
  for (const id of ids) for (const p of preds.get(id) ?? []) if (inScope(p)) succs.get(p).push(id);
  // Topological order (Kahn); validateWork has already refused cycles.
  const indeg = new Map(ids.map((id) => [id, (preds.get(id) ?? []).filter(inScope).length]));
  const queue = ids.filter((id) => indeg.get(id) === 0);
  const order = [];
  while (queue.length) {
    const id = queue.shift();
    order.push(id);
    for (const s of succs.get(id)) { indeg.set(s, indeg.get(s) - 1); if (indeg.get(s) === 0) queue.push(s); }
  }
  const es = new Map(), ef = new Map();
  for (const id of order) {
    const start = Math.max(0, ...(preds.get(id) ?? []).filter(inScope).map((p) => ef.get(p)));
    es.set(id, start);
    ef.set(id, start + (dur.get(id) ?? 0));
  }
  const days = Math.max(0, ...ef.values());
  const lf = new Map();
  for (const id of [...order].reverse()) {
    const s = succs.get(id);
    lf.set(id, s.length ? Math.min(...s.map((x) => lf.get(x) - (dur.get(x) ?? 0))) : days);
  }
  /** @type {Record<string, {es: number, ef: number, slack: number}>} */
  const nodes = {};
  for (const id of order) nodes[id] = { es: es.get(id), ef: ef.get(id), slack: lf.get(id) - ef.get(id) };
  const path = [];
  let cur = ids.filter((id) => nodes[id].slack === 0 && nodes[id].ef === days)[0];
  while (cur) {
    path.unshift(cur);
    const start = nodes[cur].es;
    cur = (preds.get(cur) ?? []).filter((p) => inScope(p) && nodes[p].slack === 0 && nodes[p].ef === start).sort()[0];
  }
  return { days, nodes, path };
}

/**
 * The Work view's data. `workstreams` is every workstream in reviews.json ({id, phase, size}).
 * Returns {milestones, ws, counts, git}; ws has an entry for every workstream, in or out of work.json.
 */
export function computeWork(work, workstreams, phaseIds = DEFAULT_PHASES) {
  const PHASE_ORDER = phaseIds.map(String);
  const listed = work.workstreams ?? {};
  const ids = workstreams.map((w) => w.id).sort();
  const byId = new Map(workstreams.map((w) => [w.id, w]));
  const edges = edgesOf(work).filter((e) => byId.has(e.from) && byId.has(e.to));
  const map = () => new Map(ids.map((id) => [id, []]));
  const pre = { blocks: map(), enables: map() };
  const post = { blocks: map(), enables: map() };
  const anyNext = map();
  for (const e of edges) {
    pre[e.kind].get(e.to).push(e.from);
    post[e.kind].get(e.from).push(e.to);
    anyNext.get(e.from).push(e.to);
  }
  const dur = new Map(ids.map((id) => [id, durationOf(byId.get(id).size, listed[id]?.waits, work)]));
  const phaseIdx = (p) => PHASE_ORDER.indexOf(String(p));

  /** @type {Record<string, any>} */
  const ws = {};
  for (const id of ids) {
    const w = listed[id] ?? {};
    const waits = w.waits ?? [];
    const kinds = new Set(waits.map((x) => x.kind));
    const unlocks = reach(id, post.blocks);
    const enablesReach = reach(id, post.enables);
    const why = (from, to) => edges.find((e) => e.from === from && e.to === to)?.why ?? "";
    ws[id] = {
      phase: byId.get(id).phase ?? null,
      size: byId.get(id).size ?? null,
      duration: dur.get(id),
      who: w.who ?? null,
      notes: w.notes ?? "",
      waits,
      needs: [...pre.blocks.get(id).map((p) => ({ ws: p, kind: "blocks", why: why(p, id) })), ...pre.enables.get(id).map((p) => ({ ws: p, kind: "enables", why: why(p, id) }))],
      unlocks_direct: [...post.blocks.get(id).map((s) => ({ ws: s, kind: "blocks", why: why(id, s) })), ...post.enables.get(id).map((s) => ({ ws: s, kind: "enables", why: why(id, s) }))],
      unlocks: unlocks.size,
      enables_reach: enablesReach.size,
      reach: reach(id, anyNext).size,
      milestones: {},
      long_pole: [],
      classes: [],
    };
    const c = new Set();
    const blocker = unlocks.size >= LINCHPIN_MIN;
    if (blocker) c.add("linchpin-blocker");
    if (!blocker && enablesReach.size >= LINCHPIN_MIN) c.add("linchpin-enabler");
    if (pre.blocks.get(id).length >= LINCHPIN_MIN) c.add("convergence");
    const noEdges = !pre.blocks.get(id).length && !pre.enables.get(id).length && !post.blocks.get(id).length && !post.enables.get(id).length;
    if (noEdges && !waits.length) c.add("leaf");
    const ready = !pre.blocks.get(id).length && !kinds.has("human") && !kinds.has("external") && !kinds.has("decision") && !kinds.has("date") && w.who !== "human";
    if (ready) c.add("ready");
    if (ready && w.who === "agent") c.add("agent-ready");
    if (kinds.has("human") || w.who === "human") c.add("human");
    for (const k of ["external", "date", "decision"]) if (kinds.has(k)) c.add(k);
    if (pre.blocks.get(id).some((p) => phaseIdx(byId.get(p).phase) > phaseIdx(byId.get(id).phase))) c.add("phase-inversion");
    ws[id].classSet = c;
  }

  const milestones = (work.milestones ?? []).map((m) => {
    const phases = new Set(m.phases.map(String));
    const scope = new Set();
    for (const id of ids) if (phases.has(String(byId.get(id).phase))) { scope.add(id); for (const p of reach(id, pre.blocks)) scope.add(p); }
    const r = cpm(scope, pre.blocks, dur);
    for (const [id, n] of Object.entries(r.nodes)) {
      ws[id].milestones[m.id] = n;
      if (n.slack === 0) { ws[id].long_pole.push(m.id); ws[id].classSet.add("long-pole"); }
    }
    return {
      id: m.id, label: m.label, phases: [...phases], days: r.days, critical_path: r.path, scope_count: scope.size,
      waiting_on_human: r.path.filter((id) => ws[id].classSet.has("human")).length,
    };
  });

  const counts = Object.fromEntries(CLASSES.map((k) => [k, 0]));
  for (const id of ids) {
    const w = ws[id];
    w.classes = CLASSES.filter((k) => w.classSet.has(k));
    w.primary = w.classes[0] ?? null;
    delete w.classSet;
    for (const k of w.classes) counts[k]++;
  }
  return {
    taken_at: work.taken_at ?? null,
    size_days: work.size_days ?? null,
    wait_days: work.wait_days ?? null,
    milestones,
    ws,
    counts,
    edges: { blocks: edges.filter((e) => e.kind === "blocks").length, enables: edges.filter((e) => e.kind === "enables").length },
    git: work.git ?? null,
  };
}
