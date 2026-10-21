# F30 — Preserve snapshot and VM-owner recovery codecs

Acceptance: host
Requires: F24

## Scope and implementation

Implement the remaining [legacy matrix](../Fixture-Design.md#legacy-recovery-compatibility)
using F24's original-proof sidecar. Read complete app snapshot schemas 1/2,
online/maintenance SSH private records, Lease._recover_recorded_cleanup,
vm_control.resume and their validators/callers/tests. Preserve exact archive/
content-equivalence rules, saved XML fingerprints, keys, run/VM identity and
supported interruption phases. Original cleanup is distinct from new acquisition;
never adopt old readiness or execute archived code.

## Finite validation and cleanup

Use private original-schema snapshot/credential/owner fixtures for stop/restore
after source changes, restored-off ownership, online lost reply and the explicitly
authorized startup-gap route. Wrong baseline/instance, replaced owner, missing
proof and unknown phases must preserve their existing refusals. Assert exact
identities and sidecar references survive interruption without being rewritten.
Run scoped snapshot/transport/recovery safety checks, review resource inventories
and finish only recorded private cleanup. Live recovery remains in F11/F12.
Update delivered recovery owners and close through the
[master](../Fixture-Execution-Plan.md).
