# 003aa — Select an ordinary GDM account and return

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **GDM01/02 ordinary account-list navigation and Escape return**. Named consumer: task **003a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **011** — REQUEST01, REQUEST03.

## Read only this context

Read the GDM and external-provider rows in the [catalogue](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), `AccessibleUI.greeter_list`, `greeter_prompt`, `password_recipient` and `gdm_nonsecret_navigation` in [accessible_ui.py](../../../tests/e2e/accessible_ui.py), and the [GDM worker](../../../tests/integration/graphical_smoke/lib/onpc_gdm.pm). Reuse the installed passwordless station route; its evidence does not qualify ordinary accounts.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.


## Implementation

Bind the scoped GDM account list, exact fixture selection and prompt owner. Implement nonsecret selection and Escape with fresh complete observations. Do not inspect password contents or authorize secret input.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

Select the declared fixture account, observe its prompt, Escape once and independently read the returned list. Repeat from an independently supplied valid list. Refuse wrong owner, duplicate accounts, overlapping list/prompt and uncertain input.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_gdm_navigation
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **003aa**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
