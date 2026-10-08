# 129a — Reach an overlay request from fullscreen gameplay

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **DESK12 fullscreen reveal; overlay/game return**. First scheduled consumer: [E2E-024, case 131](../E2E-Scenario-Recipes.md#e2e-024).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **129** — APP05/FLOW10 fullscreen play.
- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.

## Implementation

Qualify the game's supported normal Shell reveal sequence, then use REQUEST13 to open one overlay through the panel. This is the explicit graphical launch exception for E2E-024/fullscreen. Bind the route back to the same game via DESK10 and compare its earlier activity. A missing panel route blocks these request consumers without blocking fullscreen expiry.

## Live VM acceptance

On the live VM, play fullscreen, capture activity, expose the panel normally and open the request overlay. Read the intended fixed child, cancel through the qualified form control and return to the same usable game activity. Repeat from an independent fullscreen entry and reject wrong-window proofs.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_fullscreen_request
```
