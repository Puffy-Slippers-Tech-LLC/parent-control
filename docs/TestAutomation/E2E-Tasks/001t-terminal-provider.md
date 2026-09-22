# 001t — Qualify the installed terminal adapter

Estimate: 40–60 minutes; an estimate, never a stop timer. Follow the
[master execution contract](../E2E-Execution-Plan.md#execute-one-task) and its
[provider rules](../E2E-Execution-Plan.md#external-provider-work-within-the-sequence).
This brief does not select or skip tasks.

## Scope and prerequisites

Deliver **FILE01/02/06 terminal command, help/denial projections and normal close/return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry.

## Read only this context

Read FILE01/02/06, INFO02, terminal methods in [accessible_ui.py](../../../tests/e2e/accessible_ui.py) and [parent_terminal.py](../../../tests/e2e/parent_terminal.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind the actual installed terminal owner and window, focused nonsecret input, bounded public output and close/return. Reuse the qualified Terminal search entry. Keep command echo distinct from a command result and preserve one submission/no replay after uncertain input. Authentication remains task 005.

## Live VM acceptance

In the live terminal, execute the declared installed-help command and independently read its required output. From the standard account, launch the Parent command and observe the actual owned management-denial message, then close/return normally. Include independently supplied valid terminal entry and wrong-window/unfocused-recipient/echo-only refusal. Pass focused safety tests, evidence and cleanup.

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
