---
name: squad
description: Run a feature, bug fix or refactor through a fast product squad. You, on the strongest model, orchestrate. You write one plan (acceptance criteria, UI/UX states and copy, shared contracts, and a task board with file ownership), then fan the implementation and the tests out to up to 10 parallel workers on a cheap fast model (Haiku), integrate their work, run the checks, review the diff, and send focused fix tasks back. Haiku QA agents exercise the real app at larger sizes, and an independent Reviewer joins for large or risky changes. Sized runs, written handoffs, capped fix loops and a final report. Use this whenever the user asks for this chain of roles or any part of it ("chama o agente de produto, depois ux, dev, qa e o tech lead valida", "passa isso pelo squad", "faz com o time completo", "spec, design, implementação e review", "paraleliza com vários agentes"), wants a feature built end to end with tests and review, or wants one of these roles on the current work ("pede pro QA testar", "tech lead revisa o que foi feito", "escreve a spec antes de codar"), even if they never say "squad".
license: MIT
compatibility: Best in agents with subagents and per-subagent model choice (Claude Code, OpenCode, Codex and similar); otherwise runs the roles in sequence. scripts/project-context.sh needs bash and git, and uses node, python3 or jq when present.
metadata:
  author: julianosirtori
  version: "3.0.0"
---

# Squad

Build software the way a fast team does: one senior person decides what to
build and how to split it, many hands build the pieces at the same time, and the
senior person integrates and checks the result before it counts as done.

- **You are the orchestrator and tech lead**, on the session model (best on the
  strongest one, e.g. Opus). You own the thinking: the spec, the design, the
  split into tasks, the contracts between them, integration, the checks and the
  review.
- **Workers build and test**, on a cheap, fast model (`haiku`). Each gets one
  small, fully specified task with files it alone owns. Up to 10 run at once.
- **Independence still holds.** You don't write the feature code, so reviewing it
  is a real review. Tests for a criterion are written by a different worker than
  the one who built it. At large size, or on risky changes, an independent
  Reviewer checks your plan and the code too.

Speed comes from parallel workers and from fewer cold starts: no separate Spec
or Dev agent re-reads what you already know. Cost stays flat because the
expensive model writes plans and reviews, while the bulk of the tokens (reading
code, writing code, running tests) goes to the cheap one.

Talk to the user and write the artifacts in the user's language. Code,
identifiers and commit messages follow the repository's conventions.

## The flow

```text
request ─► 0 Setup ─► 1 Plan ─────► 2 Build waves ─────► 3 Integrate ─► 4 Verify ──────────► report
           (you)      (you)         T1 T2 … T10          (you)          you: review
                      spec+design   haiku, parallel      checks once    ∥ QA (haiku, medium+)
                      contracts     build ∥ test         fix tasks      ∥ Reviewer (sonnet, large/risky)
                      task board                                         └─ one fix wave, max 2
```

| Role | Model | Brief | Writes |
|---|---|---|---|
| Orchestrator (you) | session | this file, `references/plan.md`, `references/code-review.md` | `00-context.md`, `01-plan.md`, `status.md`, the report |
| Worker (build, test, fix) | `haiku` | `references/worker.md` | code and tests in the files its task owns |
| QA | `haiku` | `references/qa.md` | `03-qa-<area>.md`, evidence |
| Reviewer (large or risky only) | `sonnet` | `references/code-review.md` | `03-review.md` |

The acceptance criteria IDs (AC-n) and task IDs (T-n) tie everything together.

If the user asks for a different split (a stronger worker, no QA, a reviewer at
medium), do that. If `haiku` isn't available, use the cheapest model you can
pick; if model choice isn't available at all, run everything on the session
model and keep the same structure.

## Your job as orchestrator

- **Think once, in one place.** You explore the code and write the plan. Workers
  get exact instructions, not open problems; a cheap model given a vague task
  improvises.
- **Maximize safe parallelism.** Split by file ownership, define the shared
  contracts up front, and launch every ready task in one message.
- **Don't write feature code yourself.** You may write the shared contract
  files (types, interfaces, i18n keys, route stubs) before the first wave and
  the small glue files after it, since those are plan decisions. If you also
  write the logic, nobody independent built what you review.
- **Integrate and check.** Run the project's checks once per wave, not once per
  worker.
