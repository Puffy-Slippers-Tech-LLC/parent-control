# F21 — Integrate Fedora product-free E2E preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F20

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Qualify F20's existing `InstalledJourney.product_free` and asset-bearing
package/upgrade preparation on Fedora. Reuse its helper, selector and histories;
change only the target gates and evidenced Fedora differences. Read complete
affected functions and necessary callers plus the design's exact smoke exceptions.
Provision after owned SSH readiness, before customer package input.
GDM-only selects an empty closure. Retain dormant `install_current_package`,
`check_parent_about` and `check_parent_access` guards with host coverage;
this task does not enable them. Preserve all scenario installation/update and
document/attachment/version/launcher checkpoints.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Preserve enforcing SELinux, exact native admissions and labels. Apply the design's
[bounded renewal rule](../Fixture-Design.md#validation-reuse-and-invalidation)
before selecting Ubuntu checks; a Fedora gate extension alone needs no Ubuntu
live rerun or new shared-provisioner audit.

## Acceptance and cleanup

Confirm the existing `check_fixture_e2e_product_free` binding lists Fedora before invoking:

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

Run each existing distinct preparation once; reuse unchanged shared safety proof.
No customer package install, upgrade, login or product assertion is part of this
task's acceptance.
