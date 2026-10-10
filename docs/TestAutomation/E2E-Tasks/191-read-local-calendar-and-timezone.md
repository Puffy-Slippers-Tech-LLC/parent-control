# 191 — Read local date, time and timezone through SSH

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **TIME05 read-only system clock/timezone observations**.

Required tasks: none (Baseline).

## Read only this context

Read TIME05, the natural-calendar-window recipe and the shared guarded SSH command/monotonic observation helpers.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Read UTC epoch, local date/time and numeric UTC offset through one fixed,
locale-independent `date` projection; read the timezone through a named system
property rather than parsing `timedatectl`'s human-readable status. Bracket the
reads with controller monotonic timestamps and reject a projection that spans
the tested calendar boundary instead of combining before/after fields. Repeat
only the read within its original deadline. UTC instants plus offsets distinguish
the repeated fall-back hour; local clock text alone cannot order it. Never set
the guest clock or timezone. No Shell calendar or Settings page.

Extend the guarded observation transport in `guest_observations.py` and
`observation_transport.py` with one finite clock projection and independent
readback. TIME05 has no callable yet. Monotonic bracketing requires no deliberate
TIME03 wait or unrelated About-window qualification.

## Live VM acceptance

On an ordinary day, independently read and validate the actual system clock/timezone in the owned VM. Reject malformed, incomplete or stale output. Natural calendar scenarios still require their actual eligible windows and app countdown/access results.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_read_local_calendar_and_timezone
```
