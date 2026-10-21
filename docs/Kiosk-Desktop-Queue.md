# Kiosk full desktop prevention queue

The [master](Kiosk-Desktop-Plan.md) owns desktop-only scope, usability, threat
limits and both-target acceptance. Audit and close residual cleanup first;
require accepted baseline use at D01, then finish this plan before
`tools/kiosk-prompt-new`. Planning completes no task.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | D00 | [Audit the confinement replacement and cleanup boundary](Kiosk-Prompt-Tasks/D00-cleanup-audit.md) | Baseline | Verify the pinned v1.3 confinement lineage and map residual conflicting source and automation to their cleanup owners | 20–30 min |
| [ ] | D00a | [Close residual conflicting confinement source](Kiosk-Prompt-Tasks/D00a-source-cleanup.md) | D00 | Remove or verify absent residual conflicting source and direct package/lifecycle consumers while preserving main features | 20–30 min |
| [ ] | D00b | [Close obsolete confinement automation consumers](Kiosk-Prompt-Tasks/D00b-automation-cleanup.md) | D00a | Reconcile residual obsolete v1.4 fixtures, imports and registrations with retained behavioral outcomes and historical evidence | 20–30 min |
| [ ] | D00u | [Verify tolerant baseline use on Ubuntu](Kiosk-Prompt-Tasks/D00u-tolerant-use-ubuntu.md) | D00b | Ubuntu: Verify passwordless core use and the cleanup audit's finite benign/unknown configuration controls before new protection | 30–60 min; session exception: complete tolerant-use and restoration history |
| [ ] | D00f | [Verify tolerant baseline use on Fedora](Kiosk-Prompt-Tasks/D00f-tolerant-use-fedora.md) | D00u | Fedora: Verify passwordless core use and the cleanup audit's finite benign/unknown configuration controls before new protection | 30–60 min; session exception: complete tolerant-use and restoration history |
| [ ] | D01 | [Review full desktop entry routes](Kiosk-Prompt-Tasks/D01-desktop-review.md) | D00f | Verify the accepted baseline gate and map local graphical-session selection and request-session desktop escapes with permitted controls | 20–30 min |
| [ ] | D01r | [Review the named remote-desktop route](Kiosk-Prompt-Tasks/D01r-remote-review.md) | D01 | Map one supported provider's actual account/session path and usable ordinary-account positive without implementation | 20–30 min |
| [ ] | D02 | [Review the minimal desktop protection design](Kiosk-Prompt-Tasks/D02-desktop-design.md) | D01r | Independently review and allocate only the finite desktop barriers and directly affected controls | 20–30 min |
| [ ] | C07a | [Prevent local full desktop access](Kiosk-Prompt-Tasks/C07a-local-routes.md) | D02 | Protect reviewed local graphical-session selection at the actual admission boundary | 20–30 min |
| [ ] | C07au | [Verify normal kiosk use after C07a on Ubuntu](Kiosk-Prompt-Tasks/C07a-usability-ubuntu.md) | C07a | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C07af | [Verify normal kiosk use after C07a on Fedora](Kiosk-Prompt-Tasks/C07a-usability-fedora.md) | C07au | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C07s | [Prevent desktop launches from the request session](Kiosk-Prompt-Tasks/C07s-session-escapes.md) | C07af | Protect reviewed request-session actions that yield a full desktop with permitted form and approval controls | 20–30 min |
| [ ] | C07su | [Verify normal kiosk use after C07s on Ubuntu](Kiosk-Prompt-Tasks/C07s-usability-ubuntu.md) | C07s | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C07sf | [Verify normal kiosk use after C07s on Fedora](Kiosk-Prompt-Tasks/C07s-usability-fedora.md) | C07su | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C07 | [Protect the supported remote-desktop route](Kiosk-Prompt-Tasks/C07-login-routes.md) | C07sf | Implement the named remote-desktop barrier with ordinary-account positive coverage | 20–30 min |
| [ ] | C07u | [Verify normal kiosk use after C07 on Ubuntu](Kiosk-Prompt-Tasks/C07-usability-ubuntu.md) | C07 | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C07f | [Verify normal kiosk use after C07 on Fedora](Kiosk-Prompt-Tasks/C07-usability-fedora.md) | C07u | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | D03 | [Freeze desktop acceptance bindings](Kiosk-Prompt-Tasks/D03-desktop-acceptance-map.md) | C07f | Verify exact registered desktop histories, normal-use controls, qualification and both-target ownership | 20–30 min |
| [ ] | C11d | [Qualify local desktop prevention on Ubuntu](Kiosk-Prompt-Tasks/C11d-local-routes-ubuntu.md) | D03 | Ubuntu: Verify local full-desktop denial and complete usable request/core-effects controls | 30–60 min; session exception: complete desktop attempt, core-use and restoration history |
| [ ] | C11f | [Qualify the remote-desktop boundary on Ubuntu](Kiosk-Prompt-Tasks/C11f-remote-desktop-ubuntu.md) | C11d | Ubuntu: Verify named-provider kiosk desktop denial and permitted ordinary-account remote desktop | 20–30 min |
| [ ] | C12d | [Qualify local desktop prevention on Fedora](Kiosk-Prompt-Tasks/C12d-local-routes-fedora.md) | C11f | Fedora: Verify local full-desktop denial and complete usable request/core-effects controls | 30–60 min; session exception: complete desktop attempt, core-use and restoration history |
| [ ] | C12f | [Qualify the remote-desktop boundary on Fedora](Kiosk-Prompt-Tasks/C12f-remote-desktop-fedora.md) | C12d | Fedora: Verify named-provider kiosk desktop denial and permitted ordinary-account remote desktop | 20–30 min |
| [ ] | D04 | [Close desktop prevention evidence and documentation](Kiosk-Prompt-Tasks/D04-desktop-closeout.md) | C12f | Verify matching desktop product/automation/docs, both-target evidence and completed owned restoration | 20–30 min |

Order is authoritative; IDs are stable labels. C07a/C07s/C07 and C11d/f–C12d/f
carry their desktop assertions here. Standalone terminal/TTY assertions are
retained as C07t/C11t/C12t in the [remaining queue](Kiosk-Prompt-New-Queue.md),
which also owns SSH and other confinement work. Preserve case IDs, acceptance
targets and historical failures. Selectors remain planned until registered and
qualified. Missing independent work becomes a bounded prerequisite at its
selected consumer; host checks and `--check` supply no installed acceptance.
Apply the master's retained-run admission before executing this changed queue;
current-file validation does not adopt a saved scope or dependency change.
