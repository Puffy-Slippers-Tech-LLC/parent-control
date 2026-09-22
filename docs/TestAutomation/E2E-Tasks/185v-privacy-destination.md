# 185v — Qualify the Parent privacy destination

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **INFO01 Parent privacy page identity and close/return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **185w** — INFO01 Parent website browser identity and close/return.

## Read only this context

Read INFO01 and the actual privacy action in [about.py](../../../common/oh_no_parent_control_ui/about.py). Reuse only the qualified browser provider operations.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind the privacy destination independently, with public destination identity/content and normal return to the owned About/Parent surface.

## Live VM acceptance

Follow the installed privacy link, read the actual privacy page and return with the same Parent selection/settings. Independently reached valid entry works; wrong page, stale tab and uncertain close refuse. Require evidence and cleanup. A website pass does not qualify privacy.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_parent_privacy
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**185v** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
