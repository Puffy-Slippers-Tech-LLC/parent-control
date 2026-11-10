# VM scheduling task queue

Order and completion live here; the [master](VM-Scheduling-Design.md) owns the
next-task pointer. Baseline means the current checkout and owning contracts,
including unrelated work that must be preserved. Estimates cover implementation,
scoped checks and cleanup; live resource waits may add time.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | Protect unfinished runs during replacement | Baseline | Extract the source guard and establish a non-destructive retained-state version boundary before cutover. | Source protection and saved-state checks passed; queued builds retained. Shared-file approval and affected host checks passed; review findings resolved. |
| [x] | 002 | Share VM workers with preparation | 001 | Centralize allowed-pool reservation, availability, capacity and worker cleanup; move ordinary tests and preparation onto that executor. | 27 affected host checks passed after merge recovery with 180s limits; fresh Astra review clean. Shared-file review approved; unrelated edits excluded. Owned cleanup finished. Live qualification remains task 005. |
| [ ] | 003 | [Give test work one coordinator](VM-Scheduling-Tasks/003.md) | 001, 002 | Balance available workers across families; centralize per-family FIFO claims, independent coverage, accepted results and recovery. | 4–6 h |
| [ ] | 004 | [Move repairs and rounds onto shared scheduling](VM-Scheduling-Tasks/004.md) | 001, 002, 003 | Cut repairs over with adapter-based impact triage and conditional admission; remove duplicate scheduling and deliver run-wide rounds, task budgets and progress. | 1–2 days |
| [ ] | 005 | [Check the shared workflow on live VMs](VM-Scheduling-Tasks/005.md) | 001, 002, 003, 004 | Qualify bounded preparation, family execution, cancellation/resume and repair-round accounting; finish the ownership audit. | 3–6 h |

Task 004 keeps its coupled public cutover together so no released intermediate
path reinterprets old budgets or mixes scheduling authorities. Its internal
steps are finite in the brief; do not add a temporary alternate scheduler.
The other rows separate independently verifiable deliverables.

Scheduling exclusions: remote execution, new launchers/services, product behavior
changes, broad regression campaigns and unrelated fixture or UI work.
