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

## Current handoff — 2026-09-15

**E2E-003/existing-and-new, E2E-003/none, E2E-004/app-grid and E2E-030/parent are complete.**
Progress is **4 completed, 152 remaining of the frozen 156**, with no additions
or transfers and **0 consecutive slices without a completed customer variant**.
Task 21A remains unchecked for E2E-004/terminal and E2E-031.

The registered [discovery callback](../../tests/e2e/parent_discovery.py) now owns
both finite variants. Existing-and-new retains its guarded in-app account event
and visible refresh/selection path. None pauses at the normal app grid, requires
the guarded baseline's exact three eligible standard-account fixtures, preserves
the package request station, makes only that finite set ineligible, launches
Parent and matches the visible empty explanation. Fixture identities and role
changes remain setup evidence; ordered screens alone supply customer acceptance.
The [composition contract](../../tests/e2e/README.md#parent-consumer-composition-limits),
[building blocks](E2E-Building-Blocks.md) and [reuse row](Reuse-Map.md#customer-scenario-work)
own the bounded action, refusal, matcher and cleanup limits.

E2E-003/none public acceptance `scenario-5eaf88431a4a410d8c851acc266ad172`
passed every declared phase and all four outcome domains. Case evidence is
`/tmp/onpc-e2e-evidence-ydumn7i0`, invocation evidence
`/tmp/onpc-e2e-evidence-7mu8l2oe`, worker evidence
`/tmp/onpc-e2e-evidence-cfpnrur8`, ordered matches
`/tmp/onpc-graphical-smoke-nsebkdir/testresults`, and artifacts
`/tmp/onpc-test-artifacts-ws32mits`. Passing source is
`9db43a1776e96a1eebd3a324d629e60210d1500fabd45e18da61e60ff75dcc8d`;
inventory is `16ed590ee9fd7be782625c741fddd94d7c147a5103482efde6017134e614c3d8`.
E2E-003/existing-and-new remains `scenario-117ce953fa404067aef01072bbce5b6b`;
E2E-030 remains `scenario-986d63c38497407a9d562696774c0d4d`.

Four failed acquisition runs remain retained and fully restored: the first
exposed a missing declared step-2 transition (`/tmp/onpc-e2e-evidence-z2nkqg2x`);
the second visibly exposed one unhandled baseline standard account
(`/tmp/onpc-e2e-evidence-ynz2p1qn`); the third fixed the failure at the package
request-station exclusion (`empty-account:baseline`,
`/tmp/onpc-e2e-evidence-ubaj_nv8`); the fourth acquired the genuine empty screen
before its reviewed needle existed (`/tmp/onpc-e2e-evidence-oboc3c81`). Each
subsequent attempt used new discriminating evidence and locally checked code;
none reported a product failure. Focused fixture, worker, inventory, runner,
needle and controller regressions pass, as do each run's 1,184 cleanup-safety
tests plus 3 subtests. The final run verified full baseline restoration.

**Next: E2E-004/terminal.** Reuse the qualified standard-user recipient and
installed setup. Invoke the executable through the guest terminal and observe
denial with no management window. The app-grid variant proves the intentional
absence of the administrator-only launcher; it does not exercise executable
denial. Do not add internal authorization assertions.
Post-pass documentation edits require fresh artifacts. VM is off,
temporary exports are removed, no owned operation remains, and R1 stays 0 hours /
0 attempts.

**Actual settings:** `gpt-5.6-sol` / `high`, Standard.
**Next-session settings:** `gpt-5.6-sol` / `high`; model: keep; effort: keep.
**Reason:** standard-user login and app-grid unavailability are qualified; the
terminal route needs its own complete installed customer run.
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
