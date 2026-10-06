# 309 — Kiosk Hebrew presentation and inherited dialogs

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Also apply [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **309a** — Restricted station form/About/report Hebrew/LTR and retained draft binding.

Estimate: 30–45 minutes.
Session exception: The complete station history includes its real report-trigger and fresh report return while retaining draft and request values across both language directions.

## Scope and acceptance

Compose one complete case from the
[fixed kiosk recipe](../E2E-Scenario-Recipes.md#kiosk-language-presentation-planned-task-309).
Preserve the selected child's saved language across approver changes and the
English → Hebrew → English history, with representative inherited dialog context
and retained draft/reply. Compare account identity and 75-second request values
at the functional transitions; do not traverse every translated label. Keep the real report-entry
gate and station restrictions intact. The ordinary translated kiosk approvals
remain in task 300's independent continuous Chinese case.

## Shared implementation

Reuse 309a and LANG01/REQUEST04 operations with finite case-owned order and immutable comparisons; do not copy station/report lifecycle mechanics.

## Implementation entry

One planned complete case; no numeric coverage ID or executable is registered.
Allocate one stable scenario/coverage binding for the linked recipe before
implementation. Run that exact case through the maintained E2E launcher and
regenerate coverage at close-out. Prerequisite qualification is not case acceptance.
