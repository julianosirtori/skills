#!/bin/bash
# scan.sh - read-only disk usage report for macOS.
# Never deletes or modifies anything except its own history file.
#
# Usage: scan.sh [--no-history] [--min-mb N]
#   --no-history  do not record this run in the history file
#   --min-mb N    hide entries smaller than N MB (default 100)
#
# History lives in ${XDG_STATE_HOME:-~/.local/state}/mac-cleanup/history.tsv,
# so the next run can show what grew since the last one.
# Compatible with the stock macOS bash 3.2.

set -u

MIN_MB=100
RECORD=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-history) RECORD=0 ;;
    --min-mb) shift; MIN_MB="${1:-100}" ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/mac-cleanup"
HISTORY="$STATE_DIR/history.tsv"
MIN_KB=$((MIN_MB * 1024))
DU_CACHE="$(mktemp -t mac-cleanup-du)"
SNAPSHOT="$(mktemp -t mac-cleanup-snap)"
trap 'rm -f "$DU_CACHE" "$SNAPSHOT"' EXIT

human() { # KB -> human readable
  awk -v k="${1:-0}" 'BEGIN {
    if (k >= 1048576) printf "%.1f GB", k/1048576;
    else if (k >= 1024) printf "%.0f MB", k/1024;
    else printf "%d KB", k }'
}

tilde() { printf '%s' "${1/#$HOME/~}"; }

kb() { # size of a path in KB; reuses the home scan when possible
  [ -e "$1" ] || { echo 0; return; }
  local hit
  hit=$(awk -F'\t' -v p="$1" '$2 == p {print $1; exit}' "$DU_CACHE")
  if [ -n "$hit" ]; then echo "$hit"; return; fi
  du -skx "$1" 2>/dev/null | awk '{print $1}' | tail -1
}

section() { printf '\n== %s ==\n' "$1"; }

print_rows() { # stdin: "kb<TAB>path", prints the biggest above the threshold
  sort -rn | head -n "${1:-12}" | while IFS=$'\t' read -r k p; do
    [ "$k" -ge "$MIN_KB" ] || continue
    printf '%10s  %s\n' "$(human "$k")" "$(tilde "$p")"
  done
}

children_cached() { # direct children of a dir, from the home scan
  awk -F'\t' -v d="$1" '{ parent = $2; sub(/\/[^\/]*$/, "", parent); if (parent == d) print }' "$DU_CACHE" | print_rows "${2:-12}"
}

