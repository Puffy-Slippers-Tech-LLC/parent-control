# 154 — Deferred qualification of restored mute

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract).
This deferred brief has no current-release acceptance.

This is future-feature scope, outside current-release completion. No active
task depends on it. Reconsider only after a real product release restores the
public mute control; current absence cannot qualify interaction.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
After the feature gate opens, read only the restored mute contract and qualified
request-form/toggle callables. No other task brief or full queue is needed.

## Scope and prerequisites

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.

Use its maintained callables plus the restored feature's
contract. Preserve the saved-field obligations under
[engineering reconciliation](../E2E-Building-Blocks.md#inventory-reconciliation).
No old task document or VM state is required.

## Conditional live VM acceptance

After restoration, qualify the real control on both installed VM forms: read
initial state, set the explicit value and verify the specified surface-local
behavior and persistence through normal public exits/re-entry. Do not enable a
test-only feature switch. Require independent entry and owned cleanup. Reassess
the task under the [sizing contract](../E2E-Execution-Contracts.md#task-size-and-order)
when the feature returns.

## Reactivation and close-out

Keep this row unchecked and outside the active queue until the feature is restored
and its scope is authorized. Reactivation must repair queue order and prerequisites
under the shared contract; it cannot skip the current active task. Apply capability
acceptance and normal close-out only after that selection and live qualification.
