#!/bin/bash
# leftovers.sh - read-only search for remnants of apps that are no longer installed.
# Prints candidates only; it never deletes anything. Verify each one before removing.
#
# Usage: leftovers.sh
# Compatible with the stock macOS bash 3.2.

set -u

human() {
  awk -v k="${1:-0}" 'BEGIN {
    if (k >= 1048576) printf "%.1f GB", k/1048576;
    else if (k >= 1024) printf "%.0f MB", k/1024;
    else printf "%d KB", k }'
}
kb() { du -skx "$1" 2>/dev/null | awk '{print $1}' | tail -1; }
tilde() { printf '%s' "${1/#$HOME/~}"; }
section() { printf '\n== %s ==\n' "$1"; }

IDS="$(mktemp -t mac-cleanup-ids)"
NAMES="$(mktemp -t mac-cleanup-names)"
TEAMS="$(mktemp -t mac-cleanup-teams)"
trap 'rm -f "$IDS" "$NAMES" "$TEAMS"' EXIT

# plutil prints its errors on stdout, so only echo the value when it succeeds.
plist_get() { local v; v=$(plutil -extract "$1" raw -o - "$2" 2>/dev/null) && printf '%s' "$v"; }

# Bundle ids and names of every app Spotlight knows about.
mdfind "kMDItemContentType == 'com.apple.application-bundle'" -attr kMDItemCFBundleIdentifier 2>/dev/null |
  awk -F'kMDItemCFBundleIdentifier = ' 'NF == 2 && $2 != "(null)" { print tolower($2) }' | sort -u > "$IDS"
mdfind "kMDItemContentType == 'com.apple.application-bundle'" 2>/dev/null |
  sed -E 's|.*/||; s|\.app$||' | tr '[:upper:]' '[:lower:]' | sort -u > "$NAMES"
# Developer Team IDs of installed apps: shared group containers are often named
# "<TEAMID>.<suffix>" (e.g. UBF8T346G9.Office belongs to every Microsoft app).
for app in /Applications/*.app /Applications/*/*.app "$HOME/Applications"/*.app; do
  [ -d "$app" ] && codesign -dv "$app" 2>&1 | sed -n 's/^TeamIdentifier=//p'
done | grep -v '^not set$' | sort -u > "$TEAMS"

# True when an installed app owns this bundle-id-like string: exact match,
# an extension of an app (app.id.Extension), or the app id extends it.
owned() {
  local id; id=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  awk -v c="$id" '$0 == c || index(c, $0 ".") == 1 || index($0, c ".") == 1 { found = 1; exit } END { exit !found }' "$IDS"
}

section "Containers with no matching app (sandbox data of removed apps)"
for d in "$HOME/Library/Containers"/*; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  case "$name" in com.apple.*) continue ;; esac
  id="$name"
  # Some containers are named by UUID; the real bundle id is in the metadata.
  if printf '%s' "$name" | grep -Eq '^[0-9A-F-]{36}$'; then
    id=$(plist_get MCMMetadataIdentifier "$d/.com.apple.containermanagerd.metadata.plist" || echo "$name")
    case "$id" in com.apple.*) continue ;; esac
  fi
  owned "$id" && continue
  k=$(kb "$d"); [ "${k:-0}" -ge 1024 ] || continue
  printf '%10s  %s  (%s)\n' "$(human "$k")" "$(tilde "$d")" "$id"
done

section "Group Containers with no matching app"
for d in "$HOME/Library/Group Containers"/*; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  case "$name" in group.com.apple.*|*.com.apple.*|com.apple.*) continue ;; esac
  team=$(printf '%s' "$name" | sed -nE 's/^([A-Z0-9]{10})\..*/\1/p')
  [ -n "$team" ] && grep -qxF "$team" "$TEAMS" && continue
  # Strip "group." and a leading Team ID ("ABCDE12345.") to get the app id.
  id=$(printf '%s' "$name" | sed -E 's/^group\.//; s/^[A-Z0-9]{10}\.//; s/^group\.//')
  owned "$id" && continue
  k=$(kb "$d"); [ "${k:-0}" -ge 1024 ] || continue
  printf '%10s  %s\n' "$(human "$k")" "$(tilde "$d")"
done

