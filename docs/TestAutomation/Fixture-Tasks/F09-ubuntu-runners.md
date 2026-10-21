# F09 — Integrate Ubuntu product-free system preparation

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F06

## Purpose and scope

Deliver the common attempt-preparation API and migrate only Ubuntu's product-free
system row of the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix).
Other envelopes remain gated until their own paired tasks. Preserve every case's
finite inputs and independent assertions.

## Read and implement

Read F01's matrix binding, `tools/test_commands.py`, `vm_artifacts.py`,
`test_storage.named_input`, `tests/integration/system_runner.py`,
`system_snapshots.py`, `tests/e2e/asset_transfer.py`, `native_fixtures.py`,
`private_artifacts.py` and the common attempt-envelope sections of
`E2E-Building-Blocks.md`. Bind `system_snapshots._run_attempts(installed=False)`
and `system_runner.installed_run`: establish owned transport and stage before
installation/customer input without preinstalling the product or altering the
initial policy state.

Resolve/pin one compatible exact bundle/subset before provisioning, keep product
and fixture artifact identities independent, and record readiness/provenance in
existing results. After restore/reboot bind a fresh receipt before fixture use.
Remove case-local reusable preparation; deliberate scenario mutations stay local.
Do not repair fixtures after an assertion or allow live refresh inside a recorded
attempt. Retain target-gated compatibility until Fedora's F10 qualification.
Host attempt/result trees reference the pin and exact manifest rather than
copying the full fixture cache; product artifacts retain their separate owner.

## Finite validation and cleanup

Extend affected envelope/provenance/launcher safety tests; register the planned
engineering binding `check_fixture_system_product_free` (planned, not registered)
and list it before invoking
`tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_system_product_free`.
It must call the real product-free system preparation, not a parallel provisioner.
Use F01's selected case metadata to exercise that preparation branch, independently
read/execute a harmless fixture witness over SSH and stop before installation or
any product action/assertion. Observe readiness with the product still absent.
Prove selected bundle/subset reaches guest use; missing/incompatible inputs stop
before scenario input, mid-run host changes do not switch the pin and input
failures remain distinguishable from consumer assertions. Host composition tests
bind all product-free system selectors to the same API and preserve rebooted
readiness. Run affected fixture infrastructure regressions only. Finish each
lease/transport/pin cleanup; update support/runner/provenance owners through the
[master](../Fixture-Execution-Plan.md).
