# 001t — Read direct-command management denial

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Qualify PARENT01's shared direct-command launch with the standard-account
management-denial result and desktop return through the existing shared launch helper.

Reuse the maintained direct-command operations and qualified scope. Preserve the
management-denial assertion and independent desktop result. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **PARENT01 direct command, public management denial and desktop return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings.

## Read only this context

Read PARENT01, the direct launch and denial methods in [accessible_ui.py](../../../tests/e2e/accessible_ui.py) and [parent_terminal.py](../../../tests/e2e/parent_terminal.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Reuse `onpc_parent::launch`, its fixed executable and active-user session guard.
Preserve one submission/no replay after uncertain execution and independently
observe the specific owned denial, management absence and desktop return.
Help and manuals use shared INFO02 guarded command output. Supporting commands
never require Terminal entry or unrelated authentication dialogs.

## Live VM acceptance

From the standard desktop, invoke the shared direct Parent-command block and
observe the actual owned management-denial message, then close/return normally.
Include independent valid desktop entry and wrong-user, inactive/remote session,
missing denial and uncertain-submission refusal. Pass focused safety tests,
evidence and cleanup; submission success alone is never a denial result.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_terminal_provider
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**001t** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
