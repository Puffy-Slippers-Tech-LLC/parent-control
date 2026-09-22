# 191 — Read timezone and compose local calendar observations

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **TIME05 Settings Date & Time binding and composed calendar observation**. First scheduled consumer: [E2E-044, case 196](../E2E-Scenario-Recipes.md#e2e-044).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces), [related block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **191a** — TIME05 Shell calendar and DESK12 clock binding.
- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse task 191a's qualified Shell clock/calendar reads. Qualify only the Settings
Date & Time page's owner, public timezone/date/time fields, available precision and
normal close/return. Bind parsing to the recorded provider locale. Compose TIME05
from those separately qualified observations without changing the clock/timezone.
Calendar scenarios retain their actual scheduled windows.

## Live VM acceptance

On the VM, read the actual date/time and timezone, close the views and return to the same desktop. Record available display precision. Calendar scenarios still require their own naturally eligible date/window; this block can qualify on an ordinary day.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_read_local_calendar_and_timezone
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
Check **191** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
