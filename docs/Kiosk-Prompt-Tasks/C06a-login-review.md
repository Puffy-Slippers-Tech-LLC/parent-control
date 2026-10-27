# C06a — Review remaining login routes

Acceptance: review

Required tasks: Baseline (C05u/C05f gates below).
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use the completed C05u/C05f
[baseline handoff](../TestAutomation/E2E-Building-Blocks.md#c05f-fedora-baseline-acceptance)
without inspecting old reports. Finish prior owner/Git/resource transactions
before new work. This review supplies no acceptance by inheritance.

Inspect standalone terminal/TTY paths, non-desktop shortcuts and SSH, including
whether each invokes the expected PAM stack. Preserve the
[local desktop boundary](../SystemDesign/Kiosk-Confinement.md#local-desktop-boundary).
Remote-desktop testing is excluded. Record any newly exposed desktop gap in
the design owner and include affected checks with the concrete change.

For each route record actual child access, deliberate action, prohibited result,
smallest enforcement owner, normal-use positive, negative and restoration.
Keep ordinary-account authentication/SSH access and kiosk passwordless entry
working. A disabled or absent SSH service cannot prove blocked kiosk access.

Write this finite map in the confinement design owner for C07t/C07b.
Record already effective defenses without inventing extra code work. Unknown
configuration alone is no threat, and no arbitrary-kiosk-execution premise is
allowed. This source review grants no installed acceptance; C06 reviews the
combined protection design independently.
