# 037a — Save to a customer-selected location through the chooser

Estimate: 20–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FILE03 save**. First scheduled consumer: [E2E-031, case 155](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **037** — FILE03 open/cancel.
- **031a** — FEED09 collection trace.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend FILE03 for the real save chooser reached from feedback Download after collection. Bind the directory, filename, Save and closure; reject wrong chooser modes. FEED08 owns opening and reading the resulting artifact.

## Live VM acceptance

On the live VM, observe collection complete, open Download's chooser, choose a synthetic destination and filename, then Save. Independently observe closure and the named file in the file manager. Exercise Cancel from a fresh chooser and prove that no second file was created.

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
