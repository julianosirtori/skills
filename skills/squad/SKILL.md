---
name: squad
description: Run a feature, bug fix or refactor through a lean product squad of subagents. A Spec role writes acceptance criteria plus the UI/UX (flows, states, copy, accessibility) in one document, Dev plans, codes and tests, then QA verifies each criterion with evidence while an independent Reviewer reviews the diff and gives the final verdict. Sized runs, written handoffs, capped fix loops and a final report. Use this whenever the user asks for this chain of roles or any part of it ("chama o agente de produto, depois ux, dev, qa e o tech lead valida", "passa isso pelo squad", "faz com o time completo", "spec, design, implementação e review"), wants a feature built end to end with QA and review, or wants one of these roles on the current work ("pede pro QA testar", "tech lead revisa o que foi feito", "escreve a spec antes de codar"), even if they never say "squad".
license: MIT
compatibility: Best in agents with subagents (Claude Code, OpenCode, Codex and similar); otherwise runs the roles in sequence. scripts/project-context.sh needs bash and git, and uses node, python3 or jq when present.
metadata:
  author: julianosirtori
  version: "2.0.0"
---

# Squad

Build software the way a lean team does: one person owns the problem and the
experience, one builds it, and fresh eyes check it before it counts as done.
The checking roles run as separate subagents, so the review comes from someone
other than the author. That independence is the reason to use this skill.

Every extra role costs a cold start: a new agent re-reads the artifacts and the
code. So the squad has as few roles as independence needs, and passes files
instead of summaries.

Talk to the user and write the artifacts in the user's language. Code,
identifiers and commit messages follow the repository's conventions.

## The flow

```text
request ─► 0 Context ─► 1 Spec ─► 2 Dev ─┬─► 3 QA ──────┬─► report
           (you)      product+UX   code  └─► 3 Reviewer ─┘
                          │                 ▲       │
                          └─ questions      └─ B-n, R-n (one fix round, max 2)
                             to the user
```

| # | Role | Brief | Deliverable | Model | Owns |
|---|---|---|---|---|---|
| 0 | You (orchestrator) | this file | `00-context.md`, `status.md` | session | the run |
| 1 | Spec | `references/spec.md` | `01-spec.md` | sonnet | what, why and the experience: criteria (AC-n), states, copy |
| 2 | Developer | `references/dev.md` | code + `02-dev.md` | session | how: plan, implementation, tests, checks |
| 3 | QA | `references/qa.md` | `03-qa.md` (+ test files) | sonnet | evidence that each AC holds, bugs (B-n) |
| 3 | Reviewer | `references/code-review.md` | `03-review.md` | sonnet | the code and the final verdict, findings (R-n) |

The acceptance criteria IDs tie the roles together: Dev maps code and tests to
them, QA builds its matrix from them, and the Reviewer traces them to code.

The Model column is the default. Pass it as the subagent's model. If the user
asked for a stronger review, or the change is large and touches auth, payments
or data, run the Reviewer on the session model.

## Your job as orchestrator

- **Hand over file paths, not paraphrases.** Each role reads the user's verbatim
  request in `00-context.md` and the earlier artifacts itself.
- **Decide which roles run and how deep** (Tracks, Size).
- **Run the gates.** Stop for the user only when a decision is really theirs.
- **Keep `status.md` current** so the run can be resumed.
- **Report faithfully.** A failed check or an unverified criterion goes in the
  report as it is.
- **Stay light.** Read a role's reply, not its whole artifact, unless a gate
  depends on it.

When subagents are available, don't do a role's work yourself. If you write the
code and then review it, nobody independent has checked it.

## 0. Set up the run

1. **Pick the track and size.** Tell the user in one line, e.g. "Feature, size
   medium: Spec → Dev → QA ∥ Reviewer."
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
   section for anything it missed.
4. **Check the baseline.** If the tree has unrelated changes, tell the user. Dev
   must not touch them and the reviewers must not attribute them to the squad.
5. **Create `status.md`**:

   ```markdown
   # Squad: <feature>
   Track: feature · Size: medium · Base: <sha> on <branch> · Started: <date>

   | Phase | Round | Result | Notes |
   |---|---|---|---|

   ## Decisions (from the user)
   ## Assumptions (defaults adopted without asking)
   ## Follow-ups
   ```

