# C01c — Map automation and package consumers

Acceptance: review

Required tasks: C01b.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

Trace C01a/C01b's interface map through Makefile package inputs, packaging
confinement/PAM configuration, provisioning, lifecycle templates and removal.
Map host fixtures/registrations, installed helpers/system IDs and kiosk E2E
callers through their documented owners. Inspect checked-in code and every
relevant old-plan staged, unstaged and untracked addition; no inactive copy is
exempt. Do not perform repository-wide cleanup.

Extend the existing disposition table with source owner, caller, retained
behavior, removal/port action and receiving C02/C03/C04 task. Distinguish obsolete
implementation assertions from required customer results and historical evidence.
Record artifact/installed-state ownership separately from deletable source.

Inspect maintained help/inventory before naming selectors; mark missing or
changed qualification as pending. Hand C01 a complete finite removal/preservation
map and sizing risks. Check links/plan structure. This is review, not execution
or a promise that the old automation is reusable unchanged.
