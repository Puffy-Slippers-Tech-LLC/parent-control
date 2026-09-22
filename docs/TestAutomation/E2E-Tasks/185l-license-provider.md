# 185l — Qualify the installed license viewer

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **ABOUT02/03 actual license handler identity/content and close/return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry.

## Read only this context

Read ABOUT02/03, the default-viewer provider row and [parent_about.py](../../../tests/e2e/parent_about.py). Inspect only the actual handler reached from the installed About dialog.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind one real default handler's document identity, meaningful license content, active readiness and normal close/return. Use owned IDs for About and a scoped provider adapter for its viewer. Reuse this binding for later document work only when the handler matches.

## Live VM acceptance

Open the license from Parent About, independently read the correct document/content, close the viewer and verify the same About/Parent state. Cover independent valid entry, different document, ambiguous window, empty/unrelated content and uncertain close refusal. Require live evidence and cleanup.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_license_viewer
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**185l** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
