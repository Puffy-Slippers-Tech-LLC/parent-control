# 197 — Compose overlay approval and return

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW20 overlay new/open form**. First scheduled consumer: [E2E-048, case 223](../E2E-Scenario-Recipes.md#e2e-048).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048d** — Fixed overlay AUTH01/02, explicit approval and automatic original-activity return.
- **052** — TIME01 child-desktop presence and limits-off absence.

## Implementation

Compose the overlay branches of FLOW04 and FLOW05, then TIME01/UI12 on the same child desktop. Accept explicit new/open form entry and earlier public balance observations. No hidden allowance, policy preparation or desktop transition. Keep the kiosk branch pending.

Reuse `request_flow.prepared_request`, `overlay_approved_request` and
`KioskRequestJourney.check_countdown`. The existing request leaves accept only
Riley/Jamie/75 seconds/soft included; implement and qualify FLOW20's explicit
child, eligible-parent, duration and soft-choice arguments, with public balance
arithmetic, before advertising that scope. Immediate exit,
rejection and Cancel qualifications are not prerequisites of automatic approval.

Expose bounded caller-owned selections for Jordan/Riley, Jamie/Casey (the
recipe's Sam binding), soft excluded/included and the consuming recipes' finite
durations: 30/60/75/120/150/180/900 seconds. This also supplies
[E2E-012's selected approval branches](../E2E-Scenario-Recipes.md#e2e-012) and
the selected bindings in E2E-048/049/050/051. Carry the explicit child through
form/recipient authentication, activity identity and countdown comparisons;
never infer it from a fixed wrapper or substitute a remembered approver.
Qualify new-form Riley/Jamie/30-second/soft-excluded approval and independently
open-form Jordan/Casey/75-second/soft-included approval, with fresh exact
request/recipient proofs and public time increments. Reuse immutable activity
endpoints. Do not multiply independent values into every combination;
each later case owns its finite selection, policy outcome and complete acceptance.

## Live VM acceptance

In separate live attempts, supply a usable child desktop for the declared new-form binding and an independently prepared overlay for the declared open-form binding. Approve once per invocation, observe automatic form disappearance and the same usable child desktop, then compare countdown with the earlier public balance plus the requested interval and measured elapsed time. Missing, wrong-child or kiosk entry refuses without preparatory input.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_compose_approval_and_return_to_the_child
```
