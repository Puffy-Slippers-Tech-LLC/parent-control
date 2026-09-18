# Customer E2E scenario recipes

[scenarios.json](../../tests/e2e/scenarios.json) owns customer-readable steps,
persistent case IDs, matrices and readiness. This document supplies their exact
block compositions and finite data. The [block catalogue](E2E-Building-Blocks.md)
owns atomic operations and composites; the [execution plan](E2E-Execution-Plan.md)
owns implementation order and live completion. Do not copy these recipes into
task documents or silently substitute different inputs. In an implementation
session, read only the selected family's variant branches, applicable finite-data
rows and common entry/time rules it uses; the master's Next task pointer avoids
loading unrelated task briefs or the full scheduling queue.

There are **50 families and 252 persistent cases**: **240 customer cases**
(6 ready, 234 pending), **11 engineering fault obligations**, and **1 ready
harness qualification**. E2E-034 is retired and is not reused. Cases **3, 4, 5, 6,
151 and 193** are the ready customer bindings; case **1** is ready harness
qualification. Overall, **7 bindings are ready and 245 are pending**.

Each family below records current implementation status. After a complete
scenario and terminal cleanup pass, run `tools/generate_test_coverage.sh`
(the approved launcher for `tools/generate_test_coverage.py`), update that
family's ready/pending cases and these totals, update qualified scope in the
[block catalogue](E2E-Building-Blocks.md), and check its master task. A block
qualification alone leaves its scenario pending. Retain current status and
remaining gates, not an accumulated run history.

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

Customer steps use app interfaces, ordinary desktop controls, Users settings,
package commands and normal app/file actions. Only setup, credential safety,
transport ownership, and final cleanup use the existing harness exceptions.
Cases 3 and 4 retain their established account-fixture checkpoints as supporting
setup; their ready result covers visible discovery/empty state, not operation of
Users settings. Case 179 adds that actual customer account-creation route.
Case 1 and cases 140–150 are explicitly not customer journeys.

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
state. A later newly launched app cannot prove earlier work survived. When testing a new
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
| Daily presets (158) | 0, 15, 30, 45, and every 30-minute increment from 60 through 1410: 50 offered presets. Select/read each; no login per value. |
| Daily custom (158) | Accept 0, 1, 15, 1439. Reject empty, abc, −1, 0.5, 1440, 1441. Start invalid attempts with saved 15; reopen and read 15 afterward. The API's 1440 allowance belongs to engineering tests. |
| Daily saving (159) | Save 2 by pause, 3 by Enter, 4 by leaving focus. Then type valid 5 followed promptly by 6; final saved value is 6. Switch to Riley, save 7, return and read Jordan=6/Riley=7. Launch Parent again without closing it: PARENT01 → UI13(one management window) → PARENT03/UI12(same selected child and values). Qualify the public window-count projection with this consumer. Close/reopen and repeat the value read. Do not assert a minimum visible Saving animation duration. |
| E2E-005 profiles | daily-only: positive daily, no grant; grant-only: zero daily with real 10-minute approval before edits; combined: positive daily plus a real 10-minute addition. Enabled edits: daily-only/combined 4→5→0→5 minutes; grant-only 0→4→0. At zero, daily-only must deny access while combined retains its grant. Re-read actual D and the original grant deadline; if navigation exhausts a required margin, fail preparation rather than inject usage. |
| Request presets (38/41) | 5, 15, 30, 60, 120, 240 minutes. Read every footer and matching prompt, cancel each review, then approve representative 5. |
| Request custom (39/42) | Accept 0.1, 0.5, 1.25, 1440; reject empty, abc, −1, 0, 0.09, 1440.1 and comma decimal 1,5. Valid prompts reflect whole seconds (6, 30, 75, 86400). Approve representative 1.25. |
| Rest of the day (40/43) | First approve a 1440-minute fixed grant, read its later deadline, then choose/approve Rest of the day. Read PARENT09 before and after: the replacement interval is shorter and the footer says until midnight. Calendar cases own the exact deadline check. No 24-hour wait. |
| Shared choices (58–61) | Jordan custom 1.25, soft included; Riley custom 2.5, soft excluded. Seed station approver Jamie and each overlay approver Sam. Compare shared values and local selectors before edits; reverse direction/primary child per variant. |
| Short time | Natural daily tests use 2–4 minutes and verify positive D before entry. Grant-only uses 2 minutes; replacement uses 3. Active reboot/update uses 15–20 minutes. These are preparation choices, not bypasses of observed balances. |
| E2E-038 daily dominant | Start with daily 4 minutes and a real 0.1-minute addition including soft apps. Enter, open S, switch away, and wait until displayed G is 60–90 seconds while D remains at least 120 seconds. Return before grant expiry. No later screen/app save occurs before the tested action. FLOW18 checks the inequalities; wrong timing fails preparation. |
| Station restriction routes | Super/Overview, Super-A/app grid, ordinary terminal shortcut; inspect available controls for Parent/settings launch. If no search field appears, no query is typed. About/report restrictions have their own cases. |
| App transitions (13–16) | Allowed→Soft, Soft→Hard, Hard→Soft, Soft→Allowed, Allowed→Hard, Hard→Allowed: all six directed changes. Open work under Allowed before Allowed→Soft/Hard. Before Soft→Hard obtain real soft approval and reopen the matching activity; in limits-off cases temporarily enable, approve/open, then disable (preserving the activity). Verify the declared limit state again before the tested save. Hard→Soft stays blocked without a new exception; Soft→Allowed and Hard→Allowed permit launches. Unchanged-block restoration is owned by 169. |
| Match/control/route matrix | Preserve all four precise/pattern × on/off cases and all 48 route × rule × on/off cases. Alias, special-path, update and file-pattern data run only in their owning cases. |

