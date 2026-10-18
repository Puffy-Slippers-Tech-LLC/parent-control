# 004 — Single-authentication retained unlock recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 45–75 minutes.

## Session boundary

Deliver the complete installed exhaustion/approval/single-authentication return.
004a supplies deterministic authority-ordering regressions. Session exception:
splitting exhaustion from approval or return would lose the stale native state
and retained-work result; the whole history remains required on both targets.

## Purpose and route

Required tasks: 003, 004a.
Read the [master](../Reliability-Plan.md), the
[unlock continuation contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
`child/sessionUnlock.js`, `sessionDiagnostics.js`, extension lifecycle callers
and `tests/child/session_unlock.test.mjs`. Reuse the existing retained-unlock,
approved-return and natural-expiry helpers and public credential guards.

Planned qualification (unimplemented):
`check_e2e_exhausted_retained_unlock_recovery` under the existing retained-unlock
owner. It adds the stale-native-state boundary; existing customer approved-entry
and exhaustion cases retain their own scope and queue positions.

## Finite history and expected results

In a renewed real child session with a public two-minute daily-only profile and
observed zero initial grant, use the allowance until native exhaustion locks
the retained desktop. Obtain one real parent-approved additional 120 seconds
through the kiosk while locked; verify the resulting original grant deadline.
Submit the child's credential once to the verified native challenge. Independently
observe the original usable desktop and unchanged work within the existing
bounded return deadline; a second authentication must not rescue the test.
A native restriction without a challenge is a behavior mismatch to investigate,
not permission to manufacture a password prompt.

Positive estimates/grants alone must never unlock. Reuse 004a's host
authority-ordering coverage, extending it only for a newly demonstrated defect.
The original trusted Unlock may continue once within its monotonic lifetime;
after native handoff,
observe actual lock state rather than claiming asynchronous callbacks cancelled.
Demonstrate a fresh normal lock still requires its own authorized return and
that grant expiry still enforces without affecting the other child.

## Validation and close-out

Run affected host/GJS authority, cancellation and diagnostic tests first, then
the complete installed natural-exhaustion/approval/single-authentication return
on both targets. Keep first-failure evidence and ordinary authentication
negative controls. Fix root causes within the native authority boundary; do not
mutate private Shell state or add an unlock/relock workaround.
Build after product edits and retain renewed-session provenance, actual public
results and cleanup. Update the design's installed-validation limit only for
the exact qualified scope; leave customer E2E rows unchanged.
