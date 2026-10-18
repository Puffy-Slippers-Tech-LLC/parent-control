# 011 — Repeated retained-session recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 003a, 004.
Estimate: 45–75 minutes.
Session exception: the second exhaustion/approval/return must reuse the first
cycle's real session and history; resetting would remove the accumulated state.
Bound each target's history to 12 minutes, preserving existing operation deadlines.

## Purpose and route

Close the accumulated-state gap behind `5b15f17d` and `f0e4dc77`: a successful
first recovery must not leave stale admission authority, accounting state or
callbacks that break the next one. Compose two repetitions of the qualified
retained-session recovery from 004, using 003a's daily-accounting observations.

Read the [master](../Reliability-Plan.md), complete canonical accounting,
retained-work, approval/credential and cleanup helpers, and
[shared support](../../tests/support/README.md). Reuse those operations; cases
own only finite data, order and assertions. Synthetic load/workload qualification,
overlay variants, package transactions and diagnostic-export journeys are not
part of this history. Existing long-routine/suspend cases keep their own scope.

Planned qualification (unimplemented): `check_e2e_repeated_reliability_history`.

## Finite history and expected results

Use Riley as the exercised child and Jordan as the independent retained-work
control, keeping their recognizable work and saved policies in one attempt.
Publicly configure Riley's two-minute daily-only profile with observed zero
initial grant and enough starting daily balance. Jordan's public allowance must
cover the bounded history; its balances follow its own observed real activity.

Run exactly two Riley cycles: use the current entitlement to natural exhaustion,
observe native lock/zero-time denial, obtain one real kiosk approval of 120
additional seconds, then submit the child's credential once to the freshly
verified native challenge and observe the original usable desktop/work.
Record the actual original grant deadline. Cycle two must exhaust cycle one's
grant before its new approval; a second credential must not rescue either
return. No private usage/clock edits or state reset may manufacture exhaustion.

Observe accounting, independent Jordan policy/work and owned resource state
after each cycle, before another transition can conceal a failure. No unearned
time, premature lock while usable time remains, stale authority reuse or
additional child/report callbacks may accumulate. Compare equivalent checkpoints
with the same recorded timer/signal/process/unit/mount baseline. Do not restore
snapshots, clear usage or reset policies between cycles.

## Work sequence

1. Verify qualified operations, native session identities, public profiles,
   starting margins, retained work and owned resource baseline.
2. Finish cycle one through natural exhaustion, approval and one authenticated
   usable return; record every independent balance/work/resource result.
3. Preserve that session and wait through its actual grant deadline. Complete
   cycle two's exhaustion, approval and single authenticated return; compare the
   same results before cleanup.
4. Retain first failures and complete owned cleanup. A successful later return
   cannot turn a failed intermediate assertion into a pass.

## Validation and close-out

Run affected host composition, accounting, authority and cleanup guards, then
the complete two-cycle history on both targets. Add no new stress harness.
Repair demonstrated leaks/races/accounting defects and rerun the complete
affected history after final edits. Retain intermediate results, candidate
identities and cleanup; build as required and register once in the existing
qualification owner. Close only 011.
