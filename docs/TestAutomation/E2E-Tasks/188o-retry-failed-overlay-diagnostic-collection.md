# 188o — Observe failed overlay diagnostic collection

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED09 overlay collection failure and usable controls**. First scheduled consumer: [E2E-046, case 211](../E2E-Scenario-Recipes.md#e2e-046).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** No deterministic public collection-failure trigger is established. Leave pending until an exact normal customer trigger is qualified; no internal fault injection. Recovery is required only by the separate Retry slice.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **187o** — REQUEST09 cooldown and FEED15 overlay; gate in brief.
- **031a** — FEED09 collection trace.

## Implementation

Bind FEED09's unavailable/partial collection explanation and editing/Close controls on overlay. Arm the public observer before entry. Reach the error report through the qualified public cooldown prefix and FEED15. Record the exact genuine public prerequisite failure; a lost Internet connection alone does not fail local collection.

## Live VM acceptance

On the VM, observe collection actually fail on overlay with its read-only trace already active. Read the failure explanation, enter a synthetic draft through the usable editor and close normally through the usable Close action. No successful recovery or submission is needed to qualify this failure-state slice.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_overlay_collection_failure
```
