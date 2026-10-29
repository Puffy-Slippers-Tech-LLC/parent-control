# 229a — Qualify two native launchers sharing one target

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FIX06 and APP01/02/03 shared-target native launcher bindings**. First scheduled consumer: [E2E-041, case 187](../E2E-Scenario-Recipes.md#e2e-041).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079d** — Shared native usable/blocked results and public app-policy operations.
- **180** — Public usable daily allowance and Parent entry for the selected child.

## Implementation

Extend the finite [native fixture declaration](../E2E-Building-Blocks.md#native-fixture-preparation)
in `native_assets.py` with one owned Jordan launcher alias of A's exact
`Exact Fixture.AppImage` executable. Give it a distinct desktop ID and visible
name while retaining the same supported target. Update idempotent baseline
placement and `NativeFixtures` exact readback; preserve unrelated launchers and
recorded ownership. Attempts verify both aliases and never install or repair
them. The four existing A/H/S/N executables remain distinct.

Extend shared public row and native grid/result bindings for those two explicit
launcher identities. Reuse `policy_edits.policy_edit`, `onpc_app_rows` and the
native command-denial witness from 079d. Resolve each declared launch route
independently, with one launch per invocation and an independently observed
owned window/use or specific denial. Do not use executable introspection as
the product result or substitute a different launch after failure.

## Live VM acceptance

In a fresh guarded installed attempt, verify the baseline's two exact launcher
identities and observe their distinct public Parent rows for Jordan. With both
Allowed, launch/use each declared alias in separate invocations, closing the
first normally before the next. Qualify the newly added alias identity and
input/result route; reuse unchanged single-target ownership, wrong-recipient
and uncertain-input guards without replaying their refusal matrix.

Case 187 owns the complete public block-first, reverse-block and both-Allowed
recovery history, including saved choices and both launch results at every
declared effect. Do not run that policy/effect sequence in this prerequisite.
System ID 280, `test_native_catalog_is_selected_child_scoped`, owns engineering
catalogue membership and target resolution through
`system_enforcement.observe_catalog`; it does not qualify these alias rows,
shared-target policy merging or their public launch routes. This slice supplies
alias readiness/results, with no saved VM state or complete case acceptance.

Planned selector; implement and register it before use:

```sh
tools/run-tests integration check_e2e_shared_target_launchers
```