The 50-preset set includes 46 half-hour entries plus the four shorter presets.
Noninteracting combinations, such as every attachment size with every app launch
route, add no app-behavior coverage and are not multiplied. Every declared
interacting matrix is complete; this is a finite coverage model, not a claim
that arbitrary inputs, elapsed durations and user histories can be enumerated.
Setup is shared code, not prior execution. Group implementation work, but run
each numeric variant as an independent attempt. Long calendar and retry-expiry
cases have their own queue gates and budgets.

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

Exhaust every declared finite interacting matrix. For values that share the
same result mechanism, enumerate boundary/representative inputs inside the
owning case instead of multiplying unrelated dimensions. E2E-019 owns baseline
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

Implementation status: All cases pending.

**Install the app and begin managing a child.** Cases 2.

Bindings: installation = clean.

1. V(parent,fresh) → LIFE04(install) → FILE06(notice).
2. LIFE02 → GDM01 → UI13(personal accounts, station).
3. P0 → PARENT03(defaults) → PARENT04(App Limits) → UI13(unblocked rows) → DESK03 → REQUEST01 → REQUEST03 → REQUEST12(cancel).

### E2E-003

Implementation status: All cases ready (3, 4).

**Parent discovery and navigation.** Cases 3, 4.

Bindings: children = existing-and-new / none.

1. FLOW01(existing child) → PARENT03(capture defaults) → PARENT04(App Limits); none: V(parent,fresh) → SEARCH06(Parent), no launch yet.
2. Existing: PARENT04(Screen Limits) → PARENT03 → FIX01 (supporting account checkpoint) → UI13(new choice); none: FIX02 (supporting account checkpoint).
3. Existing: PARENT02(new) → PARENT03 → PARENT04(App Limits) → PARENT04(Screen Limits) → PARENT03 → UI12 → PARENT02(original) → PARENT03 → UI12. None: UI05(Enter) → PARENT19.

### E2E-004

Implementation status: Ready: 5, 6. Case 6 implementation and verification
confirmed complete by the developer.