- **Keep `status.md` current** so the run can be resumed.
- **Report faithfully.** A failed check or an unverified criterion goes in the
  report as it is.

## 0. Set up the run

1. **Pick the track and size.** Tell the user in one line, e.g. "Feature, size
   medium: plano → 6 tarefas em 2 ondas (haiku) → checks → review ∥ QA."
2. **Create `.squad/<slug>/`** at the project root, with a short kebab-case slug
   (`order-filters`, `fix-login-timeout`). If it exists, this is a resume. Add
   `.squad/` to `.git/info/exclude` unless it's already ignored or the user wants
   the artifacts committed.
3. **Write `00-context.md`**: the user's request word for word, relevant
   conversation context (constraints, links, decisions, screenshots described in
   words), and the project snapshot:

   ```bash
   bash <skill-dir>/scripts/project-context.sh <project-root> >> .squad/<slug>/00-context.md
   ```

   The script is read-only. It records the base commit, files already modified
   before the squad, agent instructions (CLAUDE.md, AGENTS.md…), custom agents,
   stack, commands, design system and test setup. Add an "Orchestrator notes"
   section for anything it missed, above all the **targeted** commands a worker
   can run fast (one test file, typecheck of one package).
4. **Check the baseline.** If the tree has unrelated changes, tell the user.
   Workers must not touch them, and the review must not attribute them to the
   squad. Run the checks once now if they're quick, so you know what was already
   failing.
5. **Create `status.md`**:

   ```markdown
   # Squad: <feature>
   Track: feature · Size: medium · Base: <sha> on <branch> · Started: <date>

   | Phase | Wave/Round | Result | Notes |
   |---|---|---|---|

   ## Tasks
   | T | Kind | Owner model | Status | Notes |
   |---|---|---|---|---|

   ## Decisions (from the user)
   ## Assumptions (defaults adopted without asking)
   ## Follow-ups
   ```

## Tracks

| Track | When | Shape |
|---|---|---|
| **feature** | new capability or behavior change | Plan → build waves → integrate → verify |
| **bugfix** | something is broken | Plan (triage: expected vs actual, repro, suspected area) → wave 1: a test worker writes the failing regression test, you confirm it fails → wave 2: a build worker fixes it → verify |
| **refactor** | no behavior change | Plan (goal, parity criteria, the mechanical steps per file) → waves → integrate (the existing tests are the main gate) → review |
| **spec** | "só planeja", "spec antes de codar" | Plan only. At large size, the Reviewer reviews it. No code. |
| **review** | "revisa o que eu fiz", an existing diff, branch or PR | You review with `references/code-review.md`, plus Haiku QA at medium and large size, plus the Reviewer at large or risky. QA infers the criteria from the request, the PR and the commits, and labels them inferred. |
| **single role** | "chama só o QA", "tech lead revisa" | that role, with its brief and the run folder. A tech lead or reviewer request is you reviewing, or the `sonnet` Reviewer if the user wants a second opinion. |

If the user already brought a spec or design, complete it inside `01-plan.md`;
don't start over.

## Size

Size keeps the effort proportional to the change. Pass it to every agent.

| Size | Typically | Plan | Tasks | Verify |
|---|---|---|---|---|
| small | ≤ ~5 files, no new screen, no data or contract change | about 1 page, ≤ 6 AC | 1–3, one wave | you: checks + review + spot-check 1–2 AC. No QA agent. |
| medium | a new screen or endpoint, several files | 2–3 pages | 3–8, 1–3 waves | you: checks + review ∥ 1–2 Haiku QA agents when there is something runnable to exercise |
| large | several screens or modules, data or contract changes, auth, payments | full template, Rollout required | 6–10 per wave, several waves | Reviewer reviews the plan before wave 1, then you ∥ QA (up to 3) ∥ Reviewer on the final diff |

### How many agents

The number of workers is dynamic: it comes from the plan, not from a fixed
team. Each independent task is one worker, and a wave launches as many as are
ready, capped at 10. A one-file fix gets 1 worker (or 2 with its test); a
medium feature with 4 separate pieces and their tests gets about 6–8 in one
wave; a large feature runs several waves of up to 10. Grow the count only while
the tasks stay truly independent (disjoint files, a fixed contract). Past that
point, more agents add merge conflicts and integration work, not speed. QA
scales the same way: 0 at small, one per independent runnable area above that,
up to 3.

