# 011 — Enter and read the request station

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **REQUEST01, REQUEST03**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Use the existing qualified source interfaces and guarded attempt envelope; no new capability prerequisite.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify the public kiosk bus and GDM02 passwordless station route, plus UI15 session choice only if offered. Implement station entry and shared immutable form observations; fixed overlay-child binding is qualified later.

## Live VM acceptance

From live GDM enter the dedicated station through its offered session control, observe one request form and exact public child/approver/duration/control state. Prove unavailable selectors without activating them. No desktop-login shortcut.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_kiosk_choices
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
