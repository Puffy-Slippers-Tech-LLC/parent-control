# D00 — Audit the confinement replacement and cleanup boundary

Acceptance: review

Required tasks: Baseline (repository/source baseline; installed C05 gate is at D01).
Estimate: 20–30 min.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract)
and [retained-run admission](../Kiosk-Desktop-Plan.md#retained-run-admission).

## Session boundary and deliverable

Read the selected C02 baseline and C01–C04 source/test dispositions in the
[confinement design](../SystemDesign/Kiosk-Confinement.md#c01-selective-replacement-boundary).
Verify the pinned v1.3 session-confinement lineage against the current candidate,
including relevant staged, unstaged and untracked old-plan work. Preserve main's
feature/approval/product code and all unrelated work. Never reconstruct the
baseline by subtracting main/v1.4 restrictions or restoring whole release files.

In that existing design owner, record only residual conflicts, exact source and
consumer paths, preserved behavior, disposal rationale and focused validation.
Assign source/package/lifecycle residuals to D00a and obsolete automation
consumers to D00b. Verify already delivered cleanup rather than replay it.
An empty residual map is a valid review result with inspectable source evidence.
Include affected admission/refusal/exception paths under the master's usability
stop gate; identify normal missing/stale-state, contention and configuration
failures that lack a concrete deliberate breach justification. Those are product
availability defects to correct, not accepted confinement results.
Apply the master's narrow denylist to each refusal/default/error branch: map the
exact attack predicate or its removal/recovery owner, plus a benign adjacent or
unknown configuration that must preserve passwordless app access. Failed discovery,
missing state and parse/lock errors alone supply no intentional-attack evidence.

This is source review, without implementation or installed acceptance. Do not
wait for C05 merely to inspect residual source; do respect any active baseline
editor, owner or Git transaction. An overlap keeps this row open with its owner
and return condition. Check links and both launcher metadata routes. No VM or
artifact allocation is needed.
