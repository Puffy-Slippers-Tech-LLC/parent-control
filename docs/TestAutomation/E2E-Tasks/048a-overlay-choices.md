# 048a — Qualify overlay Escape and invalid durations

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add Escape, invalid-custom submission with no authentication, and overlay FLOW04 composition. Reuse 048e's valid choices/Cancel and preserve distinct exit observations.

Reuse the delivered scope of tasks **048e** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048** — DESK12, REQUEST02 direct entry, REQUEST13 panel entry and REQUEST03 readback.
- **014** — FLOW04 kiosk.
- **047** — APP04; FLOW08 native usable-app scope.
- **048e** — REQUEST04/05/06/08 overlay valid choices and REQUEST11/12 Cancel.

## Implementation

Reuse the shared form operations with explicit overlay selectors and the fixed child. Qualify approver/duration, custom text, soft-app choice, estimate, Cancel and Escape; compose overlay FLOW04 only after those bindings. Mute and authenticated outcomes belong to their later scoped capabilities.

Use the [qualified valid-value/Cancel slice](../E2E-Building-Blocks.md#valid-overlay-choice-and-cancel-qualification)
for exact shared callables and remaining scope. Reuse `KioskRequestJourney`,
`journey_blocks.overlay_entry`, `native_usable_app('command', child='child')`,
`overlay-valid-*`, `text-overlay-fraction-*`, `overlay-request-cancel`,
`overlay_desktop` and declared `JourneyPlan.activity_checks` endpoints.
[`overlay_valid_choices.py`](../../../tests/e2e/overlay_valid_choices.py) is the
finite qualification declaration; shared libraries own the mechanics. Its
independent entry reads the remembered zero-duration/Jamie/excluded choices,
then selects 300 seconds. Keep the new Escape/invalid/FLOW04 slice and exit
observations distinct; do not treat the prior valid-value pass as those outcomes.

## Live VM acceptance

In separate live attempts with publicly prepared usable child time, record an app activity, open the overlay, change each declared choice and read it back. Cancel or Escape must close the form and return to the same usable activity. Invalid custom text shows validation while an otherwise ready Request remains enabled; selecting it preserves the form and starts no authentication prompt. Child selection is refused.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_overlay_choices
```
