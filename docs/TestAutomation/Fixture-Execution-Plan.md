# Host-owned fixture execution plan

Task queue: [Ordered task queue](Fixture-Task-Queue.md).
Next task: **F11 — [Decouple Ubuntu snapshots from fixture payloads](Fixture-Tasks/F11-ubuntu-snapshots.md)**.

## Outcome and status

Build fixtures on the host and push only a test's required runtime files over
owned SSH. Verify them before input. Fixture-only edits must not rebuild product
packages or invalidate environment/app snapshots. Support explicit refresh in an
idle owned maintenance guest without reboot.

The [target design](Fixture-Design.md) now reuses existing execution-owned inputs,
retention and VM recovery. It replaces the earlier shared cache, cross-owner pin,
guest rollback, process-supervisor and native acknowledgement proposals.
F01/F51/F52 remain completed historical inventory/design reviews. F29 delivered
the existing single-producer lifetime and safety checks. F02 delivered frozen
host construction, complete runtime manifests and independent verification for
both target ABIs. F03 delivered verified execution-owned publication/reuse,
immutable selections, authenticated read-only handoff and inherited retention
ownership. F15 delivered the host-validated, fail-closed SSH provisioning boundary.
F11 and later tasks remain unimplemented; runner dispatch stays unavailable until
target qualification. Host inputs and host checks supply no installed acceptance.

## Launcher

`tools/fixture` is a 16-line adapter to the shared ordinary-plan driver. Keep its
GPT-6.1 Sol High default, registered VM selection, ownership, task budgets,
attachment/stop, evidence and per-task Git close-out.

```sh
tools/fixture --check
tools/fixture --tasks 1
tools/fixture --stop
```

These are alternatives, not an authoring sequence. `--check` validates all active
briefs without models, VM operations or Git changes. Omitted execution `--vm`
uses the configured enabled queue; each brief still requires all named targets.
Do not run nested plan launchers or edit saved checkpoints to adopt this revision.
An older interrupted execution must use the shared
[reconciliation contract](../Execution-Plans.md#common-launcher-interface).

## Execution and acceptance

Follow [AGENTS.md](../../AGENTS.md), the [documentation map](README.md), and
[ordinary execution/delegation](../Execution-Plans.md#execution-and-delegation).
Read the selected brief, relevant design section and complete affected call chains.
Current [approval](../Approval-Tools.md),
[VM](../Mandates/VM-Mandate.MD) and
[storage](../Mandates/Test-Storage-Mandate.md) rules apply until their delivered
owners change. This plan needs no product UI or new provider qualification.

F02/F03 deliver verified execution-owned host inputs. F15 provides one fail-closed
SSH provisioner. F11/F12 establish clean target snapshots; F05/F06 qualify
provisioning there. The seven real runner envelopes then migrate once per target.
Keep unqualified branches unavailable on clean captures. F07/F08 qualify idle
same-boot maintenance refresh, and F13 reviews the complete result.

Execute only the first unchecked row through its complete acceptance and owned
cleanup. Ordinary host tasks target 15–30 minutes; installed rows allow 30–60
minutes for one target's indivisible preparation history. Split newly discovered
independent work before its consumer through the shared prerequisite contract.
Preserve scenario inputs/order/assertions; preparation checks stop before product
or worker input and supply no customer acceptance.

## Close-out

Publish exact inputs, command/results and cleanup through ordinary-plan evidence.
Update the operational owner only for delivered behavior. Review resource changes
under [host parallelism](../../tests/README.md#host-test-parallelism-review).
Check changed Markdown with `tools/read-only links`, this plan with `--check`
and affected metadata/launcher regressions. Run `make build` after edits affecting
package/build inputs; authoring this plan alone needs no build or VM.
Only accepted execution checks a row, advances the pointer and removes its brief.
The separate [E2E plan](E2E-Execution-Plan.md) remains unchanged.
