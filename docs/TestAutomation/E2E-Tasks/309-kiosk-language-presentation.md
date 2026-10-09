# 309 — Kiosk Hebrew request and child-language ownership

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **309a** — Restricted station Hebrew/restored-English request and child-language ownership across approver changes.

Estimate: 20–30 minutes.

## Scope and acceptance

Compose one complete case from the
[fixed kiosk recipe](../E2E-Scenario-Recipes.md#kiosk-language-presentation-planned-task-309).
Preserve the selected child's saved language across approver changes and the
English → Hebrew → English history, with representative translated request text.
In Hebrew, select Jamie → Casey → Jamie while keeping Riley, the 75-second
custom request and included soft apps unchanged; require the station to retain
Riley's language throughout. Restore English and compare the original request
choices. Keep station restrictions intact. Repeated About and error-report tours
are outside this journey; Parent task 307 retains the mixed-script ordinary
feedback draft check. The ordinary translated kiosk approvals
remain in task 300's independent continuous Chinese case.

## Shared implementation

Reuse 309a and LANG01/REQUEST04 operations with finite case-owned order and immutable comparisons; do not copy station lifecycle mechanics.

## Implementation entry

One planned complete case; no numeric coverage ID or executable is registered.
Allocate one stable scenario/coverage binding for the linked recipe before
implementation. Run that exact case through the maintained E2E launcher and
regenerate coverage at close-out. Prerequisite qualification is not case acceptance.
