#!/bin/bash
# safe-clean.sh - clears caches that rebuild themselves on demand.
# DRY RUN by default: it only reports what it would free. Pass --apply to act.
#
# Usage: safe-clean.sh [--apply] [--only id,id] [--skip id,id] [--list]
#
# Nothing here touches documents, media, app data or settings. Caches are
# deleted; obsolete editor extension folders are moved to the Trash.
# Compatible with the stock macOS bash 3.2.

set -u

APPLY=0
ONLY=""
SKIP=""
TARGETS="npm pnpm yarn pip brew dev-caches xcode-derived vscode-vsix vscode-obsolete chrome-updater chrome-cache"

describe() {
  case "$1" in
    npm) echo "npm download cache (npm cache clean --force)" ;;
    pnpm) echo "pnpm store: packages no project references anymore (pnpm store prune)" ;;
    yarn) echo "Yarn classic cache (yarn cache clean)" ;;
    pip) echo "pip download cache (pip cache purge)" ;;
    brew) echo "Homebrew downloads and old versions (brew cleanup --prune=all)" ;;
    dev-caches) echo "build/tool caches in ~/Library/Caches (node-gyp, go-build, CocoaPods, dotslash...)" ;;
    xcode-derived) echo "Xcode DerivedData build products (skipped while Xcode runs)" ;;
    vscode-vsix) echo "VS Code / Cursor cached extension installers (.vsix)" ;;
    vscode-obsolete) echo "VS Code / Cursor extension folders the editor marked obsolete (to Trash)" ;;
    chrome-updater) echo "Google Updater downloaded update packages" ;;
    chrome-cache) echo "Chrome browser cache (skipped while Chrome runs)" ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --only) shift; ONLY=",${1:-},"; ;;
    --skip) shift; SKIP=",${1:-},"; ;;
    --list) for t in $TARGETS; do printf '%-16s %s\n' "$t" "$(describe "$t")"; done; exit 0 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$(id -u)" -eq 0 ]; then
  echo "Do not run this as root: it only cleans your own user caches." >&2
  exit 1
fi

human() {
  awk -v k="${1:-0}" 'BEGIN {
    if (k >= 1048576) printf "%.1f GB", k/1048576;
    else if (k >= 1024) printf "%.0f MB", k/1024;
    else printf "%d KB", k }'
}

size_kb() { # total KB of the given paths
  local total=0 p k
  for p in "$@"; do
    [ -e "$p" ] || continue
    k=$(du -skx "$p" 2>/dev/null | awk '{print $1}')
    total=$((total + ${k:-0}))
  done
  echo "$total"
}

# Delete cache directories. Guards: only paths inside $HOME, never $HOME itself.
remove_paths() {
  local p
  for p in "$@"; do
    [ -e "$p" ] || continue
    case "$p" in
      "$HOME"/?*) ;;
      *) echo "  refusing to delete outside home: $p" >&2; continue ;;
    esac
    chmod -R u+w "$p" 2>/dev/null   # some tools (dotslash) extract read-only files
    rm -rf "$p"
  done
}

to_trash() {
  local p
  for p in "$@"; do
    [ -e "$p" ] || continue
    if [ -x /usr/bin/trash ]; then
      /usr/bin/trash "$p"
    else
      osascript -e 'on run argv' -e 'tell application "Finder" to delete (POSIX file (item 1 of argv) as alias)' -e 'end run' "$p" >/dev/null
    fi
  done
}

running() { pgrep -x "$1" >/dev/null 2>&1; }

json_keys_or_paths() { # $1 = mode (installed|obsolete), $2 = extensions dir
  local dir="$2"
  if command -v jq >/dev/null 2>&1; then
    if [ "$1" = installed ]; then jq -r '.[].relativeLocation // empty' "$dir/extensions.json" 2>/dev/null
    else jq -r 'keys[]' "$dir/.obsolete" 2>/dev/null; fi
  else
    python3 - "$1" "$dir" <<'EOF' 2>/dev/null
import json, sys, os
mode, d = sys.argv[1], sys.argv[2]
if mode == "installed":
    for e in json.load(open(os.path.join(d, "extensions.json"))):
        if e.get("relativeLocation"): print(e["relativeLocation"])
else:
    for k in json.load(open(os.path.join(d, ".obsolete"))): print(k)
EOF
  fi
}

