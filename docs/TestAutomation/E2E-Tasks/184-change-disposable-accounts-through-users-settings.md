# 184 — Create the registered spare child

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add creation-password recipient proofs and single-use delivery, commit one registered spare child and independently read its resulting row. Reuse 184e's wizard/Cancel; preserve sealed capture and cleanup.

Tasks **184e** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **ACCOUNT02 add-child; AUTH04 account-creation password fields**. First scheduled consumer: [E2E-040, case 179](../E2E-Scenario-Recipes.md#e2e-040).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **184a** — AUTH04 Users Unlock; ACCOUNT01.
- **009** — UI16.
- **184e** — ACCOUNT02 add-child nonsecret fields and Cancel.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the finite add-child wizard and its standard-user role. Nonsecret fields use UI16/UI15; each creation password field gets two fresh AUTH04 proofs and one UI19 input. Refuse unregistered identities before input. Preserve the active administrator and station.

Qualify the actual Users wizard and its new-account password recipients, protect baseline accounts and refuse duplicate/wrong-account input. Preserve sealed capture, cleanup and the separate Parent live-discovery assertion in case 179.

## Live VM acceptance

On the live VM, add one registered spare standard child through Users and independently read its resulting row/list. Qualify creation-secret recipient checks before input. In a separate attempt, cancel the wizard and require the original list unchanged. Parent discovery is checked by the complete scenario.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_change_disposable_accounts_through_users_settings
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
Check **184** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
