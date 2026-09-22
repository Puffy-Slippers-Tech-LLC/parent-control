# 195a — Qualify the installed text-document handler

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **FILE08 text-document identity/content and normal close/return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE07/04/05; FIX04 synthetic files.

## Read only this context

Read FILE08 and the registered-document-editor provider row; use the actual handler opened by the prepared synthetic text fixture.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind Files Open to the real text editor, its document identity, meaningful content and active close/return. Reuse license-viewer code only for the same handler. Resolve the external document through its provider adapter; a window title alone cannot identify it.

## Live VM acceptance

Open the declared text file through Files, read exact public identifying content, close normally and observe return. Qualify independently opened valid Files entry. Reject wrong document, ambiguous window, unrelated/empty content and uncertain close; require installed evidence and cleanup.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_document_open
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**195a** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
