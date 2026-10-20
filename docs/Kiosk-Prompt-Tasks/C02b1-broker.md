# C02b1 — Prepare the broker approval boundary

Acceptance: host

Required tasks: C02a.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

Using C01's map, read complete broker authorization/core/service/kiosk_visits
functions, D-Bus XML and necessary frontend callers. Prepare the broker boundary
for the release-based session without retaining discarded startup/view/receipt
mechanisms solely because they exist in HEAD or active old-plan work.

Preserve caller/target roles, genuine selected-parent authentication, cancellation
on departure, no stale/duplicate grant and grant/app transaction semantics. Keep
the selected runtime and all callers coherent: independently compatible changes
may activate here; incompatible interfaces remain unselected until C02. C02b
owns frontend adaptation. No additional live admission path or weakened approval.

Port directly affected unit/private-bus fixtures and run their exact maintained
selectors. Obtain independent Astra xHigh backend review and make build after
final packaged edits. Record the prepared interface and activation/removal
obligations in the design owner; C02e removes now-unused protocol modules.
