# 307b — Qualify inherited Parent dialog language and drafts

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **009** — Public synthetic body/reply editing and independent readback.
- **030** — Parent feedback draft preservation and normal dialog closure.
- **185p** — Parent About entry and public information reads.
- **300g** — Parent language selection.
- **307a** — Permitted installed Hebrew presentation observations.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify Parent's shared About/feedback binding in English and Hebrew. Task 307a
qualified only the Parent language chooser's logical text and keyboard/focus
binding; its `AccessibleUI.language_presentation` reader is chooser-scoped.
Reuse that contract and extend the existing dialog readers for their own public
IDs and ownership. Shared IDs do not transfer chooser qualification to dialogs.
Observe inherited translated controls and
Hebrew/restored English logical text on both dialogs under the mandate's
no-visual acceptance rule, unchanged product/application names, and the exact
synthetic body `שלום Alex 75` and reply `rtl-check@example.invalid`.
Close only the dialog, change language through public Preferences, reopen and
independently compare the retained draft/reply before any new input. Preserve
focus according to each explicit public input/result boundary and verify
keyboard use in both directions. No Send or external-link navigation.

Use only a normal customer route that actually preserves the same draft; do not
set a translation context or draft privately. A modal/public-entry limitation
is a retained gate, not permission to substitute a host fixture. Refuse
wrong-surface, stale/ambiguous ownership and altered synthetic values.

## Shared implementation

Extend shared `open_about`, `open_feedback`, `feedback_snapshot` and
synthetic text profiles in [accessible_ui.py](../../../tests/e2e/accessible_ui.py).
Current feedback readers contain English expectations and Parent-only entry.
Reuse their operations and recorder/worker contracts; qualify translated reads
without changing feedback delivery or the portal.

## Implementation entry

Planned selector: `check_e2e_parent_dialog_language`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_parent_dialog_language`.
Retain affected Parent About, feedback read/text and draft-preservation qualifications; no valid submission is authorized.
