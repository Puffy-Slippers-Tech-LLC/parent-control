# 048d — Qualify overlay approval and automatic return

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **AUTH02 overlay approval; REQUEST11/12 success and automatic child return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048c** — Shell Polkit AUTH01 overlay recipient and guarded Cancel/preserved-form result.
- **021** — FLOW05/06/07 kiosk.

## Read only this context

Read overlay AUTH01/02 and REQUEST11/12, the shared credential boundary and
[Shell prompt qualification](../E2E-Building-Blocks.md#overlay-shell-prompt-and-cancel-qualification).
Reuse `AccessibleUI.shell_prompt_owner`, `shell_prompt`, `shell_prompt_refusals`
and the worker's `onpc_request_flow::shell_cancel` guard; the qualified
`overlay_shell_cancel_ready` operation delivers no password and supplies no
secret-delivery authority.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Connect two fresh same-challenge Shell recipient proofs to sealed single-use password input and one submit. Independently observe the shared form's success and automatic return to the same child desktop/activity. The kiosk result cannot qualify this provider or destination.

## Live VM acceptance

Approve one declared overlay request with the correct fixture credential. Read public success, automatic exit and the original usable child activity. Include independently entered challenge, wrong-recipient and stale/reused-proof refusal, sealed capture reconciliation and cleanup. Task 048f adds rejection/Cancel; task 048b adds cancellation composition and immediate approved exit.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_approved_exit
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.
