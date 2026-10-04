---
name: squad
description: Run a feature, bug fix or refactor through a product squad of subagents. Product writes the spec and acceptance criteria, UI/UX designs flows, states, copy and accessibility, Dev plans, codes and tests, QA independently verifies it against the criteria, and a Tech Lead validates everything before it is called done. Includes written handoffs, fix loops between roles and a final report. Use this whenever the user asks for this chain of roles or any part of it ("chama o agente de produto, depois ux, dev, qa e o tech lead valida", "passa isso pelo squad", "faz com o time completo", "spec, design, implementação e review"), wants a feature built end to end with QA and review, or wants one of these roles on the current work ("pede pro QA testar", "tech lead revisa o que foi feito", "escreve a spec antes de codar"), even if they never say "squad".
license: MIT
compatibility: Best in agents with subagents (Claude Code, OpenCode, Codex and similar); otherwise runs the roles in sequence. scripts/project-context.sh needs bash and git, and uses node, python3 or jq when present.
metadata:
  author: julianosirtori
  version: "1.0.0"
---

# Squad

Build software the way a good cross-functional team does. Someone owns the
problem, someone owns the experience, someone builds it, someone tries to break
it, and someone senior signs off. Each role runs as a separate subagent with its
own brief. Reviews then come from fresh eyes instead of from the author grading
their own work. That independence is the main reason to use this skill, so
protect it.

Talk to the user and write the artifacts in the user's language. Code,
identifiers and commit messages follow the repository's conventions.

## The flow

```text
request ─► 0 Context ─► 1 Product ─► 2 UI/UX ─► 3 Dev ─► 4 QA ─► 5 Tech Lead ─► report
           (you)         spec          design     code     verify    validate
                           │              │         ▲        │          │
                           └─ questions ──┘         ├─ bugs ─┘          │
                              to the user           └──── changes ──────┘
```

| # | Role | Brief | Deliverable | Owns |
|---|---|---|---|---|
| 0 | You (orchestrator) | this file | `00-context.md`, `status.md` | the run |
| 1 | Product | `references/product.md` | `01-product.md` | what and why: scope, acceptance criteria (AC-n) |
| 2 | UI/UX | `references/ux.md` | `02-ux.md` | flows, screens, states, copy, accessibility |
| 3 | Developer | `references/dev.md` | code + `03-dev.md` | how: plan, implementation, tests, checks |
| 4 | QA | `references/qa.md` | `04-qa.md` (+ test files) | evidence that each AC holds, plus bugs (B-n) |
| 5 | Tech Lead | `references/tech-lead.md` | `05-tech-lead.md` | final verdict, findings (T-n) |

The acceptance criteria IDs are the thread that ties the roles together. UX maps
screens to them, Dev maps code and tests to them, QA builds its matrix from them,
and the Tech Lead checks them. Keep the IDs stable.

## Your job as orchestrator

You coordinate and the roles do the work:

- **Hand over files, not paraphrases.** Every role reads the previous artifacts
  and the user's verbatim request. Summaries passed from agent to agent lose
  detail at each step.
- **Decide which roles run and how deep** (see Tracks, and Size and budget).
- **Run the gates.** Stop for the user when a decision is really theirs, and keep
  going otherwise.
- **Keep `status.md` current** so the run can be resumed and audited.
- **Report faithfully.** A failed check or an unverified criterion goes in the
  report as it is.

When subagents are available, don't do a role's work yourself. If you write the
code and then review it yourself, nobody independent has checked it.

## 0. Set up the run

1. **Pick the track and size** (tables below). Tell the user in one line, e.g.
   "Feature, size medium: Product → UX → Dev → QA → Tech Lead."
2. **Create the run folder** at the project root: `.squad/<slug>/`, with a short
   kebab-case slug for the feature (`order-filters`, `fix-login-timeout`). If
   that folder already exists, this is a resume (see Resuming and failures).
   To keep the folder out of
   `git status` without touching tracked files, add `.squad/` to
   `.git/info/exclude` unless it is already ignored or the user wants the
   artifacts committed.
