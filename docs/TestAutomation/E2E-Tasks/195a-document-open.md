# 195a — Read declared text artifacts through guarded SSH

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **FILE08 bounded text-artifact identity/content reads over SSH**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.

## Read only this context

Read FILE08's artifact-read contract and the shared FILE05 fixture/path guards.
Use the declared synthetic text fixture; no document-editor provider is needed.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Add a fixed read-only operation to the shared guarded SSH file helper. Bind the
owned attempt, fixture user and exact declared artifact to bounded text reads
through supported filesystem APIs. Pin file identity, reject symlinks, traversal,
replacement and unrelated paths, and return only declared content comparisons
and sanitized evidence. No arbitrary path reader or editor launch is required.
Product-created files become eligible only through the caller's actual Save
result; this helper never reads source logs, private drafts or collector state.
The distinct retained-work FILE08 binding still uses APP01/03/04 to prove real
app activity; reading a file cannot qualify it.

## Live VM acceptance

On the VM, independently read the declared synthetic text artifact through the
shared command helper and compare its exact expected content. Repeat with an
independently prepared valid artifact. Reject wrong attempt/user/file, replaced
or missing files, unrelated/empty content and over-limit reads; require bounded
evidence and owned cleanup. No GUI handler qualification or complete-case credit.

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
