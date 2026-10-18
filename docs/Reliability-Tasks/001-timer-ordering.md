# 001 — Timer failure ordering and accounting safety

Acceptance: host

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: 001a, 001b, 001c.
Estimate: 15–30 minutes.

## Session boundary

Deliver the resume controller's operation-specific incident recovery.
001a supplies broker-query budgets; 001b supplies child-query budgets and query
cancellation; 001c supplies controller query/replay cancellation across lifecycle
changes. Reuse those regressions; this row's cumulative scope includes them
without reimplementing either retry engine or the cancellation matrix.

## Purpose and implementation

Follow the [master](../Reliability-Plan.md) and
[screen-time design](../SystemDesign/Screen-Time.md). Read the complete timer
controller in `resumeEstimateRefresh.js`, its `TimerUsage` adapter, callers
and existing tests before editing. Existing `5b15f17d` and `9162f12d` regressions
remain the baseline, including corrected daemon Busy names; add missing histories
rather than restating their implementation. This slice targets repeated
resume-stage failure hidden by successful independent estimate reads.

Use the existing fake clocks and explicit error/callback adapters in
`tests/child/resume_estimate_refresh.test.mjs` and relevant adapter tests.
Cover these finite compositions where not already present:

1. Three same-stage resume failures separated by successful idle/estimate reads;
   successful recovery of the relevant operation rearms one future incident.
2. No native deadline, a finite active deadline and a permanent refusal require
   their distinct reporting/recovery behavior; unknown Busy names stay errors.

Use 001c's maintained cancellation operations when composing these histories;
rerun an affected lifecycle branch if this slice changes its inputs or behavior.

Fix demonstrated product defects at their owning boundary. Do not expand the
transient allowlist, replay usage during continuous activity, reset a failing
operation's incident from an unrelated success or interpret a failed read as
zero use. Keep diagnostics isolated from the operation they describe.

## Validation and close-out

Run the exact affected unit and child-node/GJS files through `tools/run-tests`,
preserving explicit timeouts. Include real Gio error classification for changed
classifiers. Assert fixed attempt/budget limits, preserved prior estimates,
identical replay endpoints, cancellation and original terminal category with
privacy canaries. Review host resource inventories if ownership changes.

Read-only source/test review alone cannot close this host task. Retain the
actual passing selections and failure/fix details in existing runner artifacts.
Build after product/build-input edits, update owning design if needed, check
links and close only this row. Task 002 owns native service qualification.
