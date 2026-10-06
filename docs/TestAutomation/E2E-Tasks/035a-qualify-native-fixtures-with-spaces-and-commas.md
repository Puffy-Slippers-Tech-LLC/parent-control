# 035a — Qualify the comma-containing native fixture

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add the comma-containing fixture and its identical-copy checks. Reuse 035d's special-path transfer/copy/result operations; retain both finite fixtures.

Reuse the delivered scope of tasks **035d** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **FIX06 special-path readiness; FILE05 and command-result bindings**. First scheduled consumer: [E2E-041, case 188](../E2E-Scenario-Recipes.md#e2e-041).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **035d** — FIX06 space-path readiness; FILE05 copy and command-policy result.

## Implementation

Add the comma-path profile required by case 188; reuse 035d's space-path
profile. Declare reusable source assets in baseline preparation and verify them
through FIX06. Bind exact identical-copy destinations and distinct allowed N;
perform the recipe's copies through FILE05. Reuse command launch/result operations.

## Live VM acceptance

On the live VM, copy each declared executable through the shared FILE05 command helper and verify its exact destination/content. Under publicly saved Hard and Soft rules, require original and identical-copy denial while N remains usable. Do not generalize this to arbitrary copied programs.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_qualify_native_fixtures_with_spaces_and_commas
```
