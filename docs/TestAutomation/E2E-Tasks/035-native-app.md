# 035 — Prepare one native app and operate it publicly

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FIX04 native asset; APP01/02/03 native grid/command usable scope**. First scheduled consumer: [E2E-041, case 184](../E2E-Scenario-Recipes.md#e2e-041).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **001** — FILE01, FILE02, FILE06.
- **009** — UI16.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Stage the pinned native A/H/S/N app fixtures through FIX04 with declared public usability actions. Qualify APP01 grid/command input, APP02 usable-window observation and APP03 normal input/effect in that order. Register bounded app-search projections. Special-path copies and AppImage versions are separate consumer assets.

## Live VM acceptance

On the VM, launch the actual app from the grid and terminal and perform a normal action with visible result. Keep denial/hidden bindings pending for their public-policy consumer. No fake window or process probe.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_expiry
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
