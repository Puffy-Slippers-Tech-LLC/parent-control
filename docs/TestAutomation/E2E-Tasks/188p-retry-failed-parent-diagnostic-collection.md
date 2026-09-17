# 188p — Retry failed Parent diagnostic collection

Estimate: 25–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FEED16 Parent**. First scheduled consumer: [E2E-046, case 208](../E2E-Scenario-Recipes.md#e2e-046).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** No deterministic public collection-failure/recovery trigger is established. Leave pending until an exact normal customer trigger is qualified; no internal fault injection.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **186** — PARENT15 failed-save; FEED15 Parent and report-close binding.
- **031a** — FEED09 collection trace.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind FEED09 failure/Retry/ready states on Parent, then compose FEED16 from a caller-supplied, publicly observed failed collection and genuine recovery. Preserve the synthetic draft and enabled editing/Close controls. No sending is part of this slice.

## Live VM acceptance

On the VM, observe collection actually fail on Parent; inspect usable editing and Close, enter the declared synthetic draft, restore the public prerequisite and activate Retry once. Require successful collection and unchanged draft. Merely opening a report or disconnecting Internet does not establish a local-collection failure.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_collection_recovery
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
