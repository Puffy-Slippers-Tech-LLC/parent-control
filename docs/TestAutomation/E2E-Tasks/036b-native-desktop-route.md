# 036b — Launch native fixtures from the desktop

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **APP01/02/03 native desktop route**. First scheduled consumer: [E2E-019, case 68](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE07/04/05; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **035p** — FIX04 native assets; LIFE04 fixture installation.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the supported desktop entry and its public activation, then independently observe usable or blocked results. Use the existing verified assets and normal file operations for any required placement/trust action. Missing desktop support blocks this route only.

The installed desktop icon is owned by DING. Add its provider-specific icon/selection/activation binding with wrong-icon and ambiguous-owner refusal. Reuse the declared native fixture and qualified public placement/trust operations. Independently observe the owned fixture's usable result; search, terminal or file-manager activation cannot replace the desktop route.

## Live VM acceptance

On the live VM, activate the actual desktop entry, observe the real app window and perform a normal usability action. While an earlier S activity remains open, use a supported desktop gesture to launch and independently identify a second window; presenting the first window cannot pass. Apply a public Parent block and observe this route's declared blocked result. Qualify independently reached desktop entry and wrong-target refusal; terminal/file-manager activation is not desktop acceptance.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_native_desktop_route
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
Check **036b** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
