// The plan frontmatter subset, shared by check-plans.mjs (which validates it), build-map.mjs
// (which reads it) and gaps.mjs (which rewrites `gaps:`), so they never parse a plan
// differently. Deliberately not a YAML parser: `key: scalar`, `key: [a, b]`, and, for LISTS
// keys only, `key:` followed by `- item` lines; a trailing ` # comment` is dropped. LF only.

export const LISTS = new Set(["depends_on", "blocked_by", "prs", "supersedes", "features", "gaps"]);

// A plan's `features:` entries name what it does to each feature: `<verb>:<feature id>`,
// with ids from features.json.
export const FEATURE_VERBS = ["adds", "changes", "fixes", "removes"];
export const FEATURE_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const FEATURE = new RegExp(`^(${FEATURE_VERBS.join("|")}):(${FEATURE_ID.source.slice(1, -1)})$`);

// A plan's `gaps:` entries are the gaps it closes, by their permanent ids in gaps.json.
// `gaps: []` when it closes none.
export const GAP_ID = /^GAP-\d{4,}$/;
export const gapNum = (id) => Number(String(id).slice(4));
export const gapIdOf = (n) => `GAP-${String(n).padStart(4, "0")}`;

// Strips one pair of matching quotes; a double-quoted value may escape `"` and `\` with `\`.
export const unquote = (s) => {
  const m = s.trim().match(/^(["'])(.*)\1$/);
  if (!m) return s.trim();
  return m[1] === '"' ? m[2].replace(/\\(["\\])/g, "$1") : m[2];
};

/** The frontmatter as { key: string | string[] }, or null when the file has no closed leading block. */
export function frontmatter(text) {
  const end = text.startsWith("---\n") ? text.indexOf("\n---\n", 3) : -1;
  if (end === -1) return null;
  const out = {};
  let list = null;
  for (const raw of text.slice(4, end).split("\n")) {
    const item = raw.match(/^\s*- (.+)$/);
    if (list && item) { out[list].push(unquote(item[1])); continue; }
    const kv = raw.match(/^([\w-]+):(.*)$/);
    if (!kv) continue;
    const t = kv[2].trim();
    // A quoted value keeps a `#` inside its quotes; the closing quote must match the opening one.
    const v = /^["']/.test(t) ? t.replace(/^((["'])(?:\\.|(?!\2).)*\2)\s+#.*$/, "$1") : t.replace(/\s+#.*$/, "");
    list = v === "" && LISTS.has(kv[1]) ? kv[1] : null;
    out[kv[1]] = list ? [] : /^\[.*\]$/.test(v) ? v.slice(1, -1).split(",").map(unquote).filter(Boolean) : unquote(v);
  }
  return out;
}

/**
 * Rewrites (or inserts) a one-line `key: [a, b]` list in the frontmatter, replacing any
 * existing block form of the same key. Inserted after `features` when absent. Returns the
 * new text, or the text unchanged when it has no frontmatter.
 */
export function setListField(text, key, values) {
  const end = text.startsWith("---\n") ? text.indexOf("\n---\n", 3) : -1;
  if (end === -1) return text;
  const lines = text.slice(4, end).split("\n");
  const line = `${key}: [${values.join(", ")}]`;
  const at = lines.findIndex((l) => l.startsWith(`${key}:`));
  if (at !== -1) {
    let j = at + 1;
    while (j < lines.length && /^\s*- /.test(lines[j])) j++;
    lines.splice(at, j - at, line);
  } else {
    let i = lines.findIndex((l) => l.startsWith("features:"));
    if (i === -1) i = lines.length - 1;
    else { i++; while (i < lines.length && /^\s*- /.test(lines[i])) i++; i--; }
    lines.splice(i + 1, 0, line);
  }
  return "---\n" + lines.join("\n") + text.slice(end);
}
