# E01a — Design identity, capture and lifetime protocols

Acceptance: review
Requires: E01

## Purpose and delivery

Use E01's source/history maps to propose concrete interfaces and state transitions
in the existing [target design](../Export-Design.md), under the
[master](../Export-Execution-Plan.md). E01b independently reviews and freezes this
proposal before implementation. Read complete source for each inventoried
boundary, including callers/callees needed to resolve ownership or compatibility.

Specify versioned logical identities, exact-member link/selector syntax, manifests,
receipts and the finalized-capture request/acknowledgement. Define authenticated
owner/attempt binding, immutable finalized subset, cleanup completion, lock order,
durable transitions and interruption/cancellation recovery without weakening
finished-owner or independent-publication guards.

Specify bounded working/accepted lifetimes, authoritative consumer dependencies,
simultaneous old/staging/new/recovery accounting and a concrete segmentation or
compaction strategy only where needed. Cover every E01 retirement entry point,
including automatic oversized recovery after failed or unacknowledged capture.
Preserve existing disposable retirement, unknown-resource refusals and discard
authorization. Describe the supported capacity refusal/release/archive route;
do not introduce a new archive format or assume external hosting.

Specify selective journal inspection for the authenticated helper selection
path and two exact archived members while the same target has an unrelated active
producer. Freeze proportional severity and claim-protection precedence, legacy
schema/helper/checkpoint compatibility and dependency registration under the
[controller guard](../Export-Design.md#controller-compatibility-guard).
Bind each protocol to the design's
[required histories](../Export-Design.md#required-regression-histories) and its
delivery row. Proposed public commands remain unimplemented until registered.

## Validation and close-out

Walk normal, denied, corrupt, missing, capacity, cancellation and interrupted
transitions against current source and existing regressions. Identify independent
work and proposed task splits for E01b; preserve every original assertion. Check
plan structure, changed links and applicable metadata. No runtime changes,
models for execution fixtures, VM operations or live journal mutation. Follow
the master's cleanup and close-out; E01b's independent freeze remains required.
