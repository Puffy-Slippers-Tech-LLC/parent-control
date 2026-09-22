# 003d — Confirm Shell logout and observe GDM

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add confirmed logout and the GDM result. Reuse 003da's confirmation entry; retain the existing combined Switch User/logout qualification.

Tasks **003da** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **DESK04 current Shell logout/confirmation route and independently observed GDM return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003b** — GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback.
- **003c** — DESK02/03 current Shell provider route and independently observed GDM return.
- **003da** — DESK04 logout-confirmation entry and Cancel branch.

## Read only this context

Read DESK04, LOGOUT_PLAN in [desktop_session.py](../../../tests/e2e/desktop_session.py), `AccessibleUI.logout_confirm` and the existing [session worker](../../../tests/integration/graphical_smoke/lib/onpc_desktop_session.pm).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Extend the qualified Shell menu with Log Out and its separately owned confirmation surface. Consume each fresh input proof once and reacquire after the transition. Keep the combined desktop-session qualification's original Switch User and logout assertions intact.

## Live VM acceptance

Qualify explicit logout and confirmation from a fresh Parent desktop, then independently observe GDM. Cover independently supplied valid entry and wrong-owner/ambiguous/disabled/stale confirmation refusal. Run the existing combined `check_e2e_desktop_session` qualification for both modes after this binding is implemented; do not count either mode as the other's result. Require evidence and cleanup for each attempt.

Use the existing fixed qualification:

```sh
tools/run-tests integration check_e2e_desktop_session
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**003d** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
