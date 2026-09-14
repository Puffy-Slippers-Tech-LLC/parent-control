# Task 21 — Parent customer journeys

Follow [E2E-Coverage.md](E2E-Coverage.md). All acceptance uses real customer
actions and visible results. Existing lower-level regressions stay unchanged;
backend account/catalog, D-Bus, grant, rule and private-state assertions are
not part of these journeys.

## Implementation slices

Complete one named variant before expanding. Use accepted installation/account
setup, graphical input and cleanup. A helper from another task may be used or
minimally completed with this consumer; that task's full matrix is not a dependency.
Use [the workflow](Implementation-Workflow.md) for bounded work and progress.

## Task 21A

- Title: Parent discovery, navigation, access and feedback drafting.
- Depends on: accepted graphical runner and verified installed-package setup.
- Default settings: `gpt-5.6-sol` / `high`; reassess ordinary expansion.
- Customer scope: E2E-003/004/030/031. E2E-005 saves belong to 21B.
- Work:
  1. Log in as a parent, launch Parent from the app grid, discover and select
     eligible children. Observe loading, selection and independent displayed
     settings. For dynamic discovery, use the supported account fixture while
     Parent stays open and observe the new child appear.
  2. Use allowance controls, app search/filter, displayed rules and matching
     choices. Cover representative valid/invalid boundaries and visible
     explanations. Do not expand already-tested local validation matrices.
  3. Log in as a standard user and try the normal Parent launcher. Observe
     management is unavailable. Direct broker attacks remain separate tests.
  4. Open About/license, compose feedback, review synthetic attachments and
     cancel. Check visible validation and retained/cleared drafts as specified.
     No external message is sent in this task.
- Verification: run the assigned complete variants through the guarded E2E
  selector, inspect safe screens/step results, and run affected regressions
  plus existing safety prerequisites. Use `make check` and scoped whitespace
  checks once at stable task acceptance, not after every UI step.
- Completion criteria: the listed visible flows pass on the installed app.
  Correct the pending E2E-003 fixture-event declaration with its first consumer.
  E2E-005 ownership now matches 21B; registration or reclassification earns no
  scenario credit.

## Current handoff — 2026-09-14

First customer result: complete `E2E-003/existing-and-new`. Log in as the
parent, open Parent, observe/select existing eligible children, provision the
declared new account through accepted fixture setup, and observe its discovery
without restarting Parent. Do not inspect the catalog or broker to assert the
result. This starts the broad customer queue; timeout/login is only another
family, not a privileged priority.

Reconcile this pending declaration and only the minimum common evidence-gate
adaptation needed to accept visible assertions without backend product
witnesses. Preserve existing VM, provenance, secret-input and cleanup guards.
No new collector or general framework is required by the plan. The adapter
alone earns no completed customer variant; its consumer is this same journey.

Baseline: 0 completed customer variants; selected finish line 1 complete
discovery journey; consecutive implementation slices without a completed
customer variant since this scope rewrite 0. No implementation or runtime
acceptance occurred in this documentation session. Record executed steps,
remaining frozen scope, actual blockers and evidence here at the next handoff.
Use the workflow's two-slice intervention rule for stalled completion.

Next settings: `gpt-5.6-sol` / `high`, Standard, for a bounded visible journey.
Reconcile actual runner/lease ownership before execution; historical cleanup
is not current machine-state evidence.

## Task 21B

- Title: Parent saves, control changes and revocation.
- Depends on: only the Parent/login/approval interactions needed by its selected
  variant; no Task 15B, 16B or policy-acknowledgement prerequisite.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-005/006/007; share canonical app-use cases with Task 25.
- Work:
  1. Set zero/positive allowance and enable/disable control in Parent. Observe
     saving, reopen the settings, and attempt child login/use to see the result.
  2. Change allowed/hard/soft app choices and supported matching options.
     Attempt actual child launches; observe the intended window or denial.
     Switch to another user and use their app where isolation is claimed.
  3. Establish time through a real request/authentication when needed. Cancel
     revocation, then confirm it in a separate declared path. Observe displayed
     time, child access and app-window effects required by the product.
  4. Check visible loading/disabled controls and ordinary cancellation/retry.
     Do not induce service/reload/termination faults or inspect transaction state.
     A real failed save remains a failed scenario with a separate product blocker.
- Verification: complete each selected UI-to-child-use journey, retain visible
  evidence and existing cleanup results, then affected regressions and stable
  task acceptance checks.
- Completion criteria: saved choices and revocation have the documented visible
  effect for the selected child, with customer-observed isolation where assigned.
  No internal atomicity, activation receipt or rollback-readback claim is made.