**Standard user cannot manage policy.** Cases 5, 6.

Bindings: launch = app-grid / terminal.

1. V(standard,fresh) → SEARCH01 or FILE01, selected by launch.
2. Grid: UI21 → SEARCH03 → SEARCH04(unavailable), no Enter. Terminal: FILE02(parent command) → FILE06(specific GUI management denial) → UI11(management). Read **Administrator access required** and its administrator-sign-in explanation, then dismiss the denial and close the terminal. Generic startup errors and command echo cannot establish access denial.

### E2E-005

Implementation status: All cases pending.

**Change screen limits while starting or returning to a child desktop.** Cases 7, 8, 9, 10, 11, 12.

Bindings: time = daily-only / grant-only / combined; session = new / retained.

1. P0 → FLOW03(allowed and hard targets) → FLOW02(profile allowance, final off). Retained: C(fresh) → FLOW08(allowed) → APP04 → P(retained).
2. UI17(on) → PARENT08 → PARENT09 → C(variant entry, expected access) → access-check. Grant profiles: G → FLOW06(short grant) → P(retained) → PARENT09.
3. For each enabled allowance edit in the transition table: P → PARENT06 → PARENT08 → PARENT09 → C → access-check → leave-child → P.
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

**Countdown and visibility transitions.** Cases 27, 28, 29.

Bindings: time = daily-only / grant-only / combined.

1. FLOW13(profile) → P → PARENT09 → C(fresh) → TIME01 → PANEL03.
2. DESK05 → TIME01(absent) → DESK08(success) → TIME01 → DESK03 → TIME01(absent) → V(Riley,fresh) → TIME01(absent) → C(retained).
3. TIME02(minute and seconds); TIME04 only if the declared interval reaches expiry.

### E2E-012

Implementation status: All cases pending.

**Single child overlay and selected-parent approval.** Cases 30, 31, 32, 33.

Bindings: soft-apps = excluded / included; approver = first / second.

1. FLOW13(combined, soft included) → C → FLOW08(soft) → APP04 → REQUEST02 twice → REQUEST03(fixed child,one form).
2. REQUEST04(approver,duration) → REQUEST06(soft choice) → REQUEST08 → REQUEST09 → AUTH01(exact prompt).
3. AUTH02(correct) → REQUEST11(success) → REQUEST12(automatic) → TIME01 → APP02(soft effect) → FLOW08(hard/soft). After TIME03(cooldown): REQUEST02 → REQUEST09 → AUTH02(cancel) → REQUEST11(cancel) → REQUEST12(cancel).

### E2E-013

Implementation status: All cases pending.

**Authentication denial and cancellation retry.** Cases 34, 35, 36, 37.

Bindings: surface = child-overlay / kiosk; outcome = wrong-password / cancel.

1. P0 → FLOW02(overlay daily-positive or kiosk zero) → FLOW03(blocked target). Overlay C → FILE01 → FLOW04; kiosk G → FLOW04.
2. FLOW07(wrong approval credential or cancel). Overlay DESK10(terminal) → FILE02(target command) → FILE06(denied) → DESK10(form) → REQUEST03. Kiosk REQUEST12(cancel) → C(fresh,denied) → DESK11 → REQUEST01 → REQUEST03. UI12(choices).
3. FLOW05(fresh approval) → C if kiosk → TIME01 → FLOW08(expected target).

### E2E-014

Implementation status: All cases pending.

**Shared duration boundaries and duplicate submission.** Cases 38, 39, 40, 41, 42, 43.

Bindings: surface = child-overlay / kiosk; choice = predefined / custom / rest-of-day.

1. FLOW16(enable and selected daily allowance) → request-entry(surface). Iterate the duration table with REQUEST04/05 → REQUEST03 → REQUEST08.
2. Invalid: REQUEST09(validation) → UI11(prompt). Valid: REQUEST09 → AUTH01(exact details) → AUTH02(cancel) → REQUEST11(cancel). Rest-of-day first obtains 1440 minutes with FLOW05, reopens and selects Rest of the day.
3. REQUEST10(representative) → AUTH01 → AUTH02(correct) → REQUEST11 → REQUEST12(automatic) → C if kiosk → TIME01 → UI12(expected time).

