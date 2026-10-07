# Handoff template

Copy the skeleton below and fill it in, in the user's language (headings too,
keeping this order). The
`<!-- ... -->` comments explain each section. Delete them in the final file, and
drop any section that would only say "none". The reader is an agent that has
never seen this conversation. Everything it needs is either in the file or
behind a path the file gives it.

Aim for 60–150 lines. A small task can take 40. When the file gets longer than
that, you are copying content that already lives somewhere else (a spec, a plan,
the diff). Link to it instead.

````markdown
# Handoff: <short title of the work>

- Created: <YYYY-MM-DD HH:MM> · Branch: <branch> · HEAD: <short sha> (<clean | N uncommitted files>)
- Next session: <the focus, in one line: the user's argument, or the obvious next step>

## Start here

<!-- The prompt the user pastes into the new session, word for word; it is also
     copied to the clipboard. One primary task, never a menu of options. Keep it
     to 2–4 lines: everything else is below. -->

```text
Retome o trabalho do handoff .handoffs/<file>.md (skill handoff, modo resume): leia o arquivo inteiro antes de agir.
Foco: <next focus>. Comece por: <step 1>.
```

## Goal

<!-- What the user wants and why, in 2–5 lines. Quote the original request word
     for word when its wording matters (scope, constraints, names). Include the
     definition of done if one was agreed. -->

## State

<!-- Where things actually stand, checked against the diff and the checks, not
     remembered. Use the three groups below. A failing test is written as
     failing, with the command that shows it. Name files as path:line. -->

- **Done:** ...
- **In progress:** ... (what exactly is half-written, where it stops)
- **Not started:** ...

## Next steps

<!-- Ordered. Step 1 must be concrete enough to start without asking anything:
     a file, a function, a command. Mark steps that need the user. -->

1. ...
2. ...

Done when: <observable result: a test passes, a screen shows X, a command returns Y>

## Decisions

<!-- Choices that are settled, each with the reason, so the next session does not
     reopen them. Tag who made it: (user) when the user decided or confirmed it,
     (agent) when it is your call or your inference and can be revisited.
     Include the main rejected alternative when someone would naturally suggest it. -->

- <decision>: <why>. (user)
- <decision>: <why>; rejected <alternative> because <reason>. (agent)

## Dead ends

<!-- What was tried and did not work, and why. This is the most expensive thing
     to rediscover. Be specific: the error, the symptom, the number. "X did not
     work" without a reason is useless. -->

- Tried <approach>: <what happened> → <why it fails / what that ruled out>.

## User preferences and corrections

<!-- How the user wants things done, as they said it in this session: style,
     tools, things they asked you to stop doing, tone, language, what they care
     about. Quote short corrections verbatim. Leave out what is already in
     CLAUDE.md / AGENTS.md. -->

## Gotchas

<!-- Things that cost time and will again: env quirks, commands that need a flag
     or a specific dir, flaky tests, a service that must be running, misleading
     error messages. -->

## Read first

<!-- The 3–8 files (or artifacts) the next session should open before touching
     anything, as path:line plus why. Reference specs, plans, ADRs, issues, PRs,
     .squad/ runs or earlier handoffs by path or URL instead of copying them. -->

- `src/feature/thing.ts:42`: <why it matters>
- `docs/spec.md`: <what it settles>

## Running

<!-- Processes left running for this work (dev server, watcher, tunnel,
     background job) and how to check or restart them. The snapshot lists the
     ones started from this project; add what it cannot see (a background job,
     a tunnel, a container). Drop the section when nothing is running. -->

- `pnpm dev` on :5173 (pid 1234). Restart: `pnpm dev` in `apps/web`.

## Verify

<!-- Commands that confirm the state above in under a couple of minutes, with
     the expected result. -->

- `pnpm test src/feature`: 12 pass, 1 fails (`thing.test.ts:88`, expected; see In progress)

## Suggested skills

<!-- Skills or tools the next session should load, and for what step. -->

## Open questions

<!-- Decisions that belong to the user and are still open. Each one gets your
     recommended answer, so the next session can propose it. -->

- <question>? Recommended: <answer>, because <reason>.

<snapshot.sh output, pasted exactly as printed>
````

## What makes a handoff good

- **It describes state, not history.** "Login works with email; Google OAuth
  is half done (`auth/google.ts:30`, callback missing)". Not "First we looked at
  the login, then...". History only appears in Dead ends and in the reasons
  under Decisions.
- **It stands on its own.** Phrases like "as discussed" or "the approach we
  chose" mean nothing to the reader. Name the approach.
- **It gives numbers, not adjectives.** "Build went from 48 s to 12 s" or "3 of
  14 tests fail". Not "faster" or "mostly works".
- **It keeps what was checked apart from what was assumed.** Write "(not
  verified)" next to anything you did not confirm in this session.
- **It never carries secrets.** No tokens, passwords, keys or connection strings,
  even when they appeared in the conversation. Write "the API key is in
  `.env.local` (`STRIPE_KEY`)" instead.
