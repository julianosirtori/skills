#!/usr/bin/env bash
# clip.sh: copy stdin to the system clipboard.
# Tries pbcopy (macOS), wl-copy (Wayland), xclip, xsel (X11) and clip.exe (WSL/Windows).
#
# Usage: printf '%s' "text" | bash clip.sh
# Prints the tool it used. Exits 1 when no clipboard tool works (the caller then
# shows the text for the user to copy by hand).

set -u

have() { command -v "$1" >/dev/null 2>&1; }

TEXT=$(cat)
[ -z "$TEXT" ] && { echo "error: nothing on stdin" >&2; exit 1; }

try() {
  local name=$1
  shift
  if printf '%s' "$TEXT" | "$@" >/dev/null 2>&1; then
    echo "copied with $name"
    exit 0
  fi
}

have pbcopy && try pbcopy pbcopy
[ -n "${WAYLAND_DISPLAY:-}" ] && have wl-copy && try wl-copy wl-copy
[ -n "${DISPLAY:-}" ] && have xclip && try xclip xclip -selection clipboard
[ -n "${DISPLAY:-}" ] && have xsel && try xsel xsel --clipboard --input
have clip.exe && try clip.exe clip.exe

echo "no clipboard tool available" >&2
exit 1
