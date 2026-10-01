# 126p — Prepare the declared offline game in the baseline

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **Offline-game baseline assets and verification; FIX04 transfer only**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — shared guarded administrator command transport.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the repository's existing offline game fixture, builder/artifact cache,
verified asset profile and one fixed level through the
[fixture contract](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope).
Its controls require public automation IDs. Add its finite files/launcher and
dependencies to idempotent `tools/prepare-baseline` reconciliation, using the
existing fixture layout rather than inventing a package. Bind sources to the
baseline identity; FIX04 retains transfer only. No game selection, vendor launcher,
account, asset download or graphics-settings qualification is needed. Leave
actual gameplay, windowed/fullscreen behavior and expiry to the following tasks.

## Live VM acceptance

Qualify baseline first preparation, unchanged repetition, owned updates and
interrupted retry. After ordinary restore, independently verify the declared
files, modes, owners and launcher without writes, then observe the exact public
catalogue identity. Refuse stale/missing assets with baseline-refresh guidance;
preserve cleanup refusal cases. This does not claim a playable-game or expiry result.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_game_fixture
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
