# Task 26 — Complete customer journeys, recovery and persistence

Follow [E2E-Coverage.md](E2E-Coverage.md). Customer E2E can do only what a
customer can do and observe. No daemon control, private-state mutation, fault
injection or backend observation is part of acceptance. Existing lower-level
and installation fault tests retain their own scope.

## Implementation slices

Use accepted graphical input and supported setup. Complete one named journey
before expanding; do not require all earlier matrices or internal helper
qualification. A continuous journey must actually run from start to finish;
separately passing fragments cannot establish it.

## Task 26A

- Title: Remaining customer cancellation and retry gaps.
- Depends on: the real form/app interactions required by a selected gap.
- Default settings: `gpt-5.6-sol` / `high`.
- Work:
  1. Review existing customer cancellation, rejected authentication, invalid
     input, close/reopen and retry cases in Tasks 21/23/24. Reuse their canonical
     executions instead of building another failure matrix.
  2. Implement only a missing distinct customer path, such as closing a request
     before completion, reopening it and submitting normally. Observe choices,
     messages, access and recovery through the app.
  3. Reconcile E2E-029 declarations: keep customer-reproducible operations;
     transfer induced internal faults to the separate engineering list below.
     No transfer or duplicate removal earns a passing scenario.
- Verification/completion: every identified customer recovery path has one
  complete canonical execution and visible outcome. If existing cases cover
  the entire visible scope, close the mapping with their evidence and report
  zero newly completed variants; do not invent failures to create work.

## Separate engineering obligations

Preserve all existing tests and historical evidence. The following unfinished
internal work is outside the customer queue and requires separate engineering
direction, except Task 20's installation faults:

| Former obligation | Retained owner |
| --- | --- |
| Policy reload/rollback, partial termination, exact process confinement | [Task 15](Task-15.md), with [acknowledgement design](Policy-Acknowledgement.md) separate. |
| Usage-reader faults, forced zero-time desktop exposure, PAM/session internals | [Task 16](Task-16.md). |
| Stale identity, transaction contention, requester disconnect, precise grant commits | [Task 17](Task-17.md). |
| Kiosk authentication-agent stop/restart and non-installation service recovery | Deferred system qualification; existing controls/regressions retained. |
| Injected feedback transport/provider failures | Separate adapter/service integration; existing local tests retained. |
| Startup enforcement/broker failures | Required mechanical [Task 20](Task-20.md) qualification. |

A demonstrated visible failure blocks its customer case and is recorded with
actual steps/results. An E2E worker must not follow this table into a design
investigation. Continue independent customer cases or stop for a repair decision.

## Task 26B

- Title: Reopen, login, reboot and resumed use.
- Depends on: only the configuration/request interactions needed by the case.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-022.
- Work:
  1. Configure through Parent or request time through a real approval. Close
     and reopen Parent/request surfaces; observe displayed choices and access.
  2. Log out/in or use Switch User normally. Observe per-child choices,
     countdown and actual allowed/blocked app use.
  3. Reboot through the desktop and resume use. Exercise supported idle and
     suspend/wake through normal interfaces where required. Observe resumed
     screens, app interaction and remaining-time behavior.
  4. Observe separate mute choices on both request surfaces. Verify retained
     windows by viewing them after legitimate unlock, not through process reads.
- Verification/completion: each finite customer restart/resume path passes with
  visible evidence. Do not stop the broker/package services, inspect stored
  data, extension publication or backend grants, or require internal continuity
  witnesses beyond the unchanged runner's own safeguards.

## Task 26C

- Title: Complete everyday journeys and authorized feedback.
- Depends on: the minimal Parent/login/kiosk/game interactions needed per case.
  Full Tasks 15–18, 20 or 26A/B acceptance is not a dependency.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-023/024/025/032 and customer-reproducible E2E-033.
- Work:
  1. Execute [E2E-023](E2E-Coverage.md#required-continuous-example-e2e-023):
     Parent sets zero → Switch User → correct-password child rejection →
     kiosk approval → child login → real gameplay → natural expiry → lock
     and correct-password unlock rejection. Complete windowed and fullscreen
     variants with a prepared real offline game. Menu-only or sleeping fixtures
     do not prove gameplay; game correctness itself is outside scope.
  2. Execute E2E-024: request additional time during real use, authenticate,
     observe confirmation/countdown, continue playing and eventually expire.
  3. Execute E2E-025: after expiry, obtain replacement time with each soft-app
     choice before returning to the desktop; observe access and app behavior.
     Do not inspect session-entry reconciliation, policy or grants.
  4. With explicit external-sending authorization and a dedicated test recipient,
     use Parent to submit feedback and observe its response (E2E-032).
     Test a distinct customer-reproducible error/retry path if available.
     Do not send to routine support, probe delivery internals or inject
     transport faults. Visible success proves the app's reported result, not
     recipient receipt. Missing authorization blocks only those sending cases.
  5. Register/reconcile the finite surface-only variants, retain safe screen/step
     evidence and report actual completions and remaining gaps. No backend
     proof or general coverage-framework project is part of this task.
- Verification/completion: each assigned complete customer journey passes.
  Use existing safety checks and affected regressions. Preserve failed attempts;
  repeated helper qualification is not a substitute for finished journeys.

## Customer package journeys and mechanical qualification

E2E-026/027 remain required continuous customer journeys, owned with
[18A/18C](Task-18.md) after the prioritized everyday customer work. They use
actual customer package operations, reboot/login and visible saved choices.
Task 18 separately verifies activation, migration, ownership and cleanup
internals; those checks remain necessary and are not customer assertions.
Task 20 similarly retains its clean-install surface and mechanical qualification.
A shared attempt may provide both kinds of evidence with separate acceptance.
