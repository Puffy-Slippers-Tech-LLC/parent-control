# 188k — Observe failed kiosk diagnostic collection

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED09 genuine installed kiosk collection failure and usable controls**.
Former case 213's sending behavior is now a
[separate UI obligation](../UI-and-E2E-Coverage.md#feedback-sending-allocation)
and does not consume or qualify this installed result. Read the named
[block contracts](../E2E-Building-Blocks.md#additional-public-surfaces).

**Gate:** Neither a genuine public kiosk request-error entry nor a deterministic public collection-failure trigger is established. Leave pending until both normal customer routes are qualified; no internal fault injection or manufactured cooldown error. No successful collection recovery or Send is required by this installed failure-state slice. These gaps do not gate the component without-logs check.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021a** — delivered kiosk request entry and approval operations.
- **030** — delivered Privacy mechanics; kiosk binding still needs qualification.

## Implementation

Bind FEED09's unavailable/partial collection explanation and editing/Close controls on kiosk. First qualify a genuine public request-error entry through FEED15 and its kiosk report destination; successful requests may be repeated immediately and no longer provide an error trigger. Then independently capture the terminal failed-collection state before editing. Record the exact genuine public prerequisites for error entry and collection failure; a lost Internet connection alone does not fail local collection. Retiring task 187k supplied neither binding nor acceptance.

Extend `AccessibleUI.feedback_snapshot` and `FeedbackStateObservation` for
the station's failed-collection projection. Parent's ready/Download waiter is
neither this result nor a station qualification. Retain wrong-surface/owner
refusals; no successful Retry history or pre-entry trace is needed to observe
the persistent failure before Send without logs.

## Live VM acceptance

On the VM, independently observe collection actually fail on kiosk. Read the failure explanation, enter a synthetic draft through the usable editor and close normally through the usable Close action. No successful recovery or submission is needed to qualify this failure-state slice.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests system check_e2e_kiosk_collection_failure
```
