# 043a — Qualify retained unlock and return from the lock screen

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **GDM02 retained-child lock entry; DESK08/11**. First scheduled consumer: [E2E-014, case 40](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), [related block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.
- **042** — DESK05, DESK06, DESK07.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify GDM02(child, destination=lock) for the already observed retained child session. Compose DESK06, two fresh DESK07 proofs, UI19, submission and the declared success/time-denial observation. Bind the normal lock-screen Switch User route separately from rejected GDM; never reuse a GDM secret proof on the lock surface.

## Live VM acceptance

On the VM, enter the child with positive daily time, lock normally and unlock with the intended correct credential. In an independent attempt, prepare positive time in Parent, log Parent out normally and admit the child. Switch User from the child, sign Parent in fresh and change daily time to zero through the UI. Switch to GDM and select that retained child through GDM02; require its lock challenge and explicit time-limit denial after correct authentication. Reach GDM through the observed control. Refuse stale/wrong-recipient proofs and pass credential/cleanup checks before live execution. This configured-zero qualification makes no natural-expiry claim.

Record the same desktop/activity before locking and compare it after successful unlock; a newly launched window or fresh login cannot satisfy retention. Preserve two fresh same-user lock proofs, single-use delivery, wrong-recipient refusal and no replay after uncertain input.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_retained_unlock
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
Check **043a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
