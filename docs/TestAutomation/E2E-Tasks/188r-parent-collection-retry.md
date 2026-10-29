# 188r — Observe and retry failed Parent diagnostic collection

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–45 minutes.
Session exception: Qualify genuine collection failure, usable editing and normal
Retry recovery in one uninterrupted attempt, retaining the failed observation
before recovery and the independently observed ready result afterward.

## Scope and prerequisites

Deliver **FEED09 Parent collection failure and usable controls; FEED16 Parent collection recovery**. First scheduled consumer: [E2E-046, case 208](../E2E-Scenario-Recipes.md#e2e-046).
Read the [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and the selected consumer's recipe.

**Gate:** No deterministic public diagnostic-collection failure/recovery trigger
is established. The genuine public failure and its normal recovery must both
be available; keep this combined slice pending until their exact customer
trigger is qualified. Internet loss alone does not fail local collection;
internal fault injection supplies no customer acceptance.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **009** — Ordinary Parent feedback entry and public synthetic-text operations.
- **031a** — Parent's completed diagnostic-collection result after recovery.

## Implementation

Absorb former task 188p's missing failure projection into this shared
failure/recovery binding. Enter ordinary Parent feedback through FEED01,
independently capture terminal failed collection and its explanation, and read
the usable editor/Close controls before recovery. Enter and capture a synthetic
draft, restore the declared public prerequisite, then compose one normal Retry
collection input, FEED09 ready-state readback and FEED03/UI12 draft comparison.
The same failed observation feeds recovery; do not close and reproduce failure
in another qualification attempt merely to separate the two stage labels.

Extend `AccessibleUI.feedback_snapshot` / `wait_feedback_collection` and
`FeedbackStateObservation` with an explicit failure projection. The current
ready/Download waiter cannot observe failed collection as success. Capture the
persistent failed result before recovery; no observer running before entry or
collecting-transient trace is required.

Extend `feedback_collection.PLAN`, `AccessibleUI.wait_feedback_collection`
and the shared feedback API operation with `feedback-retry-logs`.
The failure projection, failed-before-ready composition and selector are planned; reuse the
unchanged ready-state observation without rerunning its two-entry history.

## Live VM acceptance

In one fresh live attempt, independently observe genuine Parent collection
failure, read the failure explanation and usable editor/Close controls, enter a
synthetic draft, restore the declared public prerequisite and select Retry once.
Require completed collection and the unchanged draft, then close normally.
No Send. An already-ready draft cannot stand in for failure-before-recovery.
This consolidated qualification supplies no completion credit for case 208;
its complete customer journey remains pending until its own acceptance.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_parent_collection_retry
```
