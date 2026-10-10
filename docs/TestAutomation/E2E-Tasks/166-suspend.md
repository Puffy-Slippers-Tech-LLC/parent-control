# 166 — Observe time denial after suspend and wake

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add wake after the real grant deadline and specific time-limit denial with no desktop access. Reuse 166a's suspend/wake route; daily suspended usage cannot substitute for elapsed-grant denial.

Reuse the delivered scope of tasks **166a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **LIFE03**. First scheduled consumer: [E2E-022, case 125](../E2E-Scenario-Recipes.md#e2e-022).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **166a** — LIFE03 normal suspend/wake with active grant.

## Implementation

Reuse 166a's shared LIFE03 suspend/wake route and add the post-deadline result. Use the guarded real wait from 052c and 043a's [qualified retained-child result branches](../E2E-Building-Blocks.md#retained-child-time-restriction-and-greeter-return-qualification). Record the actual return/lock state independently, then observe the specific time-limit denial and no desktop access. A native restriction without a password field requires no credential input and makes no authenticated-denial claim. Deliver the intended correct credential only when the observed, qualified route supplies a real authentication challenge; never manufacture one. Backend service state cannot establish the customer result. Preserve the same attempt and retained session across the expected guest transport loss.

## Live VM acceptance

In a fresh guarded VM attempt, use FLOW13 to prepare a real active grant with
zero daily allowance. Suspend normally and wake through the qualified supported
input after that grant's real elapsed deadline. Independently observe the actual
return/lock surface and use DESK08's corresponding result branch to require
specific time-limit denial with no desktop access. Qualify this new post-suspend
result and retained-session continuity; configured-zero denial cannot qualify it.
Reuse 166a's unchanged pre-deadline and entry-safety qualification, rerunning only
affected branches if shared code changes. Cover new post-deadline refusal logic
in focused harness checks; its live attempt retains every current identity and
recipient guard. Evidence supplies no saved VM state. Suspended daily usage
alone cannot prepare elapsed-time denial.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_suspend
```
