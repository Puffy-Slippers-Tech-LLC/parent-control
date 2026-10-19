# 006e3 — Qualify Fedora native bootstrap

Acceptance: installed
Targets: onpc-Fedora44

Requires 006e1 and 006e2. Read [006e's complete finite acceptance](006e-bootstrap-permissions.md#finite-acceptance-on-each-target)
and the applicable installed runner, VM, approval and storage owners. Every one
of its six assertion families applies to this target, unchanged.

```sh
tools/run-tests system --vm 'onpc-Fedora44' --area 'enforcement' --test 'test_kiosk_native_bootstrap_permissions'
```

Use the actual enforcing SELinux `init_t` and `xdm_t` caller routes, exact loaded
production policy, both selected copied ELFs, independent proc/pidfd and recursive
view observations, the live manager reexec and exact native/kernel denials.
Prove all namespace/write/escape restrictions, original manager/completed-record
preservation and descriptor ownership. Inspect the instrumented logger receipt
before classifying the fifth attempt's mismatch; never allow an unknown socket
or weaken policy to accommodate the engineering fixture.

Preserve first failures and exact inputs; run affected host/build checks after
bounded authorized repairs. Finish runner restoration and owned cleanup before
recording a pass. Reconcile changes with 006e2's Ubuntu assertions and explicitly
identify any invalidated history; do not erase its historical receipt or claim
both-target acceptance here. 006e remains responsible for final complete,
applicable passing receipts on both targets.
