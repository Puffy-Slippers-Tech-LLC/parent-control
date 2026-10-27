# C06a — Review remaining login routes

Acceptance: review

Required tasks: Baseline (external desktop D04 and C05u/C05f gates below).
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Before route work, require D04 complete in the
[desktop queue](../Kiosk-Desktop-Queue.md) and use the completed C05u/C05f
[baseline handoff](../TestAutomation/E2E-Building-Blocks.md#c05f-fedora-baseline-acceptance).
Trust completed prerequisites without inspecting old reports. An unfinished desktop
prerequisite keeps C06a unchecked until its owning launcher completes it.
Never execute or close desktop rows here.
Finish any prior owner/Git/resource transaction before starting new work.
This review supplies no new-plan acceptance by inheritance.
The [D04 desktop handoff](../SystemDesign/Kiosk-Confinement.md#d04-desktop-close-out-and-remaining-plan-handoff)
records both-target local acceptance and completed restoration, with no current
desktop blocker; preserve its finite scope and return condition.

Start from the current source and completed prerequisites. Inspect
standalone terminal/TTY paths, non-desktop shortcuts and SSH, including whether
each invokes the expected PAM stack. Local full graphical desktop/session selection
remains solely with the desktop plan. Remote-desktop testing is excluded from
both plans. Record any
new desktop gap or invalidated evidence under that owner's return condition.

For each route record actual child access, deliberate action, prohibited result,
smallest enforcement owner, normal-use positive, negative and restoration.
Keep ordinary-account authentication/SSH access and kiosk passwordless entry
working. A disabled or absent SSH service cannot prove blocked kiosk access.

Write this finite map in the confinement design owner for C07t/C07b.
Record already effective defenses without inventing extra code work. Unknown
configuration alone is no threat, and no arbitrary-kiosk-execution premise is
allowed. This source review grants no installed acceptance; C06 reviews the
combined protection design independently.
