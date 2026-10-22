# F15 — Compose transactional guest contraction

Acceptance: host
Requires: F33

## Purpose and scope

Compose transactional placement/removal under the
[contraction contract](../Fixture-Design.md#profile-contraction-and-activation-transaction).
Native rule rendering/witnesses, process supervision and legacy import are
prerequisites, not additional implementations inside this task. Runtime dispatch
remains gated until F05/F06 qualify the complete target boundary.

## Read and implement

Read the complete F31/F32/F50 native/process APIs and F33 import/removal API with
their shared fixture/guest-file callers. Preflight the old/new union, classify
additions/replacements/removals and preserve still-required shared runtime files.
Journal payload/rollback identities before mutations. Compose the verified
launch barrier (including staged added-content denies), explicit owned quiescence,
old-path trust retirement before removal or same-path replacement, atomic
placement/removal, canonical added-path deny proof, final new-set trust transition,
independent readback, barrier release and readiness receipt in one
recoverable state machine. Use F50's finite fixture proof, not a claim of complete
arbitrary native-policy acknowledgement. No second process scanner or native
updater is permitted.

## Finite validation and cleanup

Use private real-file and explicit native/process doubles for larger→smaller→
disjoint subsets, retained shared members, removed launchers/admissions and
foreign/modified-file refusal before mutation. Inject interruption before/after
each placement, removal, native transition and readiness commit. Assert uncertain
replies resume recorded phases, with unavailable readiness until complete, and
no repeated uncertain exec/signal. Reuse prerequisite race/identity tests and add
composition guards that prevent bypassing them. Cover absent canonical paths on
first provisioning/disjoint additions, plus interrupted old-path trust revocation
before replacement or unlink. Register exact safety selectors
and resource classifications. No live VM or host native policy is used. Update
delivered support owners and close through the
[master](../Fixture-Execution-Plan.md).
