# 036b — Observe policy results for desktop launches

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add desktop-specific blocked results after a public Parent save. Reuse 036g/036h's usable and separate-window bindings; missing DING support remains a blocker.

Tasks **036g**, **036h** supply the extracted operations through their maintained
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

Deliver **APP01/02/03 native desktop route**. First scheduled consumer: [E2E-019, case 68](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **035p** — FIX04 native assets; LIFE04 fixture installation.
- **036h** — APP01/02 desktop separate-window route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse 036g's verified entry and shared command/API placement and trust
preparation. Bind its public desktop activation and independently observe usable
or blocked results. Missing desktop support blocks this route; do not install
another desktop extension or substitute a different launcher.

The installed desktop icon is owned by DING. Reuse 036g/036h's qualified
icon/activation and separate-window bindings with wrong-icon and ambiguous-owner
refusal. This task adds only the policy-result observations; it does not repeat
launcher preparation or add selection/menu permutations. Search, command or
file-manager activation cannot replace the tested desktop route.

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
