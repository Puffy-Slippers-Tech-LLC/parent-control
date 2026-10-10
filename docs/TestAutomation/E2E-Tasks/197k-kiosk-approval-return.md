# 197k — Compose kiosk approval and retained child entry

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
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

- **197a** — FLOW20 kiosk new/open form with fresh-child destination.
- **043c** — Legitimate retained-child return with immutable original-activity comparison.

## Implementation

Extend 197a's kiosk FLOW04/FLOW05 composition with explicit retained-child FLOW15 entry and TIME01/UI12 comparison. Receive GDM or an independently open station form as declared. Reuse the shared FLOW20 argument/result contract and unchanged fresh-child bindings; do not depend on overlay qualification, open a session implicitly or alter daily/app policy.

## Live VM acceptance

Qualify new-form Riley/Jamie/30-second/soft-excluded and independently supplied
open-form Jordan/Casey/75-second/soft-included requests with retained-child
destinations in fresh guarded VM attempts. Approve once per
invocation; require success, automatic station exit, legitimate return to the
same child activity and countdown within prebound public/elapsed-time intervals.
Reuse unchanged exact fresh-child qualification from 197a, rerunning it only when
affected; its evidence supplies no saved VM state.
Missing entry modes refuse without repair. Keep entry/recipient and uncertain
input guards in shared qualification; no additional choice combinations or
expiry wait belong to this composition.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_kiosk_approval_return
```

Keep 197a's explicit child/eligible-parent/duration/soft-choice arguments and
finite consumer scope; carry child identity through authentication, countdown
and the supplied earlier activity. Extend only its destination through
`journey_blocks.desktop_entry(entry='retained')` and shared activity comparisons.
Missing prior activity or a newly created desktop cannot satisfy retained return.
