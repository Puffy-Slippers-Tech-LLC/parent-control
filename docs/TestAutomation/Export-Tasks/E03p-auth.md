# E03p-auth — Authenticate sealed producer handoffs

Acceptance: host
Requires: E02

## Status and reading route

Completed 2026-10-21 under the [master](../Export-Execution-Plan.md).
This brief remains because the parent consumer's frozen insertion and navigation
still reference it. Enduring delivered rules are in
[sealed producer handoffs](../../../tests/README.md#sealed-producer-handoffs).
The [parent consumer](E03-capture.md) retains every original assertion and its
close-out obligation after this allocation passes. Shared protocols remain owned
by the [design](../Export-Design.md), not by this brief.
Read [finalized authority](../Export-Design.md#finalized-capture-authority-and-durable-transitions), [wire records](../Export-Design.md#canonical-identities-and-wire-records), [producer map](../Export-Design.md#producer-and-consumer-inventory).
Follow the design maps to complete affected functions and necessary callers;
discover any additional source/test filename before reading it.

## Delivery

Read complete `tools/test_activity.py` producer ownership and session callers,
`tools/test_retention.py` owner/allocation state, `tools/test_storage.py`
allocation admission and `tools/onpc-test-artifacts` authenticated dispatch.
Deliver the opaque session handle bound to held descriptor, journal, run and
issued attempt; paths, environment, nonce or supplied UID cannot mint authority.
Register one disjoint sealed subowner/slot before copying and mark it readable
only after its independent finished-owner commit. Never inspect arbitrary active
parent payloads; preserve finished-owner and independent-publication guards.
Bind the exact finalized allowlist, original/sealed provenance, identities and
before/after digests. Root-required sources gain their private safety witness
before caller catalogue registration. Charge every slot to its parent budget.

## Finite acceptance

P03 covers required/sealing/sealed states: authentic finished handoff succeeds;
missing, pending, foreign, replaced or active registrations and mutated files refuse.
Exercise missing dependencies, wrong attempt/target/request, replay and capacity
refusal without source release, leaked slots or changed prior proof.
Interruption/cancellation retains the same intent and exact resumable stage;
no new capture ID, extra retention allowance or diagnostic promotion.
Register planned finalize/capture selection authentication and helper capabilities
before use; E03p-capture owns publication, acknowledgement and release.

## Validation and close-out

P03 is registered in `tests/unit/test_evidence_capture.py`; the internal
`tools/evidence_capture.py` session/sealing/read-scope API and helper inspection
parsers are delivered. Capture export, acknowledgement and release remain gated
for E03p-capture.
Discover actual tests, then select the lowest effective maintained host checks
through tools/run-tests help/list; record exact selectors and explicit timeout
before invocation. Run applicable safety selections before changed protected
operations. Follow [test maintenance](../../../tests/README.md) and the
[storage mandate](../../Mandates/Test-Storage-Mandate.md).
Apply the [controller guard](../Export-Design.md#controller-compatibility-guard)
in this introducing task for every new/changed retained-decision dependency,
including actual-file-byte restart coverage before close-out.
Finish [host resource review](../../../tests/README.md#host-test-parallelism-review)
for applicable module/resource inventories; runtime fallback is not review.
Use private fixtures only, clean only their owned identities, preserve unrelated
work and retain exact commands/results/cleanup through shared publication.
Check changed documentation links and update existing owners for delivered rules.
Complete this row only after host acceptance and owned cleanup; the parent
consumer still owns inherited acceptance and final composition obligations.

## Accepted evidence and review

The twelve-module host selection used `tools/run-tests unit`, `--timeout 300s`
and `-q`: capture, bundle, identity, retention/storage safety, activity, artifacts,
plan evidence/recovery, execution-plan launcher, unit inventory and helper
installation checks. Its [retained report](../../../output/test-runs/host/reports/20261022T044236Z-5d23b57e/report.md)
records 1391 passes, including all 90 P03 cases and the new module's real-byte
controller restart histories. Two E03 freeze-insertion cases skipped because the
block was already active. The repaired fixture reconstructs only its private
pre-insertion queue; the exact function selector
`tests/unit/test_execution_plan_launcher.py::test_export_frozen_blocks_use_real_prerequisite_and_cleanup_guards`
then passed all 12 cases with the same timeout and `-q`
([renewal](../../../output/test-runs/host/reports/20261022T044606Z-05281222/report.md)).
All 1393 distinct selected cases therefore passed; the first aggregate's failed
status is retained rather than relabelled. No assertions or scope were dropped.

Independent Sol xHigh review found five issues: unpublished-input/transfer
retirement bypasses, source-path validation after readability, inner allocation
registration recovery, output descriptor ownership during cancellation and the
64-source-budget limit. All were corrected with focused regressions, and fresh
review approved with no remaining actionable findings. `make build` passed for
DEB and RPM after the final build-affecting edit; its command output is retained
by the controller. All agents finished; test processes and build scratch owners
closed normally. Only maintained retained reports/build outputs remain. Host
identity simulations supplied no installed-product or VM acceptance.

The design's two expired E01b report destinations were repaired without changing
their labels or claims. The authenticated bundle reader verified both original
members (`20261022T035225Z-30f98d1c/report.md`, SHA-256
`7f39dce28f1985e1880bfb0cf2c6f00d9963058422d1fcafbe50f618876c6e93`,
and `20261022T035426Z-61e9715f/report.md`, SHA-256
`0513a2a6c54b716d490db05089cff75a3b39123ea4e8af39d64b4fa9ad0a0e2d`)
in the existing accepted bundle, whose digest matches its stable locator.
Their original 759/12 passes and accepted E01b result/cleanup remain intact;
this destination-only repair grants no new predecessor acceptance.

