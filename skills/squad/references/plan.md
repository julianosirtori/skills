# Plan (orchestrator)

You turn the request into one document, `01-plan.md`, that does two jobs:

1. **The spec**: what "done" means, so QA can test it and you can review
   against it. Acceptance criteria, plus the screens, states, copy and
   accessibility when there is UI.
2. **The build plan**: how the work splits into small tasks that cheap, fast
   workers can do in parallel without talking to each other or guessing.

The second job is where the run's speed and quality are decided. A worker on a
small model follows instructions well and makes product or architecture
decisions badly. Every decision you leave open in a task becomes a guess, a
merge conflict or a fix round. So decide here.

## Depth by size

| | small | medium | large |
|---|---|---|---|
| Criteria | **≤ 6**: the requested behavior plus the 1–2 most likely unhappy paths | typically 6–12 | full coverage, grouped by story |
| Design | only what changes: one wireframe per changed piece of UI, the states that apply | every affected screen, a states table per screen | every screen and flow |
| Contracts | inline in the task rows | a Contracts section | a Contracts section, with the files you write before wave 1 |
| Tasks | 1–3 | 3–8 | 6–10 per wave |
| Length | **about 1 page** | 2–3 pages | as needed; Rollout required |
| Questions | ≤ 2 | ≤ 4 | as needed |

Quality extras beyond the request (detailed accessibility, performance targets,
rare races) are not criteria at small size unless the user asked or the risk is
real.

## How to work

1. **Start from the source.** The user's request in `00-context.md` is the
   source of truth. If the user brought a spec or design, complete it and
   convert it to the template.
2. **Explore the code once, properly.** Read what the feature touches and the
   closest existing feature: its routing, state, data fetching, error handling,
   i18n and test style. Find helpers and components to reuse. Note the exact
   file paths workers should mirror. Workers do only a short local read, so
   whatever you don't find here they won't find either.
3. **Write the spec part**, then design only what the criteria need.
4. **Design the split** (below), then write the task board and the waves.
5. **Separate what you know, what you assume and what only the user can
   decide.**

## Acceptance criteria

- Number them AC-1, AC-2, … and never renumber. New ones get new numbers.
- Observable behavior, not implementation: "Given a cart with 2 items, when the
  user removes one, then the total shows the remaining item's price". Plain
  sentences for rules ("Coupon codes are case-insensitive").
- Cover the plausible unhappy paths: invalid input, empty data, no permission,
  network failure, limits, duplicates.
- Exact values ("up to 50 characters", "sorted by most recent"), never "fast".
- Tag **(manual)** what only a person or a real device can check.

## Design (when there is a user-facing surface)

ASCII wireframes by default. If the user gave design links a tool can read, use
them as the source.

- **Flow**: entry points, steps, exits (success, cancel, error), back and
  refresh.
- **States** for each new or changed screen, the ones that apply: default,
  loading, empty (first use vs no results), error (validation, network, server,
  permission), long or partial, success, disabled or no permission, offline or
  slow (required on mobile).
- **Components**: reuse first; name the component and its path. No colors,
  sizes or spacing outside the design system.
- **Copy**: the exact strings, in the product's voice, with i18n keys if the
  project has i18n. Workers paste them; they don't write copy.
- **Accessibility** (WCAG 2.2 AA floor) for new controls: accessible names,
  contrast with the real tokens, focus order, touch targets (44pt iOS, 48dp
  Android, 24px web), meaning not by color alone, async results announced.

No screens but an API, CLI or config? Design that surface: names, shapes, flags,
defaults, error messages. No user-facing surface? Skip Design in one line.

## Designing the split

- **Split by file ownership.** Each task owns a set of files no other task in
  its wave touches. Typical seams: a component, a hook or service, an endpoint
  handler, a migration, a test file per area.
- **Fix the contracts first.** Whatever two tasks share (a type, a function
  signature, an endpoint's request and response, component props, i18n keys,
  `data-testid`s) goes in the Contracts section, written as code. Mark which
  contract files you create yourself before wave 1. With the contracts fixed,
  a build task and the tasks that use it can run in the same wave.