children_live() { # direct children of a dir outside the home scan
  [ -d "$1" ] || return
  du -skx "$1"/* "$1"/.[!.]* 2>/dev/null | print_rows "${2:-12}"
}

remember() { printf '%s\t%s\n' "$1" "$2" >> "$SNAPSHOT"; }

# ---------------------------------------------------------------- disk
section "Disk"
DATA_VOL=/System/Volumes/Data
[ -d "$DATA_VOL" ] || DATA_VOL=/
df -k "$DATA_VOL" | awk 'NR==2 {
  printf "size %.0f GB | used %.0f GB | free %.1f GB (%s used)\n", $2/1048576, $3/1048576, $4/1048576, $5 }'
remember "free space" "$(df -k "$DATA_VOL" | awk 'NR==2 {print $4}')"
echo "Trash: $(human "$(du -skx "$HOME/.Trash" 2>/dev/null | awk '{print $1}')")"
SNAPS=$(tmutil listlocalsnapshots / 2>/dev/null | grep -c 'com.apple')
echo "APFS local snapshots: $SNAPS (Time Machine / OS-update snapshots hold space until macOS purges them)"

# One pass over the home folder, three levels deep; everything below reuses it.
echo "Scanning home folder (this can take a minute or two)..." >&2
du -kx -d 3 "$HOME" 2>/dev/null > "$DU_CACHE"

section "Home folder"
children_cached "$HOME" 15
section "Library"
children_cached "$HOME/Library" 12
for sub in "Application Support" "Caches" "Containers" "Group Containers"; do
  section "Library/$sub"
  children_cached "$HOME/Library/$sub" 8
done

# ---------------------------------------------------------------- apps
section "Applications (biggest)"
children_live /Applications 15
section "/Library (system-wide, mostly root-owned)"
children_live /Library 8
section "/Library/Application Support"
children_live "/Library/Application Support" 8

# ---------------------------------------------------------------- hotspots
# label|path - places that tend to grow. See references/locations.md for what
# each one is and whether it is safe to clean.
section "Known hotspots"
HOTSPOTS="WhatsApp media (manage in-app)|$HOME/Library/Group Containers/group.net.whatsapp.WhatsApp.shared
Telegram media (manage in-app)|$HOME/Library/Group Containers/6N38VWS5BX.ru.keepcoder.Telegram
iCloud Drive local copies|$HOME/Library/Mobile Documents
iPhone/iPad backups (Finder)|$HOME/Library/Application Support/MobileSync/Backup
Xcode DerivedData|$HOME/Library/Developer/Xcode/DerivedData
Xcode Archives|$HOME/Library/Developer/Xcode/Archives
iOS DeviceSupport|$HOME/Library/Developer/Xcode/iOS DeviceSupport
iOS Simulators|$HOME/Library/Developer/CoreSimulator/Devices
Docker Desktop disk image|$HOME/Library/Containers/com.docker.docker
Android SDK|$HOME/Library/Android/sdk
Android emulators|$HOME/.android/avd
npm cache|$HOME/.npm
pnpm store|$HOME/Library/pnpm/store
Yarn cache|$HOME/Library/Caches/Yarn
pip cache|$HOME/Library/Caches/pip
Homebrew downloads cache|$HOME/Library/Caches/Homebrew
Homebrew install|/opt/homebrew
Gradle caches|$HOME/.gradle/caches
CocoaPods cache|$HOME/Library/Caches/CocoaPods
Cargo registry|$HOME/.cargo/registry
Go module cache|$HOME/go/pkg/mod
Playwright browsers|$HOME/Library/Caches/ms-playwright
VS Code extensions|$HOME/.vscode/extensions
VS Code extension installers cache|$HOME/Library/Application Support/Code/CachedExtensionVSIXs
Cursor extensions|$HOME/.cursor/extensions
Chrome cache|$HOME/Library/Caches/Google/Chrome
Chrome profiles|$HOME/Library/Application Support/Google/Chrome
Chrome updater cache|$HOME/Library/Application Support/Google/GoogleUpdater/crx_cache
Biome - Siri/Spotlight data (macOS, do not delete)|$HOME/Library/Biome
CloudKit - iCloud cache (do not delete)|$HOME/Library/Caches/CloudKit
Claude Code old versions|$HOME/.local/share/claude/versions
Logi Options+ update depots|/Library/Application Support/Logi/LogiOptionsPlus/depots
Adobe shared files|/Library/Application Support/Adobe
Downloads|$HOME/Downloads"
for lib in "$HOME"/Pictures/*.photoslibrary; do
  [ -d "$lib" ] && HOTSPOTS="$HOTSPOTS
Photos library (do not touch inside)|$lib"
done
printf '%s\n' "$HOTSPOTS" | while IFS='|' read -r label path; do
  k=$(kb "$path")
  remember "$label" "$k"
  [ "$k" -ge "$MIN_KB" ] && printf '%s\t%s\t%s\n' "$k" "$label" "$path"
done | sort -rn | while IFS=$'\t' read -r k label path; do
  printf '%10s  %-50s %s\n' "$(human "$k")" "$label" "$(tilde "$path")"
done
for lib in "$HOME"/Pictures/*.photoslibrary; do
  [ -d "$lib/originals" ] && echo "  $(basename "$lib"): originals stored locally = $(human "$(kb "$lib/originals")") (small means 'Optimize Mac Storage' is on)"
done

# ---------------------------------------------------------------- downloads
if [ -d "$HOME/Downloads" ]; then
  section "Downloads"
  OLD_KB=$(find "$HOME/Downloads" -mindepth 1 -maxdepth 1 -mtime +60 -print0 2>/dev/null |
    xargs -0 du -sk 2>/dev/null | awk '{s += $1} END {print s + 0}')
  echo "Items older than 60 days: $(human "$OLD_KB")"
  echo "Largest files:"
  find "$HOME/Downloads" -type f -size +50M 2>/dev/null | while read -r f; do
    printf '%s\t%s\n' "$(du -sk "$f" | awk '{print $1}')" "$f"
  done | sort -rn | head -10 | while IFS=$'\t' read -r k f; do
    printf '%10s  %s\n' "$(human "$k")" "$(tilde "$f")"
  done
  echo "Archives that look already extracted (a folder with the same name sits next to them):"
  find "$HOME/Downloads" -maxdepth 2 -type f \( -iname '*.zip' -o -iname '*.rar' -o -iname '*.7z' -o -iname '*.tar.gz' -o -iname '*.tgz' \) 2>/dev/null |
    while read -r a; do
      base="${a%.*}"; base="${base%.tar}"
      [ -d "$base" ] && printf '%10s  %s\n' "$(human "$(du -sk "$a" | awk '{print $1}')")" "$(tilde "$a")"
    done
  echo "Installers (.dmg / .pkg):"
  find "$HOME/Downloads" -maxdepth 2 -type f \( -iname '*.dmg' -o -iname '*.pkg' \) 2>/dev/null |
    while read -r f; do printf '%10s  %s\n' "$(human "$(du -sk "$f" | awk '{print $1}')")" "$(tilde "$f")"; done
fi

# ---------------------------------------------------------------- dev
section "node_modules (days since last install)"
for root in "$HOME/Developer" "$HOME/Projects" "$HOME/projects" "$HOME/code" "$HOME/dev" "$HOME/src" "$HOME/workspace" "$HOME/repos" "$HOME/git"; do
  [ -d "$root" ] && find "$root" -maxdepth 4 -type d -name node_modules -prune 2>/dev/null
done | sort -u | while read -r nm; do
  k=$(du -skx "$nm" 2>/dev/null | awk '{print $1}')
  [ "${k:-0}" -ge $((50 * 1024)) ] || continue
  days=$(( ( $(date +%s) - $(stat -f %m "$nm") ) / 86400 ))
  printf '%s\t%s\t%s\n' "$k" "$days" "$nm"
done | sort -rn | while IFS=$'\t' read -r k days nm; do
  printf '%10s  %4sd  %s\n' "$(human "$k")" "$days" "$(tilde "$nm")"
done

if command -v brew >/dev/null 2>&1; then
  section "Homebrew formulae you installed (largest; their dependencies not counted)"
  CELLAR="$(brew --cellar 2>/dev/null)"
  brew leaves 2>/dev/null | while read -r f; do
    short="${f##*/}"
    k=$(du -skx "$CELLAR/$short" 2>/dev/null | awk '{print $1}')
    [ "${k:-0}" -ge $((50 * 1024)) ] && printf '%s\t%s\n' "$k" "$short"
  done | sort -rn | head -10 | while IFS=$'\t' read -r k f; do
    users=$(brew uses --installed "$f" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')
    printf '%10s  %s (needed by: %s)\n' "$(human "$k")" "$f" "${users:-nothing}"
  done
fi

# ---------------------------------------------------------------- history
section "Changes since last scan (> 500 MB)"
if [ -s "$HISTORY" ]; then
  LAST_DATE=$(tail -1 "$HISTORY" | cut -f1)
  echo "Previous scan: $LAST_DATE"
  awk -F'\t' -v d="$LAST_DATE" 'NR == FNR { if ($1 == d) prev[$2] = $3; next }
    ($1 in prev) {
      delta = $2 - prev[$1]; abs = delta < 0 ? -delta : delta
      if (abs < 512000) next
      sign = delta < 0 ? "-" : "+"
      if (abs >= 1048576) printf "%10s  %s\n", sign sprintf("%.1f GB", abs/1048576), $1
      else printf "%10s  %s\n", sign sprintf("%.0f MB", abs/1024), $1
      shown = 1
    }
    END { if (!shown) print "  nothing changed by more than 500 MB" }' "$HISTORY" "$SNAPSHOT"
else
  echo "No previous scan recorded."
fi

if [ "$RECORD" -eq 1 ]; then
  mkdir -p "$STATE_DIR"
  NOW=$(date '+%Y-%m-%dT%H:%M:%S')
  awk -F'\t' -v d="$NOW" 'NF == 2 {print d "\t" $1 "\t" $2}' "$SNAPSHOT" >> "$HISTORY"
  echo "(recorded in $(tilde "$HISTORY"))"
fi

echo
echo "If folders show 0 or 'Operation not permitted', give your terminal app Full Disk Access"
echo "(System Settings > Privacy & Security > Full Disk Access) and run again."