3. **Write `00-context.md`**. It holds the user's request word for word, anything
   relevant from the conversation (constraints, links, decisions, pasted specs or
   screenshots described in words), and the project snapshot:

   ```bash
   bash <skill-dir>/scripts/project-context.sh <project-root> >> .squad/<slug>/00-context.md
   ```

   The script is read-only. It records the base commit and the files that were
   already modified before the squad started. It also finds agent and contributor
   instructions (CLAUDE.md, AGENTS.md...), custom agents, the stack, the
   package manager, which checks exist (and which don't), the UI layer, the
   design system and the test setup. If it missed something you can see (say,
   the UI lives somewhere unusual), add a short "Orchestrator notes" section to
   the file.
4. **Check the baseline.** If the working tree already has unrelated changes,
   tell the user. The developer must not touch or revert them, and reviewers
   must not attribute them to the squad.
5. **Create `status.md`**:

   ```markdown
   # Squad: <feature>
   Track: feature · Size: medium · Base: <sha> on <branch> · Started: <date>

   | Phase | Round | Result | Notes |
   |---|---|---|---|
   | Product | 1 | done | 7 AC, 1 blocking question answered |

   ## Decisions (from the user)
   ## Assumptions (defaults adopted without asking)
   ## Follow-ups
   ```

## Tracks

| Track | When | Roles | What changes |
|---|---|---|---|
| **feature** | new capability or behavior change | all five | the default flow |
| **bugfix** | something is broken | Product (triage) → UX if the fix changes UI → Dev → QA → TL | Product writes expected vs actual, repro and impact. Dev reproduces the bug with a failing test before fixing it. QA confirms the repro is gone and checks around it. |
| **refactor** | tech debt, no behavior change | Product (goal and constraints, short) → Dev → QA → TL | The criteria say behavior is unchanged, plus the measurable goal. QA focuses on parity. The TL review is heavier. |
| **spec** | "só planeja", "spec antes de codar" | Product → UX → Dev (plan only) → TL (plan review) | no code is written |
| **review** | "revisa o que eu fiz", an existing diff, branch or PR | QA → TL | No Product phase. QA infers criteria from the request, the PR description and the commits, and labels them as inferred. The work to review is the user's existing changes. The snapshot lists those as "already modified", so write the review scope explicitly in `00-context.md`: the uncommitted files and/or `git diff <default-branch>...HEAD`. |
| **single role** | "chama só o QA" | that role | It still uses its brief and the run folder. |

Skip UI/UX when the change has no user-facing surface. When the surface is an
API, CLI, SDK or error messages, UX reviews the developer experience instead.
Record every skipped role and the reason in `status.md`.

If the user already brought a spec or a design (pasted text, a file, a link a
tool can read), that role's job becomes completing it and converting it to the
template. The role does not start from scratch.

## Size and budget

The squad is expensive. In testing, a small feature (a filter and a counter,
about 100 lines of code) took 42 minutes and roughly 650k tokens when the
roles had no limits. The roles went for completeness: 18 criteria, a 250-line
design document, and three home-made test harnesses. Size is how you keep the
effort proportional to the change, so choose it deliberately and pass it to
every role. Each brief opens with a "Depth by size" table that sets concrete
limits.

| Size | Typically | Shape of the run |
|---|---|---|
| small | ≤ ~5 files, no new screen, no data or contract change | short artifacts: ≤ 8 criteria, about 1 page per document |
| medium | a new screen or endpoint, several files | the full templates |
| large | several screens or modules, data model or contract changes, auth, payments | full templates, plus a plan review before coding |

Two rules apply at every size:

- **Verify with what the project already has**: its test runner, its scripts,
  `curl`, and the browser or simulator tools the agent already has. Don't
  install packages or build custom verification harnesses unless the user
  agrees. Anything the existing tools can't verify becomes NOT VERIFIED plus a
  short manual check for the user. A two-minute check by a person is cheaper
  than a 100k-token harness.
- **Don't redo the previous role's work.** The Tech Lead spot-checks QA's
  evidence; it doesn't re-run all of QA's testing. QA runs the checks fresh, but
  it doesn't redesign the test plan Product already wrote as criteria.

If an artifact clearly overshoots its budget, don't pass the bloat downstream.
Tell the next role which criteria are the core and which are best effort, or ask
the role for a short trim round.

If the request is trivial (a typo, one config value), say the full squad is
overkill and offer to do it directly. Run the squad anyway if the user wants it.

## 1–5. Running each role

Run the roles one at a time, because each role reads the previous role's
artifact. In Claude Code, use the `general-purpose` subagent type for every
role. Each one writes its own file, and Dev and QA also run commands and edit
code or tests. Subagents may run in the background. Wait for the completion
notification before starting the next role, and don't poll for the artifact:
the file can exist before the role is done with it.

If `00-context.md` lists custom agents for a role (e.g. `.claude/agents/qa.md`),
use them instead, because they carry the team's conventions. Still give them
the run folder and the deliverable path.

Prompt for each role:

```text
You are the <Role> of a product squad working on: <one-line feature>.
Track: <track>. Size: <size>. Write everything in <user's language>.

1. Read your brief first: <skill-dir>/references/<role>.md. It defines your job,
   your deliverable, the depth for your size and the quality bar.
2. Project root: <abs-path>. Run folder: <abs-path>/.squad/<slug>/
3. Read: 00-context.md, status.md<, previous artifacts in order>.
4. Write your deliverable to <run folder>/<NN-role>.md. Put any throwaway
   scripts or outputs in <run folder>/scratch/, never elsewhere.
<Round-specific instructions, e.g. "Fix round 2: fix B1 and B3 from 04-qa.md, Round 1.">
<Decisions from the user since the last phase.>
<Tools and skills worth using, e.g. "Browser automation is available for testing
the UI." or "Load the expo-router skill before touching navigation.">

Reply in at most 15 lines: your status or verdict, blocking issues, questions
for the user (each with your recommended answer), and the path you wrote.
```

After each role finishes:

1. Read its reply, and read the artifact when a gate depends on it.
2. Update `status.md`.
3. Give the user one line of progress, e.g. "Produto ✓: 8 critérios, 1 dúvida
   bloqueante".
4. Check the gates.

### Gates: when to stop and ask the user

Stop and ask (use the question tool if the agent has one, e.g. AskUserQuestion)
when:

- **Product or UX lists a blocking question.** That is a decision that changes
  what gets built and has no safe default. Put the role's recommended option
  first. Record the answer under Decisions and pass it to the next role.
- **The change is risky or irreversible**: a migration on existing data,
  auth or permissions, payments, deleting data, or breaking a public contract.
  Show the plan summary and get a go-ahead before Dev implements it.
- **The user asked to approve each step** ("com aprovação em cada etapa"). Pause
  after every role.
- **Roles disagree on a product trade-off.** For example, the Tech Lead says a
  specified behavior is too costly. Present the options and don't pick one
  silently.
- **A loop does not converge** (see below).

Otherwise keep going. A non-blocking question gets the role's recommended
default, recorded under Assumptions and repeated in the final report so the user
can revisit it.

### Plan review for large or risky changes

When the size is large or the spec touches a risk area, run Dev in two steps.
First Dev writes only the Plan section of `03-dev.md` ("plan only, do not edit
code"). Then the Tech Lead reviews that plan alone (plan review mode in its
brief). Then Dev implements the approved plan. A wrong approach caught at this
point costs minutes. Caught in the final review, it costs the whole
implementation.

### Fix loops

- **QA verdict FAIL** (an open blocker or major bug): run Dev for a fix round with
  those bug IDs. Then run QA for a retest round covering the fixed bugs, plus a
  regression check around the files that changed. Repeat up to **3** QA rounds.
  Minor bugs can go into the same fix round when they are cheap. Never start a
  full round only for minor bugs or nits. One exception: when the open minor
  findings have tiny, safe fixes (a few lines each), you may run one short Dev
  micro-round for them before the report. Re-run the project's checks after
  it, but skip the full QA round. Everything else becomes a follow-up.
- **Tech Lead CHANGES REQUESTED**: run Dev for the T-n findings. Then run QA for a
  short regression round (checks plus the affected criteria). Then run the Tech
  Lead to re-review the changes. Repeat up to **2** TL rounds.
- **Disputed findings**: if Dev marks a finding "Disputed", the reviewer who
  raised it decides in the next round. If it is a product trade-off, the user
  decides.
- **The spec is wrong**: if Dev or QA finds the spec contradictory or infeasible,
  don't let the developer improvise a product decision. Send it back to Product
  for a short revision round, or to the user.
- **No convergence**: a bug is reopened twice, or a round limit is hit. Stop.
  Show the user where things stand (what passes, what fails, what was tried) and
  the options.

### Resuming and failures

Judge a phase by its artifact, not only by `status.md`. A phase is done when its
file is complete: every section of the template is present, and reviews have a
verdict line. When resuming, or after a subagent dies mid-run (rate limit,
crash, timeout):

1. Read the artifact. If it is complete, record the phase in `status.md` and
   move on.
2. If it is partial, check for leftovers: servers still listening, half-applied
   edits (`git status`, `git diff`). Then resume the same agent if the
   environment allows it (in Claude Code, SendMessage keeps its context).
   Otherwise re-run the role and tell it to continue from the partial file.
3. Note the interruption in `status.md` and in the final report.

## Definition of done

- Every criterion is PASS in QA's last matrix. A NOT VERIFIED criterion is
  allowed only with a stated reason, and the final report names it.
- The project's checks pass (format, lint, typecheck, tests, build, whichever
  apply), or any failure was shown to exist before the squad started.
