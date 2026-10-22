# Host-owned fixture execution plan

Task queue: [Ordered task queue](Fixture-Task-Queue.md).
Next task: **F17 — [Integrate Fedora installed-system preparation](Fixture-Tasks/F17-fedora-installed-system.md)**.

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
F11 delivered Ubuntu's fixture-independent baseline/app captures, exact legacy
retirement, standalone app reuse and dependency/product invalidation proof.
F53 delivered package-owned native policy bootstrap and a separate fresh-boot
readiness step. Restored Ubuntu baseline/app captures passed active-service,
read-only database, vendor preservation and complete fixture-absence checks.
F05 qualified Ubuntu's shared provisioning on clean baseline/app attempts,
including exact activation, runtime use, no-write repeats and failure recovery.
F12 delivered Fedora's fixture-independent baseline/app captures, authenticated
native policy and compiler-backup retirement, enforcing SELinux, standalone
reuse/stop and renewed Ubuntu snapshot acceptance. Owned restoration and cleanup
passed on both targets.
F06 qualified Fedora's shared provisioning with enforcing SELinux, exact finite
admissions, trusted/untrusted runtime outcomes, no-write repeats and real staged
lost-reply recovery. The shared four-attempt history also renewed Ubuntu proof;
both targets restored their baselines and ended off after owned cleanup.
F09 delivered Ubuntu's product-free system preparation and the three Parent
bootstrap aliases. The actual system attempt passed two clean restored boots:
hard-only independent readback/runtime use, selection refusals, no-write repeats,
unchanged selection after producer-source edits and prior-generation refusal,
without installation input or phase execution. Package-only provenance retains
finite scenario comparison inputs. Independent review findings were resolved;
baseline, producer, transport and retention cleanup passed, with Ubuntu off.
F10 delivered the same product-free system boundary and Parent bootstrap aliases
on Fedora 44. Two restored Fedora boots passed independent hard-only byte/runtime
checks, enforcing SELinux and exact native policy/labels, input refusals, fresh
readiness and immutable selection after actual producer-source edits. The source-edit
proof helper now supports both targets; its Ubuntu-only guard and a new test's
incorrect error expectation were repaired while preserving behavior assertions.
Ubuntu product-free preparation proof was renewed. Independent Sol High review found
no remaining issues; host composition/provenance/ownership checks and watched
owned cleanup passed, with both VMs independently off.
F16 delivered Ubuntu's installed-system preparation through explicit offline app
restores and the shared hard-only provisioning boundary. Two restored boots
passed independent byte/runtime checks as Riley, input refusals, fresh readiness,
no-write repeats and unchanged selection after actual producer-source edits,
without system input or phase execution. Package-only snapshot provenance and
the restored-boot startup race were repaired without changing native assertions.
Affected host checks passed; one worker deadline's unfinished checks passed in a
focused rerun. Independent Sol High review found no remaining issues after a
diagnostic-storage finding was resolved. Watched baseline, producer, credential,
staging, input-retention and transport cleanup passed; Ubuntu independently ended
off. The [installed report](../../output/test-runs/host/reports/20261022T174825Z-4752b1f0/report.md)
records the exact selector and retained evidence. This supplies no customer/E2E
acceptance.
Later tasks remain unimplemented;
other runner dispatch stays unavailable until target and envelope qualification. Host inputs and
host checks supply no installed acceptance.

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
