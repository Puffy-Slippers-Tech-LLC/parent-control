# 021a — Compose successful kiosk approval and time request

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **FLOW05/06 kiosk approved branch**. Named consumer: task **021** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **020** — AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits.
- **014** — FLOW04 kiosk.

## Read only this context

Read only the delivered block rows and their named callables in the
[catalogue](../E2E-Building-Blocks.md), the selected consumer's recipe clauses,
and the affected safety/adapter tests. Follow the
[scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Use delivered prerequisite scopes; do not open predecessor briefs.

Start at `kiosk_approval.PLAN`, `AccessibleUI.kiosk_mate_approval` /
`kiosk_approval_success`, `request_flow.prepared_request` and
`onpc_request_flow::run(exchange, 'approval')` / `prepare`.
Task 020's outcome set and exact qualification limits are in the catalogue's
**Kiosk approval qualification** and **Kiosk rejection qualification** sections.
Supporting checks are `test_e2e_kiosk_valid_duration.py`,
`test_challenges_cleanup_safety.py` and `test_installed_journey_cleanup_safety.py`.

## Implementation

Compose REQUEST09/AUTH02/REQUEST11/REQUEST12 for success, then kiosk FLOW04/FLOW05 for a prepared request. Use fresh invocation stages and explicit automatic GDM exit.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

Obtain real short time through the station, observe approval and automatic GDM return. Also qualify an independently prepared valid form; wrong child/request entry refuses.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_kiosk_approved_flow
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **021a**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