### E2E-015

Implementation status: All cases pending.

**Request surface exit behavior.** Cases 44, 45, 46, 47, 48, 49.

Bindings: surface = child-overlay / kiosk; exit = cancel / escape / approved.

1. FLOW16 → C if overlay → FLOW08(allowed) → APP04 → FLOW04; kiosk uses G → FLOW04. Approved: REQUEST09 → AUTH02(correct) → REQUEST11.
2. REQUEST12(cancel|escape|approved-immediate). Overlay APP04(compare) → APP03; kiosk GDM01. Approved enters child if needed → TIME01.

### E2E-016

Implementation status: All cases pending.

**Restricted request station.** Cases 50, 51, 52.

Bindings: request = approved / denied / cancelled.

1. FLOW16(enable) → G → REQUEST01 → REQUEST03. For each restriction route: UI05(route) → UI11(forbidden window) → REQUEST03.
2. FLOW04(entry=open) → REQUEST09 → AUTH02(outcome) → REQUEST11. Repeat restrictions if form remains.
3. REQUEST12(cancel or automatic) → GDM01.

### E2E-017

Implementation status: All cases pending.

**Kiosk selection and unavailable requests.** Cases 53, 54, 55, 56, 57.

Bindings: accounts = multiple / no-child / no-parent / ineligible-parent / disabled-child.

1. Account profile is the declared setup. Enable available targets with FLOW16 except disabled-child and no-parent. No-parent starts directly at GDM with default limits off: no inaccessible administrator setup or hidden enabled-policy fixture is needed to inspect its empty parent list. G → REQUEST01.
2. Open each enabled selector: UI04 → UI13(exact eligible set) → UI05(Escape); REQUEST04(each declared choice). Disabled/empty uses UI02/03 without input.
3. REQUEST03 → REQUEST08. Available: REQUEST09 → AUTH01 → AUTH02(cancel) → REQUEST11. Unavailable: UI02(disabled) → UI11(prompt). No-parent specifically requires the missing-eligible-parent explanation and empty parent list; it makes no isolated screen-time enforcement claim with its also-disabled child.

### E2E-018

Implementation status: All cases pending.

**Remember each child's choices across both request forms.** Cases 58, 59, 60, 61.

Bindings: direction = overlay-to-kiosk / kiosk-to-overlay; child = first / second.

1. FLOW16 for both children (ample daily time). Establish distinct surface approvers through request-entry → REQUEST04 → REQUEST12. Starting child: FLOW04(custom,soft choice) → REQUEST03(capture).
2. FLOW12(other surface) → REQUEST03 → UI12(shared fields,local approver) → UI11(mute).
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
2. LIFE04(app update/remove in its newly opened administrator terminal); Parent's editor stays open.
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
2. REQUEST02(qualified panel reveal) → REQUEST04(custom additional duration) → REQUEST08 → FLOW05 → TIME01 → UI12(increase).
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

1. V(parent,fresh) → LIFE04(install) → FILE06(notice) → LIFE02.
2. FLOW16 → FLOW03 → both forms FLOW04/REQUEST03/REQUEST12 → FLOW06 → C → FLOW08.
3. P → LIFE04(remove) → FILE06(notice) → LIFE02 → C(fresh) → FLOW08(formerly blocked,usable).
4. V(parent,fresh after the removal reboot) → LIFE04(reinstall) → LIFE05 → P(new window) → PARENT03/PARENT09/PARENT12(retained choices,zero grant) → request-entry(kiosk) → REQUEST03 → REQUEST12(cancel) → FLOW16/FLOW03(reapply) → C → FLOW08. P → LIFE04(purge) → LIFE05 → LIFE04(reinstall) → LIFE05 → P(new window) → PARENT03(defaults) → G → REQUEST01 → REQUEST03(fresh shared defaults). A removed product has no Parent window to launch; package work uses the ordinary administrator desktop/terminal. A disabled child has no overlay entry until limits are publicly enabled.

