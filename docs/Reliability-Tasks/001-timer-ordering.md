# 001 — Timer failure ordering and accounting safety

Acceptance: host

## Purpose and implementation

Follow the [master](../Reliability-Plan.md) and
[screen-time design](../SystemDesign/Screen-Time.md). Read the complete timer
helper, `TimerUsage`, `timerQuery.js`, `resumeEstimateRefresh.js`, their callers
and existing tests before editing. Existing `5b15f17d` regressions remain the
baseline; add missing histories rather than restating their implementation.

Use the existing fake clocks and explicit error/callback adapters in
`tests/unit/test_usage_query_retry.py`, `test_adapters.py`,
`tests/child/timer_query.test.mjs` and `resume_estimate_refresh.test.mjs`.
Cover these finite compositions where not already present:

1. Busy → owner loss → timeout/success, and mixed terminal failures sharing the
   original budget; delayed wake after budget expiry dispatches no new call.
2. Three same-stage resume failures separated by successful idle/estimate reads;
   successful recovery of the relevant operation rearms one future incident.
3. Inactivity/resume/disable/close while query or replay is pending, including
   cancellation immediately before dispatch and reply after cancellation.
4. No native deadline, a finite active deadline and a permanent refusal require
   their distinct reporting/recovery behavior; unknown Busy names stay errors.

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