# Folders listed in .obsolete and not referenced by extensions.json.
obsolete_extension_dirs() {
  local dir name installed
  for dir in "$HOME/.vscode/extensions" "$HOME/.vscode-insiders/extensions" "$HOME/.cursor/extensions"; do
    [ -f "$dir/.obsolete" ] && [ -f "$dir/extensions.json" ] || continue
    installed=$(json_keys_or_paths installed "$dir")
    json_keys_or_paths obsolete "$dir" | while read -r name; do
      [ -n "$name" ] && [ -d "$dir/$name" ] || continue
      printf '%s\n' "$installed" | grep -qxF "$name" && continue
      printf '%s\n' "$dir/$name"
    done
  done
}

TOTAL_KB=0
report() { # id, kb, note
  local verb="would free"
  [ "$APPLY" -eq 1 ] && verb="freed"
  printf '  %-10s %9s  %-16s %s\n' "$verb" "$(human "$2")" "$1" "${3:-$(describe "$1")}"
  TOTAL_KB=$((TOTAL_KB + $2))
}
skip() { printf '  %-10s %9s  %-16s %s\n' "skipped" "-" "$1" "$2"; }

# Each target measures its paths, acts only with --apply, then reports.
clean() {
  local id="$1" before after
  case "$id" in
    npm)
      command -v npm >/dev/null || { skip npm "npm not installed"; return; }
      before=$(size_kb "$HOME/.npm/_cacache")
      [ "$APPLY" -eq 1 ] && npm cache clean --force >/dev/null 2>&1
      after=$(size_kb "$HOME/.npm/_cacache") ;;
    pnpm)
      command -v pnpm >/dev/null || { skip pnpm "pnpm not installed"; return; }
      local store; store=$(pnpm store path 2>/dev/null)
      [ -n "$store" ] && [ -d "$store" ] || { skip pnpm "no pnpm store"; return; }
      before=$(size_kb "$store")
      if [ "$APPLY" -eq 1 ]; then pnpm store prune >/dev/null 2>&1; after=$(size_kb "$store")
      else report pnpm 0 "pnpm store is $(human "$before"); prune frees only unreferenced packages (size known after --apply)"; return; fi ;;
    yarn)
      command -v yarn >/dev/null || { skip yarn "yarn not installed"; return; }
      case "$(yarn --version 2>/dev/null)" in 1.*) ;; *) skip yarn "Yarn Berry keeps caches per project"; return ;; esac
      local ydir; ydir=$(yarn cache dir 2>/dev/null)
      before=$(size_kb "$ydir")
      [ "$APPLY" -eq 1 ] && yarn cache clean >/dev/null 2>&1
      after=$(size_kb "$ydir") ;;
    pip)
      before=$(size_kb "$HOME/Library/Caches/pip")
      [ "$before" -gt 0 ] || { skip pip "no pip cache"; return; }
      if [ "$APPLY" -eq 1 ]; then
        python3 -m pip cache purge >/dev/null 2>&1 || remove_paths "$HOME/Library/Caches/pip"
      fi
      after=$(size_kb "$HOME/Library/Caches/pip") ;;
    brew)
      command -v brew >/dev/null || { skip brew "Homebrew not installed"; return; }
      local bcache; bcache=$(brew --cache 2>/dev/null)
      before=$(size_kb "$bcache")
      if [ "$APPLY" -eq 1 ]; then
        brew cleanup --prune=all -s >/dev/null 2>&1
        after=$(size_kb "$bcache")
      else
        report brew "$before" "Homebrew download cache; old versions also removed (size known after --apply)"; return
      fi ;;
    dev-caches)
      local c paths=""
      for c in node-gyp pnpm dotslash goimports staticcheck typescript go-build CocoaPods deno; do
        [ -e "$HOME/Library/Caches/$c" ] && paths="$paths