## Tracks

| Track | When | Roles |
|---|---|---|
| **feature** | new capability or behavior change | Spec → Dev → QA ∥ Reviewer |
| **bugfix** | something is broken | Spec (triage: expected vs actual, repro, impact) → Dev (failing test first) → QA ∥ Reviewer |
| **refactor** | no behavior change | Spec (half a page: goal, constraints, parity criteria) → Dev → Reviewer, plus QA at large size |
| **spec** | "só planeja", "spec antes de codar" | Spec → Dev (plan only) → Reviewer (plan review). No code. |
| **review** | "revisa o que eu fiz", an existing diff, branch or PR | Reviewer, plus QA at medium and large size. QA infers the criteria from the request, the PR and the commits, and labels them inferred. Write the review scope in `00-context.md` (uncommitted files and/or `git diff <default-branch>...HEAD`). |
| **single role** | "chama só o QA", "tech lead revisa" | that role (a tech lead request maps to the Reviewer), with its brief and the run folder |

If the user already brought a spec or design, the Spec role completes it and
converts it to the template; it doesn't start over. If the change has no
user-facing surface, the spec has no Design section.

## Size

Size keeps the effort proportional to the change. Choose it deliberately and
pass it to every role; each brief opens with a "Depth by size" table.

| Size | Typically | Shape of the run |
|---|---|---|
| small | ≤ ~5 files, no new screen, no data or contract change | Spec ≤ 6 AC, about 1 page → Dev → **Reviewer only**, which also runs the checks and spot-checks the criteria |
| medium | a new screen or endpoint, several files | Spec → Dev → QA ∥ Reviewer |
| large | several screens or modules, data or contract changes, auth, payments | Spec → Dev (plan only) → Reviewer (plan review) → Dev → QA ∥ Reviewer |

At every size:

- **Verify with what the project already has**: its test runner, scripts,
  `curl`, and the browser or simulator tools the agent already has. No new
  packages or custom harnesses unless the user agrees. Anything they can't
  verify becomes NOT VERIFIED plus a short manual check for the user.
- **Don't redo another role's work.** QA doesn't redesign the criteria; the
  Reviewer doesn't re-test by hand when QA ran.
- **Don't pass bloat downstream.** If an artifact clearly overshoots its size,
  tell the next role which criteria are the core.

If the request is trivial (a typo, one config value), say the squad is overkill
and offer to do it directly.

## Running each role

Run Spec, then Dev, one at a time. In Claude Code, use the `general-purpose`
subagent type with the model from the roles table, unless `00-context.md` lists
a matching custom agent (e.g. `.claude/agents/qa.md`); then use it and still
give it the run folder and deliverable path. Wait for the completion
notification before starting the next role; don't poll for the artifact.

Prompt for each role:

```text
You are the <Role> of a product squad working on: <one-line feature>.
Track: <track>. Size: <size>. Write everything in <user's language>.

1. Read your brief: <skill-dir>/references/<brief>.md. It sets your job, your
   deliverable, the depth for your size and the quality bar.
2. Project root: <abs-path>. Run folder: <abs-path>/.squad/<slug>/
3. Read: 00-context.md, status.md<, earlier artifacts>.
4. Write your deliverable to <run folder>/<NN-role>.md. Throwaway files go in
   <run folder>/scratch/.
<Round-specific instructions, e.g. "Fix round 1: fix B1, B3 and R2.">
<Decisions from the user since the last phase.>
<Useful tools or skills, e.g. "Browser automation is available.">

Reply in at most 10 lines: status or verdict, blocking issues, questions for
the user (each with your recommendation), and the path you wrote.
```

