# Test automation documentation

This directory defines customer-facing E2E composition and its implementation
queue. [AGENTS.md](../../AGENTS.md) is the repository entry point; the contracts
below own their detailed rules. Product behavior remains in the
[specification](../Specification.md) and [system design](../System-Design.md).
When documents disagree, use the ownership table below instead of combining the
strongest-looking fragments.

Checkout files may change while tests run. Such edits do not invalidate the run
or its completed cleanup prerequisites. Preserve actual test failures and the
staged-artifact, evidence and VM ownership checks. A test must not overwrite
unrelated host/source files; that preservation duty is distinct from rejecting
concurrent developer edits.

## Document ownership

| Source | Owns | Does not establish |
| --- | --- | --- |
| [Approval tools](../Approval-Tools.md) | Authorized command routes, setup and unattended execution | Permission for work outside the requested scope |
| [UI automation mandate](../Mandates/UI-Automation-Mandate.MD) | GUI versus supporting-command selection, public IDs, external-provider exception and input/result guards | Qualification of an adapter merely because its technique is permitted |
| [Application UI API](Application-UI-API.md) | Required product-control route for UI/E2E tests and tasks, stable operations, canonical values, adapter boundaries and control inventory | Installed desktop qualification |
| [VM mandate](../Mandates/VM-Mandate.MD) | Target selection, leases, observation and baseline preparation lifetime | A passing product result or permission to use the development host as an installed target |
| [Test storage mandate](../Mandates/Test-Storage-Mandate.md) | Shared allocation, retention and cleanup boundaries | Permission to delete unowned artifacts |
| [Test maintenance](../../tests/README.md) | Suite selection/scheduling, parallelism review, failure handling and runner operation | Customer acceptance from a host test |
| [Shared support guide](../../tests/support/README.md) | Reusable fixture and harness implementation routes | Scenario data or a second implementation of shared mechanics |
| [`tests/e2e/scenarios.json`](../../tests/e2e/scenarios.json) | Persistent scenario IDs, customer steps, runtime status and executable binding | A pass merely because a declaration exists |
| [E2E building blocks](E2E-Building-Blocks.md) | Atomic/composite operation contracts, callables, scoped qualification and provider gaps | Scenario readiness or task order |
| [Scenario recipes](E2E-Scenario-Recipes.md) | Exact scenario composition, finite inputs and expected public results | Current runner status or scheduling |
| [UI and E2E coverage](UI-and-E2E-Coverage.md) | GUI matrix ownership, duplicate review and minimal installed checks | A test pass, task completion or another task queue |
| [Execution plan](E2E-Execution-Plan.md) | Sole next-task pointer, implementation workflow and scoped reading routes | Product behavior, reusable block semantics or a second copy of the queue |
| [Execution contracts](E2E-Execution-Contracts.md) | Detailed sizing, provider qualification, live verification and close-out rules delegated by the execution plan | A second task queue, alternate selection or optional acceptance |
| [Task queue](E2E-Task-Queue.md) | Single ordered checklist, including provider prerequisites and retained regressions, and delivered task scope | Current block or scenario readiness |
| `E2E-Tasks/` | Temporary brief for one unfinished queue item | Enduring policy or history after the task closes |
| [Generated coverage](../Test-Coverage.md) | Generated view of the executable inventories | Authority over its source files |

Use the narrowest owner. The specification owns expected customer behavior;
system design owns implementation boundaries and documented limitations. Neither
an observed result nor a task brief silently changes the specification. A mismatch
follows the repository regression-failure contract rather than being reconciled
as a documentation preference.

When reconciling documents, correct the conflicting copy and link to the owner.
Do not weaken an assertion or infer a new authorization from stale prose.
Mandates constrain implementation; briefs add the selected task's finite scope
and acceptance, and cannot override a mandate. Preserve historical evidence as
historical, with current readiness in its inventory/catalogue owner.

## Status vocabulary

- **Task complete (`[x]`)** means the task's recorded deliverable and close-out
  passed when completed. A later mandate or dependency change can make its block
  or scenario pending without erasing that history.
