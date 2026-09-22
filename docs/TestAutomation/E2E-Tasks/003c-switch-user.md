# 003c — Switch User through qualified Shell controls

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Bind Switch User and independently observed GDM return using 003ca. Preserve the fixed Switch User qualification and existing SWITCH_PLAN guards.

Tasks **003ca** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **DESK02/03 current Shell provider route and independently observed GDM return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003b** — GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback.
- **003ca** — DESK02 Shell Quick Settings and session-menu entry/readback.

## Read only this context

Read DESK02/03 and the provider catalogue, [desktop_session.py](../../../tests/e2e/desktop_session.py), `AccessibleUI.session_menu_toggle`, `session_menu_power`, `session_menu`, `choose_session_action`, and [onpc_desktop_session.pm](../../../tests/integration/graphical_smoke/lib/onpc_desktop_session.pm).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Resolve desktop, Quick Settings, the session menu and Switch User inside a Shell-specific adapter. Prefer a direct accessibility action; otherwise observe each bounded keyboard focus step. Preserve the existing SWITCH_PLAN stages and guards. Add a fixed Switch User selection to the maintained qualification envelope so this task does not require the later logout binding.

## Live VM acceptance

From a fresh logged-in Parent, open the declared menu, read its available actions, invoke Switch User once and independently observe the usable GDM account list. Repeat from an independently supplied valid desktop/menu entry. Reject wrong session, ambiguous menu, hidden/disabled action, stale focus and uncertain input. This qualifies the GDM destination; retained windows remain task 044's scope. Pass safety tests, collection and cleanup.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_desktop_switch
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**003c** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