### E2E-030

Implementation status: All cases ready (151).

**Installed About and license access.** Cases 151.

Bindings: surface = parent.

1. FLOW01(child) → ABOUT01 → ABOUT02.
2. ABOUT03(previous child/settings observation). Established phase timing is unchanged.

### E2E-031

Implementation status: All cases pending.

**Feedback drafts, validation and attachment review.** Cases 152, 153, 154, 155.

Bindings: flow = draft-reopen / validation / attachments / diagnostic-export.

1. P0; draft: FEED01 → UI16(body,email) → FEED04(all formats) → FEED03; validation: FEED01 → repeat input table UI16 → FEED09; attachments: FEED01 → repeat file table FEED06/07/13; export: watch(FEED09){FEED01} → FEED08 with chooser cancel/failure/success branches.
2. DESK10(feedback) → FEED05 → FEED10(dialog,compare). draft additionally FEED10(app-exit,reset). Never FEED11.

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

Implementation status: All cases pending.

**Choose allowances and save edits.** Cases 158, 159.

Bindings: flow = boundaries / save-order.

1. P → PARENT03(off,zero,editor disabled) → FLOW16(allowance=0,final=on).
2. boundaries: repeat allowance table {PARENT06 → PARENT08 → PARENT03 → UI12}; save-order: watch(PARENT08){PARENT06(commit trigger)} for each trigger, then rapid edits and PARENT02(other).
3. LIFE01(Parent) → PARENT02(each child) → PARENT03 → UI12(last accepted values).

### E2E-036

Implementation status: All cases pending.

**Revoke when there is no active grant.** Cases 160, 161.

Bindings: balance = daily-positive / zero-total.

1. daily-positive: FLOW13(grant-only,soft included) → C → FLOW08(soft) → APP04 → P → FLOW02(positive daily,off) → UI17(on) → PARENT08 → PARENT09(G=0). zero-total: FLOW16(on,0) → PARENT09.
2. PARENT08(idle) → UI02(Revoke). Positive: PARENT17 → PARENT18(cancel) → C → APP04 → P → PARENT17 → PARENT18(confirm). Zero: UI02(disabled), then UI17(off) → PARENT08 → UI02(disabled).
3. Positive: PARENT09(D unchanged,G=0) → C → APP02(soft closed) → FLOW08(allowed usable,soft/hard denied). Zero: PARENT03(saved allowance retained).

### E2E-037

Implementation status: All cases pending.

**Use and remember the child panel option.** Cases 162, 163.

Bindings: boundary = sign-out-in / reboot.

1. FLOW16(each child,6 daily minutes) → C(first) → PANEL03 → PANEL01(default off) → PANEL02(on).
2. REQUEST02 → REQUEST12(cancel) → TIME01; DESK04 → C(fresh) or LIFE02 → C(fresh); PANEL01 → UI02(on) → UI05(Escape).
3. C(second) → PANEL01(off) → UI05(Escape); C(first) → PANEL01 → PANEL02(off) → PANEL01 → PANEL02(on) → FLOW08(allowed) → TIME04.

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

Implementation status: All cases pending.

**Search the app list and edit match rules.** Cases 184, 185, 186, 187, 188, 189.

Bindings: flow = search-filters / match-editor / match-reopen / shared-launchers / special-paths / pattern-files.

1. FLOW16(ample daily) → PARENT04(App Limits) → UI04(legend) → UI03 → PARENT12(assets).
2. Run the corresponding finite catalogue subrecipe below using PARENT10/11/13/15/16, UI16, FILE04/05 and LIFE01.
3. PARENT12 → UI12(saved/expected rule) → C → FLOW08(declared positive and negative targets). Search-only checks compare rules without changing them.

