# E2E execution plan

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md

Read this entry plan and the **Next task** brief, then use the reading routes
below. The [documentation map](README.md) defines ownership and status terms.
This entry point owns selection and reading routes, with execution and completion procedures
in [execution contracts](E2E-Execution-Contracts.md). Its canonical
[queue](E2E-Task-Queue.md) is one fixed sequence, including provider qualification
and retained regressions. Briefs never select a different task.

Queue IDs identify tasks. Numeric case IDs in briefs and `--id` commands identify
inventory variant `coverage_id` values; `E2E-NNN` identifies their scenario family.
Keep each brief's case, variant parameters, recipe and consumer hints aligned
with those owners. Reconciliation checks metadata without closing queue rows or
changing runtime readiness on the strength of documentation alone.

## Next task

Next task: **300j — [Qualify kiosk selected-child language restoration](E2E-Tasks/300j-kiosk-language-restoration.md)**.

Task 300's Chinese recipe now starts product-free and installs the latest verified
current-source package once, observes the Chinese pre-reboot prompt, then reboots
and checks Chinese first presentation and two approvals across fresh kiosk entries.
It does not install v1.2 or test an upgrade. Tasks 300c/300d remain completed
historical qualifications, not prerequisites for this revised scenario. Recheck
the current-install composition with the existing Chinese observations before
complete-case registration; their historical upgrade passes do not qualify the
changed sequence.
When 300j closes and the launcher resumes suspended task 300, re-read its current
brief and recipe. The saved consumer handoff's Chinese-upgrade wording predates
this scope change; carry the latest-install sequence in the new handoff while
preserving the prior launcher state and qualification evidence.

Task 300's composition preflight found an unqualified REQUEST04/LANG01 binding:
At preflight, `AccessibleUI.select_kiosk_account` compared English offered-choice
labels and selected-account descriptions, then called `kiosk_request_form` with
its English default. LANG01 kiosk form observations also bound Jordan. The active
300j implementation is extending these shared bindings; its registered selector
uses current-source inputs, but qualification is still pending. The previous
fixed-language slices cannot establish German/Hebrew selected-child restoration
or approver independence.
Task 300j is the unchecked prerequisite immediately before 300; qualify the fixed
Jordan/German and Riley/Hebrew station selection/re-entry slice through shared
operations before resuming the complete-case preflight. No product defect or
new live failure is established. Task 300 remains unchecked and unregistered;
panel refresh, inherited dialogs, RTL layout, countdown and translated approval
results still need their exact bindings checked after this slice. Preserve its
entire multilingual/RTL and uninterrupted Chinese lifecycle acceptance.

Task 300i is complete. The fixed Riley overlay LANG01 qualification passed on
Ubuntu 26.04 in `20261004T115946Z-5cd0363a`, replacing its expired earlier report.
Untouched English presentation, four native names, multilingual Save/Cancel,
independent text/checked-choice observations, request preservation, German
command-relaunch without startup setup and final unchanged public Parent policy
passed. The required shell-panel and kiosk-language regressions passed in
`20261004T114913Z-24503104` and `20261004T115236Z-05dd2d98`.
All three reports are retained; collection, worker shutdown, callback closure,
owned cleanup, baseline restoration, finalization and host/source preservation
passed. The shell-panel launcher and automatic preparation now use current-source
package inputs instead of the legacy v1.2 bundle; five host checks reproduced
that mismatch before repair, then all 277 selected unit/safety checks plus source
passed in `20261004T114809Z-1e837a49`. Earlier overlay host validation included
1,953 unit/safety checks and eight real GTK checks. No product/package code changed.
Task 300 remains unchecked and unregistered. Recheck selected-child restoration
and account isolation, panel refresh, inherited dialogs, RTL layout, countdown
and translated approval-result bindings before composing its complete
multilingual/RTL and continuous Chinese history. This slice supplies none of
those remaining results or complete-case acceptance.

