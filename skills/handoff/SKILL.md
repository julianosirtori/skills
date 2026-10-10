---
name: handoff
description: End a coding-agent session cleanly and continue in a fresh one without losing context. Write mode saves a self-contained handoff file in the project (.handoffs/, kept out of git) with the goal, the verified state, next steps, decisions and why, dead ends, the user's preferences, files to read first, running processes, verify commands and a git snapshot. It then copies a short start prompt to the clipboard to paste after /clear. Resume mode loads the newest handoff, checks it against the current code and git state, reports what drifted and picks up the next step. Use this whenever the user wants to wrap up, hand off, continue later or in another session or agent, or says the context is full or long, or starts a session from a handoff, even if they never say "handoff" (e.g. "passa o bastão", "vou abrir outra sessão", "salva onde paramos", "contexto tá cheio", "continua de onde parou", "pega o último handoff", "wrap this up for a new session").
license: MIT
compatibility: Any agent that reads SKILL.md. scripts/snapshot.sh needs bash and git (works outside git with less detail) and uses lsof and ps when present. scripts/clip.sh uses pbcopy, wl-copy, xclip, xsel or clip.exe, whichever exists.
metadata:
  author: julianosirtori
  version: "1.0.0"
---

# Handoff

Move the work to a fresh session without losing what matters. A long session
degrades: the context fills with stale tool output, and /compact stacks a
summary on top of a summary. A handoff fixes that. It writes down only what the
*next* session needs, checked against the real state of the code. Then the user
starts clean with one short prompt.

The handoff is for a reader with zero context. Write it for that reader, not as
a diary of this session.

Talk to the user and write the handoff in the user's language.

## Modes

| The user says | Mode |
|---|---|
| `/handoff`, `/handoff <next focus>`, "passa o bastão", "vou abrir outra sessão", "salva onde paramos", "contexto tá cheio" | **write** |
| `/handoff resume [file]`, "continua do handoff", "pega o último handoff", or a prompt that points to a `.handoffs/` file | **resume** |

