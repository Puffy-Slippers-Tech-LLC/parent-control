# 150p — Send an authorized Parent error report

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED11, FEED09 success and FEED14 Parent error-report**. First scheduled consumer: [E2E-047, case 222](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

**Gate:** Explicit authorization must cover this synthetic Parent error-report submission.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **186** — PARENT15 failed-save; FEED15 Parent and report-close binding.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the automatically opened Parent report to one reviewed synthetic Send and its actual success/dismissal route. Reuse the public rejected-pattern prefix and shared feedback operations; Parent has no request Report toggle.

## Live VM acceptance

On the VM, reject the declared wildcard, review the resulting report and Privacy, submit once with explicit authorization and read service acceptance. Dismiss thanks and require Parent with its last confirmed policy. Do not claim a station exit.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_parent_error_send
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
