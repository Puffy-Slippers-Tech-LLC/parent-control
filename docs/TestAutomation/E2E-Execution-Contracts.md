# E2E execution contracts

These are the detailed contracts of the [execution plan](E2E-Execution-Plan.md),
not a second task queue. Use that plan's reading routes to load the applicable
sections; requirements remain mandatory when their trigger applies.
The shared live verification section ends at **Capability acceptance**.
Read it and the selected acceptance branch before implementation, and read
completion before close-out. Planning and provider sections have their own
triggers in the master.

## Task brief contract

Every unfinished brief inherits this contract. Read its task-specific scope,
prerequisites, implementation and acceptance alongside these applicable owners:

| Trigger | Required owner and execution rule |
| --- | --- |
| Selecting or resuming work | [Plan reading routes](E2E-Execution-Plan.md#load-only-the-selected-context); the first unchecked active queue row is authoritative. Prerequisite task IDs select delivered scope, not predecessor briefs or saved VM state. |
| Any implementation | [Shared support guide](../../tests/support/README.md), [bounded supporting work](E2E-Building-Blocks.md#keep-supporting-work-bounded) and [composition preflight](E2E-Building-Blocks.md#composition-preflight). Cases and qualifications call the same shared operations; callers retain their distinct assertions. |
| UI work | [Application UI API](Application-UI-API.md), [UI mandate](../Mandates/UI-Automation-Mandate.MD) and [UI/E2E allocation](UI-and-E2E-Coverage.md). All existing and new product reads/actions use the shared UI/E2E facade with scoped stable IDs and canonical values. Keep authentication, file choosers and supporting tools in their external adapters; supporting system operations use shared commands/APIs. |
| Reusable guest inputs | [Baseline lifetime](../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline). Add declared fixtures/dependencies to idempotent baseline preparation; attempts and app-snapshot preparation verify them. Deliberate package/account/file mutations under test remain in the journey. |
| Host checks | [Suite selection](../../tests/README.md#all-established-regressions) and [parallelism review](../../tests/README.md#host-test-parallelism-review); use selected `tools/run-tests unit`/`ui` scopes. Direct launchers remain available for narrow diagnosis. |
| Storage or cleanup changes | [Storage mandate](../Mandates/Test-Storage-Mandate.md) and the affected ownership/cleanup regressions. Use shared allocation and recorded identities. |
| Local UI obligation | [UI acceptance](#ui-acceptance). Keep component checks in their host UI owner; they supply no installed qualification or customer acceptance. |
| Live work | [Shared live verification](#live-verification-contract) plus the capability, scenario or system branch below. The [VM mandate](../Mandates/VM-Mandate.MD) owns watch, target selection and preparation flags. |
| Failure or missing prerequisite | [Failure handling](../../tests/README.md#handling-test-failures); retain expected/actual evidence and the current blocker. Repair proven mechanical defects within the bounded supporting-work contract. |
| Completion | [Close-out](#completion-and-document-cleanup), only after the selected task's complete acceptance and owned cleanup. |

Briefs contain task-specific deltas. Use this format for new and revised briefs:

- Link this contract and the applicable acceptance branch at the top. Those
  links include live prerequisites, failure handling and close-out; do not copy
  their procedures into a second checklist or generic Close out section.
- State the estimate and any session exception. For a split task, identify the
  remaining operation in Session boundary and name extracted prerequisite tasks.
  Implementation and acceptance describe that remaining slice; the cumulative
  delivered scope includes its unchanged qualified prerequisites.
- List required task IDs in the queue row's declared order with only the capability each supplies.
  State exact inventory binding/parameters for a scenario and link its recipe.
- Name the final product result, finite input/branch references, relevant source
  paths/symbols and selected qualification or case command. Mark nonexistent
  selectors as planned; inspect registration before running them.
- For a scenario, state the customer's goal and the outcomes that prove it.
  Include only UI operations needed to achieve or observe those outcomes;
  simplify redundant navigation, unchanged reads and dialog visits. Allocate
  individual widget behavior and local validation matrices to their UI owner.
  A capability brief states the named journey it enables and qualifies only
  the necessary operation/result and safety boundaries, not an extra UI matrix.
- Bind product steps to the shared Application UI API facade: declare the
  endpoint/surface, stable IDs, canonical values and independent results in the
  owning shared operation. Reuse the same operation in host UI and installed
  consumers. A brief's historical words such as click, type, Escape, focus or
  menu selection describe the user function; they do not authorize native input
  to product controls. Use `setValue`, `setText`, `activate`, editor operations
  and surface `close` as appropriate. Keep actual graphical authentication and
  system file chooser handoffs in their existing external-provider adapters.
- Apply the [result-oriented UI scope](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope)
  to new briefs and revised completed or pending coverage. Keep one independent
  final observation per tested result; retain intermediate checks only for a
  distinct functional outcome or necessary shared input-safety guard. Do not
  require popup, focus, caret or rendering choreography or exhaustive independent
  GUI combinations as a capability prerequisite. A final widget state alone is
  insufficient when the customer goal concerns access, saved work or another
  product effect.
- Retain task-specific gates, expected public results and unresolved acceptance
  with its existing evidence pointer. Shared rules remain links to their owners.

Cases use the [existing consumer path](E2E-Building-Blocks.md#add-a-consumer)
and the recipe's entry/transition rules in a fresh guarded attempt. Keep one
complete case per scenario task and independent-entry/refusal checks in capability
qualification. Cases and qualifications reuse shared operations; neither another
brief nor saved VM state supplies a prerequisite.

Target selection follows the [VM mandate](../Mandates/VM-Mandate.MD#authority-and-operation).
An explicit `--vm NAME` narrows diagnosis; report that limit without claiming other
targets. Brief commands without it select the enabled registry queue. A real
case command selects inventory `coverage_id`, never the task ID.

## Task size and order

The customer-first selection principle is applied when maintaining this fixed
order: prerequisites precede consumers, and every newly enabled complete scenario
is placed immediately after its last capability, in numeric case order, before
the next capability. Retained regression rows follow the same rule.
Ordinary customer work precedes the retained system obligations. Capabilities
requiring external authorization/assets or an unproven public trigger, with
their consumers, form the final part of the same queue; calendar windows are
last. This placement is fixed during planning, never selected at runtime.

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

One scenario task owns one numeric case and its complete fixed recipe. The
recipe may contain finite value checks or a continuous repeated customer history;
these are assertions inside that case, never task-selection loops. A capability
task uses its named fixed qualification and does not absorb the later scenario
task. Previously delivered scopes remain recorded when a task is split.

The UI mandate's [unsupported native gestures](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures)
are explicitly excluded from scheduling. Do not introduce tasks or prerequisites
for them; preserve uncovered case IDs without acceptance credit. This authorized
scope exclusion does not permit skipping an unrelated active blocker.

Authorization, real calendar windows and other unsupported public routes cannot be
removed by editing the schedule. They are acceptance prerequisites with one
documented return condition, not alternate branches. Prepare the selected task's
concrete inputs, then report the exact missing prerequisite and keep that task
current. This plan guarantees deterministic selection; it does not claim that
external prerequisites are already available.


## External-provider work within the sequence

Apply the [route-selection mandate](../Mandates/UI-Automation-Mandate.MD#route-selection)
before proposing provider work. Required product integration and unavoidable
graphical authentication need qualified GUI adapters; supporting system
operations use shared commands/APIs. Negative GDM/keyring exercises qualify
harness safety separately from customer journeys.

Necessary provider adapters are capability work for named consumers. Their scope and
current qualification stay in the
[provider catalogue](E2E-Building-Blocks.md#external-provider-qualification);
their next action is always a row in this queue. Product UI uses the Application
UI API with mandatory scoped public automation IDs. Supporting fixture apps use
their shared activity adapters and mandatory public IDs; owning their fixture
source does not turn them into product API endpoints or grant the external
provider exception.

For an external surface lacking usable IDs, use the
[provider exception](../Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception).
Spend at most ten minutes per provider surface once on an available tree and
useful official source, then implement the permitted scoped adapter. Reuse
recorded findings; an upstream patch, provider rebuild or exhaustive ID search
is not a prerequisite. The catalogue records each adapter's actual selectors,
limitations and installed route qualification.

Use the existing `AccessibleUI`, `UiObservations`, worker and guarded attempt
envelope. Apply the [input/result guards](../Mandates/UI-Automation-Mandate.MD#input-and-independent-results)
and [secret route contract](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary) to independent valid entry,
wrong-entry refusal and owned cleanup on the pinned VM. Incomplete observations
cannot prove absence; unknown prompts refuse. Viewport clipping alone does not
make an otherwise available control hidden or require scrolling before its action.

Record the actually qualified package versions, provider locale and keyboard
layout in existing sanitized evidence and the catalogue. Observer locale is
not provider locale. Scope support to that tuple; do not build an unsolicited
version/translation matrix. Native/portal choosers and MATE/Shell authentication
are separate bindings and keep separate live results.

Task briefs select fixed qualification routes in the maintained envelope.
Planned selectors must be implemented, registered and cleanup-tested before
use. Preparation and every live operation use the shared watch lease,
intention, display and guarded command transport. No additional runner, viewer,
generic selector language or VM controller is part of this plan.


## Live verification contract

Task **192** is the historical host-only exception. Explicit **UI obligation**
rows follow [UI acceptance](#ui-acceptance), without installed qualification.
All capability/scenario work,
including provider adapters, needs its stated acceptance on the guarded live VM;
engineering tasks need their actual system fault/recovery qualification.
Former separate host/VM adapter rows are combined into a bounded live slice or
split into smaller independently qualified operations. Host checks alone cannot
complete any new capability.

Follow [functional validation](E2E-Building-Blocks.md#functional-validation)
and the [UI mandate](../Mandates/UI-Automation-Mandate.MD) for route selection.
Use the Application UI API for product controls, qualified external input for
provider surfaces, and independent observations of required results.
Backend product probes, synthetic grants, clock changes,
internal faults and cosmetic/screenshot comparisons cannot pass customer cases.
Reuse the existing [consumer path](E2E-Building-Blocks.md#add-a-consumer):
`InstalledJourney/JourneyPlan`, `UiObservations`, `AccessibleUI` and the shared
worker/dispatch. Locate only the relevant callables through the catalogue.
Use shared watch observation and nonsecret intentions under the
[VM observation mandate](../Mandates/VM-Mandate.MD#vm-observation-mandate).
The viewer may attach independently; its lifetime never gates the operation.

Each attempt starts with fresh declared state and its own session/window ledger.
For post-installation work, run `./tools/prepare-appsnapshot --vm NAME --y --overwrite false`
under the [setup contract](E2E-Building-Blocks.md#parent-login-and-time-scenarios).
Use `--overwrite true` when application code changed; documentation-only and
test-only changes continue to use `false`.
Wait for completion; report meaningful blockers or results rather than routine
polling. Required watch observation remains active. Proceed only on success.
Online preparation leaves a maintenance-owned running VM;
release it with `tools/test-vm --vm NAME stop` before launching qualification or E2E so
the guarded attempt can acquire its own lease. The normal dispatcher owns
preparation/restoration. Package
lifecycle cases use their declared product-free start and real customer install.
Never use manual snapshots, resets or prior task state as a journey step.

Run affected cleanup/ownership safety regressions as an explicit scoped
validation before live integration; cleanup itself runs no tests. Use
`tools/run-tests unit` and relevant `tools/run-tests ui --timeout <duration>`
selections under the [scheduling contract](../../tests/README.md#all-established-regressions).
The recorded retained-case direction is a specific regression-scope exception:
complete retained cases other than case 6 are validated in tasks
specifically about those cases. Shared GDM, secret, routing, recorder or cleanup
changes in capability tasks still require affected host safety checks and the
task-local live qualification, without running cases **1, 3, 4, 5, 151** merely
as regressions. Do not claim complete-case validation from a capability slice.
Shared Parent launch changes retain case **6** when directly affected; case **193** remains
for its own validation task.

The initial provider migration's regression rows **001r, 003r, 004r, 005r,
002r, 235r and 151r** are historical delivered scope. Its gate is closed under
the recorded [acceptance decision](E2E-Execution-Plan.md#current-scope).
Preserve valid unchanged results. Later changes require affected checks and
qualification within the regression scope above; the historical decision is
not acceptance for newly changed code or additional registered cases.

Staged artifacts, evidence and VM ownership must remain valid. Checkout edits
during a run follow the [documentation map's contract](README.md); they do not
by themselves invalidate the attempt or its completed safety prerequisites.

The selected brief owns its applicability/authorization gate. Resolve it through
supported public routes; unavailable routes remain pending. Never edit/deploy
the portal or change expected behavior to manufacture a pass.

### Capability acceptance

For a **capability**, pass every stated outcome, independent valid entry and
wrong-entry refusal through the brief's fixed slice qualification in the
existing guarded envelope. Complete scenarios stay in their separate rows. Planned
`check_e2e_...` names must be implemented before invocation. New entries are
argument-free `tests/integration/check_[a-z][a-z0-9_]*.py` files with applicable
cleanup tests, selected by `tools/run-tests integration --vm NAME <name>`. Reuse shared
helpers and verified assets (`tools/run-tests artifacts build` when needed);
no new generic dispatcher or partial registered scenario. Record a passing slice
as qualified for its exact scope. Other bindings can keep the catalogue row
pending; a later complete scenario is not a prerequisite of its own building block.

### Scenario acceptance

For a **scenario**, register the complete recipe in the established
inventory/worker path, preserving every finite branch and terminal result.
Once the full executable binding and required capabilities are available, set
the variant to `ready` with that binding and a null `pending_reason` so the runner
can execute it. Keep the task unchecked until acceptance and close-out pass.
`ready` records registration, not a passing result; `pending` has no executable
and cannot be used for the acceptance run. Preserve any failed attempt and its
remaining work on the current task under the failure contract.
Run each exact `tools/run-tests e2e --id '<case>'` separately on the required
targets; use `--vm NAME` only for an explicitly narrowed run. Registration is
not acceptance. Require public results, reconciliation, collection and cleanup.
Refresh coverage after **each** successful case, including retained regressions,
before advancing the task pointer.

### System acceptance

For a **system obligation**, use the brief's maintained owner and listed
area. Discover actual selectors with
`tools/run-tests system --list --area '<area>'`; select every exact test needed
to cover the obligation. For each required registered target, prepare verified
package inputs with `tools/run-tests artifacts prepare --for-vm --vm NAME`,
then execute `tools/run-tests system --vm NAME --artifacts '<verified-directory>' --area '<area>' --test '<listed-test>'`.
Use the returned directory for that target: the maintained preparation route
selects RPM or DEB from its verified baseline. Replace all placeholders with
actual returned values and repeat the selections for the complete required
target set. These per-target commands do not reduce acceptance to one VM;
report any explicitly narrowed diagnostic run as such.

If no listed test covers the obligation, implement the brief's bounded planned
test under the same maintained owner and require it to be listed before running
it. Require the exact fault, observed failure, real recovery, unrelated-user
isolation and owned cleanup on the guarded VM. A mapping, proposed selector or
host-only check cannot complete it.

At [close-out](#completion-and-document-cleanup), record the actual owner,
selectors and qualification in [inventory reconciliation](E2E-Building-Blocks.md#inventory-reconciliation)
and update the [engineering scope](E2E-Scenario-Recipes.md#coverage-ownership-and-remaining-limits)
only when its composition or implementation context changed. Preserve the
obligation's numeric identity and suite allocation; system qualification supplies
no customer E2E credit. Regenerate coverage after inventory/collection changes.

### UI acceptance

An explicit `UI obligation;` queue row owns local control behavior removed from
customer E2E. Implement it in the named existing `tests/ui/` component owner,
reuse shared operations where appropriate, and pass the focused maintained
`tools/run-tests ui --timeout <duration>` selection. Apply host resource review
if its implementation changes resource ownership. No VM qualification or
package installation is required for a host component check.

Retain the task's finite functional assertions and mark missing component
coverage pending until executable and passing. This supplies no installed
scenario or provider acceptance, and must not gate unrelated customer journeys.
If a result actually needs live session identity, enforcement or OS integration,
keep that distinct result in its installed owner instead of calling a host
double equivalent. After a UI obligation passes, apply ordinary document
close-out without claiming an E2E pass or changing scenario readiness.

## Completion and document cleanup

After the guard is released and cleanup succeeds:

Verify that the selected task's required acceptance reports are still retained
after preparation and validation rotate completed runs. Finish input preparation
before the live acceptance slices where possible. A handoff's report reference
does not replace missing acceptance evidence; repeat only the affected slice if
its required report has been removed.

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
   Preserve the machine-readable scope prefix (`Cases N;`, `Retained regression N;`
   or `System obligation N`) when recording results. Close-out prose must not
   turn a scenario row into an apparent capability or lose its inventory mapping.
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
   Retained regression rows preserve the original migration bindings.
   Splitting former paired rows changes task granularity, never case IDs, finite
   matrices or assertions. Planning repairs leave Lunar case 253 pending; its
   scenario task follows the registration and acceptance sequence above. Retain system
   obligations formerly numbered 140–150 outside the UI inventory and preserve
   current customer case implementations and bindings. The explicitly
   [reallocated UI cases 161 and 190](UI-and-E2E-Coverage.md#duplicate-review-and-allocation)
   retain their stable IDs and historical evidence without runnable E2E bindings.
   Their shared
   provider routes still require qualification under the current mandate.

Run the maintained host consistency check after queue, pointer, brief or inventory
changes, including ordinary close-out:

```sh
tools/run-tests unit 'tests/unit/test_e2e_plan.py' 'tests/unit/test_e2e_inventory.py' 'tests/unit/test_coverage_generation.py' 'tests/unit/test_e2e_case_composition.py'
```

It checks the pointer, task/brief dependencies, exact scenario bindings, acceptance
branches and recipe links, one case per scenario task,
queued case titles and parameters, first-consumer hints, session sizing/exception
metadata and capability-before-consumer
order, plus declaration/worker composition for every ready binding. Lifecycle
recorders must declare their command operations and comparison callbacks through
shared APIs too; registration must not leave an existing composition failure for
a later audit. It does not qualify UI
adapters or establish a live pass.

If only coverage/status close-out remains, finish it without
rerunning an unchanged valid attempt solely for documentation.

Current-release completion requires every active row checked or explicitly
excluded by an authorized scope decision, all active gates resolved, and each
obligation passed in its proper suite. Deferred work is never counted as a pass.


## Planned Lunar Client regression

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
