# 047 — Record app activity and compose launch/use

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP04; FLOW08 native usable-app scope**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **035** — APP01/02/03 native grid/command usable scope.
- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.

## Implementation

Implement APP04 capture and comparison using explicit immutable public observations. Then compose FLOW08 from the qualified native launch/result/usability blocks. Register only usable-app scope here; policy-denial bindings and retained-user FLOW09/14 are qualified with their respective consumers.

Implementation: `AccessibleUI.native_app_snapshot(with_window=True)` and
`native-activity` expose the public window endpoint and exact submitted draft.
`AppActivityObservation` / `compare_app_activity` in
[`ui_observations.py`](../../../tests/e2e/ui_observations.py) copy the capture;
`InstalledJourney.check_activity` uses explicit `JourneyPlan.activity_checks`
endpoints before replying to the worker. FLOW08 uses
`journey_blocks.native_usable_app` / `onpc_app_rows::native_usable_app` for the
finite command/grid usable routes. The
[`native_activity.PLAN`](../../../tests/e2e/native_activity.py) qualification
declares independent reads, wrong-entry refusal and replacement-window rejection.
Host guards are in
[`test_e2e_app_activity.py`](../../../tests/unit/test_e2e_app_activity.py), with
real public identity readback in the native GTK fixture preview.

## Live VM acceptance

In a fresh installed VM attempt, enter the child, launch the prepared native app through each qualified route and prove its normal input has a visible effect. Capture a recognizable activity, reread it independently and compare to the earlier immutable observation before further edits. Repeated invocation IDs stay unique; a replaced window cannot pass a same-window comparison. Cross-user retention is a separate qualification.

Registered qualification selector (live qualification remains required):

```sh
tools/run-tests integration check_e2e_app_activity
```
