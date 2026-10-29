# 309 — Kiosk Hebrew request and child-language ownership

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **300j** — Kiosk selected-child language restoration and approver independence.

Estimate: 20–30 minutes.

## Scope and acceptance

Compose one complete case from the
[fixed kiosk recipe](../E2E-Scenario-Recipes.md#kiosk-language-presentation-planned-task-309).
Preserve the selected child's saved language across approver changes and the
English → Hebrew → English history, with representative translated request text.
In Hebrew, select Casey once while keeping Riley, the 75-second
custom request and included soft apps unchanged; require the station to retain
Riley's language. Restore English with Casey still selected and compare the
same child, duration and soft-app choice. Keep station restrictions intact.
Repeated About and error-report tours are outside this journey; Parent task 307 retains the mixed-script ordinary
feedback draft check. The ordinary translated kiosk approvals
remain in task 300's independent continuous Chinese case.

## Shared implementation

Reuse LANG01/REQUEST04, `AccessibleUI.language_history_request` and
`kiosk_language_form` with finite case-owned order and immutable comparisons.
The existing language persistence history already binds Riley's Hebrew custom
75-second/soft-included request and Jamie/Casey changes. Extend only missing
restored-English literal projections and this recipe's ordering; do not add a
second request-presentation qualifier or copy station lifecycle mechanics.
Reuse station restriction guards without link/file/shortcut tours. Existing
language coverage does not pass this still-pending complete history.

## Implementation entry

One planned complete case; no numeric coverage ID or executable is registered.
Allocate one stable scenario/coverage binding for the linked recipe before
implementation. Run that exact case through the maintained E2E launcher and
regenerate coverage at close-out. Prerequisite qualification is not case acceptance.
