# 150 — Submit one authorized synthetic report and read success

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

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

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_feedback_send
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **150** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
