# E2E task queue

This is the canonical checklist of the [master execution plan](E2E-Execution-Plan.md).
Start each session at that plan's **Next task**. Its pointer names the first
unchecked active row below. This table is one fixed sequence: follow it from
top to bottom, including provider qualification and retained regressions.
An incomplete or blocked row stays current; there is no second queue to consult.

The master owns live acceptance, coverage refresh and close-out. A checked row
records its delivered scope at completion time. It does not override a later
pending block/provider qualification; see the [status vocabulary](README.md#status-vocabulary).
The completed tasks remain intact; the first new rows restore their missing
provider bindings under the current mandate.

## Ordered task queue

Requires lists **task IDs**, not block IDs. Reuse their delivered capability
scopes; prerequisites apply transitively. Block IDs live in Delivered scope and
the catalogue. A qualified slice can be reused while unrelated bindings remain
pending; consumers do not wait for their own scenario to qualify that slice.
`Baseline` means existing qualified source and the standard guarded envelope,
not an exemption for an unqualified provider. Table order is execution order;
IDs and filenames are stable labels, not sort keys. The customer-first rule is
already reflected here: each newly enabled scenario or retained regression
precedes the next capability, with simultaneously enabled cases in numeric order.
Each scenario row owns one numeric case; finite checks inside its complete recipe
do not create a task-selection loop.
Scenario execution is never a prerequisite of another scenario.

Minutes are estimates, never stop timers. Check completion only after the
master's acceptance and cleanup. Every unfinished active row has one brief;
briefs contain acceptance requirements, not alternate next-task decisions.
Scheduling repairs update this table and the master's pointer together and run
`tools/run-tests unit 'tests/unit/test_e2e_plan.py'`.

Ordinary customer capabilities/cases come first, followed by the retained system
obligations. Work requiring sending authorization, manual Lunar assets or an
unproven public trigger follows in this same fixed sequence; natural calendar
windows are last. This order prevents known external prerequisites from sitting
in front of ordinary implementation. It does not waive acceptance or authorize
skipping a blocked row. Plan separate real calendar windows in table order.

| Done | ID | Task | Requires tasks | Delivered scope | Minutes |
| --- | --- | --- | --- | --- | --- |
| [x] | 192 | Align inventory regression fixtures with the current metadata | Baseline | Host-only metadata compatibility; no product readiness change | 25–45 |
| [x] | 001 | Visible terminal launch, submission and denial | Baseline | FILE01, FILE02, FILE06 | 25–45 |
| [x] | 002 | E2E-004: terminal | 001 | Cases 6 | 30–55 |
| [x] | 185c | Read installed command help and manuals | 001 | INFO02 | 20–40 |
| [x] | 235 | E2E-042: command-help | 185c | Cases 193 | 30–55 |
| [x] | 003 | Open session controls and switch or sign out | Baseline | DESK02, DESK03, DESK04 | 35–55 |
| [x] | 011 | Enter and read the request station | Baseline | REQUEST01, REQUEST03 | 35–55 |
| [x] | 013 | Observe request results and exits | 011 | REQUEST11/12 kiosk Cancel and Escape | 25–45 |
| [x] | 010 | Set one public toggle explicitly | Baseline | UI17 Parent Screen time limit binding; installed qualification and owned cleanup passed | 25–45 |
| [x] | 017 | Observe Parent save results | 010 | PARENT08 snapshot saved/control states; installed qualification and owned cleanup passed | 25–45 |
| [ ] | 003a | [Qualify ordinary GDM account and recipient proofs](E2E-Tasks/003a-gdm-recipient.md) | 011 | GDM01/02 ordinary prompt entry; GDM03/04/08/09 recipient, refusal and Escape-return proofs | 40–60 |
| [ ] | 001r | [Requalify retained case 1](E2E-Tasks/001r-case-1-regression.md) | 003a | Retained regression 1; complete graphical/serial recipe and capture/return reconciliation | 30–50 |
| [ ] | 003b | [Qualify fresh desktop entry and keyring Cancel](E2E-Tasks/003b-desktop-keyring.md) | 003a | GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback | 40–60 |
| [ ] | 003c | [Qualify Shell session controls and Switch User](E2E-Tasks/003c-switch-user.md) | 003b | DESK02/03 current Shell provider route and independently observed GDM return | 35–55 |
| [ ] | 003d | [Qualify confirmed Shell logout](E2E-Tasks/003d-logout.md) | 003b, 003c | DESK04 current Shell logout/confirmation route and independently observed GDM return | 35–55 |
| [ ] | 001s | [Qualify Shell search and application launch](E2E-Tasks/001s-shell-search.md) | 003b, 003c, 003d | SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry | 40–60 |
| [ ] | 003r | [Requalify retained case 3](E2E-Tasks/003r-case-3-regression.md) | 001s | Retained regression 3; existing/new-child discovery | 30–50 |
| [ ] | 004r | [Requalify retained case 4](E2E-Tasks/004r-case-4-regression.md) | 001s | Retained regression 4; no-child discovery | 30–50 |
| [ ] | 005r | [Requalify retained case 5](E2E-Tasks/005r-case-5-regression.md) | 001s | Retained regression 5; standard-account app-grid unavailability | 30–50 |
| [ ] | 001t | [Qualify the installed terminal adapter](E2E-Tasks/001t-terminal-provider.md) | 001s | FILE01/02/06 terminal command, help/denial projections and normal close/return | 40–60 |
| [ ] | 002r | [Requalify retained case 6](E2E-Tasks/002r-case-6-regression.md) | 001t | Retained regression 6; full terminal management denial | 30–50 |
| [ ] | 235r | [Requalify retained case 193](E2E-Tasks/235r-case-193-regression.md) | 001t | Retained regression 193; both installed commands/manuals and terminal return | 30–50 |
| [ ] | 185l | [Qualify the installed license viewer](E2E-Tasks/185l-license-provider.md) | 001s | ABOUT02/03 actual license handler identity/content and close/return | 40–60 |
| [ ] | 151r | [Requalify retained case 151](E2E-Tasks/151r-case-151-regression.md) | 185l | Retained regression 151; complete About/license recipe and migration regression close-out | 30–50 |
| [ ] | 012 | [Select kiosk accounts and read availability](E2E-Tasks/012-request-choices.md) | 011, 017, 003d | REQUEST04 kiosk child/approver; REQUEST08 unavailable state | 25–45 |
| [ ] | 018 | [E2E-017: disabled-child](E2E-Tasks/018-case-57.md) | 012, 013 | Cases 57 | 30–50 |
| [ ] | 024 | [Prepare empty kiosk account profiles](E2E-Tasks/024-kiosk-fixtures.md) | 012 | FIX03 no-child/no-approver profiles | 40–60 |
| [ ] | 026 | [E2E-017: no-child](E2E-Tasks/026-case-54.md) | 024, 013 | Cases 54 | 25–45 |
| [ ] | 026b | [E2E-017: no-parent](E2E-Tasks/026b-case-55.md) | 024, 013 | Cases 55 | 25–45 |
| [ ] | 004a | [Give repeated public operations distinct stages](E2E-Tasks/004a-give-repeated-public-operations-distinct-stages.md) | Baseline | JourneyPlan repeated invocation IDs and assertion placement | 30–50 |
| [ ] | 004 | [Allow distinct single-use authentication challenges](E2E-Tasks/004-challenges.md) | 003d, 004a | UI19/GDM05 distinct single-use authentication challenges | 40–60 |
| [ ] | 005a | [Start a graphical journey before product installation](E2E-Tasks/005a-product-free-entry.md) | 001t, 004 | Product-free graphical start and verified package staging | 30–50 |
| [ ] | 005 | [Qualify terminal administrator password input](E2E-Tasks/005-terminal-auth.md) | 005a | AUTH03; FILE06 package challenge/completion | 40–60 |
| [ ] | 006 | [Perform a customer package operation](E2E-Tasks/006-package-command.md) | 005 | LIFE04 install only | 35–55 |
| [ ] | 007 | [Observe a deliberate customer reboot](E2E-Tasks/007-customer-reboot.md) | 006 | LIFE02 | 40–60 |
| [ ] | 077a | [Read app rows and initial access choices](E2E-Tasks/077a-app-row-observations.md) | Baseline | PARENT12; UI13 complete public app-row observations | 20–40 |
| [ ] | 008 | [E2E-002: clean](E2E-Tasks/008-case-2.md) | 007, 013, 077a | Cases 2 | 40–60 |
| [ ] | 029 | [Open feedback and read synthetic drafts](E2E-Tasks/029-feedback-read.md) | Baseline | FEED01, FEED03 | 25–45 |
| [ ] | 009 | [Replace a nonsecret field value](E2E-Tasks/009-text.md) | 029 | UI16 | 25–45 |
| [ ] | 040 | [Choose ordinary daily allowances](E2E-Tasks/040-allowance.md) | 009, 017 | PARENT05/06 valid ordinary values | 25–45 |
| [ ] | 194 | [Read an expanded time explanation](E2E-Tasks/194-read-an-expanded-time-explanation.md) | 040 | PARENT20 | 20–40 |
| [ ] | 041 | [Read remaining time and configure time controls](E2E-Tasks/041-time-explanation.md) | 194 | PARENT09, FLOW02 | 25–45 |
| [ ] | 180 | [Set an allowance for a named child](E2E-Tasks/180-set-an-allowance-for-a-named-child.md) | 041 | FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup | 15–30 |
| [ ] | 203 | [E2E-036: zero-total](E2E-Tasks/203-case-161.md) | 180 | Cases 161 | 30–55 |
| [ ] | 028 | [Close and reopen Parent](E2E-Tasks/028-app-restart.md) | Baseline | LIFE01 | 25–45 |
| [ ] | 040a | [Qualify daily-allowance boundaries](E2E-Tasks/040a-allowance-boundaries.md) | 040 | PARENT06 boundary/invalid values; PARENT08 validation | 25–45 |
| [ ] | 200 | [E2E-035: boundaries](E2E-Tasks/200-case-158.md) | 180, 040a, 028 | Cases 158 | 30–55 |
| [ ] | 012a | [Choose kiosk duration and app-access values](E2E-Tasks/012a-request-duration.md) | 012, 009 | REQUEST04 duration; REQUEST05/06/08 and REQUEST09 invalid-input branch, kiosk | 30–50 |
| [ ] | 014 | [Compose prepared request choices](E2E-Tasks/014-request-flow.md) | 012a, 013 | FLOW04 kiosk | 25–45 |
| [ ] | 015 | [E2E-015: kiosk-cancel](E2E-Tasks/015-case-47.md) | 180, 014 | Cases 47 | 25–45 |
| [ ] | 015b | [E2E-015: kiosk-escape](E2E-Tasks/015b-case-48.md) | 180, 014 | Cases 48 | 25–45 |
| [ ] | 019a | [Inspect and qualify the kiosk MATE prompt entry](E2E-Tasks/019a-mate-prompt.md) | 012a, 004, 013 | MATE provider owner, real request context and guarded Cancel/form return | 35–55 |
| [ ] | 019 | [Qualify the real selected-parent approval prompt](E2E-Tasks/019-auth-prompt.md) | 012a, 004, 019a | REQUEST09, AUTH01 kiosk | 40–60 |
| [ ] | 020a | [Qualify kiosk secret submission and automatic approved exit](E2E-Tasks/020a-kiosk-approval.md) | 019, 013 | AUTH02 kiosk approval; REQUEST11/12 success and automatic GDM exit | 40–60 |
| [ ] | 020 | [Qualify kiosk rejection, Cancel and immediate approved exit](E2E-Tasks/020-auth-result.md) | 019, 013, 020a | AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits | 40–60 |
| [ ] | 021 | [Compose approval, kiosk time and rejection](E2E-Tasks/021-approval-flow.md) | 020, 014 | FLOW05/06/07 kiosk | 35–55 |
| [ ] | 022 | [E2E-016: approved](E2E-Tasks/022-case-50.md) | 180, 021 | Cases 50 | 30–50 |
| [ ] | 023 | [E2E-016: denied](E2E-Tasks/023-case-51.md) | 180, 021 | Cases 51 | 25–45 |
| [ ] | 023b | [E2E-016: cancelled](E2E-Tasks/023b-case-52.md) | 180, 021 | Cases 52 | 25–45 |
| [ ] | 024a | [Prepare multiple and ineligible-approver profiles](E2E-Tasks/024a-eligible-kiosk-fixtures.md) | 020 | FIX03 multiple/ineligible-approver profiles | 30–50 |
| [ ] | 025 | [E2E-017: multiple](E2E-Tasks/025-case-53.md) | 024a, 180 | Cases 53 | 30–55 |
| [ ] | 027 | [E2E-017: ineligible-parent](E2E-Tasks/027-case-56.md) | 024a, 180 | Cases 56 | 30–55 |
| [ ] | 185k | [Read restricted station About](E2E-Tasks/185k-read-restricted-station-about.md) | 014 | ABOUT01 kiosk and unavailable external actions | 25–45 |
| [ ] | 234 | [E2E-042: kiosk](E2E-Tasks/234-case-192.md) | 185k, 180 | Cases 192 | 30–55 |
| [ ] | 030 | [Read privacy and preserve a dialog draft](E2E-Tasks/030-feedback-privacy.md) | 009 | FEED05; FEED10 dialog persistence | 25–40 |
| [ ] | 031 | [Observe feedback validation and Send availability](E2E-Tasks/031-feedback-states.md) | 009 | FEED09 validation/control snapshots | 20–40 |
| [ ] | 033 | [Apply and observe rich-text formatting](E2E-Tasks/033-format.md) | 009 | UI24, FEED04 | 30–50 |
| [ ] | 044a | [Return to an already-open window on one desktop](E2E-Tasks/044a-window-switch.md) | 001t, 009 | DESK10 same-desktop window switching | 20–40 |
| [ ] | 032 | [E2E-031: validation](E2E-Tasks/032-case-153.md) | 030, 031, 033, 044a | Cases 153 | 30–50 |
| [ ] | 036c | [Qualify synthetic files and Nautilus navigation](E2E-Tasks/036c-files-navigation.md) | 009, 001s | FIX04 synthetic files; FILE07 and FILE04 exact Nautilus location/entry observations | 40–60 |
| [ ] | 036d | [Qualify public file copy and destination readback](E2E-Tasks/036d-files-copy.md) | 036c | FILE05 copy; exact source/destination and public resulting entry | 30–50 |
| [ ] | 036 | [Qualify file rename and compose synthetic-file operations](E2E-Tasks/036-files.md) | 009, 036d | FILE07/04/05; FIX04 synthetic files | 35–55 |
| [ ] | 037 | [Select multiple files or cancel through the installed chooser](E2E-Tasks/037-file-chooser.md) | 036, 029, 031 | FILE03 installed feedback open/cancel; actual provider binding | 25–45 |
| [ ] | 038 | [Add, inspect, preview and remove attachments](E2E-Tasks/038-attachments.md) | 037, 010, 031 | FEED06, FEED07, FEED12, FEED13 | 40–60 |
| [ ] | 030a | [Observe draft reset after Parent exits](E2E-Tasks/030a-feedback-reset.md) | 028, 030 | FEED10 app-exit reset | 20–40 |
| [ ] | 034 | [E2E-031: draft-reopen](E2E-Tasks/034-case-152.md) | 033, 030a, 038, 044a | Cases 152 | 30–50 |
| [ ] | 195a | [Qualify the installed text-document handler](E2E-Tasks/195a-document-open.md) | 036 | FILE08 text-document identity/content and normal close/return | 40–60 |
| [ ] | 195 | [Qualify archive contents and compose document opening](E2E-Tasks/195-open-a-customer-document-or-archive.md) | 036, 195a | FILE08 | 25–45 |
| [ ] | 196 | [Edit and save an open synthetic document](E2E-Tasks/196-edit-and-save-an-open-synthetic-document.md) | 195 | FILE09 | 25–45 |
| [ ] | 039 | [E2E-031: attachments](E2E-Tasks/039-case-154.md) | 038, 030, 196, 044a | Cases 154 | 35–55 |
| [ ] | 016 | [Start and finish bounded public-state traces](E2E-Tasks/016-trace.md) | 004a, 031 | UI25/26 trace start/readiness and finish | 40–60 |
| [ ] | 016a | [Compose observation around one caller input](E2E-Tasks/016a-compose-observation-around-one-caller-input.md) | 016 | UI22 | 15–30 |
| [ ] | 017a | [Observe saving while a Parent control changes](E2E-Tasks/017a-parent-save-trace.md) | 017, 016a | PARENT08 transition mode | 25–45 |
| [ ] | 201 | [E2E-035: save-order](E2E-Tasks/201-case-159.md) | 180, 017a, 028 | Cases 159 | 30–55 |
| [ ] | 031a | [Observe diagnostic collection from its start](E2E-Tasks/031a-feedback-collection.md) | 016a, 030 | FEED09 collection trace | 25–45 |
| [ ] | 037a | [Save to a selected location through the installed chooser](E2E-Tasks/037a-save-chooser.md) | 037, 031a | FILE03 installed feedback save; actual provider binding | 20–40 |
| [ ] | 045 | [Save and open customer-selected diagnostics](E2E-Tasks/045-diagnostic-export.md) | 037a, 044a, 195 | FEED08 | 25–45 |
| [ ] | 046 | [E2E-031: diagnostic-export](E2E-Tasks/046-case-155.md) | 045 | Cases 155 | 35–55 |
| [ ] | 052c | [Wait a bounded real interval under the attempt guard](E2E-Tasks/052c-wait-a-bounded-real-interval-under-the-attempt-guard.md) | Baseline | TIME03 | 15–30 |
| [ ] | 185w | [Qualify the Parent website destination](E2E-Tasks/185w-website-destination.md) | 044a, 001s | INFO01 Parent website browser identity and close/return | 35–55 |
| [ ] | 185v | [Qualify the Parent privacy destination](E2E-Tasks/185v-privacy-destination.md) | 185w | INFO01 Parent privacy page identity and close/return | 25–45 |
| [ ] | 185s | [Qualify the Parent support mail destination](E2E-Tasks/185s-support-destination.md) | 044a, 001s | INFO01 Parent support mail recipient/subject and close without sending | 35–55 |
| [ ] | 185p | [Read Parent Help and legal notices and complete information links](E2E-Tasks/185p-read-parent-information-links.md) | 044a, 185w, 185v, 185s, 185l | INFO01 Parent | 25–45 |
| [ ] | 232 | [E2E-042: parent-links](E2E-Tasks/232-case-190.md) | 185p | Cases 190 | 30–55 |
| [ ] | 193 | [Operate public connectivity controls](E2E-Tasks/193-operate-public-connectivity-controls.md) | 003d, 010, 044a | LIFE06 | 25–45 |
| [ ] | 035p | [Install the declared native app fixtures](E2E-Tasks/035p-native-fixtures.md) | 006, 077a | FIX04 native assets; LIFE04 fixture installation | 25–45 |
| [ ] | 077 | [Search and filter the public app catalogue](E2E-Tasks/077-catalogue.md) | 010, 035p, 009, 077a | PARENT10, PARENT11 | 35–55 |
| [ ] | 226 | [E2E-041: search-filters](E2E-Tasks/226-case-184.md) | 077, 180 | Cases 184 | 30–55 |
| [ ] | 078 | [Edit, save, cancel or reset one match rule](E2E-Tasks/078-match-editor.md) | 077, 017 | PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts | 25–45 |
| [ ] | 079 | [Save app access choices and compose one rule edit](E2E-Tasks/079-policy.md) | 078 | PARENT16 and FLOW03 public app-policy editing | 40–60 |
| [ ] | 186 | [Review a rejected Parent rule's report](E2E-Tasks/186-review-a-rejected-parent-rule-s-report.md) | 078, 030 | PARENT15 failed-save; FEED15 Parent and report-close binding | 25–45 |
| [ ] | 247 | [E2E-045: parent](E2E-Tasks/247-case-205.md) | 186 | Cases 205 | 30–55 |
| [ ] | 043 | [Qualify fresh child login and time denial](E2E-Tasks/043-unlock.md) | 004, 041 | GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return | 30–50 |
| [ ] | 052 | [Observe the child countdown or its absence](E2E-Tasks/052-countdown.md) | 043 | TIME01 child-desktop presence and limits-off absence | 25–45 |
| [ ] | 061 | [E2E-015: kiosk-approved](E2E-Tasks/061-case-49.md) | 180, 021, 052 | Cases 49 | 30–55 |
| [ ] | 070 | [Double-click kiosk Request and observe one prompt](E2E-Tasks/070-double-request.md) | 020, 016a | UI20; REQUEST10 kiosk binding | 35–55 |
| [ ] | 074 | [E2E-014: kiosk-predefined](E2E-Tasks/074-case-41.md) | 180, 070, 052 | Cases 41 | 40–60 |
| [ ] | 075 | [E2E-014: kiosk-custom](E2E-Tasks/075-case-42.md) | 180, 070, 052 | Cases 42 | 40–60 |
| [ ] | 035 | [Launch and use the native app fixtures](E2E-Tasks/035-native-app.md) | 035p, 001t, 009 | APP01/02/03 native grid/command usable scope | 30–50 |
| [ ] | 047 | [Record app activity and compose launch/use](E2E-Tasks/047-app-activity.md) | 035, 043 | APP04; FLOW08 native usable-app scope | 25–45 |
| [ ] | 048 | [Reveal the child's request entry](E2E-Tasks/048-shell-panel.md) | 043, 011 | DESK12, REQUEST02/03 overlay entry/readback | 40–60 |
| [ ] | 048a | [Choose overlay values and cancel or escape](E2E-Tasks/048a-overlay-choices.md) | 048, 014, 047 | Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04 | 30–50 |
| [ ] | 049 | [E2E-015: child-overlay-cancel](E2E-Tasks/049-case-44.md) | 180, 048a | Cases 44 | 25–45 |
| [ ] | 049b | [E2E-015: child-overlay-escape](E2E-Tasks/049b-case-45.md) | 180, 048a | Cases 45 | 25–45 |
| [ ] | 185o | [Read overlay About and links](E2E-Tasks/185o-read-overlay-about-and-links.md) | 048a, 044a, 185p, 185l | ABOUT01/02 and INFO01 overlay | 25–45 |
| [ ] | 233 | [E2E-042: child-overlay](E2E-Tasks/233-case-191.md) | 185o, 180 | Cases 191 | 30–55 |
| [ ] | 048c | [Qualify the overlay Shell prompt and Cancel](E2E-Tasks/048c-shell-prompt.md) | 048a, 019, 004 | Shell Polkit AUTH01 overlay recipient and guarded Cancel/preserved-form result | 40–60 |
| [ ] | 048d | [Qualify overlay approval and automatic return](E2E-Tasks/048d-overlay-approved-exit.md) | 048c, 021 | AUTH02 overlay approval; REQUEST11/12 success and automatic child return | 40–60 |
| [ ] | 048b | [Complete overlay rejection, exits and approval flows](E2E-Tasks/048b-overlay-approval.md) | 048a, 021, 048c, 048d | Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07 | 35–55 |
| [ ] | 060 | [E2E-015: child-overlay-approved](E2E-Tasks/060-case-46.md) | 180, 048b, 052 | Cases 46 | 30–55 |
| [ ] | 070a | [Observe one prompt after an overlay double-click](E2E-Tasks/070a-overlay-double-request.md) | 070, 048b | REQUEST10 overlay binding | 20–40 |
| [ ] | 071 | [E2E-014: child-overlay-predefined](E2E-Tasks/071-case-38.md) | 180, 070a, 052 | Cases 38 | 40–60 |
| [ ] | 072 | [E2E-014: child-overlay-custom](E2E-Tasks/072-case-39.md) | 180, 070a, 052 | Cases 39 | 40–60 |
| [ ] | 042 | [Observe and qualify an intended lock challenge](E2E-Tasks/042-lock-recipient.md) | 003d | DESK05, DESK06, DESK07 | 40–60 |
| [ ] | 043a | [Qualify retained unlock and return from the lock screen](E2E-Tasks/043a-retained-unlock.md) | 043, 042 | GDM02 retained-child lock entry; DESK08/11 | 35–55 |
| [ ] | 044 | [Visit retained users and existing windows](E2E-Tasks/044-retained-entry.md) | 043a, 044a | DESK09; FLOW15 and FLOW01 retained scopes | 40–60 |
| [ ] | 073 | [E2E-014: child-overlay-rest-of-day](E2E-Tasks/073-case-40.md) | 180, 070a, 052, 044, 052c | Cases 40 | 40–60 |
| [ ] | 076 | [E2E-014: kiosk-rest-of-day](E2E-Tasks/076-case-43.md) | 180, 070, 052, 044, 052c, 021 | Cases 43 | 40–60 |
| [ ] | 155 | [Compare per-child choices across request surfaces](E2E-Tasks/155-cross-surface.md) | 048a, 044, 180 | FLOW12 current choices | 35–55 |
| [ ] | 156 | [E2E-018: overlay-to-kiosk-first](E2E-Tasks/156-case-58.md) | 155 | Cases 58 | 25–45 |
| [ ] | 156b | [E2E-018: overlay-to-kiosk-second](E2E-Tasks/156b-case-59.md) | 155 | Cases 59 | 25–45 |
| [ ] | 157 | [E2E-018: kiosk-to-overlay-first](E2E-Tasks/157-case-60.md) | 155 | Cases 60 | 25–45 |
| [ ] | 157b | [E2E-018: kiosk-to-overlay-second](E2E-Tasks/157b-case-61.md) | 155 | Cases 61 | 25–45 |
| [ ] | 047a | [Compose retained app visits for distinct users](E2E-Tasks/047a-retained-app-visits.md) | 047, 044 | FLOW09 and FLOW14 distinct-user retention | 30–50 |
| [ ] | 050 | [Cancel and confirm grant revocation](E2E-Tasks/050-revocation.md) | 021, 044 | PARENT17, PARENT18 | 35–55 |
| [ ] | 051 | [Compose the daily-only time profile](E2E-Tasks/051-time-profiles-daily.md) | 180, 003d | FLOW13 daily-only, fresh/same Parent entry with observed G=0 | 25–45 |
| [ ] | 052a | [Measure displayed countdown ticks](E2E-Tasks/052a-countdown-ticks.md) | 052, 051, 052c | TIME02 minute/final-second ticks | 30–50 |
| [ ] | 062 | [Use an app until a natural enforced lock](E2E-Tasks/062-natural-expiry.md) | 052a, 047 | TIME04 | 35–55 |
| [ ] | 063 | [E2E-008: retained-unlock](E2E-Tasks/063-case-21.md) | 062, 043a | Cases 21 | 35–55 |
| [ ] | 064 | [E2E-008: fresh-login](E2E-Tasks/064-case-22.md) | 062, 050 | Cases 22 | 40–60 |
| [ ] | 052b | [Prove countdown absence on other surfaces](E2E-Tasks/052b-countdown-absence.md) | 052, 043a | TIME01 lock/GDM/other-user absence | 20–40 |
| [ ] | 181h | [Read the countdown hover explanation](E2E-Tasks/181h-read-the-countdown-hover-explanation.md) | 052 | DESK12 showing countdown binding; UI27 and PANEL03 | 25–45 |
| [ ] | 059 | [E2E-011: daily-only](E2E-Tasks/059-case-27.md) | 052b, 181h, 044, 062 | Cases 27 | 35–55 |
| [ ] | 065 | [Compose grant-only and combined time profiles](E2E-Tasks/065-time-profiles-grant.md) | 051, 050 | FLOW13 grant-only/combined; retained entry and explicit revoke preparation | 30–50 |
| [ ] | 066 | [E2E-010: parent](E2E-Tasks/066-case-25.md) | 065, 052a, 047a | Cases 25 | 35–55 |
| [ ] | 067 | [E2E-010: other-child](E2E-Tasks/067-case-26.md) | 065, 052a, 047a | Cases 26 | 35–55 |
| [ ] | 068 | [E2E-011: grant-only](E2E-Tasks/068-case-28.md) | 065, 052b, 181h, 062 | Cases 28 | 35–55 |
| [ ] | 069 | [E2E-011: combined](E2E-Tasks/069-case-29.md) | 065, 052b, 181h, 062 | Cases 29 | 35–55 |
| [ ] | 181m | [Operate the countdown context menu](E2E-Tasks/181m-operate-the-countdown-context-menu.md) | 181h | UI28 and PANEL01/02 | 25–45 |
| [ ] | 204 | [E2E-037: sign-out-in](E2E-Tasks/204-case-162.md) | 181m, 048a, 062, 044 | Cases 162 | 30–55 |
| [ ] | 205 | [E2E-037: reboot](E2E-Tasks/205-case-163.md) | 181m, 048a, 062, 044, 007 | Cases 163 | 30–55 |
| [ ] | 197 | [Compose overlay approval and return](E2E-Tasks/197-compose-approval-and-return-to-the-child.md) | 048b, 044, 052 | FLOW20 overlay new/open form | 20–40 |
| [ ] | 265 | [E2E-048: daily-only-child-overlay](E2E-Tasks/265-case-223.md) | 197, 052c, 051 | Cases 223; gate in brief | 30–55 |
| [ ] | 267 | [E2E-048: grant-only-child-overlay](E2E-Tasks/267-case-225.md) | 197, 052c, 065 | Cases 225; gate in brief | 30–55 |
| [ ] | 271 | [E2E-048: grant-dominant-child-overlay](E2E-Tasks/271-case-229.md) | 197, 052c, 065 | Cases 229; gate in brief | 30–55 |
| [ ] | 197k | [Compose kiosk approval and child entry](E2E-Tasks/197k-kiosk-approval-return.md) | 021, 044, 052 | FLOW20 kiosk new/open form and fresh/retained child | 25–45 |
| [ ] | 266 | [E2E-048: daily-only-kiosk](E2E-Tasks/266-case-224.md) | 197k, 052c, 051 | Cases 224; gate in brief | 30–55 |
| [ ] | 268 | [E2E-048: grant-only-kiosk](E2E-Tasks/268-case-226.md) | 197k, 052c, 065 | Cases 226; gate in brief | 30–55 |
| [ ] | 272 | [E2E-048: grant-dominant-kiosk](E2E-Tasks/272-case-230.md) | 197k, 052c, 065 | Cases 230; gate in brief | 30–55 |
| [ ] | 079a | [Observe native policy denial and existing-window closure](E2E-Tasks/079a-observe-native-policy-denial-and-existing-window-closure.md) | 079, 047, 044 | APP02 and FLOW08 native grid/command policy results | 35–55 |
| [ ] | 053 | [E2E-005: daily-only-new](E2E-Tasks/053-case-7.md) | 079a, 180, 052 | Cases 7 | 40–60 |
| [ ] | 054 | [E2E-005: daily-only-retained](E2E-Tasks/054-case-8.md) | 079a, 180, 052 | Cases 8 | 40–60 |
| [ ] | 055 | [E2E-005: grant-only-new](E2E-Tasks/055-case-9.md) | 079a, 180, 052, 021 | Cases 9 | 40–60 |
| [ ] | 056 | [E2E-005: grant-only-retained](E2E-Tasks/056-case-10.md) | 079a, 180, 052, 021 | Cases 10 | 40–60 |
| [ ] | 057 | [E2E-005: combined-new](E2E-Tasks/057-case-11.md) | 079a, 180, 052, 021 | Cases 11 | 40–60 |
| [ ] | 058 | [E2E-005: combined-retained](E2E-Tasks/058-case-12.md) | 079a, 180, 052, 021 | Cases 12 | 40–60 |
| [ ] | 090 | [E2E-019: native-grid-allowed-enabled](E2E-Tasks/090-case-62.md) | 079a, 180 | Cases 62 | 25–45 |
| [ ] | 090b | [E2E-019: native-grid-allowed-disabled](E2E-Tasks/090b-case-63.md) | 079a, 180 | Cases 63 | 25–45 |
| [ ] | 091 | [E2E-019: native-grid-hard-blocked-enabled](E2E-Tasks/091-case-64.md) | 079a, 180 | Cases 64 | 25–45 |
| [ ] | 091b | [E2E-019: native-grid-hard-blocked-disabled](E2E-Tasks/091b-case-65.md) | 079a, 180 | Cases 65 | 25–45 |
| [ ] | 092 | [E2E-019: native-grid-soft-blocked-enabled](E2E-Tasks/092-case-66.md) | 079a, 180 | Cases 66 | 25–45 |
| [ ] | 092b | [E2E-019: native-grid-soft-blocked-disabled](E2E-Tasks/092b-case-67.md) | 079a, 180 | Cases 67 | 25–45 |
| [ ] | 099 | [E2E-019: native-command-allowed-enabled](E2E-Tasks/099-case-80.md) | 079a, 180 | Cases 80 | 25–45 |
| [ ] | 099b | [E2E-019: native-command-allowed-disabled](E2E-Tasks/099b-case-81.md) | 079a, 180 | Cases 81 | 25–45 |
| [ ] | 100 | [E2E-019: native-command-hard-blocked-enabled](E2E-Tasks/100-case-82.md) | 079a, 180 | Cases 82 | 25–45 |
| [ ] | 100b | [E2E-019: native-command-hard-blocked-disabled](E2E-Tasks/100b-case-83.md) | 079a, 180 | Cases 83 | 25–45 |
| [ ] | 101 | [E2E-019: native-command-soft-blocked-enabled](E2E-Tasks/101-case-84.md) | 079a, 180 | Cases 84 | 25–45 |
| [ ] | 101b | [E2E-019: native-command-soft-blocked-disabled](E2E-Tasks/101b-case-85.md) | 079a, 180 | Cases 85 | 25–45 |
| [ ] | 227 | [E2E-041: match-editor](E2E-Tasks/227-case-185.md) | 186, 180, 079a | Cases 185 | 30–55 |
| [ ] | 228 | [E2E-041: match-reopen](E2E-Tasks/228-case-186.md) | 186, 079, 028, 180, 079a | Cases 186 | 30–55 |
| [ ] | 229 | [E2E-041: shared-launchers](E2E-Tasks/229-case-187.md) | 079a, 180 | Cases 187 | 30–55 |
| [ ] | 079b | [Compose a named app-rule set](E2E-Tasks/079b-compose-a-named-app-rule-set.md) | 079, 044 | FLOW19 | 15–30 |
| [ ] | 080 | [E2E-006: enabled-precise](E2E-Tasks/080-case-13.md) | 079a, 079b, 047a, 065, 028 | Cases 13 | 40–60 |
| [ ] | 081 | [E2E-006: enabled-pattern](E2E-Tasks/081-case-14.md) | 079a, 079b, 047a, 065, 028 | Cases 14 | 40–60 |
| [ ] | 082 | [E2E-006: disabled-precise](E2E-Tasks/082-case-15.md) | 079a, 079b, 047a, 065, 028 | Cases 15 | 40–60 |
| [ ] | 083 | [E2E-006: disabled-pattern](E2E-Tasks/083-case-16.md) | 079a, 079b, 047a, 065, 028 | Cases 16 | 40–60 |
| [ ] | 084 | [E2E-007: zero-single](E2E-Tasks/084-case-17.md) | 079b, 079a, 047a, 065 | Cases 17 | 40–60 |
| [ ] | 085 | [E2E-007: remaining-single](E2E-Tasks/085-case-19.md) | 079b, 079a, 047a, 065 | Cases 19 | 40–60 |
| [ ] | 086 | [E2E-012: excluded-first](E2E-Tasks/086-case-30.md) | 048b, 079b, 079a, 065, 052, 052c | Cases 30 | 25–45 |
| [ ] | 086b | [E2E-012: excluded-second](E2E-Tasks/086b-case-31.md) | 048b, 079b, 079a, 065, 052, 052c | Cases 31 | 25–45 |
| [ ] | 087 | [E2E-012: included-first](E2E-Tasks/087-case-32.md) | 048b, 079b, 079a, 065, 052, 052c | Cases 32 | 25–45 |
| [ ] | 087b | [E2E-012: included-second](E2E-Tasks/087b-case-33.md) | 048b, 079b, 079a, 065, 052, 052c | Cases 33 | 25–45 |
| [ ] | 088 | [E2E-013: child-overlay-wrong-password](E2E-Tasks/088-case-34.md) | 079b, 079a, 048b, 052 | Cases 34 | 25–45 |
| [ ] | 088b | [E2E-013: child-overlay-cancel](E2E-Tasks/088b-case-35.md) | 079b, 079a, 048b, 052 | Cases 35 | 25–45 |
| [ ] | 089 | [E2E-013: kiosk-wrong-password](E2E-Tasks/089-case-36.md) | 079b, 079a, 021, 052 | Cases 36 | 25–45 |
| [ ] | 089b | [E2E-013: kiosk-cancel](E2E-Tasks/089b-case-37.md) | 079b, 079a, 021, 052 | Cases 37 | 25–45 |
| [ ] | 158 | [E2E-022: app-restart-active](E2E-Tasks/158-case-116.md) | 155, 079b, 079a, 065, 052c, 052, 028 | Cases 116 | 40–60 |
| [ ] | 159 | [E2E-022: app-restart-expired](E2E-Tasks/159-case-117.md) | 155, 079b, 079a, 065, 052c, 052, 028 | Cases 117 | 40–60 |
| [ ] | 160 | [E2E-022: sign-out-in-active](E2E-Tasks/160-case-118.md) | 155, 079b, 079a, 065, 052c, 052 | Cases 118 | 40–60 |
| [ ] | 161 | [E2E-022: sign-out-in-expired](E2E-Tasks/161-case-119.md) | 155, 079b, 079a, 065, 052c, 052 | Cases 119 | 40–60 |
| [ ] | 162 | [E2E-022: reboot-active](E2E-Tasks/162-case-120.md) | 155, 079b, 079a, 065, 052c, 052, 007 | Cases 120 | 40–60 |
| [ ] | 163 | [E2E-022: reboot-expired](E2E-Tasks/163-case-121.md) | 155, 079b, 079a, 065, 052c, 052, 007 | Cases 121 | 40–60 |
| [ ] | 164 | [E2E-022: idle-active](E2E-Tasks/164-case-122.md) | 155, 079b, 079a, 065, 052c, 052 | Cases 122 | 40–60 |
| [ ] | 165 | [E2E-022: idle-expired](E2E-Tasks/165-case-123.md) | 155, 079b, 079a, 065, 052c, 052 | Cases 123 | 40–60 |
| [ ] | 105 | [E2E-025: excluded-new-login](E2E-Tasks/105-case-132.md) | 065, 079b, 079a, 052c | Cases 132 | 40–60 |
| [ ] | 106 | [E2E-025: excluded-retained-unlock](E2E-Tasks/106-case-133.md) | 065, 079b, 079a, 052c | Cases 133 | 40–60 |
| [ ] | 107 | [E2E-025: included-new-login](E2E-Tasks/107-case-134.md) | 065, 079b, 079a, 052c | Cases 134 | 40–60 |
| [ ] | 108 | [E2E-025: included-retained-unlock](E2E-Tasks/108-case-135.md) | 065, 079b, 079a, 052c | Cases 135 | 40–60 |
| [ ] | 202 | [E2E-036: daily-positive](E2E-Tasks/202-case-160.md) | 065, 079b, 079a | Cases 160 | 30–55 |
| [ ] | 236 | [E2E-043: child-overlay](E2E-Tasks/236-case-194.md) | 193, 079b, 079a, 052a, 050, 048b | Cases 194 | 30–55 |
| [ ] | 237 | [E2E-043: kiosk](E2E-Tasks/237-case-195.md) | 193, 079b, 079a, 052a, 050 | Cases 195 | 30–55 |
| [ ] | 273 | [E2E-049: native-grid-child-overlay](E2E-Tasks/273-case-231.md) | 197, 079b, 079a, 180 | Cases 231 | 30–55 |
| [ ] | 274 | [E2E-049: native-grid-kiosk](E2E-Tasks/274-case-232.md) | 197k, 079b, 079a, 180 | Cases 232 | 30–55 |
| [ ] | 279 | [E2E-049: native-command-child-overlay](E2E-Tasks/279-case-237.md) | 197, 079b, 079a, 180 | Cases 237 | 30–55 |
| [ ] | 280 | [E2E-049: native-command-kiosk](E2E-Tasks/280-case-238.md) | 197k, 079b, 079a, 180 | Cases 238 | 30–55 |
| [ ] | 035a | [Qualify native fixtures with spaces and commas](E2E-Tasks/035a-qualify-native-fixtures-with-spaces-and-commas.md) | 036, 079a | FIX04 special-path native assets; FILE05 and command-result bindings | 25–45 |
| [ ] | 230 | [E2E-041: special-paths](E2E-Tasks/230-case-188.md) | 035a, 180 | Cases 188 | 30–55 |
| [ ] | 035b | [Qualify versioned AppImage pattern assets](E2E-Tasks/035b-qualify-versioned-appimage-pattern-assets.md) | 036, 079a, 186, 052c | FIX04 AppImage versions; FILE05 and pattern launch results | 25–45 |
| [ ] | 231 | [E2E-041: pattern-files](E2E-Tasks/231-case-189.md) | 035b, 180 | Cases 189 | 30–55 |
| [ ] | 036a | [Launch native fixtures from the file manager](E2E-Tasks/036a-native-file-routes.md) | 036, 079a | APP01/02/03 native file-manager route | 30–50 |
| [ ] | 096 | [E2E-019: native-file-manager-allowed-enabled](E2E-Tasks/096-case-74.md) | 180, 036a | Cases 74 | 25–45 |
| [ ] | 096b | [E2E-019: native-file-manager-allowed-disabled](E2E-Tasks/096b-case-75.md) | 180, 036a | Cases 75 | 25–45 |
| [ ] | 097 | [E2E-019: native-file-manager-hard-blocked-enabled](E2E-Tasks/097-case-76.md) | 180, 036a | Cases 76 | 25–45 |
| [ ] | 097b | [E2E-019: native-file-manager-hard-blocked-disabled](E2E-Tasks/097b-case-77.md) | 180, 036a | Cases 77 | 25–45 |
| [ ] | 098 | [E2E-019: native-file-manager-soft-blocked-enabled](E2E-Tasks/098-case-78.md) | 180, 036a | Cases 78 | 25–45 |
| [ ] | 098b | [E2E-019: native-file-manager-soft-blocked-disabled](E2E-Tasks/098b-case-79.md) | 180, 036a | Cases 79 | 25–45 |
| [ ] | 277 | [E2E-049: native-file-manager-child-overlay](E2E-Tasks/277-case-235.md) | 197, 079b, 180, 036a | Cases 235 | 30–55 |
| [ ] | 278 | [E2E-049: native-file-manager-kiosk](E2E-Tasks/278-case-236.md) | 197k, 079b, 180, 036a | Cases 236 | 30–55 |
| [ ] | 036b | [Launch native fixtures from the desktop](E2E-Tasks/036b-native-desktop-route.md) | 036, 079a, 035p | APP01/02/03 native desktop route | 30–50 |
| [ ] | 093 | [E2E-019: native-desktop-allowed-enabled](E2E-Tasks/093-case-68.md) | 180, 036b | Cases 68 | 25–45 |
| [ ] | 093b | [E2E-019: native-desktop-allowed-disabled](E2E-Tasks/093b-case-69.md) | 180, 036b | Cases 69 | 25–45 |
| [ ] | 094 | [E2E-019: native-desktop-hard-blocked-enabled](E2E-Tasks/094-case-70.md) | 180, 036b | Cases 70 | 25–45 |
| [ ] | 094b | [E2E-019: native-desktop-hard-blocked-disabled](E2E-Tasks/094b-case-71.md) | 180, 036b | Cases 71 | 25–45 |
| [ ] | 095 | [E2E-019: native-desktop-soft-blocked-enabled](E2E-Tasks/095-case-72.md) | 180, 036b | Cases 72 | 25–45 |
| [ ] | 095b | [E2E-019: native-desktop-soft-blocked-disabled](E2E-Tasks/095b-case-73.md) | 180, 036b | Cases 73 | 25–45 |
| [ ] | 275 | [E2E-049: native-desktop-child-overlay](E2E-Tasks/275-case-233.md) | 197, 079b, 180, 036b | Cases 233 | 30–55 |
| [ ] | 276 | [E2E-049: native-desktop-kiosk](E2E-Tasks/276-case-234.md) | 197k, 079b, 180, 036b | Cases 234 | 30–55 |
| [ ] | 109p | [Install the declared Snap fixtures](E2E-Tasks/109p-snap-fixtures.md) | 006, 077a | FIX04 Snap assets; LIFE04 fixed Snap installation profile | 30–50 |
| [ ] | 109 | [Qualify Snap fixtures and command launches](E2E-Tasks/109-snap.md) | 109p, 079a | APP01/02/03/04 and FLOW08 Snap command route | 35–55 |
| [ ] | 113 | [E2E-019: snap-command-allowed-enabled](E2E-Tasks/113-case-92.md) | 180, 109 | Cases 92 | 25–45 |
| [ ] | 113b | [E2E-019: snap-command-allowed-disabled](E2E-Tasks/113b-case-93.md) | 180, 109 | Cases 93 | 25–45 |
| [ ] | 114 | [E2E-019: snap-command-hard-blocked-enabled](E2E-Tasks/114-case-94.md) | 180, 109 | Cases 94 | 25–45 |
| [ ] | 114b | [E2E-019: snap-command-hard-blocked-disabled](E2E-Tasks/114b-case-95.md) | 180, 109 | Cases 95 | 25–45 |
| [ ] | 115 | [E2E-019: snap-command-soft-blocked-enabled](E2E-Tasks/115-case-96.md) | 180, 109 | Cases 96 | 25–45 |
| [ ] | 115b | [E2E-019: snap-command-soft-blocked-disabled](E2E-Tasks/115b-case-97.md) | 180, 109 | Cases 97 | 25–45 |
| [ ] | 283 | [E2E-049: snap-command-child-overlay](E2E-Tasks/283-case-241.md) | 197, 079b, 180, 109 | Cases 241 | 30–55 |
| [ ] | 284 | [E2E-049: snap-command-kiosk](E2E-Tasks/284-case-242.md) | 197k, 079b, 180, 109 | Cases 242 | 30–55 |
| [ ] | 109a | [Qualify Snap app-grid launches](E2E-Tasks/109a-snap-grid.md) | 109 | APP01/02/03/04 and FLOW08 Snap app-grid route | 25–45 |
| [ ] | 110 | [E2E-019: snap-grid-allowed-enabled](E2E-Tasks/110-case-86.md) | 180, 109a | Cases 86 | 25–45 |
| [ ] | 110b | [E2E-019: snap-grid-allowed-disabled](E2E-Tasks/110b-case-87.md) | 180, 109a | Cases 87 | 25–45 |
| [ ] | 111 | [E2E-019: snap-grid-hard-blocked-enabled](E2E-Tasks/111-case-88.md) | 180, 109a | Cases 88 | 25–45 |
| [ ] | 111b | [E2E-019: snap-grid-hard-blocked-disabled](E2E-Tasks/111b-case-89.md) | 180, 109a | Cases 89 | 25–45 |
| [ ] | 112 | [E2E-019: snap-grid-soft-blocked-enabled](E2E-Tasks/112-case-90.md) | 180, 109a | Cases 90 | 25–45 |
| [ ] | 112b | [E2E-019: snap-grid-soft-blocked-disabled](E2E-Tasks/112b-case-91.md) | 180, 109a | Cases 91 | 25–45 |
| [ ] | 281 | [E2E-049: snap-grid-child-overlay](E2E-Tasks/281-case-239.md) | 197, 079b, 180, 109a | Cases 239 | 30–55 |
| [ ] | 282 | [E2E-049: snap-grid-kiosk](E2E-Tasks/282-case-240.md) | 197k, 079b, 180, 109a | Cases 240 | 30–55 |
| [ ] | 116p | [Install the declared Flatpak fixtures](E2E-Tasks/116p-flatpak-fixtures.md) | 006, 077a | FIX04 Flatpak assets; LIFE04 fixed Flatpak installation profile | 30–50 |
| [ ] | 116 | [Qualify Flatpak fixtures and command launches](E2E-Tasks/116-flatpak.md) | 116p, 079a | APP01/02/03/04 and FLOW08 Flatpak command route | 35–55 |
| [ ] | 120 | [E2E-019: flatpak-command-allowed-enabled](E2E-Tasks/120-case-104.md) | 180, 116 | Cases 104 | 25–45 |
| [ ] | 120b | [E2E-019: flatpak-command-allowed-disabled](E2E-Tasks/120b-case-105.md) | 180, 116 | Cases 105 | 25–45 |
| [ ] | 121 | [E2E-019: flatpak-command-hard-blocked-enabled](E2E-Tasks/121-case-106.md) | 180, 116 | Cases 106 | 25–45 |
| [ ] | 121b | [E2E-019: flatpak-command-hard-blocked-disabled](E2E-Tasks/121b-case-107.md) | 180, 116 | Cases 107 | 25–45 |
| [ ] | 122 | [E2E-019: flatpak-command-soft-blocked-enabled](E2E-Tasks/122-case-108.md) | 180, 116 | Cases 108 | 25–45 |
| [ ] | 122b | [E2E-019: flatpak-command-soft-blocked-disabled](E2E-Tasks/122b-case-109.md) | 180, 116 | Cases 109 | 25–45 |
| [ ] | 287 | [E2E-049: flatpak-command-child-overlay](E2E-Tasks/287-case-245.md) | 197, 079b, 180, 116 | Cases 245 | 30–55 |
| [ ] | 288 | [E2E-049: flatpak-command-kiosk](E2E-Tasks/288-case-246.md) | 197k, 079b, 180, 116 | Cases 246 | 30–55 |
| [ ] | 116a | [Qualify Flatpak app-grid launches](E2E-Tasks/116a-flatpak-grid.md) | 116 | APP01/02/03/04 and FLOW08 Flatpak app-grid route | 25–45 |
| [ ] | 117 | [E2E-019: flatpak-grid-allowed-enabled](E2E-Tasks/117-case-98.md) | 180, 116a | Cases 98 | 25–45 |
| [ ] | 117b | [E2E-019: flatpak-grid-allowed-disabled](E2E-Tasks/117b-case-99.md) | 180, 116a | Cases 99 | 25–45 |
| [ ] | 118 | [E2E-019: flatpak-grid-hard-blocked-enabled](E2E-Tasks/118-case-100.md) | 180, 116a | Cases 100 | 25–45 |
| [ ] | 118b | [E2E-019: flatpak-grid-hard-blocked-disabled](E2E-Tasks/118b-case-101.md) | 180, 116a | Cases 101 | 25–45 |
| [ ] | 119 | [E2E-019: flatpak-grid-soft-blocked-enabled](E2E-Tasks/119-case-102.md) | 180, 116a | Cases 102 | 25–45 |
| [ ] | 119b | [E2E-019: flatpak-grid-soft-blocked-disabled](E2E-Tasks/119b-case-103.md) | 180, 116a | Cases 103 | 25–45 |
| [ ] | 285 | [E2E-049: flatpak-grid-child-overlay](E2E-Tasks/285-case-243.md) | 197, 079b, 180, 116a | Cases 243 | 30–55 |
| [ ] | 286 | [E2E-049: flatpak-grid-kiosk](E2E-Tasks/286-case-244.md) | 197k, 079b, 180, 116a | Cases 244 | 30–55 |
| [ ] | 102 | [Compose expiry recovery through kiosk approval](E2E-Tasks/102-replacement.md) | 062, 079a, 065 | FLOW11 | 35–55 |
| [ ] | 103 | [E2E-009: excluded](E2E-Tasks/103-case-23.md) | 102, 079b | Cases 23 | 35–55 |
| [ ] | 104 | [E2E-009: included](E2E-Tasks/104-case-24.md) | 102, 079b | Cases 24 | 35–55 |
| [ ] | 123 | [Keep an unsaved match draft across a fixture update](E2E-Tasks/123-catalog-change.md) | 079, 006, 044a, 028 | LIFE04 fixture update; PARENT15 retained-editor save; LIFE01 catalogue refresh | 25–45 |
| [ ] | 124 | [E2E-020: update](E2E-Tasks/124-case-110.md) | 123, 079a, 180 | Cases 110 | 35–55 |
| [ ] | 123a | [Save a match draft after fixture removal](E2E-Tasks/123a-catalog-removal.md) | 079, 006, 044a, 028 | LIFE04 fixture remove/reinstall; PARENT15 retained-editor save; LIFE01 catalogue refresh | 30–50 |
| [ ] | 125 | [E2E-020: remove](E2E-Tasks/125-case-111.md) | 123a, 079a, 180 | Cases 111 | 35–55 |
| [ ] | 126p | [Install the declared offline game fixture](E2E-Tasks/126p-game-fixture.md) | 006, 077a | FIX04 game asset; LIFE04 fixed game installation profile | 25–45 |
| [ ] | 126a | [Launch and observe the prepared offline game](E2E-Tasks/126a-game-activity.md) | 126p, 047 | Game APP01/02/03/04 and FLOW08 usable activity | 30–50 |
| [ ] | 126 | [Compose windowed gameplay through natural expiry](E2E-Tasks/126-game.md) | 126a, 062, 065 | APP05/FLOW10 windowed game | 25–45 |
| [ ] | 127 | [E2E-023: windowed](E2E-Tasks/127-case-126.md) | 126, 102, 079b | Cases 126 | 40–60 |
| [ ] | 128 | [E2E-024: grant-dominant-windowed](E2E-Tasks/128-case-130.md) | 126, 048b, 079b | Cases 130 | 40–60 |
| [ ] | 132 | [Compose a daily-dominant profile without clearing the grant](E2E-Tasks/132-time-profiles-dominant.md) | 065 | FLOW13 daily-dominant scope | 25–45 |
| [ ] | 133 | [E2E-024: daily-dominant-windowed](E2E-Tasks/133-case-128.md) | 126, 048b, 079b, 132 | Cases 128 | 40–60 |
| [ ] | 269 | [E2E-048: daily-dominant-child-overlay](E2E-Tasks/269-case-227.md) | 197, 052c, 132 | Cases 227; gate in brief | 30–55 |
| [ ] | 270 | [E2E-048: daily-dominant-kiosk](E2E-Tasks/270-case-228.md) | 197k, 052c, 132 | Cases 228; gate in brief | 30–55 |
| [ ] | 129 | [Play fullscreen to natural lock](E2E-Tasks/129-game-fullscreen.md) | 126 | APP05/FLOW10 fullscreen play | 30–50 |
| [ ] | 130 | [E2E-023: fullscreen](E2E-Tasks/130-case-127.md) | 102, 079b, 129 | Cases 127 | 40–60 |
| [ ] | 129a | [Reach an overlay request from fullscreen gameplay](E2E-Tasks/129a-fullscreen-request.md) | 129, 048a | DESK12 fullscreen reveal; overlay/game return | 25–45 |
| [ ] | 134 | [E2E-024: daily-dominant-fullscreen](E2E-Tasks/134-case-129.md) | 048b, 079b, 132, 129a | Cases 129 | 40–60 |
| [ ] | 131 | [E2E-024: grant-dominant-fullscreen](E2E-Tasks/131-case-131.md) | 048b, 079b, 129a | Cases 131 | 40–60 |
| [ ] | 289 | [E2E-050: overlay-first-retained](E2E-Tasks/289-case-247.md) | 197, 197k, 196, 079b, 102, 155, 129a, 047a, 028 | Cases 247; gate in brief | 30–50 + continuous run |
| [ ] | 290 | [E2E-050: overlay-first-fresh](E2E-Tasks/290-case-248.md) | 197, 197k, 196, 079b, 102, 155, 129a, 047a, 028 | Cases 248; gate in brief | 30–50 + continuous run |
| [ ] | 291 | [E2E-050: kiosk-first-retained](E2E-Tasks/291-case-249.md) | 197, 197k, 196, 079b, 102, 155, 129a, 047a, 028 | Cases 249; gate in brief | 30–50 + continuous run |
| [ ] | 292 | [E2E-050: kiosk-first-fresh](E2E-Tasks/292-case-250.md) | 197, 197k, 196, 079b, 102, 155, 129a, 047a, 028 | Cases 250; gate in brief | 30–50 + continuous run |
| [ ] | 198 | [Manage from the second parent's own window](E2E-Tasks/198-manage-from-the-second-parent-s-own-window.md) | 044, 079 | FLOW15/FLOW01 other-parent management entry | 30–50 |
| [ ] | 293 | [E2E-051: jordan](E2E-Tasks/293-case-251.md) | 197, 197k, 198, 196, 079b, 079a, 155, 126, 047a | Cases 251; gate in brief | 30–50 + continuous run |
| [ ] | 294 | [E2E-051: riley](E2E-Tasks/294-case-252.md) | 197, 197k, 198, 196, 079b, 079a, 155, 126, 047a | Cases 252; gate in brief | 30–50 + continuous run |
| [ ] | 166 | [Suspend and wake through normal controls](E2E-Tasks/166-suspend.md) | 052a, 065, 043a, 052c | LIFE03 | 35–55 |
| [ ] | 167 | [E2E-022: suspend-wake-active](E2E-Tasks/167-case-124.md) | 155, 079b, 079a, 065, 166 | Cases 124 | 40–60 |
| [ ] | 168 | [E2E-022: suspend-wake-expired](E2E-Tasks/168-case-125.md) | 155, 079b, 079a, 065, 166 | Cases 125 | 40–60 |
| [ ] | 135 | [Follow process activation after a real update](E2E-Tasks/135-activation-process.md) | 028, 044, 007, 079, 048a | LIFE04 update; LIFE05 process/none scope | 30–50 |
| [ ] | 136 | [E2E-026: process](E2E-Tasks/136-case-136.md) | 135, 155, 079a, 079b, 065, 052 | Cases 136 | 40–60 |
| [ ] | 137 | [Follow session activation after a real update](E2E-Tasks/137-activation-session.md) | 044, 007, 079, 048a | LIFE04 update; LIFE05 session scope | 30–50 |
| [ ] | 138 | [E2E-026: session](E2E-Tasks/138-case-137.md) | 137, 155, 079a, 079b, 065, 052 | Cases 137 | 40–60 |
| [ ] | 139 | [Follow reboot activation after a real update](E2E-Tasks/139-activation-reboot.md) | 007, 044, 079, 048a | LIFE04 update; LIFE05 reboot scope | 30–50 |
| [ ] | 140 | [E2E-026: reboot](E2E-Tasks/140-case-138.md) | 139, 155, 079a, 079b, 065, 052 | Cases 138 | 40–60 |
| [ ] | 141 | [Qualify product removal and reinstall commands](E2E-Tasks/141-product-removal.md) | 007, 079a, 014 | LIFE04 product remove/reinstall; LIFE05 corresponding notices/activation | 30–50 |
| [ ] | 141a | [Qualify purge and reinstall to visible defaults](E2E-Tasks/141a-product-purge.md) | 141 | LIFE04 purge; LIFE05 notice and reinstall/defaults | 30–50 |
| [ ] | 142 | [E2E-027: continuous](E2E-Tasks/142-case-139.md) | 141a, 155, 065, 079b | Cases 139 | 35–60 + continuous run |
| [ ] | 182 | [Prepare a daily balance that outlasts a soft exception](E2E-Tasks/182-prepare-a-daily-balance-that-outlasts-a-soft-exception.md) | 065, 079b, 079a, 052a | FLOW18 | 30–50 |
| [ ] | 206 | [E2E-038: none](E2E-Tasks/206-case-164.md) | 182, 047a | Cases 164 | 30–55 |
| [ ] | 207 | [E2E-038: unlock](E2E-Tasks/207-case-165.md) | 182, 047a | Cases 165 | 30–55 |
| [ ] | 208 | [E2E-038: fresh-login](E2E-Tasks/208-case-166.md) | 182, 047a | Cases 166 | 30–55 |
| [ ] | 209 | [E2E-038: allowance-edit](E2E-Tasks/209-case-167.md) | 182, 047a | Cases 167 | 30–55 |
| [ ] | 210 | [E2E-038: toggle](E2E-Tasks/210-case-168.md) | 182, 047a | Cases 168 | 30–55 |
| [ ] | 211 | [E2E-038: app-save](E2E-Tasks/211-case-169.md) | 182, 047a | Cases 169 | 30–55 |
| [ ] | 212 | [E2E-038: revoke](E2E-Tasks/212-case-170.md) | 182, 047a | Cases 170 | 30–55 |
| [ ] | 184a | [Open Users settings and qualify its authentication](E2E-Tasks/184a-open-users-settings-and-qualify-its-authentication.md) | 004, 048d, 001s | AUTH04 Users Unlock; ACCOUNT01 | 30–50 |
| [ ] | 184 | [Add a disposable child through Users settings](E2E-Tasks/184-change-disposable-accounts-through-users-settings.md) | 184a, 009 | ACCOUNT02 add-child; AUTH04 account-creation password fields | 30–50 |
| [ ] | 221 | [E2E-040: add-child](E2E-Tasks/221-case-179.md) | 184, 017, 044a | Cases 179 | 30–55 |
| [ ] | 184b | [Remove a logged-out spare child through Users](E2E-Tasks/184b-remove-disposable-child.md) | 184 | ACCOUNT02 remove-child | 25–40 |
| [ ] | 222 | [E2E-040: remove-selected](E2E-Tasks/222-case-180.md) | 184b, 017, 044a | Cases 180 | 30–55 |
| [ ] | 223 | [E2E-040: remove-last-child](E2E-Tasks/223-case-181.md) | 184b, 017, 044a | Cases 181 | 30–55 |
| [ ] | 225 | [E2E-040: missing-remembered-child](E2E-Tasks/225-case-183.md) | 184b, 014, 180, 044 | Cases 183 | 30–55 |
| [ ] | 184c | [Change a spare approver's role through Users](E2E-Tasks/184c-change-spare-account-role.md) | 184a, 009 | ACCOUNT02 change-role | 25–40 |
| [ ] | 224 | [E2E-040: ineligible-approver](E2E-Tasks/224-case-182.md) | 184c, 155 | Cases 182 | 30–55 |
| [ ] | 169 | [Preserve and qualify system obligation 140: startup enforcement](E2E-Tasks/169-system-140.md) | Baseline | System obligation 140 | 30–60 |
| [ ] | 170 | [Preserve and qualify system obligation 141: broker startup](E2E-Tasks/170-system-141.md) | Baseline | System obligation 141 | 30–60 |
| [ ] | 171 | [Preserve and qualify system obligation 142: zero-time exposure](E2E-Tasks/171-system-142.md) | Baseline | System obligation 142 | 30–60 |
| [ ] | 172 | [Preserve and qualify system obligation 143: usage read](E2E-Tasks/172-system-143.md) | Baseline | System obligation 143 | 30–60 |
| [ ] | 173 | [Preserve and qualify system obligation 144: kiosk authentication agent](E2E-Tasks/173-system-144.md) | Baseline | System obligation 144 | 30–60 |
| [ ] | 174 | [Preserve and qualify system obligation 145: failed save](E2E-Tasks/174-system-145.md) | Baseline | System obligation 145 | 30–60 |
| [ ] | 175 | [Preserve and qualify system obligation 146: stale identity](E2E-Tasks/175-system-146.md) | Baseline | System obligation 146 | 30–60 |
| [ ] | 176 | [Preserve and qualify system obligation 147: disconnect](E2E-Tasks/176-system-147.md) | Baseline | System obligation 147 | 30–60 |
| [ ] | 177 | [Preserve and qualify system obligation 148: concurrent transaction](E2E-Tasks/177-system-148.md) | Baseline | System obligation 148 | 30–60 |
| [ ] | 178 | [Preserve and qualify system obligation 149: policy reload](E2E-Tasks/178-system-149.md) | Baseline | System obligation 149 | 30–60 |
| [ ] | 179 | [Preserve and qualify system obligation 150: partial termination](E2E-Tasks/179-system-150.md) | Baseline | System obligation 150 | 30–60 |
| [ ] | 150a | [Prepare the reviewed feedback submission profile](E2E-Tasks/150a-feedback-profile.md) | 038, 031a, 030, 052c | Concrete synthetic reports, recipient and authorization scope for FEED11 consumers | 30–50 |
| [ ] | 150 | [Submit one authorized synthetic report and read success](E2E-Tasks/150-feedback-send.md) | 150a | FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief | 30–50 |
| [ ] | 151 | [E2E-032: success](E2E-Tasks/151-case-156.md) | 150 | Cases 156; gate in brief | 35–55 |
| [ ] | 256 | [E2E-047: no-reply](E2E-Tasks/256-case-214.md) | 150 | Cases 214; gate in brief | 30–55 |
| [ ] | 152 | [Change connectivity through public network controls](E2E-Tasks/152-network.md) | 150, 193 | FEED09 Parent retry/recovery over qualified LIFE06; gate in brief | 35–55 |
| [ ] | 153 | [E2E-033: retry](E2E-Tasks/153-case-157.md) | 152 | Cases 157; gate in brief | 35–55 |
| [ ] | 257 | [E2E-047: background](E2E-Tasks/257-case-215.md) | 152 | Cases 215; gate in brief | 30–55 |
| [ ] | 258 | [E2E-047: app-exit](E2E-Tasks/258-case-216.md) | 152, 030a | Cases 216; gate in brief | 30–55 |
| [ ] | 259 | [E2E-047: retry-expired](E2E-Tasks/259-case-217.md) | 152 | Cases 217; gate in brief | 35–60 incl. retry |
| [ ] | 150p | [Send an authorized Parent error report](E2E-Tasks/150p-parent-error-send.md) | 150, 186 | FEED11, FEED09 success and FEED14 Parent error-report; gate in brief | 20–40 |
| [ ] | 264 | [E2E-047: parent-error-success](E2E-Tasks/264-case-222.md) | 150p | Cases 222; gate in brief | 30–55 |
| [ ] | 295 | [Validate the manually prepared Lunar VM profile](E2E-Tasks/295-lunar-preparation.md) | 006, 036 | FIX05; restored Lunar/AppImageLauncher/autostart/Minecraft prerequisites only. Blocker: profile and repeatable setup unqualified; resume when the manual assets and standard restore path are available. | 25–45 |
| [ ] | 296 | [Qualify Lunar launch, tray and Quit](E2E-Tasks/296-lunar-provider.md) | 295, 079a, 052c | APP06 snapshot and APP01/02/03/UI18 Lunar launch, tray and Quit bindings | 40–60 |
| [ ] | 296a | [Qualify Minecraft launch, local play and exit](E2E-Tasks/296a-minecraft-provider.md) | 296 | APP01/02/03 and UI18 Minecraft local-world binding | 40–60 |
| [ ] | 296b | [Qualify continuous Lunar login observations](E2E-Tasks/296b-lunar-login-observer.md) | 296a, 007, 016a, 004, 052c, 180 | APP06/UI22 continuous login interval and Lunar autostart binding | 40–60 |
| [ ] | 297 | [E2E-052: appimagelauncher-login-autostart](E2E-Tasks/297-case-253.md) | 296b, 180, 197 | Cases 253; pending metadata only. Blocker: complete public journey unimplemented; resume when required blocks are qualified. | 40–60 + ≤30 live |
| [ ] | 183a | [Lock during pending overlay approval](E2E-Tasks/183a-lock-during-pending-overlay-approval.md) | 048b, 044, 052c | FLOW17 overlay lock; gate in brief | 25–55 |
| [ ] | 213 | [E2E-039: overlay-lock](E2E-Tasks/213-case-171.md) | 183a, 180, 079b, 079a | Cases 171; gate in brief | 30–55 |
| [ ] | 183b | [Switch User during pending overlay approval](E2E-Tasks/183b-switch-user-during-pending-overlay-approval.md) | 048b, 044, 052c | FLOW17 overlay Switch User; gate in brief | 25–55 |
| [ ] | 214 | [E2E-039: overlay-switch](E2E-Tasks/214-case-172.md) | 183b, 180, 079b, 079a | Cases 172; gate in brief | 30–55 |
| [ ] | 183c | [Sign out during pending overlay approval](E2E-Tasks/183c-sign-out-during-pending-overlay-approval.md) | 048b, 044, 052c | FLOW17 overlay sign-out; gate in brief | 25–55 |
| [ ] | 215 | [E2E-039: overlay-signout](E2E-Tasks/215-case-173.md) | 183c, 180, 079b, 079a | Cases 173; gate in brief | 30–55 |
| [ ] | 183d | [Close the overlay during pending approval](E2E-Tasks/183d-close-the-overlay-during-pending-approval.md) | 048b, 044, 028, 052c | FLOW17 overlay app-close; gate in brief | 25–55 |
| [ ] | 216 | [E2E-039: overlay-close](E2E-Tasks/216-case-174.md) | 183d, 180, 079b, 079a | Cases 174; gate in brief | 30–55 |
| [ ] | 183e | [Close the station during pending approval](E2E-Tasks/183e-close-the-station-during-pending-approval.md) | 020, 014, 180, 044, 052c | FLOW17 kiosk app-close; gate in brief | 25–55 |
| [ ] | 217 | [E2E-039: kiosk-close](E2E-Tasks/217-case-175.md) | 183e, 079b, 079a, 021 | Cases 175; gate in brief | 30–55 |
| [ ] | 187o | [Read overlay cooldown errors and report choices](E2E-Tasks/187o-read-overlay-cooldown-errors-and-report-choices.md) | 048b, 044, 052c, 030 | REQUEST09 cooldown and FEED15 overlay; gate in brief | 30–50 |
| [ ] | 218 | [E2E-039: overlay-cooldown](E2E-Tasks/218-case-176.md) | 187o, 180, 079b, 079a | Cases 176; gate in brief | 30–55 |
| [ ] | 248 | [E2E-045: child-overlay](E2E-Tasks/248-case-206.md) | 187o, 180 | Cases 206; gate in brief | 30–55 |
| [ ] | 150o | [Send an authorized overlay error report](E2E-Tasks/150o-send-an-authorized-overlay-error-report.md) | 150, 187o | FEED11, FEED09 success and FEED14 overlay; gate in brief | 25–45 |
| [ ] | 262 | [E2E-047: overlay-success](E2E-Tasks/262-case-220.md) | 150o | Cases 220; gate in brief | 30–55 |
| [ ] | 187k | [Read station cooldown errors and report choices](E2E-Tasks/187k-read-station-cooldown-errors-and-report-choices.md) | 021, 044, 052c, 030 | REQUEST09 cooldown and FEED15 kiosk; gate in brief | 30–50 |
| [ ] | 219 | [E2E-039: kiosk-cooldown-same](E2E-Tasks/219-case-177.md) | 187k, 180, 079b, 079a | Cases 177; gate in brief | 30–55 |
| [ ] | 220 | [E2E-039: kiosk-cooldown-other](E2E-Tasks/220-case-178.md) | 187k, 180, 079b, 079a, 024a | Cases 178; gate in brief | 30–55 |
| [ ] | 249 | [E2E-045: kiosk](E2E-Tasks/249-case-207.md) | 187k, 180 | Cases 207; gate in brief | 30–55 |
| [ ] | 150k | [Send an authorized kiosk error report](E2E-Tasks/150k-send-an-authorized-kiosk-error-report.md) | 150, 187k | FEED11, FEED09 success and FEED14 kiosk; gate in brief | 25–45 |
| [ ] | 263 | [E2E-047: kiosk-success](E2E-Tasks/263-case-221.md) | 150k | Cases 221; gate in brief | 30–55 |
| [ ] | 188p | [Observe failed Parent diagnostic collection](E2E-Tasks/188p-retry-failed-parent-diagnostic-collection.md) | 031a | FEED09 Parent collection failure and usable controls; gate in brief | 25–40 |
| [ ] | 189p | [Send a Parent report without unavailable logs](E2E-Tasks/189p-send-a-parent-report-without-unavailable-logs.md) | 188p, 150 | FEED11 without-logs and FEED09/14 Parent result; gate in brief | 25–55 |
| [ ] | 251 | [E2E-046: parent-without-logs](E2E-Tasks/251-case-209.md) | 189p | Cases 209; gate in brief | 30–55 |
| [ ] | 188r | [Retry failed Parent diagnostic collection](E2E-Tasks/188r-parent-collection-retry.md) | 188p | FEED16 Parent collection recovery; gate in brief | 25–40 |
| [ ] | 250 | [E2E-046: parent-retry](E2E-Tasks/250-case-208.md) | 188r | Cases 208; gate in brief | 30–55 |
| [ ] | 188o | [Observe failed overlay diagnostic collection](E2E-Tasks/188o-retry-failed-overlay-diagnostic-collection.md) | 187o, 031a | FEED09 overlay collection failure and usable controls; gate in brief | 25–40 |
| [ ] | 189o | [Send an overlay report without unavailable logs](E2E-Tasks/189o-send-a-overlay-report-without-unavailable-logs.md) | 188o, 150 | FEED11 without-logs and FEED09/14 overlay result; gate in brief | 25–55 |
| [ ] | 253 | [E2E-046: child-overlay-without-logs](E2E-Tasks/253-case-211.md) | 189o | Cases 211; gate in brief | 30–55 |
| [ ] | 188s | [Retry failed overlay diagnostic collection](E2E-Tasks/188s-overlay-collection-retry.md) | 188o | FEED16 overlay collection recovery; gate in brief | 25–40 |
| [ ] | 252 | [E2E-046: child-overlay-retry](E2E-Tasks/252-case-210.md) | 188s | Cases 210; gate in brief | 30–55 |
| [ ] | 188k | [Observe failed kiosk diagnostic collection](E2E-Tasks/188k-retry-failed-kiosk-diagnostic-collection.md) | 187k, 031a | FEED09 kiosk collection failure and usable controls; gate in brief | 25–40 |
| [ ] | 189k | [Send a kiosk report without unavailable logs](E2E-Tasks/189k-send-a-kiosk-report-without-unavailable-logs.md) | 188k, 150 | FEED11 without-logs and FEED09/14 kiosk result; gate in brief | 25–55 |
| [ ] | 255 | [E2E-046: kiosk-without-logs](E2E-Tasks/255-case-213.md) | 189k | Cases 213; gate in brief | 30–55 |
| [ ] | 188t | [Retry failed kiosk diagnostic collection](E2E-Tasks/188t-kiosk-collection-retry.md) | 188k | FEED16 kiosk collection recovery; gate in brief | 25–40 |
| [ ] | 254 | [E2E-046: kiosk-retry](E2E-Tasks/254-case-212.md) | 188t | Cases 212; gate in brief | 30–55 |
| [ ] | 190o | [Confirm stopping a sending overlay report](E2E-Tasks/190o-confirm-stopping-a-sending-overlay-report.md) | 150o, 152 | FEED09 retry and FEED17/18 overlay; gate in brief | 25–55 |
| [ ] | 260 | [E2E-047: overlay-stop](E2E-Tasks/260-case-218.md) | 190o | Cases 218; gate in brief | 30–55 |
| [ ] | 190k | [Confirm stopping a sending kiosk report](E2E-Tasks/190k-confirm-stopping-a-sending-kiosk-report.md) | 150k, 152 | FEED09 retry and FEED17/18 kiosk; gate in brief | 25–55 |
| [ ] | 261 | [E2E-047: kiosk-stop](E2E-Tasks/261-case-219.md) | 190k | Cases 219; gate in brief | 30–55 |
| [ ] | 143 | [Qualify distinct retained desktops for one child](E2E-Tasks/143-multi-desktop.md) | 047a, 079a, 050, 048b | FLOW14 same-child multi-desktop scope; gate in brief | 20–40 |
| [ ] | 144 | [E2E-007: zero-multiple](E2E-Tasks/144-case-18.md) | 079b, 065, 143 | Cases 18; gate in brief | 40–60 |
| [ ] | 145 | [E2E-007: remaining-multiple](E2E-Tasks/145-case-20.md) | 079b, 065, 143 | Cases 20; gate in brief | 40–60 |
| [ ] | 146 | [E2E-021: save](E2E-Tasks/146-case-112.md) | 143, 079b, 065 | Cases 112; gate in brief | 40–60 |
| [ ] | 147 | [E2E-021: approve-without-soft](E2E-Tasks/147-case-113.md) | 143, 079b, 065 | Cases 113; gate in brief | 40–60 |
| [ ] | 148 | [E2E-021: approve-with-soft](E2E-Tasks/148-case-114.md) | 143, 079b, 065 | Cases 114; gate in brief | 40–60 |
| [ ] | 149 | [E2E-021: revoke](E2E-Tasks/149-case-115.md) | 143, 079b, 065 | Cases 115; gate in brief | 40–60 |
| [ ] | 191a | [Read the Shell calendar and clock](E2E-Tasks/191a-calendar-provider.md) | 003d, 044a, 052c | TIME05 Shell calendar and DESK12 clock binding | 25–45 |
| [ ] | 191 | [Read timezone and compose local calendar observations](E2E-Tasks/191-read-local-calendar-and-timezone.md) | 191a, 001s | TIME05 Settings Date & Time binding and composed calendar observation | 25–45 |
| [ ] | 238 | [E2E-044: ordinary-daily-reset](E2E-Tasks/238-case-196.md) | 191, 065, 062 | Cases 196; gate in brief | Scheduled window; ≤60 |
| [ ] | 239 | [E2E-044: ordinary-rest-of-day](E2E-Tasks/239-case-197.md) | 191, 065, 062 | Cases 197; gate in brief | Scheduled window; ≤60 |
| [ ] | 240 | [E2E-044: ordinary-fixed-grant](E2E-Tasks/240-case-198.md) | 191, 065, 062 | Cases 198; gate in brief | Scheduled window; ≤60 |
| [ ] | 241 | [E2E-044: spring-forward-daily-reset](E2E-Tasks/241-case-199.md) | 191, 065, 062 | Cases 199; gate in brief | Scheduled window; ≤60 |
| [ ] | 242 | [E2E-044: spring-forward-rest-of-day](E2E-Tasks/242-case-200.md) | 191, 065, 062 | Cases 200; gate in brief | Scheduled window; ≤60 |
| [ ] | 243 | [E2E-044: spring-forward-fixed-grant](E2E-Tasks/243-case-201.md) | 191, 065, 062 | Cases 201; gate in brief | Scheduled window; ≤60 |
| [ ] | 244 | [E2E-044: fall-back-daily-reset](E2E-Tasks/244-case-202.md) | 191, 065, 062 | Cases 202; gate in brief | Scheduled window; ≤60 |
| [ ] | 245 | [E2E-044: fall-back-rest-of-day](E2E-Tasks/245-case-203.md) | 191, 065, 062 | Cases 203; gate in brief | Scheduled window; ≤60 |
| [ ] | 246 | [E2E-044: fall-back-fixed-grant](E2E-Tasks/246-case-204.md) | 191, 065, 062 | Cases 204; gate in brief | Scheduled window; ≤60 |

## Deferred future work

This row has no current-release consumer and does not prevent active completion.

| Done | ID | Task | Requires tasks | Delivered scope | Minutes |
| --- | --- | --- | --- | --- | --- |
| [ ] | 154 | [Deferred qualification of restored mute](E2E-Tasks/154-mute.md) | 048a | Deferred future public mute; outside current-release completion; gate in brief | 20–40 |