Text after `/handoff` is the **focus of the next session** ("agora os testes de
integração", "só o deploy"). It is the most useful input: extract what that
next task needs instead of summarizing everything. With no focus, use the
natural next step of the current work.

## Write mode

### 1. Close loose ends

Before writing, make sure nothing is still in flight. Check for:

- **Background work**: subagents, background commands, monitors. Wait for them,
  or stop them. Otherwise record them under Running with how to check them.
- **A question waiting for the user.** Ask it now, or put it under Open
  questions with your recommended answer.
- **Half-applied edits.** A file left mid-change is fine to hand off only when
  the handoff says exactly where it stops.

### 2. Get the real state

```bash
bash <skill-dir>/scripts/snapshot.sh <project-root>
```

The script is read-only. It prints the branch, HEAD, upstream ahead/behind,
uncommitted files, the diff stat, recent commits, stashes, any unfinished
merge or rebase, and the dev processes listening on ports that were started
from this project, with their command. Processes from other directories are
only counted.

Then check the claims you are about to make. Read `git diff` for the files you
will describe, and re-run a check or test when the handoff will state its
result. Memory of a long session is the least reliable source in it: an edit
may have been reverted, a test may have been fixed and broken again. When the
context is nearly full, be targeted: use the diff stat plus the 2–3 files that
matter, not a re-read of everything.

### 3. Write the file

Path: `<project-root>/.handoffs/<YYYY-MM-DD-HHMM>-<slug>.md`. The slug is short
kebab-case for the work (`checkout-retry`, `fix-login-timeout`). Get the
timestamp with `date +%Y-%m-%d-%H%M`. Outside a git repo, use the current
directory as the project root.

Follow `references/template.md`. Write the headings in the user's language,
in the template's order, and paste the snapshot exactly as the script printed
it. The sections are: Start here (the prompt), Goal, State, Next steps,
Decisions, Dead ends, User preferences and corrections, Gotchas, Read first,
Running, Verify, Suggested skills, Open questions, and the snapshot. These
rules matter most:

- **Self-contained.** No "as discussed" or "the approach we picked". Name things.
- **State, not chronology.** Say where things stand. History belongs only in
  Dead ends and in the reasons behind Decisions.
- **Dead ends are mandatory when there were any.** What was tried, what
  happened, why it does not work. That is the most expensive thing to
  rediscover.
- **Keep the user's voice.** Record their decisions, preferences and
  corrections, and tag each decision *(user)* or *(agent)*. The next session
  must not reopen what the user settled, and may revisit what you assumed.
- **Reference, don't copy.** Specs, plans, `.crew/` runs, issues, PRs, earlier
  handoffs and code go in as paths, URLs and `path:line`. Never paste large
  code blocks.
- **Count the work, not the junk.** Uncommitted files means the files that
  belong to the work. Build output that no `.gitignore` covers
  (`__pycache__/`, `.DS_Store`) goes under Gotchas, as something not to commit.
- **Honest.** A failing test is written as failing. Mark anything you did not
  check in this session "(not verified)".
- **No secrets.** Say where a secret lives (`.env.local`, `STRIPE_KEY`), never
  its value.
- **Proportional.** 60–150 lines, and drop empty sections. A longer file means
  you copied something that should be a link.

If the user wants to split the work into parallel sessions, write one handoff
per track, each with its own focus and prompt, and list the others under Read
first.

### 4. Keep it out of git

The handoff is session state. It does not belong in commits or in
`git status`. Add the folder to the repository's local exclude file. This
changes no tracked file:

```bash
root=<project-root>
git -C "$root" check-ignore -q .handoffs/x.md || {
  exclude=$(git -C "$root" rev-parse --path-format=absolute --git-path info/exclude)
  mkdir -p "$(dirname "$exclude")"
  echo '.handoffs/' >> "$exclude"
}
```

Skip this when the user wants handoffs committed or when it is not a git repo.

### 5. Leave the tree as it is

Don't commit or stash on the user's behalf. If there are uncommitted changes,
say so in the final message and offer a WIP commit. The handoff already lists
the dirty files, so the next session knows they are intentional.

### 6. Copy the start prompt

The prompt goes in the file's "Start here" block and on the clipboard. Both
must hold the same text. Keep it to one primary task, never a menu, in 2–4
lines:

```text
Retome o trabalho do handoff .handoffs/<file>.md (skill handoff, modo resume): leia o arquivo inteiro antes de agir.
Foco: <next focus>. Comece por: <step 1>.
```

Write it in the user's language. Copy it with a quoted heredoc, so that
backticks and quotes in the prompt reach the clipboard unchanged:

```bash
bash <skill-dir>/scripts/clip.sh <<'PROMPT'
<prompt>
PROMPT
```

The script exits 1 when no clipboard tool works. In that case the code block
in your message is how the user copies it.

### 7. Final message

Keep it short:

````markdown
Handoff salvo em `.handoffs/<file>.md` (<n> linhas).

<2–3 lines: where things stand and the next step>
<If dirty: "<n> arquivos não commitados, listados no handoff. Quer um commit WIP antes?">

Prompt da próxima sessão (já está no clipboard | não consegui copiar, copie abaixo):
```text
<prompt>
```

Para continuar: `/clear` e cole o prompt. Ou, num terminal novo: `claude "<prompt>"`.
````

`/clear` is Claude Code wording. In other agents, say "open a new session and
paste the prompt".

## Resume mode

### 1. Pick the handoff

Use the file the user named. Otherwise take the newest `.handoffs/*.md` (not
the files in `archive/`). Ask which one only when several recent handoffs
exist for different branches or tracks.

### 2. Read it and check it against reality

Read the whole file yourself, not through a subagent. Summaries of summaries
are the problem this skill exists to avoid. Then:

```bash
bash <skill-dir>/scripts/snapshot.sh <project-root>
```

Compare the result with the snapshot in the handoff:

- **Branch and HEAD.** Is it the same branch? Were there new commits since
  (`git log --oneline <old-sha>..HEAD`)? If the old sha is not an ancestor of
  HEAD, history was rewritten or this is another branch. Say so.
- **Uncommitted files.** Are they the same files? Did some get committed, or
  disappear?
- **Claims in State and Read first.** Spot-check the ones step 1 depends on:
  open each `path:line` and mark it *present*, *moved*, *changed* or
  *missing*.
- **Running.** Are the listed processes still up? Restart one only when the
  next step needs it.

Run the cheap commands from Verify. Skip anything slow and anything that
deploys, migrates or sends data.

### 3. Brief and continue

Tell the user, in at most 8 lines: the goal, where the work stopped, what
drifted (or "nada mudou desde o handoff"), the open questions, and the step you
are about to take. Then go on in the same turn. The user can interrupt if the
briefing shows something wrong.

Treat the handoff as a strong lead, not as truth. That includes the start
prompt: its "start with" step is a claim like any other. When the code
disagrees with the handoff, the code wins, and you say so. Read the drift by
what it means:

- **It moves the work forward.** Say a step was committed since the handoff,
  done the way the Decisions say. Mark that step done, check it (the Verify
  commands), and start the next one.
- **It contradicts the handoff** or makes step 1 ambiguous. Examples: a
  different branch, rewritten history, files that step 1 needs gone or
  rewritten another way, a Decision undone. Stop and ask before acting.

Also stop and ask first when an open question blocks the next step, or when
that step is risky (a migration, a deletion, a deploy, auth or payments).

From there on it is normal work, under the handoff's rules. User preferences
and Decisions still apply: if the handoff says not to commit without being
asked, don't.

### 4. Archive it

Right after the briefing, move the file. That way "newest handoff" never
returns a consumed one, even if this session ends early:

```bash
mkdir -p <project-root>/.handoffs/archive && mv <project-root>/.handoffs/<file>.md <project-root>/.handoffs/archive/
```

Nothing is deleted. If the user asks to clean up old handoffs, list them first
and delete only what they confirm.