section "Application Support folders (>= 100 MB) whose name matches no installed app - verify"
for d in "$HOME/Library/Application Support"/*; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  case "$name" in
    com.apple.*|Apple|AddressBook|CallHistory*|CloudDocs|CrashReporter|Knowledge|MobileSync|iCloud|FileProvider|Dock|DiskImages|networkserviceproxy|Animoji|CloudKit|Caches) continue ;;
  esac
  k=$(kb "$d"); [ "${k:-0}" -ge $((100 * 1024)) ] || continue
  lname=$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')
  owned "$name" && continue
  grep -qiF "$lname" "$NAMES" && continue
  grep -qiF ".$lname" "$IDS" && continue
  printf '%10s  %s\n' "$(human "$k")" "$(tilde "$d")"
done

section "Launch agents/daemons pointing to programs that no longer exist"
for plist in "$HOME/Library/LaunchAgents"/*.plist /Library/LaunchAgents/*.plist /Library/LaunchDaemons/*.plist; do
  [ -f "$plist" ] && [ -r "$plist" ] || continue
  prog=$(plist_get Program "$plist" || plist_get ProgramArguments.0 "$plist")
  case "$prog" in /*) ;; *) continue ;; esac
  [ -e "$prog" ] && continue
  label=$(plist_get Label "$plist")
  printf '  %s\n    label: %s\n    missing: %s\n' "$(tilde "$plist")" "$label" "$(tilde "$prog")"
done

section "Broken command-line links and wrappers"
for bindir in /usr/local/bin /opt/homebrew/bin "$HOME/.local/bin"; do
  [ -d "$bindir" ] || continue
  for f in "$bindir"/*; do
    if [ -L "$f" ] && [ ! -e "$f" ]; then
      printf '  %s -> %s (target missing)\n' "$(tilde "$f")" "$(tilde "$(readlink "$f")")"
    elif [ -f "$f" ] && [ "$(stat -f %z "$f")" -lt 4096 ]; then
      # Small shell wrappers that exec an app bundle that is gone (e.g. VirtualBox).
      app=$(grep -IEo '/Applications/[^"/]+\.app' "$f" 2>/dev/null | head -1)
      [ -n "$app" ] && [ ! -e "$app" ] && printf '  %s (wrapper for missing %s)\n' "$(tilde "$f")" "$app"
    fi
  done
done

LOGI="/Library/Application Support/Logi/LogiOptionsPlus"
if [ -d "$LOGI/depots" ]; then
  section "Logi Options+ update depots not referenced by the app"
  for dep in "$LOGI/depots"/*; do
    [ -d "$dep" ] || continue
    id=$(basename "$dep")
    grep -qF "$id" "$LOGI/current.json" "$LOGI/next.json" "$LOGI/installation.json" 2>/dev/null && continue
    printf '%10s  %s\n' "$(human "$(kb "$dep")")" "$dep"
  done
fi

ADOBE_DB="/Library/Application Support/Adobe/caps/hdpim.db"
if [ -f "$ADOBE_DB" ] && command -v sqlite3 >/dev/null 2>&1; then
  section "Adobe products still registered but missing from disk (block the Creative Cloud uninstaller)"
  sqlite3 -readonly "$ADOBE_DB" "SELECT p.SAPCode, p.ProductVersion, m.Value FROM product_installation_info p
    JOIN product_installation_meta_info m ON m.SAPCode = p.SAPCode AND m.ProductVersion = p.ProductVersion
    WHERE m.Key = 'InstallDir';" 2>/dev/null | while IFS='|' read -r sap ver dir; do
      [ -e "$dir" ] && continue
      base=$(sqlite3 -readonly "$ADOBE_DB" "SELECT Value FROM product_installation_meta_info WHERE SAPCode='$sap' AND ProductVersion='$ver' AND Key='BaseVersion';" 2>/dev/null)
      plat=$(sqlite3 -readonly "$ADOBE_DB" "SELECT Value FROM product_installation_meta_info WHERE SAPCode='$sap' AND ProductVersion='$ver' AND Key='Platform';" 2>/dev/null)
      printf '  %s %s (was in %s) base=%s platform=%s\n' "$sap" "$ver" "$dir" "$base" "$plat"
    done
fi

echo
echo "These are candidates, not verdicts. See references/uninstall.md before removing anything."
