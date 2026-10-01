# 190a — Keep a sending overlay report open after Close

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED09 retry and FEED17/18 overlay stay-open branch**. Named consumer: task **190o** and any
complete cases released directly by this slice in the canonical queue.

**Gate:** Authorization for the submission, public cooldown-error entry and safe normal connectivity control are required.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150o** — FEED11, FEED09 success and FEED14 overlay; gate in brief.
- **152** — FEED09 Parent retry/recovery over qualified LIFE06; gate in brief.

## Implementation

Reuse the exact reviewed sending authorization and public connectivity route. Bind Close warning and the stay-open response while this surface is retrying; preserve its actual destination and no-replay guards.

## Live VM acceptance

In an authorized VM attempt, use LIFE06 to remove Internet access, Send once and observe retry. Close, read the warning and choose stay; independently require the report still open. Reconnect within the retry window, observe the same submission succeed and use the already-qualified success exit for cleanup.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_sending_stay
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
