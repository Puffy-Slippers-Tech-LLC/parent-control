# 003ba — Qualify fresh login without a keyring prompt

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **GDM05 fresh Parent/standard entry and DESK01 no-prompt desktop**. Named consumer: task **003b** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003a** — GDM01/02 ordinary prompt entry; GDM03/04/08/09 recipient, refusal and Escape-return proofs.

## Read only this context

Read the [search/sign-in contract](../E2E-Building-Blocks.md#search-and-standard-sign-in-contracts), [credential boundary](../../../tests/e2e/README.md#credential-staging-and-password-capture-boundary), desktop/prompt callables in [accessible_ui.py](../../../tests/e2e/accessible_ui.py), and the entry stages of [desktop_session.py](../../../tests/e2e/desktop_session.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.


## Implementation

Connect the qualified GDM proofs to the existing sealed single-use login transport and recognize the intended Parent and standard fixture desktops. Use a declared reproducible no-keyring-prompt profile; unknown modals refuse.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

In separate fresh attempts, log in to each named fixture account and independently observe its usable desktop. Qualify an independently supplied desktop and wrong-recipient refusal, private capture reconciliation and cleanup.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_fresh_desktop
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **003ba**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
