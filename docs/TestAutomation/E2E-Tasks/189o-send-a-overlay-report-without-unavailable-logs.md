# 189o — Send a overlay report without unavailable logs

Estimate: 25–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FEED11 without-logs and FEED09/14 overlay result**. First scheduled consumer: [E2E-046, case 211](../E2E-Scenario-Recipes.md#e2e-046).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

**Gate:** Both the genuine public collection-failure route and explicit authorization for this synthetic submission must be available.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **188o** — FEED16 overlay.
- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the explicit Send without logs action on overlay after observed collection failure and reviewed FEED03/FEED05 evidence. Qualify its actual acceptance and confirmation destination; use one input and no automatic retry by the test.

## Live VM acceptance

With the reviewed sending authorization, reproduce the qualified public collection failure on the VM, submit the declared report once without logs, observe service acceptance, dismiss thanks and require the overlay-specific final destination. Missing logs alone is not acceptance.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_collection_recovery
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
