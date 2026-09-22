# 193 — Operate public connectivity controls

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **LIFE06**. First scheduled consumer: [E2E-033, case 157](../E2E-Scenario-Recipes.md#e2e-033).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003d** — DESK04 current Shell logout/confirmation route and independently observed GDM return.
- **010** — UI17 Parent Screen time limit binding; installed qualification and owned cleanup passed.
- **044a** — DESK10 same-desktop window switching.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the desktop's ordinary network controls and independent displayed connectivity observations. Preserve the guarded UI/ownership channel while offline, then reconnect. No feedback submission is needed.

Bind the declared connection and its actual Shell controls. Require independently displayed disconnected and connected states; do not infer them from the input's success. Wrong-control/owner and uncertain-input tests apply to both changes.

## Live VM acceptance

On the VM, disconnect through normal settings, read offline state, return to the existing Parent window and observe it usable, then reconnect and read connected state. If this route severs required observation with no supported recovery, record that exact prerequisite gap.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_operate_public_connectivity_controls
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
Check **193** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
