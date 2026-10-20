# C02d — Remove obsolete native and runtime code

Acceptance: host

Required tasks: C02.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

C02 supplies the single selected release-based runtime and owned migration.
Delete the mapped superseded native/private-view/material/startup/preparation
implementations, runtime graph inputs and direct includes/imports. Inventory
checked-in HEAD plus staged, unstaged and untracked old-plan changes. Delete
obsolete new modules as well as legacy code; no disabled copies, test-only
production probes or speculative fallback survives solely to preserve old work.

Read complete remaining callers and Makefile inputs before removal. Port or
delete directly dependent fixtures/registrations in this task so imports,
collection and the selected tests stay coherent; C03a1 audits the remainder.
Keep required ownership, authentication and current feature behavior.

Run exact affected host checks and final make build; obtain independent backend
review for core changes. Update the disposition table with verified absent
consumers. Hand remaining feature/protocol/package deletions to C02e. No live
qualification or new protection addition precedes completion of source cleanup.
