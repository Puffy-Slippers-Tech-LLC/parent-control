# Test evidence and export infrastructure

Task queue: [Ordered infrastructure queue](Export-Task-Queue.md).
Next task: **E09 — [Generate and validate specific evidence links](Export-Tasks/E09-validation.md)**.

Reduce missing, wrong and expired evidence references through the existing shared
storage, retention, verified bundle and plan-driver code. The
[implementation direction](Export-Design.md#implementation-direction) replaces
the unimplemented global custody and segmented-archive proposal. Delivered
readers, authentication, exact identities and acceptance stay strict.

## Scope and execution

This is host-side test infrastructure work using private synthetic runs and
recorded metadata. No task installs the product, operates a VM, runs product
acceptance, qualifies a provider or completes another queue. Target names in
fixtures test provenance only.

`tools/export` is a small adapter to the ordinary shared driver: GPT-6.1 Sol
High, its existing plan namespace and no automatic VM selection. Examples:

```sh
tools/export --check
tools/export --tasks 1
tools/export --tasks 0
tools/export --stop
```

The generic equivalent is:

```sh
tools/execute-plan --plan 'docs/TestAutomation/Export-Execution-Plan.md' --check
```

Both entries share
[ownership, resumption, task budgets and Git close-out](../Execution-Plans.md#common-launcher-interface).
`--check` is model-free, VM-free and Git-free. Do not start a nested launcher or
pass `--vm` to this plan. Authoring this plan requires no setup, commit or push.

## Delivery

Follow [AGENTS.md](../../AGENTS.md), the [documentation map](README.md),
[approval tools](../Approval-Tools.md) and [test maintenance](../../tests/README.md).
The mandate boundaries below apply to every remaining brief and final review;
historical counts and frozen audit matrices do not override current mandates.
Read the selected brief and complete affected functions/callers. Use the shared
[delegation contract](../Execution-Plans.md#execution-and-delegation) when useful,
with one editor per state owner and self-contained reviews.

| Owner | Application to this queue |
| --- | --- |
| [Test scope mandate](../Mandates/Test-Scope-Mandate.md) | Test core dispatch, verdict, identity, evidence, authority and cleanup guarantees directly. Reuse existing coverage; add only a concrete uncovered failure or changed composition. Do not test ordinary cases/helpers recursively or add/retain UI tests of test tools. |
| [UI automation mandate](../Mandates/UI-Automation-Mandate.MD) | Evidence viewers, watchers and fixture panels gain no UI acceptance matrix. Preserve existing product input/result guards; private protocol doubles establish no product UI or provider qualification. |
| [VM mandate](../Mandates/VM-Mandate.MD) | All target and privileged identities here are private host simulations. No VM probing, preparation, operation, observation qualification or installed acceptance is part of a task; new live needs require separate authorized scope under that owner. |
| [Test storage mandate](../Mandates/Test-Storage-Mandate.md) | Use shared allocation, owner journals, retention, descriptors and exact owned cleanup for fixtures and retained proof. Preserve recording/screenshot exceptions and existing budgets; no independent roots, sweeps or new custody system. |

Keep delivery simple: extend the existing shared owner before adding a module,
interface or state machine. Account for every inventoried producer/consumer and
retirement route, but test a shared guarantee at its owner with representative
consumers. Add a separate consumer check only for distinct dispatch, policy or
lifetime behavior. Do not multiply consumers, handoff kinds and failure inputs
into a Cartesian matrix. Preserve all distinct safety outcomes and the three
required integration histories.

Implement one bounded path: finalize the explicit selection, publish and verify
it with the existing bundle transaction, record the exact receipt in the owning
workflow, then release the original. Keep pending-source guards at every
applicable retirement route. Use owner-local journals, cumulative replacement
and existing recovery; capacity refusal preserves current proof.

The queue directly assigns each mechanism and producer/consumer family.
The thirteen unactivated prerequisite allocations have been folded back into
their parent briefs, including their behavioral checks. Do not perform the old
automatic insertions. The already inserted E03 prerequisites and suspended work
retain their IDs, dependencies, counters and cleanup obligations. Discovering a
real independent prerequisite still uses the existing guarded insertion route;
structural replanning never silently adopts or weakens a retained checkpoint.

Each delivery reuses or extends its affected safety regressions. E14 composes
their real boundaries and E14a independently reviews the result. Estimates are
planning aids, not time caps or permission to drop checks. A plan edit completes
no queue task.

Follow the [remaining delivery boundaries](Export-Design.md#remaining-delivery-boundaries):
E10 owns the shared policy; E11 produces one finite inventory; E12 and E13 consume
and update it through delivered preview/apply and protected recovery. E14 reuses
the resulting safety checks and E14a reviews the final result. Add an interface,
module or transaction only for a concrete gap in an existing owner. Discovery,
verification, authorized mutation and acceptance remain separate operations.

## Validation and close-out

Apply [proportional validation](Export-Design.md#proportional-validation).
Required evidence, identity, authority and integrity failures block their affected
operation. Presentation and unchanged unrelated historical loss are advisory;
neither can satisfy acceptance or suppress a required failure.

Use the lowest effective maintained host selection with exact selectors and an
explicit timeout; do not expand to `host` or `all` for scheduling. Register new
interfaces/tests before use. Cover the
[three required histories](Export-Design.md#required-regression-histories):
real startup report rotation, exact archived selection during unrelated active
production, and actual dependency-byte changes reaching controller restart.
Each introducing change applies the
[controller guard](Export-Design.md#controller-compatibility-guard).
Use private fixture journals, finish applicable
[resource reviews](../../tests/README.md#host-test-parallelism-review), and retain
commands, expected/actual results and owned cleanup through shared publication.

Check changed Markdown with `tools/read-only links` and this plan with `--check`.
For queue/brief reconciliation, also run the maintained
[host consistency selection](E2E-Execution-Contracts.md#completion-and-document-cleanup).
Prose-only reconciliation adds no wording tests, executes no queue task and
changes no inventories or generated coverage. Run `make build` after the final
edit affecting build/package inputs, assessed through the Makefile's source and
tool dependencies; tests do not replace it. Only accepted execution checks a row,
advances the pointer and retires its temporary brief.
