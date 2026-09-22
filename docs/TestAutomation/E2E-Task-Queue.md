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

Ordinary rows target one **15–30-minute session**, including targeted checks,
live qualification, cleanup and close-out under the master's
[task-size contract](E2E-Execution-Plan.md#task-size-and-order). Estimates assume
available prerequisites; they are not measured runtimes or stop timers.
A Minutes cell marked **(exception)** has a concrete reason in its brief.
Continuous journeys and required regressions keep their real run bounds.

When a capability is split, new rows deliver independently qualified operations;
the original ID closes the remaining operation/composition. Its brief's
**Session boundary** identifies the new work. Delivered scope includes qualified
prerequisites transitively, so consumers retain the full contract without
reimplementing extracted operations. Completed rows and case IDs are unchanged.

Check completion only after the master's acceptance and cleanup. Every unfinished
active row has one brief; briefs contain acceptance requirements, not alternate
next-task decisions.
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
| [x] | 003aa | Select an ordinary GDM account and return | 011 | GDM01/02 ordinary account-list navigation and Escape return | 20–30 |
| [ ] | 003a | [Prove the intended GDM password recipient](E2E-Tasks/003a-gdm-recipient.md) | 011, 003aa | GDM01/02 ordinary prompt entry; GDM03/04/08/09 recipient, refusal and Escape-return proofs | 20–30 |
| [ ] | 001r | [Requalify retained case 1](E2E-Tasks/001r-case-1-regression.md) | 003a | Retained regression 1; complete graphical/serial recipe and capture/return reconciliation | 20–30 |
| [ ] | 003ba | [Qualify fresh login without a keyring prompt](E2E-Tasks/003ba-fresh-desktop.md) | 003a | GDM05 fresh Parent/standard entry and DESK01 no-prompt desktop | 20–30 |
| [ ] | 003b | [Cancel a real keyring prompt after login](E2E-Tasks/003b-desktop-keyring.md) | 003a, 003ba | GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback | 20–30 |
| [ ] | 003ca | [Open and dismiss Shell session controls](E2E-Tasks/003ca-shell-session-menu.md) | 003b | DESK02 Shell Quick Settings and session-menu entry/readback | 20–30 |
| [ ] | 003c | [Switch User through qualified Shell controls](E2E-Tasks/003c-switch-user.md) | 003b, 003ca | DESK02/03 current Shell provider route and independently observed GDM return | 20–30 |
| [ ] | 003da | [Open and cancel the Shell logout confirmation](E2E-Tasks/003da-logout-cancel.md) | 003b, 003c | DESK04 logout-confirmation entry and Cancel branch | 20–30 |
| [ ] | 003d | [Confirm Shell logout and observe GDM](E2E-Tasks/003d-logout.md) | 003b, 003c, 003da | DESK04 current Shell logout/confirmation route and independently observed GDM return | 20–30 |
| [ ] | 001sa | [Read Shell search results and the Terminal entry](E2E-Tasks/001sa-shell-search-results.md) | 003b, 003c, 003d | SEARCH01/02/03/04/06 exact queries and Terminal result identity | 20–30 |
| [ ] | 001sb | [Launch Parent through administrator search](E2E-Tasks/001sb-parent-search-launch.md) | 001sa | SEARCH05 administrator Parent launch and owned-window result | 20–30 |
| [ ] | 003r | [Requalify retained case 3](E2E-Tasks/003r-case-3-regression.md) | 001sb | Retained regression 3; existing/new-child discovery | 20–30 |
| [ ] | 004r | [Requalify retained case 4](E2E-Tasks/004r-case-4-regression.md) | 001sb | Retained regression 4; no-child discovery | 20–30 |
| [ ] | 001s | [Prove Parent is unavailable to a standard account](E2E-Tasks/001s-shell-search.md) | 003b, 003c, 003d, 001sb | SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry | 20–30 |
| [ ] | 005r | [Requalify retained case 5](E2E-Tasks/005r-case-5-regression.md) | 001s | Retained regression 5; standard-account app-grid unavailability | 20–30 |
| [ ] | 001ta | [Submit one nonsecret terminal command and read help](E2E-Tasks/001ta-terminal-help.md) | 001s | FILE01/02/06 terminal owner, nonsecret submission, help and close | 20–30 |
| [ ] | 001t | [Read terminal management denial](E2E-Tasks/001t-terminal-provider.md) | 001s, 001ta | FILE01/02/06 terminal command, help/denial projections and normal close/return | 20–30 |
| [ ] | 002r | [Requalify retained case 6](E2E-Tasks/002r-case-6-regression.md) | 001t | Retained regression 6; full terminal management denial | 20–30 |
| [ ] | 235r | [Requalify retained case 193](E2E-Tasks/235r-case-193-regression.md) | 001t | Retained regression 193; both installed commands/manuals and terminal return | 20–30 |
| [ ] | 185l | [Qualify the installed license viewer](E2E-Tasks/185l-license-provider.md) | 001s | ABOUT02/03 actual license handler identity/content and close/return | 20–30 |
| [ ] | 151r | [Requalify retained case 151](E2E-Tasks/151r-case-151-regression.md) | 185l | Retained regression 151; complete About/license recipe and migration regression close-out | 20–30 |
| [ ] | 012b | [Select eligible kiosk children and approvers](E2E-Tasks/012b-kiosk-eligible-choices.md) | 011, 017, 003d | REQUEST04 kiosk eligible account choices and selected-value readback | 20–30 |
| [ ] | 012 | [Read kiosk disabled-child availability](E2E-Tasks/012-request-choices.md) | 011, 017, 003d, 012b | REQUEST04 kiosk child/approver; REQUEST08 unavailable state | 20–30 |
| [ ] | 018 | [E2E-017: disabled-child](E2E-Tasks/018-case-57.md) | 012, 013 | Cases 57 | 20–30 |
| [ ] | 024b | [Prepare and qualify the no-child kiosk profile](E2E-Tasks/024b-kiosk-no-child.md) | 012 | FIX03 no-child profile and public station empty state | 20–30 |
| [ ] | 026 | [E2E-017: no-child](E2E-Tasks/026-case-54.md) | 024b, 013 | Cases 54 | 20–30 |
| [ ] | 024 | [Prepare the no-approver kiosk profile](E2E-Tasks/024-kiosk-fixtures.md) | 012, 024b | FIX03 no-child/no-approver profiles | 20–30 |
| [ ] | 026b | [E2E-017: no-parent](E2E-Tasks/026b-case-55.md) | 024, 013 | Cases 55 | 20–30 |
| [ ] | 004a | [Give repeated public operations distinct stages](E2E-Tasks/004a-give-repeated-public-operations-distinct-stages.md) | Baseline | JourneyPlan repeated invocation IDs and assertion placement | 30–50 (exception) |
| [ ] | 004 | [Allow distinct single-use authentication challenges](E2E-Tasks/004-challenges.md) | 003d, 004a | UI19/GDM05 distinct single-use authentication challenges | 40–60 (exception) |
| [ ] | 005a | [Start a graphical journey before product installation](E2E-Tasks/005a-product-free-entry.md) | 001t, 004 | Product-free graphical start and verified package staging | 30–50 (exception) |
| [ ] | 005 | [Qualify terminal administrator password input](E2E-Tasks/005-terminal-auth.md) | 005a | AUTH03; FILE06 package challenge/completion | 40–60 (exception) |
| [ ] | 006 | [Perform a customer package operation](E2E-Tasks/006-package-command.md) | 005 | LIFE04 install only | 20–30 |
| [ ] | 007 | [Observe a deliberate customer reboot](E2E-Tasks/007-customer-reboot.md) | 006 | LIFE02 | 40–60 (exception) |
| [ ] | 077a | [Read app rows and initial access choices](E2E-Tasks/077a-app-row-observations.md) | Baseline | PARENT12; UI13 complete public app-row observations | 20–30 |
| [ ] | 008 | [E2E-002: clean](E2E-Tasks/008-case-2.md) | 007, 013, 077a | Cases 2 | 40–60 (exception) |
| [ ] | 029 | [Open feedback and read synthetic drafts](E2E-Tasks/029-feedback-read.md) | Baseline | FEED01, FEED03 | 20–30 |
| [ ] | 009 | [Replace a nonsecret field value](E2E-Tasks/009-text.md) | 029 | UI16 | 20–30 |
| [ ] | 040b | [Select and read ordinary daily presets](E2E-Tasks/040b-allowance-presets.md) | 009, 017 | PARENT05 preset 0/15 selection and saved readback | 20–30 |
| [ ] | 040 | [Commit custom daily allowances](E2E-Tasks/040-allowance.md) | 009, 017, 040b | PARENT05/06 valid ordinary values | 20–30 |
| [ ] | 194 | [Read an expanded time explanation](E2E-Tasks/194-read-an-expanded-time-explanation.md) | 040 | PARENT20 | 20–30 |
| [ ] | 041 | [Read remaining time and configure time controls](E2E-Tasks/041-time-explanation.md) | 194 | PARENT09, FLOW02 | 20–30 |
| [ ] | 180 | [Set an allowance for a named child](E2E-Tasks/180-set-an-allowance-for-a-named-child.md) | 041 | FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup | 15–30 |
| [ ] | 203 | [E2E-036: zero-total](E2E-Tasks/203-case-161.md) | 180 | Cases 161 | 20–30 |
| [ ] | 028 | [Close and reopen Parent](E2E-Tasks/028-app-restart.md) | Baseline | LIFE01 | 20–30 |
| [ ] | 040a | [Qualify daily-allowance boundaries](E2E-Tasks/040a-allowance-boundaries.md) | 040 | PARENT06 boundary/invalid values; PARENT08 validation | 20–30 |
| [ ] | 200 | [E2E-035: boundaries](E2E-Tasks/200-case-158.md) | 180, 040a, 028 | Cases 158 | 30–55 (exception) |
| [ ] | 012c | [Choose valid kiosk durations and soft-app access](E2E-Tasks/012c-kiosk-valid-duration.md) | 012, 009 | REQUEST04/05/06/08 kiosk valid durations, estimates and app choice | 20–30 |
| [ ] | 012a | [Reject invalid kiosk durations](E2E-Tasks/012a-request-duration.md) | 012, 009, 012c | REQUEST04 duration; REQUEST05/06/08 and REQUEST09 invalid-input branch, kiosk | 20–30 |
| [ ] | 014 | [Compose prepared request choices](E2E-Tasks/014-request-flow.md) | 012a, 013 | FLOW04 kiosk | 20–30 |
| [ ] | 015 | [E2E-015: kiosk-cancel](E2E-Tasks/015-case-47.md) | 180, 014 | Cases 47 | 20–30 |
| [ ] | 015b | [E2E-015: kiosk-escape](E2E-Tasks/015b-case-48.md) | 180, 014 | Cases 48 | 20–30 |
| [ ] | 019a | [Inspect and qualify the kiosk MATE prompt entry](E2E-Tasks/019a-mate-prompt.md) | 012a, 004, 013 | MATE provider owner, real request context and guarded Cancel/form return | 20–30 |
| [ ] | 019 | [Qualify the real selected-parent approval prompt](E2E-Tasks/019-auth-prompt.md) | 012a, 004, 019a | REQUEST09, AUTH01 kiosk | 20–30 |
| [ ] | 020a | [Qualify kiosk secret submission and automatic approved exit](E2E-Tasks/020a-kiosk-approval.md) | 019, 013 | AUTH02 kiosk approval; REQUEST11/12 success and automatic GDM exit | 20–30 |
| [ ] | 020b | [Observe kiosk password rejection and Cancel](E2E-Tasks/020b-kiosk-rejection.md) | 019, 013, 020a | AUTH02 kiosk rejection/Cancel with REQUEST11 preserved-form results | 20–30 |
| [ ] | 020 | [Qualify immediate approved kiosk exit](E2E-Tasks/020-auth-result.md) | 019, 013, 020a, 020b | AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits | 20–30 |
| [ ] | 021a | [Compose successful kiosk approval and time request](E2E-Tasks/021a-kiosk-approved-flow.md) | 020, 014 | FLOW05/06 kiosk approved branch | 20–30 |
| [ ] | 022 | [E2E-016: approved](E2E-Tasks/022-case-50.md) | 180, 021a | Cases 50 | 20–30 |
| [ ] | 021 | [Compose kiosk rejection and cancellation](E2E-Tasks/021-approval-flow.md) | 020, 014, 021a | FLOW05/06/07 kiosk | 20–30 |
| [ ] | 023 | [E2E-016: denied](E2E-Tasks/023-case-51.md) | 180, 021 | Cases 51 | 20–30 |
| [ ] | 023b | [E2E-016: cancelled](E2E-Tasks/023b-case-52.md) | 180, 021 | Cases 52 | 20–30 |
| [ ] | 024c | [Prepare and qualify multiple eligible kiosk accounts](E2E-Tasks/024c-kiosk-multiple.md) | 020 | FIX03 multiple-child/multiple-approver profile | 20–30 |
| [ ] | 025 | [E2E-017: multiple](E2E-Tasks/025-case-53.md) | 024c, 180 | Cases 53 | 20–30 |
| [ ] | 024a | [Prepare the ineligible-approver kiosk profile](E2E-Tasks/024a-eligible-kiosk-fixtures.md) | 020, 024c | FIX03 multiple/ineligible-approver profiles | 20–30 |
| [ ] | 027 | [E2E-017: ineligible-parent](E2E-Tasks/027-case-56.md) | 024a, 180 | Cases 56 | 20–30 |
| [ ] | 185k | [Read restricted station About](E2E-Tasks/185k-read-restricted-station-about.md) | 014 | ABOUT01 kiosk and unavailable external actions | 20–30 |
| [ ] | 234 | [E2E-042: kiosk](E2E-Tasks/234-case-192.md) | 185k, 180 | Cases 192 | 20–30 |
| [ ] | 030 | [Read privacy and preserve a dialog draft](E2E-Tasks/030-feedback-privacy.md) | 009 | FEED05; FEED10 dialog persistence | 20–30 |
| [ ] | 031 | [Observe feedback validation and Send availability](E2E-Tasks/031-feedback-states.md) | 009 | FEED09 validation/control snapshots | 20–30 |
| [ ] | 033 | [Apply and observe rich-text formatting](E2E-Tasks/033-format.md) | 009 | UI24, FEED04 | 20–30 |
| [ ] | 044a | [Return to an already-open window on one desktop](E2E-Tasks/044a-window-switch.md) | 001t, 009 | DESK10 same-desktop window switching | 20–30 |
| [ ] | 032 | [E2E-031: validation](E2E-Tasks/032-case-153.md) | 030, 031, 033, 044a | Cases 153 | 20–30 |
| [ ] | 036e | [Stage synthetic files and navigate to their directory](E2E-Tasks/036e-files-location.md) | 009, 001s | FIX04 synthetic files; FILE07 Nautilus directory entry | 20–30 |
| [ ] | 036c | [Select exact synthetic entries in Files](E2E-Tasks/036c-files-navigation.md) | 009, 001s, 036e | FIX04 synthetic files; FILE07 and FILE04 exact Nautilus location/entry observations | 20–30 |
| [ ] | 036d | [Qualify public file copy and destination readback](E2E-Tasks/036d-files-copy.md) | 036c | FILE05 copy; exact source/destination and public resulting entry | 20–30 |
| [ ] | 036 | [Qualify file rename and compose synthetic-file operations](E2E-Tasks/036-files.md) | 009, 036d | FILE07/04/05; FIX04 synthetic files | 20–30 |
| [ ] | 037 | [Select multiple files or cancel through the installed chooser](E2E-Tasks/037-file-chooser.md) | 036, 029, 031 | FILE03 installed feedback open/cancel; actual provider binding | 20–30 |
| [ ] | 038a | [Read attachment details and remove one item](E2E-Tasks/038a-attachment-items.md) | 037, 010, 031 | FEED06/07/13 attachment names, sizes, order and removal | 20–30 |
| [ ] | 038b | [Qualify offered attachment preview and return](E2E-Tasks/038b-attachment-preview.md) | 038a | FEED12 offered preview and unchanged attachment-list return | 20–30 |
| [ ] | 038 | [Qualify attachment rejection boundaries](E2E-Tasks/038-attachments.md) | 037, 010, 031, 038b | FEED06, FEED07, FEED12, FEED13 | 20–30 |
| [ ] | 030a | [Observe draft reset after Parent exits](E2E-Tasks/030a-feedback-reset.md) | 028, 030 | FEED10 app-exit reset | 20–30 |
| [ ] | 034 | [E2E-031: draft-reopen](E2E-Tasks/034-case-152.md) | 033, 030a, 038, 044a | Cases 152 | 20–30 |
| [ ] | 195a | [Qualify the installed text-document handler](E2E-Tasks/195a-document-open.md) | 036 | FILE08 text-document identity/content and normal close/return | 20–30 |
| [ ] | 195 | [Qualify archive contents and compose document opening](E2E-Tasks/195-open-a-customer-document-or-archive.md) | 036, 195a | FILE08 | 20–30 |
| [ ] | 196 | [Edit and save an open synthetic document](E2E-Tasks/196-edit-and-save-an-open-synthetic-document.md) | 195 | FILE09 | 20–30 |
| [ ] | 039 | [E2E-031: attachments](E2E-Tasks/039-case-154.md) | 038, 030, 196, 044a | Cases 154 | 35–55 (exception) |
| [ ] | 016b | [Start and collect a trace of an unchanged public state](E2E-Tasks/016b-trace-stable-state.md) | 004a, 031 | UI25/26 observer readiness, token lifetime and stable-state collection | 40–60 (exception) |
| [ ] | 016 | [Trace one public state transition](E2E-Tasks/016-trace.md) | 004a, 031, 016b | UI25/26 trace start/readiness and finish | 40–60 (exception) |
| [ ] | 016a | [Compose observation around one caller input](E2E-Tasks/016a-compose-observation-around-one-caller-input.md) | 016 | UI22 | 15–30 |
| [ ] | 017a | [Observe saving while a Parent control changes](E2E-Tasks/017a-parent-save-trace.md) | 017, 016a | PARENT08 transition mode | 20–30 |
| [ ] | 201 | [E2E-035: save-order](E2E-Tasks/201-case-159.md) | 180, 017a, 028 | Cases 159 | 20–30 |
| [ ] | 031a | [Observe diagnostic collection from its start](E2E-Tasks/031a-feedback-collection.md) | 016a, 030 | FEED09 collection trace | 20–30 |
| [ ] | 037a | [Save to a selected location through the installed chooser](E2E-Tasks/037a-save-chooser.md) | 037, 031a | FILE03 installed feedback save; actual provider binding | 20–30 |
| [ ] | 045 | [Save and open customer-selected diagnostics](E2E-Tasks/045-diagnostic-export.md) | 037a, 044a, 195 | FEED08 | 20–30 |
| [ ] | 046 | [E2E-031: diagnostic-export](E2E-Tasks/046-case-155.md) | 045 | Cases 155 | 35–55 (exception) |
| [ ] | 052c | [Wait a bounded real interval under the attempt guard](E2E-Tasks/052c-wait-a-bounded-real-interval-under-the-attempt-guard.md) | Baseline | TIME03 | 15–30 |
| [ ] | 185w | [Qualify the Parent website destination](E2E-Tasks/185w-website-destination.md) | 044a, 001s | INFO01 Parent website browser identity and close/return | 20–30 |
| [ ] | 185v | [Qualify the Parent privacy destination](E2E-Tasks/185v-privacy-destination.md) | 185w | INFO01 Parent privacy page identity and close/return | 20–30 |
| [ ] | 185s | [Qualify the Parent support mail destination](E2E-Tasks/185s-support-destination.md) | 044a, 001s | INFO01 Parent support mail recipient/subject and close without sending | 20–30 |
| [ ] | 185p | [Read Parent Help and legal notices and complete information links](E2E-Tasks/185p-read-parent-information-links.md) | 044a, 185w, 185v, 185s, 185l | INFO01 Parent | 20–30 |
| [ ] | 232 | [E2E-042: parent-links](E2E-Tasks/232-case-190.md) | 185p | Cases 190 | 20–30 |
| [ ] | 193 | [Operate public connectivity controls](E2E-Tasks/193-operate-public-connectivity-controls.md) | 003d, 010, 044a | LIFE06 | 20–30 |
| [ ] | 035p | [Install the declared native app fixtures](E2E-Tasks/035p-native-fixtures.md) | 006, 077a | FIX04 native assets; LIFE04 fixture installation | 20–30 |
| [ ] | 077b | [Search the public app catalogue](E2E-Tasks/077b-catalogue-search.md) | 010, 035p, 009, 077a | PARENT10 exact catalogue search results | 20–30 |
| [ ] | 077 | [Filter the public app catalogue](E2E-Tasks/077-catalogue.md) | 010, 035p, 009, 077a, 077b | PARENT10, PARENT11 | 20–30 |
| [ ] | 226 | [E2E-041: search-filters](E2E-Tasks/226-case-184.md) | 077, 180 | Cases 184 | 20–30 |
| [ ] | 078a | [Edit one match rule and Save or Cancel](E2E-Tasks/078a-match-save-cancel.md) | 077, 017 | PARENT13/15 match editor, valid Save and Cancel | 20–30 |
| [ ] | 078 | [Validate and reset one match rule](E2E-Tasks/078-match-editor.md) | 077, 017, 078a | PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts | 20–30 |
| [ ] | 079c | [Save one app's public access choice](E2E-Tasks/079c-access-choices.md) | 078 | PARENT16 Allowed/Hard/Soft save and row readback | 20–30 |
| [ ] | 079 | [Compose one app match/access edit](E2E-Tasks/079-policy.md) | 078, 079c | PARENT16 and FLOW03 public app-policy editing | 20–30 |
| [ ] | 186 | [Review a rejected Parent rule's report](E2E-Tasks/186-review-a-rejected-parent-rule-s-report.md) | 078, 030 | PARENT15 failed-save; FEED15 Parent and report-close binding | 20–30 |
| [ ] | 247 | [E2E-045: parent](E2E-Tasks/247-case-205.md) | 186 | Cases 205 | 20–30 |
| [ ] | 043b | [Qualify a fresh child login with usable daily time](E2E-Tasks/043b-fresh-child-allowed.md) | 004, 041 | GDM06/07 and FLOW15 fresh-child success | 20–30 |
| [ ] | 043 | [Observe fresh child time denial and return](E2E-Tasks/043-unlock.md) | 004, 041, 043b | GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return | 20–30 |
| [ ] | 052 | [Observe the child countdown or its absence](E2E-Tasks/052-countdown.md) | 043 | TIME01 child-desktop presence and limits-off absence | 20–30 |
| [ ] | 061 | [E2E-015: kiosk-approved](E2E-Tasks/061-case-49.md) | 180, 021, 052 | Cases 49 | 20–30 |
| [ ] | 070 | [Double-click kiosk Request and observe one prompt](E2E-Tasks/070-double-request.md) | 020, 016a | UI20; REQUEST10 kiosk binding | 20–30 |
| [ ] | 074 | [E2E-014: kiosk-predefined](E2E-Tasks/074-case-41.md) | 180, 070, 052 | Cases 41 | 40–60 (exception) |
| [ ] | 075 | [E2E-014: kiosk-custom](E2E-Tasks/075-case-42.md) | 180, 070, 052 | Cases 42 | 40–60 (exception) |
| [ ] | 035c | [Launch and use a native fixture from the app grid](E2E-Tasks/035c-native-grid-usable.md) | 035p, 001t, 009 | APP01/02/03 native app-grid usable route | 20–30 |
| [ ] | 035 | [Launch and use native fixtures by command](E2E-Tasks/035-native-app.md) | 035p, 001t, 009, 035c | APP01/02/03 native grid/command usable scope | 20–30 |
| [ ] | 047 | [Record app activity and compose launch/use](E2E-Tasks/047-app-activity.md) | 035, 043 | APP04; FLOW08 native usable-app scope | 20–30 |
| [ ] | 048 | [Reveal the child's request entry](E2E-Tasks/048-shell-panel.md) | 043, 011 | DESK12, REQUEST02/03 overlay entry/readback | 20–30 |
| [ ] | 048e | [Choose valid overlay values and Cancel](E2E-Tasks/048e-overlay-valid-choices.md) | 048, 014, 047 | REQUEST04/05/06/08 overlay valid choices and REQUEST11/12 Cancel | 20–30 |
| [ ] | 048a | [Qualify overlay Escape and invalid durations](E2E-Tasks/048a-overlay-choices.md) | 048, 014, 047, 048e | Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04 | 20–30 |
| [ ] | 049 | [E2E-015: child-overlay-cancel](E2E-Tasks/049-case-44.md) | 180, 048a | Cases 44 | 20–30 |
| [ ] | 049b | [E2E-015: child-overlay-escape](E2E-Tasks/049b-case-45.md) | 180, 048a | Cases 45 | 20–30 |
| [ ] | 185oa | [Read overlay About and its license](E2E-Tasks/185oa-overlay-license.md) | 048a, 044a, 185p, 185l | ABOUT01/02 overlay information and license-handler binding | 20–30 |
| [ ] | 185ob | [Qualify overlay website and privacy links](E2E-Tasks/185ob-overlay-browser-links.md) | 185oa | INFO01 overlay website/privacy browser destinations | 20–30 |
| [ ] | 185o | [Complete overlay support and legal links](E2E-Tasks/185o-read-overlay-about-and-links.md) | 048a, 044a, 185p, 185l, 185ob | ABOUT01/02 and INFO01 overlay | 20–30 |
| [ ] | 233 | [E2E-042: child-overlay](E2E-Tasks/233-case-191.md) | 185o, 180 | Cases 191 | 20–30 |
| [ ] | 048c | [Qualify the overlay Shell prompt and Cancel](E2E-Tasks/048c-shell-prompt.md) | 048a, 019, 004 | Shell Polkit AUTH01 overlay recipient and guarded Cancel/preserved-form result | 20–30 |
| [ ] | 048d | [Qualify overlay approval and automatic return](E2E-Tasks/048d-overlay-approved-exit.md) | 048c, 021 | AUTH02 overlay approval; REQUEST11/12 success and automatic child return | 20–30 |
| [ ] | 048f | [Observe overlay password rejection and Cancel](E2E-Tasks/048f-overlay-rejection.md) | 048a, 021, 048c, 048d | AUTH02 overlay rejection/Cancel and preserved-form readback | 20–30 |
| [ ] | 048b | [Complete overlay exits and approval compositions](E2E-Tasks/048b-overlay-approval.md) | 048a, 021, 048c, 048d, 048f | Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07 | 20–30 |
| [ ] | 060 | [E2E-015: child-overlay-approved](E2E-Tasks/060-case-46.md) | 180, 048b, 052 | Cases 46 | 20–30 |
| [ ] | 070a | [Observe one prompt after an overlay double-click](E2E-Tasks/070a-overlay-double-request.md) | 070, 048b | REQUEST10 overlay binding | 20–30 |
| [ ] | 071 | [E2E-014: child-overlay-predefined](E2E-Tasks/071-case-38.md) | 180, 070a, 052 | Cases 38 | 40–60 (exception) |
| [ ] | 072 | [E2E-014: child-overlay-custom](E2E-Tasks/072-case-39.md) | 180, 070a, 052 | Cases 39 | 40–60 (exception) |
| [ ] | 042a | [Lock a desktop and observe its challenge surface](E2E-Tasks/042a-lock-surface.md) | 003d | DESK05/06 explicit Lock, curtain and challenge reveal | 20–30 |
| [ ] | 042 | [Prove the intended lock-screen recipient](E2E-Tasks/042-lock-recipient.md) | 003d, 042a | DESK05, DESK06, DESK07 | 20–30 |
| [ ] | 043c | [Unlock the intended retained child successfully](E2E-Tasks/043c-retained-unlock-success.md) | 043, 042 | GDM02 retained lock entry and DESK08 successful unlock | 20–30 |
| [ ] | 043a | [Observe retained-child time denial and return](E2E-Tasks/043a-retained-unlock.md) | 043, 042, 043c | GDM02 retained-child lock entry; DESK08/11 | 20–30 |
| [ ] | 044b | [Return to an existing Parent desktop and window](E2E-Tasks/044b-retained-parent.md) | 043a, 044a | DESK09 and FLOW01 retained Parent entry | 20–30 |
| [ ] | 044 | [Visit both retained child desktops](E2E-Tasks/044-retained-entry.md) | 043a, 044a, 044b | DESK09; FLOW15 and FLOW01 retained scopes | 20–30 |
| [ ] | 073 | [E2E-014: child-overlay-rest-of-day](E2E-Tasks/073-case-40.md) | 180, 070a, 052, 044, 052c | Cases 40 | 40–60 (exception) |
| [ ] | 076 | [E2E-014: kiosk-rest-of-day](E2E-Tasks/076-case-43.md) | 180, 070, 052, 044, 052c, 021 | Cases 43 | 40–60 (exception) |
| [ ] | 155a | [Compare overlay choices at the kiosk](E2E-Tasks/155a-choices-overlay-to-kiosk.md) | 048a, 044, 180 | FLOW12 overlay-to-kiosk choices for both children | 20–30 |
| [ ] | 156 | [E2E-018: overlay-to-kiosk-first](E2E-Tasks/156-case-58.md) | 155a | Cases 58 | 20–30 |
| [ ] | 156b | [E2E-018: overlay-to-kiosk-second](E2E-Tasks/156b-case-59.md) | 155a | Cases 59 | 20–30 |
| [ ] | 155 | [Compare kiosk choices at each child overlay](E2E-Tasks/155-cross-surface.md) | 048a, 044, 180, 155a | FLOW12 current choices | 20–30 |
| [ ] | 157 | [E2E-018: kiosk-to-overlay-first](E2E-Tasks/157-case-60.md) | 155 | Cases 60 | 20–30 |
| [ ] | 157b | [E2E-018: kiosk-to-overlay-second](E2E-Tasks/157b-case-61.md) | 155 | Cases 61 | 20–30 |
| [ ] | 047a | [Compose retained app visits for distinct users](E2E-Tasks/047a-retained-app-visits.md) | 047, 044 | FLOW09 and FLOW14 distinct-user retention | 20–30 |
| [ ] | 050a | [Read a revocation warning and Cancel](E2E-Tasks/050a-revoke-cancel.md) | 021, 044 | PARENT17/18 revocation target, warning and Cancel | 20–30 |
| [ ] | 050 | [Confirm grant revocation and read balances](E2E-Tasks/050-revocation.md) | 021, 044, 050a | PARENT17, PARENT18 | 20–30 |
| [ ] | 051 | [Compose the daily-only time profile](E2E-Tasks/051-time-profiles-daily.md) | 180, 003d | FLOW13 daily-only, fresh/same Parent entry with observed G=0 | 20–30 |
| [ ] | 052d | [Measure the displayed countdown's minute ticks](E2E-Tasks/052d-countdown-minutes.md) | 052, 051, 052c | TIME02 minute-precision sampling | 20–30 |
| [ ] | 052a | [Measure final-second countdown ticks](E2E-Tasks/052a-countdown-ticks.md) | 052, 051, 052c, 052d | TIME02 minute/final-second ticks | 20–30 |
| [ ] | 062 | [Use an app until a natural enforced lock](E2E-Tasks/062-natural-expiry.md) | 052a, 047 | TIME04 | 20–30 |
| [ ] | 063 | [E2E-008: retained-unlock](E2E-Tasks/063-case-21.md) | 062, 043a | Cases 21 | 35–55 (exception) |
| [ ] | 064 | [E2E-008: fresh-login](E2E-Tasks/064-case-22.md) | 062, 050 | Cases 22 | 40–60 (exception) |
| [ ] | 052b | [Prove countdown absence on other surfaces](E2E-Tasks/052b-countdown-absence.md) | 052, 043a | TIME01 lock/GDM/other-user absence | 20–30 |
| [ ] | 181h | [Read the countdown hover explanation](E2E-Tasks/181h-read-the-countdown-hover-explanation.md) | 052 | DESK12 showing countdown binding; UI27 and PANEL03 | 20–30 |
| [ ] | 059 | [E2E-011: daily-only](E2E-Tasks/059-case-27.md) | 052b, 181h, 044, 062 | Cases 27 | 35–55 (exception) |
| [ ] | 065a | [Prepare grant-only time and explicit revoke-first entry](E2E-Tasks/065a-grant-only-profile.md) | 051, 050 | FLOW13 grant-only profile and explicit revoke preparation | 20–30 |
| [ ] | 065 | [Compose the combined grant-dominant profile](E2E-Tasks/065-time-profiles-grant.md) | 051, 050, 065a | FLOW13 grant-only/combined; retained entry and explicit revoke preparation | 20–30 |
| [ ] | 066 | [E2E-010: parent](E2E-Tasks/066-case-25.md) | 065, 052a, 047a | Cases 25 | 35–55 (exception) |
| [ ] | 067 | [E2E-010: other-child](E2E-Tasks/067-case-26.md) | 065, 052a, 047a | Cases 26 | 35–55 (exception) |
| [ ] | 068 | [E2E-011: grant-only](E2E-Tasks/068-case-28.md) | 065, 052b, 181h, 062 | Cases 28 | 35–55 (exception) |
| [ ] | 069 | [E2E-011: combined](E2E-Tasks/069-case-29.md) | 065, 052b, 181h, 062 | Cases 29 | 35–55 (exception) |
| [ ] | 181m | [Operate the countdown context menu](E2E-Tasks/181m-operate-the-countdown-context-menu.md) | 181h | UI28 and PANEL01/02 | 20–30 |
| [ ] | 204 | [E2E-037: sign-out-in](E2E-Tasks/204-case-162.md) | 181m, 048a, 062, 044 | Cases 162 | 20–30 |
| [ ] | 205 | [E2E-037: reboot](E2E-Tasks/205-case-163.md) | 181m, 048a, 062, 044, 007 | Cases 163 | 20–30 |
| [ ] | 197 | [Compose overlay approval and return](E2E-Tasks/197-compose-approval-and-return-to-the-child.md) | 048b, 044, 052 | FLOW20 overlay new/open form | 20–30 |
| [ ] | 265 | [E2E-048: daily-only-child-overlay](E2E-Tasks/265-case-223.md) | 197, 052c, 051 | Cases 223; gate in brief | 20–30 |
| [ ] | 267 | [E2E-048: grant-only-child-overlay](E2E-Tasks/267-case-225.md) | 197, 052c, 065 | Cases 225; gate in brief | 20–30 |
| [ ] | 271 | [E2E-048: grant-dominant-child-overlay](E2E-Tasks/271-case-229.md) | 197, 052c, 065 | Cases 229; gate in brief | 20–30 |
| [ ] | 197a | [Compose kiosk approval and fresh child entry](E2E-Tasks/197a-kiosk-fresh-return.md) | 021, 044, 052 | FLOW20 kiosk new/open form with fresh-child destination | 20–30 |
| [ ] | 197k | [Compose kiosk approval and retained child entry](E2E-Tasks/197k-kiosk-approval-return.md) | 021, 044, 052, 197a | FLOW20 kiosk new/open form and fresh/retained child | 20–30 |
| [ ] | 266 | [E2E-048: daily-only-kiosk](E2E-Tasks/266-case-224.md) | 197k, 052c, 051 | Cases 224; gate in brief | 20–30 |
| [ ] | 268 | [E2E-048: grant-only-kiosk](E2E-Tasks/268-case-226.md) | 197k, 052c, 065 | Cases 226; gate in brief | 20–30 |
| [ ] | 272 | [E2E-048: grant-dominant-kiosk](E2E-Tasks/272-case-230.md) | 197k, 052c, 065 | Cases 230; gate in brief | 20–30 |
| [ ] | 079d | [Observe native launch denial without a prior window](E2E-Tasks/079d-native-denial.md) | 079, 047, 044 | APP02 and FLOW08 native grid/command blocked-launch results | 20–30 |
| [ ] | 079a | [Observe closure of an already-open native app](E2E-Tasks/079a-observe-native-policy-denial-and-existing-window-closure.md) | 079, 047, 044, 079d | APP02 and FLOW08 native grid/command policy results | 20–30 |
| [ ] | 053 | [E2E-005: daily-only-new](E2E-Tasks/053-case-7.md) | 079a, 180, 052 | Cases 7 | 40–60 (exception) |
| [ ] | 054 | [E2E-005: daily-only-retained](E2E-Tasks/054-case-8.md) | 079a, 180, 052 | Cases 8 | 40–60 (exception) |
| [ ] | 055 | [E2E-005: grant-only-new](E2E-Tasks/055-case-9.md) | 079a, 180, 052, 021 | Cases 9 | 40–60 (exception) |
| [ ] | 056 | [E2E-005: grant-only-retained](E2E-Tasks/056-case-10.md) | 079a, 180, 052, 021 | Cases 10 | 40–60 (exception) |
| [ ] | 057 | [E2E-005: combined-new](E2E-Tasks/057-case-11.md) | 079a, 180, 052, 021 | Cases 11 | 40–60 (exception) |
| [ ] | 058 | [E2E-005: combined-retained](E2E-Tasks/058-case-12.md) | 079a, 180, 052, 021 | Cases 12 | 40–60 (exception) |
| [ ] | 090 | [E2E-019: native-grid-allowed-enabled](E2E-Tasks/090-case-62.md) | 079a, 180 | Cases 62 | 20–30 |
| [ ] | 090b | [E2E-019: native-grid-allowed-disabled](E2E-Tasks/090b-case-63.md) | 079a, 180 | Cases 63 | 20–30 |
| [ ] | 091 | [E2E-019: native-grid-hard-blocked-enabled](E2E-Tasks/091-case-64.md) | 079a, 180 | Cases 64 | 20–30 |
| [ ] | 091b | [E2E-019: native-grid-hard-blocked-disabled](E2E-Tasks/091b-case-65.md) | 079a, 180 | Cases 65 | 20–30 |
| [ ] | 092 | [E2E-019: native-grid-soft-blocked-enabled](E2E-Tasks/092-case-66.md) | 079a, 180 | Cases 66 | 20–30 |
| [ ] | 092b | [E2E-019: native-grid-soft-blocked-disabled](E2E-Tasks/092b-case-67.md) | 079a, 180 | Cases 67 | 20–30 |
| [ ] | 099 | [E2E-019: native-command-allowed-enabled](E2E-Tasks/099-case-80.md) | 079a, 180 | Cases 80 | 20–30 |
| [ ] | 099b | [E2E-019: native-command-allowed-disabled](E2E-Tasks/099b-case-81.md) | 079a, 180 | Cases 81 | 20–30 |
| [ ] | 100 | [E2E-019: native-command-hard-blocked-enabled](E2E-Tasks/100-case-82.md) | 079a, 180 | Cases 82 | 20–30 |
| [ ] | 100b | [E2E-019: native-command-hard-blocked-disabled](E2E-Tasks/100b-case-83.md) | 079a, 180 | Cases 83 | 20–30 |
| [ ] | 101 | [E2E-019: native-command-soft-blocked-enabled](E2E-Tasks/101-case-84.md) | 079a, 180 | Cases 84 | 20–30 |
| [ ] | 101b | [E2E-019: native-command-soft-blocked-disabled](E2E-Tasks/101b-case-85.md) | 079a, 180 | Cases 85 | 20–30 |
| [ ] | 227 | [E2E-041: match-editor](E2E-Tasks/227-case-185.md) | 186, 180, 079a | Cases 185 | 20–30 |
| [ ] | 228 | [E2E-041: match-reopen](E2E-Tasks/228-case-186.md) | 186, 079, 028, 180, 079a | Cases 186 | 20–30 |
| [ ] | 229 | [E2E-041: shared-launchers](E2E-Tasks/229-case-187.md) | 079a, 180 | Cases 187 | 20–30 |
| [ ] | 079b | [Compose a named app-rule set](E2E-Tasks/079b-compose-a-named-app-rule-set.md) | 079, 044 | FLOW19 | 15–30 |
| [ ] | 080 | [E2E-006: enabled-precise](E2E-Tasks/080-case-13.md) | 079a, 079b, 047a, 065, 028 | Cases 13 | 40–60 (exception) |
| [ ] | 081 | [E2E-006: enabled-pattern](E2E-Tasks/081-case-14.md) | 079a, 079b, 047a, 065, 028 | Cases 14 | 40–60 (exception) |
| [ ] | 082 | [E2E-006: disabled-precise](E2E-Tasks/082-case-15.md) | 079a, 079b, 047a, 065, 028 | Cases 15 | 40–60 (exception) |
| [ ] | 083 | [E2E-006: disabled-pattern](E2E-Tasks/083-case-16.md) | 079a, 079b, 047a, 065, 028 | Cases 16 | 40–60 (exception) |
| [ ] | 084 | [E2E-007: zero-single](E2E-Tasks/084-case-17.md) | 079b, 079a, 047a, 065 | Cases 17 | 40–60 (exception) |
| [ ] | 085 | [E2E-007: remaining-single](E2E-Tasks/085-case-19.md) | 079b, 079a, 047a, 065 | Cases 19 | 40–60 (exception) |
| [ ] | 086 | [E2E-012: excluded-first](E2E-Tasks/086-case-30.md) | 048b, 079b, 079a, 065, 052, 052c | Cases 30 | 20–30 |
| [ ] | 086b | [E2E-012: excluded-second](E2E-Tasks/086b-case-31.md) | 048b, 079b, 079a, 065, 052, 052c | Cases 31 | 20–30 |
| [ ] | 087 | [E2E-012: included-first](E2E-Tasks/087-case-32.md) | 048b, 079b, 079a, 065, 052, 052c | Cases 32 | 20–30 |
| [ ] | 087b | [E2E-012: included-second](E2E-Tasks/087b-case-33.md) | 048b, 079b, 079a, 065, 052, 052c | Cases 33 | 20–30 |
| [ ] | 088 | [E2E-013: child-overlay-wrong-password](E2E-Tasks/088-case-34.md) | 079b, 079a, 048b, 052 | Cases 34 | 20–30 |
| [ ] | 088b | [E2E-013: child-overlay-cancel](E2E-Tasks/088b-case-35.md) | 079b, 079a, 048b, 052 | Cases 35 | 20–30 |
| [ ] | 089 | [E2E-013: kiosk-wrong-password](E2E-Tasks/089-case-36.md) | 079b, 079a, 021, 052 | Cases 36 | 20–30 |
| [ ] | 089b | [E2E-013: kiosk-cancel](E2E-Tasks/089b-case-37.md) | 079b, 079a, 021, 052 | Cases 37 | 20–30 |
| [ ] | 158 | [E2E-022: app-restart-active](E2E-Tasks/158-case-116.md) | 155, 079b, 079a, 065, 052c, 052, 028 | Cases 116 | 40–60 (exception) |
| [ ] | 159 | [E2E-022: app-restart-expired](E2E-Tasks/159-case-117.md) | 155, 079b, 079a, 065, 052c, 052, 028 | Cases 117 | 40–60 (exception) |
| [ ] | 160 | [E2E-022: sign-out-in-active](E2E-Tasks/160-case-118.md) | 155, 079b, 079a, 065, 052c, 052 | Cases 118 | 40–60 (exception) |
| [ ] | 161 | [E2E-022: sign-out-in-expired](E2E-Tasks/161-case-119.md) | 155, 079b, 079a, 065, 052c, 052 | Cases 119 | 40–60 (exception) |
| [ ] | 162 | [E2E-022: reboot-active](E2E-Tasks/162-case-120.md) | 155, 079b, 079a, 065, 052c, 052, 007 | Cases 120 | 40–60 (exception) |
| [ ] | 163 | [E2E-022: reboot-expired](E2E-Tasks/163-case-121.md) | 155, 079b, 079a, 065, 052c, 052, 007 | Cases 121 | 40–60 (exception) |
| [ ] | 164 | [E2E-022: idle-active](E2E-Tasks/164-case-122.md) | 155, 079b, 079a, 065, 052c, 052 | Cases 122 | 40–60 (exception) |
| [ ] | 165 | [E2E-022: idle-expired](E2E-Tasks/165-case-123.md) | 155, 079b, 079a, 065, 052c, 052 | Cases 123 | 40–60 (exception) |
| [ ] | 105 | [E2E-025: excluded-new-login](E2E-Tasks/105-case-132.md) | 065, 079b, 079a, 052c | Cases 132 | 40–60 (exception) |
| [ ] | 106 | [E2E-025: excluded-retained-unlock](E2E-Tasks/106-case-133.md) | 065, 079b, 079a, 052c | Cases 133 | 40–60 (exception) |
| [ ] | 107 | [E2E-025: included-new-login](E2E-Tasks/107-case-134.md) | 065, 079b, 079a, 052c | Cases 134 | 40–60 (exception) |
| [ ] | 108 | [E2E-025: included-retained-unlock](E2E-Tasks/108-case-135.md) | 065, 079b, 079a, 052c | Cases 135 | 40–60 (exception) |
| [ ] | 202 | [E2E-036: daily-positive](E2E-Tasks/202-case-160.md) | 065, 079b, 079a | Cases 160 | 20–30 |
| [ ] | 236 | [E2E-043: child-overlay](E2E-Tasks/236-case-194.md) | 193, 079b, 079a, 052a, 050, 048b | Cases 194 | 20–30 |
| [ ] | 237 | [E2E-043: kiosk](E2E-Tasks/237-case-195.md) | 193, 079b, 079a, 052a, 050 | Cases 195 | 20–30 |
| [ ] | 273 | [E2E-049: native-grid-child-overlay](E2E-Tasks/273-case-231.md) | 197, 079b, 079a, 180 | Cases 231 | 20–30 |
| [ ] | 274 | [E2E-049: native-grid-kiosk](E2E-Tasks/274-case-232.md) | 197k, 079b, 079a, 180 | Cases 232 | 20–30 |
| [ ] | 279 | [E2E-049: native-command-child-overlay](E2E-Tasks/279-case-237.md) | 197, 079b, 079a, 180 | Cases 237 | 20–30 |
| [ ] | 280 | [E2E-049: native-command-kiosk](E2E-Tasks/280-case-238.md) | 197k, 079b, 079a, 180 | Cases 238 | 20–30 |
| [ ] | 035d | [Qualify a native executable path containing a space](E2E-Tasks/035d-native-space-path.md) | 036, 079a | FIX04 space-path asset; FILE05 copy and command-policy result | 20–30 |
| [ ] | 035a | [Qualify the comma-containing native fixture](E2E-Tasks/035a-qualify-native-fixtures-with-spaces-and-commas.md) | 036, 079a, 035d | FIX04 special-path native assets; FILE05 and command-result bindings | 20–30 |
| [ ] | 230 | [E2E-041: special-paths](E2E-Tasks/230-case-188.md) | 035a, 180 | Cases 188 | 20–30 |
| [ ] | 035b | [Qualify versioned AppImage pattern assets](E2E-Tasks/035b-qualify-versioned-appimage-pattern-assets.md) | 036, 079a, 186, 052c | FIX04 AppImage versions; FILE05 and pattern launch results | 20–30 |
| [ ] | 231 | [E2E-041: pattern-files](E2E-Tasks/231-case-189.md) | 035b, 180 | Cases 189 | 20–30 |
| [ ] | 036f | [Launch separate usable native windows from Files](E2E-Tasks/036f-native-files-usable.md) | 036, 079a | APP01/02/03 native file-manager usable/new-window route | 20–30 |
| [ ] | 036a | [Observe policy results for Files launches](E2E-Tasks/036a-native-file-routes.md) | 036, 079a, 036f | APP01/02/03 native file-manager route | 20–30 |
| [ ] | 096 | [E2E-019: native-file-manager-allowed-enabled](E2E-Tasks/096-case-74.md) | 180, 036a | Cases 74 | 20–30 |
| [ ] | 096b | [E2E-019: native-file-manager-allowed-disabled](E2E-Tasks/096b-case-75.md) | 180, 036a | Cases 75 | 20–30 |
| [ ] | 097 | [E2E-019: native-file-manager-hard-blocked-enabled](E2E-Tasks/097-case-76.md) | 180, 036a | Cases 76 | 20–30 |
| [ ] | 097b | [E2E-019: native-file-manager-hard-blocked-disabled](E2E-Tasks/097b-case-77.md) | 180, 036a | Cases 77 | 20–30 |
| [ ] | 098 | [E2E-019: native-file-manager-soft-blocked-enabled](E2E-Tasks/098-case-78.md) | 180, 036a | Cases 78 | 20–30 |
| [ ] | 098b | [E2E-019: native-file-manager-soft-blocked-disabled](E2E-Tasks/098b-case-79.md) | 180, 036a | Cases 79 | 20–30 |
| [ ] | 277 | [E2E-049: native-file-manager-child-overlay](E2E-Tasks/277-case-235.md) | 197, 079b, 180, 036a | Cases 235 | 20–30 |
| [ ] | 278 | [E2E-049: native-file-manager-kiosk](E2E-Tasks/278-case-236.md) | 197k, 079b, 180, 036a | Cases 236 | 20–30 |
| [ ] | 036g | [Place and launch a native desktop entry](E2E-Tasks/036g-native-desktop-usable.md) | 036, 079a, 035p | APP01/02/03 DING desktop entry and usable launch | 20–30 |
| [ ] | 036h | [Open a second native window from the desktop](E2E-Tasks/036h-native-desktop-new-window.md) | 036g | APP01/02 desktop separate-window route | 20–30 |
| [ ] | 036b | [Observe policy results for desktop launches](E2E-Tasks/036b-native-desktop-route.md) | 036, 079a, 035p, 036h | APP01/02/03 native desktop route | 20–30 |
| [ ] | 093 | [E2E-019: native-desktop-allowed-enabled](E2E-Tasks/093-case-68.md) | 180, 036b | Cases 68 | 20–30 |
| [ ] | 093b | [E2E-019: native-desktop-allowed-disabled](E2E-Tasks/093b-case-69.md) | 180, 036b | Cases 69 | 20–30 |
| [ ] | 094 | [E2E-019: native-desktop-hard-blocked-enabled](E2E-Tasks/094-case-70.md) | 180, 036b | Cases 70 | 20–30 |
| [ ] | 094b | [E2E-019: native-desktop-hard-blocked-disabled](E2E-Tasks/094b-case-71.md) | 180, 036b | Cases 71 | 20–30 |
| [ ] | 095 | [E2E-019: native-desktop-soft-blocked-enabled](E2E-Tasks/095-case-72.md) | 180, 036b | Cases 72 | 20–30 |
| [ ] | 095b | [E2E-019: native-desktop-soft-blocked-disabled](E2E-Tasks/095b-case-73.md) | 180, 036b | Cases 73 | 20–30 |
| [ ] | 275 | [E2E-049: native-desktop-child-overlay](E2E-Tasks/275-case-233.md) | 197, 079b, 180, 036b | Cases 233 | 20–30 |
| [ ] | 276 | [E2E-049: native-desktop-kiosk](E2E-Tasks/276-case-234.md) | 197k, 079b, 180, 036b | Cases 234 | 20–30 |
| [ ] | 109p | [Install the declared Snap fixtures](E2E-Tasks/109p-snap-fixtures.md) | 006, 077a | FIX04 Snap assets; LIFE04 fixed Snap installation profile | 20–30 |
| [ ] | 109b | [Launch and use Snap fixtures by command](E2E-Tasks/109b-snap-command-usable.md) | 109p, 079a | APP01/02/03/04 and FLOW08 Snap command usable/new-window route | 20–30 |
| [ ] | 109 | [Observe Snap command denial and closure](E2E-Tasks/109-snap.md) | 109p, 079a, 109b | APP01/02/03/04 and FLOW08 Snap command route | 20–30 |
| [ ] | 113 | [E2E-019: snap-command-allowed-enabled](E2E-Tasks/113-case-92.md) | 180, 109 | Cases 92 | 20–30 |
| [ ] | 113b | [E2E-019: snap-command-allowed-disabled](E2E-Tasks/113b-case-93.md) | 180, 109 | Cases 93 | 20–30 |
| [ ] | 114 | [E2E-019: snap-command-hard-blocked-enabled](E2E-Tasks/114-case-94.md) | 180, 109 | Cases 94 | 20–30 |
| [ ] | 114b | [E2E-019: snap-command-hard-blocked-disabled](E2E-Tasks/114b-case-95.md) | 180, 109 | Cases 95 | 20–30 |
| [ ] | 115 | [E2E-019: snap-command-soft-blocked-enabled](E2E-Tasks/115-case-96.md) | 180, 109 | Cases 96 | 20–30 |
| [ ] | 115b | [E2E-019: snap-command-soft-blocked-disabled](E2E-Tasks/115b-case-97.md) | 180, 109 | Cases 97 | 20–30 |
| [ ] | 283 | [E2E-049: snap-command-child-overlay](E2E-Tasks/283-case-241.md) | 197, 079b, 180, 109 | Cases 241 | 20–30 |
| [ ] | 284 | [E2E-049: snap-command-kiosk](E2E-Tasks/284-case-242.md) | 197k, 079b, 180, 109 | Cases 242 | 20–30 |
| [ ] | 109a | [Qualify Snap app-grid launches](E2E-Tasks/109a-snap-grid.md) | 109 | APP01/02/03/04 and FLOW08 Snap app-grid route | 20–30 |
| [ ] | 110 | [E2E-019: snap-grid-allowed-enabled](E2E-Tasks/110-case-86.md) | 180, 109a | Cases 86 | 20–30 |
| [ ] | 110b | [E2E-019: snap-grid-allowed-disabled](E2E-Tasks/110b-case-87.md) | 180, 109a | Cases 87 | 20–30 |
| [ ] | 111 | [E2E-019: snap-grid-hard-blocked-enabled](E2E-Tasks/111-case-88.md) | 180, 109a | Cases 88 | 20–30 |
| [ ] | 111b | [E2E-019: snap-grid-hard-blocked-disabled](E2E-Tasks/111b-case-89.md) | 180, 109a | Cases 89 | 20–30 |
| [ ] | 112 | [E2E-019: snap-grid-soft-blocked-enabled](E2E-Tasks/112-case-90.md) | 180, 109a | Cases 90 | 20–30 |
| [ ] | 112b | [E2E-019: snap-grid-soft-blocked-disabled](E2E-Tasks/112b-case-91.md) | 180, 109a | Cases 91 | 20–30 |
| [ ] | 281 | [E2E-049: snap-grid-child-overlay](E2E-Tasks/281-case-239.md) | 197, 079b, 180, 109a | Cases 239 | 20–30 |
| [ ] | 282 | [E2E-049: snap-grid-kiosk](E2E-Tasks/282-case-240.md) | 197k, 079b, 180, 109a | Cases 240 | 20–30 |
| [ ] | 116p | [Install the declared Flatpak fixtures](E2E-Tasks/116p-flatpak-fixtures.md) | 006, 077a | FIX04 Flatpak assets; LIFE04 fixed Flatpak installation profile | 20–30 |
| [ ] | 116b | [Launch and use Flatpak fixtures by command](E2E-Tasks/116b-flatpak-command-usable.md) | 116p, 079a | APP01/02/03/04 and FLOW08 Flatpak command usable/new-window route | 20–30 |
| [ ] | 116 | [Observe Flatpak command denial and closure](E2E-Tasks/116-flatpak.md) | 116p, 079a, 116b | APP01/02/03/04 and FLOW08 Flatpak command route | 20–30 |
| [ ] | 120 | [E2E-019: flatpak-command-allowed-enabled](E2E-Tasks/120-case-104.md) | 180, 116 | Cases 104 | 20–30 |
| [ ] | 120b | [E2E-019: flatpak-command-allowed-disabled](E2E-Tasks/120b-case-105.md) | 180, 116 | Cases 105 | 20–30 |
| [ ] | 121 | [E2E-019: flatpak-command-hard-blocked-enabled](E2E-Tasks/121-case-106.md) | 180, 116 | Cases 106 | 20–30 |
| [ ] | 121b | [E2E-019: flatpak-command-hard-blocked-disabled](E2E-Tasks/121b-case-107.md) | 180, 116 | Cases 107 | 20–30 |
| [ ] | 122 | [E2E-019: flatpak-command-soft-blocked-enabled](E2E-Tasks/122-case-108.md) | 180, 116 | Cases 108 | 20–30 |
| [ ] | 122b | [E2E-019: flatpak-command-soft-blocked-disabled](E2E-Tasks/122b-case-109.md) | 180, 116 | Cases 109 | 20–30 |
| [ ] | 287 | [E2E-049: flatpak-command-child-overlay](E2E-Tasks/287-case-245.md) | 197, 079b, 180, 116 | Cases 245 | 20–30 |
| [ ] | 288 | [E2E-049: flatpak-command-kiosk](E2E-Tasks/288-case-246.md) | 197k, 079b, 180, 116 | Cases 246 | 20–30 |
| [ ] | 116a | [Qualify Flatpak app-grid launches](E2E-Tasks/116a-flatpak-grid.md) | 116 | APP01/02/03/04 and FLOW08 Flatpak app-grid route | 20–30 |
| [ ] | 117 | [E2E-019: flatpak-grid-allowed-enabled](E2E-Tasks/117-case-98.md) | 180, 116a | Cases 98 | 20–30 |
| [ ] | 117b | [E2E-019: flatpak-grid-allowed-disabled](E2E-Tasks/117b-case-99.md) | 180, 116a | Cases 99 | 20–30 |
| [ ] | 118 | [E2E-019: flatpak-grid-hard-blocked-enabled](E2E-Tasks/118-case-100.md) | 180, 116a | Cases 100 | 20–30 |
| [ ] | 118b | [E2E-019: flatpak-grid-hard-blocked-disabled](E2E-Tasks/118b-case-101.md) | 180, 116a | Cases 101 | 20–30 |
| [ ] | 119 | [E2E-019: flatpak-grid-soft-blocked-enabled](E2E-Tasks/119-case-102.md) | 180, 116a | Cases 102 | 20–30 |
| [ ] | 119b | [E2E-019: flatpak-grid-soft-blocked-disabled](E2E-Tasks/119b-case-103.md) | 180, 116a | Cases 103 | 20–30 |
| [ ] | 285 | [E2E-049: flatpak-grid-child-overlay](E2E-Tasks/285-case-243.md) | 197, 079b, 180, 116a | Cases 243 | 20–30 |
| [ ] | 286 | [E2E-049: flatpak-grid-kiosk](E2E-Tasks/286-case-244.md) | 197k, 079b, 180, 116a | Cases 244 | 20–30 |
| [ ] | 102 | [Compose expiry recovery through kiosk approval](E2E-Tasks/102-replacement.md) | 062, 079a, 065 | FLOW11 | 20–30 |
| [ ] | 103 | [E2E-009: excluded](E2E-Tasks/103-case-23.md) | 102, 079b | Cases 23 | 35–55 (exception) |
| [ ] | 104 | [E2E-009: included](E2E-Tasks/104-case-24.md) | 102, 079b | Cases 24 | 35–55 (exception) |
| [ ] | 123 | [Keep an unsaved match draft across a fixture update](E2E-Tasks/123-catalog-change.md) | 079, 006, 044a, 028 | LIFE04 fixture update; PARENT15 retained-editor save; LIFE01 catalogue refresh | 20–30 |
| [ ] | 124 | [E2E-020: update](E2E-Tasks/124-case-110.md) | 123, 079a, 180 | Cases 110 | 35–55 (exception) |
| [ ] | 123a | [Save a match draft after fixture removal](E2E-Tasks/123a-catalog-removal.md) | 079, 006, 044a, 028 | LIFE04 fixture remove/reinstall; PARENT15 retained-editor save; LIFE01 catalogue refresh | 30–50 (exception) |
| [ ] | 125 | [E2E-020: remove](E2E-Tasks/125-case-111.md) | 123a, 079a, 180 | Cases 111 | 35–55 (exception) |
| [ ] | 126p | [Install the declared offline game fixture](E2E-Tasks/126p-game-fixture.md) | 006, 077a | FIX04 game asset; LIFE04 fixed game installation profile | 20–30 |
| [ ] | 126a | [Launch and observe the prepared offline game](E2E-Tasks/126a-game-activity.md) | 126p, 047 | Game APP01/02/03/04 and FLOW08 usable activity | 20–30 |
| [ ] | 126 | [Compose windowed gameplay through natural expiry](E2E-Tasks/126-game.md) | 126a, 062, 065 | APP05/FLOW10 windowed game | 20–30 |
| [ ] | 127 | [E2E-023: windowed](E2E-Tasks/127-case-126.md) | 126, 102, 079b | Cases 126 | 40–60 (exception) |
| [ ] | 128 | [E2E-024: grant-dominant-windowed](E2E-Tasks/128-case-130.md) | 126, 048b, 079b | Cases 130 | 40–60 (exception) |
| [ ] | 132 | [Compose a daily-dominant profile without clearing the grant](E2E-Tasks/132-time-profiles-dominant.md) | 065 | FLOW13 daily-dominant scope | 20–30 |
| [ ] | 133 | [E2E-024: daily-dominant-windowed](E2E-Tasks/133-case-128.md) | 126, 048b, 079b, 132 | Cases 128 | 40–60 (exception) |
| [ ] | 269 | [E2E-048: daily-dominant-child-overlay](E2E-Tasks/269-case-227.md) | 197, 052c, 132 | Cases 227; gate in brief | 20–30 |
| [ ] | 270 | [E2E-048: daily-dominant-kiosk](E2E-Tasks/270-case-228.md) | 197k, 052c, 132 | Cases 228; gate in brief | 20–30 |
| [ ] | 129 | [Play fullscreen to natural lock](E2E-Tasks/129-game-fullscreen.md) | 126 | APP05/FLOW10 fullscreen play | 20–30 |
| [ ] | 130 | [E2E-023: fullscreen](E2E-Tasks/130-case-127.md) | 102, 079b, 129 | Cases 127 | 40–60 (exception) |
| [ ] | 129a | [Reach an overlay request from fullscreen gameplay](E2E-Tasks/129a-fullscreen-request.md) | 129, 048a | DESK12 fullscreen reveal; overlay/game return | 20–30 |
| [ ] | 134 | [E2E-024: daily-dominant-fullscreen](E2E-Tasks/134-case-129.md) | 048b, 079b, 132, 129a | Cases 129 | 40–60 (exception) |
| [ ] | 131 | [E2E-024: grant-dominant-fullscreen](E2E-Tasks/131-case-131.md) | 048b, 079b, 129a | Cases 131 | 40–60 (exception) |
| [ ] | 289 | [E2E-050: overlay-first-retained](E2E-Tasks/289-case-247.md) | 197, 197k, 196, 079b, 102, 155, 129a, 047a, 028 | Cases 247; gate in brief | 20–30 + ≤90 live (exception) |
| [ ] | 290 | [E2E-050: overlay-first-fresh](E2E-Tasks/290-case-248.md) | 197, 197k, 196, 079b, 102, 155, 129a, 047a, 028 | Cases 248; gate in brief | 20–30 + ≤90 live (exception) |
| [ ] | 291 | [E2E-050: kiosk-first-retained](E2E-Tasks/291-case-249.md) | 197, 197k, 196, 079b, 102, 155, 129a, 047a, 028 | Cases 249; gate in brief | 20–30 + ≤90 live (exception) |
| [ ] | 292 | [E2E-050: kiosk-first-fresh](E2E-Tasks/292-case-250.md) | 197, 197k, 196, 079b, 102, 155, 129a, 047a, 028 | Cases 250; gate in brief | 20–30 + ≤90 live (exception) |
| [ ] | 198 | [Manage from the second parent's own window](E2E-Tasks/198-manage-from-the-second-parent-s-own-window.md) | 044, 079 | FLOW15/FLOW01 other-parent management entry | 20–30 |
| [ ] | 293 | [E2E-051: jordan](E2E-Tasks/293-case-251.md) | 197, 197k, 198, 196, 079b, 079a, 155, 126, 047a | Cases 251; gate in brief | 20–30 + ≤90 live (exception) |
| [ ] | 294 | [E2E-051: riley](E2E-Tasks/294-case-252.md) | 197, 197k, 198, 196, 079b, 079a, 155, 126, 047a | Cases 252; gate in brief | 20–30 + ≤90 live (exception) |
| [ ] | 166a | [Suspend and wake before a grant expires](E2E-Tasks/166a-suspend-active-grant.md) | 052a, 065, 043a, 052c | LIFE03 normal suspend/wake with active grant | 20–30 |
| [ ] | 166 | [Observe time denial after suspend and wake](E2E-Tasks/166-suspend.md) | 052a, 065, 043a, 052c, 166a | LIFE03 | 20–30 |
| [ ] | 167 | [E2E-022: suspend-wake-active](E2E-Tasks/167-case-124.md) | 155, 079b, 079a, 065, 166 | Cases 124 | 40–60 (exception) |
| [ ] | 168 | [E2E-022: suspend-wake-expired](E2E-Tasks/168-case-125.md) | 155, 079b, 079a, 065, 166 | Cases 125 | 40–60 (exception) |
| [ ] | 135a | [Qualify a real update requiring no activation](E2E-Tasks/135a-update-no-action.md) | 028, 044, 007, 079, 048a | LIFE04 update and LIFE05 no-action notice | 20–30 |
| [ ] | 135 | [Follow a real process-activation update](E2E-Tasks/135-activation-process.md) | 028, 044, 007, 079, 048a, 135a | LIFE04 update; LIFE05 process/none scope | 30–50 (exception) |
| [ ] | 136 | [E2E-026: process](E2E-Tasks/136-case-136.md) | 135, 155, 079a, 079b, 065, 052 | Cases 136 | 40–60 (exception) |
| [ ] | 137 | [Follow session activation after a real update](E2E-Tasks/137-activation-session.md) | 044, 007, 079, 048a | LIFE04 update; LIFE05 session scope | 30–50 (exception) |
| [ ] | 138 | [E2E-026: session](E2E-Tasks/138-case-137.md) | 137, 155, 079a, 079b, 065, 052 | Cases 137 | 40–60 (exception) |
| [ ] | 139 | [Follow reboot activation after a real update](E2E-Tasks/139-activation-reboot.md) | 007, 044, 079, 048a | LIFE04 update; LIFE05 reboot scope | 30–50 (exception) |
| [ ] | 140 | [E2E-026: reboot](E2E-Tasks/140-case-138.md) | 139, 155, 079a, 079b, 065, 052 | Cases 138 | 40–60 (exception) |
| [ ] | 141b | [Remove the product and follow its reboot notice](E2E-Tasks/141b-product-remove.md) | 007, 079a, 014 | LIFE04 remove and LIFE05 removal activation | 40–60 (exception) |
| [ ] | 141 | [Reinstall after removal and follow activation](E2E-Tasks/141-product-removal.md) | 007, 079a, 014, 141b | LIFE04 product remove/reinstall; LIFE05 corresponding notices/activation | 30–50 (exception) |
| [ ] | 141a | [Qualify purge and reinstall to visible defaults](E2E-Tasks/141a-product-purge.md) | 141 | LIFE04 purge; LIFE05 notice and reinstall/defaults | 30–50 (exception) |
| [ ] | 142 | [E2E-027: continuous](E2E-Tasks/142-case-139.md) | 141a, 155, 065, 079b | Cases 139 | 20–30 + continuous run (exception) |
| [ ] | 182 | [Prepare a daily balance that outlasts a soft exception](E2E-Tasks/182-prepare-a-daily-balance-that-outlasts-a-soft-exception.md) | 065, 079b, 079a, 052a | FLOW18 | 20–30 |
| [ ] | 206 | [E2E-038: none](E2E-Tasks/206-case-164.md) | 182, 047a | Cases 164 | 20–30 |
| [ ] | 207 | [E2E-038: unlock](E2E-Tasks/207-case-165.md) | 182, 047a | Cases 165 | 20–30 |
| [ ] | 208 | [E2E-038: fresh-login](E2E-Tasks/208-case-166.md) | 182, 047a | Cases 166 | 20–30 |
| [ ] | 209 | [E2E-038: allowance-edit](E2E-Tasks/209-case-167.md) | 182, 047a | Cases 167 | 20–30 |
| [ ] | 210 | [E2E-038: toggle](E2E-Tasks/210-case-168.md) | 182, 047a | Cases 168 | 20–30 |
| [ ] | 211 | [E2E-038: app-save](E2E-Tasks/211-case-169.md) | 182, 047a | Cases 169 | 20–30 |
| [ ] | 212 | [E2E-038: revoke](E2E-Tasks/212-case-170.md) | 182, 047a | Cases 170 | 20–30 |
| [ ] | 184d | [Open Users settings and read its locked state](E2E-Tasks/184d-users-page.md) | 004, 048d, 001s | ACCOUNT01 Settings Users page and account-list observation | 20–30 |
| [ ] | 184a | [Authenticate Users Unlock and observe controls](E2E-Tasks/184a-open-users-settings-and-qualify-its-authentication.md) | 004, 048d, 001s, 184d | AUTH04 Users Unlock; ACCOUNT01 | 20–30 |
| [ ] | 184e | [Fill and cancel the nonsecret add-child wizard](E2E-Tasks/184e-users-add-cancel.md) | 184a, 009 | ACCOUNT02 add-child nonsecret fields and Cancel | 20–30 |
| [ ] | 184 | [Create the registered spare child](E2E-Tasks/184-change-disposable-accounts-through-users-settings.md) | 184a, 009, 184e | ACCOUNT02 add-child; AUTH04 account-creation password fields | 20–30 |
| [ ] | 221 | [E2E-040: add-child](E2E-Tasks/221-case-179.md) | 184, 017, 044a | Cases 179 | 20–30 |
| [ ] | 184b | [Remove a logged-out spare child through Users](E2E-Tasks/184b-remove-disposable-child.md) | 184 | ACCOUNT02 remove-child | 20–30 |
| [ ] | 222 | [E2E-040: remove-selected](E2E-Tasks/222-case-180.md) | 184b, 017, 044a | Cases 180 | 20–30 |
| [ ] | 223 | [E2E-040: remove-last-child](E2E-Tasks/223-case-181.md) | 184b, 017, 044a | Cases 181 | 20–30 |
| [ ] | 225 | [E2E-040: missing-remembered-child](E2E-Tasks/225-case-183.md) | 184b, 014, 180, 044 | Cases 183 | 20–30 |
| [ ] | 184c | [Change a spare approver's role through Users](E2E-Tasks/184c-change-spare-account-role.md) | 184a, 009 | ACCOUNT02 change-role | 20–30 |
| [ ] | 224 | [E2E-040: ineligible-approver](E2E-Tasks/224-case-182.md) | 184c, 155 | Cases 182 | 20–30 |
| [ ] | 169 | [Preserve and qualify system obligation 140: startup enforcement](E2E-Tasks/169-system-140.md) | Baseline | System obligation 140 | 30–60 (exception) |
| [ ] | 170 | [Preserve and qualify system obligation 141: broker startup](E2E-Tasks/170-system-141.md) | Baseline | System obligation 141 | 30–60 (exception) |
| [ ] | 171 | [Preserve and qualify system obligation 142: zero-time exposure](E2E-Tasks/171-system-142.md) | Baseline | System obligation 142 | 30–60 (exception) |
| [ ] | 172 | [Preserve and qualify system obligation 143: usage read](E2E-Tasks/172-system-143.md) | Baseline | System obligation 143 | 30–60 (exception) |
| [ ] | 173 | [Preserve and qualify system obligation 144: kiosk authentication agent](E2E-Tasks/173-system-144.md) | Baseline | System obligation 144 | 30–60 (exception) |
| [ ] | 174 | [Preserve and qualify system obligation 145: failed save](E2E-Tasks/174-system-145.md) | Baseline | System obligation 145 | 30–60 (exception) |
| [ ] | 175 | [Preserve and qualify system obligation 146: stale identity](E2E-Tasks/175-system-146.md) | Baseline | System obligation 146 | 30–60 (exception) |
| [ ] | 176 | [Preserve and qualify system obligation 147: disconnect](E2E-Tasks/176-system-147.md) | Baseline | System obligation 147 | 30–60 (exception) |
| [ ] | 177 | [Preserve and qualify system obligation 148: concurrent transaction](E2E-Tasks/177-system-148.md) | Baseline | System obligation 148 | 30–60 (exception) |
| [ ] | 178 | [Preserve and qualify system obligation 149: policy reload](E2E-Tasks/178-system-149.md) | Baseline | System obligation 149 | 30–60 (exception) |
| [ ] | 179 | [Preserve and qualify system obligation 150: partial termination](E2E-Tasks/179-system-150.md) | Baseline | System obligation 150 | 30–60 (exception) |
| [ ] | 150a | [Prepare the reviewed feedback submission profile](E2E-Tasks/150a-feedback-profile.md) | 038, 031a, 030, 052c | Concrete synthetic reports, recipient and authorization scope for FEED11 consumers | 20–30 |
| [ ] | 150 | [Submit one authorized synthetic report and read success](E2E-Tasks/150-feedback-send.md) | 150a | FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief | 20–30 |
| [ ] | 151 | [E2E-032: success](E2E-Tasks/151-case-156.md) | 150 | Cases 156; gate in brief | 35–55 (exception) |
| [ ] | 256 | [E2E-047: no-reply](E2E-Tasks/256-case-214.md) | 150 | Cases 214; gate in brief | 20–30 |
| [ ] | 152 | [Change connectivity through public network controls](E2E-Tasks/152-network.md) | 150, 193 | FEED09 Parent retry/recovery over qualified LIFE06; gate in brief | 20–30 |
| [ ] | 153 | [E2E-033: retry](E2E-Tasks/153-case-157.md) | 152 | Cases 157; gate in brief | 35–55 (exception) |
| [ ] | 257 | [E2E-047: background](E2E-Tasks/257-case-215.md) | 152 | Cases 215; gate in brief | 20–30 |
| [ ] | 258 | [E2E-047: app-exit](E2E-Tasks/258-case-216.md) | 152, 030a | Cases 216; gate in brief | 20–30 |
| [ ] | 259 | [E2E-047: retry-expired](E2E-Tasks/259-case-217.md) | 152 | Cases 217; gate in brief | 35–60 incl. retry (exception) |
| [ ] | 150p | [Send an authorized Parent error report](E2E-Tasks/150p-parent-error-send.md) | 150, 186 | FEED11, FEED09 success and FEED14 Parent error-report; gate in brief | 20–30 |
| [ ] | 264 | [E2E-047: parent-error-success](E2E-Tasks/264-case-222.md) | 150p | Cases 222; gate in brief | 20–30 |
| [ ] | 295 | [Validate the manually prepared Lunar VM profile](E2E-Tasks/295-lunar-preparation.md) | 006, 036 | FIX05; restored Lunar/AppImageLauncher/autostart/Minecraft prerequisites only. Blocker: profile and repeatable setup unqualified; resume when the manual assets and standard restore path are available. | 20–30 |
| [ ] | 296c | [Launch Lunar and Quit through its normal controls](E2E-Tasks/296c-lunar-launch-quit.md) | 295, 079a, 052c | APP01/02/03/UI18 Lunar original-AppImage usable launch and Quit | 20–30 |
| [ ] | 296d | [Close Lunar to its tray and restore it](E2E-Tasks/296d-lunar-tray.md) | 296c | APP06 Lunar/tray snapshot and close-to-tray/restore | 20–30 |
| [ ] | 296 | [Observe Lunar command denial](E2E-Tasks/296-lunar-provider.md) | 295, 079a, 052c, 296d | APP06 snapshot and APP01/02/03/UI18 Lunar launch, tray and Quit bindings | 20–30 |
| [ ] | 296e | [Launch Minecraft to its menu and exit normally](E2E-Tasks/296e-minecraft-entry-exit.md) | 296 | APP01/02/UI18 Lunar-to-Minecraft entry and return | 20–30 |
| [ ] | 296a | [Play the prepared Minecraft local world](E2E-Tasks/296a-minecraft-provider.md) | 296, 296e | APP01/02/03 and UI18 Minecraft local-world binding | 20–30 |
| [ ] | 296f | [Observe allowed Lunar autostart across login](E2E-Tasks/296f-lunar-autostart-positive.md) | 296a, 007, 016a, 004, 052c, 180 | APP06/UI22 allowed continuous login interval | 40–60 (exception) |
| [ ] | 296b | [Prove the denied Lunar login interval](E2E-Tasks/296b-lunar-login-observer.md) | 296a, 007, 016a, 004, 052c, 180, 296f | APP06/UI22 continuous login interval and Lunar autostart binding | 40–60 (exception) |
| [ ] | 297 | [E2E-052: appimagelauncher-login-autostart](E2E-Tasks/297-case-253.md) | 296b, 180, 197 | Cases 253; pending metadata only. Blocker: complete public journey unimplemented; resume when required blocks are qualified. | 20–30 + ≤30 live (exception) |
| [ ] | 183a | [Lock during pending overlay approval](E2E-Tasks/183a-lock-during-pending-overlay-approval.md) | 048b, 044, 052c | FLOW17 overlay lock; gate in brief | 20–30 |
| [ ] | 213 | [E2E-039: overlay-lock](E2E-Tasks/213-case-171.md) | 183a, 180, 079b, 079a | Cases 171; gate in brief | 20–30 |
| [ ] | 183b | [Switch User during pending overlay approval](E2E-Tasks/183b-switch-user-during-pending-overlay-approval.md) | 048b, 044, 052c | FLOW17 overlay Switch User; gate in brief | 20–30 |
| [ ] | 214 | [E2E-039: overlay-switch](E2E-Tasks/214-case-172.md) | 183b, 180, 079b, 079a | Cases 172; gate in brief | 20–30 |
| [ ] | 183c | [Sign out during pending overlay approval](E2E-Tasks/183c-sign-out-during-pending-overlay-approval.md) | 048b, 044, 052c | FLOW17 overlay sign-out; gate in brief | 20–30 |
| [ ] | 215 | [E2E-039: overlay-signout](E2E-Tasks/215-case-173.md) | 183c, 180, 079b, 079a | Cases 173; gate in brief | 20–30 |
| [ ] | 183d | [Close the overlay during pending approval](E2E-Tasks/183d-close-the-overlay-during-pending-approval.md) | 048b, 044, 028, 052c | FLOW17 overlay app-close; gate in brief | 20–30 |
| [ ] | 216 | [E2E-039: overlay-close](E2E-Tasks/216-case-174.md) | 183d, 180, 079b, 079a | Cases 174; gate in brief | 20–30 |
| [ ] | 183e | [Close the station during pending approval](E2E-Tasks/183e-close-the-station-during-pending-approval.md) | 020, 014, 180, 044, 052c | FLOW17 kiosk app-close; gate in brief | 20–30 |
| [ ] | 217 | [E2E-039: kiosk-close](E2E-Tasks/217-case-175.md) | 183e, 079b, 079a, 021 | Cases 175; gate in brief | 20–30 |
| [ ] | 187a | [Observe and decline a overlay cooldown error](E2E-Tasks/187a-overlay-cooldown-error.md) | 048b, 044, 052c, 030 | REQUEST09 overlay cooldown and FEED15 decline branch; gate in brief | 20–30 |
| [ ] | 187o | [Review an overlay cooldown report](E2E-Tasks/187o-read-overlay-cooldown-errors-and-report-choices.md) | 048b, 044, 052c, 030, 187a | REQUEST09 cooldown and FEED15 overlay; gate in brief | 20–30 |
| [ ] | 218 | [E2E-039: overlay-cooldown](E2E-Tasks/218-case-176.md) | 187o, 180, 079b, 079a | Cases 176; gate in brief | 20–30 |
| [ ] | 248 | [E2E-045: child-overlay](E2E-Tasks/248-case-206.md) | 187o, 180 | Cases 206; gate in brief | 20–30 |
| [ ] | 150o | [Send an authorized overlay error report](E2E-Tasks/150o-send-an-authorized-overlay-error-report.md) | 150, 187o | FEED11, FEED09 success and FEED14 overlay; gate in brief | 20–30 |
| [ ] | 262 | [E2E-047: overlay-success](E2E-Tasks/262-case-220.md) | 150o | Cases 220; gate in brief | 20–30 |
| [ ] | 187b | [Observe and decline a kiosk cooldown error](E2E-Tasks/187b-kiosk-cooldown-error.md) | 021, 044, 052c, 030 | REQUEST09 kiosk cooldown and FEED15 decline branch; gate in brief | 20–30 |
| [ ] | 187k | [Review a kiosk cooldown report](E2E-Tasks/187k-read-station-cooldown-errors-and-report-choices.md) | 021, 044, 052c, 030, 187b | REQUEST09 cooldown and FEED15 kiosk; gate in brief | 20–30 |
| [ ] | 219 | [E2E-039: kiosk-cooldown-same](E2E-Tasks/219-case-177.md) | 187k, 180, 079b, 079a | Cases 177; gate in brief | 20–30 |
| [ ] | 220 | [E2E-039: kiosk-cooldown-other](E2E-Tasks/220-case-178.md) | 187k, 180, 079b, 079a, 024a | Cases 178; gate in brief | 20–30 |
| [ ] | 249 | [E2E-045: kiosk](E2E-Tasks/249-case-207.md) | 187k, 180 | Cases 207; gate in brief | 20–30 |
| [ ] | 150k | [Send an authorized kiosk error report](E2E-Tasks/150k-send-an-authorized-kiosk-error-report.md) | 150, 187k | FEED11, FEED09 success and FEED14 kiosk; gate in brief | 20–30 |
| [ ] | 263 | [E2E-047: kiosk-success](E2E-Tasks/263-case-221.md) | 150k | Cases 221; gate in brief | 20–30 |
| [ ] | 188p | [Observe failed Parent diagnostic collection](E2E-Tasks/188p-retry-failed-parent-diagnostic-collection.md) | 031a | FEED09 Parent collection failure and usable controls; gate in brief | 20–30 |
| [ ] | 189p | [Send a Parent report without unavailable logs](E2E-Tasks/189p-send-a-parent-report-without-unavailable-logs.md) | 188p, 150 | FEED11 without-logs and FEED09/14 Parent result; gate in brief | 20–30 |
| [ ] | 251 | [E2E-046: parent-without-logs](E2E-Tasks/251-case-209.md) | 189p | Cases 209; gate in brief | 20–30 |
| [ ] | 188r | [Retry failed Parent diagnostic collection](E2E-Tasks/188r-parent-collection-retry.md) | 188p | FEED16 Parent collection recovery; gate in brief | 20–30 |
| [ ] | 250 | [E2E-046: parent-retry](E2E-Tasks/250-case-208.md) | 188r | Cases 208; gate in brief | 20–30 |
| [ ] | 188o | [Observe failed overlay diagnostic collection](E2E-Tasks/188o-retry-failed-overlay-diagnostic-collection.md) | 187o, 031a | FEED09 overlay collection failure and usable controls; gate in brief | 20–30 |
| [ ] | 189o | [Send an overlay report without unavailable logs](E2E-Tasks/189o-send-a-overlay-report-without-unavailable-logs.md) | 188o, 150 | FEED11 without-logs and FEED09/14 overlay result; gate in brief | 20–30 |
| [ ] | 253 | [E2E-046: child-overlay-without-logs](E2E-Tasks/253-case-211.md) | 189o | Cases 211; gate in brief | 20–30 |
| [ ] | 188s | [Retry failed overlay diagnostic collection](E2E-Tasks/188s-overlay-collection-retry.md) | 188o | FEED16 overlay collection recovery; gate in brief | 20–30 |
| [ ] | 252 | [E2E-046: child-overlay-retry](E2E-Tasks/252-case-210.md) | 188s | Cases 210; gate in brief | 20–30 |
| [ ] | 188k | [Observe failed kiosk diagnostic collection](E2E-Tasks/188k-retry-failed-kiosk-diagnostic-collection.md) | 187k, 031a | FEED09 kiosk collection failure and usable controls; gate in brief | 20–30 |
| [ ] | 189k | [Send a kiosk report without unavailable logs](E2E-Tasks/189k-send-a-kiosk-report-without-unavailable-logs.md) | 188k, 150 | FEED11 without-logs and FEED09/14 kiosk result; gate in brief | 20–30 |
| [ ] | 255 | [E2E-046: kiosk-without-logs](E2E-Tasks/255-case-213.md) | 189k | Cases 213; gate in brief | 20–30 |
| [ ] | 188t | [Retry failed kiosk diagnostic collection](E2E-Tasks/188t-kiosk-collection-retry.md) | 188k | FEED16 kiosk collection recovery; gate in brief | 20–30 |
| [ ] | 254 | [E2E-046: kiosk-retry](E2E-Tasks/254-case-212.md) | 188t | Cases 212; gate in brief | 20–30 |
| [ ] | 190a | [Keep a sending overlay report open after Close](E2E-Tasks/190a-overlay-sending-stay.md) | 150o, 152 | FEED09 retry and FEED17/18 overlay stay-open branch; gate in brief | 20–30 |
| [ ] | 190o | [Stop a sending overlay report](E2E-Tasks/190o-confirm-stopping-a-sending-overlay-report.md) | 150o, 152, 190a | FEED09 retry and FEED17/18 overlay; gate in brief | 20–30 |
| [ ] | 260 | [E2E-047: overlay-stop](E2E-Tasks/260-case-218.md) | 190o | Cases 218; gate in brief | 20–30 |
| [ ] | 190b | [Keep a sending kiosk report open after Close](E2E-Tasks/190b-kiosk-sending-stay.md) | 150k, 152 | FEED09 retry and FEED17/18 kiosk stay-open branch; gate in brief | 20–30 |
| [ ] | 190k | [Stop a sending kiosk report](E2E-Tasks/190k-confirm-stopping-a-sending-kiosk-report.md) | 150k, 152, 190b | FEED09 retry and FEED17/18 kiosk; gate in brief | 20–30 |
| [ ] | 261 | [E2E-047: kiosk-stop](E2E-Tasks/261-case-219.md) | 190k | Cases 219; gate in brief | 20–30 |
| [ ] | 143 | [Qualify distinct retained desktops for one child](E2E-Tasks/143-multi-desktop.md) | 047a, 079a, 050, 048b | FLOW14 same-child multi-desktop scope; gate in brief | 20–30 |
| [ ] | 144 | [E2E-007: zero-multiple](E2E-Tasks/144-case-18.md) | 079b, 065, 143 | Cases 18; gate in brief | 40–60 (exception) |
| [ ] | 145 | [E2E-007: remaining-multiple](E2E-Tasks/145-case-20.md) | 079b, 065, 143 | Cases 20; gate in brief | 40–60 (exception) |
| [ ] | 146 | [E2E-021: save](E2E-Tasks/146-case-112.md) | 143, 079b, 065 | Cases 112; gate in brief | 40–60 (exception) |
| [ ] | 147 | [E2E-021: approve-without-soft](E2E-Tasks/147-case-113.md) | 143, 079b, 065 | Cases 113; gate in brief | 40–60 (exception) |
| [ ] | 148 | [E2E-021: approve-with-soft](E2E-Tasks/148-case-114.md) | 143, 079b, 065 | Cases 114; gate in brief | 40–60 (exception) |
| [ ] | 149 | [E2E-021: revoke](E2E-Tasks/149-case-115.md) | 143, 079b, 065 | Cases 115; gate in brief | 40–60 (exception) |
| [ ] | 191a | [Read the Shell calendar and clock](E2E-Tasks/191a-calendar-provider.md) | 003d, 044a, 052c | TIME05 Shell calendar and DESK12 clock binding | 20–30 |
| [ ] | 191 | [Read timezone and compose local calendar observations](E2E-Tasks/191-read-local-calendar-and-timezone.md) | 191a, 001s | TIME05 Settings Date & Time binding and composed calendar observation | 20–30 |
| [ ] | 238 | [E2E-044: ordinary-daily-reset](E2E-Tasks/238-case-196.md) | 191, 065, 062 | Cases 196; gate in brief | Scheduled window; ≤60 (exception) |
| [ ] | 239 | [E2E-044: ordinary-rest-of-day](E2E-Tasks/239-case-197.md) | 191, 065, 062 | Cases 197; gate in brief | Scheduled window; ≤60 (exception) |
| [ ] | 240 | [E2E-044: ordinary-fixed-grant](E2E-Tasks/240-case-198.md) | 191, 065, 062 | Cases 198; gate in brief | Scheduled window; ≤60 (exception) |
| [ ] | 241 | [E2E-044: spring-forward-daily-reset](E2E-Tasks/241-case-199.md) | 191, 065, 062 | Cases 199; gate in brief | Scheduled window; ≤60 (exception) |
| [ ] | 242 | [E2E-044: spring-forward-rest-of-day](E2E-Tasks/242-case-200.md) | 191, 065, 062 | Cases 200; gate in brief | Scheduled window; ≤60 (exception) |
| [ ] | 243 | [E2E-044: spring-forward-fixed-grant](E2E-Tasks/243-case-201.md) | 191, 065, 062 | Cases 201; gate in brief | Scheduled window; ≤60 (exception) |
| [ ] | 244 | [E2E-044: fall-back-daily-reset](E2E-Tasks/244-case-202.md) | 191, 065, 062 | Cases 202; gate in brief | Scheduled window; ≤60 (exception) |
| [ ] | 245 | [E2E-044: fall-back-rest-of-day](E2E-Tasks/245-case-203.md) | 191, 065, 062 | Cases 203; gate in brief | Scheduled window; ≤60 (exception) |
| [ ] | 246 | [E2E-044: fall-back-fixed-grant](E2E-Tasks/246-case-204.md) | 191, 065, 062 | Cases 204; gate in brief | Scheduled window; ≤60 (exception) |

## Deferred future work

This row has no current-release consumer and does not prevent active completion.

| Done | ID | Task | Requires tasks | Delivered scope | Minutes |
| --- | --- | --- | --- | --- | --- |
| [ ] | 154 | [Deferred qualification of restored mute](E2E-Tasks/154-mute.md) | 048a | Deferred future public mute; outside current-release completion; gate in brief | 20–40 |
