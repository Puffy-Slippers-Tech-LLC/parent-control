# E2E execution plan

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md

Read this master, then the **Next task** brief. The
[documentation map](README.md) defines ownership and status terms. The full
scheduling table is separate so ordinary implementation sessions do not load
hundreds of unrelated tasks. This master owns selection, execution and
completion; the [queue](E2E-Task-Queue.md) is its canonical checklist. It contains
one fixed sequence, including external-provider qualification and retained
regressions. Start only here; individual briefs provide the selected task's
instructions and never select a different task.

## Next task

Next task: **003ab — [Qualify product-free GDM navigation](E2E-Tasks/003ab-product-free-gdm.md)**.

Task 001r's product-free attempt found that the installed GDM adapter requires
the product's station account, which is absent on the declared baseline.
Task 003ab is the explicit missing prerequisite immediately before 001r;
qualify the product-free Parent list/prompt/return binding without weakening
installed station checks. Task 001r retains its implementation and host checks
but remains unchecked until the complete case, collection and cleanup pass.
The existing [failed attempt](Evidence/test-all-runs/20260922T153110Z-ef1d0c40/report.md)
preserves the account-cardinality refusal and passing owned cleanup.

This pointer must name the first unchecked active queue row. After completion,
advance to the following unchecked row. An incomplete or blocked task keeps the
pointer; record its exact remaining work and return condition here and in its
row. Repair a stale pointer against table order, without scanning for other
eligible work.

## Current scope

Current scenario status and counts come from `tests/e2e/scenarios.json`; block
status comes from the catalogue. Preserve implementations and regressions for
ready cases 1, 3, 4, 5, 6, 151 and 193. A checked queue task records its
delivered scope; it does not override a later `pending` block or scenario status.

Retired E2E IDs 140–150 remain separate system-test obligations and cannot be
selected as UI cases. Deferred mute task 154 is outside current-release
completion and blocks no active task. Consumerless SEC01/GDM10 extractions retain
their recorded scope. A customer pass cannot replace displaced engineering
obligations under their maintained owners.

### Planned Lunar Client regression