- **Block ready** means the exact catalogue scope has an implementation and the
  required qualification under the current automation mandate. A qualified
  slice is reusable even while other bindings keep the overall block pending.
  It does not wait for its later complete scenario to become a prerequisite of
  that same scenario. Readiness does not transfer to an unlisted binding.
- **Scenario ready** is the inventory's executable registration status. Retained
  ready cases keep their bindings while shared adapters are being requalified;
  the label does not certify those adapters or a current installed pass. Execution
  must still satisfy every runtime guard and the catalogue's route qualifications.
- **Pending** means required implementation or qualification remains. Preserve a
  concrete blocker and return condition.
- **Provider blocked** means the current route safely refuses because neither a
  usable public-ID mapping nor a qualified external-provider adapter is available.
  Missing IDs alone do not prohibit adapter work authorized by AGENTS.md.
- **Retired** means the route cannot execute. Preserve displaced behavioral or
  engineering obligations under their current owner.
- **Excluded from scheduling** means an explicit scope decision removes the
  implementation task, not the uncovered behavior or stable case ID. The
  [native-gesture exclusion](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures)
  must not be recreated as a task or block the next-task pointer. Retained
  inventory variants stay pending with an explicit exclusion reason and no
  executable; this is not a pass or deferred implementation task.
- **Reallocated to UI** means a stable historical case verifies only local
  control behavior, so its executable coverage belongs to the named UI owner.
  Retain its inventory ID as pending with no executable and an explicit E2E
  scheduling exclusion. Preserve checked historical task evidence, but create
  no replacement E2E task and claim no current customer-journey acceptance.
  A host UI pass establishes only that component coverage.

Current counts are derived from the source inventories and regenerated into
[Test coverage](../Test-Coverage.md); do not maintain independent totals in
multiple prose documents. Historical evidence may be cited to preserve delivered
scope, but current readiness always uses the current contracts and inventory. If
the generated report differs, the source inventory wins and regeneration remains
required.

## Working route

For documentation reconciliation:

1. Identify each rule's owner in the table above. Correct a conflicting copy and
   replace repeated procedure with a scoped link; retain task-specific assertions,
   authorization gates, blockers and valid evidence.
2. Check source callables, inventory bindings and launcher help before describing
   an interface as implemented. Distinguish planned selectors from registered ones.
   Read the affected function and its necessary callers/callees, not just a search hit.
3. Update every unfinished consumer of the changed rule, including deferred briefs.
   Keep dependency order, case IDs, acceptance, session exceptions and the current
   blocker intact. Reconcile stale task descriptions against delivered scope.
4. Run `tools/read-only links` for changed Markdown and the host consistency
   selection in [close-out](E2E-Execution-Contracts.md#completion-and-document-cleanup).
   Refactored test code also needs its affected regressions and resource review.

This work does not execute or close the next queue task. Changes confined to
prose and metadata tests need no VM qualification or package build. Runtime,
provider, ownership or preparation changes retain their normal validation gates.

For test implementation, apply the [shared task contract](E2E-Execution-Contracts.md#task-brief-contract)
and the selected brief. Use the existing shared operations in both qualification
and cases; validate at the lowest effective layer before a required live attempt.

For queue work, read the [entry plan](E2E-Execution-Plan.md), its **Next task**
brief, then follow its [reading routes](E2E-Execution-Plan.md#load-only-the-selected-context).
Read the shared live contract and applicable acceptance branch before
implementation, and completion at close-out. Retrieve only applicable
catalogue/recipe rows, contract sections and source callables; do not load the
whole execution-contract reference, queue or every brief into an ordinary
implementation session. Scoped reading changes no acceptance requirement.

For design or review work, start with the owning document above. Identity
requirements, external-provider gaps and their return conditions are maintained
in [functional validation](E2E-Building-Blocks.md#functional-validation); keep
them separate from customer scenario completion.

Provider work follows the [UI mandate's route selection](../Mandates/UI-Automation-Mandate.MD#route-selection)
and the same [execution plan](E2E-Execution-Plan.md#external-provider-work-within-the-sequence).
The catalogue records qualification of exact bindings; historical tasks and
host-only checks cannot qualify a new route.
