# 044a — Return to an already-open window on one desktop

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **DESK10 same-desktop window switching**. First scheduled consumer: [E2E-031, case 153](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001t** — FILE01/02/06 terminal command, help/denial projections and normal close/return.
- **009** — UI16.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement bounded normal app-switcher navigation to an explicitly identified existing window. Independently observe its active state. Bind Parent, Terminal and feedback first; the diagnostic-viewer binding is qualified by FEED08. Do not log out, unlock, relaunch a window or restore fields.

Keep switcher discovery and navigation inside the qualified Shell adapter. Reacquire each application's owner after switching and compare preserved public draft/state; no title or position selects a repository-owned surface. Tests reject absent/wrong windows, focus loss and uncertain input.

## Live VM acceptance

Open Parent feedback with a synthetic draft and Terminal on the same live desktop. Switch to Terminal and back normally, verify the intended active window each time and compare the unchanged draft before editing. An absent target must fail without relaunching it. No retained-user or child-login work is needed.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_window_switch
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
Check **044a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