Task 300h is complete. `check_e2e_kiosk_language` passed on the selected Ubuntu
26.04 VM in `20261004T103336Z-73d60bd2`: Jordan's untouched English chooser,
four native names, English/German/Simplified Chinese/Hebrew Save and independent
checked-choice/visible/accessibility text, Chinese Cancel preserving German,
normal re-entry with German retained, and unchanged request/policy projections.
The required fixed Chinese native-authentication regression passed all 14
assertions in `20261004T104017Z-b60581d0`. Both runs passed collection, worker
shutdown, callback closure, owned cleanup, baseline restoration, lease
finalization and host/source preservation. Host validation passed 2,417
unit/safety checks, source validation and four real GTK checks.
The first-presentation reader now reuses the kiosk identity guard within its
owned snapshot; the Parent-only child helper cannot accept kiosk IDs.
Task 300 remains unchecked and unregistered. Recheck overlay, selected-child
language restoration/isolation, panel, inherited dialogs, RTL layout and
countdown/result bindings before complete-case registration; preserve all
multilingual/RTL and continuous Chinese acceptance.

Task 300g is complete. `check_e2e_parent_language` passed on the selected Ubuntu
26.04 VM in `20261004T092815Z-1784595b`: untouched first-run English choice, four
native names, English/German/Simplified Chinese/Hebrew Save and independent
visible/accessibility text, Cancel preserving German, normal relaunch persistence,
and unchanged selected child, zero allowance and app-policy projection.
The required case 6 regression passed in `20261004T093246Z-b19110a7`. Both runs
completed collection, owned cleanup and baseline restoration; preservation passed.
The management reader now compares visible titles separately from accessible
names, fixing the test's incorrect capitalization equality. Host validation
passed 1851 unit/safety checks and source validation in `20261004T092702Z-38868f49`,
plus four real GTK management-reader checks in `20261004T092607Z-596c9c0b`.
The shared bounded stale-chooser reacquisition remains covered.

Task 300 remains unchecked and unregistered. Preserve its full multilingual/RTL
and continuous Chinese history. Recheck remaining overlay/kiosk, panel, inherited
dialog, RTL-layout and countdown bindings before complete-case registration;
the qualified Parent slice supplies none of those results or complete-case credit.
Reuse LANG01's `initial-language` launch result to observe the untouched chooser;
the ordinary `parent-window` checkpoint still performs automatic first-run Save.

