# Kiosk full desktop prevention queue

The [master](Kiosk-Desktop-Plan.md) owns desktop-only scope, usability, threat
limits and both-target acceptance. Audit and close residual cleanup first;
require accepted baseline use at D01, then finish this plan before
`tools/kiosk-prompt-new`. Planning completes no task.

Every row applies the master's [simple implementation](Kiosk-Desktop-Plan.md#simple-implementation)
and [simple tests](Kiosk-Desktop-Plan.md#simple-tests): reuse existing mechanisms
and coverage, add only missing product checks and avoid duplicate runs for task labels.

D00a/C07a/C07s/C07 include both-target installed usability before completion and
automatic Git propagation. Their former later usability rows are folded into
these tasks, not marked done. Keep one small fix per product task; prepare missing
automation separately before editing. Use the master's bounded confinement check,
not general product acceptance. Ordinary tasks take 20–30 minutes; the named
30–60 minute exceptions keep a small fix and its indivisible checks together.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | D00 | Audit the confinement replacement and cleanup boundary | Baseline | Verify the pinned v1.3 confinement lineage and map residual conflicting source and automation to their cleanup owners | Reviewed lineage, admission residuals and finite gate prerequisites in the design owner; obsolete automation map empty; links and both metadata routes passed |
| [x] | D00a1 | Qualify the short confinement usability check | D00 | Compose and qualify the bounded public entry, rejection, Cancel, approval and reentry history from existing shared operations on both targets | Both-target complete history passed; public restoration and runner cleanup passed; registered binding in building blocks |
| [x] | D00a2q | Qualify the graphical service-dispatch variation | D00a1 | Qualify one real graphical service variation and its selected-session observations and owned restoration on both targets for D00a2; no product admission changes or consumer acceptance credit | Both-target real service refusal, command resolution, exact restoration, normal entry and cleanup passed; positive execution remains unqualified |
| [x] | D00a2r | Qualify the reached service-route control | D00a1, D00a2q | Qualify one actual child-invoked prohibited service route, its distinguishing account-refusal witness, ordinary-account positive and owned restoration on both targets before D00a2; no product changes or consumer acceptance credit | Both-target real child su-l native refusal, ordinary positive, passwordless station entry/form/Cancel/return and owned cleanup passed; no product changes |
| [x] | D00a2 | Remove service-name admission rejection | D00a1, D00a2q, D00a2r | Repair the service-dispatch boundary without treating unfamiliar graphical service names as attacks; pass both-target usability and directly affected route controls | Both-target graphical execution, child su-l refusal/ordinary positive, complete short usability and installed 268 passed; Astra review, 216 host checks, DEB/RPM builds and owned cleanup passed |
| [ ] | D00a3 | [Remove saved-routing admission dependence](Kiosk-Prompt-Tasks/D00a3-routing-admission.md) | D00a1, D00a2 | Repair the routing-discovery admission boundary for stale or unavailable saved preferences; pass both-target usability and affected recovery controls | 30–60 min; session exception: one admission fix, review/build and both-target usability |
| [ ] | D00a | [Close residual conflicting confinement source](Kiosk-Prompt-Tasks/D00a-source-cleanup.md) | D00, D00a1, D00a2, D00a3 | Resolve one residual confinement issue and require both-target tolerant kiosk use before completion | 30–60 min; session exception: small confinement fix, review/build and both-target usability |
| [ ] | D00b | [Close obsolete confinement automation consumers](Kiosk-Prompt-Tasks/D00b-automation-cleanup.md) | D00a | Reconcile residual obsolete v1.4 fixtures, imports and registrations with retained behavioral outcomes and historical evidence | 20–30 min |
| [ ] | D01 | [Review full desktop entry routes](Kiosk-Prompt-Tasks/D01-desktop-review.md) | D00b | Verify accepted cleanup/baseline use and map finite local desktop attacks with permitted controls | 20–30 min |
| [ ] | D01r | [Review the named remote-desktop route](Kiosk-Prompt-Tasks/D01r-remote-review.md) | D01 | Map one supported provider's actual account/session path and usable ordinary-account positive without implementation | 20–30 min |
| [ ] | D02 | [Review the minimal desktop protection design](Kiosk-Prompt-Tasks/D02-desktop-design.md) | D01r | Independently review and allocate only the finite desktop barriers and directly affected controls | 20–30 min |
| [ ] | C07a | [Prevent local full desktop access](Kiosk-Prompt-Tasks/C07a-local-routes.md) | D02 | Add one justified graphical-session barrier and pass both-target kiosk usability before completion | 30–60 min; session exception: small confinement fix, review/build and both-target usability |
| [ ] | C07s | [Prevent desktop launches from the request session](Kiosk-Prompt-Tasks/C07s-session-escapes.md) | C07a | Close one reviewed desktop-launch boundary and pass both-target kiosk usability before completion | 30–60 min; session exception: small confinement fix, review/build and both-target usability |
| [ ] | C07 | [Protect the supported remote-desktop route](Kiosk-Prompt-Tasks/C07-login-routes.md) | C07s | Add the named provider's narrow barrier and pass both-target kiosk usability before completion | 30–60 min; session exception: small confinement fix, review/build and both-target usability |
| [ ] | D03 | [Freeze desktop acceptance bindings](Kiosk-Prompt-Tasks/D03-desktop-acceptance-map.md) | C07 | Audit exact registered desktop histories and prior both-target usability; no deferred product gate | 20–30 min |
| [ ] | C11d | [Qualify local desktop prevention on Ubuntu](Kiosk-Prompt-Tasks/C11d-local-routes-ubuntu.md) | D03 | Ubuntu: Verify finite local desktop attacks, normal kiosk use and affected recovery controls | 30–60 min; session exception: one local route family, usability and restoration |
| [ ] | C11f | [Qualify the remote-desktop boundary on Ubuntu](Kiosk-Prompt-Tasks/C11f-remote-desktop-ubuntu.md) | C11d | Ubuntu: Verify named-provider kiosk desktop denial and permitted ordinary-account remote desktop | 20–30 min |
| [ ] | C12d | [Qualify local desktop prevention on Fedora](Kiosk-Prompt-Tasks/C12d-local-routes-fedora.md) | C11f | Fedora: Verify finite local desktop attacks, normal kiosk use and affected recovery controls | 30–60 min; session exception: one local route family, usability and restoration |
| [ ] | C12f | [Qualify the remote-desktop boundary on Fedora](Kiosk-Prompt-Tasks/C12f-remote-desktop-fedora.md) | C12d | Fedora: Verify named-provider kiosk desktop denial and permitted ordinary-account remote desktop | 20–30 min |
| [ ] | D04 | [Close desktop prevention evidence and documentation](Kiosk-Prompt-Tasks/D04-desktop-closeout.md) | C12f | Verify matching desktop product/automation/docs, both-target evidence and completed owned restoration | 20–30 min |

Order is authoritative; IDs are stable labels. C07a/C07s/C07 and C11d/f–C12d/f
carry their desktop assertions here. Standalone terminal/TTY assertions are
retained as C07t/C11t/C12t in the [remaining queue](Kiosk-Prompt-New-Queue.md),
which also owns SSH and other confinement work. Preserve case IDs, acceptance
targets and historical failures. Selectors remain planned until registered and
qualified. Missing independent work becomes a bounded prerequisite at its
selected consumer; host checks and `--check` supply no installed acceptance.
Use the shared launcher's current-definition and completion policies; ordinary
execution needs no plan-specific migration or historical-report preflight.
