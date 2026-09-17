# 012 — Select kiosk accounts and read availability

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **REQUEST04 kiosk child/approver; REQUEST08 unavailable state**. First scheduled consumer: [E2E-017, case 57](../E2E-Scenario-Recipes.md#e2e-017).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **011** — REQUEST01, REQUEST03.
- **017** — PARENT08 snapshot saved/control states.
- **003** — DESK02, DESK03, DESK04.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind UI15 to the offered child/approver selectors, then compose REQUEST04 with independent REQUEST03 readback. Read each exact eligible choice set before selection. Bind REQUEST08's unavailable explanation and distinguish disabled selectors from empty lists. Duration editing, numeric estimates and toggles remain pending.

## Live VM acceptance

In one fresh live attempt, disable the target in Parent, observe saved state, Switch User and enter the station. Read its disabled-child explanation, unavailable Request and absence of an authentication prompt. In another attempt, enable the target publicly and observe saved state before station entry; inspect offered lists, select the intended eligible child/approver and independently read the selection. Do not activate disabled controls. Empty-account fixture profiles are qualified by their own consumer.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_request_choices
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
