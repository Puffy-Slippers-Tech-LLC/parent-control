# 004b — Trusted unlock sender and eligibility

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract sender and native admission decisions from 004a. Read the
[unlock contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
`child/sessionUnlock.js`, `sessionDiagnostics.js`, lifecycle callers and
`tests/child/session_unlock.test.mjs`. Reuse canonical fake native objects and
clocks. 004a retains authority lifetime/consumption; 004 retains native usability.

## Work sequence

1. Map current assertions and add missing trusted-current-owner versus foreign,
   absent or replaced-sender controls. Names, grants and positive estimates
   alone never authorize an unlock.
2. Pair eligible parental exhaustion with ordinary/native unlocking, non-parental
   locks, greeter, sleep and disabled-limit controls. Only the appropriate trusted
   Unlock may arm recovery; untrusted Lock cannot cancel trusted authority.
3. Recheck dispatch admission against the current owner, active session and
   verified finite future native deadline. A lagging per-session IdleHint must
   not override the native aggregate activity decision. Assert independent
   native-call counts and lock-state results, not diagnostic callbacks.
4. Run exact affected child-node/GJS authority/adapter selections through
   `tools/run-tests`, with explicit timeouts; repair demonstrated decision defects.

## Acceptance and close-out

Retain accepted/refused controls, actual passing selections and owned-source
cleanup. Preserve the public native authority boundary; no private Shell edits
or unlock/relock workaround. Review resources and follow master build/evidence
rules. Close only 004b; expiry, one-use consumption and lifecycle cancellation
remain in 004a, and both installed targets remain required in 004.
