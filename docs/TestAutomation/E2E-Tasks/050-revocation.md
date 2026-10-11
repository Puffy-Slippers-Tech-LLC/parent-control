# 050 — Confirm grant revocation and read balances

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add Confirm and independent saved time readback. Reuse 050a's warning/target and Cancel; child effects remain later consumers.

Reuse the delivered scope of tasks **050a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **PARENT17, PARENT18**. First scheduled consumer: [E2E-008, case 22](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **050a** — PARENT17/18 revocation target, warning and Cancel.

## Implementation

Reuse 050a's warning/target operation and add explicit Confirm, then independently verify saved time and settings. Warning dismissal is shared navigation, not a separate acceptance result. Obtain the grant through kiosk approval.

Extend the same shared PARENT17/18 operation, then use
`AccessibleUI.reach_time_explanation` and `settings` for independent G=0,
elapsed-bounded unchanged daily time and unchanged saved allowance/app rules.
No child entry or application launch belongs to this balance-only capability.

Start with `AccessibleUI.open_revoke_warning`, `revoke_warning` and
`cancel_revoke` in `tests/e2e/accessible_ui.py`; Cancel currently refuses a
confirmation response before discovery. `RevokeCancelJourney` / `REVOKE_PLAN`
in `tests/e2e/time_explanation.py` and
`onpc_time_explanation::revoke_cancel` compose the real fixed grant and retained
Parent return. Reuse that composition with explicit Confirm authority and its
own independent results; keep shared sealed password bindings finite.
Host guards/decoder, durable-reply and worker-order regressions are in
`test_accessible_e2e_ui.py`, `test_installed_journey_cleanup_safety.py`,
`test_e2e_toggle.py` and `test_challenges_cleanup_safety.py`.
The [warning/Cancel qualification](../E2E-Building-Blocks.md#revocation-warning-and-cancel-qualification)
owns its exact scope and reports.

## Live VM acceptance

In a fresh guarded VM attempt with a real kiosk-approved grant, open the owned warning, verify its child target, Confirm once and independently read the new daily/one-time explanation and saved settings. Qualify independent valid entry and wrong-child/confirmation refusal. Reuse 050a's unchanged exact warning/Cancel qualification, rerunning affected branches when necessary; its evidence supplies no saved VM state. Child effects remain separate later observations.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_revocation
```
