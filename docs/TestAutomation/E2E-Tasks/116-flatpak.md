# 116 — Observe Flatpak command denial and closure

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add publicly configured Hard/Soft command denial and expected closure, preserving usable A. Reuse 116b's activity and new-window route; do not reimplement package installation.

Tasks **116b** supply the extracted operations through their maintained
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

Deliver **APP01/02/03/04 and FLOW08 Flatpak command route**. First scheduled consumer: [E2E-019, case 104](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **116p** — FIX04 Flatpak assets; LIFE04 fixed Flatpak installation profile.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **116b** — APP01/02/03/04 and FLOW08 Flatpak command usable/new-window route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the qualified FIX04/LIFE04 Flatpak profile from task 116p in a fresh attempt.
Qualify APP01/02/03 for the fixed Flatpak command route, then APP04 activity identity
and FLOW08. Register the supported new-window command so presenting an existing
window cannot pass a new launch. Use repository-owned fixture IDs. Preserve the
qualified installation scope; do not add package installation to this slice.

## Live VM acceptance

On the VM, use the declared Flatpak command to launch each required fixture and observe normal input effects. Capture S, open a distinguishable second instance and prove the earlier activity remains. Through Parent, apply Hard and Soft blocks and require explicit command denial and the expected closure, with A still usable. A missing supported asset, new-instance route or public observation blocks the affected consumer.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_flatpak
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
Check **116** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
