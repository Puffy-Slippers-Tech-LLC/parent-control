# 048d — Qualify overlay approval and automatic return

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **AUTH02 overlay approval; REQUEST11/12 success and automatic child return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048c** — Shell Polkit AUTH01 overlay recipient and guarded Cancel/preserved-form result.
- **021** — FLOW05/06/07 kiosk.

## Read only this context

Read overlay AUTH01/02 and REQUEST11/12, the shared credential boundary and the Shell prompt/worker callables recorded in the catalogue.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Connect two fresh same-challenge Shell recipient proofs to sealed single-use password input and one submit. Independently observe the shared form's success and automatic return to the same child desktop/activity. The kiosk result cannot qualify this provider or destination.

## Live VM acceptance

Approve one declared overlay request with the correct fixture credential. Read public success, automatic exit and the original usable child activity. Include independently entered challenge, wrong-recipient and stale/reused-proof refusal, sealed capture reconciliation and cleanup. Task 048b adds rejection, cancellation composition and immediate approved exit.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_approved_exit
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**048d** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
