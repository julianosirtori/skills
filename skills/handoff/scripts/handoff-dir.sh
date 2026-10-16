#!/usr/bin/env bash
# handoff-dir.sh: decide where handoffs live, or list the ones that exist.
#
# A coding project keeps its handoffs inside the project; anything else goes to
# the user's home. The folder follows the agent: .claude/ for Claude Code,
# .agents/ for every other agent.
#
#   project scope: <project-root>/.claude/handoffs/  or  <project-root>/.agents/handoffs/
#   user scope:    ~/.claude/handoffs/               or  ~/.agents/handoffs/
#
# A coding project is a git work tree (its top level is the root), or the nearest
# folder below $HOME that has a project marker (package.json, pyproject.toml,
# go.mod, Cargo.toml, AGENTS.md, CLAUDE.md, .claude/, .agents/...). $HOME itself
# is never a project.
#
# Usage:
#   bash handoff-dir.sh [dir] [claude|agents]   print scope, root, dir and git (yes/no)
#   bash handoff-dir.sh --list [dir]            list handoffs, newest first, from the
#                                               project and user folders (and the legacy
#                                               <root>/.handoffs/), archive/ excluded
# Read-only: it never creates or changes anything.

set -u

MARKERS="package.json pyproject.toml setup.py requirements.txt go.mod Cargo.toml Gemfile
composer.json pom.xml build.gradle build.gradle.kts deno.json mix.exs pubspec.yaml
Package.swift CMakeLists.txt Makefile AGENTS.md CLAUDE.md .claude .agents"

LIST=0
if [ "${1:-}" = "--list" ]; then
  LIST=1
  shift
fi

START="${1:-.}"
AGENT="${2:-agents}"
cd "$START" 2>/dev/null || { echo "error: cannot cd to $START" >&2; exit 1; }
HERE=$(pwd -P)
HOME_DIR=$(cd "$HOME" 2>/dev/null && pwd -P || echo "$HOME")

case "$AGENT" in
  claude) FOLDER=.claude ;;
  agents) FOLDER=.agents ;;
  *) echo "error: agent must be claude or agents, got $AGENT" >&2; exit 1 ;;
esac

ROOT="" GIT=no
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  top=$(git rev-parse --show-toplevel)
  top=$(cd "$top" && pwd -P)
  if [ "$top" != "$HOME_DIR" ]; then
    ROOT=$top
    GIT=yes
  fi
fi

if [ -z "$ROOT" ]; then
  d=$HERE
  while [ "$d" != "/" ] && [ "$d" != "$HOME_DIR" ]; do
    for m in $MARKERS; do
      if [ -e "$d/$m" ]; then
        ROOT=$d
        break 2
      fi
    done
    d=$(dirname "$d")
  done
fi

if [ "$LIST" -eq 1 ]; then
  dirs=()
  [ -n "$ROOT" ] && dirs=("$ROOT/.claude/handoffs" "$ROOT/.agents/handoffs" "$ROOT/.handoffs")
  dirs+=("$HOME_DIR/.claude/handoffs" "$HOME_DIR/.agents/handoffs")
  # Names start with YYYY-MM-DD-HHMM, so sorting by file name is sorting by age.
  found=$(for dir in "${dirs[@]}"; do
    [ -d "$dir" ] && find "$dir" -maxdepth 1 -type f -name '*.md' 2>/dev/null
  done | awk -F/ '{ print $NF "\t" $0 }' | sort -r | cut -f2-)
  if [ -z "$found" ]; then
    echo "(no handoffs)"
  else
    echo "$found"
  fi
  exit 0
fi

if [ -n "$ROOT" ]; then
  echo "scope=project"
  echo "root=$ROOT"
  echo "dir=$ROOT/$FOLDER/handoffs"
else
  echo "scope=user"
  echo "root=$HERE"
  echo "dir=$HOME_DIR/$FOLDER/handoffs"
fi
echo "git=$GIT"
