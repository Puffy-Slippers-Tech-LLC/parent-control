# 308 — Overlay Hebrew dialogs and translated approval

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Also apply [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **308b** — Hebrew product request/success with genuine Shell approval and normal return.
- **308a** — Child-owned form/About/error-report Hebrew/LTR observations and draft retention.

Estimate: 30–45 minutes.
Session exception: The complete child history retains its genuine error-report trigger, language changes, draft comparisons and real approval/return in one guarded attempt.

## Scope and acceptance

Compose the [fixed overlay recipe](../E2E-Scenario-Recipes.md#overlay-language-presentation-planned-task-308)
as one complete case. Preserve all English/Hebrew/English form, About and feedback
RTL, mixed-script, keyboard, focus, synthetic draft/reply and unchanged request
assertions from 308a, followed by one ordinary translated approval through 308b
and independent return to the original activity. Keep the native agent's own
language separate from the product-owned request/result language. The actual
report trigger and same-draft reopening gates remain mandatory.

## Shared implementation

Compose qualified shared request, report, language and approval fragments; the case owns finite ordering and comparisons, never private error creation or authentication mechanics.

## Implementation entry

One planned complete case; no numeric coverage ID or executable is registered.
Allocate one stable scenario/coverage binding for the linked recipe before
implementation. Run that exact case through the maintained E2E launcher and
regenerate coverage at close-out. Prerequisite qualification is not case acceptance.
