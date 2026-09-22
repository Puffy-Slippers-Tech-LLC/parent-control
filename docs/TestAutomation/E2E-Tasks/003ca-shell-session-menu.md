# 003ca — Open and dismiss Shell session controls

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **DESK02 Shell Quick Settings and session-menu entry/readback**. Named consumer: task **003c** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003b** — GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback.

## Read only this context

Read DESK02/03 and the provider catalogue, [desktop_session.py](../../../tests/e2e/desktop_session.py), `AccessibleUI.session_menu_toggle`, `session_menu_power`, `session_menu`, `choose_session_action`, and [onpc_desktop_session.pm](../../../tests/integration/graphical_smoke/lib/onpc_desktop_session.pm).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.


## Implementation

Resolve the current Shell desktop, Quick Settings and session menu through the provider adapter. Read offered actions; implement normal dismissal and independent return to the same desktop.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

Open the menu from a fresh Parent desktop and an independently supplied valid entry, read the offered session actions, dismiss without selecting one and observe the same desktop. Refuse wrong session, ambiguity, disabled input and stale focus.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_shell_session_menu
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **003ca**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
