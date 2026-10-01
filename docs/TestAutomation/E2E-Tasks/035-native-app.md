# 035 — Launch and use native fixtures by command

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add the native command usable route through the shared guarded SSH helper as the active child desktop user. Reuse 035c for grid launch and shared app observations.

Reuse the delivered scope of tasks **035c** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03 native grid/command usable scope**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **035p** — native baseline assets and launchers; guarded read-only verification.
- **001t** — PARENT01 direct command, public management denial and desktop return.
- **009** — UI16.
- **035c** — APP01/02/03 native app-grid usable route.

## Implementation

Verify the native baseline through FIX06, then qualify APP01 command input,
APP02 usable-window observation and APP03 normal input/effect. Reuse 035c's
qualified grid route and result readers. Special-path copies and versioned-path
fixtures remain separate consumer assets.

Shared source routes: `onpc_app_rows::native_search/native_launch_grid/native_open_grid`
and `native_use_app/native_close_app` in
[`onpc_app_rows.pm`](../../../tests/integration/graphical_smoke/lib/onpc_app_rows.pm);
`AccessibleUI.native_app_operation/native_app_snapshot/native_app_submit/native_app_closed`
in [`accessible_ui.py`](../../../tests/e2e/accessible_ui.py), with public projections
in `FixtureUI` and exact controller decoding in `UiObservations`.
The existing grid qualifier is `native_grid_usable.PLAN` / `NativeGridJourney` in
[`native_grid_usable.py`](../../../tests/e2e/native_grid_usable.py).
The command route is `AccessibleUI.native_launch_command` and
`onpc_app_rows::native_open_command`. Its qualification uses `native_app.PLAN` /
`NativeAppJourney` in [`native_app.py`](../../../tests/e2e/native_app.py), with
host command/worker refusal coverage in
[`test_e2e_native_app.py`](../../../tests/unit/test_e2e_native_app.py) and the
shared recorder/cleanup inventory. FIX06 readback precedes child desktop entry;
two independent launches reuse the grid route's Submit and closure observations.
Ownership, worker-marker reconciliation and refusal regressions are in
[`test_e2e_native_grid_usable.py`](../../../tests/unit/test_e2e_native_grid_usable.py).

## Live VM acceptance

On the VM, launch the app through the shared direct-command route and perform
one normal action with its visible result. Reuse unchanged grid qualification;
rerun that branch only if affected. Keep denial/hidden bindings pending for their
public-policy consumer. No fake window or process probe.

Registered qualification selector (live qualification pending):

```sh
tools/run-tests integration check_e2e_native_app
```

## Current recovery boundary

Host checks passed: command/session and worker-marker checks, existing grid
checks, actual recorder durability/constructor coverage, launcher input
preparation, resource inventory, ownership safety and composition/plan checks.
The final repair verification report is
`output/test-runs/host/reports/20261001T164621Z-2bc2a5b6/report.md` (1658 passed).
The earlier affected run `20261001T164429Z-09267656` passed 1244 checks;
its single synthetic system-evidence test defect was repaired and passed in
the final report. Changes are test-only; no package-source/build dependency
changed. Missing named fixture inputs were built and verified automatically.

The first live attempt on every enabled VM (Ubuntu only) failed in
`output/test-runs/host/reports/20261001T164907Z-5a798333/report.md` with
`e2e:worker-execution-failed`. FIX06's ten-file readback, administrator entry,
logout, child greeter and `child-standard-focused` passed. The worker then
stopped before the next recipient check and before native launch. No cause or
product-behavior mismatch has been established; collection/product outcomes
are `not-run`. Owned worker cleanup and baseline restoration passed.

Preserved evidence:

- Worker/graphical attempt: `output/test-runs/privileged/allocations/onpc-graphical-smoke-2s1p4f63`.
- Worker evidence: `output/test-runs/privileged/allocations/onpc-e2e-evidence-dn7uich6`.
- Qualification evidence: `output/test-runs/privileged/allocations/onpc-e2e-evidence-zm3vrwa_`.
- VM queue: `output/test-runs/host/allocations/onpc-vm-queue-x5l2skl1/results.json`.

Resume by diagnosing that failure, adding a focused host reproduction and
repairing its established cause. Run affected host checks, then the registered
live selector above on all enabled VMs. Preserve the same first-live-failure
boundary in recovery. No adviser consultation occurred; use the current
Sol High / bounded read-only Astra escalation policy. Keep this task unchecked
and the pointer here until complete acceptance and close-out pass.
