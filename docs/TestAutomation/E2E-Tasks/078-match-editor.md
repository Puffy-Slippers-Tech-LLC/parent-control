# 078 — Edit, save, cancel or reset one match rule

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts**. First scheduled consumer: [E2E-045, case 205](../E2E-Scenario-Recipes.md#e2e-045).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **077** — PARENT10, PARENT11.
- **017** — PARENT08 snapshot saved/control states.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement PARENT13 first, then PARENT15 Save, Cancel, Reset and local invalid-draft results. Compare Cancel with the supplied old rule and Reset with its immediate default save. Broker-rejected wildcard reporting is qualified separately with FEED15.

## Live VM acceptance

In installed Parent, enter a valid same-directory wildcard, Cancel and read the old rule; reopen, Save and read the new rule. Empty/unrelated precise input must leave the editor open with validation. Reset saves the detected default immediately. Bind inputs before execution and use no preference reads.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_match_editor
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
