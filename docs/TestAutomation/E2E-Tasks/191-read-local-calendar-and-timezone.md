# 191 — Read local calendar and timezone

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **TIME05 including DESK12 clock binding**. First scheduled consumer: [E2E-044, case 196](../E2E-Scenario-Recipes.md#e2e-044).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces), [related block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **003** — DESK02, DESK03, DESK04.
- **044a** — DESK10 same-desktop window switching.
- **052c** — TIME03.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the showing desktop clock, calendar date/time and normal Date & Time settings. Compose public reads and ordinary closes only; reading time never changes it.

## Live VM acceptance

On the VM, read the actual date/time and timezone, close the views and return to the same desktop. Record available display precision. Calendar scenarios still require their own naturally eligible date/window; this block can qualify on an ordinary day.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_calendar
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
