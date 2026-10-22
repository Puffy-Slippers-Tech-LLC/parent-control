# F11 — Decouple Ubuntu snapshots from fixture payloads

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F15

## Scope and implementation

Implement Ubuntu's [clean snapshot boundary](../Fixture-Design.md#runner-and-snapshot-migration).
Read complete `prepare_vm.SCRIPT_FILES`/digest, baseline guest/capture/fixture
ownership, app snapshot, online credential and standalone app preparation paths.
Separate runtime dependency ABI from fixture-only bytes while preserving product
and genuinely shared source invalidation.

Recover existing VM owners before changing writers. Retire the complete proven
owned legacy movable inventory, exact admissions and retained source copies
before capture; preserve environment settings and avatar/recovery data. Refuse
ambiguous ownership rather than importing or sweeping it. Preserve legacy
stop/restoration. Unmigrated consumers must refuse clean captures before input.
Update VM/approval/environment owners only for the delivered Ubuntu boundary.

## Acceptance and cleanup

Run affected baseline/capture/recovery safety tests first. Register/list the
planned `check_fixture_snapshots` binding. Use a separately invoked authorized
auto-mode preparation refresh to prove clean baseline/app captures, standalone
app preparation without movable fixtures, legacy recovery and fixture-only source
changes leaving snapshot identities valid. Actual dependency/product changes
must still invalidate. Audit archived input trees and the baseline preparation
checkout as well as runtime destinations. No hidden fixture fallback is allowed.
Record preparation separately from later same-boot refresh, finish watched owned
restoration and keep other targets gated until their own delivery.

Follow the [master](../Fixture-Execution-Plan.md) for reading, resource review,
owned cleanup and ordinary evidence/Git close-out.
