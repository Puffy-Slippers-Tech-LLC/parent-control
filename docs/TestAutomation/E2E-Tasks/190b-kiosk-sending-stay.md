# 190b — Keep a sending kiosk report open after Close

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED09 retry and FEED17/18 kiosk stay-open branch**. Named consumer: task **190k** and any
complete cases released directly by this slice in the canonical queue.

**Gate:** Authorization for the submission, public cooldown-error entry and safe normal connectivity control are required.

The declared warning/stay-open branch is also unimplemented: current
`FeedbackDialog._hide_draft` stops a busy error report directly, without a
confirmation or stay response. Preserve FEED17/18's required branch and keep
this task pending until it is available through normal public controls; direct
stop cannot substitute for staying open.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150k** — FEED11, FEED09 success and FEED14 kiosk; gate in brief.
- **193a** — Owned VM Internet isolation/recovery; no Parent retry or toggle history.

## Implementation

Reuse the exact reviewed sending authorization and public connectivity route. Bind Close warning and the stay-open response while this surface is retrying; preserve its actual destination and no-replay guards.

Extend `AccessibleUI.feedback_snapshot` / `FeedbackStateObservation` and the
shared feedback API facade for sending/retry and FEED17/18. Reuse LIFE06's
`InternetIsolation` directly; Parent's toggle/retry journey is not part of
this surface's qualification. Keep one guarded Send and an independent
stay-open result.

## Live VM acceptance

In an authorized VM attempt, use LIFE06 to remove Internet access, Send once and observe retry. Close, read the warning and choose stay; independently require the report still open. Reconnect within the retry window, observe the same submission succeed and use the already-qualified success exit for cleanup.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_kiosk_sending_stay
```
