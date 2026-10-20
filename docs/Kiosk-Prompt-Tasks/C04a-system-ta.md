# C04a — Reconcile installed-system confinement cases

Acceptance: host

Required tasks: C03.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Read tests/system/test_enforcement.py, its registered cases 267–269/290–294,
tests/integration/system_kiosk_confinement.py and their actual shared helpers.
These are discovery inputs, not a claim that all selectors remain applicable.

Map old retained-view/generation/refusal assertions to current engineering
obligations or retire the discarded detail. Cover checked-in implementations
and old-plan active helper/fixture changes, including new files. Delete unused
legacy/unfinished code after mapping its behavior and consumers.
Retain stable customer IDs, ordinary
role controls, cleanup and original evidence history. Update exact fixtures and
qualification inputs through maintained storage routes; no artifact purge.

Run host registration/composition checks and inspect the installed runner list.
Record runnable, pending and retired bindings honestly. New reusable public
operations require separately bounded installed qualification before consumption;
a host port cannot mark them qualified. No VM work in this task.
