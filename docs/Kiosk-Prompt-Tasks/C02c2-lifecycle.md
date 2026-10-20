# C02c2 — Prepare owned lifecycle migration

Acceptance: host

Required tasks: C02c1.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

Read C01's mapped package configure/upgrade/removal templates, provisioning
rollback and confinement-state owners. Prepare the finite migration from
checked-in v1.4 and the old plan's active installed-state formats to the rebuilt
account/runtime. Use source-defined ownership and known state identities; do
not invent generic filesystem cleanup or delete live/foreign sessions.

Preserve policy/preferences and unrelated installation/removal behavior. Prepare
the matching build/package inputs and owned rollback/remove/purge handling.
Keep production selection unchanged here; C02 activates the migration with the
runtime/PAM cutover, so no intermediate package depends on deleted old state.

Use targeted host lifecycle/composition/rollback tests for before, interrupted
and retry states. Review backend changes independently and run final make build.
Record exact activation/removal obligations for C02 and residual dead-source
deletions for C02d/C02e. Installed update acceptance remains C11c1/C12c1.