### E2E-042

Implementation status: Ready: 193. Command-help passed its complete installed
journey, collection and cleanup. Cases 190–192 remain pending.

**Read Help, About and command usage on each surface.** Cases 190, 191, 192, 193.

Bindings: surface = parent-links / child-overlay / kiosk / command-help.

1. Parent P0 → PARENT03(capture); overlay/station FLOW16(on,30) → request-entry(surface) → REQUEST03(capture); command-help V(parent) → FILE01.
2. Parent/overlay INFO01(Help) → ABOUT01; overlay additionally ABOUT02 → UI18(license viewer). Then INFO01(website,privacy,support,legal as offered). Kiosk ABOUT01 → UI03 → UI11(external actions). Command INFO02(each fixed command/manual). Parent's complete license-reading path remains owned by case 151.
3. UI18(About, only where opened) → PARENT03 or REQUEST03 → UI12. INFO01 has already closed each external destination; do not close it twice. INFO02 ends at the terminal.

Command-help binds INFO02 to `/usr/bin/oh-no-parent-control-parent --help`,
`/usr/bin/oh-no-parent-control --help`, `man oh-no-parent-control-parent` and
`man oh-no-parent-control`, in that order. Each starts at focused normal shell
input in a fresh Terminal window. Read each help's usage, identifying description
and help option; read each manual's command identity, purpose, NAME, SYNOPSIS and
DESCRIPTION. Use `q` to leave each manual. Check the returned shell prompt and
absence of management/request windows before closing Terminal normally. The
first entry uses FILE01; later entries independently open Terminal. Refuse the
desktop as command input before opening any terminal. Public observations have
the adapter's 45-second deadline and retain only semantic results, never raw
terminal text. The complete consumer is `command_help::execute` and
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

Implementation status: All cases pending.

**Review or decline an error report.** Cases 205, 206, 207.

Bindings: surface = parent / child-overlay / kiosk.

1. Parent: P → PARENT04(App Limits) → PARENT10(declared app) → PARENT13 → UI16(rejected pattern) → PARENT15(error). Request surfaces: FLOW16(on,30) → request-entry → FLOW04(custom=0.5,soft=false) → FLOW05 → reopen before cooldown → REQUEST09(error). These are the explicit public-error prefixes reused by E2E-047; its setup does not manufacture a report.
2. FEED15(review) → FEED03 → UI16(synthetic body) → FEED05 → UI02/11(surface actions) → UI18(report) → UI01(original destination).
3. Repeat the same public error: FEED15(decline) where offered → UI11(report). Parent's report window simply closes; no nonexistent report switch is assumed.

### E2E-046

Implementation status: All cases pending.

**Recover unavailable diagnostic collection.** Cases 208, 209, 210, 211, 212, 213.

Bindings: surface = parent / child-overlay / kiosk; choice = retry / without-logs.

1. Open the declared genuine failing collection with FEED01 or FEED15 while watch(FEED09) is active.
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
2. Run four rows, each as request-entry(surface) → FLOW20(entry=open) →
   APP02/APP04(existing activities) → FLOW08(S via declared route). Requests
   add 0.5 minutes: **Jamie/include → Sam/exclude → Sam/include → Jamie/exclude**.
   Included opens S and records a new activity; excluded requires its closure.
   After each row A remains usable and a new H launch remains denied. If the
   blocked grid entry is hidden, observe that and use the recipe's explicit
   command denial witness; an included grid entry must become launchable.
3. P → PARENT12(A,H,S) → UI12(original saved choices). Temporary approval
   must not rewrite the parent's access selections. Finish after the last
   excluded result; no natural wait for the long combined grant.

This completes route × request-surface coverage and both approvers × both
soft-app choices inside each case. Baseline rule permutations remain in 62–109;
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

## Additional finite branch recipes

### App catalogue and matching

