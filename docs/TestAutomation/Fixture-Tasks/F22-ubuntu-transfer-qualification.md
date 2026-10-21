# F22 — Integrate Ubuntu transfer qualification

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F21

## Scope and implementation

Migrate the standalone transfer [matrix row](../Fixture-Design.md#runner-acceptance-matrix).
Read `check_graphical_smoke` asset preparation, `AssetTransfer.provision`,
`serial_harness` callers, guarded bootstrap and F01's exact qualification binding.
Keep preboot work to transport prerequisites; push fixture bytes through the
shared provisioner only after owned SSH is ready. No installed app snapshot or
implicit product installation may substitute for this product-free envelope.
Leave serial callers gated until F25/F26 rather than changing their timing silently.

## Finite acceptance

Run affected host transfer/cleanup/provenance checks. Register/list the planned
binding before
`tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_transfer`.
It must exercise the real standalone `--qualify-transfer` preparation and independent
guest byte/harmless fixture readback over SSH, then stop before graphical input.
Prove selected closure use, no preboot fixture upload,
product absence, missing/corrupt refusal before graphical input, one attempt pin
and fresh boot receipt. Cover uncertain transfer reconciliation and preserve
existing fixture transfer assertions. Add no product actions/assertions. Finish watched restoration and all transport/pin
cleanup, update delivered owners and close through the [master](../Fixture-Execution-Plan.md).
