# 001 — Qualify optional PAM installation and confinement

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and scope

Qualify the implemented root fix and new Ubuntu baseline input with real native
PAM callbacks and policy tools. Keep the first-configuration failure, quarantine,
retry, reboot and execution boundary in their existing indivisible history.
Fedora remains a required regression target; do not invent an LXC dependency there.

## Reading and implementation route

Read the [master](../Core-Installation-Coverage-Handoff.md),
[system design](../../System-Design.md), affected Lifecycle/Kiosk-Confinement
modules, [test maintenance](../../../tests/README.md#core-installation-and-runtime-compatibility),
[VM mandate](../../Mandates/VM-Mandate.MD) and
[installed runner/environment](../../../tests/integration/README.md).
Inspect `guest_test_dependencies`, baseline dependency preparation,
`system_first_configure` and `system_kiosk_confinement` with their callers and
host tests. Check the runtime registry and launcher help before execution.

Refresh stale baselines through the maintained preparation route. Verify that
Ubuntu's package installation enables the declared profile in both shared
session stacks. If a pre-existing disabled profile prevents this, correct its
finite preparation/reconciliation owner with explicit ownership and host
regressions; never repair reusable prerequisites inside a test or weaken the
effective-rule witness. Preserve unrelated PAM inputs.

```sh
tools/prepare-vm --vm 'onpc-Ubuntu26.04,onpc-Fedora44' --mode auto --y
tools/run-tests system --list --area 'package'
tools/run-tests system --list --area 'enforcement'
tools/run-tests system --vm 'onpc-Ubuntu26.04,onpc-Fedora44' --area 'package' --test 'test_first_configuration_interruption_retry'
tools/run-tests system --vm 'onpc-Ubuntu26.04,onpc-Fedora44' --area 'enforcement' --test 'test_kiosk_execution_confinement'
```

These selectors are registered at handoff. Preserve launcher timeouts and the
complete histories. Read the current live contract before any GUI adapter work;
this brief does not authorize a new input route.

## Expected results and close-out

Ubuntu must record the active optional profile at all three checkpoints, execute
native installation/retry and survive normal reboot and manager teardown while
confinement remains enforcing. Both targets must preserve quarantine and ordinary
user behavior, publish valid installed state, activate the broker and pass the
native execution/refusal matrix. Retain actual native package/version receipts.
Successful configuration must also satisfy the shared
[failed-manager recovery check](../../../tests/integration/README.md#running-the-current-installed-suite):
the kiosk leaves native trigger enumeration and its scoped wildcard reload succeeds.
Do not accept a test that silently drops the optional module.

Use the existing runner's collection and owned cleanup; both VMs finish in the
required powered-off restored state. Run the lowest affected host regressions
after any repair, and `make build` after product/build-input edits. Record both
target reports and cleanup, update pending wording in the installed/environment
guides, check Markdown links and the plan, then close only this row and advance
the master. Any native mismatch follows the failure-handling contract.
