# 309a — Qualify kiosk Hebrew request presentation

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **300j** — Kiosk selected-child language ownership and approver independence.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify the station binding for Riley/Jamie, a 75-second soft-included request,
and English → Hebrew → English via public Preferences. Verify the selected
child's saved language reaches representative request text. Compare exact Riley
and Jamie account identities, the 75-second custom request and included soft apps
at each language transition. In Hebrew, change approver Jamie → Casey → Jamie;
require Riley's checked language and Hebrew request context to remain unchanged,
with the declared approver as the only changed request field. Restore English
and require the original Riley/Jamie request choices. Retain station restrictions
on external actions/files. Full translated-label/dialog combinations belong to
host UI coverage; public IDs and matching semantics remain shared automation
guards. Qualify independent entry and wrong selected-child/surface/owner refusal
without uncertain replay.

About and error-report tours remain with their existing owners. Parent task 307
retains the mixed-script ordinary feedback draft history. Error-report drafts end
on closure under the [specification](../../Specification.md#feedback-and-error-reports);
this binding requires no report reopening or draft-retention qualification.

## Shared implementation

Reuse selected-child language, approver-selection and language-aware REQUEST04
operations in [accessible_ui.py](../../../tests/e2e/accessible_ui.py).
Qualify the station ownership binding separately from the child overlay.

Reuse `AccessibleUI.language_history_request` and the 300j station
selected-child/approver operations, extending only the English → Hebrew → English
fixed-history observation and immutable request comparisons. Parent-only 307a
qualification is not a station prerequisite. Reuse the station's unchanged
restriction guards; do not repeat shortcut/file/link restriction tours merely
to observe translated request text.

## Implementation entry

Planned selector: `check_e2e_kiosk_dialog_language`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_kiosk_dialog_language`.
Retain affected language-selection, approver-independence and selected-child restoration qualifications. No external-link activation.
