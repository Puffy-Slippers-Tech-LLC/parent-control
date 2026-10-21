# F11 — Decouple Ubuntu snapshots from fixture payloads

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F28

## Purpose and scope

Deliver Ubuntu's [snapshot/dependency split](../Fixture-Design.md#runner-and-snapshot-migration).
New snapshots contain environment dependencies and the installed product where
appropriate, with movable fixture payloads excluded. Ordinary new-schema dispatch
stays disabled until F34–F40 and F48 complete; this task does not enable cutover.

## Read and implement

Read F01's complete digest/capture/recovery map, `prepare_vm.SCRIPT_FILES` /
`preparation_digest`, `baseline_guest.prepare`, `prepare_baseline.inspect_guest`,
`baseline_fixtures.verify`, `tests/e2e/app_snapshot.py`, `prepare_snapshot.py`,
`tests/integration/online_snapshot.py`, `tools/prepare_appsnapshot.py`,
`artifact_inputs.py`, `e2e_startup_cache.py` and affected baseline/snapshot tests.
Separate dependency/provisioning ABI from fixture-only changes without dropping
actual product/shared-file dependency tracking. Remove movable fixture compilation
from new baseline preparation; verify clean capture and no pending transaction.
Use F24/F30's version-dispatched [legacy matrix](../Fixture-Design.md#legacy-recovery-compatibility)
and F33's complete movable-set/source-copy retirement.
Preserve original-schema legacy recovery rather than making old owners impossible
to stop/restore. Update mandate/approval/environment owners for the delivered
Ubuntu boundary, keeping Fedora migration explicit until F12.

## Finite validation and cleanup

Run isolated baseline/capture/recovery safety checks first. A separately invoked,
authorized auto-mode baseline/app refresh may establish this new schema; record
it distinctly from sync. Through registered engineering bindings prove clean
baseline/app capture, restore plus minimum dynamic provisioning, old-schema
stop/restoration after current fixture/dependency source changes, legacy recovery
and a subsequent fixture-only A→B host edit/use in fresh attempts without changed
baseline/app snapshot identity. F07 separately owns same-boot live refresh after
this dependency split is delivered. Dependency ABI and real product changes still
invalidate their own caches. Prove standalone app preparation needs no movable
fixtures and no consumer silently uses an embedded fallback. Audit archived
`onpc-system-input-snapshot-*`, E2E asset, native trust/barrier and retained
baseline-preparation checkout locations too; renaming a payload cannot pass clean
capture. Require the initial both-target integration matrix before schema
preparation, then register the fixed engineering qualification route for all
seven clean Ubuntu rows. Ordinary dispatch must refuse without the matching F48
receipt. F34–F40 repeat readiness/use/refusal/cleanup through each actual envelope
on these clean snapshots before F48 enables it. Preserve stale-acquisition refusal
for legacy snapshots while original accepted cleanup remains usable. Complete owned
restoration/pin cleanup and close through the [master](../Fixture-Execution-Plan.md).
