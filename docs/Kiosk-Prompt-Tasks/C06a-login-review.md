# C06a — Review ordinary login and remote routes

Acceptance: review

Required tasks: C05f.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Start from the rebuilt source and both baseline receipts. Inspect actual
graphical session selection, terminal/TTY paths, SSH and the finite supported
remote-desktop provider, including whether each invokes the expected PAM stack.

For each route record actual child access, deliberate action, prohibited result,
smallest enforcement owner, normal-use positive, negative and restoration.
Keep ordinary-account authentication/remote access and kiosk passwordless entry
working. A disabled or absent remote service cannot prove blocked kiosk access.

Write this finite map in the confinement design owner for C07a/C07b/C07.
Record already effective defenses without inventing extra code work. Unknown
configuration alone is no threat, and no arbitrary-kiosk-execution premise is
allowed. This source review grants no installed acceptance; C06 reviews the
combined protection design independently.
