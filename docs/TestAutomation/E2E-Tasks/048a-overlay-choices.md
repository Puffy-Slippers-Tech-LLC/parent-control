# 048a — Qualify overlay Escape and invalid durations

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add Escape, invalid-custom submission with no authentication, and overlay FLOW04 composition. Reuse 048e's valid choices/Cancel and preserve distinct exit observations.

Tasks **048e** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048** — DESK12, REQUEST02 direct entry, REQUEST13 panel entry and REQUEST03 readback.
- **014** — FLOW04 kiosk.
- **047** — APP04; FLOW08 native usable-app scope.
- **048e** — REQUEST04/05/06/08 overlay valid choices and REQUEST11/12 Cancel.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the shared form operations with explicit overlay selectors and the fixed child. Qualify approver/duration, custom text, soft-app choice, estimate, Cancel and Escape; compose overlay FLOW04 only after those bindings. Mute and authenticated outcomes belong to their later scoped capabilities.

## Live VM acceptance

In separate live attempts with publicly prepared usable child time, record an app activity, open the overlay, change each declared choice and read it back. Cancel or Escape must close the form and return to the same usable activity. Invalid custom text shows validation while an otherwise ready Request remains enabled; selecting it preserves the form and starts no authentication prompt. Child selection is refused.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_overlay_choices
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
