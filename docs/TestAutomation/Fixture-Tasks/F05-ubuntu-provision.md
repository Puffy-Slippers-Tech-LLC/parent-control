# F05 — Provision fixtures over owned SSH on Ubuntu

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F15

## Purpose and scope

Implement the shared [owned provisioning boundary](../Fixture-Design.md#owned-ssh-provisioning-and-readiness)
and qualify Ubuntu. Retain the present baseline route for other targets until
their own qualification; production runner integration stays gated until each
preparation matrix row passes.

## Read and implement

Read F01's finite closure/route/schema map, shared VM/watch/approval contracts,
`tests/integration/vm_transport.py`, `system_runner.py`,
`tests/e2e/asset_transfer.py`, `guest_files.py`, `native_fixtures_guest.py`,
`tests/integration/baseline_fixtures.py`, `tests/fixtures/native_trust.py` and
their safety tests. Reuse owned transport and extract the finite reconciliation
mechanics needed by the fixed guest helper. Add bounded staging, full preflight,
intent/receipt journaling, metadata/role resolution, exact trust activation and
independent readback. Integrate F15's composed F31/F32/F50/F33 safety APIs without exposing a
second updater. Preserve intentional untrusted fixtures and product policy.

## Finite validation and cleanup

Register/list F01's planned engineering qualification before invoking it through
`tools/run-tests integration`. Run affected isolated transport/fixture/trust/
cleanup regressions first. In a watched owned Ubuntu attempt prove first transfer,
repeat/no writes, changed version, minimal closure and runtime use of native
trusted/untrusted witnesses. Cover truncated transfer, lost reply, interrupted
activation/retry, wrong compatibility/owner and foreign destination refusal;
use host fault injection for unsafe cases that need no live mutation. Receipts
must bind actual boot/attempt and loaded trust. No sync-triggered reboot/snapshot
or dependency installation. Prove a larger→smaller→disjoint subset sequence with
removed files/launchers/admission absent, shared members retained and modified
removal refused. Exercise a fresh launch/runtime-open race while the loaded
barrier is held, the recorded C/Python pair's explicit exit and unknown-owner
refusal; failed barrier activation must leave old payloads unchanged. Include
interrupted removal, trust and barrier release with unavailable readiness until
exact reconciliation. Qualify F50's attributed decision plus actual syscall
outcomes, fresh nonce executable and exact trust=0/1 transitions. Reject stale
logs, unrelated/overflow denials, partial parse, permissive/stopped/restarted
daemon and delayed observer removal with PID reuse. Use host injection where
unsafe faults need no live mutation. Prove full legacy movable-set import and
retirement, including unrequested outputs and original source copies; preserve
environmental settings. These are fixture/native-infrastructure witnesses only;
no product actions or denial assertions are part of this task. Reconcile every
owned transaction and restore through
the lease before close-out. Update only delivered VM/approval/environment/support
boundaries; preserve legacy restoration. Use the [master](../Fixture-Execution-Plan.md).
