# 123 — Keep an unsaved match draft across a fixture update

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **LIFE04 fixture update; PARENT15 retained-editor save; LIFE01 catalogue refresh**. First scheduled consumer: [E2E-020, case 110](../E2E-Scenario-Recipes.md#e2e-020).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries), [related block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **006** — LIFE04 install only.
- **044a** — DESK10 same-desktop window switching.
- **028** — LIFE01.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind a verified old/new fixture package pair and extend LIFE04(update). Leave the real Edit Match Rule draft open while the package changes, then foreground that same editor and Save normally.

## Live VM acceptance

On the VM, type a nondefault unsaved match draft, update the fixture through a separate visible administrator terminal, return to the same editor and Save. Close/reopen Parent through LIFE01, reselect the child and independently read the refreshed public app row and expected rule; save-time target resolution does not refresh existing rows. Preserve owned cleanup; no autosave pause or saved-preference probe.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_catalog_change
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