- No blocker or major bug is open from QA, and no blocker or major finding is
  open from the Tech Lead.
- The Tech Lead verdict is APPROVED or APPROVED WITH FOLLOW-UPS.

## Final report

Close with:

```markdown
## Squad: <feature>, <DONE | DONE WITH FOLLOW-UPS | BLOCKED>

<2–4 sentences: what was built and how it behaves>

**Verdict:** Tech Lead <verdict> · QA <verdict> (<n>/<total> AC PASS<, n NOT VERIFIED>) · rounds: QA <n>, TL <n>
**Checks:** <only the checks this project has, e.g. lint ✅ · tests ✅ (<n>) · build ✅; "none" if it has none>
**Changes:** <n> files (+<a>/−<b>): <the 3–5 that matter>. New files: <list them; they must be included in the commit>
**Decisions and assumptions:** <the few the user would plausibly change, at most 5; the rest are in status.md>
**Follow-ups:** <non-blocking findings>
**Needs you:** <manual checks for NOT VERIFIED items, a migration to run, an env var to set, copy to review...>
**Artifacts:** .squad/<slug>/
```

Count a criterion as PASS only when every case for it passed. Count it as NOT
VERIFIED when any of its cases is unverified and none failed. List what each
NOT VERIFIED criterion needs from the user under "Needs you", as a short manual
check.

Don't commit or push unless the user asks. Offer to do it. If they want a PR,
build the description from the artifacts: summary, acceptance criteria, test
evidence and the Tech Lead verdict.

## Without subagents

If the agent can't spawn subagents, run the roles yourself, one at a time:

- Re-read the role's brief before each phase, and write the same artifacts.
- Finish each phase completely before starting the next. No coding during the
  spec.
- For QA and Tech Lead, review the work as if someone else wrote it. Read the
  diff from `git diff`, not from memory, and run every check again. Self-review
  is the weak point of this mode, so be deliberately adversarial.
- Say in the final report that the roles ran in a single context.
