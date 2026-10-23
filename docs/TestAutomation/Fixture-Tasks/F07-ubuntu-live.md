# F07 — Refresh an idle owned Ubuntu VM

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F28

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Add explicit [idle maintenance refresh](../Fixture-Design.md#live-refresh-and-recorded-attempts)
to `tools/test-vm`. Read the complete VM-control/online-snapshot ownership,
session, process and transport paths and the shared provisioner. Use existing
authenticated input handoff, watch and maintenance owner. Register validated
options/help; this surface is unimplemented until then.

Before mutation prove the existing idle boundary excludes fixture workers,
fixture-using graphical sessions and other launchers. Busy, foreign or uncertain
ownership refuses; do not add a supervisor, process scan or launch barrier.
Implement the design's explicit maintenance replacement operation over F15's
shared mechanics. Verify retained A and same-subset B before writes, invalidate
old readiness and publish a new diagnostic generation only after verification.
Keep ordinary attempt provisioning immutable; its restore-only reset is not a
refresh API. Failure makes maintenance unavailable until normal owned
recovery, without promising same-boot rollback or repairing an active scenario.

## Acceptance and cleanup

Run affected maintenance/provisioning safety tests first. Register/list
`check_fixture_live_refresh`. In an idle watched Ubuntu maintenance instance,
use A, change/build B on the host, explicitly sync and independently use B.
Require unchanged boot/domain and baseline/app snapshot identities, correct native
activation, unrelated state preservation and repeated verification without writes.
Prove busy/session/worker, different-subset, corrupt-input and foreign-owner
refusal before writes. Inject interruption/lost reply and verify unavailable
readiness plus owned recovery. Finish all input/staging/maintenance cleanup.

Follow the [master](../Fixture-Execution-Plan.md) for reading, resource review,
owned cleanup and ordinary evidence/Git close-out.
