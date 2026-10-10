# 065a — Prepare grant-only time and explicit revoke-first entry

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW13 grant-only profile and explicit revoke preparation**. Named consumer: task **065** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **051** — FLOW13 daily-only, fresh/same Parent entry with observed G=0.
- **050** — PARENT17, PARENT18.

## Implementation

Compose real kiosk approval at daily=0 with retained Parent readback and final GDM return. Reuse the initial public PARENT09 observation when G is already zero. Require explicit revoke-first input when clearing an existing grant and fresh balance readback after that mutation; never clear it silently.

Extend the shared FLOW13 declaration/worker from 051, composing
`kiosk_approved_flow.obtain_time` and `onpc_request_flow::obtain_time` with
`onpc_parent::open_for_child` retained-window entry. The existing approval
leaves accept only 75 seconds/soft included; add the recipe's 2-minute grant
binding explicitly and qualify its public D=0/G>0 result. Do not replay kiosk
rejection, immediate-exit or retained-child qualifications to prepare the profile.

Give the shared request leaf validated caller-owned duration arguments for the
later recipes' 3-minute replacement, 4-minute delayed-approval preparation,
10-minute enablement history and 20-minute active lifecycle grant. Those values
are not implemented by today's fixed 75-second leaf. Keep one representative
2-minute profile qualification here; later cases bind their finite values and
own the unchanged-deadline, arithmetic and recovery assertions without replaying
this qualifier. Do not hide those later durations or policy changes in FLOW13.

## Live VM acceptance

Observe D=0/G>0 after real approval and finish at GDM. In a separate attempt, explicitly revoke first and independently read G=0 before preparing the grant; an unexpected undeclared existing grant refuses.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_grant_only_profile
```
