# 166a — Suspend and wake before a grant expires

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **LIFE03 normal suspend/wake with active grant**. Named consumer: task **166** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052a** — TIME02 minute/final-second ticks.
- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.
- **043a** — GDM02 retained-child lock entry; DESK08/11.
- **052c** — TIME03.

## Implementation

Use the shared LIFE03 system suspend command, supported wake input and independent return-surface observation. Reuse a real grant-only profile, guarded wait and legitimate unlock; backend power state does not prove the customer result.

Bind one supported guest suspend command and one existing owned-VM wake route.
Keep the host awake and preserve the attempt/VM identity across the expected
temporary guest transport loss. Resume observation of the same attempt after
wake; no power-settings UI, host suspend, RTC setup or wake-method matrix.

## Live VM acceptance

Prepare a real active grant with zero daily allowance, suspend normally, wake before its deadline, independently observe the return surface and unlock successfully. Qualify independent valid entry, wrong-owner refusal and continuity of the existing activity.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_suspend_active_grant
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
