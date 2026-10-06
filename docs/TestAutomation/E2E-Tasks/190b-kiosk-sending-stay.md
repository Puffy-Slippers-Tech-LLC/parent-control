# 190b — Keep a sending kiosk report open after Close

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED09 retry and FEED17/18 kiosk stay-open branch**. Named consumer: task **190k** and any
complete cases released directly by this slice in the canonical queue.

**Gate:** Authorization for the submission, public cooldown-error entry and safe normal connectivity control are required.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150k** — FEED11, FEED09 success and FEED14 kiosk; gate in brief.
- **152** — FEED09 Parent retry/recovery over qualified LIFE06; gate in brief.

## Implementation

Reuse the exact reviewed sending authorization and public connectivity route. Bind Close warning and the stay-open response while this surface is retrying; preserve its actual destination and no-replay guards.

## Live VM acceptance

In an authorized VM attempt, use LIFE06 to remove Internet access, Send once and observe retry. Close, read the warning and choose stay; independently require the report still open. Reconnect within the retry window, observe the same submission succeed and use the already-qualified success exit for cleanup.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_kiosk_sending_stay
```
