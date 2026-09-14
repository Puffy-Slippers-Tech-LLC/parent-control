# Task 22 — Customer time limits, login and countdown

Follow [E2E-Coverage.md](E2E-Coverage.md). Correct-password rejection with the
time-limit message and no usable desktop is sufficient customer evidence.
Do not inspect PAM, logind, usage/grants, extension state, filters, rules,
processes or broker reconciliation. Existing tests of those internals remain intact.

## Implementation slices

Select this task in the broad customer queue. Complete one assigned time-limit
variant, then expand natural expiry and restored-access variants.
Reuse the smallest real Parent/kiosk interaction needed; Tasks 15–17 and the
whole Parent/request matrices are not dependencies.

## Task 22A

- Title: Zero-time rejection, natural expiry and restored access.
- Depends on: accepted guarded graphical runner and verified package/account setup.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-008/009/010.
- Work:
  1. For `E2E-008/fresh-login`, parent opens Parent and sets zero allowance,
     observes save, switches users, and attempts child login with the correct
     password. Observe the time-limit explanation and no desktop access.
     Reconcile this pending variant as configured zero-time denial; do not claim
     that setting zero also proves natural exhaustion.
  2. For `E2E-008/retained-unlock`, select a short supported allowance, log in
     and use the child desktop until time naturally runs out. Observe lock;
     correct-password unlock shows the time-limit rejection.
  3. For E2E-009, obtain time through real kiosk selection and authentication,
     log in, use the app and let the grant expire. Obtain replacement time and
     unlock normally. Cover soft apps included/excluded through actual launch
     results. The successful login/unlock provides the positive access control.
  4. For E2E-010, switch to the parent or another child while the selected
     child's time expires. Continue using that foreground desktop, then try to
     return to the expired child and observe rejection.
  5. If retained app state is claimed, obtain legitimate time and observe the
     same window/activity after normal unlock. No invisible process-survival or
     internal event-order assertion is required.
- Verification: execute complete variants through the existing guarded E2E
  selector, inspect visible results and retain normal evidence/cleanup.
  Run existing safety prerequisites and affected regression checks; run common
  acceptance checks once after the stable batch.
- Completion criteria: the finite fresh-login, natural-lock, replacement-access
  and other-user journeys pass by customer observation.
- Separate work: `E2E-028/zero-time-exposure` uses a forced internal operation
  and is outside this task. Preserve it as deferred system qualification.

## Current handoff — 2026-09-14

Customer variants remain pending. The [current continuation](Continuation.md)
starts the general customer queue with Parent discovery. Time-limit rejection
is one illustration of surface-only acceptance, not a priority over other
families. Reuse the common graphical/evidence adaptation when this task is
selected and reconcile only its affected legacy declarations. Preserve actual
natural-expiry steps where claimed; configured zero alone does not prove them.

## Task 22B

- Title: Countdown display and visibility.
- Depends on: only the real login/request interactions needed to show time.
- Default settings: `gpt-5.6-sol` / `high`, lowered for settled UI expansion.
- Customer scope: E2E-011.
- Work:
  1. Obtain a duration long enough to observe minutes and final seconds.
     Watch the countdown during real use; do not change clocks or read usage.
  2. Observe the control on the unlocked managed desktop and its absence on
     lock/GDM and inappropriate user surfaces. Use ordinary customer transitions.
  3. Reopen/return through normal interactions and observe display refresh.
     Do not stop Malcontent or inject read failures.
- Verification/completion: all declared visible display variants pass using
  bounded screen waits, normal evidence/cleanup and affected regressions.
  `E2E-028/usage-read` stays separate internal fault qualification.
