# 310a — Qualify child panel language refresh and presentation

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — Owned child countdown observations.
- **300i** — Riley overlay language Save/Cancel and command relaunch.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify Riley's missing panel language/time projection with one English → Hebrew
Save through overlay Preferences. Close the overlay normally and independently
observe the refreshed public countdown language and remaining time on the same
child desktop. Reuse independent entry and unchanged language input/owner guards;
the complete English → Hebrew → English history belongs to task 310, including
its observation after each Save. Require Hebrew public meaning and correct
remaining time through the shared `child-panel` Application UI API. Full
tooltip/menu translation and content combinations belong to host UI coverage;
public IDs and matching semantics remain automation guards.

Capture public time/policy before changing language and compare afterwards with
declared monotonic elapsed bounds; no reset, extra access or policy/app changes.
This slice reads bounded countdown samples; task 310 composes qualified TIME02
progression and TIME04 natural expiry. No tooltip/menu traversal or coordinate
hover/click input is needed for this result. Apply the mandate's no-visual
acceptance rule; missing public text or identity keeps a gate. Installed GTK
language evidence alone does not qualify the distinct product child-panel endpoint.

## Shared implementation

Reuse `AccessibleUI.child_countdown`, `overlay_panel_target`, LANG01,
[countdown.py](../../../tests/e2e/countdown.py) and shared overlay
workers. Read `child-remaining-time` canonical seconds and translated text;
extend their public observation schema for the exact panel language
binding, preserving active Riley, duplicate-ID and uncertain-input guards.

The current `CountdownObservation` projection contains presence, display text,
timestamp and stability only; it has no language or canonical-seconds field.
Implement that missing public panel projection and controller validation rather
than treating Parent-only 307a qualification as a panel binding. Reuse the
host `test_child_panel_refreshes_language_after_overlay_save` shared API path;
its preview pass supplies no installed language/time result.

## Implementation entry

Planned selector: `check_e2e_panel_language_refresh`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_panel_language_refresh`.
Retain affected child-panel API checks and scoped installed qualification of
the new projection. Reuse unchanged overlay-language/countdown qualifications;
do not repeat their matrices or task 310's complete history here.
