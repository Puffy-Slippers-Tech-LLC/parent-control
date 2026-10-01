# 150 — Submit one authorized synthetic report and read success

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED11, FEED09 sending/success and FEED14 Parent feedback**. First scheduled consumer: [E2E-032, case 156](../E2E-Scenario-Recipes.md#e2e-032).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

Authorization is supplied by task 150a's exact reviewed profile. A changed or
expired authorization remains a blocker; do not request renewed permission for
an unchanged covered submission.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150a** — Concrete synthetic reports, recipient and authorization scope for FEED11 consumers.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the concrete reviewed profile and submission authorization from task 150a.
Compose FEED03/Privacy observations, one Send, FEED09 sending/success and FEED14
dismissal. Qualify these result projections through the supported real service
and dedicated recipient. Do not expand content, recipient or submission counts.

## Live VM acceptance

With authorized service configuration, submit once on the VM, observe the actual app response, dismiss confirmation and reopen feedback to observe clearing. No provider receipt probe or automatic repeat send. Planning is not sending authorization.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_feedback_send
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
