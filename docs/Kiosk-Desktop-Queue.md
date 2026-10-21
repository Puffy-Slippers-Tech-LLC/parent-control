# Kiosk full desktop prevention queue

The [master](Kiosk-Desktop-Plan.md) owns desktop-only scope, usability, threat
limits and both-target acceptance. Finish the accepted baseline first, then
this plan before `tools/kiosk-prompt-new`. Planning completes no task.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | D01 | [Review full desktop entry routes](Kiosk-Prompt-Tasks/D01-desktop-review.md) | Baseline | Map actual local desktop/session escapes and one named supported remote-desktop route, with normal-use controls and the accepted baseline gate | 20–30 min |
| [ ] | D02 | [Review the minimal desktop protection design](Kiosk-Prompt-Tasks/D02-desktop-design.md) | D01 | Independently review and allocate only the finite desktop barriers and directly affected controls | 20–30 min |
| [ ] | C07a | [Prevent local full desktop access](Kiosk-Prompt-Tasks/C07a-local-routes.md) | D02 | Protect reviewed local graphical-session selection and desktop-enabling request-session escapes | 20–30 min |
| [ ] | C07 | [Protect the supported remote-desktop route](Kiosk-Prompt-Tasks/C07-login-routes.md) | C07a | Implement the named remote-desktop barrier with ordinary-account positive coverage | 20–30 min |
| [ ] | D03 | [Freeze desktop acceptance bindings](Kiosk-Prompt-Tasks/D03-desktop-acceptance-map.md) | C07 | Verify exact registered desktop histories, normal-use controls, qualification and both-target ownership | 20–30 min |
| [ ] | C11d | [Qualify local desktop prevention on Ubuntu](Kiosk-Prompt-Tasks/C11d-local-routes-ubuntu.md) | D03 | Ubuntu: Verify local full-desktop denial and complete usable request/core-effects controls | 30–60 min; session exception: complete desktop attempt, core-use and restoration history |
| [ ] | C11f | [Qualify the remote-desktop boundary on Ubuntu](Kiosk-Prompt-Tasks/C11f-remote-desktop-ubuntu.md) | C11d | Ubuntu: Verify named-provider kiosk desktop denial and permitted ordinary-account remote desktop | 20–30 min |
| [ ] | C12d | [Qualify local desktop prevention on Fedora](Kiosk-Prompt-Tasks/C12d-local-routes-fedora.md) | C11f | Fedora: Verify local full-desktop denial and complete usable request/core-effects controls | 30–60 min; session exception: complete desktop attempt, core-use and restoration history |
| [ ] | C12f | [Qualify the remote-desktop boundary on Fedora](Kiosk-Prompt-Tasks/C12f-remote-desktop-fedora.md) | C12d | Fedora: Verify named-provider kiosk desktop denial and permitted ordinary-account remote desktop | 20–30 min |
| [ ] | D04 | [Close desktop prevention evidence and documentation](Kiosk-Prompt-Tasks/D04-desktop-closeout.md) | C12f | Verify matching desktop product/automation/docs, both-target evidence and completed owned restoration | 20–30 min |

Order is authoritative; IDs are stable labels. C07a/C07 and C11d/f–C12d/f
carry their desktop assertions here. Standalone terminal/TTY assertions are
retained as C07t/C11t/C12t in the [remaining queue](Kiosk-Prompt-New-Queue.md),
which also owns SSH and other confinement work. Preserve case IDs, acceptance
targets and historical failures. Selectors remain planned until registered and
qualified. Missing independent work becomes a bounded prerequisite at its
selected consumer; host checks and `--check` supply no installed acceptance.
