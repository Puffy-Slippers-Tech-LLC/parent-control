# Host-owned fixture execution plan

Task queue: [Ordered task queue](Fixture-Task-Queue.md).
Next task: **F51 — [Freeze schemas and transition contracts](Fixture-Tasks/F51-schemas.md)**.

## Outcome and present status

Keep as much fixture state on the host as possible. Restore a VM environment,
push only the selected test's necessary runtime payload over owned SSH, verify
readiness, then execute. Fix movable fixture payloads on the host and refresh an
owned running VM without snapshot replacement or reboot. Bound retained builds
and recover interrupted publication/provisioning without consuming partial state.

The [target design](Fixture-Design.md) remains unimplemented. F01 completed its
source-backed [placement inventory](Fixture-Design.md#frozen-placement-inventory),
consumer/alias map and planned public names under review acceptance. Schemas and
independent design review remain F51/F52. No fixture was provisioned, no current
VM/storage policy changed and no installed acceptance was supplied.

The specialized [E2E plan](E2E-Execution-Plan.md) remains responsible for customer
scenario work. This plan reuses its underlying
[ordinary execution-plan infrastructure](../Execution-Plans.md#extension-boundary),
not its scenario state machine. It neither advances that queue nor changes case
IDs, assertions, provider qualification or product behavior.

## Execution

`tools/fixture` is the migration-plan launcher, not a fixture build/sync command.
It constructs `PlanWorkflow` with GPT-6.1 Sol High and registered VM selection.
The shared driver owns task budgets, supervision, attachment/stop, evidence,
restart/reconciliation, namespace and per-task commit/push. It defaults to one
task. Future runtime operations extend maintained fixture and VM interfaces;
their proposed surfaces in the design are not implemented commands.

```sh
tools/fixture --check
tools/fixture --tasks 1
tools/fixture --tasks 0
tools/fixture --stop
```

These are alternatives, not a sequence to run during authoring. The existing
grant equivalent for checking is:

```sh
tools/execute-plan --plan 'docs/TestAutomation/Fixture-Execution-Plan.md' --check
```

Both entries share the master-path namespace. `--check` reads all unfinished
briefs without models, VM selection/operations or Git changes. Omitted `--vm`
uses the configured enabled queue at execution; narrowing selection never
waives a brief's named targets. Do not run nested plan launchers. New executable
grants join the next normal [setup refresh](../Approval-Tools.md#one-time-setup);
authoring needs no setup, rule refresh, product install, commit or push.

## Selection, reading and acceptance

Execute only the first unchecked active row and its brief through acceptance,
owned cleanup and shared Git close-out. Apply [AGENTS.md](../../AGENTS.md), the
[test documentation map](README.md), [execution/delegation](../Execution-Plans.md#execution-and-delegation)
and applicable [approval](../Approval-Tools.md),
[VM](../Mandates/VM-Mandate.MD), [storage](../Mandates/Test-Storage-Mandate.md)
and [UI](../Mandates/UI-Automation-Mandate.MD) owners. Read the selected design
sections and complete affected functions, callers, shared state and regressions.
The design is a future requirement, not an exception to current mandates.

F01 freezes finite placement/consumer inventory and public route names; F51
freezes schemas and transition contracts; F52 independently reviews that design.
Implementation tasks update each enduring
owner with their delivered boundary; preserve current rules until that boundary
exists. F29 owns a single producer's build slot/descendants before F02 builds;
F04 delivers six-slot retention with automatic oldest eligible cleanup, without
a fixture byte quota. F14 delivers the authenticated cache/session bridge.
F24/F30 protect original-schema recovery. F31 implements native rule/decision
validation, F32 process supervision, F50 finite activation witnesses and F33 full
legacy movable-set import. F15 composes guest contraction; F05/F06 qualify the
complete provisioning boundary. These independent mechanisms have separate tasks.
The [runner acceptance matrix](Fixture-Design.md#runner-acceptance-matrix) assigns
seven distinct envelopes to paired Ubuntu/Fedora tasks; a migrated row cannot
enable an unqualified branch. After the first paired preparation checks,
F11/F12 establish clean snapshots with ordinary new-schema dispatch disabled.
F34–F40 and F41–F47 repeat the seven real preparation envelopes on those clean
snapshots. F48/F49 publish target admission receipts only after their seven rows
pass and cleanup is proven; earlier fixture-bearing results cannot substitute.
F07/F08 then deliver live maintenance refresh. Queue order deliberately differs from ID order so real
fixture source edits cannot hit the old baseline freshness guard during live
refresh acceptance. Keep unsupported targets and unqualified profiles on their
existing route throughout migration.

Host checks use the lowest effective maintained selection. Each implementation
task owns its safety regressions and applicable live proof; no separate later
verification task excuses missing acceptance. Installed tasks qualify fixture
infrastructure only. Preparation bindings stop at fixture readiness/use and owned
cleanup before product actions/assertions; no customer journey or product
acceptance is added or credited. Use shared watch, leases,
guarded transport and recorded cleanup. Exercise fixture witnesses through owned
SSH; this plan requires no product UI or new provider qualification. Planned
selectors in briefs must be registered and listed before their first invocation.

Ordinary tasks target 15–30 minutes. F32/F50 have explicit 30–60 minute host
exceptions for one indivisible supervision/activation state machine. Installed
qualification rows have 30–60 minute exceptions for one target's complete
provisioning history or one runner envelope, including refusal, restoration and
cleanup. F48/F49 are finite 15–30 minute admission histories.
Split newly discovered independent work through the shared prerequisite route;
do not drop assertions or defer cleanup to meet an estimate. Missing grants,
ambiguous ownership and product behavior mismatches retain the selected task's
blocker and return condition under [failure handling](../../tests/README.md#handling-test-failures).

F01/F51/F52 verify the design's decided [cache ownership/session boundary](Fixture-Design.md#cache-ownership-and-execution-sessions),
[build-count policy](Fixture-Design.md#initial-working-set-and-producer-reservation),
[guest contraction](Fixture-Design.md#profile-contraction-and-activation-transaction),
[launch barrier](Fixture-Design.md#quiescence-and-launch-barrier) and
[legacy recovery matrix](Fixture-Design.md#legacy-recovery-compatibility) against
complete source. The native protocol uses attributed finite open/exec witnesses,
unique private probe executables and exact trust transitions; it supplies no
complete arbitrary product-policy acknowledgement. Original movable ownership
includes unrequested payloads and retained preparation-source copies. These
choices are frozen requirements with implementation and target qualification
still outstanding; authoring neither completes the design tasks nor supplies
runtime acceptance.

## Close-out

Preserve exact bundle/dependency identities, finite commands, expected/actual
results and cleanup through ordinary-plan evidence publication. Review resource
changes under [host parallelism](../../tests/README.md#host-test-parallelism-review).
Run `make build` only if final edits affect package/build inputs. Validate changed
Markdown with `tools/read-only links`; validate this queue with `--check` and
affected launcher/metadata checks. Only accepted execution checks a row, advances
this pointer and removes its temporary brief after its requirements have moved
to maintained owners. No other plan receives completion credit.
