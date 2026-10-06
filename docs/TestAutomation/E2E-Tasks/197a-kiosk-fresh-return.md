# 197a — Compose kiosk approval and fresh child entry

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW20 kiosk new/open form with fresh-child destination**. Named consumer: task **197k** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052** — TIME01 child-desktop presence and limits-off absence.

## Implementation

Compose kiosk FLOW04/FLOW05 with explicit fresh FLOW15 and countdown comparison. Accept GDM or an independently open station form; no implicit policy setup.

## Live VM acceptance

Qualify new-form/fresh-child and open-form/fresh-child in a fresh guarded attempt. Approve once per invocation, read success and automatic exit, then perform fresh child entry and compare countdown with elapsed-time bounds.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_kiosk_fresh_return
```
