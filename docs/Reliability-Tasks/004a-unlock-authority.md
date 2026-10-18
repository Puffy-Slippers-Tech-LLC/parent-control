# 004a — Trusted unlock authority lifetime

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract deterministic authority-ordering coverage from original 004.
Read the [unlock continuation contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
`child/sessionUnlock.js`, `sessionDiagnostics.js`, lifecycle callers and
`tests/child/session_unlock.test.mjs`. Reuse fake monotonic clocks and existing
native-adapter callbacks; add only missing compositions.

Positive estimates/grants cannot arm a return. Only the current trusted
owner/session's authorized Unlock can continue once inside its original
monotonic lifetime. Check owner replacement, Lock/suspend, direct relock without
a logind Lock, session departure, limit disable/close, late idle/timeout
callbacks and renewed exhaustion. Delayed dispatch rechecks expiry. Native
unlock/animation consumes pending authority before relock; a newer trusted
Unlock has its own lifetime. After native handoff, public lock-state observation
owns success; callbacks cannot be claimed cancelled without a native cancellation
handle. Reporter failures must not change the authority decision.

## Acceptance and close-out

Run exact affected child-node/GJS authority, cancellation and diagnostic files
through `tools/run-tests`, with explicit timeouts. Assert native dispatch counts,
remaining authority and independent lock-state outcomes. Fix demonstrated
defects without private Shell edits or unlock/relock workarounds; review resources
and follow master build/cleanup/evidence rules. Close only 004a. Native
single-authentication usability still requires 004 on both targets.
