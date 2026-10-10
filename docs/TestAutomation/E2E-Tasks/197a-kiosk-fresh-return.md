# 197a — Compose kiosk approval and fresh child entry

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW20 kiosk new/open form with fresh-child destination**. Named consumer: task **197k** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021a** — Fixed kiosk FLOW05/06 approval and automatic GDM return.
- **052** — TIME01 child-desktop presence and limits-off absence.

## Implementation

Compose kiosk FLOW04/FLOW05 with explicit fresh FLOW15 and countdown comparison. Accept GDM or an independently open station form; no implicit policy setup.

Reuse `request_flow.prepared_request`, `kiosk_approved_flow.approved_request`,
`journey_blocks.desktop_entry(entry='fresh')` and
`KioskRequestJourney.check_countdown`. Current approval leaves are the fixed
75-second/soft-included Riley/Jamie binding; explicitly implement the shared
FLOW20 caller-owned child, eligible-parent, duration and soft-choice arguments.
Bound them to Jordan/Riley, Jamie/Casey (the recipe's Sam), soft excluded/included
and the consuming recipes' finite 30/60/75/120/150/180/900-second requests.
Carry the selected child through real authentication, fresh destination identity
and public arithmetic comparisons. TIME01's
existing fresh-child entry supplies the necessary destination; no retained child
or Parent desktop is required for this slice.

## Live VM acceptance

Qualify new-form Riley/Jamie/30-second/soft-excluded and independently open-form
Jordan/Casey/75-second/soft-included requests with fresh-child destinations in
fresh guarded attempts. Approve once per invocation, read success and automatic
exit, then perform the selected child's fresh entry and compare countdown with
elapsed-time bounds. These representative argument bindings qualify the shared
finite API; later cases own their exact values and histories, with no Cartesian
qualification matrix.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_kiosk_fresh_return
```
