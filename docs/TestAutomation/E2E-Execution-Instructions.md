# Shared E2E execution instructions

[Plan A](E2E-Execution-Plan.md), [Plan B](E2E-Execution-PlanB.md) and
[Plan C](E2E-Execution-PlanC.md) use these
instructions and the [execution contracts](E2E-Execution-Contracts.md).
Each master owns its own **Next task** pointer and declares its own task queue.
Read the selected master, these instructions and its current brief. Select and
close work only in that queue. No plan has an unfinished prerequisite in
another, and none executes, advances or waits for another plan.

Run `tools/write-e2e` for Plan A, `tools/write-e2e --planb` for Plan B,
or `tools/write-e2e --planc` for Plan C. The two selectors are mutually exclusive.
Use the same selector when attaching, stopping, reloading, reconciling or finishing
close-out. Each plan retains independent locks, checkpoints, task limits,
suspended tasks and optimization batches. Plan A keeps its existing storage;
Plans B and C each use the shared plan namespace derived from their master path. They may run
at different times or concurrently in separate branches/checkouts. Plan A uses
the launcher's configured default branch; Plans B and C default to the current
checkout's branch. Use `--branch` to select a different checkout explicitly.
Shared VM leases and Git close-out locks still serialize access to shared resources.
Concurrent execution in one checkout is unsupported because agents edit shared source.

Unfinished task IDs and brief paths belong to exactly one queue. Keep each
prerequisite group with its consumers. Plans B and C include checked records for only
its already-delivered prerequisites; these are a fixed baseline at the split,
not work delegated to another plan. `Baseline` on those records means their prerequisites
were already satisfied before the split. Preserve their delivered scope and do
not requalify unchanged completed work. Pending task dependencies must stay
within the owning queue. New shared work needed by multiple plans must be delivered
before it becomes a prerequisite; do not add cross-plan pending dependencies.

Queue IDs identify tasks; numeric case IDs identify inventory `coverage_id`
values and `E2E-NNN` names scenario families. Preserve cases, acceptance scopes,
variant parameters and exclusions when maintaining any queue. The
[generic execution-plan instructions](../Execution-Plans.md) own shared launcher
structure; E2E acceptance and model policy remain specialized here.

