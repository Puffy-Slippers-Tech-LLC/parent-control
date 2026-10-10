# 166a — Suspend and wake before a grant expires

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **LIFE03 normal suspend/wake with active grant**. Named consumer: task **166** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — TIME01 public child-desktop remaining balance.
- **065a** — FLOW13 grant-only preparation and explicit revoke-first entry.
- **043a** — GDM02 retained-child lock entry; DESK08/11.
- **052c** — TIME03.

## Implementation

Use the shared LIFE03 system suspend command, supported wake input and independent return-surface observation. Reuse a real grant-only profile, guarded wait and legitimate unlock; backend power state does not prove the customer result.

Consume only 065a's grant-only operation. A combined daily/grant profile and its
dominance qualification add no result to this zero-daily suspend boundary.

Bind one supported guest suspend command and one existing owned-VM wake route.
Keep the host awake and preserve the attempt/VM identity across the expected
temporary guest transport loss. Resume observation of the same attempt after
wake; no power-settings UI, host suspend, RTC setup or wake-method matrix.

LIFE03 has no registered callable/qualification yet. Add the bounded suspend
transition beside `InstalledJourney.submit_reboot` and the existing owned-VM
transport, without treating suspend as a boot change or restoring the attempt.
Reuse `real_interval.wait_real_interval` and the qualified DESK08 result reader;
the new operation must independently establish suspend/wake completion and the
same retained desktop/activity.

Observe the owned VM's actual suspend event/state before the single wake input,
then require the same boot/session identity and public return result. A failed
SSH read alone is not suspension. Measure the suspended interval on the
controller's monotonic clock, which continues while the guest is suspended;
do not use guest uptime or wait for a guest reply before waking. Bind the wake
deadline before suspend so the active branch retains a sufficient grant margin.

## Live VM acceptance

Prepare a real active grant with zero daily allowance, suspend normally, wake
before its deadline, independently observe the return surface and unlock
successfully. Qualify independent valid entry and continuity of the existing
activity. Cover wrong-owner/attempt/deadline refusal in focused harness checks
before discovery or suspend input; retain fresh runtime identity guards without
replaying GDM's unchanged qualification history.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_suspend_active_grant
```
