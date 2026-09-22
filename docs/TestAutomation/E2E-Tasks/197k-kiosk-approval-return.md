# 197k — Compose kiosk approval and retained child entry

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add new/open-form retained-child destinations. Reuse 197a's fresh-child branches; preserve all four explicit invocations in the cumulative FLOW20 contract.

Tasks **197a** supply the extracted operations through their maintained
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

Deliver **FLOW20 kiosk new/open form and fresh/retained child**. First scheduled consumer: [E2E-048, case 224](../E2E-Scenario-Recipes.md#e2e-048).
Read only the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and that consumer's selected recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052** — TIME01 child-desktop presence and limits-off absence.
- **197a** — FLOW20 kiosk new/open form with fresh-child destination.

Use maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose kiosk FLOW04 and FLOW05, then the explicitly fresh/retained child FLOW15 entry and TIME01/UI12. Receive GDM or an independently open station form as declared. Reuse the shared FLOW20 argument/result contract; do not depend on overlay qualification, open a session implicitly or alter daily/app policy.

## Live VM acceptance

In one fresh guarded VM attempt, qualify four explicit invocations: new-form/fresh-child, open-form/retained-child, new-form/retained-child and open-form/fresh-child. Prepare each entry through normal public actions; the final fresh entry follows a declared child logout. Approve once per invocation. Require success confirmation, automatic station exit, the declared child entry and countdown within prebound public/elapsed-time intervals. Supply the open-form entries independently of FLOW20; missing entry modes refuse without repair. No expiry wait or unrelated choice matrix is needed.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_kiosk_approval_return
```

The selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract).
Require independent valid entry, wrong-entry refusal and owned live VM cleanup.
Host checks and a diagnostic slice do not establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **197k** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
