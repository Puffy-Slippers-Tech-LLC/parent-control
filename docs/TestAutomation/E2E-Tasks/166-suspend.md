# 166 — Observe time denial after suspend and wake

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add wake after the real grant deadline and correct-password time-limit denial. Reuse 166a's suspend/wake route; daily suspended usage cannot substitute for elapsed-grant denial.

Tasks **166a** supply the extracted operations through their maintained
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

Deliver **LIFE03**. First scheduled consumer: [E2E-022, case 124](../E2E-Scenario-Recipes.md#e2e-022).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052a** — TIME02 minute/final-second ticks.
- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.
- **043a** — GDM02 retained-child lock entry; DESK08/11.
- **052c** — TIME03.
- **166a** — LIFE03 normal suspend/wake with active grant.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose system controls, guarded real wait, supported wake input and observed actual return surface. Keep subsequent unlock separate; retained activity comparisons require successful legitimate access.

Use the shared LIFE03 supported system suspend command, guarded real wait and supported wake input. Record the displayed return/lock state independently; backend service state cannot establish the customer result. Task 043a owns subsequent unlock and task 052c owns the bounded real wait.

## Live VM acceptance

In separate VM attempts, use FLOW13 to prepare a real active grant with zero daily allowance. Suspend normally and wake through supported input, once before and once after that grant's elapsed deadline. Observe the actual lock/desktop and use DESK08 to require successful access or specific time-limit denial. Suspended daily usage alone cannot prepare elapsed-time denial.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_suspend
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
Check **166** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
