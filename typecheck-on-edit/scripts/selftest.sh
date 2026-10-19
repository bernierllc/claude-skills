#!/usr/bin/env bash
# Runs the hook commands from ../hooks.json against scratch repos with a stub
# compiler, so it needs no TypeScript install. Exit 0 = all cases pass.
set -u
here=$(cd "$(dirname "$0")/.." && pwd)
cmd() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print([h["command"] for g in d["claude"] if g["id"]==sys.argv[2] for h in g["hooks"]][0])' "$here/hooks.json" "$1"; }
TC=$(cmd toe-typecheck); LF=$(cmd toe-lockfile-freshness)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
fail=0
check() { # name want_rc want_text got_rc got_text; empty want_text = no output allowed
  if [ "$4" != "$2" ] || { [ -z "$3" ] && [ -n "$5" ]; } || { [ -n "$3" ] && ! printf '%s' "$5" | grep -q -- "$3"; }; then echo "FAIL $1: rc=$4 (want $2) out=[$5]"; fail=1; fi
}
repo() { r="$tmp/$1"; mkdir -p "$r/node_modules/.bin"; echo '{}' > "$r/tsconfig.json"
  # stub tsgo: logs each -p it sees, fails with a TS2322 line when that dir holds a BROKEN file
  printf '%s\n' '#!/usr/bin/env bash' 'while [ $# -gt 0 ]; do [ "$1" = -p ] && p=$2; shift; done' 'echo "$p" >> calls' \
    '[ -e "$p/BROKEN" ] && { echo "$p/x.ts(1,1): error TS2322: bad"; exit 1; }; exit 0' > "$r/node_modules/.bin/tsgo"
  chmod +x "$r/node_modules/.bin/tsgo"; echo "$r"; }
run() { out=$(printf "%s" "${3:-}" | CLAUDE_PROJECT_DIR=$1 bash -c "$2" 2>&1); rc=$?; } # $3 = hook stdin JSON

r=$(repo clean); run "$r" "$TC"; check clean 0 "" $rc "$out"
r=$(repo broken); touch "$r/BROKEN"; run "$r" "$TC"; check diagnostic 2 TS2322 $rc "$out"
r=$(repo nocompiler); rm "$r/node_modules/.bin/tsgo"; touch "$r/BROKEN"; run "$r" "$TC"; check no-compiler 0 "" $rc "$out"
r=$(repo notsconfig); rm "$r/tsconfig.json"; touch "$r/BROKEN"; run "$r" "$TC"; check no-tsconfig 0 "" $rc "$out"
r=$(repo refs); mkdir "$r/app"; touch "$r/app/BROKEN"
printf '{\n "references": [\n  // { "path": "./gone" }\n  { "path": "./app" }\n ]\n}\n' > "$r/tsconfig.json"
run "$r" "$TC"; check reference-error 2 "app/x.ts" $rc "$out"
calls=$(tr '\n' '|' < "$r/calls"); [ "$calls" = ".|./app|" ] || { echo "FAIL references: checked [$calls], want [.|./app|]"; fail=1; }
r=$(repo spaced); mkdir "$r/my app"; printf '{ "references": [ { "path": "./my app" } ] }\n' > "$r/tsconfig.json"
run "$r" "$TC"; check spaced-path 0 "" $rc "$out"; touch "$r/my app/BROKEN"; run "$r" "$TC"; check spaced-path-error 2 "my app/x.ts" $rc "$out"

# the checked checkout follows the edited file, not CLAUDE_PROJECT_DIR (which stays put when Claude enters a worktree)
p=$(repo primary); w=$(repo worktree); git -C "$w" init -q; mkdir "$w/src"; touch "$w/BROKEN"
run "$p" "$TC" "{\"tool_input\":{\"file_path\":\"$w/src/a.ts\"}}"; check edited-checkout 2 TS2322 $rc "$out"
touch "$p/BROKEN"; rm "$w/BROKEN"; run "$p" "$TC" "{\"tool_input\":{\"file_path\":\"$w/src/a.ts\"}}"; check edited-checkout-clean 0 "" $rc "$out"

r=$(repo lockfresh); echo a > "$r/package-lock.json"; sleep 1; echo b > "$r/node_modules/.package-lock.json"
run "$r" "$LF"; check lock-fresh 0 "" $rc "$out"
sleep 1; touch "$r/package-lock.json"; run "$r" "$LF"; check lock-stale 0 "npm ci" $rc "$out"
r=$(repo pnpmmissing); rm -rf "$r/node_modules"; echo a > "$r/pnpm-lock.yaml"; run "$r" "$LF"; check pnpm-missing 0 "pnpm install" $rc "$out"
src=$(repo linksrc); echo a > "$src/package-lock.json"; r="$tmp/linked"; mkdir "$r"; ln -s "$src/node_modules" "$r/node_modules"
echo a > "$r/package-lock.json"; run "$r" "$LF"; check link-same 0 "" $rc "$out"
echo b > "$r/package-lock.json"; run "$r" "$LF"; check link-differs 0 "another checkout" $rc "$out"

[ $fail = 0 ] && echo "selftest: typecheck-on-edit hooks OK"; exit $fail
