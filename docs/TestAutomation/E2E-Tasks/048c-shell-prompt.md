# 048c — Qualify the overlay Shell prompt and Cancel

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **Shell Polkit AUTH01 overlay recipient and guarded Cancel/preserved-form result**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **019** — REQUEST09, AUTH01 kiosk.
- **004** — UI19/GDM05 distinct single-use authentication challenges.

## Read only this context

Read overlay AUTH01, the Shell Polkit provider row and shared request-form/agent callables in [accessible_ui.py](../../../tests/e2e/accessible_ui.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Implement Shell's distinct prompt owner/recipient binding for the declared overlay request. Reuse challenge/input guards but never MATE selectors or its qualification claim. Verify the visible selected administrator, child, duration and app choice before protected-field qualification. Cancel consumes a fresh prompt proof and independently reads back the same overlay choices.

## Live VM acceptance

Make two deliberate requests in separate live attempts and cancel each real Shell challenge once. Require disappearance, preserved choices, no error and a usable form. Qualify an independently supplied valid prompt and reject wrong provider/session/request, ambiguous/nonempty/unfocused field and stale/replaced challenge. No secret submission in this slice; collect evidence and clean up.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_prompt
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**048c** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
