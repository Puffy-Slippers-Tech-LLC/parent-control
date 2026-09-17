# 150p — Send an authorized Parent error report

Estimate: 20–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FEED11, FEED09 success and FEED14 Parent error-report**. First scheduled consumer: [E2E-047, case 222](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

**Gate:** Explicit authorization must cover this synthetic Parent error-report submission.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **186** — PARENT15 failed-save; FEED15 Parent and report-close binding.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the automatically opened Parent report to one reviewed synthetic Send and its actual success/dismissal route. Reuse the public rejected-pattern prefix and shared feedback operations; Parent has no request Report toggle.

## Live VM acceptance

On the VM, reject the declared wildcard, review the resulting report and Privacy, submit once with explicit authorization and read service acceptance. Dismiss thanks and require Parent with its last confirmed policy. Do not claim a station exit.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_parent_error_send
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
