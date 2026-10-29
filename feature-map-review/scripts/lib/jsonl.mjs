// Writes the data files with one record per line, so a diff shows one line per gap, feature,
// workstream or row instead of reformatting the whole file. Separators match Python's
// json.dumps defaults (", " and ": "), so files written by either language stay byte-identical.
import { writeFileSync } from "node:fs";

/** One JSON value on one line, Python-style separators. */
export function jl(v) {
  if (v === null || v === undefined) return "null";
  if (Array.isArray(v)) return "[" + v.map(jl).join(", ") + "]";
  if (typeof v === "object") return "{" + Object.entries(v).filter(([, x]) => x !== undefined).map(([k, x]) => JSON.stringify(k) + ": " + jl(x)).join(", ") + "}";
  return JSON.stringify(v);
}

/**
 * A top-level object: `head` keys one per line, then each section either a list (one record
 * per line, indented 4) or a map (one `"key": record` per line).
 */
export function writeLines(path, head, sections) {
  const parts = [];
  for (const [k, v] of Object.entries(head)) parts.push(`  ${jl(k)}: ${jl(v)}`);
  for (const [k, v, render = jl] of sections) {
    if (Array.isArray(v)) parts.push(v.length ? `  ${jl(k)}: [\n${v.map((x) => render(x)).join(",\n")}\n  ]` : `  ${jl(k)}: []`);
    else {
      const ents = Object.entries(v ?? {});
      parts.push(ents.length ? `  ${jl(k)}: {\n${ents.map(([kk, vv]) => `    ${jl(kk)}: ${render(vv)}`).join(",\n")}\n  }` : `  ${jl(k)}: {}`);
    }
  }
  writeFileSync(path, ["{", parts.join(",\n"), "}"].join("\n") + "\n");
}

export const listItem = (x) => "    " + jl(x);
