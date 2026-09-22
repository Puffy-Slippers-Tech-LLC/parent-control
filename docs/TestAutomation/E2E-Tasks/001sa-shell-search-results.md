# 001sa — Read Shell search results and the Terminal entry

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **SEARCH01/02/03/04/06 exact queries and Terminal result identity**. Named consumer: task **001s** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003b** — GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback.
- **003c** — DESK02/03 current Shell provider route and independently observed GDM return.
- **003d** — DESK04 current Shell logout/confirmation route and independently observed GDM return.

## Read only this context

Read the [search/sign-in contract](../E2E-Building-Blocks.md#search-and-standard-sign-in-contracts), search methods in [accessible_ui.py](../../../tests/e2e/accessible_ui.py), and the retained [parent_access.py](../../../tests/e2e/parent_access.py) and [parent_discovery.py](../../../tests/e2e/parent_discovery.py) consumers.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.


## Implementation

Bind Overview/app-grid/search to the scoped Shell provider and guarded keyboard focus. Read empty, first-character and full queries and identify the actual Terminal result. Reuse qualified keyring handling.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

On the VM, enter each declared query, read its exact result set, identify and focus Terminal without claiming terminal input, then dismiss normally. Independently supplied search entry works; wrong result, incomplete trees and stale focus refuse.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_shell_search_results
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **001sa**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
