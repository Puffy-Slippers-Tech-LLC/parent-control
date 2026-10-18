# 011a — Bounded guest workload ownership

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 008, 010.
Estimate: 45–75 minutes.
Session exception: native resource admission, independent cap observation and
interruption/cleanup must qualify on both targets before the loaded composition.

## Deliverable and route

Supply the reusable resource operation assumed by 011. Read the
[shared support map](../../tests/support/README.md), installed worker/process
ownership code, [VM baseline lifetime](../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline)
and [storage contract](../Mandates/Test-Storage-Mandate.md). Locate a maintained
interface before extending one; no qualified binding is claimed by this plan.
Planned qualification (unimplemented): `check_e2e_bounded_guest_workload`.

Admit one guest-owned scope for at most 45 seconds: one CPU worker capped at 25%
of one virtual CPU, one writer producing one file of at most 64 MiB in
attempt-owned scratch, a total 128 MiB memory limit and at most four tasks.
Return exact recorded scope/process identities and immutable cap observations
for the later consumer. Reusable worker/dependency inputs belong in baseline
preparation; attempts verify them and own their scratch. Extend shared mechanics,
never a bespoke stress process inside 011 or a second allocation/cleanup system.

Qualify normal completion and interruption after admission. Independently read
native limits and file bounds, verify only owned workload identities are stopped
and reaped, and compare quiescent process/unit/scratch state. Reject missing or
ambiguous ownership, unavailable caps and oversized inputs before load. No host
stress, global disk fill, unbounded allocation or global process-name signals.

## Work sequence

1. Locate or extend the supported shared scope interface. Bind admission,
   immutable cap observations, exact identities and cleanup to the existing
   allocator; declare reusable inputs in baseline preparation.
2. Verify deterministic admission/input/timeout/ownership guards at host scope,
   including refusal before load when required limits or identity are unavailable.
3. Qualify normal completion on each target, independently observing the declared
   CPU, memory, task and file bounds and the quiescent resource result.
4. In a fresh finite branch, interrupt after admission. Prove only recorded owned
   identities stop/reap and scratch/unit state returns to its recorded baseline.
5. Retain both branches' cap and cleanup receipts and register the shared callable
   for 011. Both outcomes are required to qualify this one workload operation.

## Acceptance and close-out

Run host admission/input/timeout/ownership/cleanup guards and applicable resource
inventory reviews, then both finite native branches on both targets. Preserve
cap receipts, exact identities, outcomes and cleanup. Missing supported native
limits are a concrete blocker, never an uncapped passing fallback. Repair
mechanical defects within the master's bounded-support route, build if required
and register the qualified callable in its existing owner. Close only 011a; the
three-cycle product result still requires 011.