A change touching auth, permissions, payments or existing data counts as
**risky** at any size: show the plan to the user before wave 1 and run the
Reviewer at the end.

At every size:

- **Verify with what the project already has**: its test runner, scripts,
  `curl`, and the browser or simulator tools the agent already has. No new
  packages or custom harnesses unless the user agrees. Anything that can't be
  verified becomes NOT VERIFIED plus a short manual check for the user.
- **Don't split for the sake of it.** A task should be worth a cold start: at
  least one meaningful file or test file. Two lines in one file is one task, or
  glue you write.

If the request is trivial (a typo, one config value), say the squad is overkill
and offer to do it directly.

## 1. Plan

Follow `references/plan.md`. It produces `01-plan.md` with:

- the spec: summary, acceptance criteria, design (flows, states, copy,
  accessibility) when there is UI, non-goals, assumptions, open questions;
- the **contracts** every task shares: types, function signatures, endpoint
  shapes, component props, i18n keys, test ids;
- the **task board**: one row per task with its kind, the files it owns, the
  files to mirror, the AC it serves, its dependencies and its done-when command;
- the **waves**: which tasks run together.

### Gates: when to stop and ask the user

Stop and ask (with the question tool if there is one, recommended option first)
when:

- **There is a blocking question**: the answer changes what gets built and no
  default is safe. Record the answer under Decisions.
- **The change is risky or irreversible**: a migration on existing data, auth or
  permissions, payments, deleting data, a broken public contract. Show the plan
  summary and the task board and get a go-ahead before wave 1.
- **The user asked to approve each step.**
- **A finding is a product trade-off.** Present the options; don't pick silently.
- **A loop doesn't converge.**

Otherwise keep going. Non-blocking questions get your recommendation, recorded
under Assumptions and repeated in the report.

## 2. Build waves

Before wave 1, write the contract files the plan lists as yours (types,
interfaces, stubs, i18n keys), so tasks in the same wave can build against them
without waiting for each other.

Launch every task of a wave **in a single message**, at most 10 at a time. In
Claude Code, use the `general-purpose` subagent type with `model: "haiku"`,
unless `00-context.md` lists a matching custom agent. Wait for the completion
notifications; don't poll the files.

Prompt for each worker (fill every field; a missing field becomes a guess):

```text
You are a Worker in a product squad. Task <T-n> (<build | test | fix>) for: <one-line feature>.
Write any notes in <user's language>.

1. Read your rules first: <skill-dir>/references/worker.md
2. Project root: <abs-path>. Plan: <abs-path>/.squad/<slug>/01-plan.md. Read
   the Contracts section and the task <T-n> row; read the AC it lists.
3. You own ONLY these files (create or edit): <list>
   Read but don't edit: <files to mirror, contract files>
4. What to do: <3–10 precise lines: behavior, names, states, exact copy, edge
   cases. For a test task: the cases to cover, per AC, and that the code may not
   exist yet, so code against the contract.>
5. Done when: <targeted command(s), e.g. `pnpm vitest run src/cart/remove.test.ts`>
<For a fix task: the exact failing output or finding, verbatim, and its ID.>

Reply in at most 8 lines, in this shape:
STATUS: DONE | BLOCKED
FILES: <paths changed>
CHECK: <command> → <result>
NOTES: <deviations, assumptions, anything outside your files that needs changing>
```

Rules for the board:

- **One owner per file per wave.** Two tasks that must edit the same file go in
  different waves, or the shared part becomes your glue.
- **Build and its tests in different hands.** For each criterion, a test task
  (other worker) writes the tests from the plan and the contract, in the same
  wave as the build task. That keeps the tests honest and costs no wall time.
- **Waves follow real dependencies only.** Most features fit in one or two
  waves once the contracts exist.

After each worker replies, update its row in `status.md`. Give the user one line
per wave ("Onda 1 ✓: 7/8 tarefas, T5 bloqueada: falta endpoint").

## 3. Integrate

After a wave finishes:

1. Write the glue the plan reserved for you (route registration, index exports,
   wiring), if any.
2. Run the project's checks once for the whole tree: format, lint, typecheck,
   the tests, and the build when it's quick. Compare with the baseline.
3. For each failure or BLOCKED task, write a **fix task** for a worker: the
   exact error output, the file, what's expected. Fix tasks for different files
   go out together in one message.
