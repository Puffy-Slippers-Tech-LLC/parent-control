# F20 — Integrate Ubuntu product-free E2E preparation

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F19

## Scope and implementation

Migrate the graphical product-free E2E preparation
[matrix row](../Fixture-Design.md#runner-acceptance-matrix). Read `InstalledJourney`
product-free branch and dormant `install_current_package` guard, product-free entry,
package/upgrade consumers, private asset staging and F01's exact branch bindings.
Establish owned SSH and provision the selected closure before customer package
input. Preserve deliberate installation/update mutations; generic preparation
does not install the product or preseed policy. Host branch tests must keep the
current-install setup ordering explicit rather than merging it with clean entry.

## Finite acceptance

Run affected host composition/input/provenance tests. Register/list the planned
binding before
`tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_e2e_product_free`.
Invoke F01's real graphical product-free preparation binding and observe product
absence and selected fixture readiness/use over SSH before package input. Stop
there without a product install, action or assertion.
Prove missing/stale input refusal, one pin despite host edits, fresh reboot
readiness and no hidden preboot fixture upload or full result-tree cache copy.
Host tests cover the dormant current-install setup guard; enabling a new consumer
of that distinct branch requires its own preparation-only prerequisite. Finish watched restoration and transport/pin
cleanup, update delivered owners and close through the [master](../Fixture-Execution-Plan.md).
