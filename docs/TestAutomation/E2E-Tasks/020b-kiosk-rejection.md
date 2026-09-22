# 020b — Observe kiosk password rejection and Cancel

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **AUTH02 kiosk rejection/Cancel with REQUEST11 preserved-form results**. Named consumer: task **020** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **019** — REQUEST09, AUTH01 kiosk.
- **013** — REQUEST11/12 kiosk Cancel and Escape.
- **020a** — AUTH02 kiosk approval; REQUEST11/12 success and automatic GDM exit.

## Read only this context

Read only the delivered block rows and their named callables in the
[catalogue](../E2E-Building-Blocks.md), the selected consumer's recipe clauses,
and the affected safety/adapter tests. Follow the
[scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Use delivered prerequisite scopes; do not open predecessor briefs.

## Implementation

Reuse 019/020a's MATE recipient and sealed submission. Add explicit wrong-password rejection and normal Cancel with independent preserved-form readback.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

In separate attempts, submit one declared wrong password, observe rejection and Cancel; separately Cancel a fresh prompt without a password. Require unchanged usable form/choices, private capture reconciliation and no false approval.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_kiosk_rejection
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **020b**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
