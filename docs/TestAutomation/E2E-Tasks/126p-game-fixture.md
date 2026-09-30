# 126p — Install the declared offline game fixture

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **FIX04 game asset; LIFE04 fixed game installation profile**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — LIFE04 install only.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the repository's existing offline game fixture, builder/artifact cache,
verified package profile and one fixed level through the
[fixture contract](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope).
Its controls require public automation IDs. Stage through FIX04 and install
through LIFE04's shared local package route. No game selection, vendor launcher,
account, asset download or graphics-settings qualification is needed. Leave
actual gameplay, windowed/fullscreen behavior and expiry to the following tasks.

## Live VM acceptance

On the guarded VM, install the fixed game package and independently observe
command completion and the exact public launcher/catalogue identity. Validate
asset and cleanup refusal cases. Qualification supplies repeatable setup after
ordinary restore and does not claim a playable-game or expiry result.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_game_fixture
```

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the callable and exact qualified scope in the
[catalogue](../E2E-Building-Blocks.md), check **126p** only after acceptance and
cleanup, advance to the following unchecked row, and delete this brief after
enduring context is maintained. The complete scenario stays in its own task.
