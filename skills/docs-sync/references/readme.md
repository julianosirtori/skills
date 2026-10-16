# README.md: sections and writing rules

Sources: standard-readme spec, makeareadme.com, GitHub Docs, opensource.guide,
Art of README, keepachangelog. URLs in `sources.md`.

## The funnel

Order the README from broad to deep so a reader can tell in seconds whether
it is for them, and stop reading once they have what they need:

1. Title, one-line description, (badges)
2. What it is / why (2-4 sentences, a screenshot or GIF for visual projects)
3. Quick start: the shortest path from zero to something working
4. Usage: real invocations with their output
5. Configuration, API, deeper topics (or links to them)
6. Pointers: docs, contributing, support, license

## Sections

**Always**

| Section | Rule |
|---|---|
| Title | Matches the repo/package name. |
| One-line description | Under ~120 chars, same wording as the manifest `description` and the GitHub "About" when they exist. Change them together. |
| Install / prerequisites | A code block with the lockfile's package manager. Runtime versions from `.nvmrc`, `engines`, `requires-python`, `go.mod`; never a version from memory. |
| Quick start / usage | Smallest runnable example plus what it prints or shows. It must run. |
| License | One line: SPDX name and a link to LICENSE. Last section. Flag a non-permissive license (AGPL, BUSL...) near the top too. |

**When the project needs them**

| Section | When |
|---|---|
| Badges | Only ones backed by a real source (CI status, published version, license). No heading, ≤5, on one line. Keep the existing badge style. |
| Configuration | A table: name, required, default, description. Env vars by name, never values. Mirror `.env.example`. |
| Table of contents | Over ~100 lines. GitHub also renders an outline, so short READMEs skip it. |
| Screenshots / demo | For UIs and CLIs with rich output. Never the only place a fact appears (alt text). |
| Limitations / status | When users would otherwise hit them (beta, unsupported platforms). |
| Contributing / support | One line linking CONTRIBUTING.md / SUPPORT.md / issues. |

## By project type

- **Library**: description → usage/API sample → install → API reference (or
  link) → compatibility. Readers judge the API before installing.
- **CLI**: install → usage with real commands and output → commands/flags
  table (from `--help`, not memory) → config.
- **App (web/mobile/desktop)**: what it does + screenshot → run locally
  (prereqs, env, dev command) → test → deploy (or link) → config.
- **Internal service**: what it does, who owns it, how to run locally, env
  vars, links to runbooks, dashboards and ADRs.
- **Monorepo root**: what the repo is → a table of packages/apps with one line
  and a link each → workspace-wide setup and commands. Package detail lives in
  each package's README. Packages published to npm/PyPI ship their own README
  (npm only refreshes it on publish; PyPI uses the pyproject `readme` field).

## Doesn't belong in the README

| Content | Goes to |
|---|---|
| Release history | CHANGELOG.md (written for humans, not a git log dump) |
| Contribution workflow, code style for contributors | CONTRIBUTING.md |
| Vulnerability reporting | SECURITY.md |
| Agent commands, conventions, boundaries | AGENTS.md |
| Architecture, design rationale | docs/ or ARCHITECTURE.md, ADRs |
| Long API reference, tutorials | docs/ (link from the README) |
| Maintainer runbooks (release, on-call) | docs/ or the internal wiki |

## Writing rules

- One home per fact; link instead of repeating.
- Concrete over adjectives: "parses 1 GB CSV in 3 s on an M2" only when a
  benchmark in the repo says so, otherwise no number at all.
- Relative links for files in the repo; they work on GitHub and in clones.
- Language tag on every code fence; commands copy-pasteable (no `$` prompts
  mixed with output unless the output is shown separately).
- Keep the existing voice, emoji level and heading style.
- Images need alt text.
- GitHub truncates READMEs over 500 KiB; long content belongs in docs/.

## What usually goes stale

Map a change to the section it breaks:

| Changed | Check in the README |
|---|---|
| `package.json` scripts, Makefile, justfile | install/dev/test commands |
| lockfile switched (npm → pnpm) | every install/run command |
| `.env.example` | configuration table, setup steps |
| `.nvmrc`, `engines`, `requires-python` | prerequisites |
| CLI flags, entry points | usage examples, flags table |
| routes, public exports | API section, examples |
| Dockerfile, compose | docker run instructions |
| renamed or moved files | relative links, paths in prose |
| new user-facing feature | features/usage (one line + example) |
| removed feature | delete its section; mention the replacement |
