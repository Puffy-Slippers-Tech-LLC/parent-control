# 006a — Implement owned immutable-view primitives

Acceptance: host

Read the [master](../Kiosk-Prompt.md), the [material/pin design and finite witnesses](../SystemDesign/Kiosk-Confinement.md#planned-retained-material-and-immutable-pins),
[005's admission proof](../SystemDesign/Kiosk-Confinement.md#planned-retained-view-admission-proof) and complete affected
source/pin/native callers and shared state. Implement only its selected immutable
source-storage/identity/lifetime primitives in existing owners.

Prove original pinned material survives host unlink/replacement and native
staging detach as designed. Refuse foreign/replaced objects, wrong ownership,
ambiguous source identity and interrupted publication; retain existing limits,
labels and identity-owned recovery. Keep current admission closed until the
later composition is complete; no fallback to mutable host sources.

Use independent private/native source and publication witnesses, including
failure cleanup. Review every changed resource inventory, run the lowest affected
maintained host selectors and make build after final packaged edits. Record
exact results/remaining integration and finish owned cleanup. 006b owns selection
and 006 owns native admission; do not claim retained-session installed acceptance.
