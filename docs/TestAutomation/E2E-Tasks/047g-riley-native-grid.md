# 047g — Launch and use the native target from Riley's app grid

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03 and FLOW08 Riley native-grid usable scope**. First scheduled consumer: [E2E-019, case 62](../E2E-Scenario-Recipes.md#e2e-019).
The unaffected child must use the same target through the same route.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **047** — Jordan's qualified native-grid launch/use and public activity helpers.
- **048e** — Riley's qualified command-launched native activity and session/input guards.

## Implementation

Extend `journey_blocks.native_usable_app` and `onpc_app_rows::native_usable_app`
with the explicit Riley grid binding, reusing the shared search/result recipient,
single launch, public owned window and normal draft-submission operations.
Current code permits Riley only through `command`; Jordan's grid qualification
does not supply this binding. Do not fall back to command after a grid failure.

The [native fixture contract](../E2E-Building-Blocks.md#native-fixture-preparation)
currently places per-user launchers only in Jordan's baseline home. Add only
Riley's launcher for the same `A.desktop`/`Exact Fixture.AppImage` target through
the maintained idempotent baseline declaration/preparation and exact readback.
Preserve unrelated entries, ownership and source identity. Attempts verify the
launcher; they never create or repair it. Keep the existing executable and
mandatory fixture public IDs, with no additional app-policy matrix.

## Live VM acceptance

In one fresh guarded installed attempt, enter Riley with usable access and no
temporary approval. Independently verify the declared baseline launcher, launch
the exact target once through its grid search/result, read the owned native
window and perform one normal draft submission with independent effect readback.
Qualify independently supplied valid Riley entry and focused wrong-account,
wrong-result and uncertain-input refusal; reuse unchanged Jordan grid and Riley
command qualifications rather than replaying their complete histories.

Planned selector; implement and register it before use:

```sh
tools/run-tests integration check_e2e_riley_native_grid
```

This slice qualifies Riley's unaffected grid access only. Hard/soft policy
denial remains 079d; complete cases 62/64/66 retain independent acceptance.
