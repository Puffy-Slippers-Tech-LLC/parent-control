# 047 — Record app activity and compose launch/use

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **APP04; FLOW08 native usable-app scope**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **035** — FIX04 native asset; APP01/02/03 native grid/command usable scope.
- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement APP04 capture and comparison using explicit immutable public observations. Then compose FLOW08 from the qualified native launch/result/usability blocks. Register only usable-app scope here; policy-denial bindings and retained-user FLOW09/14 are qualified with their respective consumers.

## Live VM acceptance

In a fresh installed VM attempt, enter the child, launch the prepared native app through each qualified route and prove its normal input has a visible effect. Capture a recognizable activity, reread it independently and compare to the earlier immutable observation before further edits. Repeated invocation IDs stay unique; a replaced window cannot pass a same-window comparison. Cross-user retention is a separate qualification.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_request_exit
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
