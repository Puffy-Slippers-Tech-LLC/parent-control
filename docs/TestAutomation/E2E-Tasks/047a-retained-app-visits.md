# 047a — Compose retained app visits for distinct users

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW09 and FLOW14 distinct-user retention**. First scheduled consumer: [E2E-010, case 25](../E2E-Scenario-Recipes.md#e2e-010).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **047** — APP04; FLOW08 native usable-app scope.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose FLOW09 from legitimate retained entry, APP04 comparison and APP03 use.
Compose FLOW14 from the explicit per-user entry, FLOW08, activity capture and
Switch User sequence. Carry the prior observations and current surface; do not
replace an existing desktop or relaunch an app to satisfy continuity.
Same-child multiple desktops retain their separate gate.

## Live VM acceptance

On the installed VM, prepare and capture recognizable activities for the child
and declared other user, preserving both through normal Switch User. Return
legitimately to each original desktop and prove the same activity remains
usable. FLOW14 starts and ends at GDM; FLOW09 ends at the named usable activity.
Independent retained entry must work; a missing prior observation or wrong
entry mode refuses without recreating state.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_retained_app_visits
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After live qualification and cleanup, update the callable, exact qualified scope
and status in [E2E-Building-Blocks.md](../E2E-Building-Blocks.md), and reconcile
the first consumer's status in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
A slice alone leaves the full scenario pending. If any complete E2E scenario
passed, run `tools/generate_test_coverage.sh` after that case's cleanup; it runs
`tools/generate_test_coverage.py`. Require successful generation before check-off.

Check this task in the [master](../E2E-Execution-Plan.md), then remove this brief
when its enduring context is in source/contracts and replace its master link
with plain text. Validate changed Markdown with `tools/read-only links`.
Keep normal runner artifacts; no new evidence document or accumulated history.
