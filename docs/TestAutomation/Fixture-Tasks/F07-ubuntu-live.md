# F07 — Refresh an idle owned Ubuntu VM

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F28

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Add explicit [idle maintenance refresh](../Fixture-Design.md#live-refresh-and-recorded-attempts)
to `tools/test-vm`. Read complete affected functions and necessary VM-control,
maintenance-owner, session/process and shared-provisioner callers. Use existing
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

Run focused maintenance/provisioning safety tests. Register/list
`check_fixture_live_refresh`. In an idle watched Ubuntu maintenance instance,
use A, change/build B on the host, explicitly sync and independently use B.
Require unchanged boot/domain and baseline/app snapshot identities, correct native
activation, unrelated state preservation and repeated verification without writes.
Prove busy/session/worker, different-subset, corrupt-input and foreign-owner
refusal before writes with direct host checks of the maintenance boundary.
Run one live interrupted/lost-reply replacement to verify unavailable readiness
plus owned recovery; reuse shared staging/transport fault coverage for other
injection points. Add a live refusal only where guest state cannot be represented
by those host checks. Follow the design's [validation rule](../Fixture-Design.md#validation-reuse-and-invalidation).
Do not extend refresh to active scenarios or add product UI/policy acceptance.
Finish all input/staging/maintenance cleanup.

Follow the [master](../Fixture-Execution-Plan.md) for reading, resource review,
owned cleanup and ordinary evidence/Git close-out.
