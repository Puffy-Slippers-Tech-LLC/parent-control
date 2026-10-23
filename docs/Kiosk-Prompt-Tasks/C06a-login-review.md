# C06a — Review remaining login routes

Acceptance: review

Required tasks: Baseline (external desktop D04 and C05u/C05f gates below).
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Before route work, require D04 complete in the
[desktop queue](../Kiosk-Desktop-Queue.md) and C05u/C05f complete in the
[baseline queue](../Kiosk-Prompt-Queue.md). Trust completed rows without inspecting
old reports. An unfinished prerequisite keeps C06a unchecked until its owning
launcher completes it. Never execute or close desktop/baseline rows here.
Finish any prior owner/Git/resource transaction before starting new work.
This review supplies no new-plan acceptance by inheritance.

Start from the current source and completed prerequisites. Inspect
standalone terminal/TTY paths, non-desktop shortcuts and SSH, including whether
each invokes the expected PAM stack. Full graphical desktop/session selection
and named remote-desktop work remain solely with the desktop plan. Record any
new desktop gap or invalidated evidence under that owner's return condition.

For each route record actual child access, deliberate action, prohibited result,
smallest enforcement owner, normal-use positive, negative and restoration.
Keep ordinary-account authentication/remote access and kiosk passwordless entry
working. A disabled or absent remote service cannot prove blocked kiosk access.

Write this finite map in the confinement design owner for C07t/C07b.
Record already effective defenses without inventing extra code work. Unknown
configuration alone is no threat, and no arbitrary-kiosk-execution premise is
allowed. This source review grants no installed acceptance; C06 reviews the
combined protection design independently.
