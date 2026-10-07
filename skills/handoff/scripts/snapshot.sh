#!/usr/bin/env bash
# snapshot.sh: read-only snapshot of where a project stands, as Markdown.
# The handoff records it so the next session can tell what changed since.
# Covers the git baseline (branch, HEAD, upstream, uncommitted files, diff stat,
# recent commits, stashes) and local TCP ports in LISTEN state.
#
# Usage: bash snapshot.sh [project-dir]   (default: current dir)
# Never modifies anything. Works outside git repos (prints what it can).

set -u

START="${1:-.}"
cd "$START" 2>/dev/null || { echo "error: cannot cd to $START" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# Indent stdin as a fenced block, or print "(none)" when empty.
block() {
  local out
  out=$(cat)
  if [ -z "$out" ]; then
    echo "(none)"
  else
    printf '```text\n%s\n```\n' "$out"
  fi
}

echo "## Snapshot"
echo
echo "- Taken: $(date '+%Y-%m-%d %H:%M %Z')"
echo "- Directory: $(pwd)"

if ! have git || ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "- Git: not a git repository"
else
  ROOT=$(git rev-parse --show-toplevel)
  cd "$ROOT" || exit 1
  echo "- Repo root: $ROOT"

  BRANCH=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo "(detached)")
  echo "- Branch: $BRANCH"

  if git rev-parse --verify --quiet HEAD >/dev/null; then
    echo "- HEAD: $(git log -1 --format='%h %s (%cr)')"
    echo "- HEAD full sha: $(git rev-parse HEAD)"
  else
    echo "- HEAD: (no commits yet)"
  fi

  UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)
  if [ -n "$UPSTREAM" ]; then
    COUNTS=$(git rev-list --left-right --count "HEAD...$UPSTREAM" 2>/dev/null || true)
    if [ -n "$COUNTS" ]; then
      # shellcheck disable=SC2086
      set -- $COUNTS
      echo "- Upstream: $UPSTREAM (ahead $1, behind $2; as of the last fetch)"
    else
      echo "- Upstream: $UPSTREAM"
    fi
  else
    echo "- Upstream: none"
  fi

  for marker in MERGE_HEAD REBASE_HEAD CHERRY_PICK_HEAD BISECT_LOG; do
    if [ -e "$(git rev-parse --git-path "$marker")" ]; then
      echo "- In progress: $marker (a merge, rebase, cherry-pick or bisect is unfinished)"
    fi
  done
  if [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]; then
    echo "- In progress: rebase"
  fi

  echo
  echo "### Uncommitted files"
  echo
  git status --porcelain=v1 --untracked-files=all 2>/dev/null | head -60 | block
  TOTAL=$(git status --porcelain=v1 --untracked-files=all 2>/dev/null | wc -l | tr -d ' ')
  [ "$TOTAL" -gt 60 ] && echo "(+$((TOTAL - 60)) more)"

  echo
  echo "### Diff stat (staged and unstaged, against HEAD)"
  echo
  if git rev-parse --verify --quiet HEAD >/dev/null; then
    git diff HEAD --stat=100 2>/dev/null | tail -25 | block
  else
    echo "(no commits yet)"
  fi

  echo
  echo "### Recent commits"
  echo
  git log -5 --format='%h %ad %s' --date=short 2>/dev/null | block

  STASHES=$(git stash list 2>/dev/null | head -5)
  if [ -n "$STASHES" ]; then
    echo
    echo "### Stashes"
    echo
    echo "$STASHES" | block
  fi
fi

if have lsof; then
  # Local listeners from dev runtimes owned by this user (dev servers, watchers,
  # databases). Only the ones started inside this project are listed, with their
  # command line so the next session knows how to restart them; the rest are
  # just counted. System apps are skipped.
  HERE=$(pwd)
  PIDS=$(lsof -nP -a -u "$(id -u)" -iTCP -sTCP:LISTEN 2>/dev/null \
    | awk 'NR > 1 && tolower($1) ~ /^(node|bun|deno|python|ruby|java|go|php|perl|dotnet|beam|erl|elixir|postgres|mysqld|mariadbd|redis|mongod|com\.docke|docker|vite|esbuild|uvicorn|gunicorn|rails|puma|cargo|caddy|nginx|httpd|expo|metro|ngrok|wrangler|supabase)/ { print $2 }' \
    | sort -un)
  MINE="" OTHERS=0
  for pid in $PIDS; do
    cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)
    case "$cwd" in
      "$HERE"|"$HERE"/*)
        ports=$(lsof -nP -a -p "$pid" -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR > 1 { print $9 }' | sort -u | tr '\n' ' ')
        cmd=$(ps -o command= -p "$pid" 2>/dev/null | cut -c1-200)
        dir=${cwd#"$HERE"}
        dir=${dir#/}
        MINE="$MINE- pid $pid on ${ports% }: \`$cmd\` in ./${dir}
"
        ;;
      *) OTHERS=$((OTHERS + 1)) ;;
    esac
  done
  if [ -n "$MINE" ] || [ "$OTHERS" -gt 0 ]; then
    echo
    echo "### Dev processes listening on ports"
    echo
    [ -n "$MINE" ] && printf '%s' "$MINE"
    [ -z "$MINE" ] && echo "None started from this project."
    [ "$OTHERS" -gt 0 ] && echo "($OTHERS more from other directories, not listed)"
  fi
fi

exit 0
