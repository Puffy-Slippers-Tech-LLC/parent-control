# 013 — Observe request results and exits

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **REQUEST11/12 kiosk Cancel and Escape**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **011** — REQUEST01, REQUEST03.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement named form results and exit routes using fresh observations. Start with kiosk Cancel/Escape and no active authentication prompt; approval, rejection and overlay destinations qualify with their consumers.

## Live VM acceptance

On the VM, enter kiosk and separately exit through Cancel and Escape; prove form disappearance plus usable GDM. Verify cancellation has no error. An active authentication dialog cannot be dismissed by guessing a form-exit route.

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
