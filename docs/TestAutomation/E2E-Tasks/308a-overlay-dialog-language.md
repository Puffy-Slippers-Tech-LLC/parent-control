# 308a — Qualify inherited overlay Hebrew dialogs

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **185o** — Child-owned About and normal return to captured request choices.
- **187o** — Real public overlay error-report entry and report closure.
- **300i** — Riley overlay language selection.
- **307a** — Shared installed Hebrew presentation observation contract.
- **307b** — Shared translated dialog and synthetic-draft readback mechanics.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify the child-overlay binding of shared language/presentation readers for
English → Hebrew → English, including the request form, About and real error
report. Use Riley/Jamie, 75 seconds, soft apps included; capture numeric values
and account names before changes. Independently require Hebrew/restored English
logical text, exact mixed-script content, matching accessible labels, stable IDs and usable
keyboard/focus through the qualified observation route. Retain the exact body
`שלום Alex 75` and reply `rtl-check@example.invalid` across normal report
closure, public Preferences change and genuine report reopening.

Reuse 187o's real public trigger and its actual timing gate. Ordinary Parent
feedback entry does not qualify child error-report entry. If the same-draft
language-change/reopen history cannot be completed through a supported public
route, preserve the missing binding; no forced errors, hidden calls or private
draft/context writes. Check independent entry and wrong child/owner refusal.

## Shared implementation

Reuse `overlay_about_scope`, `open_overlay_about`, shared feedback/text
operations and the qualified 187o report worker through
[AccessibleUI](../../../tests/e2e/accessible_ui.py).
Keep child session ownership distinct from the kiosk despite shared GTK IDs.

## Implementation entry

Planned selector: `check_e2e_overlay_dialog_language`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_overlay_dialog_language`.
Retain affected overlay About, real report-entry and language-selection qualifications. Do not send feedback.
