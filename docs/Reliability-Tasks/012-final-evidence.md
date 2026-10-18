# 012 — Reconcile final-candidate regression coverage

Acceptance: reconciliation
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Estimate: 30–90 minutes.

## Session boundary

Reconcile final-candidate evidence and rerun only invalidated acceptance.
012a supplies executable registration, unattended selection and resource
classification reconciliation. Session exception: the affected rerun set is
determined by actual final identities, and complete installed histories cannot
be shortened to fit a review estimate. Re-estimate and insert a bounded
prerequisite before new independent repair work; missing proof stays unfinished.

## Purpose and route

Required tasks: 001, 002, 003, 004, 005, 006a, 006b, 007a, 007b, 007, 008, 009, 010, 011, 012a.
Read the [master](../Reliability-Plan.md), actual completed queue evidence,
[test documentation ownership](../TestAutomation/README.md),
[coverage maintenance](../../tests/README.md#coverage-maintenance-workflow).
This task reconciles evidence; it cannot substitute a prose review for an
earlier task's required installed result. Its completion establishes the active
incident regressions only, not general product acceptance or release readiness.

## Work sequence

1. Record the candidate identities for this reconciliation and enumerate every
   active original/extracted condition using 012a's incident/owner/selector
   mappings. Keep scheduling exclusions outside the required rerun set.
2. Locate retained proof or verified cumulative bundles for each condition and
   target. Compare package, test-source, baseline, scope and cleanup identities;
   classify evidence as applicable, invalidated or missing before scheduling runs.
3. Reuse applicable proof and execute only the affected host checks and complete
   installed histories. Insert a bounded prerequisite for independent new repair
   work; do not absorb an unbounded fix set into this final review.
4. Recheck proof retention and applicability after the last edit/run, update the
   existing qualified-scope owners and close only when every required result and
   cleanup is satisfied. Keep concrete gaps unfinished.

## Deliverable and validation

Consume 012a's maintained owner/selector mappings and repeat commands, rechecking
applicability to final inputs. Include every active extracted row as well as
original IDs; parent-row summaries alone cannot establish their results. Check
that each condition maps to actual retained proof in its proper layer.

Compare final product, test and baseline identities against each task's accepted
receipts on both targets, using the master's verified cumulative bundles when
original reports have rotated. Require actual retained proof, not queue prose
alone. Reuse unchanged exact evidence; run affected host
checks and complete installed histories invalidated by later edits. Retain their
new receipts and cleanup. Do not combine earlier phases into a fictitious final
candidate pass. A missing required history or incapable VM leaves this task
unchecked with its concrete return condition.

Run the maintained inventory/documentation/traceability checks applicable to the
actual edits, regenerate coverage where needed and check all changed Markdown
links. Confirm any product/build changes received `make build` after their final
edit. No blanket `host`/`all` rerun is required solely for reconciliation.

Update actual qualified limitations and selector bindings in their existing
owners. Preserve core-installation 003/004 and all customer E2E statuses and
next-task pointers; record their remaining work by links rather than importing
their queues or claiming their completion. Keep first failures and useful
historical evidence in existing runner allocations. Close only this final row
when every required result and cleanup is satisfied, then set the master's
pointer to `Next task: none.`.
