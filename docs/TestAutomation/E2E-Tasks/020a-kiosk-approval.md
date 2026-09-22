# 020a — Qualify kiosk secret submission and automatic approved exit

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **AUTH02 kiosk approval; REQUEST11/12 success and automatic GDM exit**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **019** — REQUEST09, AUTH01 kiosk.
- **013** — REQUEST11/12 kiosk Cancel and Escape.

## Read only this context

Read AUTH01/02, REQUEST11/12, the [credential boundary](../../../tests/e2e/README.md#credential-staging-and-password-capture-boundary) and the MATE prompt/worker callables recorded in the catalogue.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Connect the qualified MATE recipient to the existing single-use secret transport. Require two fresh same-challenge proofs for the same administrator, child and request; submit exactly once. Implement independent approval/form success and automatic exit observations as separate leaves before composing them. Challenge disappearance alone is insufficient.

## Live VM acceptance

In a real kiosk request, type the correct fixture password once, observe explicit request success and its automatic return to GDM. Qualify independent valid challenge entry and wrong-recipient refusal. Pass stale/reused-challenge, nonempty/unfocused field, capture and uncertain-delivery tests. Require sealed capture reconciliation, collection and cleanup.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_kiosk_approval
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**020a** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
