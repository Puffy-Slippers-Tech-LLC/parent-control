# 190k — Confirm stopping a sending kiosk report

Estimate: 25–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FEED09 retry and FEED17/18 kiosk**. First scheduled consumer: [E2E-047, case 219](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** Authorization for the submission, public cooldown-error entry and safe normal connectivity control are required.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **150k** — FEED11, FEED09 success and FEED14 kiosk; gate in brief.
- **152** — FEED09 Parent retry/recovery over qualified LIFE06; gate in brief.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind retry on the kiosk report after normal public disconnection, then implement FEED17 before FEED18. Declare stay-open and Stop sending and close responses and their exact destinations; stopping cannot recall an already accepted request.

## Live VM acceptance

On the VM with an authorized synthetic report, disconnect normally, Send once and observe retry. Attempt Close, read the warning and choose stay; require the report still open. Close again and explicitly Stop; require report disappearance and GDM. Restore connectivity through Parent.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_confirm_stopping_a_sending_kiosk_report
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
