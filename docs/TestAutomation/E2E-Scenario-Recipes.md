# Customer E2E scenario recipes

[scenarios.json](../../tests/e2e/scenarios.json) owns customer-readable steps,
persistent case IDs, matrices and current readiness. This document supplies the
exact block compositions and finite data. The [documentation map](README.md)
separates recipe, block, queue and runtime status ownership. Do not copy recipes
into task briefs or silently substitute inputs. In an implementation session,
read only the selected family's branches, applicable finite-data rows and common
entry/time rules.

E2E-028, E2E-029 and E2E-034 are retired; their former coverage IDs 140–150
remain system-test obligations outside the UI inventory. Preserve all current
ready inventory bindings and their functional assertions. Each family below records
current implementation context, not an independent readiness authority. Follow
the [execution plan](E2E-Execution-Plan.md#completion-and-document-cleanup) after
a complete scenario pass. A block qualification alone leaves its scenario
pending.

## Independent entry, actions and observations

Each case starts from its own clean declared computer state. Ordinary feature
cases use the installed version snapshot; installation and update cases install
their declared initial package in their own journey. No case depends on another
case's settings, approvals, windows, timing, account changes or result. Sharing
verified installed assets and compiled blocks does not share mutable case state.

Use synthetic role labels: Jamie = parent, Sam = other eligible parent,
Jordan = selected child, Riley = other child/unrelated standard user. A variant
using second child or second parent swaps the indicated roles in all its inputs.
These are readable aliases for registered fixture identities, never literal
account names required on a customer's computer. Limits initially are off,
allowances zero and app rules allowed. Prepare every tested policy through
Parent and every grant through the real system approval prompt.

The [UI mandate](../Mandates/UI-Automation-Mandate.MD#route-selection) owns
route selection. Cases 3, 4 and 179–183 use shared account helpers and independently
observe the app's discovery, empty-state, eligibility and selector fallback.
Case 1 is harness qualification. Retired IDs 140–150 remain engineering checks
in system-test tasks 169–179.

All recipes use the [bounded supporting-work contract](E2E-Building-Blocks.md#keep-supporting-work-bounded).
Reuse verified local fixtures, direct supporting commands and existing helpers.
Preparation ends when the declared prerequisite is established; the following
product action and independent customer result supply acceptance.

Names, labels, roles, text and order below describe inputs/results, not selectors.
Use the catalogue's shared [Application UI API](Application-UI-API.md) binding
under the UI mandate for every product control. `setValue` selects canonical
account UIDs, duration tokens, language codes and rule keys; `setText` edits
literal fields, and `activate`/`close` invoke normal handlers. Dialogs and editor
operations use the same facade in both UI and E2E suites. Independently read
the required result after input. External authentication, file chooser and
supporting-tool operations retain their provider adapters.

Every ordinary Parent launch or reopening uses PARENT01's direct
`oh-no-parent-control-parent` command, including launches inside FLOW01/P/P0
and case 6's denial check. No terminal is opened. App-grid search is reserved
for the explicit discovery/launch checks in E2E-003 and the unavailability check
in E2E-004/app-grid, using the full query `Oh No! Parent Control`. Reusing an
observed retained Parent window does not launch it again. Future app-grid
exceptions must be explicit in metadata and recipe.

Every ordinary child overlay launch or reopening uses REQUEST02's direct
`oh-no-parent-control-child` command. It observes the single form and fixed
child independently. E2E-012 tests repeated graphical panel launch and
E2E-024/fullscreen tests graphical launch from fullscreen play; these cases
use REQUEST13 where that route is under test and declare the exception in
their metadata. The later E2E-012 reopen and the windowed E2E-024 cases use
REQUEST02. Reusing an already open overlay does not launch it again.

Use the following common recipe notation. It expands to catalogue blocks; it
does not permit hidden setup or automatic repair after a failed step.

| Name | Exact composition and arguments |
| --- | --- |
| P / P0 | FLOW01(parent, child, source, entry, window) → PARENT04(required page). P0 is first fresh parent entry; P uses the case's observed retained desktop/window. After logout/reboot use fresh/new explicitly. |
| C / V(user) | FLOW15(user, source, entry, result). First entry is fresh; a previously retained desktop uses retained. Expected result is success unless denial is stated. |
| G | From desktop DESK03; from lock/rejected sign-in DESK11; from a closed station GDM01. Choose from the already observed source, never by trying routes. |
| request-entry | Overlay: C → REQUEST02. Station: G → REQUEST01. Limits must already be enabled, and overlay needs positive time. Reading persistence never runs FLOW04 choices first. |
| access-check | After success, TIME01 → FLOW08(A usable) → FLOW08(H denied). With limits off TIME01 requires absence. After denial, GDM06 reads the time-limit explanation; no app-window assertion is made. |
| leave-child | New-session variant: DESK04 after a successful visit. Retained variant: DESK03. After denial: DESK11. |
| repeat / watch | Iterate the finite table with new observations each time. watch(observer){input} = UI25 start and readiness → the named input once → UI26 finish; UI22 is this declared composite. |
| AppSet | FLOW19: P → FLOW03 for each explicitly named app/rule → G. Default assets are A (Always Allowed), H (Hard Blocked), S (Soft Blocked), N (nonmatching allowed). |
| approve-and-return | FLOW20(surface, child, approver, duration, soft choice, child entry): from the child's desktop for overlay or GDM for station, prepare the form, approve once and read the child's resulting countdown. It never changes daily allowance or saved app rules. |

The current source surface, retained desktops and open windows are explicit
outputs of this case's preceding blocks. Thread this ledger through every call.
After an AppSet prefix the parent is retained: subsequent P/FLOW13 calls must
use retained parent/new or retained window as observed, never P0's fresh entry.
Where two activities share a desktop use DESK10 to return to its already-open
window. Opening Parent again must be observed to present its one active window.

AppSet is a mandatory public prefix for cases that assert hard/soft policy but
do not configure those rules in their listed steps: E2E-007, 009, 011's combined
app checks if used, 012–014, 021–025, 036, 038 and 039. Omit unused assets and
checks: countdown-only E2E-011 does not acquire an app-policy dependency.
Riley's activity is prepared with FLOW14 before an isolation action and revisited
with FLOW09 afterward. Only E2E-006/007/010/021/038 own retained other-user
continuity in the short cases; E2E-050/051 own continuity over repeated changes.
E2E-019 owns other-user launch independence. Other cases do not
append a generic unseen “other users unchanged” assertion.

Every expanded recipe also binds its entry and finish from the tables below.
`P`, `C`, `G` and a slash-separated block list are notation, not permission to
skip navigation: `PARENT03/PARENT12` means both reads, on their respective pages.
Before calling C from Parent use G; before calling P from a child desktop use
the declared leave-child route. A GDM-only operation such as REQUEST01 or
FLOW06 likewise uses G first when the current declared source is a desktop or
lock screen. These transitions are part of the expanded recipe, never fallback
inputs after failure. After sign-out/reboot invalidate old window
observations and use fresh entry. Never call P or read private state to inspect
an inactive child invisibly. In particular, returning after an expired grant
can restore blocks and close apps: finish a no-restoration observation **before**
leaving that child desktop. All scenarios finish with their final public result
recorded and no unanswered authentication prompt; ordinary exit blocks close
remaining forms before the common outer cleanup.

Activities must have recognizable public state, such as an unfinished synthetic
document or a real offline game level. APP03 proves interaction changes that
state. Game mode/level preparation uses APP05's shared supported commands or
shortcuts; settings-menu traversal is not a product assertion. Bind startup
options before FLOW08 launches and never relaunch a retained game to prepare it.
A later newly launched app cannot prove earlier work survived. When testing a new
launch beside an already-open app, use a declared supported new-instance route
and identify the new public window; merely presenting the old window is not a
successful new launch. Never
read processes behind a lock. Natural expiry is created by actual use and
elapsed time, not Lock, clock changes or synthetic usage. Correct-password
time-limit denial is app behavior; ordinary wrong-password GDM rejection is
outside scope. Wrong credentials in the product's selected-parent approval
prompt exercise the product's denial/choices/retry behavior.

## Finite data and execution budgets

Use public observations to bind actual values before actions. Expected results
come from the specification, not from accepting whichever outcome occurs.
Short observations normally have a 45-second deadline; ordinary account/app
refresh has a 60-second deadline. Approval waits allow 90 seconds for planned
fixture interaction. Natural expiry uses the earlier displayed balance plus
30 seconds for display/lock propagation, within the case deadline. A timeout
fails or records an unavailable prerequisite; it never changes the expectation.

D and G are displayed daily and grant balances; R is the requested duration.
Record their display precision and elapsed navigation time. For a fixed request,
the new usable interval is max(D,G)+R minus elapsed time; do not add D and G.
Compare bounded intervals using one display unit per observation plus measured
elapsed time. If bounds overlap so widely that an incorrect result would pass,
choose a more precise public display or retain the assertion as unqualified.
Large durations test selection and displayed arithmetic without waiting to expire.

| Data | Complete finite set / expected result |
| --- | --- |
| Daily presets (158) | Select/read 15 minutes. UI samples 0, 60, 90 and 1410 through the shared API operation; canonical preset-list completeness remains lower-layer coverage. |
| Daily custom (158) | Save custom 1 after preset 15; reopen and read the final saved 1. UI tests own invalid-input rejection, including preservation of the last saved value, and the complete custom boundary set. The API's 1440 allowance remains engineering coverage. |
| Daily saving (159) | From Jordan's enabled zero, save 15, then custom 5 followed promptly by 6; final saved value is 6. Save Riley custom 7, return and read Jordan=6/Riley=7. Close/reopen and repeat the per-child read. Real save ordering stays here; singleton-window and local validation coverage belong to shared UI. Popup, focus and per-keystroke presentation are not acceptance prerequisites. |
| E2E-005 profiles | daily-only: positive daily, no grant; grant-only: zero daily with real 10-minute approval before edits; combined: positive daily plus a real 10-minute addition. Enabled edits: daily-only/combined 4→5→0 minutes; grant-only 0→4→0. Read saved allowance and original grant deadline after each edit; visit the child at the positive and zero access boundaries. At zero, daily-only must deny access while combined retains its grant. If navigation exhausts a required margin, fail preparation rather than inject usage. |
| Request presets (38/41) | Select 5 minutes, read its footer and actual approval prompt, then approve. UI tests own all 5, 15, 30, 60, 120, 240 choices on both surfaces. |
| Request custom (39/42) | Reject 0.09 locally, then request and approve 1.25 minutes (75 seconds). UI tests own valid 0.1, 0.5, 1.25, 1440 and invalid empty, abc, −1, 0, 0.09, 1440.1, comma decimal 1,5, including whole-second display conversion. |
| Rest of the day (40/43) | First approve a 1440-minute fixed grant, read its later deadline, then choose/approve Rest of the day. Read PARENT09 before and after: the replacement interval is shorter and the footer says until midnight. Calendar cases own the exact deadline check. No 24-hour wait. |
| Shared choices (58–61) | Jordan custom 1.25, soft included; Riley custom 2.5, soft excluded. Seed station approver Jamie and each overlay approver Sam. Compare shared values and local selectors before edits; reverse direction/primary child per variant. |
| Short time | Natural daily tests use 2–4 minutes and verify positive D before entry. Grant-only uses 2 minutes; replacement uses 3. Active reboot/update uses 15–20 minutes. These are preparation choices, not bypasses of observed balances. |
| E2E-038 daily dominant | Start with daily 4 minutes and a real 0.1-minute addition including soft apps. Enter, open S, switch away, and wait until displayed G is 60–90 seconds while D remains at least 120 seconds. Return before grant expiry. No later screen/app save occurs before the tested action. FLOW18 checks the inequalities; wrong timing fails preparation. |
| Station restriction routes | Super/Overview, Super-A/app grid, ordinary terminal shortcut; inspect available controls for Parent/settings launch. If no search field appears, no query is typed. About/report restrictions have their own cases. |
| Kiosk multiple/ineligible accounts (53/56) | Read exact eligible child/approver sets. Request and Cancel Riley/Jamie, then Jordan/Sam (the second fixture administrator is Casey). Final selection and actual selected-parent prompts cover both identities with two pairs; do not cross every child with every parent. |
| App transitions (13–16) | Allowed→Soft, Soft→Hard, Hard→Soft, Soft→Allowed, Allowed→Hard, Hard→Allowed: all six directed changes. Open work under Allowed before Allowed→Soft/Hard. Before Soft→Hard obtain real soft approval and reopen the matching activity; in limits-off cases temporarily enable, approve/open, then disable (preserving the activity). Verify the declared limit state again before the tested save. Hard→Soft stays blocked without a new exception; Soft→Allowed and Hard→Allowed permit launches. Unchanged-block restoration is owned by 169. |
| Match/control/route matrix | Preserve all four precise/pattern × on/off cases and all 48 route × rule × on/off cases. Alias, special-path, update and file-pattern data run only in their owning cases. |

The daily picker offers 50 presets; case 158 checks one installed choice.
Noninteracting combinations, such as every attachment size with every app launch
route, add no app-behavior coverage and are not multiplied. Every declared
interacting matrix is complete; this is a finite coverage model, not a claim
that arbitrary inputs, elapsed durations and user histories can be enumerated.
Setup is shared code, not prior execution. Group implementation work, but run
each numeric variant as an independent attempt. Long calendar and retry-expiry
cases retain their declared acceptance prerequisites and budgets in the same fixed queue.

### Explicit time preparation

FLOW13 is a setup composition within this case, not an inherited fixture. It
starts in Parent for the selected child, verifies G=0, and uses only the
following public operations. If a recipe explicitly starts with an existing
grant, either preserve it or confirm Revoke as that recipe says; never silently
clear it. Allowances are total daily minutes, **not** a fresh balance. Read D
after every allowance save and fail preparation if the required margin is
absent. These ordinary profiles avoid midnight; calendar cases supply their
own scheduled profile.

| Profile | Allowance and real approval | Required visible result / finish |
| --- | --- | --- |
| daily-only | Enable, save 4 minutes; no approval. | D>0, G=0; GDM. E2E-008 uses 2 minutes. |
| grant-only | Enable, save 0; station approval for 2 minutes. | D=0, G>0; GDM. Replacement requests use 3 minutes unless a table overrides them. |
| combined / grant-dominant | Enable, save 4; station request for 2 additional minutes. | G>D>0 by a distinguishable margin; GDM. |
| daily-dominant | Enable, save 0; approve 2 minutes; while still enabled save 6. | D>G>0 by a distinguishable margin; GDM. This allowance save restores soft launch blocks; it does not establish a soft exception. |
| daily-dominant with soft exception | FLOW18: save 4, request 0.1 including soft apps, then spend time on the parent's retained desktop until G is 60–90 seconds and D≥120 seconds. | Return while G>0; finish on the child desktop. No policy save follows approval. |

Non-expiry form/catalogue cases use 30 daily minutes unless they need zero;
they observe the remaining margin rather than waiting for all that time.
E2E-037 uses 6 minutes so its final natural exhaustion is bounded. Lifecycle
active profiles use a 20-minute grant, expired profiles 2 minutes. Their saved
choices are Jordan custom 1.25/soft included, Riley custom 2.5/soft excluded,
station approver Jamie, overlays Sam. Grant preparation changes request choices:
after that approval, explicitly reselect the intended saved values and Cancel,
without submitting, **before** capturing persistence expectations. Entering a
disabled or exhausted child's overlay is never a preparation shortcut.

### Coverage and execution policy

Cover each distinct functional outcome in its owning layer under the
[UI/E2E allocation](UI-and-E2E-Coverage.md). Remove incidental GUI permutations;
E2E samples the installed component and retains every distinct backend or
OS result. For values sharing a backend mechanism, enumerate representative
inputs inside the owning case. E2E-019 owns baseline
launch rules; E2E-049 owns temporary exceptions on those same eight routes and
both request surfaces. E2E-048 owns elapsed time during authentication; gameplay
extension remains E2E-024. Long routines own the **ordered history**, not another
count of their individual transitions. Swapping an arbitrary display name or
running every feedback value with every app route adds no distinct behavior.

Use one installed snapshot preparation per invocation, independent restoration
per numeric case, and shared block code. Batch read-only values on the current
surface; do not batch independent cases into one mutable desktop. Each sequence
checks its intermediate result before the next change can conceal a defect.
Failed input is never repaired/replayed, and an incomplete stress loop cannot
pass from its final state. No random loops or open-ended soak are declared.

## Family compositions

Each numbered line below implements the matching inventory step. Inputs,
observations and prerequisite prefixes above are part of every expanded case.
No step calls a product API, reads private state or invokes a fault control.

### E2E-002

Implementation status: Case 2 composes `package_journey.record_package_journey` /
`onpc_clean_install::run`; see the [qualified composition](E2E-Building-Blocks.md#clean-installation-journey).

**Install the app and begin managing a child.** Cases 2.

Bindings: installation = clean.

1. V(parent,fresh) → LIFE04(install) → FILE06(notice).
2. LIFE02 → GDM01 → UI13(personal accounts, station).
3. P0 → PARENT03(defaults) → PARENT04(App Limits) → UI13(unblocked rows) → DESK03 → REQUEST01 → REQUEST03 → REQUEST12(cancel).

### E2E-003

Implementation status: Cases 3 and 4 retain complete implementations and ready
inventory bindings.

**Parent discovery and navigation.** Cases 3, 4.

Bindings: children = existing-and-new / none.

1. Explicit app-grid discovery exception: V(parent,fresh) → SEARCH05(Parent, whole query) → PARENT02(existing child) → PARENT03(capture defaults) → PARENT04(App Limits); none: V(parent,fresh) → SEARCH06(Parent), no launch yet.
2. Existing: PARENT04(Screen Limits) → PARENT03 → FIX01 (supporting account checkpoint) → UI13(new choice); none: FIX02 (supporting account checkpoint).
3. Existing: PARENT02(new) → PARENT03 → PARENT04(App Limits) → PARENT04(Screen Limits) → PARENT03 → UI12 → PARENT02(original) → PARENT03 → UI12. None: UI05(Enter) → PARENT19.

### E2E-004

Implementation status: Cases 5 and 6 retain complete implementations,
behavioral verification and ready inventory bindings.

**Standard user cannot manage policy.** Cases 5, 6.

Bindings: launch = app-grid / terminal (the stable `terminal` ID now means
direct command invocation, without opening Terminal).

1. V(standard,fresh); app-grid alone then uses SEARCH01.
2. Grid: UI21 → SEARCH03 → SEARCH04(unavailable), no Enter. Case 6: PARENT01(denied) → UI11(management). Read **Administrator access required** and its administrator-sign-in explanation, then dismiss the denial and independently observe the desktop with no denial or management controls. Generic startup errors or successful command submission cannot establish access denial.

### E2E-005

Implementation status: All cases pending.

**Change screen limits while starting or returning to a child desktop.** Cases 7, 8, 9, 10, 11, 12.

Bindings: time = daily-only / grant-only / combined; session = new / retained.

1. P0 → FLOW03(allowed and hard targets) → FLOW02(profile allowance, final off). Retained: C(fresh) → FLOW08(allowed) → APP04 → P(retained).
2. UI17(on) → PARENT08 → PARENT09 → C(variant entry, expected access) → access-check. Grant profiles: G → FLOW06(short grant) → P(retained) → PARENT09.
3. Save the positive allowance edit and then zero through PARENT06 → PARENT08 → PARENT09, comparing the saved allowance, actual balances and preserved grant deadline. Visit C at the positive and zero boundaries to require the declared access result. Leave through the declared route before returning to P; sample app launches at the enable/disable transitions.
4. Repeat(off,on): UI17 → PARENT08 → PARENT09 → C → access-check → leave-child. Read saved settings in Parent at finish.

### E2E-006

Implementation status: All cases pending.

**Change app rules while children use apps.** Cases 13, 14, 15, 16.

Bindings: control = enabled / disabled; match = precise / pattern.

1. P0 → FLOW02(control, usable allowance) → FLOW03(permissive match setup) → G → FLOW14(child,Riley activities) → P.
2. For each transition in the app table, prepare its explicitly required open activity, then P → PARENT16 → PARENT08 → C(retained) → APP02(existing result) → FLOW08(matching and nonmatching) → FLOW09(Riley). Finish each iteration's checks before the next save; phase step-2 owns the entire finite loop.
3. P → LIFE01(Parent) → PARENT02 → PARENT12 → UI12(final Allowed rule). This phase does not replay the transitions.

### E2E-007

Implementation status: All cases pending.

**Cancel then confirm revocation with open apps.** Cases 17, 18, 19, 20.

Bindings: daily = zero / remaining; sessions = single / multiple.

1. FLOW13(profile, active grant) → FLOW14(child desktop list,Riley); P opens the same child's Screen Limits.
2. PARENT17 → PARENT18(cancel) → PARENT09 → C(retained) → APP04(compare) → P.
3. PARENT17 → PARENT18(confirm) → PARENT09. D>0: C(each retained) → APP02(soft closed) → FLOW08(allowed and blocked). D=0: C(retained,denied) → DESK11. FLOW09(Riley).

### E2E-008

Implementation status: All cases pending.

**Natural daily exhaustion, retained unlock and fresh login denial.** Cases 21, 22.

Bindings: entry = retained-unlock / fresh-login.

1. FLOW13(short daily-only) → C(fresh) → FLOW08(allowed).
2. TIME04(natural daily exhaustion).
3. DESK08(time denial). Fresh-login only: DESK11 → FLOW06(temporary time) → C(retained) → DESK04 → P → PARENT17 → PARENT18(confirm) → PARENT09(D=G=0) → G → C(fresh,denied).

### E2E-009

Implementation status: All cases pending.

**Recover unfinished work after grant-only time runs out.** Cases 23, 24.

Bindings: soft-apps = excluded / included.

1. FLOW13(grant-only, soft included) → C(fresh) → FLOW08(allowed,soft) → APP04(each).
2. TIME04 → DESK08(time denial).
3. FLOW11(replacement, variant soft choice) → APP04(allowed compare) → APP02(soft expected) → FLOW08(hard and soft launches).

### E2E-010

Implementation status: All cases pending.

**Switch User while child time expires.** Cases 25, 26.

Bindings: foreground = parent / other-child.

1. FLOW13(grant-only) → C(fresh) → TIME01 → V(foreground) → FLOW08 → APP04.
2. repeat until original interval passed: APP03 → TIME03(bounded interval).
3. C(retained,denied) → DESK11 → FLOW09(foreground).

### E2E-011

Implementation status: All cases pending.

**Plan child activity with the remaining-time countdown.** Cases 27, 28, 29.

Bindings: time = daily-only / grant-only / combined.

1. FLOW13(profile) → P → PARENT09 → C(fresh) → TIME01 → FLOW08(allowed activity) → APP04.
2. DESK05 → DESK08(success) → TIME01 → APP04(compare retained activity). Compare the updated countdown against the earlier balance and actual elapsed time; return cannot reset the usable interval.
3. Use the activity through TIME02(minute and final seconds) → TIME04(natural lock). Remaining-time information must predict the end of usable desktop access. Countdown visibility across unrelated surfaces and tooltip wording remain child UI coverage.

### E2E-012

Implementation status: All cases pending.

**Request more time from the panel with the selected parent.** Cases 30, 31, 32, 33.

Bindings: soft-apps = excluded / included; approver = first / second.

REQUEST13 uses the shared `child-panel` API to activate `child-request-button`
and independently observe the fixed-child request. No panel reveal, focus or
Overview/Escape sequence is required for product input. Repeated panel input and singleton-form qualification stay
with child UI coverage; ordinary later entries use `command`.

1. FLOW13(combined, soft included) → C → FLOW08(soft) → APP04 → REQUEST13 once (explicit panel entry) → REQUEST03(fixed child).
2. REQUEST04(approver,duration) → REQUEST06(soft choice) → REQUEST08 → REQUEST09 → AUTH01(exact prompt).
3. AUTH02(correct) → REQUEST11(success) → REQUEST12(automatic) → TIME01 → APP02(soft effect) → FLOW08(hard/soft). After TIME03(cooldown): REQUEST02 → REQUEST09 → AUTH02(cancel) → REQUEST11(cancel) → REQUEST12(cancel).

### E2E-013

Implementation status: All cases pending.

**Authentication denial and cancellation retry.** Cases 34, 35, 36, 37.

Bindings: surface = child-overlay / kiosk; outcome = wrong-password / cancel.

1. P0 → FLOW02(overlay daily-positive or kiosk zero) → FLOW03(blocked target). Overlay C → FILE01 → FLOW04; kiosk G → FLOW04.
2. FLOW07(wrong approval credential or cancel). Overlay FILE02(target command over guarded SSH as the active child) → FILE06(denied) → REQUEST03. Kiosk REQUEST12(cancel) → C(fresh,denied) → DESK11 → REQUEST01 → REQUEST03. UI12(choices).
3. FLOW05(fresh approval) → C if kiosk → TIME01 → FLOW08(expected target).

### E2E-014

Implementation status: cases 38–43 are excluded from automation scheduling under
the [unsupported native-gesture rule](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures).
Their stable inventory IDs remain pending without executables or acceptance
credit. The following recipe records uncovered behavior, not an implementation
instruction. Do not create tasks for it or make it block the remaining queue.
Local duration validation is independent and remains with the UI coverage owner.

**Shared duration boundaries and duplicate submission.** Cases 38, 39, 40, 41, 42, 43.

Bindings: surface = child-overlay / kiosk; choice = predefined / custom / rest-of-day.

1. FLOW16(enable and selected daily allowance) → request-entry(surface). Select the installed sample from the duration table with REQUEST04/05 → REQUEST03 → REQUEST08; full local validation belongs to the request UI capability tasks.
2. Invalid: REQUEST09(validation) → UI11(prompt). Valid: REQUEST09 → AUTH01(exact details) → AUTH02(cancel) → REQUEST11(cancel). Rest-of-day first obtains 1440 minutes with FLOW05, reopens and selects Rest of the day.
3. REQUEST10(representative) → AUTH01 → AUTH02(correct) → REQUEST11 → REQUEST12(automatic) → C if kiosk → TIME01 → UI12(expected time).

### E2E-015

Overlay consumers use `journey_blocks.native_usable_app` /
`onpc_app_rows::native_usable_app` for FLOW08's qualified native usable route.
APP04 uses the shared `native-activity` public reader and
`JourneyPlan.activity_checks` to bind the later read to its earlier immutable
window/activity capture before further edits. This supplies no complete overlay
case or cross-user retention acceptance; those remain with their consumers.

Implementation context: case 47 uses `kiosk_cancel.PLAN` / `onpc_kiosk_cancel::run`.
Case 44 uses `overlay_cancel.PLAN` / `onpc_kiosk_cancel::run(exchange, 'overlay', ...)`.
Case 45 uses `overlay_cancel.ESCAPE_PLAN` /
`onpc_kiosk_cancel::run(exchange, 'overlay-escape', ...)` with the same preparation
and retained-activity checks; its exit is shared `onpc_request_exit::escape`.
Prepare Riley's enabled 15-minute daily allowance through Parent and independently
read 900 daily seconds with zero grant before fresh child sign-in. Verify the
baseline native fixtures through `fixture_actions(include_refusal=False)`, then
launch/use the native Allowed app by command and capture its immutable public
window/draft. Open the overlay once and prepare the qualified Jamie/custom
75-second/soft-included choices with `entry=open, initial=default`; independently
bound the estimate by the earlier balance and elapsed time. Invoke Cancel once
for case 44, or invoke the owned request-surface API `close` for legacy exit
binding `escape` in case 45. Require absent form and the original usable child desktop, and compare the exact
window/draft with the capture before submitting the same draft again. Record the
visible result only after that independent usable-app readback, then close the
app normally. Qualification-only refusal and repeated-entry matrices stay in
their capability owners.
Case 48 uses `kiosk_escape.PLAN` / `onpc_kiosk_escape::run` and the shared
`onpc_request_exit::escape` guard/input/return composition.
Other exits and surfaces remain separate cases; runtime status is in the inventory.

Overlay FLOW04 uses `request_flow.prepared_request(surface='overlay')` /
`onpc_request_flow::prepare(..., 'overlay')`, composing the shared form leaves
with a fixed child and no child-selection input. The declared Riley/Jamie,
75-second, soft-included binding is qualified for an already-open default form
and a new entry with remembered choices; see the
[overlay qualification](E2E-Building-Blocks.md#overlay-flow04-invalid-submission-and-escape-qualification).
`overlay_choices.PLAN` is the finite capability qualification, not a complete
case wrapper. Cases 44/45 reuse `KioskRequestJourney`, shared declarations,
`overlay_entry`, native activity endpoints and the normal installed-journey
lifecycle, keeping their separate Cancel/normal-close result assertions. The
stable `escape` binding names identify the latter API route. Mute and authenticated
overlay outcomes remain outside that slice.

Case 49 uses `kiosk_approved.PLAN` / `onpc_kiosk_cancel::run(exchange, 'approved', ...)`, the shared
`approved_request(exit='immediate')` declaration and
`onpc_request_flow::approve` with the qualified immediate-success/exit leaf.
Prepare and independently read 900 daily seconds and zero grant through Parent;
the child has not yet entered. Open the station once and prepare the same
75-second, soft-app-included choices as cases 47/48. Read the 975-second estimate
and its guest monotonic timestamp before submitting. Observe explicit approval
and invoke the offered immediate action once, then independently require absent
form and usable GDM. Freshly sign in as the intended child and require its usable
desktop before TIME01. `KioskRequestJourney` compares an immutable countdown
with the explicit 975-second approved balance, one-second public precision,
minute flooring and two-second sampling tolerance within 180 real elapsed
seconds of the estimate; no grant, clock or private-state probe supplies it.

**Request surface exit behavior.** Cases 44, 45, 46, 47, 48, 49.

Bindings: surface = child-overlay / kiosk; exit = cancel / escape / approved.

1. FLOW16 → C if overlay → FLOW08(allowed) → APP04 → FLOW04; kiosk uses G → FLOW04. Approved: REQUEST09 → AUTH02(correct) → REQUEST11.
2. REQUEST12(cancel|escape|approved-immediate). Overlay APP04(compare) → APP03; kiosk GDM01. Approved enters child if needed → TIME01.

Cases 47 and 48 prepare an enabled 15-minute daily allowance through Parent and read
the public balance before switching to GDM, using the shared
`daily_station_entry` declaration/worker fragment also used by case 49.
Enter the station once, then use
FLOW04 with `entry=open`, `initial=default`, explicit fixture child/parent,
custom `1.25` minutes and soft apps included. Independently compare the estimate
with that balance before Cancel (47) or one guarded API surface close (48); require the
absent form and usable GDM.

### E2E-016

Implementation status: Cases 50–52 use `restricted_station.PLAN`,
`DENIED_PLAN` and `CANCELLED_PLAN`, with
`onpc_restricted_station::run(exchange[, 'denied' | 'cancelled'])`.
Case 52 passed in `20260926T185046Z-2140b0d4`, including password-free approval
Cancel, FLOW07's preserved-form comparison, all three repeated restriction checks
and form Cancel to usable GDM. Affected cases 50 and 51 passed separately in
`20260926T185518Z-026edc31` and `20260926T185927Z-3a6cff95`.
All passed collection, owned cleanup and baseline restoration.
About/Help and report restrictions remain under
E2E-042 and E2E-045, outside this family's ordinary shortcut assertions.

**Restricted request station.** Cases 50, 51, 52.

Bindings: request = approved / denied / cancelled.

1. FLOW16(enable) → G → REQUEST01 → REQUEST03. For each restriction route: UI05(route) → UI11(forbidden window) → REQUEST03.
2. FLOW04(entry=open) → REQUEST09 → AUTH02(outcome) → REQUEST11. Repeat restrictions if form remains.
3. REQUEST12(cancel or automatic) → GDM01.

### E2E-017

Implementation status: Cases 57, 54 and 55 passed complete live acceptance in runs
`20260924T001910Z-3076f596`, `20260924T152534Z-98108590` and
`20260924T175340Z-dd93d54f`, respectively,
including collection, owned cleanup and baseline restoration;
case 53 also passed in `20260926T193803Z-abb86806` and case 56 in
`20260926T200913Z-2d372359`, with the same terminal outcomes.
`disabled_child.PLAN` / `onpc_disabled_child::run`
keeps limits off, checks the exact eligible child choices,
selects the disabled child, independently reads
the unavailable form without authentication, and observes Cancel returning to GDM.
UI17's Parent Screen time limit binding
and PARENT08's saved/control snapshots have installed slice qualification,
including wrong-child refusal and owned cleanup. REQUEST04's exact eligible
kiosk child/approver selection and independent enabled-form readback have installed
slice qualification. `check_e2e_request_choices` also qualified disabled-child
selection, explanation, unavailable Request and absence of authentication after
public Parent disable/save preparation. Transient saving is not qualified.

**Kiosk selection and unavailable requests.** Cases 53, 54, 55, 56, 57.

FIX03's no-child profile and public station empty-state slice passed
`check_e2e_kiosk_no_child` in run `20260924T064646Z-19f2aad6`, including
wrong-entry refusal, exact empty child set/explanation, disabled Request,
no authentication prompt, collection and owned baseline restoration.
Reuse `kiosk_no_child.PLAN`, `EmptyAccountFixture.prepare` and
`AccessibleUI.kiosk_request_form(no_child=True)`. Complete case 54 is registered
as `kiosk_no_child.CASE_PLAN` / `onpc_no_child::run`: direct station entry,
independent empty-form and unavailable-submission observations, then Cancel
and public GDM return. Its complete live acceptance passed independently of
the qualification-only wrong-entry checks.

Bindings: accounts = multiple / no-child / no-parent / ineligible-parent / disabled-child.

The multiple profile is qualified through `kiosk_multiple.PLAN` /
`onpc_kiosk_multiple::run` and `check_e2e_kiosk_multiple` in report run
`20260926T191541Z-dc28d61d`; the shared original prompt binding regression passed
in `20260926T192244Z-e74f7983`. Reuse the guarded canonical account profile,
public enable/save for both children, `select_kiosk_account`'s exact-set checks
and representative `MULTIPLE_MATE_BINDINGS` Cancel operations. The fixed slice uses
30 minutes with soft apps excluded for every pair and independently checks
preserved selections after each prompt. Complete case 53 uses
`kiosk_multiple.CASE_PLAN` / `onpc_kiosk_multiple::run`'s complete-case branch,
historically adding explicit selector open/exact-set/collapse observations and
unchanged-choice readback before selecting four pairs. A final preserved-form
read precedes Cancel and GDM return. It passed in `20260926T193803Z-abb86806`,
including reconciliation, collection, owned cleanup and baseline restoration.
The shared collapse helper's disabled-child case 57 regression passed in
`20260926T194240Z-ff1d1166` with the same terminal outcomes.
Current acceptance uses the two pairs in the finite-data table and the final
selected accounts, loaded settings and matching real approval prompts. Historical
open/collapse and all-four-pair samples above remain evidence of the earlier run;
they add no current acceptance requirement.

The ineligible-parent profile uses `kiosk_multiple.INELIGIBLE_PLAN` with
`IneligibleApproverFixture` to add one fixed locked administrator before Parent
entry, preserving both eligible parents and both children. Its exact offered-set
checks and all four real prompt/Cancel pairs passed the fixed qualification
`check_e2e_eligible_kiosk_fixtures` in run `20260926T195528Z-eb3740b5`, with
collection, owned cleanup and baseline restoration. Complete case 56 uses
`kiosk_multiple.INELIGIBLE_CASE_PLAN` / `execute_ineligible` with the fixed setup
action and complete multiple-account worker, historically with explicit selector inspection
and collapse, all four eligible pairs' real prompt cancellations, preserved form
and Cancel/GDM return. It passed independently in `20260926T200913Z-2d372359`,
including collection, owned cleanup and baseline restoration.

The no-parent profile's composition is qualified through
`kiosk_no_approver.PLAN` / `onpc_kiosk_no_approver::run` and
`check_e2e_kiosk_fixtures` in run `20260924T173358Z-94d5db62`, including the
starting parent observation, locking, Cancel/GDM/reentry and repeated empty-form
readback. Shared station navigation's no-child regression passed in run
`20260924T173643Z-8d742069`. Both attempts passed collection, owned cleanup and
baseline restoration. Reuse `NoApproverFixture.prepare`,
`AccessibleUI.kiosk_approver_baseline` and
`AccessibleUI.kiosk_request_form(no_approver=True)` for complete case 55.
Its `kiosk_no_approver.CASE_PLAN` / `onpc_no_parent::run` binding passed
independent complete-case acceptance in run `20260924T175340Z-dd93d54f`,
including capture reconciliation, collection, owned cleanup and baseline
restoration. Wrong-entry refusal is qualification-only.

1. Account profile is the declared setup. Enable available targets with FLOW16 except disabled-child and no-parent. No-parent keeps default limits off: first enter the request station and observe a listed parent, detect all eligible parents through the OS account service, temporarily lock that detected set regardless of names/count, Cancel to GDM and reopen the station. The observed parent must belong to the detected set. Preserve children/station and restore accounts through outer cleanup. No inaccessible administrator setup or hidden enabled-policy fixture is needed. Other profiles use G → REQUEST01.
2. Read each enabled selector's exact eligible set, then REQUEST04 for representative child/approver pairs covering both identities. Independently read the selected accounts and loaded child settings; the matching real approval prompt verifies the selected approver's effect. Use canonical selector values without popup/focus navigation. The API surface close ends the request form, including retained `escape` bindings. Disabled/empty uses UI02/03 without input.
3. REQUEST03 → REQUEST08. Available: REQUEST09 → AUTH01 → AUTH02(cancel) → REQUEST11. Unavailable: UI02(disabled) → UI11(prompt). No-parent specifically requires the missing-eligible-parent explanation and empty parent list; it makes no isolated screen-time enforcement claim with its also-disabled child.

### E2E-018

Implementation status: All cases pending.

**Remember each child's choices across both request forms.** Cases 58, 59, 60, 61.

Bindings: direction = overlay-to-kiosk / kiosk-to-overlay; child = first / second.

1. FLOW16 for both children (ample daily time). Establish distinct surface approvers through request-entry → REQUEST04 → REQUEST12. Starting child: FLOW04(custom,soft choice) → REQUEST03(capture).
2. FLOW12(other surface) → REQUEST03 → UI12(shared fields,local approver).
3. REQUEST12 → request-entry(other child) → FLOW04 choices → REQUEST03(capture). Return in both directions with FLOW12 and read/compare before editing.

### E2E-019

Implementation status: All cases pending.

**Use supported launch routes under each app rule.** Cases 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109.

Bindings: route = native-grid / native-desktop / native-file-manager / native-command / snap-grid / snap-command / flatpak-grid / flatpak-command; policy = allowed / hard-blocked / soft-blocked; control = enabled / disabled.

1. P0 → FLOW02(control,usable time) → FLOW03(target access rule).
2. C(fresh) → FLOW08(exact route, policy result). Hidden launcher: APP02(hidden) → FLOW08(explicit command route,denied).
3. V(Riley,fresh) → FLOW08(same target, corresponding route,usable).

### E2E-020

Implementation status: All cases pending.

**Catalog update/disappearance between display and save.** Cases 110, 111.

Bindings: change = update / remove.

1. FLOW16(usable time) → PARENT10 → PARENT16(Hard Blocked) → PARENT13 → UI16(match draft covering the declared updated target).
2. LIFE04(app update/remove through shared administrator SSH commands); Parent's editor stays open.
3. DESK10(editor) → PARENT15(save) → LIFE01(Parent) → PARENT02. Update: PARENT12 → C → FLOW08. Remove: UI13(app absent) → LIFE04(reinstall) → LIFE01 → PARENT02 → PARENT12 → UI12(retained rule) → C → FLOW08.

### E2E-021

Implementation status: All cases pending.

**Apply an action across a child's distinct retained desktops.** Cases 112, 113, 114, 115.

Bindings: transaction = save / approve-without-soft / approve-with-soft / revoke.

1. FLOW13(positive daily, needed grant) → FLOW14(explicit distinct child desktops,Riley).
2. Save: P → FLOW03. Approval: C(retained) → FLOW04 → FLOW05. Revoke: P → PARENT17 → PARENT18(confirm).
3. For each child desktop: C(retained) → APP02 → APP04 if preserved → FLOW08. FLOW09(Riley). No distinct public entry means pending.

### E2E-022

Implementation status: All cases pending.

**Customer lifecycle persistence and resume.** Cases 116, 117, 118, 119, 120, 121, 122, 123, 124, 125.

Bindings: boundary = app-restart / sign-out-in / reboot / idle / suspend-wake; grant = active / expired.

1. FLOW16 → FLOW03 → FLOW13(grant-only with boundary-specific duration) → prepare both request surfaces with FLOW04/REQUEST12 to restore the declared saved choices after grant issuance → REQUEST03(capture before exit) → C → TIME01 → FLOW08(allowed) → APP04.
2. app-restart: LIFE01(Parent), request exit/entry on both surfaces; sign-out: DESK04; reboot: LIFE02; idle: TIME03; suspend: LIFE03. Routes use the current session ledger.
3. TIME03 only for remaining expired wait; active return requires the original positive deadline.
4. P → PARENT03/PARENT12 → UI12 before edits. request-entry → REQUEST03 → UI12 before editing. Expired child denial → DESK11 → REQUEST01 → REQUEST03 before FLOW06 replacement. C → TIME01 → FLOW08; APP04 only on retained desktops.

### E2E-023

Implementation status: All cases pending.

**Zero allowance to kiosk approval, real gameplay and expiry.** Cases 126, 127.

Bindings: gameplay = windowed / fullscreen.

1. FLOW16(zero,on) → FLOW03(game Always Allowed).
2. G → C(fresh,denied).
3. DESK11 → FLOW06(short real grant).
4. C(fresh) → TIME01 → FLOW08(game) → APP05(mode,level) → APP03 → APP04.
5. TIME04(game natural lock).
6. DESK08(time denial) → FLOW11(replacement,game preserved) → APP04(compare) → APP03.

### E2E-024

Implementation status: All cases pending.

**Additional time accumulates during gameplay.** Cases 128, 129, 130, 131.

Bindings: time = daily-dominant / grant-dominant; gameplay = windowed / fullscreen.

1. FLOW13(dominant profile) → C → TIME01 → FLOW08(game) → APP05(mode,level) → APP04.
2. Windowed: REQUEST02. Fullscreen: REQUEST13(qualified panel reveal and graphical launch). Then REQUEST04(custom additional duration) → REQUEST08 → FLOW05 → TIME01 → UI12(increase).
3. DESK10(game) → APP04(compare) → APP03 → TIME04(extended natural expiry).

### E2E-025

Implementation status: All cases pending.

**Replace an expired grant before returning with daily time left.** Cases 132, 133, 134, 135.

Bindings: soft-apps = excluded / included; entry = new-login / retained-unlock.

1. FLOW13(grant-only,soft included) → C → FLOW08(soft) → APP04 → P → PARENT06(larger daily,still enabled) → PARENT08 → PARENT09(D>G).
2. Retained: G; fresh: C(retained while grant active) → DESK04. TIME03(to expired) → P → PARENT09(D>0,G=0).
3. G → FLOW06(replacement with variant choice) → C(declared entry) → FLOW08(hard/soft); retained additionally APP02/APP04(expected earlier soft activity).

### E2E-026

Implementation status: All cases pending.

**Customer package update and activation.** Cases 136, 137, 138.

Bindings: activation = process / session / reboot.

1. V(parent,fresh) → LIFE04(earlier release install) → LIFE05(notice) → FLOW16 → FLOW03 → FLOW06(20-minute grant) → prepare both forms with FLOW04/REQUEST03/REQUEST12 and capture the intended saved values after that approval → C → FLOW08.
2. P → LIFE04(update package) → LIFE05(exact affected users/surfaces).
3. P → PARENT03/PARENT12 → UI12 → ABOUT01(version) → UI18; request-entry(each) → REQUEST03 → UI12 before edits; C → TIME01 → FLOW08.

### E2E-027

Implementation status: All cases pending.

**Install through remove, reinstall and purge.** Cases 139.

Bindings: lifecycle = continuous.

Case 139 is implemented in
[removal_journey.py](../../tests/e2e/removal_journey.py), sharing the finite
[package lifecycle](../../tests/e2e/package_lifecycle.py) and installed journey
envelope. Its runnable registration does not establish live acceptance on either
platform. The qualified 75-second approval occurs after the child block/form
observations and immediately before the positive-grant read and removal; expiry
cannot substitute for clearing a positive grant. Retained/default assertions and
the four-minute → five-minute reapplication binding below remain independent.
Before comparing the overlay's saved request choices, select Jamie through its
local approver selector. Kiosk and overlay approver defaults have separate
[OS-user ownership](../SystemDesign/Frontends.md#request-selector-state); this
selection must preserve the shared 75-second custom duration and soft-app choice.
After remove or purge, graphical entry uses the product-free Parent/child
binding and proves the station is absent. After reinstall, entry again requires
the installed station; absence must never be accepted for an installed stage.
The recreated kiosk home has fresh local selectors: select Riley and Jamie
before reading Riley's retained shared request choices, without editing them.

1. V(parent,fresh) → LIFE04(install) → FILE06(notice) → LIFE02.
2. FLOW16 → FLOW03 → both forms FLOW04/REQUEST03/REQUEST12 → FLOW06 → C → FLOW08.
3. P → LIFE04(remove) → FILE06(notice) → LIFE02 → C(fresh) → FLOW08(formerly blocked,usable).
4. V(parent,fresh after the removal reboot) → LIFE04(reinstall) → LIFE05 → P(new window) → PARENT03/PARENT09/PARENT12(retained choices,zero grant) → request-entry(kiosk) → REQUEST03 → REQUEST12(cancel) → FLOW16/FLOW03(reapply) → C → FLOW08. P → LIFE04(purge) → LIFE05 → LIFE04(reinstall) → LIFE05 → P(new window) → PARENT03(defaults) → G → REQUEST01 → REQUEST03(fresh shared defaults). A removed product has no Parent window to launch; package work uses the shared administrator SSH helper. A disabled child has no overlay entry until limits are publicly enabled.

### E2E-030

Implementation status: Case 151 retains its complete implementation and ready
inventory binding.

**Identify the installed product and return to management.** Cases 151.

Bindings: surface = parent.

1. FLOW01(child) → ABOUT01(product, installed version and license information).
2. ABOUT03(previous child/settings observation). Close only About and compare the selected child and settings before further input.

Link clickability and the full information-control matrix belong to shared UI
coverage. This journey identifies the installed release and license and resumes
management. It does not establish external-handler or installed-license opening
acceptance; those obligations retain their qualification owner.

### E2E-031

Implementation status comes from the inventory. The UI/E2E allocation
compositions passed independently: 152 in `20260928T164519Z-04c77547`, 153 in
`20260928T165013Z-99382b18`, and 154 in `20260928T165312Z-34f506c3`, including
collection and cleanup. Coverage was refreshed after each pass. Task 039's
shared attachment, Privacy and window-switch qualifications also passed with
owned cleanup. Case 155 passed its complete export journey in
`20260929T203255Z-29d6637e`, including collection, owned cleanup and refreshed coverage.

**Feedback drafts, validation and attachment review.** Cases 152, 153, 154, 155.

Bindings: flow = draft-reopen / validation / attachments / diagnostic-export.

1. P0; draft: FEED01 → UI16(body,email) → FEED04(bold) → UI16(emoji) → FEED06(single file) → FEED03; validation: FEED01 → FEED09(empty rejection) → UI16(body,email); attachments: FEED01 → FEED06(two files) → FEED07; export: FEED01 → FEED09(finished diagnostics and Download available) → FEED08 with chooser cancel/failure/success branches.
2. Draft: DESK10(feedback) → FEED05 → FEED10(dialog,compare) → FEED10(app-exit,reset). Validation: FEED10(dialog) → FEED09(recovered valid state). Attachments: FEED13(remove one) → FEED07(remaining file). Never FEED11.

Case 152 binds `parent_feedback_draft.PLAN`: type `body-first`, apply bold to
`Synthetic`, then append the emoji through the shared `body-smoke` binding.
The full formatting/removal/undo matrix stays in UI tests using the same worker
composites. Supply the `single` fixture (`Synthetic note.txt`, 26 bytes)
through the guarded chooser and independently read its metadata. The shared
`FeedbackDraftJourney` compares the complete formatted draft and reply address
after window switching, Privacy and dialog reopening, then observes empty text,
reply address, formatting and customer-file list after Parent exits/relaunches,
before any new input. Fresh diagnostics remain separate from the customer draft.

Case 153 rejects an empty send, then types the shared ordinary body and reply.
Closing/reopening must retain the authored body/reply and recover the usable
draft after the refused empty submission. The full ASCII/emoji, hidden-character,
reply and excessive-formatting matrices stay in UI tests. No backend reset or
valid submission is permitted. Stage bindings live in
`parent_feedback_validation.PLAN`.
The guarded invalid-only Send route supplies rejection evidence; FEED11 valid
delivery remains outside this recipe. Error-report review on all three surfaces,
diagnostic privacy, byte bounds and role authorization retain their separate
customer/engineering obligations; this local case does not establish them.

Case 155 reuses shared `attachment_composition.diagnostic_export` and its matching
`onpc_feedback_read::diagnostic_export` for named Save, receipt-bound FILE08
inspection and independent same-dialog/draft return. `DiagnosticExportJourney`
compares copied public endpoint/PID and `synthetic-first` body/reply/attachments
and controls. `diagnostic_export_actions` retains the Save owner through bounded
ZIP inspection and cleanup; qualification code is not a consumer API.
`parent_diagnostic_export.PLAN` / `onpc_feedback_privacy::_diagnostic_export`
compose the complete case: observe collection before feedback entry, edit the
synthetic body/reply, Cancel a fresh chooser, then
`save_handoff(destination='unwritable', draft='synthetic-first')` to the fixed
`~/Downloads/Unwritable`. Require the app's exact save error before the successful
export fragment. `diagnostic_export_actions(preservation=True)` independently
checks empty output after both Cancel and failed Save; each has a single-use
read checkpoint under the same fixture owner. Compare captured same-dialog
drafts after Cancel, failure, successful export and Privacy. ZIP inspection
also rejects the declared synthetic account, email, body and file-content values.
The complete case passed in `20260929T203255Z-29d6637e`; affected Save/Cancel
and export qualifications passed in `20260929T203754Z-7b47ee7e` and
`20260929T204158Z-388a25b4`, including collection, owned cleanup and baseline
restoration. No valid Send or original-log inspection is permitted.

### E2E-032

Implementation status: All cases pending.

**Send reviewed feedback and read service acceptance.** Cases 156.

Bindings: delivery = success.

1. P0 → FEED01 → UI16(reviewed body,email) → FEED06 → FEED03 → FEED05 → FEED11.
2. FEED09(sending,success) → TIME03(5 seconds with thanks still present) → FEED14 → FEED01 → FEED03(cleared).

### E2E-033

Implementation status: All cases pending.

**Recover feedback sending after reconnecting.** Cases 157.

Bindings: delivery = retry.

1. P0 → FEED01 → UI16 → FEED06 → FEED03 → FEED05.
2. LIFE06(disconnect).
3. DESK10(feedback) → FEED11 → FEED09(retry).
4. LIFE06(reconnect before retry deadline).
5. DESK10(feedback) → FEED09(automatic success) → FEED14 → FEED01 → FEED03(cleared).

### E2E-035

Implementation status comes from the inventory. Case 158's reduced installed
composition passed in `20260928T165553Z-a580e06a`, including collection and
cleanup; coverage was refreshed. Case 159 passed its complete save-order
journey through `save_order.PLAN` / `onpc_feedback_states::run_save_order` in
`20260929T070054Z-c0f58f19`, including the single Parent window projection,
both named-child saved values and restart readback; coverage was refreshed.

Parent desktop preparation belongs to the shared installed envelope, with no
case-specific idle step; see the [shared entry contract](../../tests/e2e/README.md#shared-system-and-account-entry-helpers).

Parent reopening uses `onpc_lifecycle::reopen(journey, 'parent', prior_window,
'management')` with a fresh `prior-window` observation. Bind the stages in
`journey_blocks.parent_reopen()`, also used by `app_restart.PLAN`, including
`initial-selection`, before selecting each child
to compare saved values. Task 028 qualifies only this LIFE01 slice.

**Choose allowances and save edits.** Cases 158, 159.

Bindings: flow = boundaries / save-order.

Cases 158 and 159 compose `journey_blocks.allowance_selection` and
`onpc_allowance_selection::select`, the same block used by host UI through
`tests.support.gui_blocks.select_allowance`. Case 158 saves preset 15 and then
custom 1 through this block; reopening reads the final saved 1. Case 159 starts from
Jordan's enabled saved zero, selects 15 minutes and verifies saved 15.
Choose Custom with the same block, then perform rapid 5→6.
Riley's custom 7 entry and the named-child/rapid-save qualifications reuse the
same block. Case 159 uses the customer bindings of `custom_save_entry` and
`ordinary_custom_save` (`qualification=False`); refusal exercises and the
qualification's extra child reload stay in the harness checks. The rapid editor
guard checks selected-child identity while navigation is inhibited by saving.
Both children's final values are independently read before and after reopening.
The current API bindings require installed requalification. All UI and E2E tests follow the
[mandatory sequence](../Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception);
popup/highlight/cancellation assertions and alternate choice-selection routes
are excluded.

1. P → PARENT03(off,zero) → FLOW16(allowance=0,final=on).
2. boundaries: save preset 15, then custom 1 through PARENT06 → PARENT08 → PARENT03 → UI12; save-order: PARENT06(rapid edits) → PARENT08(saved final value) → PARENT02(other), retaining real save ordering. Local rejection and repeated-launch singleton behavior remain shared UI coverage.
3. LIFE01(Parent) → PARENT02(each child) → PARENT03 → UI12(last accepted values).

### E2E-036

Case 161's historical `zero_total.PLAN` / `onpc_zero_total::run` established
local zero-balance Revoke availability, with no customer journey. It is excluded
from E2E scheduling and has no executable inventory binding. Its current owner
is `tests/ui/test_preview_smoke.py::test_parent_zero_balance_keeps_revoke_unavailable_with_limits_on_and_off`,
which passed focused UI validation. The stable case ID and completed task history
remain; no replacement E2E task is created. Case 160 retains the actual daily-only
revocation result below.

**Revoke when there is no active grant.** Cases 160, 161.

Bindings: balance = daily-positive / zero-total.

1. Case 160: FLOW13(grant-only,soft included) → C → FLOW08(soft) → APP04 → P → FLOW02(positive daily,off) → UI17(on) → PARENT08 → PARENT09(G=0).
2. PARENT17 → PARENT18(cancel) → C → APP04 → P → PARENT17 → PARENT18(confirm).
3. PARENT09(D unchanged,G=0) → C → APP02(soft closed) → FLOW08(allowed usable,soft/hard denied).

### E2E-037

Implementation status: All cases pending.

**Use and remember the child panel option.** Cases 162, 163.

Bindings: boundary = sign-out-in / reboot.

1. FLOW16(each child,6 daily minutes) → C(first) → TIME01 → PANEL01(default off) → PANEL02(on).
2. DESK04 → C(fresh) or LIFE02 → C(fresh); read the persisted on choice through PANEL01, close the menu and compare remaining time against actual elapsed time.
3. C(second) → PANEL01(off), then return to C(first) → FLOW08(allowed) → TIME04. The saved personal choice must neither change the peer's choice nor grant time, alter app policy or prevent natural locking. Menu mechanics and repeated off/on samples remain child UI coverage.

### E2E-038

Implementation status: All cases pending.

**Keep daily access after a grant ends and restore soft-app blocks.** Cases 164, 165, 166, 167, 168, 169, 170.

Bindings: restore = none / unlock / fresh-login / allowance-edit / toggle / app-save / revoke.

1. FLOW18(daily-dominant,soft exception) → FLOW08(allowed) → APP04; prepare Riley's activity with FLOW14 before FLOW18.
2. Use the last public grant interval and TIME03 elapsed time to cross its latest possible expiry while the child remains active and TIME01 still shows positive daily access. APP03(soft); then perform exactly the restoration table's block sequence. Do not visit Parent to learn that G reached zero.
3. On the resulting child desktop, APP02(expected existing apps) → FLOW08(new hard/soft launches), **then** FLOW09(Riley). A Parent read is permitted inside a restoring action that already calls P, or after all child-result checks. There is no implicit extra unlock before those checks.

### E2E-039

Implementation status: All cases pending.

**Leave a pending approval or request again too soon.** Cases 171, 172, 173, 174, 175, 176, 177, 178.

Bindings: flow = overlay-lock / overlay-switch / overlay-signout / overlay-close / kiosk-close / overlay-cooldown / kiosk-cooldown-same / kiosk-cooldown-other.

1. FLOW16(surface appropriate daily) → FLOW04 → REQUEST03(capture). Interruption: REQUEST09 → AUTH01. Cooldown: FLOW05 once.
2. Interruption: FLOW17(declared route). Cooldown: reopen with REQUEST01/02 and, for other child, REQUEST04(child); REQUEST09(expected public too-soon error).
3. Read Parent balances via PARENT09 before a new approval; return via request-entry → REQUEST03 → UI12. TIME03 only to finish cooldown; FLOW05(new authentication).

### E2E-040

Implementation status: All cases pending.

**Refresh accounts and remembered selections after account changes.** Cases 179, 180, 181, 182, 183.

Bindings: change = add-child / remove-selected / remove-last-child / ineligible-approver / missing-remembered-child.

1. V(parent,fresh) → ACCOUNT01 → ACCOUNT02 only for declared initial spare account preparation. Use FLOW16(on,30) for every child whose request form will be inspected, then P or request-entry → PARENT03/REQUEST03(capture). For removal cases all removed children are logged out first; no personal account is borrowed from another test.
2. ACCOUNT01 → ACCOUNT02(variant change). Parent stays open; request windows exit with REQUEST12 before the change.
3. DESK10(Parent) → UI13/PARENT19 → PARENT03 → UI12, or request-entry → REQUEST03 → UI13(eligible fallback).

### E2E-041

Implementation context: The search/filter composition is implemented in
[search_filters.py](../../tests/e2e/search_filters.py); other matching flows remain pending.

**Search the app list and edit match rules.** Cases 184, 185, 186, 187, 188, 189.

Bindings: flow = search-filters / match-editor / match-reopen / shared-launchers / special-paths / pattern-files.

Native identities/defaults come from FIX06's [finite native declaration](E2E-Building-Blocks.md#native-fixture-preparation)
and `tests/fixtures/native_assets.py`. Reuse `native_fixtures.fixture_actions()`
for fresh baseline verification and `check_catalogue()` for the public initial defaults;
preparation assigns no policy. Other E2E-041 bindings remain pending.
The native profile belongs to Jordan; bind selection, App Limits entry and
public row operations to that same child as described in the native contract.
Case 184 requires the fresh Jordan 30-minute FLOW16 binding
`gdm/parent/fresh/new/existing/0/30/1`, qualified by task 226a through
`fresh_thirty_allowance.JORDAN_PLAN`, `FreshThirtyAllowanceJourney` and
`onpc_parent::set_allowance`. Carry the explicit `existing` child binding through
setup and independent balance readback. Task 226b qualified the public
access/match legend through `AccessibleUI.expand_policy_legend` /
`read_policy_legend` and `onpc_app_rows::legend`, with independent full reads,
wrong-entry refusals and unchanged policies. Reuse caller-owned stages from the
[public policy legend contract](E2E-Building-Blocks.md#public-policy-legend);
`PolicyLegendJourney` owns qualification, not the complete case lifecycle.
The search/filter case uses final displayed rows and unchanged policy; it does
not repeat the separate legend content qualification.
The native launchers are already Jordan-only per-user inputs.

Case 184 owns `search_filters.PLAN`, composing the
shared operations through `onpc_fresh_thirty_allowance::search_filters`.
`native_fixtures.CataloguePolicyJourney` compares caller-declared immutable row
endpoints and exact query/match/access intersections before durable replies;
the plan's `catalogue_checks` declares the initial, name, filtered and unchanged row checks, saved
settings and independent 1800/0/1800-second balances. Complete installed acceptance
passed in `20261001T054514Z-f7691e2f` on every enabled VM, including collection,
owned cleanup and baseline restoration. This supplies no acceptance for other flows.

1. FLOW16(ample daily) → PARENT04(App Limits) → PARENT12(assets).
2. Run the corresponding finite catalogue subrecipe below using PARENT10/11/13/15/16, UI16, shared FILE05 commands and LIFE01.
3. PARENT12 → UI12(saved/expected rule) → C → FLOW08(declared positive and negative targets). Search-only checks compare rules without changing them.

### E2E-042

Case 190's original Parent Help/About control checks are reallocated to
`tests/ui/test_about_release.py::test_about_displays_release_notices` and shared
UI coverage. Its stable ID remains pending and excluded from E2E scheduling,
with no executable binding or replacement E2E task. The historical
`parent_information.PLAN` / `onpc_parent_about::run_links` qualification remains
engineering context. Rewriting it as About information and management return
would duplicate [case 151](#e2e-030), which owns that installed customer result.
Case 192 uses `kiosk_about.PLAN`,
`request_composition.KioskRequestJourney` and `onpc_kiosk_about::run`; case 193 uses
`command_help.PLAN`. Current executable status belongs in the inventory.

Overlay information uses `journey_blocks.overlay_license_read(links='summary')`
and `onpc_about::overlay_license` with the same finite binding. The fragment
enters owned About, reads product/version, license and legal-notices information,
then closes only About and reads the returned form. The full link-control
qualification remains shared UI scope. Historical `overlay_license.INFORMATION_PLAN`
qualification retains its original scope; case 191 supplies its own entry, finite choices, capture/return
endpoints and phases through `KioskRequestJourney.request_checks`.

Case 191 declares `overlay_about.PLAN` and `onpc_parent_about::run_overlay`. Fresh
Parent entry saves a 30-minute allowance with limits on, then fresh child entry
opens the overlay directly. FLOW04 selects Jamie, custom 1.25 minutes and soft
apps included before capture. The information fragment reads installed information,
closes only About and compares the captured form. Normal Cancel
returns to the child desktop. Setup/capture, information and unchanged-form
return occupy separate recorder phases; no qualification lifecycle is imported.

**Read Help, About and command usage on each surface.** Cases 190, 191, 192, 193.

Bindings: surface = parent-links / child-overlay / kiosk / command-help.

1. Active request cases 191–192: FLOW16(on,30) → request-entry(surface) → REQUEST03(capture); command-help case 193: V(parent) → qualified desktop. Case 190 has no E2E composition.
2. Overlay ABOUT01(product/version, license and legal notices); kiosk also reads its offered contact information within the restricted station. Link-control completeness/clickability belongs to shared UI coverage; no external links are invoked here. Command INFO02(each fixed command/manual).
3. UI18(About, only where opened) → REQUEST03 → UI12. No external handler is launched or closed. INFO02 leaves the parent desktop clear.

Kiosk binds FLOW16 to fresh Parent entry with limits initially off, a saved
30-minute allowance and limits on. After GDM/station entry, FLOW04 selects
Jordan, Jamie, custom 1.25 minutes and soft apps included before the form
capture. About reads product/version and all five offered legal/contact values,
with no external action controls. Close About once, compare the captured form,
then Cancel normally and independently observe usable GDM. The three phases
separate setup/capture, information reading and unchanged-form return.

Command-help binds INFO02 to `/usr/bin/oh-no-parent-control-parent --help`,
`/usr/bin/oh-no-parent-control --help`, `man oh-no-parent-control-parent` and
`man oh-no-parent-control`, in that order. Run each fixed command through the
guarded VM SSH transport as the parent fixture account and capture its bounded
stdout stream, without a terminal window or GUI text projection. Read each
help's usage, identifying description and help option; read each manual's
command identity, purpose, NAME, SYNOPSIS and DESCRIPTION. Independently check
the desktop and absence of management/request windows after each command.
Each command has a 45-second deadline; durable observations retain only semantic
results, never raw command text. The complete consumer is `command_help::execute` and
`onpc_command_help::run`.

### E2E-043

Implementation status: All cases pending.

**Use local controls and approvals while offline.** Cases 194, 195.

Bindings: surface = child-overlay / kiosk.

1. P → LIFE06(disconnect) → FLOW16 → FLOW03(hard/soft/allowed).
2. request-entry(surface) → FLOW04(entry=open) → REQUEST08 → FLOW05(soft included).
3. C → FLOW08(soft usable,hard denied) → TIME02 → P → PARENT17 → PARENT18(confirm) → C → FLOW08(soft denied) → P → LIFE06(reconnect).

### E2E-044

Implementation status: All cases pending.

**Use time across local day and daylight-saving boundaries.** Cases 196, 197, 198, 199, 200, 201, 202, 203, 204.

Bindings: calendar = ordinary / spring-forward / fall-back; time = daily-reset / rest-of-day / fixed-grant.

1. V(parent,fresh) → TIME05 → FLOW13(calendar profile) → P → PARENT09(capture) → request-entry/REQUEST08/REQUEST12 only for the declared grant estimate → C → TIME01.
2. TIME03(to declared real boundary) with APP03 where active use is needed; observe the child's expected countdown or lock first. G → V(parent,retained) → TIME05 → P → PARENT09 → UI12(calendar arithmetic). A child that locked at midnight cannot operate desktop calendar controls until legitimately admitted again.
3. C → TIME01 or GDM06(time denial), as specified by the calendar table; FLOW08(allowed) when usable.

### E2E-045

Implementation context: case 205 is registered through
`parent_error_report.PLAN` / `onpc_fresh_thirty_allowance::parent_error_report`
and passed complete live acceptance in `20261001T103654Z-6ee68021` on every
enabled VM, including collection, owned cleanup and baseline restoration.
Child-overlay and kiosk cases remain pending.

**Review or decline an error report.** Cases 205, 206, 207.

Bindings: surface = parent / child-overlay / kiosk.

The Parent editor entry reuses the guarded PARENT13 operations and public input
route delivered by [task 078a's Save/Cancel slice](E2E-Building-Blocks.md#match-editor-save-and-cancel).
The rejected input for native fixture `A.desktop` is
`/opt/onpc-test-fixtures/Rejected/*.AppImage`, outside its native target directory.
First save and capture `/opt/onpc-test-fixtures/Applications/Exact*.AppImage` as
the last confirmed rule. `rejected_parent_rule.PLAN` declares task 186's
qualification through `onpc_app_rows::rejected_parent_rule`; the reusable
`parent_reports.report_review` / `onpc_feedback_privacy::review_parent_report`
binding starts from the automatic report, reads the fixed public explanation
and `Error` category, replaces body/reply with `Synthetic feedback first` and
`first@example.invalid`, checks available actions without sending, reads Privacy
and closes normally. Repeat from an independently opened editor/report, then
compare the exact confirmed rule. This qualification supplies no case acceptance.
Case 205 composes that same review, then repeats the rejected input and uses
`parent_reports.report_close` / `onpc_feedback_privacy::close_parent_report`
to read the new automatic report and close it directly without editing or sending.
Both normal closures compare the exact last-confirmed rule through
`ParentReportJourney`; Parent offers no report-choice toggle.
The qualification and case use `match_rules.match_edit` /
`onpc_app_rows::match_edit` for both the confirmed wildcard and rejected Save;
report handling remains a separate fragment.
Precise overrides on apps with suggested patterns retain the documented reload
limitation; this fixture/custom-wildcard comparison makes no claim about that branch.

1. Parent: P → PARENT04(App Limits) → PARENT10(declared app) → PARENT13 → UI16(rejected pattern) → PARENT15(error). Request surfaces: FLOW16(on,30) → request-entry → FLOW04(custom=0.5,soft=false) → FLOW05 → reopen before cooldown → REQUEST09(error). These are the explicit public-error prefixes reused by E2E-047; its setup does not manufacture a report.
2. FEED15(review) → FEED03 → UI16(synthetic body) → FEED05 → UI02/11(surface actions) → UI18(report) → UI01(original destination).
3. Repeat the same public error: FEED15(decline) where offered → UI11(report). Parent's report window simply closes; no nonexistent report switch is assumed.

### E2E-046

Implementation status: All cases pending.

**Recover unavailable diagnostic collection.** Cases 208, 209, 210, 211, 212, 213.

Bindings: surface = parent / child-overlay / kiosk; choice = retry / without-logs.

1. Open the declared genuine failing collection with FEED01 or FEED15 and wait for FEED09(failed collection).
2. UI02(edit/Close usable) → UI16(valid synthetic body). Retry: FEED16 after genuine recovery. Without logs: FEED03 → FEED05 → FEED11(action=Send without logs).
3. Retry FEED09(ready) → FEED03 → UI18; without-logs FEED09(acceptance) → FEED14 → UI01(original destination).

### E2E-047

Implementation status: All cases pending.

**Finish or stop feedback in different user flows.** Cases 214, 215, 216, 217, 218, 219, 220, 221, 222.

Bindings: flow = no-reply / background / app-exit / retry-expired / overlay-stop / kiosk-stop / overlay-success / kiosk-success / parent-error-success.

1. P → FEED01 or public-error prefix → FEED15. UI16 → FEED03 → FEED05; LIFE06(disconnect) for retry branches → DESK10(report) → FEED11.
2. Perform the precise send-lifetime subrecipe below; FEED09 supplies sending/retry/success observations.
3. Use FEED14 only for observed thanks; FEED03 checks cleared/preserved/reset draft as specified, and LIFE06 restores connectivity.

### E2E-048

Implementation status: All cases pending.

**Approve after the displayed estimate has aged.** Cases 223–230.

Bindings: balance = daily-only / grant-only / daily-dominant / grant-dominant;
surface = child-overlay / kiosk. Each balance has both surfaces, in that order.

1. FLOW13 with the delayed-approval table below → P → PARENT09(capture D,G) → G.
   Overlay C → REQUEST02; station REQUEST01. FLOW04(entry=open,custom=0.5,
   soft=false,approver=Jamie for daily-only/grant-only, Sam otherwise) →
   REQUEST08(capture estimate and time) → REQUEST09 → AUTH01.
2. TIME03(45 seconds, same requesting session and prompt) → AUTH01(fresh) →
   AUTH02(correct) → REQUEST11(success) → REQUEST12(automatic).
3. C only for station → TIME01 → P → PARENT09 → UI12(expected interval from
   public starting balances and elapsed active/away time). After five seconds
   from success, return to the same form and use FLOW20 for an immediate
   second 0.5-minute request. Read its increment too; a waiting estimate must
   neither freeze the earlier balance nor extend a grant twice.

| Balance | Public preparation for this family | Expected effect while waiting |
| --- | --- | --- |
| daily-only | Daily 6, no grant. | Overlay consumes daily time; station leaves that child's daily time unconsumed. |
| grant-only | Daily 0, approve 4 minutes. | Grant elapses on both surfaces. |
| daily-dominant | Daily 0, approve 4, then daily 10 while still enabled. | Daily dominates throughout; its use depends on the requesting surface as above. |
| grant-dominant | Daily 6, request 4 additional minutes. | Grant remains dominant and elapses on both surfaces. |

At the prompt require at least 120 seconds of usable time and a dominant-balance
gap exceeding 90 seconds where both balances are positive. Predeclare the
comparison intervals, including navigation/authentication/confirmation time.
The elapsed 45 seconds must be distinguishable from a frozen estimate with the
available display precision. No other user changes settings during the prompt.
This is normal time spent deciding a request, not an artificially delayed
authentication service. Zero-time overlay entry is impossible; zero-time station
approval belongs to 50/126–127. Exact equal positive operands that cannot be
distinguished publicly remain arithmetic unit coverage; both-zero is covered by
those station cases.

### E2E-049

Implementation status: All cases pending.

**Change temporary app permission on every supported launch route.** Cases 231–246.

Bindings: route = native-grid / native-desktop / native-file-manager /
native-command / snap-grid / snap-command / flatpak-grid / flatpak-command;
surface = child-overlay / kiosk. Each route has both surfaces, in that order.

1. FLOW16(Jordan,on,30) → AppSet(A,H,S for the declared route) → C(fresh) →
   FLOW08(A usable,H/S denied). Leave A with APP03 → APP04. All later child
   returns retain this desktop; S supports a separate new-window launch.
2. Run three rows, each as request-entry(surface) → FLOW20(entry=open) →
   APP02/APP04(existing activities) → FLOW08(S via declared route). Requests
   add 0.5 minutes: **Jamie/exclude → Sam/include → Jamie/exclude**.
   Each real prompt must identify the selected approver. Initial exclusion keeps
   S unavailable; inclusion opens S and records a new activity; replacement
   exclusion requires that activity's closure.
   After each row A remains usable and a new H launch remains denied. If the
   blocked grid entry is hidden, observe that and use the recipe's explicit
   command denial witness; an included grid entry must become launchable.
3. P → PARENT12(A,H,S) → UI12(original saved choices). Temporary approval
   must not rewrite the parent's access selections. Finish after the last
   excluded result; no natural wait for the long combined grant.

This completes route × request-surface coverage, using both approvers and the
three distinct permission results inside each case. Approver identity does not
multiply the soft-choice sequence. Baseline rule permutations remain in 62–109;
this family owns alternating **temporary** permission, existing-window effects
and fresh launches on that route. Do not reproduce every allowance boundary or
game-display mode here.

### E2E-050

Implementation status: All cases pending.

**Alternate homework, games and time sources over repeated sessions.** Cases 247–250.

Bindings: surface-order = overlay-first / kiosk-first; departure = retained /
fresh. Order is overlay-first-retained, overlay-first-fresh,
kiosk-first-retained, kiosk-first-fresh. Each case is one uninterrupted attempt
with **three complete cycles**, not three dependent tests. Budget: 5400 seconds
including setup and cleanup; expected active journey 25–50 minutes. Start with
enough time before local midnight to finish. Never move the clock.

1. FLOW16(Jordan,on,0) → AppSet(W Always Allowed editor, S Soft Blocked real
   offline game, H Hard Blocked). Prepare Riley's unrestricted W activity with
   FLOW14. No grant exists. Stage a synthetic notes file for Jordan; FILE08
   opens it and FILE09 records each cycle's distinct text when access permits.
2. Execute every row of the repeated-routine table below for cycle **1, 2, 3**.
   `first`/`second` are the variant's form order. The six approvals in rows
   2/3/4/5/7/8 use Jamie/Sam/Jamie/Sam/Jamie/Sam in cycles 1/3 and the reverse
   parents in cycle 2. Every request uses a fresh system prompt. Before editing,
   REQUEST03 compares shared fields with that child's latest choices on either
   form, and the parent selector with this surface's own remembered parent.
3. P → LIFE01(Parent) → PARENT02(Jordan) → PARENT03/PARENT09/PARENT12 reads
   enabled/zero allowance/zero grant and the original W/S/H choices. Visit
   Riley with FLOW09. Only now end the attempt.

| Cycle row | Exact composition / finite input | Required result before the next row |
| --- | --- | --- |
| 1 Homework on daily time | FLOW16(on, allowance=12×cycle) → PARENT09 → C → FILE08(W file if not open) → FILE09(replace with `homework cycle N`, Save) → APP04 → FLOW08(S/H denied). | D≥120 seconds, G=0; usable work and blocked game. Reopen the saved file after a fresh login; only retained entry compares an old window. |
| 2 Earn game time | request-entry(first) → FLOW20(1 minute,include) → FLOW08(S usable) → APP05(windowed,level 1 in cycles 1/3; fullscreen,level 1 in cycle 2) → APP03 → APP04. | New time follows max(D,G)+60; W survives any retained return; game is playable. |
| 3 More game time | request-entry(second) → FLOW20(0.5,include); retained S: APP04 → APP03; S ended by declared logout: FLOW08(S usable) → APP05(cycle mode,level 1) → APP03 → APP04. Then FLOW08(H denied). | Repeated inclusion extends current time without closing an existing game. Fresh departure ends old windows normally and requires a new playable game. |
| 4 Return to homework | request-entry(first) → FLOW20(0.5,exclude) → APP02(S closed) → FLOW08(S denied); FILE08(W) if this case's logout ended that window; FILE09(W,`work again cycle N`,Save). | Same-session/retained S closes; after fresh departure verify denied new launch, not closure by approval. Work remains usable. |
| 5 Grant-only game break | request-entry(second) → FLOW20(0.5,include) → FLOW08(S usable) → APP04; P → PARENT06(12×cycle+1) → PARENT08/PARENT09 → PARENT06(0) → PARENT08/PARENT09 → C. | Both enabled allowance edits preserve the original grant deadline; D becomes zero. Existing retained S stays open, new S/H launches are denied. Check this before another approval. |
| 6 Turn limits off, then on | P → UI17(off) → PARENT08 → C → TIME01(absent) → FLOW08(H/S denied); P → UI17(on) → PARENT08/PARENT09 → C(time denial). | Off removes time restriction but preserves app blocks. On with saved zero clears all old grant time; correct credentials alone cannot enter. No hidden-app claim behind the lock. |
| 7 Short approved visit to natural exhaustion | G → FLOW20(kiosk,2 minutes,include in cycles 1/3; exclude in cycle 2) → FILE08/APP04(W) → FLOW08(S expected) → APP03 → TIME04 → DESK08(time denial). | Actual activity ends in a natural lock. A retained work window is still not inspected behind that lock. |
| 8 Recover, then finish this cycle | G → FLOW20(kiosk,3 minutes,opposite soft choice to row 7,retained unlock) → APP04(W captured in row 7) → APP03; APP02(S closed) when row 7 left S open and replacement excludes it; FLOW08(S expected,H denied). Then leave-child → P → PARENT17/PARENT18(confirm) → PARENT09 → C(time denial) → G → FLOW09(Riley). | Both variants retain their row-7 work through this natural lock. Replacement permission has the declared game result; unused grant revocation leaves D=G=0. Riley's same activity works. No grant is carried into the next cycle. |

At **each departure from Jordan to another account/station**, retained uses
DESK03 and fresh uses DESK04 while access is positive. The latter case therefore
tests saved work and new windows after departure, not survival through logout.
After natural lock both variants have a retained locked desktop: replacement
approval uses retained unlock, then the next departure again follows the
variant. Overlay requests alone never log out. Declare each window's lifetime
in the ledger and branch APP04 versus FILE08 from that recorded action, not
from whichever app happens to appear. Use a supported new-instance launch for
S when an old S window is being preserved. For fullscreen, DESK12's qualified
normal reveal route is mandatory. If navigation exhausts a required margin,
preserve the failure instead of inserting an unplanned grant.

### E2E-051

Implementation status: All cases pending.

**Alternate two children's work and game routines without mixing their choices.**
Cases 251–252; first child = Jordan / Riley.

One continuous attempt per case, four rounds, two child visits in every round;
5400-second bound, expected 20–45 minutes. Each child has W Allowed, S Soft and
H Hard; use distinguishable W text and different game progress. All departures
retain desktops. Parents Jamie and Sam alternate management visits, each using
their own normally opened Parent window. A later visit reselects the named
child and reads current settings before changing anything; neither parent
assumes its earlier displayed values are still current.

Number the management visits 1–8 in actual visit order: Jamie manages odd
visits, Sam even visits. Approval uses Sam on overlay and Jamie at the station,
independently of the managing parent. These are explicit selected-parent inputs
to FLOW20; no remembered selection is silently substituted.

1. AppSet for both children → FLOW16(each,on,30) → G. For each child:
   FLOW15(fresh) → FILE08(own synthetic notes file) → FILE09(`child role initial`,Save)
   → APP04(capture own W) → DESK03. These independently supplied W observations
   are the inputs to later FLOW09 visits, not an earlier test's windows.
   Set Jordan's request custom 1.25/soft included, Riley's custom 2.5/soft
   excluded, station approver Jamie, overlays Sam, using FLOW04/REQUEST12.
2. For each round below visit the variant's first child then the other;
   reverse that visit order on even rounds. For the selected child:
   P → PARENT03/PARENT09/PARENT12(capture both children separately) →
   FLOW16(selected allowance,final off) → UI17(on) → PARENT08/PARENT09.
   This explicit off/on change clears that child's prior grant. Follow the
   table's time/permission route, then FILE09(own W,`child role round N`,Save)
   → APP04 → FLOW08(S expected,H denied); when included, APP05(windowed,level 1)
   → APP03 → APP04 records playable game progress. Return to Parent, select the peer,
   read **before** any edit and compare with the peer's last observation;
   FLOW09(peer,W) and REQUEST03 on its declared next request-entry verify
   independent work and remembered choices. Close that form with REQUEST12.
3. After round 4, confirm Revoke for **only** the grant-only child. It can no
   longer unlock; the daily-only peer still uses W with its configured S rule.
   PARENT03/PARENT09/PARENT12 on both children and FLOW09(peer) finish the case.

| Round | Jordan | Riley |
| --- | --- | --- |
| 1 | Daily 12; overlay request 1.25,exclude: homework. | Daily 0; kiosk request 15,include: game. |
| 2 | Daily 0; kiosk request 15,exclude: homework. | Daily 24; overlay request 2.5,include: game. |
| 3 | Daily 36; overlay request 1.25,include: game. | Daily 0; kiosk request 15,exclude: homework. |
| 4 | Daily 0; kiosk request 15,include: game. | Daily 48; no grant, S remains blocked: homework. |

Use FLOW20 for each actual approval, then explicitly save the child's preferred
custom value (1.25 or 2.5) and the row's soft choice with FLOW04/REQUEST12 without
another approval. This separates a 15-minute grant from remembered custom text.
Before peer-comparison visits require its usable balance to exceed 120 seconds;
allow only elapsed-time reduction of its grant and measured active daily use.
No unexpected allowance, app-rule or request-choice change is tolerated. If a
peer naturally expires before this check, that is a failed preparation margin,
not evidence of cross-child interference and not an invitation to grant time
silently. Work/game names describe activities, not nonexistent product modes.

### E2E-052

**Implementation:** pending metadata only; no executable binding or installed
qualification. **Lunar Client login autostart cannot bypass an ungranted soft
block.** Case 253, route `appimagelauncher-login-autostart`; one independent
1800-second attempt, not a VM experiment or process/rule inspection.

Use Jamie/Jordan fixture roles, never the reporting household's account names.
FIX05 requires the [manually prepared real-app profile](E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
after normal restore. Tasks 296, 296a and 296b separately qualify Lunar/tray,
Minecraft activity and continuous login observations before case composition.
Bind exact original AppImage path, integrated launcher,
same-directory `Lunar Client-*.AppImage` pattern, tray/autostart settings, local
world and one observable in-world action before implementation. The ordinary
shared SSH command invokes that original AppImage as the active child desktop user with AppImageLauncher integration
intact; it does not extract or invoke an inner runtime. Use the same bytes/route
at all checkpoints. N is an existing unrelated allowed native app with a
declared normal input/result, not Minecraft's embedded Java executable.

| Step | Composition and required public result |
| --- | --- |
| 1 — allowed control | P0 → FLOW16(on,120) → PARENT09 reads daily remaining and zero grant; Lunar initially Allowed. G → C(fresh) → FLOW08(Lunar,usable) → APP03(Lunar starts Minecraft) → APP03(local-world action). Exit Minecraft normally, close Lunar to tray and observe APP06(present). LIFE02 → child-first GDM07, with UI22 armed before login submission. Observe working autostart by 90 seconds after DESK01, restore Lunar from its qualified tray control, start/use Minecraft again, then exit Minecraft and genuinely Quit Lunar with observed disappearance. |
| 2 — soft, no grant | G → P(fresh/new after reboot) → FLOW03(Lunar,saved version pattern,Soft) → PARENT12/PARENT09 confirm Soft and zero grant. G → C(retained) → FLOW08(original-AppImage command,access denied) → APP06(absent) → FLOW08(N,usable). Desktop remains usable from daily time. |
| 3 — active time-only reboot | FLOW20(overlay,Jordan,Jamie,15,exclude,same child) → G → P(retained) → PARENT09 reads positive grant → G → C(retained). LIFE02 → child-first GDM07 under the same public observer contract. For the complete login interval through 90 seconds after DESK01 require no Lunar tray/background control, usable Lunar window or Minecraft. Then FLOW08(original-AppImage command,access denied) → APP06(absent) → FLOW08(N,usable). Only after these results, G → P(fresh/new) → PARENT09 confirms the grant is still positive → G → C(retained). |
| 4 — explicit soft permission | FLOW20(overlay,Jordan,Jamie,15,include,same child) → FLOW08(same Lunar command,usable) → APP03(start Minecraft) → APP03(same local-world action). Exit Minecraft and genuinely Quit Lunar normally; independently observe both gone. No app-policy or allowance edit. |
| 5 — replacement exclusion | FLOW20(overlay,Jordan,Jamie,15,exclude,same child). Repeat step 3's read-only balance visits, reboot, child-first login, complete 90-second autostart observation, one explicit command denial and usable N. The replacement grant stays active; exclusion must restore blocking despite positive time. |

Use fresh observations and unique stages for each repeated operation. Read the
public grant balance through PARENT09 and require more than 600 seconds before
each denied boot transition; read it again only after the blocked observations
to verify it stayed positive. Those Parent visits are read-only and use the
explicit fresh/retained entries above. Fixed requests add to the
larger balance, so do not assert a 15-minute total. An insufficient margin or
expired grant fails the declared precondition, never silently changes the case.
Do not open Parent, resave policy, toggle limits or issue another approval between
reboot and the blocked observations; the child must be first to sign in.

The login observer must be ready before submission and cover every relevant
public surface as it becomes available, without collecting secrets. A usable
Lunar/Minecraft surface during a denied interval fails even if later closed.
Fail incomplete observation rather than inferring absence. The shared command
attempt supplies positive access-denied evidence; command echo, generic failure,
hidden launcher or missing network/game assets cannot replace it. The allowed
autostart and explicit-soft-approval controls prevent a broken preparation from
masquerading as enforcement. Each allowed Minecraft launch has a 180-second
readiness bound; failure retains evidence without input replay or downloading
assets mid-case. A provider/profile unable to meet the fixed bounds stays pending.

These are required checkpoints in one case, not optional variants. E2E-019 owns
generic routes and other-user isolation; case 189 owns new wildcard versions;
E2E-022 owns general lifecycle persistence. This case adds the AppImageLauncher
autostart/Minecraft path without changing active-grant session behavior. No
backend assertion, synthetic grant, clock change or service restart is allowed.

## Additional finite branch recipes

### App catalogue and matching

Every row starts in the selected child's App Limits and finishes by reading
saved rows and, when stated, using the app as the child.

| Case | Exact block/data expansion |
| --- | --- |
| 184 search-filters | PARENT10 exact-name query → PARENT11 precise plus Allowed → UI13/UI12 exact expected intersection of the real declared catalogue; clear query/restore filters and compare PARENT12 initial policies. Compose `onpc_app_rows::search` / `filter` / `read_rows` with caller-owned stages and `journey_blocks.filter_screens`; use `native_fixtures.catalogue_rows` for the exact expected set. The native profile is Jordan-bound (`existing` text/filter child bindings and `existing-parent-app-rows`); unprefixed rows target Riley. A fresh case plan owns its lifecycle, rather than inheriting `CatalogueJourney`. UI's `test_preview_smoke.py::test_catalogue_query_and_representative_filter_results` checks each query source, individual categories, empty sets and representative query/filter intersections, without multiplying independent choices. |
| 185 match-editor | PARENT13 → UI16 → PARENT15 saves a same-directory wildcard. Save a wildcard for a different directory and observe the real broker's failed-save report, close it and reread confirmed choices. Tasks 078/078a own the UI matrix for precise target/basename, empty/unrelated input, Cancel and Reset, including exact explanations and unchanged values. Real saved-rule and enforcement observations remain E2E. |
| 186 match-reopen | Save custom same-directory wildcard; change access to Allowed; LIFE01 → PARENT02 → PARENT12 verifies remembered custom wildcard. Save precise on an app with a suggested pattern; reselect the child and reopen Parent, reading the documented suggested pattern each time. Reselect precise before a subsequent save. Repeat restoration after a customer-rejected pattern save, closing its report before reading. This records the current limitation, not desired new behavior. |
| 187 shared-launchers | Two visible launchers for one supported app: PARENT16(first,Hard) → PARENT16(second,Allowed); C → FLOW08(each supported launch,denied). P → allow first → C → FLOW08(each,usable). Reverse which launcher holds the block and repeat. No claim of independent rules overriding the shared target. |
| 188 special-paths | For a known native app whose displayed precise path contains a space, then a comma, FILE05 copies its executable to the declared second name/location. PARENT16(Hard) → C → FLOW08(original and identical copy,denied), with existing distinct N usable. Repeat under Soft with no exception. These supported path cases do not assert universal copied-program control. |
| 189 pattern-files | Save a same-directory version wildcard for the prepared AppImage. FILE05 adds the next matching version and a nonmatching file; FLOW08 matching denied and existing nonmatch usable. The new nonmatch may require the documented refresh: wait up to 60 seconds through TIME03/APP02 read-only observations, then perform one declared launch. A failed uncertain launch is not retried as if it never happened. A pattern unable to preserve existing nonmatches must report failure and retain the previous rule. |

No screenshot geometry or file/process introspection supplies an app result.
FIX06 verifies reusable baseline sources; FIX04 transfers attempt inputs only.
At the declared journey checkpoints, FILE05
performs copies/renames and LIFE04 performs package changes through shared
commands; Parent's UI performs rule changes. Supported asset identities and normal
launch commands must be specified before implementation; absent assets or
inaccessible required public observations leave the consumer pending.

### Expired grant with daily time remaining

FLOW18's time away lets the grant elapse while daily usage is not consumed by
that inactive child. Returning with G>0 retains the soft exception. Then let G
reach zero while D is still positive. Establish those public inequalities before
choosing the action; never relabel a failed profile.

| Case / action | Customer blocks after natural grant expiry | Required child result |
| --- | --- | --- |
| 164 none | APP03(S) → FLOW08(S,new launch) | Existing soft activity and new soft launch usable; no lock while D>0. |
| 165 unlock | DESK05 → DESK08(success) → APP02 → FLOW08 | Existing matching soft activity closes; new hard/soft launches denied; A remains usable. |
| 166 fresh-login | DESK04 → C(fresh) → FLOW08 | New hard/soft launches denied. Logout ends prior activities; no retention claim. |
| 167 allowance-edit | P → PARENT06(larger allowance,still on) → PARENT08 → C(retained) | S stays open and usable, new hard/soft launches denied. |
| 168 toggle | P → UI17(off) → PARENT08 → UI17(on) → PARENT08 → C(retained) | Old S remains open; grant is cleared and full launch blocks apply. |
| 169 app-save | P → PARENT13(unchanged S rule) → PARENT15(Save) → C(retained) | Unchanged saved block restores launch denial without closing the already-open S. |
| 170 revoke | P → PARENT17 → PARENT18(confirm) → C(retained) | G stays zero, D stays available, S closes and new hard/soft launches fail. Unlike 160, an expired grant existed before Revoke. |

The already-open hard-blocked-app preservation branch of approval has no
declared reproducible customer setup in this catalogue. Retain its exact
engineering obligation; do not secretly open a blocked process, alter policy
outside Parent, or count soft-app preservation as that branch.

Case 139 saves daily allowance 4 minutes and H Hard Blocked before removal.
After reinstall, read the retained 4-minute allowance, H rule and zero grant
before editing. Reapply by changing the enabled allowance to 5 and H from
Always Allowed to Hard Blocked, observing both saves. Selecting an already-set
toggle without a change cannot demonstrate reapplication.

### Pending approval and account changes

FLOW17 is qualified separately for each route. Lock, Switch User and sign-out
use the shared system helpers with explicit source-session checks; app close
requires a real supported way to close the requesting app while the
system prompt remains open. Escape on the system prompt merely cancels
authentication and does not qualify app-close or session-leave.

Use shared lock/switch/logout commands even when an approval modal is open;
accessibility of Shell menus is not a gate. If the supported system route itself
is unavailable, retain the case pending with that blocker. Do not replace app
Close/Cancel, natural expiry or normal logout with a signal, forced termination
or private callback. On return, inspect the original balance and
restriction before new approval, and require a new system prompt.

Cooldown cases 176–178 measure from the first successful approval to the next
Request action. Reopening must complete within five seconds for the too-soon
branch; if no supported route can do so, record that prerequisite gap. Do not
extend the product cooldown or delay a response. Cases 206/207 and the request
error-report sending cases have the same public-error prerequisite.

Accounts in cases 179–183 are disposable spare accounts, prepared independently.
Shared account operations validate administrator authority through AUTH04.
Remove only logged-out spare children, retaining an administrator to finish the
journey. For 182, both station and overlay remember Sam before ACCOUNT02 changes Sam
to standard; reopen and select the remaining eligible Jamie. For 183, station
remembers Jordan, Jordan is removed while logged out, and station falls back to
Riley with Riley's own request values. A missing eligible replacement uses the
separate empty-account case instead.

### Feedback local values

Cases 152–155 run without external submission. Public state or validation
messages must establish the result; a private draft, DOM, transport payload or
collector read is never substituted.

Attachment inputs reuse the shared
[chooser handoff and consumer guidance](E2E-Building-Blocks.md#attachment-chooser-handoff):
prepared finite file batches, public APIs and independent app results. Extend
its fixed two-file binding for the selected table row in the shared helpers,
not a case-local chooser driver. Cancel requires no candidate selection or
folder browsing. The Open qualification does not cover case 155's Save route.
For Save, prepare exact destination permissions through shared commands and
supply the path/name through supported chooser APIs and minimal shortcuts.
The product still performs the save and reports its own failures. Inspect only
the resulting customer-selected artifact through FILE08's bounded filesystem/
archive APIs over guarded SSH, then independently reread the feedback draft.
Files, archive viewers and editors add no acceptance requirement to this route.

| Owner | Complete finite data and checks |
| --- | --- |
| 152 formatting/draft | `body-smoke`: ordinary text, bold first word, emoji; public range attributes and exact text. Include one file and reply address for preservation and app-exit reset. UI owns heading, all inline formats, numbered/bulleted list, quote, code, link, clear/reapply and undo/redo through the same `onpc_format` composites and public semantic readers. |
| 153 text/email | Empty-send rejection followed by authored body/reply retained through normal dialog reopening, permitting the parent to continue preparing the report. UI owns empty/whitespace/valid body, reply variants, 5000/5001 UTF-16 ASCII and emoji, hidden controls and excessive formatting, including invalid-send preservation. |
| 154 attachments | Choose the actual shared two-file batch, review accepted names/sizes and remove the unwanted file, leaving the intended attachment. UI owns chooser Cancel preservation, five/six files, 5 MiB/5 MiB+1 per file, no-diagnostics 8 MiB/8 MiB+1 total, atomic invalid multi-selection and names 180/181/hidden characters. Empty filename remains engineering validation. |
| UI original file change | Attach the shared 26-byte text file, change its original to 34 bytes, observe the retained attachment's original size, remove/re-add and read the new size. UI performs real frontend file loading through a fixture chooser. Byte immutability beyond public metadata remains transport coverage; FILE09 stays available for explicit engineering qualification. |
| 155 diagnostic ZIP | Observe collection, then save via FILE03. Cancel preserves draft and prepared archive. Prepare an actually unwritable destination through shared fixture commands, verify its permissions as the saving user, observe the app's save error, then choose a writable location. Bind FILE08 to the exact newly saved ZIP and inspect it through the shared read-only SSH archive helper: system-information entry, Parent/Child/Kiosk/Broker folders, empty folders where applicable, and actual bounded contents. Independently reobserve the same feedback dialog and preserved draft. Do not open original product logs or substitute a staged ZIP. |
| 155 privacy | FEED05 reads what is sent, optional logs/files/email and retention disclosure. Review exported synthetic data for forbidden personal values. Absence in one archive is not a proof of every producer's sanitization; all privacy, date-retention and byte bounds keep their engineering tests. |

Formatting complexity and hidden-character sets require fixed reviewed input
fixtures; no random text, unbounded payload or screenshot-only validation.
The exact total including diagnostics is tested only when its size is publicly
available; otherwise the deterministic no-diagnostics 8 MiB boundary supplies
the customer case and combined-byte limits remain engineering qualification.
Removing diagnostics and adding them again uses UI17 → FEED09 → FEED03.
Kiosk has no chooser/download/preview route; its in-app Privacy remains readable.

### Sending, background completion and report exits

Every send needs separately explicit authorization for reviewed synthetic
content and a supported dedicated recipient profile. Documentation grants none.
The customer accepts the app's actual service confirmation; mailbox delivery,
transport idempotency and payload equality remain separate integration work.
One action is issued once; uncertain input is never replayed.

| Case | Exact branch after preparation and one Send |
| --- | --- |
| 214 no-reply | FEED09(success) → TIME03(5 seconds) → UI03(thanks without reply follow-up) → FEED14 → FEED01 → FEED03(cleared). |
| 215 background | Start offline, FEED09(retry) → UI18(ordinary feedback only) → LIFE06(reconnect). Keep Parent open and UI11(feedback/thanks); reopen feedback after the bounded success interval and FEED03(cleared). If sending remains active, read FEED09 until acceptance; no inference from elapsed time alone. |
| 216 app-exit | Offline FEED09(retry) → UI18(feedback) → UI18(Parent) → LIFE06(reconnect) → PARENT01 → FEED01 → FEED03(reset, no resumed outbox). Do not claim an earlier request could not have reached the service. |
| 217 retry-expired | Offline FEED09(retry) → TIME03(up to the actual 15-minute retry window, with observation checkpoints) → FEED09(expired) → FEED03(preserved draft and duplicate-risk explanation). Reconnect and close; do not submit again. Budget 1800 seconds includes preparation and cleanup. |
| 218 overlay-stop / 219 kiosk-stop | Offline FEED09(retry) → FEED17 → UI03(stop warning) → FEED18(stay) → FEED17 → FEED18(stop) → UI11(report) → DESK01 or GDM01. Restore Internet access through the same LIFE06 VM helper from that surface; no Parent visit/login. A stop cannot recall a request already accepted. |
| 220 overlay-success / 221 kiosk-success | FEED09(acceptance) → TIME03(5 seconds) → UI01(thanks still showing) → FEED14 → UI11(report) → DESK01 or GDM01. Original request flow exits only after manual dismissal. |
| 222 parent-error-success | Parent's customer-rejected rule automatically opens its report; FEED09(acceptance) → FEED14 → PARENT03(last confirmed policy). No request-station exit or nonexistent Report toggle is added to Parent. |

Collection recovery 208–213 is conditional on a real publicly observed failure
and recovery. Loss of Internet does not itself fail local diagnostic collection.
No deterministic public trigger is currently established: those six cases stay
pending until one is qualified or their customer/engineering ownership is
explicitly resolved. Opening the report or seeing the final draft cannot stand
in for observing failed collection, Retry, or explicit Send without logs.

### Natural calendar windows

Calendar cases run on an independently prepared computer in its declared
timezone during a real eligible window. TIME05 only reads the clock. Scheduling
waits happen before the case starts; no artificial clock or saved-usage change
is allowed. Every case has a 3600-second execution bound. Calendar work is the fixed final
part of the queue; it does not select whichever case happens to fit today's date.
Plan separate natural windows in queue order. On the single pinned VM, independent
cases cannot share an overlapping transition or reuse an earlier case's state;
seasonal coverage can therefore require later real transition dates.

| Cases | Window and expected public comparison |
| --- | --- |
| 196 / 199 / 202 daily-reset | Start before local midnight ending an ordinary / spring-transition / autumn-transition day. Exhaust one minute naturally with no grant, read D=0, cross midnight and read the renewed daily allowance. Correct-password child entry works again. No full-day wait. |
| 197 / 200 / 203 rest-of-day | Ordinary: request shortly before midnight and observe grant expiry there. DST: request shortly before the actual offset change; read the time to the next local midnight before and after it. Remaining elapsed duration decreases by elapsed time, despite the local clock jump/repetition. The timezone's 23/25-hour day arithmetic is checked through displayed remaining time, not a full-day wait. |
| 198 / 201 / 204 fixed-grant | Request a fixed duration spanning ordinary midnight / spring offset change / autumn offset change. Observe continuing access and the original elapsed deadline; no restart or extra hour is granted by the boundary. |
| 40 / 43 replacement | Independently covers replacing a fixed grant extending past midnight with Rest of the day on both request surfaces. It does not need a calendar-window wait. |

A prepared calendar profile declares the actual date, timezone, transition
window and expected displayed intervals before execution. Missing window or
public precision is a gate, not permission to sample another day and call it
the same case. Detailed timezone arithmetic and malformed timestamps retain
their fast technical coverage.

### E2E-053

Case **254**, variant `latest-install` (`history=latest-install`), implements the
continuous [Chinese kiosk lifecycle](#chinese-kiosk-language-lifecycle)
below through `chinese_lifecycle.PLAN` and `onpc_chinese_lifecycle::run`.
It starts product-free on Ubuntu 26.04. Complete acceptance passed in
`20261005T052511Z-d5a980d9`; required current-install and native-auth regressions
passed in `20261005T053736Z-2bf99fd4` and `20261005T054603Z-b58a3339`.
After the untouched chooser/form observations, cancel the station normally,
enable Jordan with zero daily time through Parent, and return before saving
Chinese. After each real approval, independently read positive granted time
bounded by that request's public estimate and unchanged saved allowance/app rows
in Parent; logout normally before the next kiosk entry. Checked Chinese is read
through public Preferences on both entries. No extra reboot is performed.

### Chinese kiosk language lifecycle

This is **one complete case**, delivered by task 300. The independent multilingual histories
retain every original assertion under the
[acceptance decomposition](#personal-language-acceptance-decomposition).
Case 254 is registered as E2E-053 and passed all 25 declared assertions,
collection and owned cleanup on Ubuntu 26.04.
Task 300k qualified the revised fresh-install first presentation in
`20261004T185057Z-2010e28f`, with both required lifecycle regressions passed.
That evidence is Ubuntu-only. The selected complete-case target is Ubuntu
26.04. The developer removed Fedora-specific Chinese qualification from this
case's acceptance scope on 2026-10-04; queue repair establishes no acceptance.
Keep all three reported
symptoms in this continuous history, without a German/Hebrew lifecycle matrix.

Use the [current-package installation binding](E2E-Building-Blocks.md#customer-package-install-composition)
and LIFE02 reboot for a fresh installation of the latest verified current-source
package. No v1.2 package or upgrade is part of this recipe.
The reusable Chinese first-presentation and reboot observations were qualified
by task 300e in an upgrade journey through
[the Chinese binding](E2E-Building-Blocks.md#chinese-language-preparation-and-desktop-language-setup);
the native authentication binding is qualified by task 300f through
that same catalogue route. `request_flow.chinese_request` /
`onpc_request_flow::prepare_chinese` and `kiosk_approved_flow.chinese_approval` /
`onpc_request_flow::approve_chinese` supply the fixed Chinese request/challenge.
`ChineseNativeAuthJourney` qualified two fresh kiosk approvals in
`20261004T073743Z-9a030ef1`; its required English regression passed in
`20261004T075449Z-01e10e04`, with collection and owned cleanup in both runs.
The first-presentation slice is implemented by `ChineseKioskJourney` in
[chinese_kiosk_lifecycle.py](../../tests/e2e/chinese_kiosk_lifecycle.py), using
the shared continuous worker and two declared customer-reboot transitions in
that historical upgrade qualification.
Initial public observations precede all generic chooser setup; Cancel exposes
the Chinese form without a preference save. This slice passed on every enabled
VM in `20261004T044302Z-572b0ee7`; task 300e's required package-upgrade and
kiosk-entry regressions and close-out also passed.
These slices supply no complete-case acceptance by themselves. The continuous
case rechecks their shared observations. `ChineseCurrentInstallJourney` in
[chinese_current_install.py](../../tests/e2e/chinese_current_install.py) now
qualifies the fresh-install, single-reboot sequence through the initial form.
It reuses `ChinesePresentationMixin` and the same worker renewal/notice/form
leaves as the historical qualification. After Parent setup, case 254 uses
`kiosk-language-jordan-jamie-chinese` to bind Jordan's already Chinese form,
the exact offered parents and Jamie's selected result. The native-auth slice
still uses its English input binding before its explicit Chinese language save.

Finite inputs: selected child Jordan; approver Jamie; child desktop locale
`zh_CN.UTF-8`; product language `zh-Hans`; Jamie and kiosk station desktop
language English; two ordinary 75-second, soft-app-included requests. Jordan
must be the independently observed default selected child on the first kiosk
entry, with no saved product language preference. Use one latest verified
current-source package asset; if that input or the real reboot-required result is
unavailable, retain the gate rather than inject state. Chinese system locale,
translation and font assets are installed by `tools/prepare-baseline` and only
verified by the attempt under the
[language preparation contract](E2E-Building-Blocks.md#chinese-language-preparation-and-desktop-language-setup).

| Phase | Shared composition and independent public result |
| --- | --- |
| Declared setup | Start from the product-free baseline with independently verified Chinese assets and one verified current-package transfer/readback. Use DESK13(Jordan, `zh_CN.UTF-8`) for the account setting, then explicit session renewal and fresh child entry to observe a Chinese desktop before product installation. Keep Jamie/station English and Jordan's product language unset. No older product is installed, and no private preference writes or synthetic grants are used. |
| Install latest, no reboot | From the declared administrator session, LIFE04 installs the latest verified current-source package once. Independently require successful completion, the expected installed version, the final reboot notice and unchanged boot. Do not reboot before the tested kiosk entry or replace this installation with an app snapshot. Navigate through the shared greeter/kiosk entry blocks and independently require Jordan as the default selected child. On the very first presentation, require the reboot-required prompt's message and buttons in Simplified Chinese, with no English first-run language dialog displacing it. Observe this before any automatic language-setup handler or Parent policy setup acts. |
| Reboot and first kiosk presentation | Exit through the public prompt/session flow and perform LIFE02 in the same attempt. Independently confirm a changed boot and fresh usable greeter. Use existing public Parent policy blocks for any required request eligibility after this reboot, leaving Jordan's personal language unset. Reacquire fresh kiosk observations. Before saving any product language for Jordan, require Jordan still selected, the first-run language preference dialog already Chinese, Chinese selected by default, and the underlying kiosk/request surface Chinese from its first usable presentation. Compare bounded representative headings, child/approver/duration/Request labels and dialog actions against independently specified Chinese expectations. A later language switch cannot repair an English initial presentation. |
| Save Chinese and approve | Use the shared public chooser operations to select/save `zh-Hans` and independently observe completion. Set/read the ordinary Jamie/Jordan/75-second/soft-included request through REQUEST04/05/06, then REQUEST09. AUTH01 must observe both the product-owned Chinese request context and the real MATE agent's Chinese Authenticate/Cancel buttons and system-owned explanatory/password text. Use the qualified Chinese provider binding and unchanged secret-safe AUTH02 route for a real approval; independently require the Chinese granted result and ordinary automatic exit/access result. |
| Fresh kiosk re-entry and approve again | Leave the approved destination through the declared shared session route and enter a new kiosk session, without another reboot or changing the station/administrator language. Reacquire fresh ownership/control observations; require Jordan, persisted Chinese preference, Chinese form and no first-run chooser. Submit the same finite request again. Independently require the new native PolicyKit prompt's buttons, system-owned text and product message all Chinese before credential input, then real AUTH02 approval and the ordinary translated result/exit. The first prompt alone does not cover this regression. |

Record first-presentation and both native-prompt observations separately. Use
public IDs for owned controls and the scoped qualified native provider adapter
for PolicyKit. Observe native translations directly, including text the product
does not control; locale environment readback, a mocked agent or product message
alone is insufficient. Do not patch the dialog, rewrite system strings or read
password content. Generic `complete_language_setup` must not dismiss/save the
chooser before the initial-language assertions. Preserve the shared request,
authorization and policy results, ordinary owned cleanup and the uninterrupted
latest installation → Chinese pre-reboot prompt → reboot → first kiosk → approval
→ fresh kiosk → approval history.

### Personal-language acceptance decomposition

Task 300 originally combined independent customer histories and unqualified
bindings. The developer authorized smaller tasks. Preserve the following
acceptance mapping; each scenario is one complete case, not a fragment of a
resumed VM attempt. These task IDs are planning IDs, not numeric coverage IDs.
The inventory owns current registration; E2E-053–055 have their own bindings
and histories below, while tasks 308–310 remain planned.

| Original task-300 acceptance | Complete scenario owner | Missing capability / prerequisite |
| --- | --- | --- |
| 1: first-run default, native names, Save/Cancel and checked translated text | 306 account/offline persistence; Chinese untouched first presentation remains 300 | Existing LANG01; 306a enabled Parent/child-selection readback |
| 2 and 5: independent administrator/two-child choices, child/approver switches, overlay/kiosk sharing, relaunch/re-entry/session renewal and offline packaged German/CJK/Hebrew | 306 | 300j station restoration; 306a; existing Internet isolation |
| 3: overlay-to-panel language/time refresh, reopening/resume and natural expiry without reset/grants/policy changes | 310 | 310a plus existing retained-session/countdown and natural-expiry tasks; tooltip/menu matrices are UI-owned |
| 4: inherited About/feedback, synthetic draft/reply, unchanged names/numbers | 307 Parent; 308 overlay; 309 kiosk | 307b, 308a, 309a; real child/station report-entry gates remain 187o/187k |
| 4: ordinary translated approval/result per request surface | 308 overlay; 300 kiosk | 308b genuine Shell approval; existing 300f Chinese MATE binding |
| 6: representative Hebrew and restored English functional context with exact mixed-script draft and unchanged policy/time | 307 Parent; 308 overlay; 309 kiosk; 310 child time/expiry | Qualified public input/result route per surface; full inherited-dialog/label and tooltip/menu matrices are UI-owned |
| 7: latest-package installation, Chinese pre-reboot prompt, one reboot, untouched Chinese chooser/form and two real Chinese approvals across fresh sessions | 300 | 300k revised current-install composition; historical upgrade evidence alone is insufficient |

Every scenario retains unchanged account/application names, numeric values,
synthetic content, selections and policy/time comparisons where relevant.
Distinct chooser Save/Cancel and validation outcomes remain with
[UI coverage](UI-and-E2E-Coverage.md); that allocation does not replace the
representative installed Hebrew logical-text and functional checks. The developer's
2026-10-05 decision removes visual inspection for this and all future tasks;
apply the [presentation acceptance rule](../Mandates/UI-Automation-Mandate.MD#input-and-independent-results).
Host UI checks also follow the result-oriented scope. Public text cannot claim
pixel rendering, glyph order, clipping, font legibility or visual alignment.
Missing required public text or identity observations remain gates. Focus proofs
remain input guards only; keyboard traversal is not a separate language outcome.

### E2E-054

Personal-language persistence (task 306).

One complete case: Jamie product language `zh-Hans`, Jordan `de`, Riley
`he`; all three desktop languages and the station remain English. Through
public Parent setup, give each child a 60-minute daily allowance with zero grant
and capture its app-policy rows. Record exact initial values before each child
session; compare active time using declared monotonic elapsed bounds.

Observe representative untouched English default/native names before saving
choices. Save Jamie's Chinese in Parent, select Riley → Jordan → Riley and
independently require Jamie's checked Chinese and management text for each UID.
Use public child/station Preferences for Jordan German and Riley Hebrew.
For one declared candidate change (Riley Hebrew → German), Cancel and reopen
to require Hebrew. Switch kiosk Jordan → Riley → Jordan and Jamie → Casey →
Jamie; language follows the child only.
Keep duration 75 seconds and soft apps included; compare accounts/numbers
without submitting. Riley's overlay and kiosk must show the same saved Hebrew.

Use InternetIsolation before the multilingual changes/readbacks and independently
confirm isolation. Close/relaunch Parent and Riley's overlay, exit/re-enter kiosk,
and renew Riley's desktop session through public qualified routes. Require
persisted choices, representative German/CJK/Hebrew customer text and no
repeated first-run chooser without downloads. Restore Internet through its
shared owner and independently read public policy/app values. No other
scenario's approval or panel rendering is needed to pass this account history.

E2E-054 `account-offline`, case 255, binds this complete history in
`tests/e2e/language_persistence.py`. Both policy captures use a 2400-second
monotonic history bound, with two seconds of public refresh/formatter tolerance.
App IDs and rules remain exact across languages. App names follow the parent's
language under [ONPC-CORE-APPS-002](../Specification.md): capture each child's
Chinese names at its first Chinese readback and require those exact names on
subsequent Chinese readbacks; English readbacks retain the English capture.
The overlay retains its independent Casey approver while the station retains
Jamie. German/Hebrew forms retain Custom `1.25`, 75 seconds and included soft apps.
The complete history passed all 26 assertions on Ubuntu 26.04 in
`20261005T162608Z-4a7cb85e`, with all three required language regressions,
owned cleanup and baseline restoration. The
[language catalogue](E2E-Building-Blocks.md#personal-language-selection)
records the shared bindings and retained acceptance reports.

### E2E-055

One complete Parent English → Hebrew → English history for Jamie, selecting
Riley with its recorded 60-minute allowance, zero grant and captured app rules.
At each language, use representative translated management/feedback context to
continue the same work and independently compare the exact mixed Hebrew/Latin
draft and child policy. Stable IDs and accessibility observations identify safe
inputs; label completeness and inherited-dialog translation matrices belong to
shared UI tests. This is a saved-work history across language changes.

Use exact body `שלום Alex 75` and reply `rtl-check@example.invalid`.
After entry, close the dialog normally, change language through Preferences and
reopen; compare retained body/reply before new input. Preserve account names,
app identities and numeric policy at each functional result boundary, and compare
app names within each language as described below. No Send or
external-link action. Public dialog reopening must preserve the actual draft;
host fixtures or privately restored content cannot replace this history.

E2E-055 `parent-hebrew`, case 256, binds the complete finite history in
`tests/e2e/parent_presentation.py` and `onpc_parent_presentation::run`.
One original English policy capture precedes draft entry. Save Hebrew and later
English once each; use the current-language readback before reopening feedback
and comparing the retained draft and final policy/name/numeric balances. About
is a supporting information visit; no chooser Cancel or duplicate read matrix
is required by this customer history.
Every feedback read compares the immutable original `synthetic-rtl` capture
before any later input. Account names, app identities and rules remain exact
against the original English policy. App names follow desktop-entry translations
as required by [ONPC-CORE-APPS-002](../Specification.md#application-access):
capture Hebrew names at the first Hebrew policy read and compare them exactly
at the Hebrew final read; both English return reads compare names against the
original English capture. Policy reads use a 600-second monotonic history bound
and two-second refresh/formatter tolerance; the entire case deadline is 900 seconds.

### Overlay language presentation (planned task 308)

One complete Riley overlay English → Hebrew → English saved-work history,
with Jamie selected, 75 seconds and soft apps included. Capture the native
activity and synthetic content through the existing approval/return binding.
Use representative translated form/report context to continue the request and
review the exact mixed-script content. Retain body `שלום Alex 75` and reply
`rtl-check@example.invalid` across normal report closure, public language
change and real reopening before any new input; preserve names/request values.

Use 187o's genuine public trigger and actual cooldown timing; no injected error.
The same-draft/public-reopen route must be qualified before composition.
After restored English text is verified, save Hebrew again and perform one genuine
75-second soft-included approval. The desktop/native Shell agent remains English;
the product request/result is Hebrew. Require correct recipient/secret guards,
ordinary translated success, return to the same usable activity with unchanged
content and the expected public time increment. Do not send feedback.

### Kiosk language presentation (planned task 309)

One complete restricted kiosk English → Hebrew → English history for Riley,
Jamie, 75 seconds and soft apps included, with English station desktop.
Observe form, About and genuine report using the same exact synthetic body/reply
as task 308. Retain the draft across normal report close, language change and
actual reopening before new input. Change approver and back while requiring
the child's checked language and translated form remain unchanged.

Require representative installed Hebrew and restored English request/report
context and exact mixed-script draft preservation. Preserve literal names,
request numbers and station restrictions. Stable IDs and matching accessible
observations remain input guards; complete label/dialog matrices stay in UI tests.
Use 187k's real error trigger/re-entry timing; unsupported draft reopening is
a retained gate, not permission for private errors/state. No report submission
or external-link activation. Ordinary translated kiosk approvals remain in
task 300's continuous Chinese case.

### Panel language and expiry (planned task 310)

One uninterrupted Riley child history with an initial 10-minute daily-only
allowance, zero grant and recorded app-policy rows. Use the declared native
activity, capturing its synthetic content. Change English → Hebrew → English
through overlay Preferences, close/reopen it and resume the retained child
session. Independently observe shared choice, refreshed remaining time and the
same retained activity using qualified public operations. Tooltip/menu content
and each label combination are child UI obligations.

Use representative Hebrew and restored English time/request context to continue
the activity. Compare public time with actual elapsed
bounds at each transition; choices cannot reset time, grant extra access or
alter saved policy. Observe genuine minute and final-second progression through
TIME02, then use the activity until natural TIME04 expiry. Require the lock to
own harmless normal input and desktop access to end; manual locking cannot
substitute. Declare exact sample windows/tolerances in the finite case plan
before execution; missed windows fail rather than restoring or resetting time.

The [complete family review](UI-and-E2E-Coverage.md#complete-scenario-family-review)
records the customer outcome and allocation decision for every registered,
pending, retired and future-language family. This recipe document owns its
finite compositions; shared UI owns local control matrices.

### E2E-056

Case **257**, variant `parent` (`surface=parent`), is one continuous English
fresh-install history. Task 302 owns complete acceptance; LIFE07's three-surface
qualification supplies shared operations, not this Parent reboot result.
`fresh_parent_restart.PLAN` composes `package_installation`, public restart
reads/actions and `prefixed_stages('return', fresh_desktop('parent'))` through
`record_package_journey` and `onpc_customer_reboot::run_parent_notice`.

| Phase | Finite actions and independent results |
| --- | --- |
| Actual installation | Start from the product-free Ubuntu baseline, authenticate Jamie graphically and install the verified current-source package once through LIFE04. Read successful completion and the final reboot notice separately. Retain this boot; no upgrade, app snapshot, private marker or injected error supplies the history. |
| Parent before reboot | Launch installed Parent directly. Require one owned modal before management or language setup, with `Restart the computer for Oh No! Parent Control to work properly.`, `Close` and `Reboot now`. Activate Close once; observe the administrator desktop, no Parent management and unchanged boot. Reopen directly and independently read the same owned modal and exact instructions on that boot. |
| Reboot and usability | Activate the Parent modal's Reboot now once through normal system authorization. Require a changed boot digest and fresh usable GDM before new graphical administrator authentication. Launch fresh Parent, finish ordinary English language setup if needed, and require an available child selector with no restart modal. No command-reboot fallback, uncertain-input replay or policy setup precedes the notice. |

Use the common 45-second public-result waits and the shared 330-second boot-change
deadline within the 1800-second case budget. Require all seven declared assertions,
worker-title reconciliation, collection, worker shutdown, owned cleanup, baseline
restoration and preservation. The command-reboot continuity regression remains
`check_e2e_customer_reboot`; Child App is case 258 below, while kiosk and the
unrelated-request control remain tasks 304–305.

### E2E-057

Case **258**, variant `child` (`surface=child`), is one continuous English
fresh-install Child App history. `fresh_child_restart.PLAN` composes LIFE04's
`package_installation`, LIFE07's shared `restart_reentry('overlay')`, fresh
desktop challenges and public postboot setup through `record_package_journey`
and `onpc_customer_reboot::run_child_notice`.

| Phase | Finite actions and independent results |
| --- | --- |
| Actual installation | Start product-free on Ubuntu, authenticate Jamie graphically, install the verified current-source package once and read completion/final reboot notice. Preserve the installation boot. |
| Child App before reboot | Log out Jamie and authenticate Riley into the ordinary desktop through the installed GDM route. Keep controls disabled; launch `oh-no-parent-control-child` directly without requiring a panel. Read one owned modal before language setup or a usable request: `Restart the computer for Oh No! Parent Control to work properly.`, `Close`, `Reboot now`. Close once, independently require blocked request, exit normally and observe the same child desktop/boot. Reopen directly and read the same modal again. |
| Reboot and usability | Activate the Child App modal's Reboot now once. Independently require a changed boot and usable GDM. Authenticate Jamie afresh, open Parent and finish English language setup; verify Riley's untouched disabled zero allowance, then save enabled 30 minutes through ordinary public controls. Log out Jamie, authenticate Riley afresh and launch Child App. Finish ordinary English language setup if needed; require enabled Request for the fixed correct child and no restart modal. |

Use the common 45-second public-result waits, shared 330-second boot-change
deadline and 1800-second case budget. Require all eight assertions, worker-title
reconciliation, collection, worker shutdown, owned cleanup, baseline restoration
and preservation. No private marker, app snapshot, command-reboot fallback,
uncertain input replay or policy setup before the notice supplies acceptance.
The shared reentry extraction affects `check_e2e_restart_notice` and Parent
case 257; retain those regressions and `check_e2e_customer_reboot`.

## Coverage ownership and remaining limits

Repeated setup and sanity observations do not count as duplicate primary
coverage. Each unique outcome has one owner below; a continuous journey may
reuse it to reach a later distinct outcome.

| Behavior | Primary owner |
| --- | --- |
| Installation/defaults; account discovery; standard management exclusion | 2; 3–4 and 179–183 for real account changes through shared helpers; 5–6 |
| Allowance values/saves; enable/edit/disable and child access | 158–159; 7–12 |
| App-rule transitions; launch routes; catalogue/matching; updates | 13–16; 62–109; 184–189; 110–111 |
| Active-grant revocation; daily-only no-grant; expired grant with daily time | 17–20; 160; 170; case 161 local availability is UI-owned |
| Daily/grant exhaustion; another foreground user; countdown/options | 21–24; 25–26; 27–29 and 162–163 |
| Approval identity/app choice; denial/cancel; input boundaries/duplicate gesture | 30–33; 34–37; 38–43 |
| Exit destinations; station restrictions; eligibility; shared choices | 44–49; 50–52; 53–57; 58–61 |
| Distinct same-child desktops; persisted choices/deadlines | 112–115 (public-route gate); 116–125 |
| Gameplay at expiry; extension while playing; replacement on return | 126–127; 128–131; 132–135 (positive daily time) |
| Package update and remove/reinstall/purge | 136–138; 139 |
| Expired soft exception and restoring actions; pending requests/cooldown | 164–170; 171–178 |
| About/help; local feedback; success/retry; error report/recovery/lifetimes | 151 and 190–193; 152–155; 156–157; 205–222 |
| Local operation offline; real calendar boundaries | 194–195; 196–204 |
| Approval after a decision delay, both surfaces and four balance profiles | 223–230 |
| Temporary soft permission by route and request surface, both parents | 231–246 |
| Repeated work/game/time-source history and retained/fresh departures | 247–250; three complete cycles each |
| Alternating two-parent/two-child routines and final targeted revocation | 251–252; four complete rounds each |
| Lunar AppImageLauncher login autostart under an ungranted/time-only soft block | 253; allowed control, exclusion, explicit inclusion and replacement exclusion |

The [engineering reconciliation](E2E-Building-Blocks.md#inventory-reconciliation)
retains every displaced internal assertion, including retired E2E IDs 140–150,
injected feedback transport behavior, inactive hard-blocked-process branches,
account authorization/storage protection, package ownership/migration failures,
diagnostic production/retention/privacy, and disabled future mute behavior.
Unsupported-OS/reserved-account installation refusal needs its separate package
environment qualification; this Ubuntu 26.04 customer runner does not simulate
another distribution by changing release files.

Requirement references identify the clauses exercised by each family, not
complete proof of every clause in a compound requirement. Public balances,
activation, repeated authentication and recoverable request errors have customer
owners. Status-read/activation failures, authentication-agent failures and
authorization beyond the available interfaces retain their engineering owners;
seeing a successful window cannot establish those failure or security contracts.

No pixel/layout/scale/style pass gate, generic GDM password test, website
filtering, unrelated networking test, remote device management or unsupported
copied-program guarantee is added. A missing feature, public route, observation,
asset, date window or authorized sending profile remains an explicit pending
obligation. A passing subset never marks its complete variant ready.