Every row starts in the selected child's App Limits and finishes by reading
saved rows and, when stated, using the app as the child.

| Case | Exact block/data expansion |
| --- | --- |
| 184 search-filters | PARENT10 for exact name, a unique description word, launcher identifier, empty query and no-match query. For each query, PARENT11 for all four subsets of {precise,pattern} and all eight subsets of {allowed,hard,soft}; UI13/UI12 compares the exact intersection from the declared fixture list. Empty selections show no rows. Restore all filters, compare PARENT12 with initial policies. These 160 cheap observations do not require new logins. |
| 185 match-editor | PARENT13 → UI16 → PARENT15 for full precise target, unambiguous basename, empty text, unrelated precise target, custom same-directory wildcard, Cancel and Reset to Default. Empty/unrelated precise text stays open with explanation; Cancel preserves the earlier value; Reset saves the detected default immediately. Save a wildcard for a different directory and observe failed-save reporting, close that report, then reread confirmed choices. |
| 186 match-reopen | Save custom same-directory wildcard; change access to Allowed; LIFE01 → PARENT02 → PARENT12 verifies remembered custom wildcard. Save precise on an app with a suggested pattern; reselect the child and reopen Parent, reading the documented suggested pattern each time. Reselect precise before a subsequent save. Repeat restoration after a customer-rejected pattern save, closing its report before reading. This records the current limitation, not desired new behavior. |
| 187 shared-launchers | Two visible launchers for one supported app: PARENT16(first,Hard) → PARENT16(second,Allowed); C → FLOW08(each supported launch,denied). P → allow first → C → FLOW08(each,usable). Reverse which launcher holds the block and repeat. No claim of independent rules overriding the shared target. |
| 188 special-paths | For a known native app whose displayed precise path contains a space, then a comma, FILE05 copies its executable to the declared second name/location. PARENT16(Hard) → C → FLOW08(original and identical copy,denied), with existing distinct N usable. Repeat under Soft with no exception. These supported path cases do not assert universal copied-program control. |
| 189 pattern-files | Save a same-directory version wildcard for the prepared AppImage. FILE05 adds the next matching version and a nonmatching file; FLOW08 matching denied and existing nonmatch usable. The new nonmatch may require the documented refresh: wait up to 60 seconds through TIME03/APP02 read-only observations, then perform one declared launch. A failed uncertain launch is not retried as if it never happened. A pattern unable to preserve existing nonmatches must report failure and retain the previous rule. |

No screenshot geometry or file/process introspection supplies an app result.
FIX04 stages declared assets only; customer copies, renames, installs and rule
changes still use the listed UI blocks. Supported asset identities and normal
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

FLOW17 is qualified separately for each normal route. Lock is the desktop's
normal lock shortcut; Switch User/sign-out require reachable session controls;
close requires a real supported way to close the requesting app while the
system prompt remains open. Escape on the system prompt merely cancels
authentication and does not qualify app-close or session-leave.

If the modal/session prevents a declared route, retain that case pending with
the unavailable action. Never replace it with a signal, forced logout, console
command or private callback. On return, inspect the original balance and
restriction before new approval, and require a new system prompt.

Cooldown cases 176–178 measure from the first successful approval to the next
Request action. Reopening must complete within five seconds for the too-soon
branch; if no supported route can do so, record that prerequisite gap. Do not
extend the product cooldown or delay a response. Cases 206/207 and the request
error-report sending cases have the same public-error prerequisite.

Accounts in cases 179–183 are disposable spare accounts, prepared independently.
Users settings may require ordinary administrator authentication through AUTH04.
Remove only logged-out spare children, retaining an administrator to finish the
journey. For 182, both station and overlay remember Sam before Users changes Sam
to standard; reopen and select the remaining eligible Jamie. For 183, station
remembers Jordan, Jordan is removed while logged out, and station falls back to
Riley with Riley's own request values. A missing eligible replacement uses the
separate empty-account case instead.

### Feedback local values

