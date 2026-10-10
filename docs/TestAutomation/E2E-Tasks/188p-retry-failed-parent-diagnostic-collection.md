# 188p — Observe failed Parent diagnostic collection

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED09 Parent collection failure and usable controls**. First scheduled consumer: [E2E-046, case 208](../E2E-Scenario-Recipes.md#e2e-046).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** No deterministic public collection-failure trigger is established. Leave pending until an exact normal customer trigger is qualified; no internal fault injection. Recovery is required only by the separate Retry slice.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **009** — Ordinary Parent feedback entry and public synthetic-text operations.

## Implementation

Bind FEED09's unavailable/partial collection explanation and editing/Close controls on Parent. Enter ordinary feedback with FEED01 and independently capture the terminal failed-collection state before editing. Record the exact genuine public prerequisite failure; a lost Internet connection alone does not fail local collection.

Extend `AccessibleUI.feedback_snapshot` / `wait_feedback_collection` and
`FeedbackStateObservation` for the explicit failure projection. Existing
`feedback_collection.PLAN` waits for ready/Download and cannot observe a failed
collection as success. This slice needs no ready-state qualification history or
observer running before entry: the independent persistent failure result is
required before any recovery or Send.

## Live VM acceptance

On the VM, independently observe collection actually fail on Parent. Read the failure explanation, enter a synthetic draft through the usable editor and close normally through the usable Close action. No successful recovery or submission is needed to qualify this failure-state slice.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_parent_collection_failure
```