[E2E-052, case 253](E2E-Scenario-Recipes.md#e2e-052) adds the real
AppImageLauncher login-autostart route. E2E-019's native launches,
E2E-022's reboot persistence and E2E-041/case 189's version patterns do not
establish this coverage. Keep their existing scope and IDs unchanged.

This is metadata/planning only: case 253 remains `pending`, with no executable
binding. Tasks **295, 296c, 296d, 296, 296e, 296a, 296f, 296b and 297** separately
cover restored-fixture validation, Lunar launch/Quit, tray controls, command
denial, Minecraft entry/exit, local play, allowed and denied continuous login
observations, and the complete scenario. Manual installation/configuration of Lunar,
AppImageLauncher and Minecraft on the guarded VM is an allowed future
prerequisite, not permission for installation on this development host or an
in-journey setup fallback. The [fixture contract](E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
requires reproducibility after the ordinary runner restore; an ad-hoc working
VM or a disabled autostart cannot qualify the negative case.

The case must distinguish a still-active **time-only** grant from explicit
soft-app approval, preserve the active-grant session contract, and observe both
the tray/autostart result and a real same-route launch denial. Its included-app
control must actually reach usable Minecraft. Do not replace these results with
process/rule probes or treat unavailable assets/provider observations as a pass.
This addition does not change the current **Next task** or claim VM acceptance.

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
   Implement leaves before composites, including within a small task. Bind
   entry, finite inputs, expected public results, precision and deadlines first.
   Apply the [UI automation mandate](../../AGENTS.md#ui-automation-mandate) and
   [functional validation](E2E-Building-Blocks.md#functional-validation) to every
   required surface, including setup, login and retained paths. Fix missing owned
   IDs first; qualify external-provider adapters where usable IDs are unavailable.
5. Finish live verification, cleanup and close-out. Report the task ID, result
   and next task. The next identical prompt repeats this workflow.

**Execution order:** follow the queue from top to bottom, one unchecked active
row at a time. There is no alternate provider queue, runtime eligibility search
or automatic jump around a blocker. IDs and filenames are stable labels, not
sort keys. A scenario never depends on another scenario's execution.

The customer-first selection principle is applied when maintaining this fixed
order: prerequisites precede consumers, and every newly enabled complete scenario
is placed immediately after its last capability, in numeric case order, before
the next capability. Retained regression rows follow the same rule.
Ordinary customer work precedes the retained system obligations. Capabilities
requiring external authorization/assets or an unproven public trigger, with
their consumers, form the final part of the same queue; calendar windows are
last. This placement is fixed during planning, never selected at runtime.

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

The normal working set is **this master + one task brief + relevant contract
rows, recipe clauses and source callables**. Do not read sibling/predecessor
briefs, the entire queue, the full block catalogue, every recipe or all inventory
entries. Do not recursively dump `E2E-Tasks/`. Prior task history is unnecessary.

Use quoted `rg -n` lookups and bounded `sed -n` or `tools/read-only slice`
reads. For example, these retrieve one scheduling row and one block slice:

```sh
rg -n '^\| \[.\] \| 192 \|' 'docs/TestAutomation/E2E-Task-Queue.md'
rg -n '^\| (FILE01|FILE02|FILE06) \|' 'docs/TestAutomation/E2E-Building-Blocks.md'
```

For the selected task, load:

- The delivered and prerequisite block rows, then only their relevant source
  callables and direct callees. Follow new references when the implementation
  actually crosses that boundary; do not recursively expand the whole catalogue.
- The named recipe family, **only its selected variant branches**, applicable
  finite-data rows, and the common entry/time rules it uses. Recipe links
  identify sections to read, not permission to load the whole recipe book.
- Only the selected inventory variants and their family declaration. Use a
  narrow JSON projection for IDs/counts rather than dumping all variants.
- Affected implementation and safety tests. Broaden reads when a concrete
  missing contract, failure or shared change requires them.

At close-out, read the following unchecked queue row and its prerequisites, then
advance the pointer to that row. Inspect dependants of a changed capability only
when repairing dependencies or splitting work. An ordinary implementation session
does not recompute task order or load unrelated briefs. A reconciliation of the
plan may inspect the full scheduling metadata to validate the fixed order.

## Task size and order

Aim for **one session of 15–30 minutes per ordinary task**, including scoped
reading, implementation, targeted checks, required live qualification, cleanup
and document close-out. A useful 30-minute budget is 3 minutes for context,
10 for implementation, 12 for validation and 5 for cleanup/close-out. These are
planning estimates, not measured runtimes or stop timers; continue authorized
work to a clean boundary when necessary.

Each ordinary capability adds one operation, provider surface, route or result
branch. Split independent work whose upper estimate exceeds 30 minutes **before
implementation**, giving every new row explicit prerequisites, a bounded live
qualification and its own brief. Extract usable operations before composing
them. Do not create host-only preparation rows, partial scenario registrations,
or a separate implementation/verification queue to make the estimate fit.

A split keeps the original ID for the remaining operation/composition. Its brief's
**Session boundary** names that new work; its delivered scope is cumulative with
the extracted prerequisites. Reuse their maintained callables and valid scoped
evidence, never predecessor briefs or saved VM state. The original acceptance
results remain required, including fresh qualification of every new composition
and reruns of affected branches. Completed rows retain their original scope and
estimates.

Routine estimates assume prerequisite capabilities, installed test tools and
declared assets are available. They include ordinary attempt preparation;
unresolved authorization, asset preparation and calendar eligibility remain
explicit gates. Recheck the estimate when those facts or the implementation
change. Do not silently relabel a larger task as 30 minutes or drop validation.

**Session exceptions** are marked in the queue's Minutes column and explained in
the corresponding brief. Complete finite E2E cases, uninterrupted customer
histories, real retry/calendar waits, package lifecycle qualification, system
fault/recovery cycles and mandatory shared-infrastructure regressions can exceed
30 minutes. Preserve their full recipes and run bounds in one task; extract
reusable capabilities first, then schedule the remaining indivisible acceptance
honestly. A long run does not authorize a split across restored attempts, an
early pass or a shortened wait. If interrupted, keep the same task current with
its remaining work and valid existing artifact pointer.

Every dependency must precede its consumer, including public setup, exits and
observations needed for qualification. Separate asset transfer/installation from
launching when they are substantial work; FIX04 transfers assets, never installs
them. Qualify a requested surface/route before composing it. Keep unrelated
feature branches out of the task.

Bind a scenario's finite values and registered selectors to already-qualified
APIs within that scenario task. If it needs a new operation, surface or result
branch, add the missing capability slice before the consumer instead of silently
expanding the task or accepting a generic block ID as qualification.

After each capability, place **all newly enabled scenarios before the next
capability**, in numeric case order. Each scenario row remains a separate
next-task selection. For example, native fixture/catalogue work releases case
184 before app-launch work; overlay FLOW20 releases its delayed-approval cases
before the separate kiosk FLOW20 slice and cases.

One scenario task owns one numeric case and its complete fixed recipe. The
recipe may contain finite value checks or a continuous repeated customer history;
these are assertions inside that case, never task-selection loops. A capability
task uses its named fixed qualification and does not absorb the later scenario
task. Previously delivered scopes remain recorded when a task is split.

Authorization, real calendar windows and unsupported public routes cannot be
removed by editing the schedule. They are acceptance prerequisites with one
documented return condition, not alternate branches. Prepare the selected task's
concrete inputs, then report the exact missing prerequisite and keep that task
current. This plan guarantees deterministic selection; it does not claim that
external prerequisites are already available.

## External-provider work within the sequence

Provider adapters are capability work for named consumers. Their scope and
current qualification stay in the
[provider catalogue](E2E-Building-Blocks.md#external-provider-qualification);
their next action is always a row in this queue. Repository-owned UI and fixtures
retain mandatory public automation IDs.

External IDs are optional. Spend at most ten minutes per provider surface once
on an available tree and useful official source, then use the approved scoped
accessibility/keyboard adapter. Reuse recorded findings. Geometry or images need
the explicit exception's documented reason and separate route qualification.
Never invent IDs from labels, restore retired generic selectors, or make an
upstream patch, provider rebuild or exhaustive ID search a prerequisite.

Use the existing `AccessibleUI`, `UiObservations`, worker and guarded attempt
envelope. Tests must reject wrong owner/session/surface, ambiguity, stale
handles, disabled/hidden input, lost focus, incomplete observations and uncertain
input. Qualify real input and independent public results, independent valid entry,
wrong-entry refusal and owned cleanup on the pinned VM. Reacquire after input
and transitions; incomplete trees never prove absence. Secret routes require two
fresh same-challenge recipient proofs, an empty masked focused field, sealed
capture and single-use delivery without replay. Unknown prompts refuse.

Record the actually qualified package versions, provider locale and keyboard
layout in existing sanitized evidence and the catalogue. Observer locale is
not provider locale. Scope support to that tuple; do not build an unsolicited
version/translation matrix. Native/portal choosers and MATE/Shell authentication
are separate bindings and keep separate live results.

Task briefs select fixed qualification routes in the maintained envelope.
Planned selectors must be implemented, registered and cleanup-tested before
use. Preparation and every live operation use the shared watchvm lease,
intention, display and guarded command transport. No additional runner, viewer,
generic selector language or VM controller is part of this plan.

## Live verification contract

Task **192** is the sole host-only exception. All capability/scenario work,
including provider adapters, needs its stated acceptance on the guarded live VM;
engineering tasks need their actual system fault/recovery qualification.
Former separate host/VM adapter rows are combined into a bounded live slice or
split into smaller independently qualified operations. Host checks alone cannot
complete any new capability.

Follow [functional validation](E2E-Building-Blocks.md#functional-validation).
Apply [environment preparation and customer interaction](E2E-Building-Blocks.md#environment-preparation-and-customer-interaction)
to every step: use the most reliable and efficient supported invocation for
supporting tools and session preparation; use real graphical customer actions
and public observations for product features and transitions under test.
Use public accessibility, normal customer input and independent observations
of required results. Backend product probes, synthetic grants, clock changes,
internal faults and cosmetic/screenshot comparisons cannot pass customer cases.
Reuse the existing [consumer path](E2E-Building-Blocks.md#add-a-consumer):
`InstalledJourney/JourneyPlan`, `UiObservations`, `AccessibleUI` and the shared
worker/dispatch. Locate only the relevant callables through the catalogue.
Publish nonsecret operation/progress labels and open `tools/watchvm` as the
desktop user for VM work.

Each attempt starts with fresh declared state and its own session/window ledger.
For post-installation work, run `./tools/prepare-appsnapshot --overwrite false`
under the [setup contract](E2E-Building-Blocks.md#parent-login-and-time-scenarios).
Use `--overwrite true` when application code changed; documentation-only and
test-only changes continue to use `false`.
Wait for completion without monitoring or reporting incremental output; proceed
only on success. The normal dispatcher owns preparation/restoration. Package
lifecycle cases use their declared product-free start and real customer install.
Never use manual snapshots, resets or prior task state as a journey step.

Run affected cleanup/ownership safety regressions in isolation before host
integration. Use `tools/run-unit-tests` and relevant
`tools/run-ui-tests --timeout <duration>` selections. Changes to shared GDM,
secret handling, routing, recorder phases/reconciliation or cleanup also require
live regressions **1, 3, 4, 5, 151**. Otherwise run the new consumer and directly
affected ready cases. Terminal changes also retain cases **6 and 193**.

The initial provider migration has explicit regression rows **001r, 003r, 004r,
005r, 002r, 235r and 151r** in this same sequence. Earlier capability rows can
close only their stated live slice; overall shared migration close-out remains
pending until those complete cases pass. Preserve valid unchanged results, and
rerun any earlier case affected by a later change before migration close-out.
This staged migration gate does not exempt subsequent shared changes from the
normal regression requirement or add scenario-to-scenario dependencies.

Staged artifacts, evidence and VM ownership must remain valid. Checkout edits
during a run follow the [documentation map's contract](README.md); they do not
by themselves invalidate the attempt or its completed safety prerequisites.

For a **capability**, pass every stated outcome, independent valid entry and
wrong-entry refusal through the brief's fixed slice qualification in the
existing guarded envelope. Complete scenarios stay in their separate rows. Planned
`check_e2e_...` names must be implemented before invocation. New entries are
argument-free `tests/integration/check_[a-z][a-z0-9_]*.py` files with applicable
cleanup tests, selected by `tools/run-tests integration <name>`. Reuse shared
helpers and verified assets (`tools/run-tests artifacts build` when needed);
no new generic dispatcher or partial registered scenario. Record a passing slice
as qualified for its exact scope. Other bindings can keep the catalogue row
pending; a later complete scenario is not a prerequisite of its own building block.

For a **scenario**, register the complete recipe in the established
inventory/worker path, preserving every finite branch and terminal result.
Run each exact `tools/run-tests e2e --id '<case>'` separately. Registration is
not acceptance. Require public results, reconciliation, collection and cleanup.
Refresh coverage after **each** successful case, including retained regressions,
before advancing the task pointer.

For a **system obligation**, use the brief's maintained owner and listed
`tools/run-tests system` selectors on the guarded VM. Require the exact fault,
observed failure, recovery, isolation and cleanup. A mapping, placeholder
selector or host-only check cannot complete it.

The selected brief owns its applicability/authorization gate. Resolve it through
supported public routes; unavailable routes remain pending. Never edit/deploy
the portal or change expected behavior to manufacture a pass.

## Completion and document cleanup

After the guard is released and cleanup succeeds:

1. After **every completed E2E scenario**, run
   `tools/generate_test_coverage.sh`. This approved executable runs the requested
   [tools/generate_test_coverage.py](../../tools/generate_test_coverage.py) and
   regenerates [Test-Coverage.md](../Test-Coverage.md). Generation must succeed
   even without declaration changes; it proves no live result. Repeat after
   later inventory/collection changes.
2. Update only relevant rows in [E2E-Building-Blocks.md](E2E-Building-Blocks.md):
   actual callable, qualified scope/selector and remaining scope. Update the
   selected family's recipe in
   [E2E-Scenario-Recipes.md](E2E-Scenario-Recipes.md) only if its composition or
   implementation context changed. Keep runtime status/bindings in the inventory
   and totals in generated coverage. A block slice alone does not complete a scenario.
3. Check the completed task `[x]` in its canonical [queue](E2E-Task-Queue.md)
   row only after all acceptance and close-out
   pass. Keep ID, delivered scope and prerequisites; remove resolved blockers.
   Close only the selected row. A capability slice supplies no complete-scenario
   acceptance credit.
4. Replace **Next task** with the following unchecked active queue row. Delete the
   completed brief once enduring context is in maintained source/contracts;
   replace its queue link with plain text. No later brief may require it.
   Preserve normal runner artifacts; create no archive, evidence document or
   accumulated history. If interrupted, keep only current remaining work,
   blocker and useful existing artifact pointer in the still-needed brief.
5. Validate changed Markdown with `tools/read-only links '<file.md>' ...`.
   Recheck changed dependency rows and newly enabled scenarios. After a queue
   split/reorder, also verify unique IDs, one brief for each unfinished row,
   matching brief/queue prerequisites, dependency order, immediate scenario
   placement, the first-unchecked pointer, ordinary estimates of at most 30
   minutes or an explained session exception, and unchanged case assignment.
   Preserve every declared inventory case exactly once as implementation scope;
   retained regression rows separately revisit the seven existing bindings.
   Splitting former paired rows changes task granularity, never case IDs, finite
   matrices or assertions. Lunar case 253 remains pending. Retain system
   obligations formerly numbered 140–150 outside the UI inventory and preserve
   all seven retained ready case implementations and bindings. Their shared
   provider routes still require qualification under the current mandate.

Run the maintained host consistency check after a queue repair:

```sh
tools/run-tests unit 'tests/unit/test_e2e_plan.py' 'tests/unit/test_e2e_inventory.py' 'tests/unit/test_coverage_generation.py'
```

It checks the pointer, task/brief dependencies, one case per scenario task,
case assignment, session sizing/exception metadata and capability-before-consumer
order. It does not qualify UI
adapters or establish a live pass.

If only coverage/status close-out remains, finish it without
rerunning an unchanged valid attempt solely for documentation.

Current-release completion requires every active row checked or explicitly
excluded by an authorized scope decision, all active gates resolved, and each
obligation passed in its proper suite. Deferred work is never counted as a pass.

## Ordered task queue

The [ordered checklist](E2E-Task-Queue.md#ordered-task-queue) contains every task's
ID, prerequisites, scope, estimate and brief link. It is scheduling metadata,
not required background reading for the current task. Check and maintain its
rows as part of this master plan; use scoped reads as described above.
