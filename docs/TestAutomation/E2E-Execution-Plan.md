# E2E execution plan

Use this prompt for each session:

> Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md

This is the execution queue for [E2E-Building-Blocks.md](E2E-Building-Blocks.md).
The catalogue owns block contracts; [scenarios.json](../../tests/e2e/scenarios.json)
owns variant identities. This plan owns session selection and completion.
An individual task needs this master, its linked current contracts and maintained
source interfaces. It never needs a completed task's document or VM state.

## Starting scope

At plan creation, the catalogue has **153 blocks: 60 ready, 93 pending**.
The queue covers **91 active pending blocks**, plus consumer-specific extensions
of ready interfaces. SEC01 and GDM10 remain deferred legacy extraction with no
named customer consumer; preserve their existing implementation/qualification.
Do not build unused legacy infrastructure merely to turn those two rows green.

The inventory has **33 families / 157 persistent variant IDs**:
five ready variants (**1, 3, 4, 5, 151**), **141 pending customer variants**
(including conditional retry case 157), and **11 internal-fault obligations**
(140–150). Case 1 is harness qualification; four ready cases are customer journeys.
All 157 IDs are accounted for; these baseline statuses are not fresh test results.

There are **200 tasks: 82 block/capability tasks, 107 customer scenario tasks and
11 separate system-qualification tasks**. All start unchecked. No implementation
or live acceptance is claimed by writing this plan.

Task IDs are stable identifiers, not sort keys: read the table from top to
bottom, including inserted suffix IDs. A completed capability supplies reusable
source, never a dependency on another task's document or retained VM state.

Small related variants share a task only where they use the same implementation
and fit one normal validation cycle. Long expiry, lifecycle and complex request
variants remain individual tasks. Estimates are normally 20–60 minutes for
related implementation and a normal verification cycle on a prepared environment. New independent routes and branches
get separate tasks when one can unblock a scenario on its own. Cold builds,
diagnosis or slow VM work can take longer; never terminate a running session
merely because its estimate expired. Required shared-helper regressions and
case 139's continuous package lifecycle can exceed the estimate; keep their
acceptance intact. Do not use a short estimate to omit required verification.

## Execute one task

1. Read repository AGENTS.md, [System-Design.md](../System-Design.md),
   [Approval-Tools.md](../Approval-Tools.md) and this master.
   Inspect the working tree and relevant current implementation. Preserve
   unrelated edits. Read only the catalogue rows, scenario recipe and design
   modules needed for that task.
2. Identify unchecked rows whose prerequisite capabilities are complete and whose
   explicit gates are available. If any customer scenario is eligible, choose
   the lowest numeric case ID among them; otherwise choose the first eligible
   capability row in table order, then a system row when no customer work is
   eligible. Open only that task file. Check prerequisites by their implemented,
   live-qualified scope in maintained source and the catalogue, not a previous
   task document or VM attempt. A completed block task can satisfy a dependency
   while its catalogue row is still pending the first full scenario. Reconsider
   a recorded blocker only when its return condition changes. Missing authorization
   blocks the dependent action, not preparation of its concrete reviewable inputs.
   A gated capability with no recorded review/blocker may be selected once for
   that authorized preparation. Record any remaining gate and return condition;
   subsequent prompts skip it until that condition changes.
