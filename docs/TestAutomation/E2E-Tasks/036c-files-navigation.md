# 036c — Select exact synthetic entries in Files

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add exact dynamic entry selection/readback under FILE04 and wrong-file/ambiguity checks. Reuse 036e for staged files and Location navigation.

Tasks **036e** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **FIX04 synthetic files; FILE07 and FILE04 exact Nautilus location/entry observations**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **009** — UI16.
- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry.
- **036e** — FIX04 synthetic files; FILE07 Nautilus directory entry.

## Read only this context

Read FILE04/07 and FIX04, the Nautilus provider row and provider projections in [accessible_ui.py](../../../tests/e2e/accessible_ui.py) and [ui_observations.py](../../../tests/e2e/ui_observations.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Prepare the finite harmless files needed by feedback and document consumers, including paths with spaces, through FIX04. Implement Nautilus Location navigation and exact dynamic entry resolution inside its owned provider surface. Directory identity and complete entry lists are independent public observations.

## Live VM acceptance

On the pinned VM, open Files, navigate to the declared directory, read the exact entries and select the declared file. Repeat from an independently opened valid Files surface. Refuse wrong directory, ambiguous names, lost focus and incomplete lists. Require input/readback, sanitized evidence and cleanup; fixture staging alone cannot pass navigation.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_files_navigation
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**036c** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
