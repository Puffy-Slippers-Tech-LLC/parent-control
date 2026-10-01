# 035a — Qualify the comma-containing native fixture

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add the comma-containing fixture and its identical-copy checks. Reuse 035d's special-path transfer/copy/result operations; retain both finite fixtures.

Tasks **035d** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **FIX04 special-path native assets; FILE05 and command-result bindings**. First scheduled consumer: [E2E-041, case 188](../E2E-Scenario-Recipes.md#e2e-041).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **035d** — FIX04 space-path asset; FILE05 copy and command-policy result.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the two supported native path fixtures required by case 188: one space and one comma, their exact identical-copy destinations and distinct allowed N. Stage assets through FIX04; perform copies through FILE05. Reuse explicit command launch/result operations.

## Live VM acceptance

On the live VM, copy each declared executable through the shared FILE05 command helper and verify its exact destination/content. Under publicly saved Hard and Soft rules, require original and identical-copy denial while N remains usable. Do not generalize this to arbitrary copied programs.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_qualify_native_fixtures_with_spaces_and_commas
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
