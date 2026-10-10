# 126p — Prepare the declared offline game in the baseline

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **Offline-game baseline assets and FIX06 verification**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — shared guarded administrator command transport.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the repository's existing offline game fixture, builder/artifact cache,
verified asset profile and one fixed level through the
[fixture contract](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope).
Its controls require public automation IDs. Add its finite files/launcher and
dependencies to idempotent `tools/prepare-vm` reconciliation, using the
existing fixture layout rather than inventing a package. Bind sources to the
baseline identity; FIX04 retains transfer only. No game selection, vendor launcher,
account, asset download or graphics-settings qualification is needed. Leave
actual gameplay, windowed/fullscreen behavior and expiry to the following tasks.

## Live VM acceptance

Exercise idempotence, owned updates, interrupted retry and unsafe-asset refusal
in the existing baseline/ownership host regressions for this added profile.
Reuse unchanged reconciliation qualification. After ordinary preparation and
restore, independently verify the declared
files, modes, owners and launcher without writes, then observe the exact public
catalogue identity. Refuse stale/missing assets with baseline-refresh guidance;
preserve cleanup refusal cases. This does not claim a playable-game or expiry result.

`build_test_applications.build` already emits `onpc-test-game` and its launcher,
and `gui_application.main` provides public move/score controls. The current
`baseline_fixtures.build_payload` builds native roles only, and
`NativeFixtures` accepts only native/Chinese verification profiles. Add the
game to those finite baseline/readback declarations. Actual level/mode and
playability bindings remain with 126a/126/129; a built file is not that result.

Qualification selector (planned; implement and register before use). Qualify
independent installed asset readback and the added profile's wrong-owner/entry
refusal, retaining shared runtime/cleanup guards without replaying unrelated
baseline histories.

```sh
tools/run-tests integration check_e2e_game_fixture
```
