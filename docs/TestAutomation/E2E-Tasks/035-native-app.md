# 035 — Launch and use native fixtures by command

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add the native command usable route through the shared guarded SSH helper as the active child desktop user. Reuse 035c for grid launch and shared app observations.

Reuse the delivered scope of tasks **035c** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03 native grid/command usable scope**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **035p** — native baseline assets and launchers; guarded read-only verification.
- **001t** — PARENT01 direct command, public management denial and desktop return.
- **009** — UI16.
- **035c** — APP01/02/03 native app-grid usable route.

## Implementation

Verify the native baseline through FIX06, then qualify APP01 command input,
APP02 usable-window observation and APP03 normal input/effect. Reuse 035c's
qualified grid route and result readers. Special-path copies and versioned-path
fixtures remain separate consumer assets.

## Live VM acceptance

On the VM, launch the app through the shared direct-command route and perform
one normal action with its visible result. Reuse unchanged grid qualification;
rerun that branch only if affected. Keep denial/hidden bindings pending for their
public-policy consumer. No fake window or process probe.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_native_app
```