$HOME/Library/Caches/$c"
      done
      [ -n "$paths" ] || { skip dev-caches "nothing to clean"; return; }
      local IFS=$'\n'
      # shellcheck disable=SC2086 # split on newlines on purpose
      before=$(size_kb $paths)
      # shellcheck disable=SC2086
      [ "$APPLY" -eq 1 ] && remove_paths $paths
      # shellcheck disable=SC2086
      after=$(size_kb $paths)
      unset IFS ;;
    xcode-derived)
      local dd="$HOME/Library/Developer/Xcode/DerivedData"
      [ -d "$dd" ] || { skip xcode-derived "no DerivedData"; return; }
      running Xcode && { skip xcode-derived "Xcode is running - quit it first"; return; }
      before=$(size_kb "$dd")
      [ "$APPLY" -eq 1 ] && remove_paths "$dd"
      after=$(size_kb "$dd") ;;
    vscode-vsix)
      local v1="$HOME/Library/Application Support/Code/CachedExtensionVSIXs" v2="$HOME/Library/Application Support/Cursor/CachedExtensionVSIXs"
      before=$(size_kb "$v1" "$v2")
      [ "$before" -gt 0 ] || { skip vscode-vsix "nothing cached"; return; }
      [ "$APPLY" -eq 1 ] && remove_paths "$v1" "$v2"
      after=$(size_kb "$v1" "$v2") ;;
    vscode-obsolete)
      local list; list=$(obsolete_extension_dirs)
      [ -n "$list" ] || { skip vscode-obsolete "no obsolete extension folders"; return; }
      local IFS=$'\n'
      # shellcheck disable=SC2086
      before=$(size_kb $list)
      # shellcheck disable=SC2086
      [ "$APPLY" -eq 1 ] && to_trash $list
      # shellcheck disable=SC2086
      after=$(size_kb $list)
      unset IFS
      local n; n=$(printf '%s\n' "$list" | wc -l | tr -d ' ')
      if [ "$APPLY" -eq 1 ]; then report vscode-obsolete $((before - after)) "$n obsolete extension folder(s) moved to Trash"
      else report vscode-obsolete "$before" "$n obsolete extension folder(s) to move to Trash"; fi
      return ;;
    chrome-updater)
      local cu="$HOME/Library/Application Support/Google/GoogleUpdater/crx_cache"
      before=$(size_kb "$cu")
      [ "$before" -gt 0 ] || { skip chrome-updater "nothing cached"; return; }
      [ "$APPLY" -eq 1 ] && remove_paths "$cu"
      after=$(size_kb "$cu") ;;
    chrome-cache)
      local cc="$HOME/Library/Caches/Google/Chrome"
      [ -d "$cc" ] || { skip chrome-cache "no Chrome cache"; return; }
      running "Google Chrome" && { skip chrome-cache "Chrome is open ($(human "$(size_kb "$cc")")) - quit it with Cmd+Q first"; return; }
      before=$(size_kb "$cc")
      [ "$APPLY" -eq 1 ] && remove_paths "$cc"
      after=$(size_kb "$cc") ;;
  esac
  if [ "$APPLY" -eq 1 ]; then report "$id" $((before - after)); else report "$id" "$before"; fi
}

DATA_VOL=/System/Volumes/Data
[ -d "$DATA_VOL" ] || DATA_VOL=/
FREE_BEFORE=$(df -k "$DATA_VOL" | awk 'NR==2 {print $4}')

if [ "$APPLY" -eq 1 ]; then echo "Cleaning (caches rebuild themselves when needed):"
else echo "Dry run - nothing is deleted. Re-run with --apply to clean:"; fi

for t in $TARGETS; do
  case "$ONLY" in ""|*",$t,"*) ;; *) continue ;; esac
  case "$SKIP" in *",$t,"*) continue ;; esac
  clean "$t"
done

echo
if [ "$APPLY" -eq 1 ]; then
  FREE_AFTER=$(df -k "$DATA_VOL" | awk 'NR==2 {print $4}')
  echo "Total freed: $(human "$TOTAL_KB") | free space: $(human "$FREE_BEFORE") -> $(human "$FREE_AFTER")"
  echo "Items moved to the Trash only free space once the Trash is emptied."
else
  echo "Total that would be freed: about $(human "$TOTAL_KB") (plus whatever pnpm/brew prune finds)"
fi
