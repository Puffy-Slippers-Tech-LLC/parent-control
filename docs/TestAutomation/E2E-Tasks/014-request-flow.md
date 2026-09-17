# 014 — Compose prepared request choices

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW04 kiosk**. First scheduled consumer: [E2E-015, case 47](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **012a** — REQUEST04 duration; REQUEST05/06/08 and REQUEST09 invalid-input branch, kiosk.
- **013** — REQUEST11/12 kiosk Cancel and Escape.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose kiosk REQUEST01 → REQUEST03/04/05/06/08 in the documented order with explicit child, approver, duration and app choice. Receive an independently prepared enabled target; the composite does not change Parent policy.

## Live VM acceptance

On the live VM, enable the target through Parent with UI17/PARENT08 and use DESK03 to reach GDM. In the station, prepare a request, read back all chosen values and estimate, then exit normally. Re-enter from an independent GDM state and reproduce the result with fresh stage IDs.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_request_flow
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
