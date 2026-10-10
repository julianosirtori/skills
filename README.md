# skills

Agent Skills by [Juliano Sirtori](https://github.com/julianosirtori).

Each skill is a folder with a `SKILL.md` that follows the open
[Agent Skills specification](https://agentskills.io/specification), so the same
skill works in Claude Code, OpenCode, Codex, Cursor, Gemini CLI, GitHub Copilot and
any other agent that reads `SKILL.md`. The repo is also a
[Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces).

## Skills

| Skill | What it does |
|---|---|
| [mac-cleanup](skills/mac-cleanup) | Analyzes and safely frees disk space on macOS. Measures what uses storage, cleans only caches that rebuild themselves, finds leftovers of uninstalled apps, and walks you through the removals that need your judgment (WhatsApp, Photos, iCloud Drive, Homebrew, Xcode, Docker...). Never deletes your data without asking, and sends anything that is not a cache to the Trash. |
| [squad](skills/squad) | Runs a feature, bug fix or refactor through a fast squad. The session model (best on Opus) orchestrates: it writes one plan with numbered acceptance criteria, the UI/UX (flows, every screen state, copy, accessibility), the shared contracts and a task board where each task owns its files. It then fans the implementation and the tests out to parallel **Haiku workers**, as many as the plan has independent tasks (up to 10 per wave), with tests written by a different worker than the code. It integrates each wave, runs the checks once and reviews the diff, while **Haiku QA** agents exercise the real app at medium and large size and an independent **Reviewer** joins for large or risky changes. Findings go back as focused fix tasks, capped at two rounds. Everything is written to `.squad/<feature>/`, and the skill stops to ask you only when a decision is yours. |
| [product-naming](skills/product-naming) | Finds a brandable name for a product or company that you can actually own. Generates hundreds of candidates in batches by naming strategy and bulk-checks domains straight from the registries (RDAP/whois for .com, .com.br, .ai, .io, .app and more). Every extension is self-tested, so a broken check never reports a taken domain as free. It filters names by meaning, sound and spelling in every market language and scores fit and marketing potential. It then vets the finalists: who owns a taken .com and whether it is for sale, Google autocomplete and search conflicts, a USPTO/INPI/WIPO trademark pre-screen, and social handles. |
| [handoff](skills/handoff) | Ends a session and continues in a fresh one without losing context. `/handoff <next focus>` checks the real state (git snapshot, diff, checks) and writes a self-contained handoff to `.handoffs/` (kept out of git): goal, state, next steps, decisions and why, dead ends, your preferences, files to read first, running processes and verify commands. It then copies a short start prompt to the clipboard for you to paste after `/clear`. `/handoff resume` loads the newest handoff, checks it against the current code, reports what drifted and picks up the next step. |

## Install

### Any agent: `npx skills`

```bash
npx skills add julianosirtori/skills                       # pick skills and agents interactively
npx skills add julianosirtori/skills --skill mac-cleanup -g  # one skill, for your user (all projects)
```

[`skills`](https://github.com/vercel-labs/skills) detects the agents you have
installed and links the skill into each one's folder.

### Claude Code: plugin marketplace

```text
/plugin marketplace add julianosirtori/skills
/plugin install mac-cleanup@julianosirtori-skills
```

Plugin skills are namespaced, so invoke it as `/mac-cleanup:mac-cleanup`, or just
describe the problem ("my Mac is out of space") and Claude picks it up.

### Manually

Clone the repo and link (or copy) the skill folder into your agent's skills
directory:

```bash
git clone https://github.com/julianosirtori/skills.git ~/Developer/skills
ln -s ~/Developer/skills/skills/mac-cleanup ~/.claude/skills/mac-cleanup
```

`squad` also ships a Haiku worker agent. The plugin install registers it on its
own; with a manual install, link it into Claude Code's agents folder too (without
it, squad falls back to general-purpose Haiku subagents):

```bash
ln -s ~/Developer/skills/skills/squad/agents/squad-worker.md ~/.claude/agents/squad-worker.md
```

| Agent | User-level skills folder | Project-level |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` (also reads `~/.claude/skills/` and `~/.agents/skills/`) | `.opencode/skills/` |
| Codex | `~/.agents/skills/` | `.agents/skills/` |
| Cursor | `~/.cursor/skills/` or `~/.agents/skills/` | `.cursor/skills/` |
| Gemini CLI | `~/.gemini/skills/` or `~/.agents/skills/` | `.gemini/skills/` |
| GitHub Copilot | `~/.copilot/skills/` or `~/.agents/skills/` | `.github/skills/` |

## Repository layout

```text
.
├── .claude-plugin/
│   └── marketplace.json   # Claude Code marketplace: one plugin per skill
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md       # frontmatter (name, description, license...) + instructions
│       ├── scripts/       # executables the skill runs
│       └── references/    # docs the agent reads only when needed
├── scripts/
│   └── validate.py        # spec + manifest checks (runs in CI)
└── LICENSE
```

## Adding a skill

1. Create `skills/<name>/SKILL.md`. The `name` must match the folder: lowercase
   letters, digits and single hyphens, up to 64 characters. The `description`
   (up to 1024 characters) says what the skill does and when to use it. Use only
   the spec's frontmatter fields: `name`, `description`, `license`,
   `compatibility`, `metadata`, `allowed-tools`.
2. Keep `SKILL.md` under 500 lines; move details to `references/` and repeatable
   work to `scripts/`.
3. Add a plugin entry for it in `.claude-plugin/marketplace.json`.
4. Run the checks:
   ```bash
   python3 scripts/validate.py
   claude plugin validate . --strict   # if Claude Code is installed
   ```

## License

[MIT](LICENSE)
