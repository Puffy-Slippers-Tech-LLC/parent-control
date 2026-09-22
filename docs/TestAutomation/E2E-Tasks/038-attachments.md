# 038 — Add, inspect, preview and remove attachments

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FEED06, FEED07, FEED12, FEED13**. First scheduled consumer: [E2E-031, case 152](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **037** — FILE03 installed feedback open/cancel; actual provider binding.
- **010** — UI17 Parent Screen time limit binding; installed qualification and owned cleanup passed.
- **031** — FEED09 validation/control snapshots.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend FIX04 with bounded synthetic files. Implement add/list result, one item's name/size/order, optional offered preview, and removal with exact remaining list. No private storage reads; unoffered preview is explicitly inapplicable.

Task 037 qualifies the installed caller's actual Open/Cancel route. Reuse only that recorded provider binding and retain exact selection/caller-result checks. Repository-owned attachment and editor controls use public IDs; provider semantics never replace them.

## Live VM acceptance

On the installed VM, add multiple synthetic files, read their names/sizes, preview only if offered, remove one and compare the remaining list. Qualify count and per-file rejection. Exclude diagnostics through the public toggle and qualify the declared 8 MiB aggregate boundary. The complete filename, mixed-selection and original-file-change matrix belongs to case 154; private draft bytes are never inspected.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_attachments
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
Check **038** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
