# 006b — Protect consumed inputs from child writes

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: none (Baseline).
Estimate: 30–60 minutes.
Coordination: the [kiosk resilience plan](../Kiosk-Resilience-Plan.md#scope-reconciliation)
owns the compatibility redesign's input protection and recovery qualification.
Before execution, require R01's accepted mapping from legacy refusal assertions
to the [prospective boundary](../SystemDesign/Kiosk-Confinement.md#prospective-compatibility-first-target);
if absent, keep this row unchecked. Review its
[historical baseline](../Kiosk-Resilience-Plan.md#implementation-baseline);
reuse only exact matching scope/candidate/target evidence. Neither plan closes
the other's row, and overlapping work must not run concurrently.
Session exception: positive/negative input controls, exact restoration and usable entry
must complete on each target in one owned fault/recovery history.

## Deliverable and route

Keep one adjacent safety control for `83d502b3`: tolerating an unrelated writable
sibling must not admit child-controlled code through a consumed path. No package
transaction or retained-child approval journey is needed. Read the
[prospective boundary](../SystemDesign/Kiosk-Confinement.md#prospective-compatibility-first-target),
R01's mapping, complete relevant consumed-input/admission callers and
`system_kiosk_confinement.py` functions. Existing case 291,
`test_kiosk_required_ancestor_refusal`, area `enforcement`, has legacy mode-bit
and refusal assertions. Adapt or reuse it only under R01's mapping; neither its
name nor a historical refusal establishes the new safety condition.

Choose one consumed startup/code path and record its identity, original metadata
and actual write authority. First require usable entry with a group-writable
ancestor writable only by trusted administrators, including the root-group
case; verify relevant group membership and ACLs. Then make one recorded owned
input writable by the non-administrator child and prove the ordinary startup
would consume it without the selected protection. Use an inert fixture; do not
assume arbitrary code execution inside the kiosk.

The kiosk must exclude the unsafe input, use a safe replacement or block its
affected route before it executes. Preserve usable entry wherever that suffices.
Whole-entry rejection is acceptable only for an essential unrecoverable boundary
identified in R01's ledger, with its exact trigger, failed recovery alternatives
and actionable diagnostic; it supplies no availability credit. Restore the exact
mutation and require passwordless usable entry and effective confinement.
Preserve ordinary-user contents/access throughout.

## Work sequence

1. Verify the consumed path, identity, original metadata and ordinary-user
   controls; establish the trusted-administrator-only group-write positive.
2. Apply the recorded child-write mutation. Independently observe exclusion or
   safe recovery, or the narrowly justified essential-boundary refusal, before
   restoration can hide the result. Record actual reachability and write authority.
3. Restore original state exactly, then prove usable native entry and enforcing
   execution with the chosen lifecycle.
4. Recheck ordinary-user contents/access and complete owned cleanup.

## Acceptance and close-out

Run affected host consumed-input and mutation-cleanup checks, then the complete
positive/negative/restoration history on both targets. Use inert finite fixtures,
recorded identities and maintained restoration; reusable inputs belong in
baseline preparation. Retain protection/recovery results, any justified refusal
stage, kernel/security mode, legitimate-use and ordinary-user controls plus
cleanup receipts. Repair demonstrated shared causes, build as required and update
existing confinement owners. Close
only 006b. General pinned-alias mismatch qualification stays with the existing
confinement owner and is excluded from this plan.