Task 300f is complete. Chinese native authentication passed all 14 assertions on
the selected Ubuntu 26.04 VM in `20261004T073743Z-9a030ef1`, including two actual
native Chinese prompts, fresh agent/challenge identities, guarded real approvals,
persisted Chinese form and normal GDM returns. The required English approved-flow
regression passed in `20261004T075449Z-01e10e04` after repairing its wrong-entry
reader's missing bounded reacquisition on an incomplete accessibility query.
The repair passed 1,933 affected host checks in `20261004T075211Z-82086cc0`.
Both live runs passed collection, verified worker shutdown, callback closure,
owned cleanup, baseline restoration, finalization and host/source preservation.
See [the qualified Chinese binding](E2E-Building-Blocks.md#chinese-language-preparation-and-desktop-language-setup).
Task 300 retains its complete multilingual/RTL and uninterrupted Chinese
lifecycle case, with no complete-case credit from these prerequisite slices.
The Parent-language prerequisite was subsequently qualified by 300g. No product
behavior decision is pending.

Task 300e is complete. Its Chinese lifecycle qualification passed all 14
assertions on every enabled VM (Ubuntu 26.04) in `20261004T044302Z-572b0ee7`,
replacing the expired earlier report. The required kiosk-entry regression passed
in `20261004T043928Z-7e4cf5c1` after its launcher and qualifier were bound to
current-source package inputs instead of the fixed legacy v1.2 bundle.
The required package-upgrade regression passed in `20261004T024908Z-8d5137eb`;
its retained report is
`output/test-runs/host/exports/onpc-artifact-export-v2s6wi_5/report.md`.
All three runs passed collection, worker shutdown, callback closure, baseline
restoration, finalization and host/source preservation. The input-selection
repair passed 1,430 host checks in `20261004T043644Z-0fdeccf5`.
See [the qualified Chinese slice](E2E-Building-Blocks.md#chinese-language-preparation-and-desktop-language-setup).
Task 300's complete multilingual/Chinese scenario retains separate acceptance.
No adviser was consulted and no developer decision is currently required.

Task 300d qualified the genuine v1.2/current package upgrade on every enabled VM
(Ubuntu 26.04) in `20261004T002735Z-d4779228`; the required current-only customer
reboot regression passed in `20261004T003258Z-f006d805`. Authentic old-release
installation/activation, one real current-package upgrade, independent final
completion/reboot notice, unchanged boot after upgrade, refusal and preservation
passed. Both runs completed collection, worker shutdown, owned cleanup, baseline
restoration and finalization. See [the qualified binding](E2E-Building-Blocks.md#genuine-package-upgrade).
Task 300e qualified the Chinese no-reboot prompt and reboot/first-kiosk composition
in its historical upgrade sequence;
300f owns Chinese native authentication after fresh kiosk entry. Both are
completed prerequisites immediately before task 300, which retains its entire
multilingual/RTL and Chinese history without complete-case acceptance credit.

Task 300c qualified the genuine v1.2/current dual-package FIX04 binding on every
enabled VM (Ubuntu 26.04) in `20261003T234321Z-f5394d82`; the affected one-package
regression passed in `20261003T234636Z-cd0eba55`. Independent repeated readback,
entry/attempt/collision/replay refusals, preservation, collection and owned
cleanup passed. See the [qualified scope](E2E-Building-Blocks.md#verified-upgrade-asset-transfer).
This supplies historical upgrade inputs without installation or complete-case
credit; task 300 now uses the single current-package transfer and installation.
Task 300 remains unchecked: compose the qualified Chinese first-presentation,
reboot and native authentication operations in its single complete case.

Task 300a qualified the Chinese baseline language slice and read-only FIX06 on
every enabled VM (Ubuntu 26.04) in `20261003T210556Z-9dc87030`; the affected native
fixture regression passed in `20261003T210811Z-d41b9452`. Task 300 remains unchecked.
Task 300b qualified DESK13's Jordan → `zh_CN.UTF-8` system-account setting on
every enabled VM (Ubuntu 26.04) in `20261003T215747Z-6bd9c168`.
Greeter/account/locale refusal, independent Chinese FIX06 verification, one
setter submission, two independent readbacks and all account/locale/session
preservation checks passed. Ubuntu AccountsService confirmed its normalized
`zh_CN` value with explicit session renewal still required. Collection, worker
shutdown, owned cleanup, baseline restoration, finalization and host/source
preservation passed. Host safety/ownership checks passed in
`20261003T215408Z-2354ac86` (766 checks), with composition/source checks in
`20261003T215549Z-5f4be22b`. This supplies no renewed Chinese desktop,
product-language, native authentication or complete-scenario acceptance.
Chinese first-presentation/reboot composition and native authentication were
subsequently qualified by 300e and 300f; task 300 still owns its single complete case.

This pointer must name the first unchecked active queue row. After completion,
advance to the following unchecked row. An incomplete or blocked task keeps the
pointer; record its exact remaining work and return condition here and in its
row. Repair a stale pointer against table order, without scanning for other
eligible work.

## Current scope

Native double-click automation is [excluded by the UI mandate](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures).
Tasks 070, 070a and 071–076 were removed by the developer's scope decision;
E2E-014 cases 38–43 retain uncovered inventory/recipe obligations but have no
active or deferred task. Do not recreate those tasks or stop queue execution
for this known exclusion. This records no acceptance pass.

Apply the [UI/E2E allocation](UI-and-E2E-Coverage.md): full local GUI matrices
belong in UI tests, with representative installed checks and complete integration
assertions in E2E. Pending UI obligations stay in the existing capability tasks.
The allocation review does not advance the pointer or replace live acceptance.

Current scenario status and counts come from `tests/e2e/scenarios.json`; block
status comes from the catalogue. The initial provider migration gate is closed.
On 2026-09-23 the developer confirmed separately validating the seven then-ready
cases—1, 3, 4, 5, 6, 151 and 193—and explicitly directed that they need not be
rerun. This confirmation supplies the shared regression gate's acceptance;
no runner artifact was supplied for that complete set.

That historical set is not the current runnable inventory. Delivered scopes and
their evidence stay in the queue/catalogue; future shared changes follow the
[live regression policy](E2E-Execution-Contracts.md#live-verification-contract).

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
   implement leaves before composites and complete composition preflight before
   the first live attempt.
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
Host checks cannot complete queued live work. Historical task 192 is the sole
host-only queue exception. Documentation reconciliation follows the
[separate working route](README.md#working-route) and closes no queue row.

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
