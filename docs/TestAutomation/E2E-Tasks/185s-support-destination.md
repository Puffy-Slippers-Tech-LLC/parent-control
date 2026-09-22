# 185s — Qualify the Parent support mail destination

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **INFO01 Parent support mail recipient/subject and close without sending**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **044a** — DESK10 same-desktop window switching.
- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry.

## Read only this context

Read INFO01 and the actual support action in [about.py](../../../common/oh_no_parent_control_ui/about.py). Identify the installed mail handler before qualification.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind the actual mail-composer owner and displayed intended recipient/subject. Use scoped public semantics for external controls and ordinary Cancel/close with independent return. This task does not send mail or a feedback report.

## Live VM acceptance

Activate Support from installed Parent, read the expected recipient/subject, close without sending and compare unchanged Parent settings. Reject wrong recipient/handler, ambiguous composer and uncertain close. Qualify independent valid entry, collect sanitized evidence and clean up. Missing usable mail handling is a blocker on this task.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_parent_support
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**185s** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
