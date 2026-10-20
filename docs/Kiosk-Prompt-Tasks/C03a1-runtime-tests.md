# C03a1 — Reconcile native runtime host tests

Acceptance: host

Required tasks: C02e.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

Audit C01's native runtime, material/view/receipt, graph and startup test families,
their tests/support helpers and tools/regression_unit.py registrations. Include
checked-in tests and old-plan staged, unstaged and untracked fixtures/modules.
C03a separately owns PAM/account/package fixtures.

Port surviving entry/exit, ownership and normal-use assertions to the rebuilt
behavior. Delete discarded mechanism assertions, private compilers/probes and
unused helpers once callers are mapped. Do not keep legacy/garbage coverage as
skipped tests; preserve required customer and authentication outcomes.

Run the exact affected unit selection and review resource/storage changes under
their owners. Record each retained/ported/removed item in the disposition map;
hand package and shared-helper interfaces to C03a. Host evidence supplies no
installed confinement or public-use acceptance.
