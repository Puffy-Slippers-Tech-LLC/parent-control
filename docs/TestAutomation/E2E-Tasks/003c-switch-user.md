# 003c — Switch users through the shared system harness

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **DESK03 shared lock/greeter command and independent GDM result**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003ba** — GDM05 fresh Parent/standard entry and DESK01 no-prompt desktop; separate installed qualification, private collection and owned cleanup passed.

## Read only this context

Read DESK03, `SWITCH_PLAN` in [desktop_session.py](../../../tests/e2e/desktop_session.py), [session_control.py](../../../tests/e2e/session_control.py) and [onpc_desktop_session.pm](../../../tests/integration/graphical_smoke/lib/onpc_desktop_session.pm).
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Use the shared guarded SSH session helper. Bind the sole active local fixture desktop, lock through the public ScreenSaver API and call GDM's public switching API once. Independently require the same source session locked/inactive and usable GDM. Resolve dependencies before input; no Shell menus, wrong-account visit or fallback after uncertain input.

## Live VM acceptance

From a fresh Parent desktop, switch once and independently observe the retained source session and usable account list. Qualify a separately supplied valid entry. Reject wrong UID, remote/wrong-seat/ambiguous sessions, a changed source and replay before input. Preserve private evidence and owned cleanup. Window retention remains task 044's product scope.

Use the existing fixed qualification:

```sh
tools/run-tests integration check_e2e_desktop_session
```

Use the shared watchvm intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **003c** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
