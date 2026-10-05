# 197k — Compose kiosk approval and retained child entry

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add new/open-form retained-child destinations. Reuse 197a's fresh-child
qualification; the cumulative FLOW20 contract supports all four entry/destination
bindings without repeating unchanged predecessor invocations.

Reuse the delivered scope of tasks **197a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **FLOW20 kiosk new/open form and fresh/retained child**. First scheduled consumer: [E2E-048, case 224](../E2E-Scenario-Recipes.md#e2e-048).
Read only the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and that consumer's selected recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052** — TIME01 child-desktop presence and limits-off absence.
- **197a** — FLOW20 kiosk new/open form with fresh-child destination.

## Implementation

Compose kiosk FLOW04 and FLOW05, then the explicitly fresh/retained child FLOW15 entry and TIME01/UI12. Receive GDM or an independently open station form as declared. Reuse the shared FLOW20 argument/result contract; do not depend on overlay qualification, open a session implicitly or alter daily/app policy.

## Live VM acceptance

Qualify the new-form/retained-child and independently supplied
open-form/retained-child entries in fresh guarded VM attempts. Approve once per
invocation; require success, automatic station exit, legitimate return to the
same child activity and countdown within prebound public/elapsed-time intervals.
Reuse unchanged fresh-child results from 197a, rerunning them only when affected.
Missing entry modes refuse without repair. Keep entry/recipient and uncertain
input guards in shared qualification; no additional choice combinations or
expiry wait belong to this composition.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_kiosk_approval_return
```

The selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract).
Require independent valid entry, wrong-entry refusal and owned live VM cleanup.
Host checks and a diagnostic slice do not establish complete scenario coverage.
