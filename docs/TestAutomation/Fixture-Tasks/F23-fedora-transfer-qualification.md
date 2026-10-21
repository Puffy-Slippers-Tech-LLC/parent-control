# F23 — Integrate Fedora transfer qualification

Acceptance: installed
Targets: onpc-Fedora44
Requires: F22

## Scope and implementation

Qualify the standalone transfer [matrix row](../Fixture-Design.md#runner-acceptance-matrix)
on Fedora. Read F22's full bootstrap/transfer/readback chain, F01's binding and
native/SELinux actions. Use the same SSH provisioner and keep serial aliases gated.

## Finite acceptance

Run affected host safety checks and register/list the planned binding before
`tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_transfer`.
Through the actual product-free standalone transfer preparation observe selected
bytes and native labels/trust, no fixture preboot upload or product installation,
missing/corrupt refusal before graphical input, fresh receipt and unchanged pin.
Cover uncertain transfer recovery without replay. Stop before graphical input or
product actions/assertions. Finish watched restoration,
transport and pin cleanup, renew affected Ubuntu proof after shared fixes and
update delivered owners through the [master](../Fixture-Execution-Plan.md).
