# 129a — Reach an overlay request from fullscreen gameplay

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **DESK12 fullscreen panel API entry; overlay/game return**. First scheduled consumer: [E2E-024, case 131](../E2E-Scenario-Recipes.md#e2e-024).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **129** — APP05/FLOW10 fullscreen play.
- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.

## Implementation

Use REQUEST13's existing shared `child-panel` Application UI API operation to activate `child-request-button` while the real game remains fullscreen. This preserves the recipe's panel-entry integration without a Shell reveal, focus or presentation prerequisite under [product-focused journeys](../E2E-Execution-Contracts.md#product-focused-journeys). Bind the return to the same game via DESK10 and compare its earlier activity. Keep logical availability and target ownership guards in the shared API operation.

## Live VM acceptance

On the live VM, play fullscreen, capture activity and open the request overlay through REQUEST13's panel API operation. Read the intended fixed child, cancel through the qualified form control and return to the same usable fullscreen game activity. Repeat from an independent fullscreen entry and reject wrong-window proofs. Hidden panel presentation alone is no blocker; an unavailable or refused product operation or missing same-game return remains pending.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_fullscreen_request
```