After each role: update `status.md`, give the user one line of progress ("Spec
✓: 6 critérios, 1 dúvida bloqueante"), and check the gates.

### QA and Reviewer in parallel

When Dev is done, save the change once, so QA's test edits don't leak into the
review:

```bash
mkdir -p .squad/<slug>/scratch
git -C <root> status --porcelain > .squad/<slug>/scratch/review-status.txt
git -C <root> diff <base> > .squad/<slug>/scratch/review.diff
```

New untracked files appear in the status file; the Reviewer reads them in full.
On the review track, save the scope from `00-context.md` instead.

At medium and large size, start QA and the Reviewer in the same message. Neither
edits production code and neither reads the other's report. At small size, run
the Reviewer alone.

### Gates: when to stop and ask the user

Stop and ask (with the question tool if there is one, recommended option first)
when:

- **Spec lists a blocking question.** Record the answer under Decisions and pass
  it on.
- **The change is risky or irreversible**: a migration on existing data, auth or
  permissions, payments, deleting data, a broken public contract. Show the plan
  and get a go-ahead before Dev implements.
- **The user asked to approve each step.** Pause after every role.
- **A finding is a product trade-off**, e.g. the Reviewer says a specified
  behavior is too costly. Present the options; don't pick silently.
- **A loop doesn't converge.**

Otherwise keep going. Non-blocking questions get the role's recommendation,
recorded under Assumptions and repeated in the report.

### Fix loops

- **QA FAIL or Reviewer CHANGES REQUESTED** (an open Blocker or Major): run one
  Dev fix round with all open B-n and R-n together. Then, in parallel:
  - QA retests the fixed bugs and regresses around the changed files (medium
    and large);
  - the Reviewer re-reviews a fresh diff of what changed since its round
    (`git diff` of the fix, saved to `scratch/review-r<n>.diff`), confirms each
    R-n and decides disputed ones.
- **At most 2 fix rounds.** After that, or when a bug is reopened twice, stop and
  show the user what passes, what fails, what was tried and the options.
- **Minor findings** ride along in a fix round when cheap. Never start a round
  only for minors or nits; those become follow-ups.
- **The spec is wrong** (contradictory or infeasible): don't let Dev improvise a
  product decision. Send it back to Spec for a short revision, or to the user.

### Resuming and failures

A phase is done when its artifact is complete: every template section present,
and reviews have a verdict line. When resuming, or after a subagent dies
mid-run:

1. Complete artifact: record the phase and move on.
2. Partial: check for leftovers (running servers, half-applied edits via `git
   status`). Resume the same agent if possible (SendMessage keeps its context);
   otherwise re-run the role and tell it to continue from the partial file.
3. Note the interruption in `status.md` and the report.

## Definition of done

- Every criterion is PASS in QA's last matrix (medium and large) or traced and
  spot-checked by the Reviewer (small). NOT VERIFIED is allowed only with a
  reason, named in the report.
- The project's checks pass, or any failure was shown to exist before the squad.
- No Blocker or Major is open from QA or the Reviewer.
- The Reviewer's verdict is APPROVED or APPROVED WITH FOLLOW-UPS.

## Final report

```markdown
## Squad: <feature>, <DONE | DONE WITH FOLLOW-UPS | BLOCKED>

<2–4 sentences: what was built and how it behaves>

**Verdict:** Reviewer <verdict> · QA <verdict> (<n>/<total> AC PASS<, n NOT VERIFIED>) | QA: not run (small) · fix rounds: <n>
**Checks:** <only the checks this project has, e.g. lint ✅ · tests ✅ (<n>) · build ✅>
**Changes:** <n> files (+<a>/−<b>): <the 3–5 that matter>. New files: <list; they must be included in the commit>
**Decisions and assumptions:** <the few the user would plausibly change, at most 5>
**Follow-ups:** <non-blocking findings>
**Needs you:** <manual checks for NOT VERIFIED items, migrations, env vars, copy to review…>
**Artifacts:** .squad/<slug>/
```

Don't commit or push unless the user asks; offer to. For a PR, build the
description from the artifacts: summary, criteria, test evidence and the
Reviewer's verdict.

## Without subagents

Run the roles yourself, one at a time: re-read each brief before its phase,
write the same artifacts, and finish each phase before the next (no coding
during the spec). For QA and the review, read the diff from `git diff`, not from
memory, re-run every check, and be deliberately adversarial; self-review is the
weak point of this mode. Say in the report that the roles ran in a single
context.
