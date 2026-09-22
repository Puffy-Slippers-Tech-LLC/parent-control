# 036d — Qualify public file copy and destination readback

Estimate: 30–50 minutes; an estimate, never a stop timer. Follow the
[master execution contract](../E2E-Execution-Plan.md#execute-one-task) and its
[provider rules](../E2E-Execution-Plan.md#external-provider-work-within-the-sequence).
This brief does not select or skip tasks.

## Scope and prerequisites

Deliver **FILE05 copy; exact source/destination and public resulting entry**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036c** — FIX04 synthetic files; FILE07 and FILE04 exact Nautilus location/entry observations.

## Read only this context

Read FILE05 and the qualified Nautilus navigation/entry callables in the catalogue.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Select one declared synthetic source, copy through ordinary input to the declared destination and independently observe the new file there. Keep source identity, destination identity and duplicate-name checks distinct. This slice has no overwrite branch.

## Live VM acceptance

Copy the real fixture on the installed VM, compare exact public source/destination entries and verify the intended result. Qualify independent valid entry, wrong source/destination and duplicate-name refusal. Uncertain copy is never replayed. Require collection and cleanup.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_files_copy
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**036d** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
