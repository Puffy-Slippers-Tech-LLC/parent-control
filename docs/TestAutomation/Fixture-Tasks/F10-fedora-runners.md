# F10 — Integrate Fedora product-free system preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F09

## Purpose and scope

Migrate the Fedora product-free system row of the
[runner matrix](../Fixture-Design.md#runner-acceptance-matrix) through F09's shared
API, preserving public results and native policy. Other Fedora envelopes remain
gated until their own paired rows; remove no readiness guard for those consumers.

## Read and implement

Read F09's complete product-free envelope/caller/provenance chain, F01's Fedora binding,
F06's runtime activation and the affected registered system/E2E/qualification
bindings. Make bounded platform corrections in shared owners; do not copy case
setup, weaken assertions or claim another queue's acceptance.

## Finite validation and cleanup

Run exact affected host safety tests first. Register/list the planned engineering
binding `check_fixture_system_product_free` before invoking
`tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_system_product_free`
(planned until registered). Invoke F01's product-free system preparation binding
through the actual `installed=False` branch. Read/execute a harmless fixture witness
over SSH, then stop before package input or any product action/assertion. Observe
readiness with the product absent and no retained full fixture copy. Prove immutable
bundle/subset selection, correct trust/labels, fresh boot/attempt receipts after
restore, stale/missing failure before scenario input and no host `latest` switch
mid-run. Preserve scenario-owned mutations and package installation behavior.
Use harmless fixture witnesses over owned SSH and exact infrastructure evidence only.
Complete every owned lease/transport/pin cleanup, renew Ubuntu results invalidated
by shared changes, update existing runner/provenance owners and close through the
[master](../Fixture-Execution-Plan.md).
