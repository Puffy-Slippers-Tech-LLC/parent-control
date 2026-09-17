# 035b — Qualify versioned AppImage pattern assets

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FIX04 AppImage versions; FILE05 and pattern launch results**. First scheduled consumer: [E2E-041, case 189](../E2E-Scenario-Recipes.md#e2e-041).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **036** — FILE07/04/05; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **186** — PARENT15 failed-save; FEED15 Parent and report-close binding.
- **052c** — TIME03.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the current/next matching AppImage versions and existing/new nonmatches for case 189. Reuse public file copying, saved same-directory wildcard rules and command-result projections. Register the finite read-only refresh wait without retrying launch input.

## Live VM acceptance

On the live VM, add the next version through the file manager, require matching versions denied and existing nonmatches usable. For the new nonmatch, wait at most the recipe's 60 seconds and issue one declared launch. A rejected pattern must expose its report and preserve the prior confirmed rule.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_qualify_versioned_appimage_pattern_assets
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
