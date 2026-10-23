# F21 — Integrate Fedora product-free E2E preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F20

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate `InstalledJourney.product_free` and the asset-bearing package/upgrade
preparations. Read complete asset/bootstrap callers and the design's exact smoke
exceptions. Provision after owned SSH readiness, before customer package input.
GDM-only selects an empty closure. Retain dormant `install_current_package`,
`check_parent_about` and `check_parent_access` guards with host coverage;
this task does not enable them. Preserve all scenario installation/update and
document/attachment/version/launcher checkpoints.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Preserve enforcing SELinux, exact native admissions and labels. Renew affected
Ubuntu checks after shared corrections.

## Acceptance and cleanup

Register/list the planned `check_fixture_e2e_product_free` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_e2e_product_free
```

Exercise both asset-bearing product-free graphical preparation and the empty
GDM-only entry. Verify selected native use in the former and no movable payload
or native-input dependency in the latter. Prove product absence in both; no
preboot reusable payload upload. Host composition binds every declared smoke
exception; distinct package/upgrade preparation paths retain their own proof.
Stop before customer package input or product assertions.
Complete shared qualification and the master's close-out.
