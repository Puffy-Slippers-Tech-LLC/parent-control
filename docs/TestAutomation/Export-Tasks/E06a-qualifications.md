# E06a — Capture qualification and E2E collector records

Acceptance: host
Requires: E06

## Purpose and delivery

Migrate the finite standalone qualification, recovery-diagnostic and E2E collector
producer families assigned by E01, under the [master](../Export-Execution-Plan.md) and
[capture design](../Export-Design.md#capture-and-publication). Read complete
`tests/integration/qualification_storage.py`, `tests/e2e/evidence.py`, their
terminal controller/collector handoffs and registered standalone callers. Include
`qualification_storage.recovery_session()`, shared and selected-target
`recovery-diagnostics-*` journals and finalized `tests/integration/vm_probe.py`
producer records. Reuse the discovery/first-export fixes from `c8fbcd58`.

Use the shared finalized-record handoff for exact target/check/attempt records,
input manifests, original result/JUnit/TAP, commands and eventual cleanup.
Capture before source release or rotation, preserve failed/partial attempts and
keep diagnostics distinct from acceptance. Respect existing leases, privilege,
caller identity and host-versus-privileged registration; this task changes only
evidence mechanics, not VM operations, selectors, product assertions or media
policy. Deliver the assigned families in this row using shared mechanics.

## Validation and close-out

Use private collector/qualification/controller fixtures without a live guest or
product. Exercise standalone and reused sessions, two target identities,
first-use storage, success/failure/interruption, late cleanup, denied helper and
rotation after capture. Assert complete original proof bytes/dependencies and
unchanged original verdicts. Extend existing evidence/qualification-storage
tests including `test_recovery_diagnostic_samples_survive_rotation`,
`test_catalogue_includes_only_selected_targets_host_and_guest_journals` and
`test_host_only_catalogue_without_privileged_storage`. Cover shared/selected-target
diagnostic capture, first export, absent optional storage versus denied access,
and required diagnostic proof surviving later report rotation. Denied access stays
a refusal; diagnostics remain nonpassing. Extend applicable safety tests, review
resource-affecting changes and run maintained scoped host checks. Update their
owning contracts and use the master's close-out.

Use actual private producer/session call chains for all diagnostic families in
the design inventory. Preserve baseline_guest's 16-KiB tail, native-log
availability and true cleanup scope for deliberately live maintenance scenes;
later recovery is a distinct linked record. Exclude transport credentials.
For E2E, capture the outer authoritative post-cleanup ledger with the immutable
candidate digest. Retain collector sync-before-registration, exact-list,
unregistered-file, tampering and first-failure controls. Required media needs a
verified captured copy or its existing explicitly bounded owner lifetime.
