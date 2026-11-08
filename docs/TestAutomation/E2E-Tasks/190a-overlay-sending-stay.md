# 190a — Check report recovery on the child desktop

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED09 child-overlay retry/reconnection and FEED17 pending Stop action**. Named consumer: task **190o** and any
complete cases released directly by this slice in the canonical queue.

**Gate:** Authorization for the submission, public cooldown-error entry and safe normal connectivity control are required.

The [product contract](../../SystemDesign/Logging-and-Feedback.md#feedback-and-diagnostic-export)
and `FeedbackDialog._hide_draft` use a direct Stop sending and close action.
Leave that action untouched while testing recovery. No extra warning dialog or
stay response is required; task 190o owns the separate direct-stop result.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150** — Shared authorized submission and success/confirmation operations; gate in brief.
- **187o** — Qualified public overlay cooldown-error/report entry; gate in brief.
- **193a** — Owned VM Internet isolation/recovery; no Parent retry or toggle history.

## Implementation

Reuse the exact reviewed sending authorization and public connectivity route.
Observe retry and the available Stop action while leaving the report open,
then reconnect and observe the same submission's automatic acceptance and exit.

Extend `AccessibleUI.feedback_snapshot` / `FeedbackStateObservation` and the
shared feedback API facade for sending/retry and FEED17. Reuse LIFE06's
`InternetIsolation` directly; Parent's toggle/retry journey is not part of
this surface's qualification. Keep one guarded Send and an independent
retry result before reconnection.

Use the recipe's [sending/retry preparation](../E2E-Scenario-Recipes.md#sending-background-completion-and-report-exits)
for this report-open/reconnection branch.

Reuse the shared overlay result/exit projections delivered for case 220 when
available, without depending on that scenario's execution or repeating its
complete history. Qualify only the new retry/reconnection binding and any
changed safety binding; missing projections remain implementation work.

## Live VM acceptance

In an authorized VM attempt, use LIFE06 to remove Internet access, Send once
and independently observe retry with the report still open. Read the pending
Stop action without activating it. Reconnect within the retry window, observe
the same submission succeed, dismiss its owned thanks and require the child
desktop through the shared success-exit operation. No second Send or Close
while retrying. This qualifies no direct-stop result or complete case.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests system check_e2e_overlay_report_retry
```
