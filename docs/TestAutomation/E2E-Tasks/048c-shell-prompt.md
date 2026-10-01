# 048c — Qualify the overlay Shell prompt and Cancel

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

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

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