- **Reserve the glue.** Shared registries (routes, index exports, DI modules,
  the i18n JSON, a nav menu) are edited by one task only, or by you after the
  wave. Name who owns each.
- **Tests in other hands.** For each build task that implements an AC, add a
  test task, owned by a different worker, that writes the tests for that AC
  from the spec and the contract. It runs in the same wave. One test task can
  cover several AC of the same area.
- **Right-size tasks.** One task is roughly what a person would do in 15–45
  minutes: 1–4 files. Smaller and the cold start dominates; larger and the cheap
  model loses the thread.
- **Bugfix track**: wave 1 is a test task that writes the failing regression
  test; you confirm it fails for the right reason; wave 2 is the fix.
- **Refactor track**: the mechanical steps per file, and "existing tests pass
  unchanged" as the done-when.
- **Order waves by real dependencies only**: a migration before the repository
  that uses it, when you can't stub it. Most features fit in one or two waves.

Write each task so a worker who has never seen the conversation can do it: what
to build, names to use, which file to mirror, the states and copy, the edge
cases, and a targeted done-when command that runs in seconds (one test file,
one package's typecheck), never the whole suite.

## Template: `01-plan.md`

````markdown
# Plan: <feature>

**Track:** feature · **Size:** medium

## Summary
<2–3 sentences: what changes, for whom, and why>

## Context
<Current behavior with file paths. The closest existing feature to mirror.>

## Acceptance criteria
- **AC-1** Given … when … then …
- **AC-2** …

## Business rules and edge cases

## Design
### Flow
### <Screen or component>
```text
┌──────────────────────────────────┐
│ ←  Pedidos              [Filtrar]│
└──────────────────────────────────┘
```
| State | What shows | Notes |
|---|---|---|

**Components:** `Button variant="secondary"` (src/components/ui/button.tsx)
### Copy
| Where / i18n key | Text |
|---|---|
### Accessibility

## Approach
<A few sentences: the approach and why over the obvious alternative. Data, API
or contract changes; migrations and how they roll back.>

## Contracts
```ts
// src/cart/types.ts (written by the orchestrator before wave 1)
export interface RemoveItemResult { items: CartItem[]; total: number }
```

## Tasks
| T | Kind | Owns (create/edit) | Mirror / read | AC | Depends on | Done when |
|---|---|---|---|---|---|---|
| T1 | build | src/cart/remove.ts | src/cart/add.ts | AC-1, AC-2 | contracts | `pnpm vitest run src/cart` |
| T2 | test | src/cart/remove.test.ts | src/cart/add.test.ts | AC-1, AC-2 | contracts | file runs; failures only where T1 isn't done |
| T3 | build | src/cart/CartRow.tsx | src/cart/CartItem.tsx | AC-3 | contracts | `pnpm tsc --noEmit -p apps/web` |

<Below the table, per task, the 3–10 lines of precise instructions that go in
the worker's prompt.>

## Waves
- **Wave 1:** T1, T2, T3 (parallel)
- **Glue (orchestrator):** register the route in src/app/routes.tsx
- **Wave 2:** …

## Non-goals
## Rollout
<Feature flag, existing data, backwards compatibility, or "none". Required at large size.>

## Assumptions
## Open questions
| # | Question | Blocking? | Options | Recommended |
|---|---|---|---|---|
````

For a bugfix, replace Context and the criteria with: Expected vs Actual, Repro
(reproduced or inferred), Impact, Suspected area, and criteria that include "an
automated regression test covers this case". For a refactor, keep it to half a
page: goal, constraints, parity criteria.

## Questions

A question is **blocking** when the answer changes what gets built and no
default is safe. It is **non-blocking** when a reasonable default exists and is
cheap to change later. Always give your recommendation; adopt it for
non-blocking ones and list it under Assumptions. Implementation details are
decisions, not questions.

## Avoid

- Tasks that say "implement the feature" or "add tests as needed". Workers need
  the what, the where and the names.
- Two tasks in one wave touching the same file.
- Leaving copy, states or names for workers to invent.
- Long documents for show: personas, market analysis, redesigns outside the
  feature.
