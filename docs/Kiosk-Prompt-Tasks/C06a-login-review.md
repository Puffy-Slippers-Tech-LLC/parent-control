# C06a — Review remaining login routes

Acceptance: review

Required tasks: Baseline (external desktop D04 and C05u/C05f gates below).
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Before route work, verify D04 is accepted in the
[desktop queue](../Kiosk-Desktop-Queue.md), with matching desktop/core-use public
results on both targets and owned cleanup. Also verify C05u and C05f in the
[baseline queue](../Kiosk-Prompt-Queue.md), with retained matching-candidate
installed results, both targets and owned cleanup. Missing results keep C06a
unchecked: resume after the owning launcher accepts the missing gate. Never execute or
close desktop/baseline rows here. Finish any prior owner/Git/resource transaction before
starting new work. This review supplies no new-plan acceptance by inheritance.

Start from the rebuilt source and accepted desktop/baseline receipts. Inspect
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
