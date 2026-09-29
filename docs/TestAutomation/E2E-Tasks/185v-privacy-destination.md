# 185v — Check the Parent privacy link

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **INFO01 Parent privacy link clickability**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **185w** — INFO01 Parent website link clickability.

## Read only this context

Read INFO01 and the privacy control in [about.py](../../../common/oh_no_parent_control_ui/about.py). Reuse the shared clickable-link reader.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Check the ID-resolved privacy link is visible, enabled and offers a usable
public activation action, then stop. Do not activate it, inspect its URI or
validate any browser, privacy page or portal workflow.

## Live VM acceptance

Open installed About, check privacy link clickability without invoking it,
close About and compare the same Parent selection/settings. Qualify independent
entry and missing/disabled/nonactionable/wrong-owner refusal. Require evidence
and owned cleanup. A website pass does not establish privacy link clickability;
no external destination is inspected.

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
