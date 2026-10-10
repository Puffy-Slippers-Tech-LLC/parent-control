# 308a — Qualify overlay Hebrew request presentation

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **300i** — Riley overlay language selection.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify the child-owned English → Hebrew → English history with Riley/Jamie,
75 seconds and soft apps included. Verify the saved language reaches the request
form while preserving Riley, Jamie, the 75-second custom request and included
soft apps at each language transition. Independently read representative Hebrew
request text and restored English through public Preferences and form operations.
Capture the original usable child activity and its synthetic content, then
require normal Cancel return to that same activity with unchanged content.
Full translated-label/dialog combinations belong to host UI coverage; stable
IDs and matching semantics remain shared automation guards. Check independent
entry and wrong child/owner refusal.

About and error-report tours remain with their existing owners. The mixed-script
ordinary feedback draft history remains in Parent task 307. Error-report drafts
end on closure under the [specification](../../Specification.md#feedback-and-error-reports);
this binding requires no report reopening or draft-retention qualification.

## Shared implementation

Reuse qualified overlay language, request observation and activity-return
operations through
[AccessibleUI](../../../tests/e2e/accessible_ui.py).
Keep child session ownership distinct from the kiosk despite shared GTK IDs.

Extend `AccessibleUI.kiosk_language_form` / `language_history_request` with
the representative English/Hebrew/restored-English observation and immutable
75-second/soft-included request comparison. Reuse 300i's saved-language input
operation and the existing overlay activity-return comparison; qualify the new
overlay projection here. Parent-only 307a evidence supplies no overlay readiness
and its chooser/dialog history is not a prerequisite.

## Implementation entry

Planned selector: `check_e2e_overlay_dialog_language`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_overlay_dialog_language`.
Retain affected language-selection and request/Cancel-return qualifications.
