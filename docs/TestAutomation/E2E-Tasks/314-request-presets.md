# 314 — Saved request presets and units persist

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Estimate: 20–30 minutes. This planned general feature scenario has no assigned
case ID or executable and is not a kiosk confinement baseline prerequisite.

## Scope and prerequisites

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **012c** — Public request preset/custom-minutes/rest-of-day and soft choices.
- **014** — Prepared request, estimates and remembered choices.

Customer goal: saved request presets and unit conversions survive ordinary
preferences editing and reentry. This preserves the feature expansion removed
from C04s; Parent daily-allowance presets are a distinct operation.

## Implementation and acceptance

Read `tests/e2e/request_choices.py`, `request_flow.py`, shared Preferences/request
methods in `accessible_ui.py`, their worker route and host Preferences coverage.
Reuse existing shared API operations, adding only missing saved-result bindings.
Do not restore excluded native double-click automation or duplicate local widget
validation matrices. Use ordinary public preset editing and selection APIs.

Starting with Riley's recorded shipped presets and zero daily/grant, add a
10-minute preset; editor Save then main Save must persist 600 seconds on reopen.
Select then delete it and require the selected duration to remain Custom.
Custom `0.1` Hours reads 360 seconds. Restore shipped presets and Custom `1.25`
Minutes/75 seconds with soft inclusion; normal Cancel/reentry reproduces saved
choices. Read independently; no authentication, time grant or policy change.

Before implementation assign one new stable case and finite recipe, register
its complete shared worker binding, and qualify any missing saved-result API
slice through a bounded prerequisite. The selector is unassigned; no runnable
case is claimed. Use maintained host checks and installed acceptance, finite
timeouts, public restoration and owned cleanup. Regenerate coverage after the
complete scenario passes. Existing local value/validation coverage remains local.
