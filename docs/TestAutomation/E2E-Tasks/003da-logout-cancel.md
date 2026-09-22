# 003da — Open and cancel the Shell logout confirmation

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **DESK04 logout-confirmation entry and Cancel branch**. Named consumer: task **003d** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003b** — GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback.
- **003c** — DESK02/03 current Shell provider route and independently observed GDM return.

## Read only this context

Read DESK04, LOGOUT_PLAN in [desktop_session.py](../../../tests/e2e/desktop_session.py), `AccessibleUI.logout_confirm` and the existing [session worker](../../../tests/integration/graphical_smoke/lib/onpc_desktop_session.pm).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.


## Implementation

Use the qualified session menu to request Log Out, resolve its distinct confirmation owner and cancel through normal input. Reacquire after each transition.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

Read the real confirmation, Cancel once and independently observe the same usable Parent desktop. Qualify a separately supplied confirmation and refuse wrong owner, stale or ambiguous prompts.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_logout_cancel
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **003da**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
