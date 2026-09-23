# Test automation documentation

This directory defines customer-facing E2E composition and its implementation
queue. Repository-wide safety, authorization and UI identity rules remain in
[AGENTS.md](../../AGENTS.md); product behavior remains in the
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
| [`tests/e2e/scenarios.json`](../../tests/e2e/scenarios.json) | Persistent scenario IDs, customer steps, runtime status and executable binding | A pass merely because a declaration exists |
| [E2E building blocks](E2E-Building-Blocks.md) | Atomic/composite operation contracts, callables, scoped qualification and provider gaps | Scenario readiness or task order |
| [Scenario recipes](E2E-Scenario-Recipes.md) | Exact scenario composition, finite inputs and expected public results | Current runner status or scheduling |
| [Execution plan](E2E-Execution-Plan.md) | Sole entry point, fixed task sequence, implementation workflow and scoped reading routes | Product behavior or reusable block semantics |
| [Execution contracts](E2E-Execution-Contracts.md) | Detailed sizing, provider qualification, live verification and close-out rules delegated by the execution plan | A second task queue, alternate selection or optional acceptance |
| [Task queue](E2E-Task-Queue.md) | Single ordered checklist, including provider prerequisites and retained regressions, and delivered task scope | Current block or scenario readiness |
| `E2E-Tasks/` | Temporary brief for one unfinished queue item | Enduring policy or history after the task closes |
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

Current counts are derived from the source inventories and regenerated into
[Test coverage](../Test-Coverage.md); do not maintain independent totals in
multiple prose documents. Historical evidence may be cited to preserve delivered
scope, but current readiness always uses the current contracts and inventory. If
the generated report differs, the source inventory wins and regeneration remains
required.

## Working route

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

All live UI work inherits the [UI automation mandate](../Mandates/UI-Automation-Mandate.MD),
including its external-provider exception. The catalogue records implementation
gaps and route qualification; it does not redefine that mandate.
Apply its route-selection rule before creating UI work: routine Shell, GDM and
other system operations use shared commands, SSH or shortcuts. Only tested app
features and unavoidable graphical authentication need GUI adapters. Historical
completed tasks cannot make an unrelated system UI a customer requirement.

Provider work follows the same [execution plan](E2E-Execution-Plan.md#external-provider-work-within-the-sequence)
and ordered queue as every customer capability. There is one next-task pointer;
an incomplete row stays current. External IDs are optional conveniences and the
approved provider exception remains available. Repository-owned UI retains its
mandatory public-ID contract. Each provider capability includes its stated live
qualification; a host implementation alone cannot complete it.