Cases 152–155 run without external submission. Public state or validation
messages must establish the result; a private draft, DOM, transport payload or
collector read is never substituted.

| Owner | Complete finite data and checks |
| --- | --- |
| 152 formatting/draft | Synthetic heading, bold, italic, underline, strike, numbered/bulleted list, quote, code block, link and remove-formatting. FEED04/UI24 reads actual public range attributes, not only a pressed toolbar control. Include one file and a synthetic reply address for close/reopen preservation. App exit/relaunch resets text, formatting, address and files. |
| 153 text/email | Empty, whitespace, ordinary ASCII, exactly 5000 and 5001 UTF-16 units, and mixed emoji at those boundaries. Empty/valid synthetic/malformed reply addresses. Include a hidden control character and the declared excessive-formatting document; read rejection without submitting valid content. Exact hidden-character and formatting fixtures come from the current specification/maintained transport limits, and must be reviewed before binding. |
| 154 attachments | Chooser Cancel; one file then Remove; 5 files accepted and a sixth rejected; per-file 5 MiB accepted and 5 MiB+1 rejected. With diagnostics excluded, two files totaling 8 MiB accepted and 8 MiB+1 rejected. One invalid file in a multi-selection adds none and preserves existing attachments. Names of 180 characters accepted, 181 and hidden controls rejected; an empty filename is not creatable through normal file tools and remains technical validation. |
| 154 original file change | FEED06 attaches the synthetic text file; FILE08 opens its original in the ordinary editor and FILE09 saves longer declared synthetic text. DESK10(feedback) → FEED07 reads the original attachment's unchanged name/size, then FEED13 → FEED06 re-adds it → FEED07 reads the larger size. Frozen contents are inspected only if the app offers a genuine public preview; otherwise byte immutability remains transport coverage. |
| 155 diagnostic ZIP | Observe collection, then save via FILE03. Cancel preserves draft and prepared archive. Choose a visibly unwritable destination, read the save error, then choose a writable location. Open the saved ZIP in a normal archive viewer; read the system-information entry and Parent/Child/Kiosk/Broker folders, empty folders where applicable, and the actual bounded contents. Do not open original product logs. |
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
| 216 app-exit | Offline FEED09(retry) → UI18(feedback) → UI18(Parent) → LIFE06(reconnect) → SEARCH05(Parent) → FEED01 → FEED03(reset, no resumed outbox). Do not claim an earlier request could not have reached the service. |
| 217 retry-expired | Offline FEED09(retry) → TIME03(up to the actual 15-minute retry window, with observation checkpoints) → FEED09(expired) → FEED03(preserved draft and duplicate-risk explanation). Reconnect and close; do not submit again. Budget 1800 seconds includes preparation and cleanup. |
| 218 overlay-stop / 219 kiosk-stop | Offline FEED09(retry) → FEED17 → UI03(stop warning) → FEED18(stay) → FEED17 → FEED18(stop) → UI11(report) → DESK01 or GDM01. Reconnect through Parent afterward. A stop cannot recall a request already accepted. |
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
is allowed. Every case has a 3600-second execution bound.

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

## Coverage ownership and remaining limits

Repeated setup and sanity observations do not count as duplicate primary
coverage. Each unique outcome has one owner below; a continuous journey may
reuse it to reach a later distinct outcome.

| Behavior | Primary owner |
| --- | --- |
| Installation/defaults; account discovery; standard management exclusion | 2; 3–4 and 179–183 for actual Users changes; 5–6 |
| Allowance values/saves; enable/edit/disable and child access | 158–159; 7–12 |
| App-rule transitions; launch routes; catalogue/matching; updates | 13–16; 62–109; 184–189; 110–111 |
| Active-grant revocation; no-grant; expired grant with daily time | 17–20; 160–161; 170 |
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

The [engineering reconciliation](E2E-Building-Blocks.md#inventory-reconciliation)
retains every displaced internal assertion, including fault cases 140–150,
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
