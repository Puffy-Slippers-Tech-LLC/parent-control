# 191a — Read the Shell calendar and clock

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **TIME05 Shell calendar and DESK12 clock binding**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003d** — DESK04 current Shell logout/confirmation route and independently observed GDM return.
- **044a** — DESK10 same-desktop window switching.
- **052c** — TIME03.

## Implementation

Qualify only the Shell clock/calendar provider surface under the
[external-provider contract](../E2E-Building-Blocks.md#external-provider-qualification).
Read the actual date/time with its recorded provider locale and display precision;
open and close the calendar normally. This read-only route never changes time or
timezone. Settings Date & Time remains the next task's separate provider binding.

## Live VM acceptance

Read current date/time, open the calendar, independently compare its public
date and return to the same owned desktop. Qualify a separately supplied open
calendar and reject wrong owner, ambiguous fields and incomplete observations.
An ordinary day is sufficient; this slice does not pass a calendar scenario.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watchvm observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_shell_calendar
```

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the callable and exact qualified scope in the
[catalogue](../E2E-Building-Blocks.md), check **191a** only after acceptance and
cleanup, advance to the following unchecked row, and delete this brief after
enduring context is maintained. The complete scenario stays in its own task.
