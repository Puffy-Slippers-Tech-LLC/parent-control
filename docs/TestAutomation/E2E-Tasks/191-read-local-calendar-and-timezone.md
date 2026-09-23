# 191 — Read local date, time and timezone through SSH

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **TIME05 read-only system clock/timezone observations**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052c** — TIME03.

## Read only this context

Read TIME05, the natural-calendar-window recipe and the shared guarded SSH command/monotonic observation helpers.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Read date/time, UTC offset and timezone through fixed `date`/`timedatectl` commands over SSH. Bind locale-independent output, explicit precision and monotonic bracketing. Never set the guest clock or timezone. No Shell calendar or Settings page.

## Live VM acceptance

On an ordinary day, independently read and validate the actual system clock/timezone in the owned VM. Reject malformed, incomplete or stale output. Natural calendar scenarios still require their actual eligible windows and app countdown/access results.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_read_local_calendar_and_timezone
```

Use the shared watchvm intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **191** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
