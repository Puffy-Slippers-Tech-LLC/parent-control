# 006b — Implement retained-material selection

Acceptance: host

Read the [master](../Kiosk-Prompt.md), the [material transition table and finite witnesses](../SystemDesign/Kiosk-Confinement.md#planned-retained-material-and-immutable-pins),
[005's composition proof](../SystemDesign/Kiosk-Confinement.md#planned-retained-view-admission-proof), 006a's
delivered primitives and complete affected prepare/generation/manager callers.

Implement required-material digest/source selection using the reviewed pins.
Cover finite ambient addition/removal/mode/owner/kind and disappearance versus
replacement transitions. Preserve strict config/policy/native/library/privilege
and consumed-runtime-root checks, manager identity and bounded diagnostics.
No digest-only bypass or reconstruction from mutable/vanished sources is allowed.

Add meaningful private host tests for every distinct selection/refusal branch,
unchanged required material, stale required material and interrupted publication.
Native attachment remains with 006; preserve the existing fail-closed route until
that composition is complete. New independent mechanisms need prerequisites.

Run affected maintained host selectors, review resource inventories and build
after final packaged edits. Retain original failures, candidate/results and
exact private restoration/cleanup. Close only preparation selection.
