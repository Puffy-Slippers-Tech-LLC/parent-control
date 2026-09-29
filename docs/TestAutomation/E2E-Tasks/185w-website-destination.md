# 185w — Check the Parent website link

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **INFO01 Parent website link clickability**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **044a** — DESK10 same-desktop window switching.
- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings.

## Read only this context

Read INFO01, the Parent Help/About contract and website action in [about.py](../../../common/oh_no_parent_control_ui/about.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Open the owned Help/About surface and use the shared clickable-link reader for
its ID-resolved website link. Require visible/enabled state and a usable public
activation action, then stop. Do not activate it, inspect its URI, launch or
qualify a browser, or validate a destination. Ordinary product clicks use the
system default browser; tests have no Firefox/Chrome dependency.

## Live VM acceptance

Capture Parent child/settings, open About, verify the website link is clickable
without invoking it, close About and compare the unchanged Parent. Qualify
independent valid entry and missing/disabled/nonactionable/wrong-owner link
refusal. Require live evidence and owned cleanup. Browser availability, URL,
page content, destination identity and external return are outside acceptance.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_parent_website
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**185w** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
