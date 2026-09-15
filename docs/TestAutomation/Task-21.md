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

**E2E-030/parent is complete and passed public customer acceptance.** Progress:
**1 completed**, **155 remaining of the frozen 156**, no transfers or
scope additions; **0 consecutive slices without a completed customer variant**.
The supervised intervention resolved the session-100 repair decision and earned
the first complete customer variant. Task 21A remains unchecked for its other
variants. The launcher summary and saved blocked status describe session 100;
this handoff supersedes that blocker after the supervised pass.

The registered [Parent callback](../../tests/e2e/parent_about.py) logs in through
the installed Parent prompt, launches from the app grid, selects the existing
fixture child, reads About/version and the installed GPL license, closes the
viewer, reads the copyright/footer, closes About and returns to that same child
with unchanged displayed settings. All 18 positive matches passed at 100%;
negative recipient checks precede unchanged secret input. Setup and customer
actions retain separate recorded phases. Boot continuity, source/package
identities and outer cleanup passed; no backend product probe supplies acceptance.
The requirement is `ONPC-CORE-ABOUT-001`, with surface-only evidence.

The [composition contract](../../tests/e2e/README.md#parent-consumer-composition-limits)
and [building-block guide](E2E-Building-Blocks.md) own the reusable boundaries
and lessons. New consumers compose `InstalledJourney`/`record_installed_journey`,
`onpc_pointer`, `onpc_journey` and the Parent login/launch/selection operations.
The About modules retain scenario-specific expectations. The
[reuse row](Reuse-Map.md#customer-scenario-work) selects the next consumer.
Qualification review mode cannot supply acceptance or bypass recipient/click checks.
The shared composition passed the public `--ready` invocation with E2E-001 and
E2E-030/parent; this refactor adds no customer variant or scope credit.

**Evidence needed for continuation:**

- Public invocation: `/tmp/onpc-e2e-evidence-3esteq9z/invocation-terminal-candidate.json`.
  Selector `--ready`; E2E-001 and E2E-030/parent passed, dispatcher exited 0.
  Partial scope explicitly retains 155 pending exclusions. Parent run
  `scenario-986d63c38497407a9d562696774c0d4d` passed product, infrastructure,
  collection and cleanup with no first failure.
- Accepted Parent record and final phases/preservation:
  `/tmp/onpc-e2e-evidence-pj3urxa2/acceptance.json`.
  Raw matches/screens: `/tmp/onpc-graphical-smoke-6ehyth8a/testresults/`.
  Worker cleanup: `/tmp/onpc-e2e-evidence-t2pybly1/worker-result.json`.
- Passing inputs: `/tmp/onpc-test-artifacts-deuc055i`, source
  `e98b18f77e8836d3ce4184b2d5997c67324e9ef332df0422ddd634efb56396b5`,
  inventory `33a1025063f9a5fb2fcba678d6d17aec97791f617961ecb1635220e8a12e020e`.
  Coverage/handoff metadata changed afterward; build fresh artifacts for future
  VM runs. Original qualification reports, private captures and build inputs remain.
- `make check` passed: 9,103 unit tests, 139 component tests, and 1,182 isolated
  cleanup-safety tests plus 3 subtests. The public E2E invocation independently
  passed its safety prerequisites and full baseline restoration.

**Next bounded consumer: E2E-003/existing-and-new.** Reuse the now-proven
installed login, launch and selected-child observations. Complete the scoped
bridge to the existing account fixture while Parent stays open, reconcile the
fixture-event declaration, and prove that the new child appears and both
children can be selected with their displayed settings. Do not repeat E2E-030
acquisition or postpone this consumer for unrelated internal designs.

Other retained boundaries: E2E-003/none needs an empty-account fixture and its
visible empty state. E2E-004/app-grid and /terminal need a qualified standard-user
recipient and their normal launch/refusal interactions; no denial is yet proven.
Later customer work remains in its owning handoffs. No earlier task is marked
complete by this pass.

**Cleanup complete:** VM off, accepted baseline fully restored, owned worker and
callback stopped, host/source preserved; no owned operation remains. All-task VM
authorization persists. R1 remains 0 charged hours / 0 new attempts because its
execution-source/validation-lifetime recovery was unchanged.

**Actual settings:** `gpt-6-astra` / `high`, Standard.
**Next-session settings:** `gpt-5.6-sol` / `high`; model: lower; effort: keep.
**Reason:** installed input, pointer mapping and the complete evidence path are
now qualified. Use the settled helpers for the next consumer; reassess to Astra
if its new fixture bridge exposes unresolved ownership or concurrency questions.
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
