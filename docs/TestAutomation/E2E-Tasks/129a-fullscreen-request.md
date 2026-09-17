# 129a — Reach an overlay request from fullscreen gameplay

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **DESK12 fullscreen reveal; overlay/game return**. First scheduled consumer: [E2E-024, case 129](../E2E-Scenario-Recipes.md#e2e-024).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **129** — APP05/FLOW10 fullscreen play.
- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify the game's supported normal Shell reveal sequence, then reuse REQUEST02 to open one overlay. Bind the route back to the same game via DESK10 and compare its earlier activity. A missing panel route blocks these request consumers without blocking fullscreen expiry.

## Live VM acceptance

On the live VM, play fullscreen, capture activity, expose the panel normally and open the request overlay. Read the intended fixed child, cancel through the qualified form control and return to the same usable game activity. Repeat from an independent fullscreen entry and reject wrong-window proofs.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_game
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After live qualification and cleanup, update the callable, exact qualified scope
and status in [E2E-Building-Blocks.md](../E2E-Building-Blocks.md), and reconcile
the first consumer's status in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
A slice alone leaves the full scenario pending. If any complete E2E scenario
passed, run `tools/generate_test_coverage.sh` after that case's cleanup; it runs
`tools/generate_test_coverage.py`. Require successful generation before check-off.

Check this task in the [master](../E2E-Execution-Plan.md), then remove this brief
when its enduring context is in source/contracts and replace its master link
with plain text. Validate changed Markdown with `tools/read-only links`.
Keep normal runner artifacts; no new evidence document or accumulated history.
