# E2E execution plan

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md

Read this master, then the **Next task** brief. The
[documentation map](README.md) defines ownership and status terms. The full
scheduling table is separate so ordinary implementation sessions do not load
hundreds of unrelated tasks. This master owns selection, execution and
completion; the [queue](E2E-Task-Queue.md) is its canonical checklist.

## Next task

Next task: **011 — [Enter and read the request station](E2E-Tasks/011-kiosk-entry.md)**.
It needs GDM route qualification under the external-provider exception, then installed
station exposure of the repository-owned request-form IDs; its brief records
both return conditions. Host adapter/UI results qualify neither gate.

Maintain this single pointer after completion, a split or a newly identified
blocker. Verify its queue row and named prerequisites before starting; a stale
pointer never overrides the queue. Keep only current continuation information.

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

## Execute one task

1. Follow repository AGENTS.md, start at [System-Design.md](../System-Design.md),
   apply [Approval-Tools.md](../Approval-Tools.md), and inspect working-tree status.
   Preserve unrelated edits and reuse existing session authorization.
2. Verify the Next task's unchecked queue row, required completed capabilities
   and task-local gate. Read only those rows. If the pointer is stale or blocked,
   apply the selection rule below; do not open every brief to find work.
3. Read the selected brief and its scoped references as described below.
   Required IDs identify implemented capabilities, not predecessor documents
   or saved VM state. Verify the exact surface, route and branch in maintained
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

**Selection rule:** choose the lowest case-number eligible scenario first.
Otherwise choose the first eligible capability/metadata row in queue order;
choose a system row when no independent customer work is eligible. IDs and
filenames are stable labels, not sort keys. A scenario never depends on another
scenario's execution.

If blocked, retain the row's delivered scope and append only
`Blocker: …; resume when: …`. Leave it unchecked and skip its dependants.
Review an untested gate once, complete authorized preparation and continue
independent work. Revisit a known blocker only when its condition changes.
If nothing is eligible, report the remaining conditions without claiming
completion. Missing sending authorization blocks Send, not preparation of
concrete reviewable inputs. Product-behavior mismatches follow the
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

At close-out, inspect queue rows that require the completed ID and verify their
other prerequisites by ID. If none becomes eligible, scan scheduling metadata
in bounded portions using the selection rule. Open a candidate's brief only
when checking its gate or selecting it. This selection work does not require
loading the contents of unrelated tasks. Update the pointer before ending.

## Task size and order

Plan focused implementation plus targeted validation for **15–60 minutes**.
These are estimates, never stop timers. Continue authorized work when necessary.
Split independent work likely to require about two hours before starting; each
new slice needs its own prerequisites and live acceptance. Keep continuous
customer journeys intact, including their declared run bounds.

Every dependency must precede its consumer, including public setup, exits and
observations needed for qualification. Separate asset transfer/installation from
launching when they are substantial work; FIX04 transfers assets, never installs
them. Qualify a requested surface/route before composing it. Keep unrelated
feature branches out of the task.

Bind a scenario's finite values and registered selectors to already-qualified
APIs within that scenario task. If it needs a new operation, surface or result
branch, add the missing capability slice before the consumer instead of silently
expanding the task or accepting a generic block ID as qualification.

After each capability, place **all newly eligible scenarios before the next
capability**, in numeric case order. Each scenario row remains a separate
next-task selection. For example, native fixture/catalogue work releases case
184 before app-launch work; overlay FLOW20 releases its delayed-approval cases
before the separate kiosk FLOW20 slice and cases.

## Live verification contract

Task **192** is the sole host-only exception. All capability/scenario work needs
its stated acceptance on the guarded live VM; engineering tasks need their
actual system fault/recovery qualification.

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
Publish nonsecret operation/progress labels and open `tools/watch-e2e` as the
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
affected ready cases. Finish edits/builds first; keep source and documents
unchanged through live collection and cleanup.

For a **capability**, pass every stated outcome, independent valid entry and
wrong-entry refusal. Prefer its complete runnable consumer; otherwise use the
brief's fixed slice qualification in the existing guarded envelope. Planned
`check_e2e_...` names must be implemented before invocation. New entries are
argument-free `tests/integration/check_[a-z][a-z0-9_]*.py` files with applicable
cleanup tests, selected by `tools/run-tests integration <name>`. Reuse shared
helpers and verified assets (`tools/run-tests artifacts build` when needed);
no new generic dispatcher or partial registered scenario. A slice can complete
while its catalogue row remains pending until the first complete consumer passes.

For a **scenario**, register the complete recipe in the established
inventory/worker path, preserving every finite branch and terminal result.
Run each exact `tools/run-tests e2e --id '<case>'` separately. Registration is
not acceptance. Require public results, reconciliation, collection and cleanup.
Refresh coverage after **each** successful case before the next, including pairs,
regressions and full scenarios completed during capability qualification.

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
   If a complete scenario passed during a capability task, close its row only
   after its exact selector, full recipe, cleanup and coverage refresh.
4. Replace **Next task** with the next eligible unchecked task. Delete the
   completed brief once enduring context is in maintained source/contracts;
   replace its queue link with plain text. No later brief may require it.
   Preserve normal runner artifacts; create no archive, evidence document or
   accumulated history. If interrupted, keep only current remaining work,
   blocker and useful existing artifact pointer in the still-needed brief.
5. Validate changed Markdown with `tools/read-only links '<file.md>' ...`.
   Recheck changed dependency rows and newly eligible scenarios. After a queue
   split/reorder, also verify unique IDs, matching brief/queue prerequisites,
   dependency order, immediate scenario placement and unchanged case assignment.
   The frozen 236 customer cases must each occur exactly once; retain system
   obligations formerly numbered 140–150 outside the UI inventory and preserve
   all seven retained ready case implementations and bindings. Their shared
   provider routes still require qualification under the current mandate.

For a paired task, update each completed case immediately; keep the task unchecked
until both pass. Resume only remaining work unless later changes invalidate the
earlier result. If only coverage/status close-out remains, finish it without
rerunning an unchanged valid attempt solely for documentation.

Current-release completion requires every active row checked or explicitly
excluded by an authorized scope decision, all active gates resolved, and each
obligation passed in its proper suite. Deferred work is never counted as a pass.

## Ordered task queue

The [ordered checklist](E2E-Task-Queue.md#ordered-task-queue) contains every task's
ID, prerequisites, scope, estimate and brief link. It is scheduling metadata,
not required background reading for the current task. Check and maintain its
rows as part of this master plan; use scoped reads as described above.
