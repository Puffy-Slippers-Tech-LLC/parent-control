# Test automation documentation

This directory defines customer-facing E2E composition and reusable operations.
[AGENTS.md](../../AGENTS.md) is the repository entry point; the contracts
below own their detailed rules. Product behavior remains in the
[specification](../Specification.md) and [system design](../System-Design.md).
When documents disagree, use the ownership table below instead of combining the
strongest-looking fragments.

For checkout edits during a run and reconnecting to existing work, follow
[runner reconnection](../../tests/README.md#aggregate-execution-and-reconnection)
and [failure handling](../../tests/README.md#handling-test-failures). Concurrent
edits supply no reason to discard valid results or overwrite unrelated work.
Each change owns its checks and cleanup. Completed work needs no historical
report renewal. The shared [completion policy](../Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery)
applies to all launchers and agent sessions; optional archives and expired
diagnostic files do not govern task progression.

## Document ownership

| Source | Owns | Does not establish |
| --- | --- | --- |
| [Approval tools](../Approval-Tools.md) | Authorized command routes, setup and unattended execution | Permission for work outside the requested scope |
| [Generic execution plans](../Execution-Plans.md) | Shared plan format, stable completion, launcher extension boundaries, task budgets and delegation | A replacement for the current work's E2E acceptance |
| [Test scope mandate](../Mandates/Test-Scope-Mandate.md) | Required product coverage, limits on recursive tests, exclusion of test-tool UI tests and reduction criteria | Permission to delete a failing product assertion to obtain a pass |
| [UI automation mandate](../Mandates/UI-Automation-Mandate.MD) | GUI versus supporting-command selection, public IDs, external-provider exception and input/result guards | Qualification of an adapter merely because its technique is permitted |
| [Application UI API](Application-UI-API.md) | Product-control operations, canonical values, adapter boundaries and control inventory | Installed desktop qualification or route selection independent of the UI mandate |
| [VM mandate](../Mandates/VM-Mandate.MD) | Target selection, leases, observation, baseline preparation lifetime and [timing resilience](../Mandates/VM-Mandate.MD#timing-and-slow-vm-resilience) | A passing product result or permission to use the development host as an installed target |
| [Test storage mandate](../Mandates/Test-Storage-Mandate.md) | Shared allocation, retention and cleanup boundaries | Permission to delete unowned artifacts |
| [Test maintenance](../../tests/README.md) | Suite selection/scheduling, parallelism review, failure handling and runner operation | Customer acceptance from a host test |
| [Shared support guide](../../tests/support/README.md) | Reusable fixture and harness implementation routes | Scenario data or a second implementation of shared mechanics |
| [Installed runner guide](../../tests/integration/README.md) and [environment](../../tests/integration/Environment.md) | Guarded installed-test interfaces and finite baseline dependency/fixture inventory | Authorization independent of the VM mandate or customer acceptance from preparation |
| [E2E runner guide](../../tests/e2e/README.md) | Implementation workflow, live acceptance, controller dispatch, observation and recovery | Acceptance from declaration, preparation or diagnostic qualification |
| [`tests/e2e/scenarios.json`](../../tests/e2e/scenarios.json) | Persistent scenario IDs, customer steps, runtime status and executable binding | A pass merely because a declaration exists |
| [E2E building blocks](E2E-Building-Blocks.md) | Atomic/composite operation contracts, callables, scoped qualification and provider gaps | Scenario readiness or task order |
| [Scenario recipes](E2E-Scenario-Recipes.md) | Exact scenario composition, finite inputs and expected public results | Current runner status or scheduling |
| [UI and E2E coverage](UI-and-E2E-Coverage.md) | GUI matrix ownership, duplicate review and minimal installed checks | A test pass, task completion or another task queue |
| [Two desktops](../Two_Desktops.md) | Open question and unscheduled same-child/two-desktop scenario descriptions | An execution plan, prerequisite, passing result or automatic authorization to implement the scenarios |
| [Unlock desktop](../Unlock_Desktop.md) | Open zero-time entry question and unscheduled exposure scenarios | An execution plan, prerequisite, passing result or automatic authorization to implement the scenarios |
| [Failed usage saves](../Failed_Save.md) | Open usage-save issue, causal findings and unscheduled former E2E-048 scenarios | An execution plan, passing result, regression gate or automatic authorization to resume the investigation |
| [Fixture design](Fixture-Design.md) | Immutable host inputs, minimal guest closure, provisioning/readiness and compatibility boundaries; runtime guides own current target availability | New runner capability or customer acceptance merely from the design |
| [Evidence/export design](Export-Design.md) | Test evidence identity, capture, export and lifetime design; runtime contracts remain authoritative | Product acceptance, VM operations or new passing results |
| [Generated coverage](../Test-Coverage.md) | Generated view of the executable inventories | Authority over its source files |

Use the narrowest owner. The specification owns expected customer behavior;
system design owns implementation boundaries and documented limitations. Neither
an observed result nor a task brief silently changes the specification. A mismatch
follows the repository regression-failure contract rather than being reconciled
as a documentation preference.

When reconciling documents, correct the conflicting copy and link to the owner.
Do not weaken a product assertion or infer a new authorization from stale prose.
Apply the [result-oriented review](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope)
when removing incidental external-provider requirements from existing coverage.
Mandates constrain implementation; a session request or ordinary task brief
adds finite scope and acceptance without overriding them. Current readiness
belongs in the inventory/catalogue, not task histories.

## Status vocabulary

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
- **Deferred Snap enforcement** is the developer-authorized exception in the
  [Snap scope decision](../Snap_Limitation.md#e2e-scope-decision).
  Retain pending IDs without runnable bindings or acceptance credit; separate
  remediation does not block active E2E work or require a repeated product choice.
- **Provider blocked** means the current route safely refuses because neither a
  usable public-ID mapping nor a qualified external-provider adapter is available.
  Missing IDs alone do not prohibit adapter work authorized by AGENTS.md.
- **Retired** means the route cannot execute. Preserve displaced behavioral or
  engineering obligations under their current owner.
- **Excluded from scheduling** means an explicit scope decision removes the
  implementation task, not the uncovered behavior or stable case ID. The
  [native-gesture exclusion](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures)
  must not be recreated as implementation work or a prerequisite. Retained
  inventory variants stay pending with an explicit exclusion reason and no
  executable; this is not a pass or deferred implementation task.
- **Reallocated to UI** means a stable historical case verifies only local
  control behavior, so its executable coverage belongs to the named UI owner.
  Retain its inventory ID as pending with no executable and an explicit E2E
  scheduling exclusion. Create no replacement E2E task and claim no customer-journey acceptance.
  A host UI pass establishes only that component coverage.

Current counts are derived from the source inventories and regenerated into
[Test coverage](../Test-Coverage.md); do not maintain independent totals in
multiple prose documents. Current readiness uses the maintained contracts and inventory. If
the generated report differs, the source inventory wins and regeneration remains
required.

## Working route

For documentation reconciliation:

1. Identify each rule's owner in the table above. Correct a conflicting copy and
   replace repeated procedure with a scoped link; retain functional assertions,
   authorization gates and current blockers.
2. Check source callables, inventory bindings and launcher help before describing
   an interface as implemented. Distinguish planned selectors from registered ones.
   Read the affected function and its necessary callers/callees, not just a search hit.
   When source falls short of a requirement, describe the implementation gap and
   return condition in its owner; do not rewrite the requirement to match source.
3. Update every affected consumer of the changed rule. Keep case IDs, acceptance,
   allocation and the current blocker intact.
4. Run `tools/read-only links` for changed Markdown and
   `tools/run-tests e2e --list` when inventory/registration changes.
   Refactored test code also needs its affected regressions and resource review.
   Documentation checks do not require old reports or repetition of passed work.

Check renamed headings against incoming links as well: the link reader checks
local Markdown fragments under its [reader contract](../Approval-Tools.md#launcher-inspection-and-workspace-edits).
Keep still-used anchors or update their consumers. Verify the final diff stays within the authorized scope; a prose-only
session leaves executable code, inventories and generated coverage unchanged.

Prose-only reconciliation needs no VM qualification or package build. Changed
metadata tests need their affected host checks. Runtime, provider, ownership or
preparation changes retain their normal validation gates.

For test implementation, follow the
[E2E guide](../../tests/e2e/README.md#verify-edits) in a normal session.
For a substantial batch, use an ordinary [execution plan](../Execution-Plans.md)
through `tools/execute-plan PATH`; installed tasks name their canonical targets
and exact cases. Read only the affected recipe, catalogue binding and source.
Use shared operations in qualification and cases, and validate at the lowest
effective layer before required live acceptance.

For design or review work, start with the owning document above. Identity
requirements, external-provider gaps and their return conditions are maintained
in [functional validation](E2E-Building-Blocks.md#functional-validation); keep
them separate from customer scenario completion.

Provider work follows the [UI mandate's route selection](../Mandates/UI-Automation-Mandate.MD#route-selection)
and the [E2E implementation guide](../../tests/e2e/README.md#verify-edits).
The catalogue records qualification of exact bindings; declarations and
host-only checks cannot qualify a new route.
