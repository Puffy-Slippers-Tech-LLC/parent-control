# 024 — Prepare empty kiosk account profiles

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FIX03 no-child/no-approver profiles**. First scheduled consumer: [E2E-017, case 54](../E2E-Scenario-Recipes.md#e2e-017).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **012** — REQUEST04 kiosk child/approver; REQUEST08 unavailable state.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend the existing account fixture only for no-child and no-approver profiles, preserving fixed identities, the request station, ownership and outer cleanup. Reuse applicable FIX02 mechanics without turning it into arbitrary mutation. No approval prompt or product-policy mutation is needed.

## Live VM acceptance

In separate guarded VM attempts, enter the station for each empty profile and observe the exact empty choice set, unavailable explanation and disabled Request with no prompt. Pass identity/cleanup refusal regressions first. Multiple/ineligible-approver profiles remain pending.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_kiosk_fixtures
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
