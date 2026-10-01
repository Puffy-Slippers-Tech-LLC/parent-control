# 166 — Observe time denial after suspend and wake

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add wake after the real grant deadline and correct-password time-limit denial. Reuse 166a's suspend/wake route; daily suspended usage cannot substitute for elapsed-grant denial.

Tasks **166a** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

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

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_suspend
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