Original delivered scope and retained reports remain in the
[historical queue rows](E2E-Task-Queue.md#ordered-task-queue) and their exact
[catalogue qualifications](E2E-Building-Blocks.md). Those historical results do
not qualify another binding or complete a future case. The independent language
histories remain in the
[acceptance decomposition](E2E-Scenario-Recipes.md#personal-language-acceptance-decomposition).

Scheduling exclusions are maintained in the
[queue's exclusion record](E2E-Task-Queue.md#excluded-automation).
Do not recreate removed tasks, briefs, dependencies or removed case IDs.

Current work follows the mandate's
[public logical-text acceptance](../Mandates/UI-Automation-Mandate.MD#input-and-independent-results)
and geometry prohibition. Historical visual or focus observations do not create
future acceptance obligations.

## Current scope

The completed [kiosk baseline](../SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits) retains existing
coverage through C05f. The [local desktop design](../SystemDesign/Kiosk-Confinement.md#local-desktop-boundary)
defines the existing graphical session boundary. The remaining confinement
improvements plan and its targeted test queue have been removed.
New general feature automation remains in the selected queue. The
[expiry coverage allocation](UI-and-E2E-Coverage.md#expiry-coverage-allocation)
uses these same canonical rows; tasks 172a–172l contain only uncovered engineering
deltas merged from the removed broker plan. Accepted work must not be implemented
or run again under another task/selector. Distinct
remaining customer outcomes and current pending status are preserved. The
[reuse map](E2E-Building-Blocks.md#cross-plan-baseline-reuse) records the delivered
shared fixture/core-effects work; duplicate tasks 313a/313 are no longer
scheduled. Optional feature expansion remains in 314/315. Preserve the queue
order and pointer; reuse closes no other plan's row.

The [shared task contract](E2E-Execution-Contracts.md#task-brief-contract)
applies the required [Application UI API](Application-UI-API.md) route,
[result-oriented mandate](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope)
and [UI/E2E allocation](UI-and-E2E-Coverage.md) to retained implementations
and unfinished briefs. Apply its
[product-focused review](E2E-Execution-Contracts.md#product-focused-journeys) to
remove incidental provider steps while preserving each case's product outcomes
and queue order.
The queue owns exclusions and displaced UI obligations; the
[status vocabulary](README.md#status-vocabulary) distinguishes historical
completion from current route qualification and scenario registration.
Documentation or allocation review does not advance the pointer or replace
live acceptance.

The [system allocation](UI-and-E2E-Coverage.md#reuse-of-system-coverage)
keeps complete customer journeys while removing duplicate engineering cases,
steps and acceptance matrices. The queue records removed duplicate tasks;
remaining briefs identify the missing assertion or binding under the existing
owner. Do not recreate removed qualifications or replace a journey's public
result with another suite's pass.

Current scenario status and counts come from `tests/e2e/scenarios.json`; block
status comes from the catalogue. The initial provider migration gate is closed.
On 2026-09-23 the developer confirmed separately validating the seven then-ready
cases—1, 3, 4, 5, 6, 151 and 193—and explicitly directed that they need not be
rerun. This confirmation supplies the shared regression gate's acceptance;
no runner artifact was supplied for that complete set.

That historical set is not the current runnable inventory. Delivered scopes and
their evidence stay in the queue/catalogue; future shared changes follow the
[live regression policy](E2E-Execution-Contracts.md#live-verification-contract).

Preserve customer assertions and registered bindings except explicitly
[reallocated UI-only coverage](UI-and-E2E-Coverage.md#duplicate-review-and-allocation).
Displaced engineering results remain under
[inventory reconciliation](E2E-Building-Blocks.md#inventory-reconciliation)
and their proper suite; a customer pass supplies no engineering qualification.
The queue's [deferred work](E2E-Task-Queue.md#deferred-future-work) has no active
consumer and blocks no current-release task.

## Execute one task

### Snap acceptance boundary

On 2026-11-05 the developer explicitly separated Snap remediation from E2E.
[Snap limitations and options](../Snap_Limitation.md) own today's findings and
the future product choices. Apply this boundary to all three plans, all their
capabilities, recipes, supporting checks and regression selections:

- Retain Allowed Snap launch/use, public catalogue and saved-choice readback
  where declared. A saved block or hidden launcher is not an enforcement pass.
- Snap denial, closure and alternating Soft permission cases are deferred under
  [Plan B](E2E-Task-QueueB.md#deferred-future-work). Keep their inventory IDs
  pending without executable bindings. They do not gate active work, current
  release completion, or the Allowed grid qualification and case 86.
- Do not rerun task 109's known failure, invoke its maintenance reproduction,
  investigate the missing label/admission gap, add an expected-failure workaround,
  or ask the developer to choose a Snap solution during ordinary E2E execution.
  Historical next-probe handoffs are superseded by this scope decision.
- Other app cases use their explicitly declared native, Flatpak or game inputs.
  Generic APP02/FLOW08, Hard/Soft and other-user assertions do not introduce a
  Snap matrix. Preserve their full public results, isolation and safety guards;
  do not substitute a Snap app as their fixture.
- A future shared adapter change still owns affected checks within supported
  scope. Allowed Snap regressions remain available; deferred denial/closure
  acceptance is not a regression gate. New unrelated failures follow normal
  failure handling. Known Snap limitations need only a reference to their owner,
  not another investigation or product-choice request.

Resume enforcement work only after an explicit developer request for separate
Snap remediation and a chosen supported contract, then qualify it before
reactivating the deferred cases. Deferral is not a pass or evidence that all
Snaps fail identically. Native/Flatpak requirements remain unchanged.

### Active task workflow

1. Apply [repository instructions](../../AGENTS.md) and inspect working-tree status.
2. Verify that Next task is the first unchecked active queue row, and check
   its required capabilities and task-local prerequisites. Read only those rows.
   A checked historical task cannot override a currently pending provider route.
3. Read the selected brief and its scoped references as described below.
   Requires lists task IDs, not block IDs. Use each task's delivered capability
   scope, not predecessor documents or saved VM state. Verify the exact surface,
   route and branch in maintained
   callables; a ready block ID does not qualify every binding.
4. Apply the [shared task contract](E2E-Execution-Contracts.md#task-brief-contract)
   and implement the selected slice, supporting checks and stated acceptance.
   Bind entry, finite inputs, expected public results, precision and deadlines;
   reuse qualified shared operations and extend only the missing boundary.
   Review the [VM timing contract](../Mandates/VM-Mandate.MD#timing-and-slow-vm-resilience)
   against the complete composition, including preparation and recovery.
   Apply the [bounded implementation rules](E2E-Building-Blocks.md#keep-supporting-work-bounded)
   and changed-boundary composition preflight before the first live attempt.
5. Finish live verification, cleanup and close-out. Report the task ID, result
   and next task. The next identical prompt repeats this workflow.

**Execution order:** follow the queue from top to bottom, one unchecked active
row at a time. There is no alternate provider queue, runtime eligibility search
or automatic jump around a blocker. IDs and filenames are stable labels, not
sort keys. A scenario never depends on another scenario's execution.

If blocked, retain delivered scope and append
`Blocker: …; resume when: …`. Complete authorized preparation for that task,
including concrete reviewable inputs when sending authorization is missing.
Keep the row unchecked and the pointer on it; report the unresolved requirement.
Do not mark an unavailable route, missing authorization or future calendar window
as passed, and do not choose another row. A newly discovered prerequisite becomes
an explicit task immediately before its consumer through a documented queue
repair; revalidate the selected sequence before continuing.
Product-behavior mismatches follow the
[failure contract](../../tests/README.md#handling-test-failures): preserve the
failure, report expected versus actual and obtain any missing behavior decision.
Fix proven mechanical test defects without weakening checks.

## Resume after a reviewed queue revision

Apply a split to a running checkout only after its current response, accepted
completion and Git close-out have finished. Do not replace the queue underneath
an in-flight response or pending recovery transaction. Plan A keeps its existing
checkpoint store; a fresh task session adopts its remaining queue. Plan B keeps
its existing namespace and current task. Plan C starts with no copied checkpoint
or suspended work from either plan. The three-way split preserves Plan A's task
160 and Plan B's task 135a, their pointers and their pending prerequisite groups.
Only later groups move: Flatpak fixtures/command/grid cases, package update/removal
124/125, suspend 166a/167/166/168 and usage/expiry 172–172l from A;
169/170/171/173/174/175/178/179,
143–149, 191/238/239/240/242/245 and 314/315 from B. IDs are labels, not ranges
to execute implicitly. The original briefs and acceptance stay unchanged.

Ordinary restarts retain strict interruption and close-out guards. If an inactive
checkpoint retains the same unfinished task as the revised pointer, restart
normally: its task/session history is preserved and the next session reads the
revised queue. A completed checkpoint with no pending recovery or due optimization
also selects the revised queue's next task normally; its historical completed
task ID does not require administrative reconciliation. Do not modify or reset
these checkpoints just to record the split.

If an inactive `write-e2e` checkpoint instead retains an unfinished task displaced
by an explicitly reviewed queue revision, use its administrative reconciliation
route before restarting:

```sh
tools/write-e2e --reconcile RUN --check
tools/write-e2e --reconcile RUN
# Plan B uses its own retained RUN:
tools/write-e2e --planb --reconcile RUN --check
tools/write-e2e --planb --reconcile RUN
# Plan C uses only its own retained RUN:
tools/write-e2e --planc --reconcile RUN --check
tools/write-e2e --planc --reconcile RUN
```

`RUN` is the exact current retained run ID. Review the dry-run result first.
Reconciliation preserves the original checkpoint, unfinished-task history,
staging ownership and optimization ledger, then adopts the current queue and
its first unchecked task. It refuses active owners and unresolved result,
completion or optimization transactions. It starts no agent, VM or Git action
and grants no acceptance. Current briefs and prerequisites govern resumed work;
superseded handoffs cannot select another task or require replaying completed
checks. Normal implementation still owns any required cleanup and acceptance.
Do not delete checkpoints or use ordinary-plan reconciliation for this E2E store.

## Load only the selected context

The working set is the selected master, these instructions, one brief, and applicable contract sections,
rows, recipe branches and source callables. Links are reading routes, not an
instruction to recursively load documents. Reuse unchanged text already present
in the current context, including injected AGENTS.md; after a new session or
compaction, retrieve missing applicable requirements. A remembered summary or
prior pass never replaces a current contract or source check.

| Need | Read |
| --- | --- |
| Product boundaries | Start at [System design](../System-Design.md#how-to-read-this-design): overview and module map, then the owning module/sections for the affected boundary. Follow related modules when the change crosses their boundary. |
| Authorization | [Default workflow](../Approval-Tools.md#default-workflow-and-rare-exceptions), then the sections for the actual operation. Setup, publication and VM maintenance procedures are conditional, not startup reading. |
| Selection and prerequisites | First unchecked queue row, selected brief, and its required task rows. Use delivered scopes and current catalogue qualifications; do not load predecessor briefs. |
| Implementation | Selected block rows and their contract sections; named recipe's selected branches, finite inputs and common entry/time rules; relevant inventory variants and family declaration. |
| Acceptance before implementation | [Shared live rules and selected task type](#live-verification-contract); also [provider rules](#external-provider-work-within-the-sequence) when using that exception. |
| Test execution | Launcher help/listing for exact routes; [failure handling](../../tests/README.md#handling-test-failures). Read scheduling, fixture/support, cleanup or artifact sections when that operation needs them. |
| Close-out | [Completion](#completion-and-document-cleanup), following unchecked row and its prerequisites. |
| Splitting, reordering or a newly discovered prerequisite | Full [task-size and order contract](E2E-Execution-Contracts.md#task-size-and-order) and queue consistency checks. |
| Lunar case 253 or its preparation | [Planned Lunar regression](E2E-Execution-Contracts.md#planned-lunar-client-regression). |

Use quoted searches to locate headings, rows and symbols, then read bounded
sections and complete relevant functions. For example:

```sh
rg -n -m 1 '^(\| \[ \] \||## Deferred future work$)' 'docs/TestAutomation/E2E-Task-Queue.md'
rg -n '^\| \[.\] \| (003ab|003a) \|' 'docs/TestAutomation/E2E-Task-Queue.md'
rg -n '^\| (GDM01|GDM02|GDM08|GDM09) \|' 'docs/TestAutomation/E2E-Building-Blocks.md'
sed -n '/^## Live verification contract$/,/^### Capability acceptance$/p' 'docs/TestAutomation/E2E-Execution-Contracts.md'
```

The first lookup stops at the deferred-work heading if no active row remains;
do not select a deferred row. The task and block IDs and Plan A queue path are
examples; substitute the selected row's actual IDs and the selected master's
queue path. Use narrow JSON projections for inventory
variants/counts. Do not dump the
whole queue, catalogue, recipes, inventory or source modules, recursively read
briefs, or recompute established task order during routine implementation.

Start source inspection at the brief/catalogue's file and symbol references,
then follow relevant callees, callers, shared state and safety tests. Search for
affected consumers when a shared contract changes. Broaden for missing contracts,
stale references, uncertain behavior or failures; there is no token, file-count
or reading-time cap that can excuse incomplete understanding or validation.
A truncated result needs a narrower complete read, not a guessed conclusion.

Keep the selected brief's reading references useful: document headings,
block/recipe IDs, source paths and symbols, relevant test files and exact live
selectors. Identify planned selectors as unimplemented until verified. These
are navigation hints, not copied contracts or cached readiness. Repair stale
references encountered during work; do not inspect every future task in advance.
At close-out, keep the next brief usable when changed interfaces affect its
references, without implementing or qualifying that task.

## Task size and order

Ordinary tasks target one 15–30-minute session including live acceptance and
close-out; estimates are not stop timers. Keep one complete scenario in one task.
Split independent work estimated above 30 minutes before implementation.
Before splitting or changing dependencies/order,
read the full [sizing and ordering contract](E2E-Execution-Contracts.md#task-size-and-order).
Preserve indivisible histories, real waits, acceptance and explained exceptions;
never split off verification or reduce checks to fit an estimate.

## External-provider work within the sequence

When implementing, changing or qualifying an external-provider adapter, read the
[provider execution contract](E2E-Execution-Contracts.md#external-provider-work-within-the-sequence)
and the selected route's catalogue qualification. This includes provider input
used during preparation and retained cases. Reuse documented discovery findings;
each affected route still needs its stated live qualification.

## Live verification contract

Before implementation, read the
[shared live rules](E2E-Execution-Contracts.md#live-verification-contract)
(up to **Capability acceptance**) and the selected task's
[capability](E2E-Execution-Contracts.md#capability-acceptance),
[scenario](E2E-Execution-Contracts.md#scenario-acceptance) or
[system](E2E-Execution-Contracts.md#system-acceptance) acceptance branch.
They retain snapshot preparation, watch, isolated safety gates, affected
regressions, public-result observation, collection and cleanup requirements.
Host checks cannot complete queued live work. Explicit UI obligations follow
[UI acceptance](E2E-Execution-Contracts.md#ui-acceptance); historical task 192
retains its host-only exception. Documentation reconciliation follows the
[separate working route](README.md#working-route) and closes no queue row.

## Completion and document cleanup

After successful acceptance and owned cleanup, follow the full
[completion contract](E2E-Execution-Contracts.md#completion-and-document-cleanup).
Refresh coverage after every completed scenario, maintain only affected
contracts/status, close only the selected row and advance the selected plan’s pointer.
Preserve blockers and incomplete work on the current row. Documentation
close-out alone does not require rerunning an unchanged valid attempt.

## Ordered task queue

The selected master's ordered checklist contains every task's
ID, prerequisites, scope, estimate and brief link. It is scheduling metadata,
not required background reading for the current task. Check and maintain its
rows as part of the selected master plan; use scoped reads as described above.
