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
first normally before the next. Publicly block the first while the second
remains Allowed; require both routes denied through the qualified result
observers, using a separate command-denial witness if a grid entry is hidden.
Qualify independently supplied valid entry and focused wrong-alias/owner and
uncertain-input refusal. Reuse unchanged single-target qualification.

The full reverse-block/both-Allowed customer history remains case 187; this
slice establishes reusable alias readiness/results without completing that case.

Planned selector; implement and register it before use:

```sh
tools/run-tests integration check_e2e_shared_target_launchers
```
