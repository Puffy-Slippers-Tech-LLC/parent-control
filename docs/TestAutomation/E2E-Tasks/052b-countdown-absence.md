# 052b — Prove countdown absence on other surfaces

Estimate: 20–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **TIME01 lock/GDM/other-user absence**. First scheduled consumer: [E2E-011, case 27](../E2E-Scenario-Recipes.md#e2e-011).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **052** — TIME01 child-desktop snapshots.
- **043a** — GDM02 retained-child lock entry; DESK08/11.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind complete, fresh absence observations to each positively identified surface.
A disconnected observer, inaccessible tree or wrong surface cannot prove absence.
Keep input routes outside TIME01; it only observes the caller's stated surface.

## Live VM acceptance

In a fresh installed VM attempt, prepare ample positive daily time publicly,
enter the child and read its countdown. Lock normally and require countdown
absence on the identified lock surface. Unlock legitimately and observe the
countdown again. Switch User to GDM and require absence, then enter the named
other user and require absence on that desktop. Qualify independently reached
entry states and wrong-surface refusal. No natural-expiry or tick claim is made.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_countdown
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
