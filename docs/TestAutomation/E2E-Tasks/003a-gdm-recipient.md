# 003a — Prove the intended GDM password recipient

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add the intended-recipient and two-proof checks to the qualified account navigation. Reuse 003aa for list entry and Escape; retain every wrong-recipient, stale, nonempty-field and independent-prompt assertion below.

Tasks **003aa** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **GDM01/02 ordinary prompt entry; GDM03/04/08/09 recipient, refusal and Escape-return proofs**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **011** — REQUEST01, REQUEST03.
- **003aa** — GDM01/02 ordinary account-list navigation and Escape return.

## Read only this context

Read the GDM and external-provider rows in the [catalogue](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), `AccessibleUI.greeter_list`, `greeter_prompt`, `password_recipient` and `gdm_nonsecret_navigation` in [accessible_ui.py](../../../tests/e2e/accessible_ui.py), and the [GDM worker](../../../tests/integration/graphical_smoke/lib/onpc_gdm.pm). Reuse the installed passwordless station route; its evidence does not qualify ordinary accounts.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Extend the existing scoped GDM adapter to ordinary account-list, focused account, selected-recipient and password-prompt observations. Bind only the prepared fixture accounts. Resolve the sole empty masked focused field without reading its contents. Preserve fresh ownership, complete observations, hidden account list, ambiguity rejection and the secret API's two-proof/single-use contract. This slice supplies recipient proofs; it never submits a password.

## Live VM acceptance

In a fresh guarded attempt, select the declared wrong account, reach its actual prompt and prove refusal as the intended recipient. Escape once and independently observe the returned list. Select the intended account, obtain two fresh same-challenge empty-field proofs and independently qualify an already supplied valid prompt. Escape and observe the list. Reject wrong owner, duplicate account, stale/reused proof, nonempty or unfocused field and incomplete list/prompt overlap in focused tests. Require collection and cleanup.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_gdm_recipient
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**003a** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
