# Sources and what this skill took from each

Surveyed in October 2026. The tools are listed so that a future revision can
re-check them; the evidence explains why the skill prunes and verifies
instead of generating.

## Existing skills and tools

| Tool | What it does | Taken | Left out |
|---|---|---|---|
| Anthropic `claude-md-management` (claude-md-improver, /revise-claude-md) — github.com/anthropics/claude-plugins-official | Scores CLAUDE.md files, proposes small diffs with a reason each, applies on approval | Checks for failing commands, deleted files, outdated versions, generic advice, duplicates across files | CLAUDE.md-only; append-only revisions; rewards architecture overviews |
| Claude Code `/init`, `/doctor prompt-audit` — code.claude.com/docs/en/memory | Creates CLAUDE.md, imports other tools' rules; audit flags stale instructions | Import existing Cursor/Copilot rules instead of ignoring them | One-shot generation |
| Codex `/init` — github.com/openai/codex (prompt_for_init_command.md) | "Repository Guidelines" in 200-400 words | Word budget; commit/PR rules from git history | Never updates an existing file; adds a structure overview |
| narumiruna `write-agents-md` — github.com/narumiruna/agent-skills | Finds every applicable AGENTS.md, verifies commands and paths against CI, removes stale/duplicate/guessed lines | Verify against CI; prune; narrowest scope; repo-proven rules only | `[UNREVIEWED]` markers in the file |
| Sentry `agents-md` — github.com/getsentry/skills | Short AGENTS.md, CLAUDE.md as symlink, command tables, references table | Length budget, single source, nested files never repeat the root | Hard 60-line cap |
| gupsammy/claudest `update-readme` — github.com/gupsammy/claudest | Audit + codebase scan + git log since README's last commit, fixed edit order | Diff-driven update, edit order, smallest edit, keep style, report N→M lines | Changelog rewrite; adds sections for coverage; runs nothing |
| athola `update-readme` — github.com/athola/claude-night-market | README as an index; detail moves to docs/ | "Index, not manual"; move don't delete; hub and spoke | Web exemplar research; heavy gates |
| ZardLi1115 `readme-skill` | Fact ledger (verified / confirmed / uncertain / missing) | Fact list before writing; never invent | Draft-in-chat friction; long interview |
| tommy0103 `better-readme-skill` | Art of README audit | Check `git status` first; grep tests/CI for pinned README strings; one home per fact; keep what the author likes | Rewrite-oriented |
| github/awesome-copilot `create-readme`, `update-docs-on-code-change` | Short README prompt; triggers for doc updates | Trigger list; no LICENSE/CONTRIBUTING prose in README | Verifies nothing |
| borghei `doc-drift-detector`, bjornmelin `docs-align` | Scripts that find drift and build a gap map | Deterministic drift checks before editing | Detection only |
| readme-ai (eli64s) | LLM README generator CLI | Facts from manifests | Generate-only, badge/emoji boilerplate, doesn't strip sensitive data |
| rulesync, Ruler, agentsync | Generate every agent's rule file from one source | Respect the generator: edit its source | (not verified in depth) |

Gap the skill fills: none of the above both updates from the diff since the
doc last changed *and* checks commands, links, env vars and agent-file links
against the repo. `scripts/docs_audit.py` does both.

## Evidence on agent files

- **ETH Zurich, "Evaluating AGENTS.md"** (arXiv 2602.11988, ICLR 2026;
  numbers from v3). LLM-generated files: success −0.5% to −2%, cost +20-23%.
  Developer-written: +2.4% success, about 7 points better than generated.
  Generated files mostly duplicate the README (with docs removed they helped
  2.7%). Overviews did not speed up finding files. Agents use tools they are
  told about far more often (uv 1.6×/task when mentioned vs <0.01× when not).
  https://arxiv.org/html/2602.11988v3
- **Lulla et al.** (arXiv 2601.20404): human-written AGENTS.md associated with
  28.6% lower median runtime and 16.6% fewer output tokens (association,
  124 PRs).
- **McMillan** (arXiv 2605.10039): in 1,650 Claude Code sessions, size,
  position and layout had no detectable effect on adherence; adherence fell
  as a session went on.
- **Shepard & Albrecht** (arXiv 2606.20512): guidance tuned with probes beat
  a static knowledge base and no guidance; how the file is made decides
  whether it helps.
- **Vercel** (vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals):
  a compressed 8 KB docs index in AGENTS.md scored 100% vs 53-79% for a skill,
  because skills were often not invoked. Their own Next.js eval.
- **IFScale** (arXiv 2507.11538): instruction-following accuracy drops as
  instruction count grows, with a bias toward earlier instructions.
- HumanLayer, "Writing a good CLAUDE.md": https://www.humanlayer.dev/blog/writing-a-good-claude-md
- GitHub, lessons from 2,500 repos (about Copilot custom agents, carries over
  loosely): https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/

## Standards and docs

- AGENTS.md: https://agents.md/
- Claude Code memory: https://code.claude.com/docs/en/memory ; best practices: https://code.claude.com/docs/en/best-practices
- Codex AGENTS.md: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Copilot instructions: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- Gemini CLI context files: https://geminicli.com/docs/cli/gemini-md/
- Cursor rules: https://cursor.com/docs/context/rules
- standard-readme: https://github.com/RichardLitt/standard-readme/blob/main/spec.md
- Make a README: https://www.makeareadme.com/
- GitHub READMEs: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
- Community health files: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file
- Keep a Changelog: https://keepachangelog.com/en/1.1.0/
- Open Source Guides: https://opensource.guide/starting-a-project/

## Not verified

The exact Claude Code `/init` prompt; rulesync/Ruler/agentsync details;
whether every Copilot surface reads AGENTS.md; claims of a 150-line
"diminishing returns" threshold.
