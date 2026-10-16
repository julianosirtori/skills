# AGENTS.md: template, interop and maintenance

Sources: agents.md, Claude Code memory docs and best practices, Codex
AGENTS.md docs, Copilot and Cursor docs, Sentry's agents-md skill,
narumiruna's write-agents-md skill, the ETH Zurich study. URLs in `sources.md`.

## What earns a line

Ask of every line: *would an agent make a mistake without it?*

**Include**

- Exact commands with flags: install, dev, build, test, lint, typecheck, and
  the fast forms (one file, one test). Taken from the manifest or CI.
- The package manager and non-default tools ("pnpm, never npm", "uv run").
- How to verify a change before calling it done, in order.
- Conventions that differ from the language/framework default.
- Generated files and folders never edited by hand, and how to regenerate them.
- Gotchas: env quirks, required services, flaky tests, ports, platform issues.
- Boundaries: always / ask first / never.
- Commit and PR rules when the repo has them.
- Pointers to deeper docs, with when to read them.

**Exclude**

- Directory trees and per-file descriptions (agents list files themselves;
  overviews did not help them find files faster in the ETH study).
- Anything in the README already, generic advice ("write clean code",
  "add tests"), language basics.
- Rules a linter or formatter enforces (let the tool or a hook do it).
- API docs, tutorials, long code samples (they go stale; point to
  `path:line` or a doc instead).
- Task history, one-off fixes, the changelog, lists of installed skills.
- Secrets or real env values.

Agents follow instructions closely: mentioning a tool makes them use it far
more. So every extra "also run X" costs time on every task. Mention only what
should actually happen.

## Template

Drop every section the repo gives no verified facts for.

```markdown
# AGENTS.md

<One or two lines: what this repo is, only if the README doesn't open with it.>

## Commands

| Task | Command |
|---|---|
| Install | `pnpm install` |
| Dev | `pnpm dev` |
| Test (one file) | `pnpm vitest run path/to/file.test.ts` |
| Test (all) | `pnpm test` |
| Lint + types | `pnpm lint && pnpm typecheck` |

Before finishing: <the checks, in order>.

## Conventions

- <Only what differs from defaults. One rule per bullet.>

## Gotchas

- <Non-obvious things that break.>

## Boundaries

- Always: <...>
- Ask first: <schema migrations, new dependencies, CI changes...>
- Never: <commit secrets, edit src/gen/, push to main...>

## Pull requests

- <Title format, required checks, branch rules.>

## More context

- <docs/architecture.md: read before changing the data layer.>
```

## Length

| Source | Guidance |
|---|---|
| Claude Code docs | CLAUDE.md under 200 lines |
| Sentry agents-md skill | under 60, never over 100 |
| Codex `/init` | 200-400 words; loading stops at 32 KiB |
| Cursor | each rule under 500 lines |

Default target here: under ~100 lines at the root, 150 soft ceiling, 200 hard.
Nested files shorter than the root and never repeating it.

## Nesting (monorepos)

- One root AGENTS.md for repo-wide rules. Add `packages/x/AGENTS.md` only when
  that subtree has different commands or rules.
- The nearest AGENTS.md to the edited file wins (agents.md, Cursor, Copilot).
  Codex concatenates root → current directory, later files overriding.
  Claude Code loads subdirectory files when it works in that directory.
- Never copy root content into nested files; put only the delta there.

## Interop by tool

| Tool | Reads | How to keep it on AGENTS.md |
|---|---|---|
| Codex, Cursor, Copilot (agent), Jules, Aider, Zed, Warp, Devin, Windsurf, Amp... | AGENTS.md natively | nothing |
| Claude Code | CLAUDE.md; AGENTS.md only when no CLAUDE.md / CLAUDE.local.md is present | CLAUDE.md with `@AGENTS.md` as its first line, Claude-only notes after. Or a symlink (fails on some Windows checkouts, and edits go through to AGENTS.md) |
| Gemini CLI | GEMINI.md by default | `context.fileName: ["AGENTS.md", "GEMINI.md"]` in `.gemini/settings.json`, or a GEMINI.md with `@AGENTS.md` |
| Copilot | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, AGENTS.md | keep the Copilot files for Copilot-only, path-scoped rules |
| Cursor | `.cursor/rules/*.mdc`, AGENTS.md | rules files only for glob-scoped rules |

Anti-patterns:

- AGENTS.md and CLAUDE.md as two full copies (they drift; agents get both).
- A CLAUDE.md that says "read AGENTS.md" in prose instead of importing it.
- Adding a CLAUDE.local.md and silently turning AGENTS.md off for Claude.
- Editing the outputs of a sync generator (rulesync, Ruler, agentsync)
  instead of its source.

## Updating an existing file

1. Map each line to the inclusion test and to the drift report.
2. Fix lines the repo contradicts (commands, paths, tools, versions).
3. Remove: stale, duplicated (with README or another agent file),
   conflicting, generic, linter-enforced, history.
4. Add only what the diff since the last edit, the CI, the config, or the
   user proves. One rule per bullet, at the narrowest scope.
5. Over budget? Split by directory, or move detail to docs/ with a pointer
   that says when to read it.
6. Check the CLAUDE.md / GEMINI.md / Copilot links still hold.

When the user corrects the same agent mistake twice, that correction is the
best candidate for a new line.
