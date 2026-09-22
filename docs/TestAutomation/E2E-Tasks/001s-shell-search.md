# 001s — Prove Parent is unavailable to a standard account

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add standard-account launcher unavailability, exact web-description readback and complete stable absence. Reuse 001sa/001sb for query handling and administrator launch; never activate the web suggestion.

Tasks **001sa**, **001sb** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003b** — GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback.
- **003c** — DESK02/03 current Shell provider route and independently observed GDM return.
- **003d** — DESK04 current Shell logout/confirmation route and independently observed GDM return.
- **001sb** — SEARCH05 administrator Parent launch and owned-window result.

## Read only this context

Read the [search/sign-in contract](../E2E-Building-Blocks.md#search-and-standard-sign-in-contracts), search methods in [accessible_ui.py](../../../tests/e2e/accessible_ui.py), and the retained [parent_access.py](../../../tests/e2e/parent_access.py) and [parent_discovery.py](../../../tests/e2e/parent_discovery.py) consumers.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Implement provider-local Overview/app-grid/search resolution and guarded keyboard focus. Read empty, first-character and full queries independently. Distinguish the real Parent launcher from its web suggestion and resolve the actual Terminal launcher for the next consumer. Keep owned Parent controls ID-addressed. Reuse the qualified keyring handling before opening Overview; never replay a shortcut consumed by a modal.

## Live VM acceptance

On the pinned VM, launch Parent once from a real administrator search and independently observe its owned window. Through a standard-account entry, require exact query readback, the associated web description and complete stable exclusion of the launcher/management window. Do not activate the web suggestion. Qualify Terminal search-result identity/focus without claiming terminal input. Cover independent valid entry, wrong result, ambiguity, incomplete absence, stale focus and uncertain input; collect evidence and clean up.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_shell_search
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**001s** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
