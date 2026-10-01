# 035 — Launch and use native fixtures by command

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add the native command usable route through the shared guarded SSH helper as the active child desktop user. Reuse 035c for grid launch and shared app observations.

Tasks **035c** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **APP01/02/03 native grid/command usable scope**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **035p** — FIX04 native assets; LIFE04 fixture installation.
- **001t** — PARENT01 direct command, public management denial and desktop return.
- **009** — UI16.
- **035c** — APP01/02/03 native app-grid usable route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the qualified native fixture manifest and public installation route in this attempt, with declared public usability actions. Qualify APP01 grid/command input, APP02 usable-window observation and APP03 normal input/effect in that order. Register bounded app-search projections. Special-path copies and AppImage versions are separate consumer assets.

## Live VM acceptance

On the VM, launch the actual app through its declared grid route and shared direct-command route and perform a normal action with visible result. Keep denial/hidden bindings pending for their public-policy consumer. No fake window or process probe.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_native_app
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
