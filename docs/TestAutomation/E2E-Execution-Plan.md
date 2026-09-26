# E2E execution plan

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md

Read this entry plan and the **Next task** brief, then use the reading routes
below. The [documentation map](README.md) defines ownership and status terms.
This master owns selection, execution and completion, with detailed procedures
in [execution contracts](E2E-Execution-Contracts.md). Its canonical
[queue](E2E-Task-Queue.md) is one fixed sequence, including provider qualification
and retained regressions. Briefs never select a different task.

Queue IDs identify tasks. Numeric case IDs in briefs and `--id` commands identify
inventory variant `coverage_id` values; `E2E-NNN` identifies their scenario family.
Keep each brief's case, variant parameters, recipe and consumer hints aligned
with those owners. Reconciliation checks metadata without closing queue rows or
changing runtime readiness on the strength of documentation alone.

## Next task

Next task: **015b — [E2E-015: kiosk-escape](E2E-Tasks/015b-case-48.md)**.

Implement complete case 48 using the qualified FLOW04 kiosk request composition,
then Escape once and observe the absent form and usable GDM. Preserve independent
Parent preparation, public results, collection and owned cleanup.

This pointer must name the first unchecked active queue row. After completion,
advance to the following unchecked row. An incomplete or blocked task keeps the
pointer; record its exact remaining work and return condition here and in its
row. Repair a stale pointer against table order, without scanning for other
eligible work.

## Current scope

Current scenario status and counts come from `tests/e2e/scenarios.json`; block
status comes from the catalogue. The initial provider migration gate is closed.
On 2026-09-23 the developer confirmed separately validating all seven ready
cases—1, 3, 4, 5, 6, 151 and 193—and explicitly directed that they need not be
rerun. This confirmation supplies the shared regression gate's acceptance;
no runner artifact was supplied for that complete set.

Task 151r separately passed the complete guarded About/license/return case in
run `20260923T202401Z-9e9a5886`, including unchanged child/settings, capture
reconciliation, product, infrastructure, collection, owned cleanup and baseline
restoration. Before the developer's direction, the shared-change audit also
started fresh case 1 and 3 runs; both passed with collection and cleanup
(`20260923T202714Z-fc680b74` and `20260923T202932Z-38973041`). Coverage was
regenerated after each successful case. Cases 4, 5, 6 and 193 were not rerun
during this close-out.

Preserve the customer assertions and registered bindings; supporting routes
follow the current mandate. A checked queue task records its delivered scope;
it does not override a later `pending` block or scenario status. Future shared
changes retain their affected regression requirements. A capability run or
historical `ready` inventory binding does not itself validate a complete case.

Retired E2E IDs 140–150 remain separate system-test obligations and cannot be
selected as UI cases. Deferred mute task 154 is outside current-release
completion and blocks no active task. SEC01 retains secret safety; GDM10's
unnecessary navigation extraction is retired. A customer pass cannot replace displaced engineering
obligations under their maintained owners.

## Execute one task

1. Follow repository AGENTS.md, start at [System-Design.md](../System-Design.md),
   apply [Approval-Tools.md](../Approval-Tools.md), and inspect working-tree status.
   Preserve unrelated edits and reuse existing session authorization.
2. Verify that Next task is the first unchecked active queue row, and check
   its required capabilities and task-local prerequisites. Read only those rows.
   A checked historical task cannot override a currently pending provider route.
3. Read the selected brief and its scoped references as described below.
   Requires lists task IDs, not block IDs. Use each task's delivered capability
   scope, not predecessor documents or saved VM state. Verify the exact surface,
   route and branch in maintained
   callables; a ready block ID does not qualify every binding.
4. Implement that slice, its meaningful supporting checks and stated acceptance.
   Use the [composition preflight](E2E-Building-Blocks.md#composition-preflight)
   to catch integration mistakes before spending a live attempt.
   Implement leaves before composites, including within a small task. Bind
   entry, finite inputs, expected public results, precision and deadlines first.
   Apply the [UI automation mandate](../Mandates/UI-Automation-Mandate.MD) and
   [functional validation](E2E-Building-Blocks.md#functional-validation) to every
   required operation. Use shared shortcuts, SSH or system commands for Shell,
   GDM preparation and other supporting work. GUI adapters are for tested product
   features and unavoidable graphical authentication; qualify those remaining
   routes and fix missing owned IDs before their consumers.
5. Finish live verification, cleanup and close-out. Report the task ID, result
   and next task. The next identical prompt repeats this workflow.

**Execution order:** follow the queue from top to bottom, one unchecked active
row at a time. There is no alternate provider queue, runtime eligibility search
or automatic jump around a blocker. IDs and filenames are stable labels, not
sort keys. A scenario never depends on another scenario's execution.

If blocked, retain delivered scope and append only
`Blocker: …; resume when: …`. Complete authorized preparation for that task,
including concrete reviewable inputs when sending authorization is missing.
Keep the row unchecked and the pointer on it; report the unresolved requirement.
Do not mark an unavailable route, missing authorization or future calendar window
as passed, and do not choose another row. A newly discovered prerequisite becomes
an explicit task immediately before its consumer through a documented queue
repair; revalidate the single sequence before continuing.
Product-behavior mismatches follow the
[failure contract](../../tests/README.md#handling-test-failures): preserve the
failure, report expected versus actual and obtain any missing behavior decision.
Fix proven mechanical test defects without weakening checks.

## Load only the selected context

The working set is this entry plan, one brief, and applicable contract sections,
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
do not select a deferred row. The task and block IDs are examples; substitute
the selected row's actual IDs. Use narrow JSON projections for inventory
variants/counts. Do not dump the
whole queue, catalogue, recipes, inventory or source modules, recursively read
briefs, or recompute established task order during routine implementation.

Start source inspection at the brief/catalogue's file and symbol references,
then follow relevant callees, callers, shared state and safety tests. Search for
affected consumers when a shared contract changes. Broaden for missing contracts,
stale references, uncertain behavior or failures; there is no token, file-count
or reading-time cap that can excuse incomplete understanding or validation.
A truncated result needs a narrower complete read, not a guessed conclusion.

Keep the selected brief's **Read only this context** useful: document headings,
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
They retain snapshot preparation, watchvm, isolated safety gates, affected
regressions, public-result observation, collection and cleanup requirements.
Host checks cannot complete live work. Task 192 remains the sole host-only
exception; no new exception is introduced by scoped reading.

## Completion and document cleanup

After successful acceptance and owned cleanup, follow the full
[completion contract](E2E-Execution-Contracts.md#completion-and-document-cleanup).
Refresh coverage after every completed scenario, maintain only affected
contracts/status, close only the selected row and advance the sole pointer.
Preserve blockers and incomplete work on the current row. Documentation
close-out alone does not require rerunning an unchanged valid attempt.

## Ordered task queue

The [ordered checklist](E2E-Task-Queue.md#ordered-task-queue) contains every task's
ID, prerequisites, scope, estimate and brief link. It is scheduling metadata,
not required background reading for the current task. Check and maintain its
rows as part of this master plan; use scoped reads as described above.
