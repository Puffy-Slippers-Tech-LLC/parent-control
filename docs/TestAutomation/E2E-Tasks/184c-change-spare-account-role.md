# 184c — Change a spare approver's role through Users

Estimate: 25–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **ACCOUNT02 change-role**. First scheduled consumer: [E2E-040, case 182](../E2E-Scenario-Recipes.md#e2e-040).
Read the [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **184a** — AUTH04 Users Unlock; ACCOUNT01.
- **009** — UI16.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the normal role selector for the registered spare approver. Reuse ACCOUNT01 and the qualified Users authentication; retain the active Jamie administrator. Observe the explicit chosen role after confirmation without account-service calls.

Use the actual Settings role selector and public role readback for the spare only. Refuse protected/wrong accounts and ambiguous roles. The complete consumer must independently observe public approver eligibility; it cannot infer that result from account-service state.

## Live VM acceptance

On the live VM, read the spare Sam approver's administrator role, change it to standard through Users and independently verify the row and retained Jamie administrator. Cancel an uncommitted role change in a separate attempt and compare the original role. This qualifies role changes, not remembered request selectors.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_change_spare_account_role
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
Check **184c** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
