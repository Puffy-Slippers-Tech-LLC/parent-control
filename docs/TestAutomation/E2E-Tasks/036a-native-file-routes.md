# 036a — Launch native fixtures from the file manager

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **APP01/02/03 native file-manager route**. First scheduled consumer: [E2E-019, case 74](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **036** — FILE07/04/05; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the file manager's offered launch action to the declared native fixture and independently observe its usable or blocked result. Register a supported separate-window launch for later retained-activity comparisons. Reuse the prepared standard fixture; special-path and AppImage copying stay with their own consumers.

## Live VM acceptance

On the live VM, launch the declared native fixture from the file manager and perform a normal action with a visible result. Open a distinguishable new window beside an earlier activity. Save Hard and Soft rules in Parent, then require this route's declared denied result and expected window closure. No alternative route substitutes for this action.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_native_file_routes
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
