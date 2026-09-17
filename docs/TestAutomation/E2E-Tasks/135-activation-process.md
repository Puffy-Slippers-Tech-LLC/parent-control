# 135 — Follow process activation after a real update

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **LIFE04 update; LIFE05 process/none scope**. First scheduled consumer: [E2E-026, case 136](../E2E-Scenario-Recipes.md#e2e-026).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **028** — LIFE01.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **007** — LIFE02.
- **079** — PARENT16 and FLOW03 public app-policy editing.
- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind a verified old/new package profile requiring process activation. Extend LIFE04(update) and LIFE05 only for this route and the explicit no-action notice branch. Follow the displayed requirement for every named affected app/user; preserve all mechanical migration obligations.

## Live VM acceptance

On the VM install the real update, read its process requirement, perform the normal close/reopen sequence and read settings before edits. Run the affected existing package activation checks separately.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_activation_process
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
