# Kiosk local full desktop prevention queue

The [master](Kiosk-Desktop-Plan.md) owns desktop-only scope, usability, threat
limits and both-target acceptance. Audit and close residual cleanup first;
require accepted baseline use at D01, then finish this plan before
`tools/kiosk-prompt-new`. Planning completes no task.

Every row applies the master's [simple implementation](Kiosk-Desktop-Plan.md#simple-implementation)
and [simple tests](Kiosk-Desktop-Plan.md#simple-tests): reuse existing mechanisms
and coverage, add only missing product checks and avoid duplicate runs for task labels.

D00a/C07a/C07s include both-target installed usability before completion and
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
| [x] | D00a3q | Qualify saved-routing variation and recovery | D00a1, D00a2 | Qualify finite saved-preference variations with independent dedicated-session selection observations and one transient routing-discovery failure, restoration and fresh public use on both targets; no product changes or consumer acceptance credit | Both-target normal execution, three pre-fix refusal/repair controls, discovery outage, exact restoration, fresh public entry/form/Cancel/return and owned cleanup passed; no product changes |
| [x] | D00a3 | Keep kiosk entry working with old saved choices | D00a1, D00a2, D00a3q | Repair the routing-discovery admission boundary for stale or unavailable saved preferences; pass both-target usability and affected recovery controls | Both-target varied execution, discovery loss/restoration, complete public usability and installed 268 passed; Astra review, 731 host checks, DEB/RPM builds and owned cleanup passed |
| [x] | D00a4q | Check recovery from stale sign-in state | D00a1, D00a2, D00a3 | Qualify the finite owned lease variation, writer exclusion and exact restoration on both targets before D00a; no product changes or consumer acceptance credit | Both-target stale-mode refusal, real writer exclusion, retained read-only handles, exact restoration, complete short public history and owned cleanup passed; no product changes |
| [x] | D00a | Close residual conflicting confinement source | D00, D00a1, D00a2, D00a3, D00a4q | Resolve one residual confinement issue and require both-target tolerant kiosk use before completion | Both-target same-inode lease recovery, writer exclusion, retained read-only handles, complete short public history and installed 268 passed; Astra review, 498 host checks, DEB/RPM build and owned cleanup passed |
| [x] | D00b | Close obsolete confinement automation consumers | D00a | Reconcile residual obsolete v1.4 fixtures, imports and registrations with retained behavioral outcomes and historical evidence | No obsolete executable consumers; stale host expectations removed/repaired, 137 scoped checks, listings, coverage generation, links and owned cleanup passed |
| [x] | D01 | Review full desktop entry routes | D00b | Verify accepted cleanup/baseline use and map finite local desktop attacks with permitted controls | Reviewed local callers, existing barriers and finite reachability/qualification gaps in the design owner; links, plan metadata and owned cleanup passed; no product changes or installed claims |
| [x] | D01r | Review the named remote-desktop route | D01 | Map one supported provider's actual account/session path and usable ordinary-account positive without implementation | Reviewed GNOME Remote Desktop system RDP/GDM callers, vendor gate limits, public controls and finite qualification gaps; links, plan metadata and owned cleanup passed; no product changes or installed claims |
| [x] | D02 | Review the minimal desktop protection design | D01r | Independently review and allocate only the finite desktop barriers and directly affected controls | Independent Astra review passed all three criteria; finite qualification allocations, links, plan checks and cleanup passed; no product changes or installed claims |
| [x] | C07a1 | Check public desktop selection | D02 | Qualify public alternate-desktop selection and chooser cancellation, independent selected-launch observations, ordinary desktop use and fresh request entry on both targets; no product changes or consumer acceptance credit | Both-target ordinary desktop selection, station no-route dispositions, launch observations, usable Cancel/reentry, exact restoration and owned cleanup passed; no product changes |
| [x] | C07a | Prevent local full desktop access | D02, C07a1 | Add one justified graphical-session barrier and pass both-target kiosk usability before completion | Retained existing mechanism using C07a1's exact no-route results; both-target complete short usability, public restoration and owned cleanup passed; no product changes |
| [x] | C07s1 | Check desktop attempts from the request session | C07a | Qualify the finite request-session shortcuts, missing Alt+F2 result and ordinary-desktop controls on both targets using shared bindings; no product changes or consumer acceptance credit | Both-target eight shortcut results, usable Cancel/fresh entry, public restoration and cleanup passed; Fedora terminal shortcut prepared permanently; no product changes |
| [x] | C07s | Prevent desktop launches from the request session | C07a, C07s1 | Close one reviewed desktop-launch boundary and pass both-target kiosk usability before completion | Retained qualified GNOME Kiosk shortcut/action boundaries; both-target complete short usability, public restoration and owned cleanup passed; no product changes |
| [x] | C07r1 | Prepare remote sign-in on both systems | C07s | Qualify isolated GNOME Remote Desktop system login preparation, readiness and owned restoration on both targets; no product changes or consumer acceptance credit | Both-target repeated isolated readiness, exact file/service restoration, normal kiosk entry/Cancel/return and owned cleanup passed; five file-safety checks passed; no product changes |
| [x] | D03a | Make desktop selection checks reject a full kiosk desktop | C07s | Require request-only results in both existing public station-selection histories and qualify the verdict on both targets; no product changes | Both-target request-only verdicts, ordinary desktop controls, restoration and owned cleanup passed; listing and links passed; no product changes |
| [x] | D03b | Make shortcut checks reject desktop launch controls | C07s | Require request-only results after all four existing station shortcuts and qualify the verdict with ordinary controls on both targets; no product changes | Both-target eight-result verdicts, ordinary controls, Cancel/fresh entry, settings restoration and owned cleanup passed; listing and links passed; no product changes |
| [x] | D03 | Freeze desktop acceptance bindings | C07s, D03a, D03b | Audit exact registered desktop histories and prior both-target usability; no deferred product gate | Registered enforcing verdicts, finite compositions and prior both-target usability audited; runner listings, links, plan metadata and owned cleanup passed; no installed acceptance claimed |
| [x] | C11d | Qualify local desktop prevention on Ubuntu | D03 | Ubuntu: Verify finite local desktop attacks, normal kiosk use and affected recovery controls | Ubuntu candidate-matching selection and eight shortcut results passed; ordinary controls, usable Cancel/fresh entry, exact routing/policy restoration and owned cleanup passed; unchanged C07a/C07s usability reused; no product changes |
| [x] | C12d | Qualify local desktop prevention on Fedora | C11d | Fedora: Verify finite local desktop attacks, normal kiosk use and affected recovery controls | Fedora candidate-matching selection and eight shortcut results passed; ordinary controls, passwordless Cancel/reentry, exact routing/policy restoration and owned cleanup passed; unchanged C07a/C07s usability reused; 61 helper guards passed; no product changes |
| [ ] | D04 | [Close desktop prevention evidence and documentation](Kiosk-Prompt-Tasks/D04-desktop-closeout.md) | C12d | Verify matching desktop product/automation/docs, both-target evidence and completed owned restoration | 20–30 min |

Remote-desktop testing was removed by developer direction. D01r and C07r1
remain completed historical work; their dedicated automation is retired, and
they supply no remote-desktop acceptance. D03's composition audit found missing
final negative verdicts in the two local qualification journeys. D03a and D03b
qualified the desktop-selection and shortcut verdicts on both targets; D03
confirmed the registered comparisons and froze the finite final-acceptance map.
Completed qualifications and product gates stay accepted. The next active task
is D04.

Order is authoritative; IDs are stable labels. C07a/C07s and C11d/C12d
carry their desktop assertions here. Standalone terminal/TTY assertions are
retained as C07t/C11t/C12t in the [remaining queue](Kiosk-Prompt-New-Queue.md),
which also owns SSH and other confinement work. Preserve case IDs, acceptance
targets and historical failures. Selectors remain planned until registered and
qualified. Missing independent work becomes a bounded prerequisite at its
selected consumer; host checks and `--check` supply no installed acceptance.
Use the shared launcher's current-definition and completion policies; ordinary
execution needs no plan-specific migration or historical-report preflight.
