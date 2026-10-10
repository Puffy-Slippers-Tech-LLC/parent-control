# UI and installed E2E coverage

The `ui` category owns representative functional behavior and meaningful local
validation boundaries that can be established in a component preview without
executing product backend logic. Both layers follow the
[result-oriented UI mandate](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope).
Installed E2E verifies realistic customer journeys and meaningful outcomes,
including persistence, authorization, enforcement, lifecycle and operating-system
integration. UI interactions serve those journeys. An installed copy of a widget
check is not required merely because the component is packaged. A preview pass
alone does not establish installed customer outcomes.

Allocate individual assertions, not whole features. Remove incidental GUI
assertions rather than moving them to another suite. For retained functional
assertions, move coverage only after its new owner is executable.
Pending UI obligations below stay with their named component owner and existing
task, using [UI acceptance](E2E-Execution-Contracts.md#ui-acceptance) when the row
is explicitly reallocated. They confer no E2E acceptance credit and do not make
unrelated widget coverage a prerequisite of a customer journey.

For each completed or planned case, first identify the customer's goal and the
distinct results that prove it. Retain the minimum reliable UI operations to
reach and observe those results. Repeated unchanged reads, dialog tours, focus
or caret checkpoints and independent control combinations do not become useful
E2E coverage through their inclusion in a historical case. Preserve intermediate
checks that protect separate outcomes, such as no premature access, the correct
child's policy, retained work, or a cancelled submission. Shared ownership and
input guards remain mandatory automation mechanics.

## Duplicate review and allocation

| Cases / area | Local functional owner | Installed E2E scope |
| --- | --- | --- |
| 152, feedback formatting | `test_parent_feedback.py`: all block and inline formats, links, clear/reapply, undo/redo, Unicode and retained draft | Type text, bold one selection, append an emoji; retain reply, one real attachment, return from a directly launched supporting window, dialog preservation and app-exit reset. This does not activate a product link. |
| 153, feedback validation | `test_parent_feedback.py` and `test_e2e_accessible_adapter.py`: local states, 5000/5001 ASCII and emoji, hidden characters, excessive formatting, rejected-send preservation | Reject one empty send, edit body/reply, reopen and observe recovery; never send valid feedback |
| 154, attachments | `test_parent_feedback.py`: chooser Cancel preservation, count, individual/total size, filename and atomic-rejection boundaries; real file reads and frozen attachment snapshot after source mutation | Prepare a report with two real files, remove the unwanted attachment and retain the intended file; use the shortest real chooser handoff |
| 158–159, daily allowance | `test_preview_smoke.py` and `test_control_overflow.py`: representative presets through shared Application UI API value selection and saved-value readback, custom boundaries, distinct commit paths and local window behavior; no popup, caret or focus acceptance | 158: preset 15 then custom 1; retain that final allowance through child switching, saved-value reload and restart. 159: last-change-wins rapid saves and independent child values after restart; no repeated launch/window-count exercise |
| 38–43, request forms | `test_request_form_component.py` owns local duration validation; the complete preset/custom matrix on both surfaces remains uncompleted and carries no acceptance credit from the removed gesture tasks | Cases excluded from scheduling by the [unsupported native-gesture rule](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures). Preserve their duration, authorization, duplicate-submission and rest-of-day assertions as uncovered; do not recreate gesture tasks. Other ordinary request/approval cases continue independently. |
| 184, application search/filter | `test_preview_smoke.py::test_catalogue_query_and_representative_filter_results`: name, description, identifier, empty and no-match queries; each match/access category, empty filters and two combined predicates sampled separately; exact rows and no policy writes | One exact-name search, one combined precise/Allowed filter, then clear against the real catalogue |
| 185–186, application matching | `test_preview_smoke.py::test_match_editor_valid_save_cancel_matrix`: precise/wildcard and absolute/basename Save and Cancel through shared blocks; `test_match_editor_invalid_drafts_cancel_or_reset`: invalid drafts paired with precise/Cancel or wildcard/Reset, exact explanations, retained drafts, unchanged Cancel and immediate default save | Real saved custom rule, representative local refusal and immediate Reset, cross-directory broker rejection, reopen/restart persistence and actual launch/enforcement |
| Application access choices, PARENT16 | `test_preview_smoke.py::test_app_access_choices_save_and_independent_readback`: all three choices, unchanged Allowed without another save, wrong-row/modal refusal and independent entry through the shared access composite | Native fixture A's Allowed/Hard/Soft autosaves and exact public row readback; actual enforcement and full match/access composition stay with their separate tasks |
| 151, 190–193, Help/About | `test_about_release.py`, `test_preview_smoke.py`, `test_e2e_accessible_adapter.py`, `test_request_form_component.py::test_overlay_about_license_shared_reader_and_unchanged_form` own control/link availability; 185p/185o retain their historical qualification | 151 identifies the installed product and resumes management; 191–193 retain unfinished requests, kiosk restrictions and installed command manuals. Link-only case 190 is reallocated to UI and excluded from E2E scheduling; no duplicate of 151. No link invocation, URI/destination inspection or external handlers |
| 205; 176/178, error reporting | `test_error_feedback.py`: local presentation and report callback permutations; `test_preview_smoke.py::test_rejected_parent_rule_report_review_and_confirmed_policy`: confirmed precise/wildcard restoration, automatic report, synthetic draft, Privacy and normal closure through shared blocks | Complete case 205 and request-surface error routing, review/decline and exits within cooldown cases 176/178; former 206/207 absorbed |
| 155–157, 208, 213, 216, 218–221, diagnostics/transport | Local presentation is UI; existing feedback UI tests cover callback success/failure states | Preserve actual collection, cancellation, service/network failures, sanitization and transport/lifetime checks; these execute different code from a stubbed preview. Former 214's ordinary no-reply send is owned by 156 below. |
| Scaling and automation identity | Representative scaled product operations and shared identity/input-safety qualification; no geometry, alignment, CSS, glyph-run or widget-order acceptance | No repeated layout or scale matrix in E2E |
| Observer traces and input safety | Trace/token, ownership, ambiguity and uncertain-input checks qualify the shared harness; they are not customer typing or popup acceptance | Customer cases use final public results; no feedback trace sampling or per-keystroke checks |
| 27–29, 22, 118/120, countdown and panel preferences | `test_child_shell_lifecycle.py` and its nested-Shell fixture own local panel text, tooltip and menu behavior. Tasks 052b and 181h retain pending UI obligations; they supply no installed result. | Use accurate remaining time to continue work until natural exhaustion; case 22 verifies locking with animation enabled. Cases 118/120 preserve different saved choices for both children after sign-out/return and reboot without changing time limits or app access. No separate preference journey, tooltip gesture, visibility tour, menu-toggle matrix or standalone tick-format acceptance |
| 161, zero-total Revoke availability | `test_preview_smoke.py::test_parent_zero_balance_keeps_revoke_unavailable_with_limits_on_and_off` owns Revoke disabled with zero total for limits on and off. | No standalone customer journey: stable case 161 is excluded from E2E scheduling, pending with no executable. Its completed task remains historical; daily-only revocation case 160 retains its distinct product result. |
| Personal language settings | `test_language_settings.py`: representative languages paired with Parent, overlay and kiosk for first-run/session defaults, saved startup, Save/Cancel, read/save failure and retry, accessible labels and dynamic errors; Parent Hebrew logical text and saved language. Parent, request and feedback preservation sample Latin, CJK, RTL and complex-script changes; `tests/unit/test_localization.py` owns exhaustive catalogue/message checks. `test_child_shell_lifecycle.py` samples English, Hebrew and Tamil through overlay-to-panel refresh. Selected-child desktop defaults and restart notices have component coverage; agent preparation is a transport double, not native approval evidence. Search checks matching choices and translated results, without focus traversal. | Tasks 300 and 306–310 follow the [acceptance mapping](E2E-Scenario-Recipes.md#personal-language-acceptance-decomposition): Chinese latest-install/reboot/two native approvals; account/offline persistence; Parent, overlay and kiosk Hebrew logical text/dialogs; panel refresh/countdown/natural expiry. Each missing surface/result binding has a bounded prerequisite. Chinese assets remain in prepare-vm and desktop language in DESK13. Actual native text is required on both Chinese approvals; Hebrew requires qualified public logical text and preserved function on each surface. No installed acceptance is claimed by this allocation. |

Task [312](E2E-Tasks/312-child-reminder-preferences.md) keeps one saved-reminder
journey: custom text creation/edit/save and exact station readback, one Cancel,
empty-list save, then one reboot with both request screens and the other child's
unchanged reminders and language. Local editing details belong to
`test_language_settings.py::test_child_preferences_reminders_sort_edit_save_cancel_and_empty_list`
and `test_language_settings.py::test_reminder_creation_validation_and_candidate_translation`.
These cover default ordering, edited literal text and trigger description,
Save/Cancel/empty-list behavior on both surfaces, minute/second duplicate refusal
and German candidate descriptions. Post-edit ordering, no synthetic custom
preset, and German descriptions alongside unchanged literal custom text/request
choices remain pending local assertions; this allocation claims no new test pass.
These details need no additional two-child journey or restart. Actual countdown
warning delivery remains with [task 311](E2E-Tasks/311-remaining-time-notifications.md).

The [installed reminder qualification slices](E2E-Building-Blocks.md#reminder-controls-and-notification-qualification)
312a/312b and 311a–311c precede those complete cases. They reuse the same public
editing and observation helpers; the local matrices above remain with UI tests.
Neither capability qualification nor a saved fullscreen boolean supplies
complete warning-delivery, persistence or customer-case acceptance.

Parent's inherited About/feedback matrix is owned by
`test_language_settings.py::test_parent_dialog_inherited_text_and_retained_hebrew_draft`:
English → Hebrew → English, one visit per dialog/language, public logical text
and the exact retained mixed-script body/reply. It executes shared installed
dialog operations. Task 307b's historical qualification included additional
visits and keyboard traversal; current consumers require the functional results.
Task 307 owns the complete policy/history assertions.

The attachment UI fixture substitutes only the external chooser's returned file
list. The real frontend reads the files, validates them and updates the dialog.
The installed case remains responsible for the actual chooser handoff. The full
matrix must not be restored to the installed case as a substitute for UI coverage.

## Complete scenario-family review

The following review covers each catalogue family, including registered and
pending variants, plus the future language recipes above. It changes acceptance
scope and composition, not historical run results. Stable case IDs, executable
bindings, pending gates and the native-gesture exclusion remain in the inventory.
Shared UI tests own local input/control/translation matrices; public identity,
readiness and secret guards still constrain every needed input. Navigation may
use the shortest qualified shared route that reaches the declared customer
action and independent result. A completed supporting action is not itself a
customer outcome.

The retained implementations apply the same allocation. Case 193 reads four
command results with one final desktop observation. Retained Parent/child
qualification compares the original Parent window, policy and session directly;
it needs no unrelated license-viewer launch or foreground-switch tour. The
explicit feedback supporting-window handoff retains its separate draft result.
Case 255 proves a working network path before isolation, requires every fixed
probe blocked while offline, and restores every path known to work beforehand.
Availability of every external DNS endpoint is a network-harness qualification,
not a language-setting result. These shortened compositions require their own
live validation; earlier reports remain historical evidence of their old scope.
Cases 44–46 compare the original activity once immediately before resuming it.
Cases 54/55 read the unavailable form once, then cancel to the greeter.
Station restriction routes run once per case: before successful approval ends
the station, or after rejection/cancellation preserves the prepared form.
The original-work comparison, each forbidden route and the distinct request
outcomes remain required; consecutive unchanged reads and repeated route sweeps
add no customer result. Case 152's wrong-entry exercise stays in isolated
qualification. Each changed composition needs scoped live validation.

Remaining suspend tasks consume the grant-only preparation needed by their
zero-daily boundary, without a combined-profile qualification. The
[sending recipes](E2E-Scenario-Recipes.md#sending-background-completion-and-report-exits)
reuse unchanged Privacy evidence while retaining a current draft review and
each submission, recovery and exit result. Future overlay task 308 approves
during Hebrew before restoring English; its saved-work and language history
remain complete. Reminder task 311a qualifies one nondefault Save and one Cancel;
311c retains both fullscreen choices and their actual banner effects. These
reductions leave natural waits, identity guards and all distinct customer
outcomes under their existing owners.

| Family / cases | Customer result and review disposition |
| --- | --- |
| E2E-001 / 1 | Retain runner-smoke transport/credential/continuity qualification; explicitly no customer acceptance. |
| E2E-002 / 2 | Retain install/restart → usable Parent and request station with fresh choices. Package internals remain system qualification. |
| E2E-003 / 3–4 | Retain finding the installed app and discovering a newly added child while Parent is open, or explaining no eligible child. Page visits only reach required settings. |
| E2E-004 / 5–6 | Retain real standard-account management exclusion on discovery and direct launch; no general terminal/website exercise. |
| E2E-005 / 7–12 | Simplify allowance edits to positive/zero access boundaries and enable/disable. Preserve original grant deadlines and independent app blocks; local value permutations stay UI. |
| E2E-006 / 13–16 | Retain six distinct app-rule transition outcomes with matching/nonmatching and other-user work. Each transition changes enforcement; control/match variants remain substantive. |
| E2E-007 / 17–20 | Retain cancelled/confirmed revocation, remaining-daily versus zero-time access and retained work/isolation. Distinct-desktop gate remains. |
| E2E-008 / 22 | One journey retains natural daily exhaustion, lock input ownership, correct-password retained-unlock denial, approved usable recovery, normal logout, revocation with D=G=0 and correct-password fresh sign-in denial. Separate case 21 is removed and its ID reserved; each intermediate result remains mandatory. |
| E2E-009 / 23–24 | Retain unfinished work recovery after natural lock; replacement soft choice determines preservation/closure. |
| E2E-010 / 25–26 | Retain another user's actual foreground work while child grant expires, then child denial and unaffected retained work. |
| E2E-011 / 27–29 | Rewrite around using time information, resuming work without a reset and reaching the predicted natural lock. Tooltip and surface-visibility matrix move to child UI. |
| E2E-012 / 30, 33 | Retain first parent with apps excluded and second parent with apps included: one panel entry to a fixed-child request, selected-parent real approval and app/time result. Remove opposite combinations 31 and 32 without reusing their IDs. Both parents also remain in E2E-049 temporary-app journeys. Repeated-entry singleton checks move to child UI; later approval must authenticate anew. |
| E2E-013 / 34, 36 | One recovery journey per request surface: wrong password, separate cancelled request, then fresh successful approval. Check no extra time, unchanged app restrictions and remembered choices after each failure. Former Cancel-only cases 35/37 are absorbed; IDs are not reused. |
| E2E-014 / 38–43 | Preserve excluded duplicate-gesture cases and IDs without acceptance credit. Local duration boundaries belong UI; any future approval arithmetic requires real access outcomes. |
| E2E-015 / 44–49 | Retain returning to the same underlying work or sign-in after Cancel/Escape/approved exit, with actual usable time after approval. |
| E2E-016 / 50–52 | Retain the request-only station across approval/denial/cancellation and normal return; forbidden general-desktop routes are meaningful restriction results. |
| E2E-017 / 53–57 | Retain selected-child settings and matching selected-parent prompt, or actionable unavailable-request explanations. Selector opening/collapse is navigation only. |
| E2E-018 / 58–61 | Retain per-child shared duration/soft choices and surface-local parent choices. Remove mute-control absence from E2E acceptance; current UI and future mute obligations remain separate. |
| E2E-019 / retained cases in [recipe](E2E-Scenario-Recipes.md#e2e-019) | Retain every launch route under all three rules with limits on; with limits off, retain ordinary, Snap and Flatpak command launches under all three rules. Remove the repeated menu, shortcut and Files combinations with limits off. Actual use versus refusal and another child's unaffected access remain required; hidden launcher alone is insufficient. Removed case IDs must not be reused. |
| E2E-020 / 110–111 | Retain applying a saved rule to an updated app and after reinstalling a disappeared app. Refresh is navigation to actual policy/launch results. |
| E2E-021 / 112–115 | Retain affected work and launches on distinct retained desktops; no invented session or repeated-resume substitute. |
| E2E-022 / 116–122, 124–125 | Retain original grant deadlines and legitimate access before and after expiry for each lifecycle boundary. Active cases 116/118/120/124 own full saved-choice tours on both forms; expired partners omit the repeat but retain saved rules, refusal, enforcement and recovery. Case 122 uses one short grant for early idle return, natural expiry, refusal and approved recovery. Compare old work only on retained desktops; future mute remains separate. |
| E2E-023 / 126–127 | Retain denied entry → station approval → real game → natural lock → replacement and same game. Display mode matters to real input ownership at lock. |
| E2E-024 / 128, 131 | Retain daily-dominant windowed play and grant-dominant fullscreen play: both time calculations, both game modes, fullscreen request access, unchanged game progress and the same game continuing until extended natural expiry. Remove opposite pairings 129 and 130 without reusing their IDs. REQUEST13's panel API entry remains the tested route; no Shell reveal sequence is required. |
| E2E-025 / 132–135 | Retain replacement soft choice before returning with daily time left; fresh launches versus preserved retained work follow the declared session lifetime. |
| E2E-026 / 136–138 | Retain each actual earlier-release update and its instructions for every affected user/surface, preserved allowance/app rules and usable/enforced access without restarting the grant. Reboot case 138 owns the full both-form saved-choice tour; process/session cases 136/137 shorten only repeated preference checks. |
| E2E-027 / 139 | Retain continuous remove/reinstall/reapply/purge history with personal access restored, choices retained or reset and no recreated grant. |
| E2E-028–029 / 140–149 | Retired customer families remain displaced engineering obligations under the existing reconciliation owner; no new E2E credit. |
| E2E-030 / 151 | Identify installed product/version/license and return to the same policy. Link clickability belongs to shared UI; external license opening is outside the [link acceptance contract](../Mandates/UI-Automation-Mandate.MD#product-integrations). |
| E2E-031 / 152–155 | Rewrite as retaining authored reports, recovering from refused empty submission, choosing intended real attachment and saving readable diagnostics after failure. Formatting/boundary/chooser matrices remain UI. |
| E2E-032 / 156 | Retain authorized reviewed Send → actual service acceptance → cleared draft. Pending widget state is guarding/UI; no email-delivery claim. |
| E2E-033 / 157 | One ordinary report waits offline; close only feedback, reconnect with the same Parent running, require no unsolicited feedback/thanks window and reopen to verify automatic completion and an empty draft without a second Send. Absorbs former E2E-047 / 215. E2E-032 / 156 retains visible confirmation. Remove incidental pending-control assertions. |
| E2E-034 / 150 | Retired transport obligation remains engineering/harness-owned, with canonical smoke in case 1 and no customer credit. |
| E2E-035 / 158–159 | Rewrite preset/custom acceptance around saved value after restart; retain rapid-save ordering and independent children. Local rejection and repeated-launch singleton checks move to UI. |
| E2E-036 / 160–161 | Retain case 160 daily-only revocation restoring restrictions. Reallocate pure zero-total action availability in case 161 to Parent UI, keeping its stable ID pending/excluded without an E2E executable. |
| Former E2E-037 / 162–163 | Standalone cases/tasks removed; IDs must not be reused. Fold both children's different saved animation choices into E2E-022 cases 118/120, read after each declared boundary and preserve time/app policy. E2E-008 case 22 owns animation-enabled normal locking during its existing exhaustion wait. All receiving journeys remain pending; menu details remain UI. |
| E2E-038 / 164–170 | Retain continued daily work after grant expiry and each distinct restoring action's launch/running-app effects. Finish child observations before a later switch can mask them. |
| E2E-039 / 171–176, 178 | Retain leaving pending approval or cooldown refusal, no unintended access and a later fresh real approval. Cases 176/178 include separate report-review/decline errors and correct desktop/GDM returns; station targets the other child. Same-child station case 177 removed. Unsupported public-close/timing routes remain gates. |
| E2E-040 / 180–182 | Retain fallback after real disposable-account removals and role changes without mixing settings. Case 180 combines Parent and reopened-station recovery after one logged-out spare-child removal, checking each screen independently with the survivor's own settings. Absorb case 183 without reusing its ID; last-child removal (181) and approver eligibility loss (182) remain separate. Duplicate add-child case 179 / task 221 is removed; completed E2E-003 case 3 already adds, selects and checks a child without reopening Parent. Account helper preparation remains for the retained branches. |
| E2E-041 / 184–189 | Retain finding actual child-installed apps without policy edits, saving/enforcing matching rules and documented reload limitation. Local search/editor matrices remain UI. |
| E2E-042 / 190–193 | Reallocate case 190 Parent Help/About link checks to shared UI, keeping its stable ID pending/excluded with no executable; case 151 owns installed information/management return. Cases 191–193 retain unfinished-request return, station restrictions and installed command usage/manuals. |
| E2E-043 / 194 | One offline journey retains local management, genuine approval on both request screens and each time/app result, then one revocation before reconnecting. Task 237 / case 195 is absorbed; no installed acceptance credit. |
| E2E-044 / 196–198, 200, 203 | Retain three ordinary-midnight checks and both grant types in one two-child journey per seasonal offset change. Separate daily-renewal proof on transition dates is dropped. Natural date windows and public precision remain gates. |
| E2E-045 / 205 | Retain Parent recovery from a customer-reproducible error and return to confirmed policy. Request-surface report review/decline and return belong to E2E-039 cases 176/178, absorbing 206/207. No injected fault or unauthorized Send. |
| E2E-046 / 208, 213 | Keep Parent's genuine failed collection → successful Retry with unchanged draft, and station's explicit Send without logs → service confirmation → manual dismissal → sign-in, with station file/external-link restrictions. Remove Parent without logs, both desktop request-report choices and station retry, accepting less screen-specific recovery coverage; cases 209–212 must not be reused. Both retained journeys remain pending on a reproducible public collection-failure trigger; Internet loss alone is insufficient. Sending retains its authorization/profile gate. |
| E2E-032 / 156 and E2E-047 / 216, 218–221 | Case 156 owns the single ordinary-feedback send without a reply address, service confirmation, manual dismissal and cleared draft after reopening. Remove the fixed five-second inspection wait from success journeys; preserve pending original-flow exit before dismissal and its destination afterwards. Case 220 owns an error-report send with an address, its follow-up note and correct desktop exit. `test_parent_feedback.py` owns exact confirmation wording with and without a reply address; no extra full ordinary-feedback send is scheduled for former case 214. Retain app-exit/stop lifetimes and correct original-flow exit. Background reconnection is combined into E2E-033 / 157; former case 215 is removed and must not be reused. Actual sending retains separate authorization/profile gates. Retry expiry remains with focused transport and feedback UI checks; its complete installed journey was removed. The additional Parent automatic error-report send was removed; Parent error review/return to confirmed settings in E2E-045 and successful station sign-in exit remain. |
| E2E-048 / 223–225, 227–228, 230 | Retain six journeys: both screens for daily-only and daily-dominant, desktop grant-only and station grant-dominant. Daily use continues on the desktop but pauses at the station; grant time elapses on either surface. Every retained journey keeps the real 45-second decision delay, current-balance approval and second increment. Remove cases 226 and 229 without reusing their IDs. No frozen estimate or private arithmetic substitute. |
| E2E-049 / 231, 232, 233, 236, 238, 239, 242, 243, 246 | Retain nine journeys: both request screens for the ordinary app menu, desktop requests for shortcuts and Snap/Flatpak app menus, station requests for Files and ordinary/Snap/Flatpak commands. Each retains both parents, fresh exclude/include/exclude approvals, soft-app closure, unchanged allowed work, continued hard denial and unchanged saved rules. Remove second-screen repeats 234, 235, 237, 240, 241, 244 and 245 without reusing their IDs. |
| E2E-050 / 247–248 | Retain two complete homework/game/recovery cycles per retained/fresh journey and every intermediate result, both forms/parents, windowed/fullscreen play and opposite expiry/recovery app choices. Reversed-start copies 249/250 removed; no final-state-only pass or hidden reset. |
| E2E-051 / 251 | Retain two recomposed rounds with reversed child order, both parents' own windows and both forms. Each child has daily/grant-only time and opposite temporary-app choices. Read the untouched peer before edits; finally revoke Jordan only while Riley continues on daily time. Reversed-start copy 252 removed. |
| E2E-052 / 253 | Retain usable Lunar/Minecraft controls and positive-grant blocked autostart/launch after reboot. Real assets and continuous login observation remain required gates. |
| E2E-053 / 254 | Retain understandable Chinese first install/reboot/request and two genuine native approvals. First-presentation language is functional context; secret guards establish recipient safety. |
| E2E-054 / 255 | Retain independent account languages, shared child choice, relaunch/session/offline persistence and unchanged policy. Replace generic assertion descriptions with exact outcomes. |
| E2E-055 / 256 | Rewrite as continuing the same mixed-script feedback/policy work across Hebrew and restored English. Duplicate reads/chooser branches/label completeness remain shared UI. |
| E2E-056–058 / 257–259 | Retain each surface's actual fresh-install → blocked Close/reentry → public Reboot now → usable postboot history under the [Parent](E2E-Scenario-Recipes.md#e2e-056), [Child App](E2E-Scenario-Recipes.md#e2e-057) and [station](E2E-Scenario-Recipes.md#e2e-058) recipes. Shared LIFE07 qualification establishes reusable notice operations, not a complete surface journey or a new installed pass. |
| Future language 308 | Retain Hebrew/restored-English requests with unchanged choices, genuine translated overlay approval and return to the same usable activity. Drop repeated About/error-report tours; Parent 307 retains mixed-script ordinary feedback draft comparisons. Translation/label matrices remain UI. |
| Future language 309 | Retain child's language and restricted station request choices across one approver change and language restoration, with the new approver still selected. Drop repeated About/error-report tours and report-draft reopening: error-report closure ends its draft under the [specification](../Specification.md#feedback-and-error-reports). |
| Future language 310 | Observe translated remaining-time use after each language save without extra time, lost work or changed policy, then natural expiry. Remove the extra unchanged overlay reopen and manual lock/unlock cycle; E2E-011/022 retain session-resume/lifecycle outcomes. Tooltip/menu/label matrices remain UI. |

The prior UI allocation review covered `tests/ui/test_*.py` modules. The screen-preview,
UI-watcher, E2E-watcher and fixture-GUI modules exercise the test harness itself;
they do not duplicate product E2E assertions. The live E2E spectator remains an
explicit opt-in check. The catalogue query/filter matrix is executable through
the shared installed worker composites and public-ID adapter. Outstanding request
matrices above remain TODO. The valid Save/Cancel and invalid/Reset match-editor
matrices are executable through the shared editor and text blocks.

## Shared operations

Both layers use the same [Application UI API](Application-UI-API.md), scoped
client facade in [`application_ui.py`](../../tests/support/application_ui.py),
public-ID readers and finite values in
[`accessible_ui.py`](../../tests/e2e/accessible_ui.py). Feedback host tests execute
the installed worker's actual `onpc_text`, `onpc_format` and
`onpc_feedback_states` composites through
[`gui_blocks.py`](../../tests/support/gui_blocks.py). The host adapter supplies
its private-session API connection; each observation is executed afresh and
failed observations stop input. It does not duplicate the worker's GUI sequence.

Attachment fixtures reuse the shared declared file matrix and public result
comparisons. Allowance cases select a small subset of the same boundary sequence
used by qualification. New UI and E2E work must extend these shared operations
before adding a second implementation of the same action.

Qualification probes remain explicitly selected engineering diagnostics. They
also follow the result-oriented mandate: incidental GUI assertions do not gain
an exemption by being called qualification. Qualify a changed input/provider
route with necessary independent-entry and refusal checks; do not make every
local value permutation a prerequisite for an unchanged installed component.

The [task queue](E2E-Task-Queue.md) still owns order and close-out. This allocation
review changes neither historical passes nor the current next-task pointer.
