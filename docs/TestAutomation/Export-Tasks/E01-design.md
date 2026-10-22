# E01 — Audit history, producers and retirement paths

Acceptance: review
Requires: Baseline

## Purpose and delivery

Deliver the finite source/history inventory for the
[master](../Export-Execution-Plan.md) and
[target design](../Export-Design.md#investigated-failures-and-remaining-exposure).
E01a owns protocol design; E01b owns independent review and the final freeze.
Together these rows retain the original E01 design obligations before runtime work.

Recheck each historical source against complete affected functions, callers and
current regressions. Read `tools/plan_evidence.py`, `plan_evidence_recovery.py`,
`evidence_bundle.py`, `test_retention.py`, `test_storage.py`, `onpc-test-artifacts`,
`document_checks.py`, `read-only`, `regression.Report`, `repair_evidence.py`,
`plan_launcher.py` and relevant callers. Include the added recovery-diagnostic,
oversized retirement, selector-checkpoint and partial capacity-failure histories.

Map every producer/consumer to a delivery row and exact retained or planned
regressions: ordinary exports, qualification bundles, aggregate/worker and
standalone reports, qualifications, shared/target recovery-diagnostic journals
through `qualification_storage.recovery_session()` and `vm_probe` callers, repair
snapshots, E2E collectors and ordinary/derived launcher proof. Include document
prose, queue cells, briefs and handoffs. Distinguish examples, operational paths
and separately retained media from evidence claims; preserve partial diagnostic
status and unavailable-history limits.

Inventory all retirement entry points under the design's
[lifetime contract](../Export-Design.md#lifetime-capacity-and-reuse), including
host/privileged startup recovery and explicit discard. Record caller, owner,
locks, dependency/acknowledgement gate, recovery action and delivery/test owner
for each. Inventory relevant controller validation/storage dependencies under the
[compatibility guard](../Export-Design.md#controller-compatibility-guard), including
currently unguarded shared files and planned extraction boundaries. This is a
finite source audit, not a live journal/filesystem sweep or a new runtime scanner.

Keep the maps in the existing target design and retained launcher artifacts;
identify concrete unknowns for E01a and assign every family before close-out.
Record which existing fixes/tests are reused so later rows do not reimplement them.

## Validation and close-out

Cross-check all historical rows, source entry points, delivery assignments and
regression names. Run plan `--check`, changed Markdown links and applicable
metadata checks. No runtime changes, product/VM work or live journal mutation.
Close only E01 through the master's shared cleanup and close-out; protocols and
independent freeze remain unchecked E01a/E01b obligations.