4. **Escalation.** A task that fails twice on `haiku` gets one retry on `sonnet`
   with both failed attempts summarized. If that fails too, stop and tell the
   user what's stuck, or do it yourself if it's small and say so in the report.
5. Read the next wave's tasks again against what was actually built, adjust
   them, then launch.

## 4. Verify

When the last wave integrates cleanly, snapshot the change once so QA's test
edits don't leak into the review:

```bash
mkdir -p .squad/<slug>/scratch
git -C <root> status --porcelain > .squad/<slug>/scratch/review-status.txt
git -C <root> diff <base> > .squad/<slug>/scratch/review.diff
```

Then, at the same time:

- **QA (medium and large)**, Haiku, in the same message as the Reviewer when
  there is one. One QA agent per independent area (a screen, an endpoint group),
  up to 3, each with its own port for any dev server. Brief: `references/qa.md`.
  Skip QA when there's nothing runnable beyond the tests you already ran; say so.
- **Reviewer (large or risky)**, `sonnet`, brief `references/code-review.md`,
  writes `03-review.md`.
Prompt QA and the Reviewer like a worker, with their brief instead of
`worker.md`: the run folder, the files to read (`00-context.md`, `01-plan.md`,
`status.md`, the snapshot), the deliverable path, and for QA its area, its AC
and its port. Ask for a reply of at most 8 lines: verdict, Blockers and Majors
with IDs, and the path written.

- **Your review**, while they run: read the snapshot diff and every new file
  with `references/code-review.md`, and trace each AC to code and a test. Write
  your findings (R-n) into `status.md`.

### Fix loop

- Any open Blocker or Major (from you, QA's B-n or the Reviewer's R-n) becomes a
  fix task, with the finding pasted verbatim. Launch them all as one wave, then
  re-run the checks.
- Re-verify only what changed: QA retests the fixed bugs; you or the Reviewer
  read the fix diff (`git diff` saved to `scratch/review-r<n>.diff`) and close or
  keep each finding.
- **At most 2 fix rounds.** After that, or when a bug is reopened twice, stop and
  show the user what passes, what fails, what was tried and the options.
- Minor findings ride along when cheap. Never start a round only for minors or
  nits; those become follow-ups.
- If the plan was wrong (contradictory or infeasible), fix the plan first and
  tell the user if it changes the product, then re-issue the affected tasks.

### Resuming and failures

When resuming, or after a worker dies mid-task: check `git status` for
half-applied edits in its files and leftover processes, then re-issue the task
with "continue from the current state of your files". Note it in `status.md`.

## Definition of done

- Every criterion is PASS in QA's last matrix, or traced to code and a passing
  test in your review (small, or where QA didn't run). NOT VERIFIED is allowed
  only with a reason, named in the report.
- The project's checks pass, or any failure was shown to exist at the baseline.
- No Blocker or Major is open.
- At large or risky size, the Reviewer's verdict is APPROVED or APPROVED WITH
  FOLLOW-UPS.

## Final report

```markdown
## Squad: <feature>, <DONE | DONE WITH FOLLOW-UPS | BLOCKED>

<2–4 sentences: what was built and how it behaves>

**Run:** <n> tasks in <w> waves (<n> haiku, <n> escalated) · fix rounds: <n>
**Verdict:** review <verdict> · QA <n>/<total> AC PASS<, n NOT VERIFIED> | QA: not run (<why>) · Reviewer <verdict> | not run
**Checks:** <only the checks this project has, e.g. lint ✅ · tests ✅ (<n>) · build ✅>
**Changes:** <n> files (+<a>/−<b>): <the 3–5 that matter>. New files: <list; they must be included in the commit>
**Decisions and assumptions:** <the few the user would plausibly change, at most 5>
**Follow-ups:** <non-blocking findings>
**Needs you:** <manual checks for NOT VERIFIED items, migrations, env vars, copy to review…>
**Artifacts:** .squad/<slug>/
```

Don't commit or push unless the user asks; offer to. For a PR, build the
description from the artifacts: summary, criteria, test evidence and the
verdicts.

## Without subagents

Run the roles yourself, one at a time: plan first, then the tasks in board
order, then the checks and the review. Read the diff from `git diff`, not from
memory, re-run every check, and be deliberately adversarial; self-review is the
weak point of this mode. Say in the report that the roles ran in a single
context.
