# Test automation documentation

This directory defines customer-facing E2E composition and its implementation
queue. Repository-wide safety, authorization and UI identity rules remain in
[AGENTS.md](../../AGENTS.md); product behavior remains in the
[specification](../Specification.md) and [system design](../System-Design.md).
When documents disagree, use the ownership table below instead of combining the
strongest-looking fragments.

## Document ownership

| Source | Owns | Does not establish |
| --- | --- | --- |
| [`tests/e2e/scenarios.json`](../../tests/e2e/scenarios.json) | Persistent scenario IDs, customer steps, runtime status and executable binding | A pass merely because a declaration exists |
| [E2E building blocks](E2E-Building-Blocks.md) | Atomic/composite operation contracts, callables, scoped qualification and provider gaps | Scenario readiness or task order |
| [Scenario recipes](E2E-Scenario-Recipes.md) | Exact scenario composition, finite inputs and expected public results | Current runner status or scheduling |
| [Execution plan](E2E-Execution-Plan.md) | Next-task selection, implementation workflow, live verification and close-out | Product behavior or reusable block semantics |
| [Task queue](E2E-Task-Queue.md) | Ordered dependency checklist and delivered task scope | Current block or scenario readiness |
| `E2E-Tasks/` | Temporary brief for one unfinished queue item | Enduring policy or history after the task closes |
| `Audit/` | Temporary accessibility-remediation scope and evidence | Customer acceptance or a replacement execution queue |
| [Generated coverage](../Test-Coverage.md) | Generated view of the executable inventories | Authority over its source files |

Use the narrowest owner. Expected customer behavior comes from the specification
and system design, not from a currently observed result. A confirmed mismatch
follows the repository regression-failure contract rather than being reconciled
as a documentation preference.

## Status vocabulary

- **Task complete (`[x]`)** means the task's recorded deliverable and close-out
  passed when completed. A later mandate or dependency change can make its block
  or scenario pending without erasing that history.
- **Block ready** means the exact catalogue scope has an implementation and the
  required qualification under the current automation mandate. Readiness does
  not transfer to an unlisted surface, binding or consumer.
- **Scenario ready** means the current `scenarios.json` variant has a complete
  executable customer journey whose required blocks, collection and cleanup are
  qualified. A declaration, host test, task checkmark or older passing run is not
  enough.
- **Pending** means required implementation or qualification remains. Preserve a
  concrete blocker and return condition.
- **Provider blocked** means every affected path safely refuses before prohibited
  discovery/input, but a required external public-ID contract is unavailable.
  This is containment, not readiness or customer acceptance.
- **Retired** means the route cannot execute. Preserve displaced behavioral or
  engineering obligations under their current owner.

Current counts are derived from the source inventories and regenerated into
[Test coverage](../Test-Coverage.md); do not maintain independent totals in
multiple prose documents. Historical evidence may be cited to preserve delivered
scope, but current readiness always uses the current contracts and inventory. If
the generated report differs, the source inventory wins and regeneration remains
required.

## Working route

For queue work, read the [execution plan](E2E-Execution-Plan.md), its **Next
task**, the selected brief, and only the referenced catalogue/recipe rows and
source callables. Do not load the full queue or every brief into an ordinary
implementation session.

For design or review work, start with the owning document above. For temporary
identity remediation, follow [the audit plan](Audit/README.md); completing that
plan does not complete customer scenarios.

All live UI work inherits the [UI automation mandate](../../AGENTS.md#ui-automation-mandate):
public scoped IDs establish identity; semantic state/text verifies results only
after identity lookup; missing external IDs block the consumer; and customer
outcomes require independent public observations.
