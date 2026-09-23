# 003d — Log out through the shared system harness

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **DESK04 direct logout command and independent GDM result**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003ba** — GDM05 fresh Parent/standard entry and DESK01 no-prompt desktop; separate installed qualification, private collection and owned cleanup passed.
- **003c** — DESK03 shared lock/greeter command and independent GDM result.

## Read only this context

Read DESK04 and the shared session files referenced by task 003c's catalogue row, plus the session ownership/cleanup regressions.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Invoke `gnome-session-quit --logout --no-prompt` once as the bound desktop user over guarded SSH. Read back source-session disappearance and usable GDM. Reuse the existing `LOGOUT_PLAN` and shared worker; no logout confirmation, menu Cancel or forced-termination fallback.

## Live VM acceptance

From an independently prepared Parent desktop, log out once and require the source session ended and GDM usable. Reject wrong source/UID/session and uncertain replay. Run both modes of the existing combined qualification in separate restored attempts; preserve the switch mode's retained-session assertion.

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
Record the proven callable/scope and existing artifact, check **003d** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
