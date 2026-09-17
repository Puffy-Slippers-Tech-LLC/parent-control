# 102 — Compose expiry recovery through kiosk approval

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW11**. First scheduled consumer: [E2E-009, case 23](../E2E-Scenario-Recipes.md#e2e-009).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **062** — TIME04.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose DESK11, FLOW06, retained FLOW15 and APP02/04/03 with explicit retained-or-closed expectations. A legitimate unlock must precede activity inspection; the closed branch ends at APP02.

## Live VM acceptance

Let real child time expire, obtain a replacement through kiosk, unlock normally and observe the declared same usable activity or closed blocked app. Compare only earlier public observations; no claim about unseen events under lock.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_replacement
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
