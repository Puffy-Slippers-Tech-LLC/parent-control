# Test evidence and export infrastructure

Task queue: [Ordered infrastructure queue](Export-Task-Queue.md).
Next task: **E03p-capture — [Publish and acknowledge working capture](Export-Tasks/E03p-capture.md)**.

Reduce repeated missing, wrong, outdated and expired evidence references through
shared test infrastructure. The [target design](Export-Design.md) records the
investigated failure families, proposed changes and quality boundary. E01's source
audit, E01a's protocol proposal and E01b's independent
[delivery freeze](Export-Design.md#e01b-delivery-freeze) are complete; runtime
delivery remains pending. Authoring a plan supplies no implementation credit.

## Scope and execution

This is test infrastructure work only. Acceptance is host-side tooling,
contract and recovery validation using private synthetic runs and recorded
metadata. No task runs product acceptance, installs the product, operates a VM,
qualifies a UI provider, renews a customer journey or completes another queue.
Target names in fixtures test provenance matching; they grant no installed pass.
Inspect existing evidence only through authorized read-only routes.

`tools/export` is an execution-plan launcher, not an artifact-copy command. It
uses the ordinary shared driver, a GPT-6.1 Sol High coordinator, a separate
master-path namespace and no automatic VM selection. Examples are alternatives:

```sh
tools/export --check
tools/export --tasks 1
tools/export --tasks 0
tools/export --stop
```

The existing generic entry can validate or execute the same plan:

```sh
tools/execute-plan --plan 'docs/TestAutomation/Export-Execution-Plan.md' --check
```

Both entries share ownership, resumption, task budgets, controller-source restart
guards and per-task Git close-out from
[execution plans](../Execution-Plans.md#common-launcher-interface). `--check`
validates all unfinished briefs without starting a model or making Git changes.
Do not start nested plan launchers or pass `--vm` to this infrastructure plan.
New executable grants join the next normal
[setup refresh](../Approval-Tools.md#one-time-setup); authoring requires no setup,
rule refresh, commit or push. A missing wrapper grant can use the existing generic
entry; it does not justify broadening permissions.

## Reading and delivery

Follow [AGENTS.md](../../AGENTS.md), the [documentation map](README.md),
[approval tools](../Approval-Tools.md),
[test maintenance](../../tests/README.md) and the
[storage mandate](../Mandates/Test-Storage-Mandate.md). Read the selected brief,
its design sections and complete affected source functions and necessary callers.
Use [ordinary-plan delegation](../Execution-Plans.md#execution-and-delegation),
with bounded Sol assignments and one editor per shared state owner. Concurrency,
ownership and difficult recovery work needs High or higher effort. Independent
reviews must use self-contained assignments with `fork_turns="none"`.

E01 audits history, producers, consumers, retirement entry points and controller
dependencies. E01a proposes the schema, helper and lock/compatibility protocols;
E01b freezes them and the delivery allocation after independent review. No runtime
task starts before that gate passes. Later tasks deliver their boundary and update
the existing owning contracts; proposed design does not override current rules.
Reuse storage, retention, verified bundles, authenticated helpers and shared
launchers. Keep infrastructure policy separate from product acceptance verdicts.

Each implementation row includes its own safety regressions and host acceptance;
E14 adds composition coverage and E14a independent final review. Queue estimates
include reading, implementation, safety checks and cleanup. Longer provisional
ranges expose indivisible ownership/recovery work instead of assuming a 30-minute
cap. E01b must resolve every provisional range and freeze executable prerequisite
rows, briefs, retained assertions and revised estimates for any
independently deliverable mechanisms or families in their affected briefs; a generic
promise to split later does not pass the gate. The selected consumer inserts its
reviewed prerequisite block through the shared route before implementation, keeping
its original obligations and updating only its permitted queue bookkeeping.
The review gate must not rewrite protected future queue rows or adopt a checkpoint;
broader structural adoption still requires the existing reviewed reconciliation.
The selected consumer uses the exact frozen insertion, preserves all original
dependencies and acceptance, completes owned cleanup and supplies the supported
handoff before any prerequisite runs. An allocation review grants no completion
or additional session allowance.
Never omit checks to fit an estimate or split one crash-safe transaction into
unsafe partial deliveries. No product
qualification may be inserted to close this queue. Report external needs separately.

## Validation and close-out

Apply the design's [proportional validation](Export-Design.md#proportional-validation):
required evidence remains strict, while presentation and unrelated historical
debt do not repeatedly consume task sessions. New wrong or broken references
must not be accepted under a legacy exception. Changed acceptance inputs still
invalidate only the proof whose applicability changed; do not rerun unrelated
product tests or redefine their expected behavior.

Use the lowest effective maintained unit/contract selection with explicit
timeouts, preserving selectors. Register planned commands/tests before invocation.
Review new modules and resource changes under
[host parallelism](../../tests/README.md#host-test-parallelism-review).
Use private fixture journals for destructive/recovery cases; never rotate or
delete a live campaign's evidence to test retirement. Retain exact commands,
expected/actual results and owned cleanup through shared plan publication.
Run `make build` only if final edits affect package/build inputs.
The design's [required regression histories](Export-Design.md#required-regression-histories)
bind startup report rotation, the authenticated active-target selection path and
actual controller-dependency changes. Every task introducing shared dependencies
also applies its [restart guard](Export-Design.md#controller-compatibility-guard).

Check changed Markdown with `tools/read-only links` and this plan with `--check`.
Only accepted execution checks a row, advances the sole pointer and removes its
temporary brief after its enduring requirements have moved to the relevant
owner. No product, E2E, kiosk, fixture or reliability task receives completion
credit from this plan.
