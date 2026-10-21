# F21 — Integrate Fedora product-free E2E preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F20

## Scope and implementation

Qualify the graphical product-free E2E [matrix row](../Fixture-Design.md#runner-acceptance-matrix)
on Fedora. Read F20's complete product-free entry/asset chain and dormant
current-install guard, F01's Fedora
binding and native trust/label actions. Preserve package transaction and product
assertions, clean entry, enforcing SELinux and all guarded input boundaries.

## Finite acceptance

Run affected isolated safety checks and register/list the planned binding before
`tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_e2e_product_free`.
Invoke the actual graphical product-free preparation to prove clean entry and
selected fixture readiness/use over SSH. Stop before package input, product
actions or assertions.
Observe fresh reboot receipts, correct trust/labels, missing/incompatible refusal,
immutable attempt pin and no preboot fixture upload/result-tree cache copy.
Preserve F20's explicit branch/alias allocation; different branches need their
own live prerequisite. Finish watched restoration and transport/pin cleanup,
renew affected Ubuntu proof and update owners through the [master](../Fixture-Execution-Plan.md).
