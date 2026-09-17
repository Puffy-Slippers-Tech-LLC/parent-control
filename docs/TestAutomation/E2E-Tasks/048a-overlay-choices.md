# 048a — Choose overlay values and cancel or escape

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **048** — DESK12, REQUEST02/03 overlay entry/readback.
- **014** — FLOW04 kiosk.
- **047** — APP04; FLOW08 native usable-app scope.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the shared form operations with explicit overlay selectors and the fixed child. Qualify approver/duration, custom text, soft-app choice, estimate, Cancel and Escape; compose overlay FLOW04 only after those bindings. Mute and authenticated outcomes belong to their later scoped capabilities.

## Live VM acceptance

In separate live attempts with publicly prepared usable child time, record an app activity, open the overlay, change each declared choice and read it back. Cancel or Escape must close the form and return to the same usable activity. Invalid custom text shows validation while an otherwise ready Request remains enabled; selecting it preserves the form and starts no authentication prompt. Child selection is refused.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_request_exit
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
