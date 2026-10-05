# 310a — Qualify child panel language refresh and presentation

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **043c** — Public retained-child session unlock/resume.
- **052** — Owned child countdown observations.
- **181m** — Public countdown tooltip/context-menu operations via 181h.
- **300i** — Riley overlay language Save/Cancel and command relaunch.
- **307a** — Installed Hebrew observation contract, requiring separate Shell qualification.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify Riley's panel binding for English → Hebrew → English through overlay
Preferences. Close the overlay normally and independently observe refreshed
panel visible/accessibility text, countdown explanation and animation menu.
Reopen the overlay, confirm the shared choice, close it, then resume the child
session through the qualified retained-session route and observe refreshed
presentation again. Require Hebrew/restored English logical text,
correct mixed text/numbers and stable IDs through a separately qualified Shell
observation route.

Capture public time/policy before changing language and compare afterwards with
declared monotonic elapsed bounds; no reset, extra access or policy/app changes.
This slice reads bounded countdown samples; task 310 composes qualified TIME02
progression and TIME04 natural expiry. Reuse 181h/181m for tooltip/menu mechanics;
do not introduce coordinate hover/click input. Apply the mandate's no-visual
acceptance rule; missing public text or identity keeps a gate, and GTK qualification
does not transfer to Shell.

## Shared implementation

Reuse `AccessibleUI.child_countdown`, `overlay_panel_target`, LANG01,
[countdown.py](../../../tests/e2e/countdown.py) and shared overlay/session
workers. Extend their public observation schema for the exact Shell language
binding, preserving active Riley, duplicate-ID and uncertain-input guards.

## Implementation entry

Planned selector: `check_e2e_panel_language_refresh`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_panel_language_refresh`.
Retain affected shell-panel, overlay-language, countdown and tooltip/menu qualifications.
