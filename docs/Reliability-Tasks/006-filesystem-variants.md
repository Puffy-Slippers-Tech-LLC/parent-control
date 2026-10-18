# 006 — Confinement with heterogeneous filesystem inputs

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 30–60 minutes.

## Session boundary

Deliver one pinned alias/target mismatch, exact restoration and native recovery.
006a supplies unrelated writable-sibling masking/replacement; 006b supplies
required-ancestor refusal. Session exception: the refusal/restoration/reentry
history and its ordinary-user control must complete on both targets.

## Purpose and route

Required tasks: 005, 006a, 006b.
Read the [master](../Reliability-Plan.md),
[directory-view contract](../SystemDesign/Kiosk-Confinement.md#native-execution-and-executable-identity),
`tools/kiosk_confinement.py`, native binding/preparation callers and the complete
relevant `system_kiosk_confinement.py` functions. Extend those canonical
environment variants and existing host directory/trust/alias tests.

Planned selector (unimplemented): `test_kiosk_directory_environment_variants`,
area `enforcement`, narrowed to the pinned-alias branch. 006a/006b register
their distinct conditions separately. Reuse existing assertions rather than
duplicate the full confinement matrix. Attempt-owned path mutations must have recorded
identities; reusable fixtures belong in baseline preparation.

## Finite variants and expected results

Use one required input whose alias/target chain no longer matches its pinned
identity. Preparation refuses before publishing untrusted execution. Keep the
existing legitimate trusted-package-change control: package replacement is not
automatically an unsafe alias. Restore only the exact owned mutation and
require normal native recovery. No saved VM state from 006a/006b is a fixture.

Use inert canaries, never an unbounded scan or arbitrary third-party installer.
Preserve required native binds and strict group/world-write rules, including
root-group inputs. Verify admission, enforcing execution and isolation rather
than accepting a generated manifest or policy string as native proof.

## Validation and close-out

Run affected host trust/layout/refusal and fixture-cleanup checks, then the
installed alias refusal and restored-input recovery on both targets. Record
the actual variant, kernel/security mode, private-view witness, positive
ordinary-user control and cleanup. Repair generic root causes in shared code;
isolate only demonstrated distro differences. Build after product edits and
update the existing confinement/environment coverage owners.
