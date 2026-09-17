# 028 — Close and reopen Parent

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **LIFE01**. First scheduled consumer: [E2E-035, case 158](../E2E-Scenario-Recipes.md#e2e-035).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Use the existing qualified source interfaces and guarded attempt envelope; no new capability prerequisite.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend UI18 and SEARCH05 only for normal Parent closure/relaunch. LIFE01 observes the new window without selecting a child or restoring fields. Keep explicit prior-window and destination arguments.

## Live VM acceptance

Open Parent on the VM, close it normally, prove it disappeared, relaunch through the app grid and observe the new management window. Read its initial selection before any edit; an already-closed/wrong window must not trigger repair.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_feedback_local
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
