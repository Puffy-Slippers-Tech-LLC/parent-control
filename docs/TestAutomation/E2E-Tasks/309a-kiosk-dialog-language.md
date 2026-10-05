# 309a — Qualify inherited kiosk Hebrew dialogs

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **185k** — Restricted station About entry/read/close.
- **187k** — Real public station error-report entry and closure.
- **300j** — Kiosk selected-child language ownership and approver independence.
- **307a** — Shared installed Hebrew presentation observation contract.
- **307b** — Shared translated dialog and synthetic-draft readback mechanics.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify the station binding for Riley/Jamie, a 75-second soft-included request,
and English → Hebrew → English via public Preferences. Read request, restricted
About and real feedback/report presentation through qualified public semantics:
Hebrew/restored English logical text, exact mixed Hebrew/Latin content, translated
visible/accessibility labels, stable IDs and usable keyboard/focus. Compare exact
account names, numeric request values, body `שלום Alex 75` and reply
`rtl-check@example.invalid` across normal report close, language switch and
real report reopen. Retain station restrictions on external actions/files.

Reuse 187k's genuine public error trigger and actual re-entry timing gate.
Keep unsupported same-draft reopening explicit; do not inject errors or use a
Parent feedback button/host fixture as station evidence. Qualify independent
entry and wrong selected-child/surface/owner refusal without uncertain replay.

## Shared implementation

Reuse `kiosk_about_entry`, `read_kiosk_about`, language-aware REQUEST04 and
the shared feedback snapshot/text operations in
[accessible_ui.py](../../../tests/e2e/accessible_ui.py), with 187k's worker.
Qualify the station ownership binding separately from the child overlay.

## Implementation entry

Planned selector: `check_e2e_kiosk_dialog_language`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_kiosk_dialog_language`.
Retain affected restricted About, kiosk report-entry and selected-child restoration qualifications. No feedback submission or external-link activation.
