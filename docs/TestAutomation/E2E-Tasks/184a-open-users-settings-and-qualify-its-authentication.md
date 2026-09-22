# 184a — Open Users settings and qualify its authentication

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **AUTH04 Users Unlock; ACCOUNT01**. First scheduled consumer: [E2E-040, case 179](../E2E-Scenario-Recipes.md#e2e-040).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **048d** — AUTH02 overlay approval; REQUEST11/12 success and automatic child return.
- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the ordinary Settings launcher and Users page. Qualify the selected administrator, action and sole empty masked recipient before two fresh proofs and one secret entry when Unlock requests authentication. Read the bounded declared account list.

Use readily available Settings Builder IDs within the qualified Users page and scoped provider semantics for remaining controls. Extend the Shell prompt machinery from 048d to this distinct Users Unlock challenge; request-approval context cannot authorize Settings. Reject wrong page/action/administrator and independently observe unlocked controls.

## Live VM acceptance

On the VM, open Users normally, unlock through the real administrator challenge when offered, and read the expected list. Wrong-action, wrong-account and stale proofs must refuse in safety checks. An already unlocked independent entry must also work.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_open_users_settings_and_qualify_its_authentication
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
Check **184a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