3. If a prerequisite is unavailable, keep the row unchecked and put a concise
   current blocker and return condition beside it. Skip its dependent rows and
   continue with the next independent eligible task under step 2. A product failure
   during acceptance follows the [failure contract](../../tests/README.md#handling-test-failures):
   retain the runner failure, report expected versus actual, and obtain any
   missing behavior decision before accepting a change or altering expectations.
   Mechanical test fixes may proceed while preserving the intended check. When
   no eligible work remains, report the exact blockers; do not declare the plan complete.
4. Implement this one coherent task, including necessary fixes and its live
   acceptance. Use explicit fixture identities, surfaces, parameters, expected
   results and deadlines. Implement children before composites, including within
   a task's listed sequence. Partial interface extensions are limited to their
   named route/surface; other bindings stay pending.
5. Run the verification contract below. Keep source and documents unchanged
   during guarded attempts through collection and cleanup. Finish functional
   edits before building/qualifying final inputs.
   Keep VM work observable through the [viewer and shared command/progress
   interfaces](E2E-Building-Blocks.md#add-a-consumer), including installed tests,
   SSH setup, customer actions and cleanup. `tools/watch-e2e` may remain open
   across tasks; its command pane also works when no graphical frame is available.
6. Perform the close-out below after cleanup has released the attempt. Report
   the completed task, validation result and next eligible row. The next simple
   prompt repeats this process.

If inspection reveals a task would reasonably need more than an hour of distinct
implementation work, split it **before** that work into independently useful,
closely related tasks with explicit capabilities and live acceptance. Update
this queue and its links without dropping requirements. Keep stable existing IDs;
use a suffix for inserted tasks if needed. A continuous scenario is never split
into resumable VM attempts. This sizing rule is planning, not a session timeout.

## Order and dependency rules

Every prerequisite in the table precedes its consumer, including the capabilities
needed to set up and observe that task's own live qualification. Dependencies
are transitive: an earlier unchecked row unrelated to the selected task does not
block it. A grouped task implements its leaves before its composites.

When splitting or changing scope, move the affected work into its own linked
task and update both its prerequisites and every consumer's prerequisites.
Reorder the table, then check that no dependency points forward, no variant is
lost or duplicated, and no eligible scenario waits behind another capability.
Keep implementation, qualification and close-out within each task's stated scope.
Audit entry and observation dependencies too: a disabled allowance editor needs
UI17 plus saved/enabled observations before it can qualify PARENT06. An allowed/
blocked-app assertion needs public policy setup and qualified denial observations,
not just a usable-app launcher. A shared block ID alone is insufficient; check
the required surface, route and branch. Do not make a scenario wait for unused
branches of the same block: give independently useful bindings separate tasks.

After each capability completes, implement **all newly eligible scenario tasks
before another block task**, using numeric case order among those eligible.
The table already follows this rule; reapply it after scope changes or a blocker
clears. Do not wait for an entire block family or future route to become ready.

For example, terminal blocks are followed immediately by case 6 and installation
capabilities by case 2. Parent save and kiosk account selection unlock case 57,
then empty-account profiles unlock 54–55, before duration editing or authentication.
Kiosk exits and prepared duration choices then unlock 47–48. Desktop countdown
readback unlocks kiosk-approved case 49 before lock/retained-unlock qualification.
Native activity capture and overlay exits unlock 44–45 before retained-user app
visits. Cases 7–12 wait for both boundary validation and app-policy/denial support.

Feedback collection tracing, app-exit reset, file-manager launch, desktop launch
and fullscreen request entry each have their own consumer. Fullscreen expiry
does not wait for its request-panel route; package removal/reinstall does not
wait for product-update support. A later case can precede a lower-numbered,
still-blocked case.

Dependencies deliberately track **scope**: the first FLOW04 task supports kiosk,
and overlay support follows its panel/form binding; APP01 first supports native
grid/command, with file/Snap/Flatpak routes added separately; FLOW13 profiles and
LIFE05 activation routes qualify incrementally. Never use a branch before its
named capability row completes. Existing ready scopes remain usable throughout.

No task asks for the deferred policy-acknowledgement design or a replacement
runner. Internal-fault cases are system work and do not interrupt the ready
customer queue. They remain executable independent work when customer gates
are blocked.

## Live verification contract

Customer acceptance operates the installed app through public accessibility and
normal UI actions. Follow [functional validation](E2E-Building-Blocks.md#functional-validation):
assert usable results, not pixels, geometry, colors or screenshot similarity.
Fresh fixture children start with limits off. A kiosk choice/approval task must
first enable its declared target through Parent with UI17/PARENT08, then use
DESK03 to reach GDM; REQUEST01/FLOW04 never change policy implicitly. Empty or
disabled-child cases keep their explicitly unavailable state.
Do not replace steps with product methods, private saved data, process probes,
synthetic grants or internal faults. Account/asset preparation and harness
ownership/secret/cleanup checks retain their existing exceptions.

Use [InstalledSetup](../../tests/e2e/installed_setup.py),
[InstalledJourney](../../tests/e2e/installed_journey.py),
[UiObservations](../../tests/e2e/ui_observations.py),
[AccessibleUI](../../tests/e2e/accessible_ui.py), the shared
[worker rendezvous](../../tests/integration/graphical_smoke/lib/onpc_journey.pm)
and registered [worker dispatch](../../tests/integration/graphical_smoke/tests/smoke.pm).
Add infrastructure only for the named consumer. Each callback has its own fresh
attempt and current-surface/session ledger; no test inherits another's state.
Ordinary feature attempts use InstalledSetup; cases 2 and 139 use the explicitly
qualified product-free start, with verified assets staged but installation left
to customer steps.

Before host-integrated execution, pass affected cleanup/ownership safety
regressions in isolation through the approved launchers. Use `tools/run-unit-tests`
for meaningful worker/controller checks; use `tools/run-ui-tests --timeout <duration>`
for relevant real-adapter qualification. These support live acceptance and never
replace it. The existing dispatcher enforces its mandatory safety gate.

For a **block task**, prefer an already-runnable full consumer exercising its
new scope. Otherwise use the planned fixed `check_e2e_...` qualification named in
the task. These names are future entries, not existing passing commands:

- Reuse/extend one fixed qualification for that consumer in the existing guarded
  envelope, following [check_graphical_smoke.py](../../tests/integration/check_graphical_smoke.py).
  An additional entry is an argument-free `tests/integration/check_[a-z][a-z0-9_]*.py`
  with applicable cleanup tests, run by `tools/run-tests integration <name>`.
- Reuse existing verified asset building/staging and InstalledSetup. The fixed
  entry must bind current verified inputs; do not rely on an arbitrary stale
  `/tmp` directory. Use `tools/run-tests artifacts build` when fresh artifacts
  are needed. Do not invent a parallel staging/VM system or generic selectors.
- Prepare visible entry states through already-qualified public operations.
  Qualify only the implemented slice, including independent entry and wrong-entry
  refusal. A qualification can pass that slice while the complete scenario and
  catalogue row remain pending. Never register a partial customer callback as
  coverage. Reuse the same qualification as its consumer grows; avoid redundant
  permanent infrastructure after the full consumer covers it.

For a **scenario task**, reconcile its current inventory declaration before
registration using [inventory reconciliation](E2E-Building-Blocks.md#inventory-reconciliation).
Preserve numeric IDs, all variant values and each displaced engineering
assertion's owner. Do not fabricate backend evidence or silently narrow siblings.
Register the complete callable, then run the task's exact
`tools/run-tests e2e --id '...'` selection. This public route builds missing
verified artifacts automatically; `--artifacts '<verified-directory>'` can reuse
matching inputs. A pending selector refuses rather than proving coverage.
Every selected variant must complete its full recipe and terminal outcomes.
For a task with multiple variants, invoke their listed selectors separately and
refresh coverage after each successful journey and cleanup before starting the
next. Do not edit or regenerate documents while any guarded run is active.
If inventory reconciliation exposes missing engineering implementation, add a
bounded system task with its exact retained obligation and owner; do not expand
this customer task into unrelated fault infrastructure or count a mapping as a pass.

Keep all five established variants runnable. Changes to shared GDM, secret input,
routing, phase/reconciliation or cleanup require affected safety checks and live
regressions **1, 3, 4, 5, 151**; other changes run the exact new consumer and directly
affected ready cases. Preserve completed unit/component/system tests. Do not
rerun the whole future matrix for a local block extension.

For **system obligations 140–150** (task IDs 169–179), keep the original fault,
failure-before-recovery, recovery and isolation obligations under existing mechanical owners. Use the
guarded `tools/run-tests system` route and exact listed selectors, adding only
a missing bounded case when necessary. Their internal controls never become
customer building blocks. A transfer, mapping or host-only test is not a live pass.

## Completion and document cleanup

A task is complete only after its stated live VM acceptance and terminal cleanup
pass. A block task can complete as an implemented, diagnostically qualified slice;
its catalogue row remains `pending` until the **complete first installed consumer**
passes. This distinction prevents a circular dependency between implementing a
block and registering its consumer.

After cleanup:

1. After **every completed E2E scenario** and its terminal cleanup, run
   `tools/generate_test_coverage.sh`, including when declarations did not change
   or the full consumer was completed during a block task. Paired variants each
   get a refresh after their own successful run and cleanup. This approved launcher
   executes [tools/generate_test_coverage.py](../../tools/generate_test_coverage.py)
   to regenerate [Test-Coverage.md](../Test-Coverage.md). The Python file is not a
   directly executable launcher. Require successful generation before checking
   off the task; generation itself is not execution evidence. Also regenerate
   after other inventory/collection changes, keeping engineering IDs/owners traceable.
2. Update [E2E-Building-Blocks.md](E2E-Building-Blocks.md): name the callable,
   exact implemented/qualified scope and maintained qualification selector.
   Keep partially qualified rows pending with the remaining scope stated.
   After the full consumer passes, mark only its ready scopes/rows ready and
   update current block/variant totals. Update runnable inventory bindings when
   relevant, then regenerate coverage again if close-out changed declarations.
   One surface does not qualify every binding. Keep qualification selectors and
   any required branch/profile parameters here or in maintained source so the
   next session never needs a completed task file.
3. Change this task's master `[ ]` to `[x]` only after all required acceptance
   and close-out work succeeds; retain its ID, title, scope and prerequisite IDs.
   Remove resolved blockers. If coverage generation or another close-out step
   fails, leave the task unchecked with only the outstanding action. Do not
   repeat a valid VM run for a status-only close-out repair when the retained
   runner result still matches the current implementation and verified inputs;
   otherwise rerun the affected acceptance. A consumer already
   completed as part of a block task may have its scenario row checked only if
   its entire recipe, exact selector, cleanup and coverage refresh also passed.
4. Preserve normal runner artifacts and existing reports. No new evidence
   document, accumulated history or task-specific report is required. Put brief
   results in the session response; retain an artifact pointer only when useful
   for an unresolved continuation.
5. Delete the completed task file once its enduring context is in source, the
   catalogue or this master. Retain it only for an explicit current need; no
   archival copy is required.
   Replace the completed row's task link with plain text before deleting it.
   No downstream task is allowed to require that deleted file.
6. Validate changed Markdown with `tools/read-only links '<file.md>' ...`.
   Status-only close-out edits happen after the guarded run; functional changes
   discovered afterward require another affected acceptance run.

The plan is finished when every active row is checked and all explicit gates
have been resolved, with every original obligation either passing in its proper
suite or explicitly retained under an agreed ownership/scope decision. Do not
describe unresolved/merely transferred work as done, or all 157 IDs as customer
passes. SEC01/GDM10 remain the two intentionally consumerless legacy deferrals.

## Explicit gates

| Task | Prerequisite | Completion rule |
| --- | --- | --- |
| 040a | Resolved public expectation for the documented 0–1440 model versus the 0–1439 editor | Inspect the existing requirements and prepare the expected/actual comparison in this task; unresolved intent blocks boundary acceptance and cases 7–12, not ordinary allowance editing. Complete only after the resolved finite set passes live. |
| 143 | Supported customer route to distinct same-child desktops or explicit ownership decision | Leave unchecked until its live acceptance passes; preserve the exact unfulfilled scope. |
| 150 | Explicit sending authorization covering the reviewed qualification/scenario submissions and dedicated test-recipient profile | Leave unchecked until its live acceptance passes; preserve the exact unfulfilled scope. |
| 152 | Supported customer connectivity route preserving safe observation | Leave unchecked until its live acceptance passes; preserve the exact unfulfilled scope. |
| 154 | Public mute feature or explicit customer-scope decision | Leave unchecked until its live acceptance passes; preserve the exact unfulfilled scope. |

The allowance boundary task may start its contract review before the decision is
available; it must not convert the current editor's behavior into the expected
result. Reuse an existing explicit decision, or request only the missing decision
with a concrete comparison. Record the resolved contract in the catalogue so no
later task needs that task document. This review does not authorize a new boundary.

Mute is currently hidden by `REQUEST_MEDIA_ENABLED = False`; planning does not
authorize a test-only switch. Distinct same-child desktops need a supported
customer entry route, not backend session creation. Public game/format locators
and supported package assets are additional task-local prerequisites: missing
access is a concrete blocker. Sending requires separately explicit authorization
for the reviewed synthetic content and dedicated test recipient; this planning
request grants none. Prepare all authorized reviewable work before requesting
any genuinely missing authorization, following the approval contract. Do not
edit/deploy the portal from this checkout.

If a gate remains unavailable, leave it and its dependent scenarios unchecked;
implement the remaining independent rows, including retained system obligations.
An explicit scope decision must retain excluded obligations and cannot create a
false passing variant. If authorized scope is retired, label the row `excluded`
with the current decision/owner instead of `[x]`, and update the active totals.
A missing feature or failed applicability check alone never retires a row.

## Ordered task queue

Prerequisite numbers refer to completed capability rows, not documents to read.
`Existing baseline` means the already-qualified source interfaces and standard
attempt envelope. Prerequisites supply code and qualified contracts; they never
supply another task's document or persisted VM state. All minutes are estimates. Suffix IDs remain where their
dependencies place them; do not sort this table by ID or filename. Add a short
current blocker directly to an affected row when necessary.

| Done | ID | Task | Prerequisites | Delivered scope | Minutes |
| --- | --- | --- | --- | --- | --- |
| [ ] | 001 | [Visible terminal launch, submission and denial](E2E-Tasks/001-terminal.md) | Existing baseline | FILE01, FILE02, FILE06 | 25–45 |
| [ ] | 002 | [E2E-004: terminal](E2E-Tasks/002-case-6.md) | 001 | Cases 6 | 30–55 |
| [ ] | 003 | [Open session controls and switch or sign out](E2E-Tasks/003-desktop-session.md) | Existing baseline | DESK02, DESK03, DESK04 | 35–55 |
| [ ] | 004 | [Allow distinct single-use authentication challenges](E2E-Tasks/004-challenges.md) | 003 | UI19/GDM05 challenge context; JourneyPlan repeated stages/assertions | 40–60 |
| [ ] | 005a | [Start a graphical journey before product installation](E2E-Tasks/005a-product-free-entry.md) | 001, 004 | Product-free graphical start and verified package staging | 30–50 |
| [ ] | 005 | [Qualify terminal administrator password input](E2E-Tasks/005-terminal-auth.md) | 005a | AUTH03; FILE06 package challenge/completion | 40–60 |
| [ ] | 006 | [Perform a customer package operation](E2E-Tasks/006-package-command.md) | 005 | LIFE04 | 35–55 |
| [ ] | 007 | [Observe a deliberate customer reboot](E2E-Tasks/007-customer-reboot.md) | 003, 006 | LIFE02 | 40–60 |
| [ ] | 008 | [E2E-002: clean](E2E-Tasks/008-case-2.md) | 007 | Cases 2 | 40–60 |
| [ ] | 011 | [Enter and read the request station](E2E-Tasks/011-kiosk-entry.md) | Existing baseline | REQUEST01, REQUEST03 | 35–55 |
| [ ] | 010 | [Set one public toggle explicitly](E2E-Tasks/010-toggle.md) | Existing baseline | UI17 | 25–45 |
| [ ] | 017 | [Observe Parent save results](E2E-Tasks/017-parent-save.md) | 010 | PARENT08 snapshot saved/control states | 25–45 |
| [ ] | 012 | [Select kiosk accounts and read availability](E2E-Tasks/012-request-choices.md) | 011, 010, 017, 003 | REQUEST04 kiosk child/approver; REQUEST08 unavailable state | 25–45 |
| [ ] | 018 | [E2E-017: disabled-child](E2E-Tasks/018-case-57.md) | 010, 017, 012, 003 | Cases 57 | 30–50 |
| [ ] | 024 | [Prepare empty kiosk account profiles](E2E-Tasks/024-kiosk-fixtures.md) | 012 | FIX03 no-child/no-approver profiles | 40–60 |
| [ ] | 026 | [E2E-017: no-child / no-parent](E2E-Tasks/026-case-54-55.md) | 024, 012 | Cases 54, 55 | 30–50 |
| [ ] | 029 | [Open feedback and read synthetic drafts](E2E-Tasks/029-feedback-read.md) | Existing baseline | FEED01, FEED03 | 25–45 |
| [ ] | 009 | [Replace a nonsecret field value](E2E-Tasks/009-text.md) | 029 | UI16 | 25–45 |
| [ ] | 012a | [Choose kiosk duration and app-access values](E2E-Tasks/012a-request-duration.md) | 012, 009 | REQUEST04 duration; REQUEST05/06(soft-apps)/08 kiosk estimates | 30–50 |
| [ ] | 013 | [Observe request results and exits](E2E-Tasks/013-request-exit.md) | 011 | REQUEST11/12 kiosk cancel/escape | 25–45 |
| [ ] | 014 | [Compose prepared request choices](E2E-Tasks/014-request-flow.md) | 012a, 013 | FLOW04 kiosk | 25–45 |
| [ ] | 015 | [E2E-015: kiosk-cancel / kiosk-escape](E2E-Tasks/015-case-47-48.md) | 014, 013 | Cases 47, 48 | 25–45 |
| [ ] | 019 | [Qualify the real selected-parent approval prompt](E2E-Tasks/019-auth-prompt.md) | 012a, 004 | REQUEST09, AUTH01 kiosk | 40–60 |
| [ ] | 020 | [Approve, reject or cancel a fresh request challenge](E2E-Tasks/020-auth-result.md) | 019, 013 | AUTH02 and REQUEST11/12 kiosk outcomes | 40–60 |
| [ ] | 021 | [Compose approval, kiosk time and rejection](E2E-Tasks/021-approval-flow.md) | 020, 014 | FLOW05/06/07 kiosk | 35–55 |
| [ ] | 022 | [E2E-016: approved](E2E-Tasks/022-case-50.md) | 021 | Cases 50 | 30–50 |
| [ ] | 023 | [E2E-016: denied / cancelled](E2E-Tasks/023-case-51-52.md) | 021 | Cases 51, 52 | 35–55 |
| [ ] | 024a | [Prepare multiple and ineligible-approver profiles](E2E-Tasks/024a-eligible-kiosk-fixtures.md) | 012, 020 | FIX03 multiple/ineligible-approver profiles | 30–50 |
| [ ] | 025 | [E2E-017: multiple](E2E-Tasks/025-case-53.md) | 024a, 012, 020 | Cases 53 | 30–55 |
| [ ] | 027 | [E2E-017: ineligible-parent](E2E-Tasks/027-case-56.md) | 024a, 012, 020 | Cases 56 | 30–55 |
| [ ] | 030 | [Read privacy and preserve a dialog draft](E2E-Tasks/030-feedback-privacy.md) | 029, 009 | FEED05; FEED10 dialog persistence | 25–40 |
| [ ] | 031 | [Observe feedback validation and Send availability](E2E-Tasks/031-feedback-states.md) | 029, 009 | FEED09 validation/control snapshots | 20–40 |
| [ ] | 032 | [E2E-031: validation](E2E-Tasks/032-case-153.md) | 030, 031 | Cases 153 | 30–50 |
| [ ] | 028 | [Close and reopen Parent](E2E-Tasks/028-app-restart.md) | Existing baseline | LIFE01 | 25–45 |
| [ ] | 030a | [Observe draft reset after Parent exits](E2E-Tasks/030a-feedback-reset.md) | 028, 030 | FEED10 app-exit reset | 20–40 |
| [ ] | 033 | [Apply and observe rich-text formatting](E2E-Tasks/033-format.md) | 009, 029 | UI24, FEED04 | 30–50 |
| [ ] | 034 | [E2E-031: draft-reopen](E2E-Tasks/034-case-152.md) | 033, 030a | Cases 152 | 30–50 |
| [ ] | 036 | [Navigate the file manager and copy or rename fixtures](E2E-Tasks/036-files.md) | 009 | FILE07/04/05; FIX04 synthetic files | 35–55 |
| [ ] | 037 | [Select multiple files or cancel through a real chooser](E2E-Tasks/037-file-chooser.md) | 036, 029 | FILE03 open/cancel | 25–45 |
| [ ] | 038 | [Add, inspect, preview and remove attachments](E2E-Tasks/038-attachments.md) | 037, 029 | FEED06, FEED07, FEED12, FEED13 | 40–60 |
| [ ] | 039 | [E2E-031: attachments](E2E-Tasks/039-case-154.md) | 038, 030 | Cases 154 | 35–55 |
| [ ] | 016 | [Observe public transitions during input](E2E-Tasks/016-trace.md) | 004, 009, 029 | UI22 | 40–60 |
| [ ] | 031a | [Observe diagnostic collection from its start](E2E-Tasks/031a-feedback-collection.md) | 016, 030, 031 | FEED09 collection trace | 25–45 |
| [ ] | 037a | [Save to a customer-selected location through the chooser](E2E-Tasks/037a-save-chooser.md) | 037, 031a | FILE03 save | 20–40 |
| [ ] | 044a | [Return to an already-open window on one desktop](E2E-Tasks/044a-window-switch.md) | 001, 009, 029 | DESK10 same-desktop window switching | 20–40 |
| [ ] | 045 | [Save and open customer-selected diagnostics](E2E-Tasks/045-diagnostic-export.md) | 037a, 044a | FEED08 | 25–45 |
| [ ] | 046 | [E2E-031: diagnostic-export](E2E-Tasks/046-case-155.md) | 045, 030 | Cases 155 | 35–55 |
| [ ] | 040 | [Choose ordinary daily allowances](E2E-Tasks/040-allowance.md) | 009, 010, 017 | PARENT05/06 valid ordinary values | 25–45 |
| [ ] | 041 | [Read remaining time and configure time controls](E2E-Tasks/041-time-explanation.md) | 040, 017 | PARENT09, FLOW02 | 25–45 |
| [ ] | 043 | [Qualify fresh child login and time denial](E2E-Tasks/043-unlock.md) | 004, 041 | GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return | 30–50 |
| [ ] | 052 | [Read the child desktop countdown](E2E-Tasks/052-countdown.md) | 041, 043 | TIME01 child-desktop snapshots | 20–40 |
| [ ] | 061 | [E2E-015: kiosk-approved](E2E-Tasks/061-case-49.md) | 021, 041, 043, 052 | Cases 49 | 30–55 |
| [ ] | 070 | [Double-click kiosk Request and observe one prompt](E2E-Tasks/070-double-request.md) | 020, 016 | UI20; REQUEST10 kiosk binding | 35–55 |
| [ ] | 074 | [E2E-014: kiosk-predefined](E2E-Tasks/074-case-41.md) | 070, 052, 043 | Cases 41 | 40–60 |
| [ ] | 075 | [E2E-014: kiosk-custom](E2E-Tasks/075-case-42.md) | 070, 052, 043 | Cases 42 | 40–60 |
| [ ] | 076 | [E2E-014: kiosk-rest-of-day](E2E-Tasks/076-case-43.md) | 070, 052, 043 | Cases 43 | 40–60 |
| [ ] | 035 | [Prepare one native app and operate it publicly](E2E-Tasks/035-native-app.md) | 001, 009 | FIX04 native asset; APP01/02/03 native grid/command usable scope | 40–60 |
| [ ] | 047 | [Record app activity and compose launch/use](E2E-Tasks/047-app-activity.md) | 035, 043 | APP04; FLOW08 native usable-app scope | 25–45 |
| [ ] | 048 | [Reveal the child's request entry](E2E-Tasks/048-shell-panel.md) | 047, 041, 011 | DESK12, REQUEST02/03 overlay entry/readback | 40–60 |
| [ ] | 048a | [Choose overlay values and cancel or escape](E2E-Tasks/048a-overlay-choices.md) | 048, 012a, 013, 014 | REQUEST04/05/06/08/11/12 and FLOW04 overlay choices/exits | 30–50 |
| [ ] | 049 | [E2E-015: child-overlay-cancel / child-overlay-escape](E2E-Tasks/049-case-44-45.md) | 048a, 047 | Cases 44, 45 | 30–50 |
| [ ] | 048b | [Qualify approval and rejection on the child overlay](E2E-Tasks/048b-overlay-approval.md) | 048a, 020, 021 | REQUEST09, AUTH01/02, REQUEST11/12 and FLOW05/07 overlay authentication | 35–55 |
| [ ] | 060 | [E2E-015: child-overlay-approved](E2E-Tasks/060-case-46.md) | 048b, 047, 052 | Cases 46 | 30–55 |
| [ ] | 070a | [Observe one prompt after an overlay double-click](E2E-Tasks/070a-overlay-double-request.md) | 070, 048b | REQUEST10 overlay binding | 20–40 |
| [ ] | 071 | [E2E-014: child-overlay-predefined](E2E-Tasks/071-case-38.md) | 070a, 052, 041 | Cases 38 | 40–60 |
| [ ] | 072 | [E2E-014: child-overlay-custom](E2E-Tasks/072-case-39.md) | 070a, 052, 041 | Cases 39 | 40–60 |
| [ ] | 073 | [E2E-014: child-overlay-rest-of-day](E2E-Tasks/073-case-40.md) | 070a, 052, 041 | Cases 40 | 40–60 |
| [ ] | 042 | [Observe and qualify an intended lock challenge](E2E-Tasks/042-lock-recipient.md) | 003 | DESK05, DESK06, DESK07 | 40–60 |
| [ ] | 043a | [Qualify retained unlock and return from the lock screen](E2E-Tasks/043a-retained-unlock.md) | 043, 042, 004 | GDM02 retained-child lock entry; DESK08/11 | 35–55 |
| [ ] | 044 | [Visit retained users and existing windows](E2E-Tasks/044-retained-entry.md) | 043a, 044a | DESK09; FLOW15 and FLOW01 retained scopes | 40–60 |
| [ ] | 047a | [Compose retained app visits for distinct users](E2E-Tasks/047a-retained-app-visits.md) | 047, 044 | FLOW09 and FLOW14 distinct-user retention | 30–50 |
| [ ] | 050 | [Cancel and confirm grant revocation](E2E-Tasks/050-revocation.md) | 017, 041, 021, 044 | PARENT17, PARENT18 | 35–55 |
| [ ] | 051 | [Compose the daily-only time profile](E2E-Tasks/051-time-profiles-daily.md) | 050, 041, 044 | FLOW13 daily-only scope | 25–45 |
| [ ] | 052a | [Measure countdown ticks and guarded intervals](E2E-Tasks/052a-countdown-ticks.md) | 052, 051 | TIME03 guarded intervals; TIME02 ticks | 30–50 |
| [ ] | 062 | [Use an app until a natural enforced lock](E2E-Tasks/062-natural-expiry.md) | 052a, 047 | TIME04 | 35–55 |
| [ ] | 063 | [E2E-008: retained-unlock](E2E-Tasks/063-case-21.md) | 062, 043a | Cases 21 | 35–55 |
| [ ] | 064 | [E2E-008: fresh-login](E2E-Tasks/064-case-22.md) | 062, 043a, 050, 021 | Cases 22 | 40–60 |
| [ ] | 052b | [Prove countdown absence on other surfaces](E2E-Tasks/052b-countdown-absence.md) | 052, 043a | TIME01 lock/GDM/other-user absence | 20–40 |
| [ ] | 059 | [E2E-011: daily-only](E2E-Tasks/059-case-27.md) | 052a, 043a, 051, 052b | Cases 27 | 35–55 |
| [ ] | 065 | [Compose grant-only and combined time profiles](E2E-Tasks/065-time-profiles-grant.md) | 051 | FLOW13 grant-only/combined scope | 30–50 |
| [ ] | 066 | [E2E-010: parent](E2E-Tasks/066-case-25.md) | 065, 052a, 047, 043a | Cases 25 | 35–55 |
| [ ] | 067 | [E2E-010: other-child](E2E-Tasks/067-case-26.md) | 065, 052a, 047, 043a | Cases 26 | 35–55 |
| [ ] | 068 | [E2E-011: grant-only](E2E-Tasks/068-case-28.md) | 052a, 043a, 065, 052b | Cases 28 | 35–55 |
| [ ] | 069 | [E2E-011: combined](E2E-Tasks/069-case-29.md) | 052a, 043a, 065, 052b | Cases 29 | 35–55 |
| [ ] | 017a | [Observe saving while a Parent control changes](E2E-Tasks/017a-parent-save-trace.md) | 017, 016 | PARENT08 transition mode | 25–45 |
| [ ] | 040a | [Resolve and qualify daily-allowance boundaries](E2E-Tasks/040a-allowance-boundaries.md) | 040 | PARENT06 boundary/invalid values; PARENT08 validation | 25–45 |
| [ ] | 077 | [Read and filter the public app catalogue](E2E-Tasks/077-catalogue.md) | 009, 010, 035 | PARENT12, PARENT10, PARENT11 | 35–55 |
| [ ] | 078 | [Edit, save, cancel or reset one match rule](E2E-Tasks/078-match-editor.md) | 077, 017 | PARENT13, PARENT15 | 25–45 |
| [ ] | 079 | [Choose app access and compose policy editing](E2E-Tasks/079-policy.md) | 078, 077, 041, 035, 047a, 036 | PARENT16, FLOW03; native APP02/FLOW08 policy results | 40–60 |
| [ ] | 053 | [E2E-005: daily-only-new](E2E-Tasks/053-case-7.md) | 040a, 041, 017a, 021, 043a, 044, 047a, 052, 079 | Cases 7 | 40–60 |
| [ ] | 054 | [E2E-005: daily-only-retained](E2E-Tasks/054-case-8.md) | 040a, 041, 017a, 021, 043a, 044, 047a, 052, 079 | Cases 8 | 40–60 |
| [ ] | 055 | [E2E-005: grant-only-new](E2E-Tasks/055-case-9.md) | 040a, 041, 017a, 021, 043a, 044, 047a, 052, 079 | Cases 9 | 40–60 |
| [ ] | 056 | [E2E-005: grant-only-retained](E2E-Tasks/056-case-10.md) | 040a, 041, 017a, 021, 043a, 044, 047a, 052, 079 | Cases 10 | 40–60 |
| [ ] | 057 | [E2E-005: combined-new](E2E-Tasks/057-case-11.md) | 040a, 041, 017a, 021, 043a, 044, 047a, 052, 079 | Cases 11 | 40–60 |
| [ ] | 058 | [E2E-005: combined-retained](E2E-Tasks/058-case-12.md) | 040a, 041, 017a, 021, 043a, 044, 047a, 052, 079 | Cases 12 | 40–60 |
| [ ] | 080 | [E2E-006: enabled-precise](E2E-Tasks/080-case-13.md) | 079, 047, 065 | Cases 13 | 40–60 |
| [ ] | 081 | [E2E-006: enabled-pattern](E2E-Tasks/081-case-14.md) | 079, 047, 065 | Cases 14 | 40–60 |
| [ ] | 082 | [E2E-006: disabled-precise](E2E-Tasks/082-case-15.md) | 079, 047, 065 | Cases 15 | 40–60 |
| [ ] | 083 | [E2E-006: disabled-pattern](E2E-Tasks/083-case-16.md) | 079, 047, 065 | Cases 16 | 40–60 |
| [ ] | 084 | [E2E-007: zero-single](E2E-Tasks/084-case-17.md) | 050, 079, 047, 065 | Cases 17 | 40–60 |
| [ ] | 085 | [E2E-007: remaining-single](E2E-Tasks/085-case-19.md) | 050, 079, 047, 065 | Cases 19 | 40–60 |
| [ ] | 086 | [E2E-012: excluded-first / excluded-second](E2E-Tasks/086-case-30-31.md) | 048b, 079, 065, 047, 052 | Cases 30, 31 | 40–60 |
| [ ] | 087 | [E2E-012: included-first / included-second](E2E-Tasks/087-case-32-33.md) | 048b, 079, 065, 047, 052 | Cases 32, 33 | 40–60 |
| [ ] | 088 | [E2E-013: child-overlay-wrong-password / child-overlay-cancel](E2E-Tasks/088-case-34-35.md) | 048b, 079, 047, 065 | Cases 34, 35 | 40–60 |
| [ ] | 089 | [E2E-013: kiosk-wrong-password / kiosk-cancel](E2E-Tasks/089-case-36-37.md) | 021, 079, 065, 043, 047 | Cases 36, 37 | 40–60 |
| [ ] | 090 | [E2E-019: native-grid-allowed-enabled / native-grid-allowed-disabled](E2E-Tasks/090-case-62-63.md) | 079, 047, 041, 036 | Cases 62, 63 | 35–55 |
| [ ] | 091 | [E2E-019: native-grid-hard-blocked-enabled / native-grid-hard-blocked-disabled](E2E-Tasks/091-case-64-65.md) | 079, 047, 041, 036 | Cases 64, 65 | 35–55 |
| [ ] | 092 | [E2E-019: native-grid-soft-blocked-enabled / native-grid-soft-blocked-disabled](E2E-Tasks/092-case-66-67.md) | 079, 047, 041, 036 | Cases 66, 67 | 35–55 |
| [ ] | 099 | [E2E-019: native-command-allowed-enabled / native-command-allowed-disabled](E2E-Tasks/099-case-80-81.md) | 079, 047, 041, 036 | Cases 80, 81 | 35–55 |
| [ ] | 100 | [E2E-019: native-command-hard-blocked-enabled / native-command-hard-blocked-disabled](E2E-Tasks/100-case-82-83.md) | 079, 047, 041, 036 | Cases 82, 83 | 35–55 |
| [ ] | 101 | [E2E-019: native-command-soft-blocked-enabled / native-command-soft-blocked-disabled](E2E-Tasks/101-case-84-85.md) | 079, 047, 041, 036 | Cases 84, 85 | 35–55 |
| [ ] | 105 | [E2E-025: excluded-new-login](E2E-Tasks/105-case-132.md) | 062, 079, 065, 021, 043, 047 | Cases 132 | 40–60 |
| [ ] | 107 | [E2E-025: included-new-login](E2E-Tasks/107-case-134.md) | 062, 079, 065, 021, 043, 047 | Cases 134 | 40–60 |
| [ ] | 036a | [Launch native fixtures from the file manager](E2E-Tasks/036a-native-file-routes.md) | 036, 035, 079 | APP01/02/03 native file-manager route | 30–50 |
| [ ] | 096 | [E2E-019: native-file-manager-allowed-enabled / native-file-manager-allowed-disabled](E2E-Tasks/096-case-74-75.md) | 079, 047, 041, 036a | Cases 74, 75 | 35–55 |
| [ ] | 097 | [E2E-019: native-file-manager-hard-blocked-enabled / native-file-manager-hard-blocked-disabled](E2E-Tasks/097-case-76-77.md) | 079, 047, 041, 036a | Cases 76, 77 | 35–55 |
| [ ] | 098 | [E2E-019: native-file-manager-soft-blocked-enabled / native-file-manager-soft-blocked-disabled](E2E-Tasks/098-case-78-79.md) | 079, 047, 041, 036a | Cases 78, 79 | 35–55 |
| [ ] | 036b | [Launch native fixtures from the desktop](E2E-Tasks/036b-native-desktop-route.md) | 036, 035, 079 | APP01/02/03 native desktop route | 30–50 |
| [ ] | 093 | [E2E-019: native-desktop-allowed-enabled / native-desktop-allowed-disabled](E2E-Tasks/093-case-68-69.md) | 079, 047, 041, 036b | Cases 68, 69 | 35–55 |
| [ ] | 094 | [E2E-019: native-desktop-hard-blocked-enabled / native-desktop-hard-blocked-disabled](E2E-Tasks/094-case-70-71.md) | 079, 047, 041, 036b | Cases 70, 71 | 35–55 |
| [ ] | 095 | [E2E-019: native-desktop-soft-blocked-enabled / native-desktop-soft-blocked-disabled](E2E-Tasks/095-case-72-73.md) | 079, 047, 041, 036b | Cases 72, 73 | 35–55 |
| [ ] | 102 | [Compose expiry recovery through kiosk approval](E2E-Tasks/102-replacement.md) | 062, 021, 047, 079, 065 | FLOW11 | 35–55 |
| [ ] | 103 | [E2E-009: excluded](E2E-Tasks/103-case-23.md) | 102, 079, 065 | Cases 23 | 35–55 |
| [ ] | 104 | [E2E-009: included](E2E-Tasks/104-case-24.md) | 102, 079, 065 | Cases 24 | 35–55 |
| [ ] | 106 | [E2E-025: excluded-retained-unlock](E2E-Tasks/106-case-133.md) | 102, 079, 065 | Cases 133 | 40–60 |
| [ ] | 108 | [E2E-025: included-retained-unlock](E2E-Tasks/108-case-135.md) | 102, 079, 065 | Cases 135 | 40–60 |
| [ ] | 109 | [Qualify supported Snap app launch routes](E2E-Tasks/109-snap.md) | 079, 047 | FIX04 and APP01/02/03 Snap scope | 35–55 |
| [ ] | 110 | [E2E-019: snap-grid-allowed-enabled / snap-grid-allowed-disabled](E2E-Tasks/110-case-86-87.md) | 079, 047, 041, 109 | Cases 86, 87 | 35–55 |
| [ ] | 111 | [E2E-019: snap-grid-hard-blocked-enabled / snap-grid-hard-blocked-disabled](E2E-Tasks/111-case-88-89.md) | 079, 047, 041, 109 | Cases 88, 89 | 35–55 |
| [ ] | 112 | [E2E-019: snap-grid-soft-blocked-enabled / snap-grid-soft-blocked-disabled](E2E-Tasks/112-case-90-91.md) | 079, 047, 041, 109 | Cases 90, 91 | 35–55 |
| [ ] | 113 | [E2E-019: snap-command-allowed-enabled / snap-command-allowed-disabled](E2E-Tasks/113-case-92-93.md) | 079, 047, 041, 109 | Cases 92, 93 | 35–55 |
| [ ] | 114 | [E2E-019: snap-command-hard-blocked-enabled / snap-command-hard-blocked-disabled](E2E-Tasks/114-case-94-95.md) | 079, 047, 041, 109 | Cases 94, 95 | 35–55 |
| [ ] | 115 | [E2E-019: snap-command-soft-blocked-enabled / snap-command-soft-blocked-disabled](E2E-Tasks/115-case-96-97.md) | 079, 047, 041, 109 | Cases 96, 97 | 35–55 |
| [ ] | 116 | [Qualify supported Flatpak launch routes](E2E-Tasks/116-flatpak.md) | 079, 047 | FIX04 and APP01/02/03 Flatpak scope | 35–55 |
| [ ] | 117 | [E2E-019: flatpak-grid-allowed-enabled / flatpak-grid-allowed-disabled](E2E-Tasks/117-case-98-99.md) | 079, 047, 041, 116 | Cases 98, 99 | 35–55 |
| [ ] | 118 | [E2E-019: flatpak-grid-hard-blocked-enabled / flatpak-grid-hard-blocked-disabled](E2E-Tasks/118-case-100-101.md) | 079, 047, 041, 116 | Cases 100, 101 | 35–55 |
| [ ] | 119 | [E2E-019: flatpak-grid-soft-blocked-enabled / flatpak-grid-soft-blocked-disabled](E2E-Tasks/119-case-102-103.md) | 079, 047, 041, 116 | Cases 102, 103 | 35–55 |
| [ ] | 120 | [E2E-019: flatpak-command-allowed-enabled / flatpak-command-allowed-disabled](E2E-Tasks/120-case-104-105.md) | 079, 047, 041, 116 | Cases 104, 105 | 35–55 |
| [ ] | 121 | [E2E-019: flatpak-command-hard-blocked-enabled / flatpak-command-hard-blocked-disabled](E2E-Tasks/121-case-106-107.md) | 079, 047, 041, 116 | Cases 106, 107 | 35–55 |
| [ ] | 122 | [E2E-019: flatpak-command-soft-blocked-enabled / flatpak-command-soft-blocked-disabled](E2E-Tasks/122-case-108-109.md) | 079, 047, 041, 116 | Cases 108, 109 | 35–55 |
| [ ] | 123 | [Keep an unsaved match draft across a fixture update](E2E-Tasks/123-catalog-change.md) | 079, 006, 044a | LIFE04 fixture update; PARENT15 present-row save | 25–45 |
| [ ] | 124 | [E2E-020: update](E2E-Tasks/124-case-110.md) | 079, 006, 044, 047, 123 | Cases 110 | 35–55 |
| [ ] | 123a | [Save a match draft after fixture removal](E2E-Tasks/123a-catalog-removal.md) | 079, 006, 044a | LIFE04 fixture remove/reinstall; PARENT15 absent-row save | 30–50 |
| [ ] | 125 | [E2E-020: remove](E2E-Tasks/125-case-111.md) | 079, 006, 044, 047, 123a | Cases 111 | 35–55 |
| [ ] | 126 | [Prepare and play a real offline game windowed](E2E-Tasks/126-game.md) | 062, 065 | Game APP01/02/03/04; APP05/FLOW10 windowed | 40–60 |
| [ ] | 127 | [E2E-023: windowed](E2E-Tasks/127-case-126.md) | 126, 079, 043 | Cases 126 | 40–60 |
| [ ] | 128 | [E2E-024: grant-dominant-windowed](E2E-Tasks/128-case-130.md) | 126, 079, 065, 048b | Cases 130 | 40–60 |
| [ ] | 132 | [Compose a daily-dominant profile without clearing the grant](E2E-Tasks/132-time-profiles-dominant.md) | 065, 048a | FLOW13 daily-dominant scope | 25–45 |
| [ ] | 133 | [E2E-024: daily-dominant-windowed](E2E-Tasks/133-case-128.md) | 126, 079, 065, 048b, 132 | Cases 128 | 40–60 |
| [ ] | 129 | [Play fullscreen to natural lock](E2E-Tasks/129-game-fullscreen.md) | 126 | APP05/FLOW10 fullscreen play | 30–50 |
| [ ] | 130 | [E2E-023: fullscreen](E2E-Tasks/130-case-127.md) | 129, 079, 043 | Cases 127 | 40–60 |
| [ ] | 129a | [Reach an overlay request from fullscreen gameplay](E2E-Tasks/129a-fullscreen-request.md) | 129, 048a, 044a | DESK12 fullscreen reveal; overlay/game return | 25–45 |
| [ ] | 134 | [E2E-024: daily-dominant-fullscreen](E2E-Tasks/134-case-129.md) | 129a, 079, 065, 048b, 132 | Cases 129 | 40–60 |
| [ ] | 131 | [E2E-024: grant-dominant-fullscreen](E2E-Tasks/131-case-131.md) | 129a, 079, 065, 048b | Cases 131 | 40–60 |
| [ ] | 135 | [Follow process activation after a real update](E2E-Tasks/135-activation-process.md) | 028, 044, 006, 079, 048a | LIFE04 update; LIFE05 process/none scope | 30–50 |
| [ ] | 136 | [E2E-026: process](E2E-Tasks/136-case-136.md) | 135, 079, 047, 014 | Cases 136 | 40–60 |
| [ ] | 137 | [Follow session activation after a real update](E2E-Tasks/137-activation-session.md) | 044, 006, 079, 048a | LIFE04 update; LIFE05 session scope | 30–50 |
| [ ] | 138 | [E2E-026: session](E2E-Tasks/138-case-137.md) | 137, 079, 047, 014 | Cases 137 | 40–60 |
| [ ] | 139 | [Follow reboot activation after a real update](E2E-Tasks/139-activation-reboot.md) | 007, 044, 006, 079, 048a | LIFE04 update; LIFE05 reboot scope | 30–50 |
| [ ] | 140 | [E2E-026: reboot](E2E-Tasks/140-case-138.md) | 139, 079, 047, 014 | Cases 138 | 40–60 |
| [ ] | 141 | [Qualify product removal and reinstall commands](E2E-Tasks/141-product-removal.md) | 007, 079, 014, 047 | LIFE04 product remove/reinstall; LIFE05 corresponding notices/activation | 30–50 |
| [ ] | 141a | [Qualify purge and reinstall to visible defaults](E2E-Tasks/141a-product-purge.md) | 141, 041, 047 | LIFE04 purge; LIFE05 notice and reinstall/defaults | 30–50 |
| [ ] | 142 | [E2E-027: continuous](E2E-Tasks/142-case-139.md) | 005a, 007, 079, 047, 014, 141, 141a | Cases 139 | 35–60 + continuous run |
| [ ] | 143 | [Qualify distinct retained desktops for one child](E2E-Tasks/143-multi-desktop.md) | 047, 079, 050, 048b | FLOW14 same-child multi-desktop scope | 20–40 | <!-- Gate: Supported customer route to distinct same-child desktops or explicit ownership decision -->
| [ ] | 144 | [E2E-007: zero-multiple](E2E-Tasks/144-case-18.md) | 050, 079, 047, 065, 143 | Cases 18 | 40–60 |
| [ ] | 145 | [E2E-007: remaining-multiple](E2E-Tasks/145-case-20.md) | 050, 079, 047, 065, 143 | Cases 20 | 40–60 |
| [ ] | 146 | [E2E-021: save](E2E-Tasks/146-case-112.md) | 143, 079, 048, 050, 047, 065 | Cases 112 | 40–60 |
| [ ] | 147 | [E2E-021: approve-without-soft](E2E-Tasks/147-case-113.md) | 143, 079, 048, 050, 047, 065 | Cases 113 | 40–60 |
| [ ] | 148 | [E2E-021: approve-with-soft](E2E-Tasks/148-case-114.md) | 143, 079, 048, 050, 047, 065 | Cases 114 | 40–60 |
| [ ] | 149 | [E2E-021: revoke](E2E-Tasks/149-case-115.md) | 143, 079, 048, 050, 047, 065 | Cases 115 | 40–60 |
| [ ] | 150 | [Submit one authorized synthetic report and read success](E2E-Tasks/150-feedback-send.md) | 038, 031, 030 | FEED11, FEED14 | 30–50 | <!-- Gate: Explicit sending authorization and dedicated test-recipient profile -->
| [ ] | 151 | [E2E-032: success](E2E-Tasks/151-case-156.md) | 150 | Cases 156 | 35–55 |
| [ ] | 152 | [Change connectivity through public network controls](E2E-Tasks/152-network.md) | 150, 003, 010, 044a | LIFE06; FEED09 public retry state | 35–55 | <!-- Gate: Supported customer connectivity route preserving safe observation -->
| [ ] | 153 | [E2E-033: retry](E2E-Tasks/153-case-157.md) | 152 | Cases 157 | 35–55 |
| [ ] | 154 | [Qualify the publicly available mute choice](E2E-Tasks/154-mute.md) | 048a | REQUEST06 mute scope | 20–40 | <!-- Gate: Public mute feature or explicit customer-scope decision -->
| [ ] | 155 | [Compare per-child choices across request surfaces](E2E-Tasks/155-cross-surface.md) | 154, 048a, 048b, 021 | FLOW12 | 35–55 |
| [ ] | 156 | [E2E-018: overlay-to-kiosk-first / overlay-to-kiosk-second](E2E-Tasks/156-case-58-59.md) | 155, 065 | Cases 58, 59 | 40–60 |
| [ ] | 157 | [E2E-018: kiosk-to-overlay-first / kiosk-to-overlay-second](E2E-Tasks/157-case-60-61.md) | 155, 065 | Cases 60, 61 | 40–60 |
| [ ] | 158 | [E2E-022: app-restart-active](E2E-Tasks/158-case-116.md) | 155, 079, 047, 065, 052a, 028 | Cases 116 | 40–60 |
| [ ] | 159 | [E2E-022: app-restart-expired](E2E-Tasks/159-case-117.md) | 155, 079, 047, 065, 052a, 028 | Cases 117 | 40–60 |
| [ ] | 160 | [E2E-022: sign-out-in-active](E2E-Tasks/160-case-118.md) | 155, 079, 047, 065, 052a | Cases 118 | 40–60 |
| [ ] | 161 | [E2E-022: sign-out-in-expired](E2E-Tasks/161-case-119.md) | 155, 079, 047, 065, 052a | Cases 119 | 40–60 |
| [ ] | 162 | [E2E-022: reboot-active](E2E-Tasks/162-case-120.md) | 155, 079, 047, 065, 052a, 007 | Cases 120 | 40–60 |
| [ ] | 163 | [E2E-022: reboot-expired](E2E-Tasks/163-case-121.md) | 155, 079, 047, 065, 052a, 007 | Cases 121 | 40–60 |
| [ ] | 164 | [E2E-022: idle-active](E2E-Tasks/164-case-122.md) | 155, 079, 047, 065, 052a | Cases 122 | 40–60 |
| [ ] | 165 | [E2E-022: idle-expired](E2E-Tasks/165-case-123.md) | 155, 079, 047, 065, 052a | Cases 123 | 40–60 |
| [ ] | 166 | [Suspend and wake through normal controls](E2E-Tasks/166-suspend.md) | 052a, 003, 043a | LIFE03 | 35–55 |
| [ ] | 167 | [E2E-022: suspend-wake-active](E2E-Tasks/167-case-124.md) | 155, 079, 047, 065, 052a, 166 | Cases 124 | 40–60 |
| [ ] | 168 | [E2E-022: suspend-wake-expired](E2E-Tasks/168-case-125.md) | 155, 079, 047, 065, 052a, 166 | Cases 125 | 40–60 |
| [ ] | 169 | [Preserve and qualify E2E-028/startup-enforcement](E2E-Tasks/169-system-140.md) | Existing baseline | System obligation 140 | 30–60 |
| [ ] | 170 | [Preserve and qualify E2E-028/startup-broker](E2E-Tasks/170-system-141.md) | Existing baseline | System obligation 141 | 30–60 |
| [ ] | 171 | [Preserve and qualify E2E-028/zero-time-exposure](E2E-Tasks/171-system-142.md) | Existing baseline | System obligation 142 | 30–60 |
| [ ] | 172 | [Preserve and qualify E2E-028/usage-read](E2E-Tasks/172-system-143.md) | Existing baseline | System obligation 143 | 30–60 |
| [ ] | 173 | [Preserve and qualify E2E-028/kiosk-auth-agent](E2E-Tasks/173-system-144.md) | Existing baseline | System obligation 144 | 30–60 |
| [ ] | 174 | [Preserve and qualify E2E-029/failed-save](E2E-Tasks/174-system-145.md) | Existing baseline | System obligation 145 | 30–60 |
| [ ] | 175 | [Preserve and qualify E2E-029/stale-identity](E2E-Tasks/175-system-146.md) | Existing baseline | System obligation 146 | 30–60 |
| [ ] | 176 | [Preserve and qualify E2E-029/disconnect](E2E-Tasks/176-system-147.md) | Existing baseline | System obligation 147 | 30–60 |
| [ ] | 177 | [Preserve and qualify E2E-029/concurrent-transaction](E2E-Tasks/177-system-148.md) | Existing baseline | System obligation 148 | 30–60 |
| [ ] | 178 | [Preserve and qualify E2E-029/policy-reload](E2E-Tasks/178-system-149.md) | Existing baseline | System obligation 149 | 30–60 |
| [ ] | 179 | [Preserve and qualify E2E-029/partial-termination](E2E-Tasks/179-system-150.md) | Existing baseline | System obligation 150 | 30–60 |
