# 004a — Trusted unlock authority lifetime

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: 004b.
Estimate: 15–30 minutes.

## Session boundary

Deliver one-use authority lifetime and consumption after an eligible trusted
request. 004b supplies sender/eligibility and native dispatch admission controls.
This row retains their cumulative scope; add no second eligibility matrix.

## Deliverable and route

Extract deterministic authority-ordering coverage from original 004.
Read the [unlock continuation contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
`child/sessionUnlock.js`, `sessionDiagnostics.js`, lifecycle callers and
`tests/child/session_unlock.test.mjs`. Reuse fake monotonic clocks and existing
native-adapter callbacks; add only missing compositions.

## Work sequence

1. Use 004b's eligible trusted request, then delay dispatch past its original
   monotonic lifetime. Expiry is rechecked even before a late timeout runs;
   a newer trusted Unlock starts only its own lifetime.
2. Cancel pending authority through owner replacement, Lock/suspend, session
   departure, limit disable/close and renewed exhaustion. Late idle/timeout
   callbacks stay inert and release their owned sources/connections.
3. Observe native unlock or animation, then direct relock without logind Lock.
   Authority is consumed before relock and can continue at most once. A returned
   native call is not successful unlock; observe actual public lock state.
4. After native handoff, distinguish observed interruption from cancellation:
   no native callback can be claimed cancelled without a cancellation handle.
   Reuse 004b's admission controls, rerunning affected ones if shared inputs change.

Positive estimates/grants alone never arm a return. Retain the narrow regression
for a reporter that throws: it cannot change authority or native dispatch. Broader
diagnostic isolation/privacy compositions belong to 010c and are not a
prerequisite for this row.

## Acceptance and close-out

Run exact affected child-node/GJS authority, cancellation and diagnostic files
through `tools/run-tests`, with explicit timeouts. Assert native dispatch counts,
remaining authority and independent lock-state outcomes. Fix demonstrated
defects without private Shell edits or unlock/relock workarounds; review resources
and follow master build/cleanup/evidence rules. Close only 004a. Native
single-authentication usability still requires 004 on both targets.
