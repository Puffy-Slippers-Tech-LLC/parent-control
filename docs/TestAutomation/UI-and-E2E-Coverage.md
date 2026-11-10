# UI and installed E2E coverage

Allocate assertions by the result they establish. UI tests own local functional
behavior a preview can establish without product backend execution. Installed
E2E owns customer outcomes: persistence, authorization, enforcement, lifecycle and
OS integration. Both follow the [UI mandate](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope).
A preview pass does not establish installed behavior; packaging a control does
not require duplicating its local matrix in E2E.

## Duplicate review and allocation

Remove incidental GUI assertions. For local UI reallocations, move retained
functional assertions only after the new owner is executable; pending obligations
remain uncovered until then. System registration follows the
[standalone assertion boundary](#reuse-of-system-coverage),
including planned E2E composition. Local coverage gives no customer acceptance credit.

Local owners are `test_parent_feedback.py` for feedback/attachments,
`test_preview_smoke.py` and `test_control_overflow.py` for Parent controls,
`test_request_form_component.py` for request forms, `test_language_settings.py`
for language/reminder/preset editing, `test_about_release.py` for information,
`test_error_feedback.py` for errors and `test_child_shell_lifecycle.py` for the
panel. `test_e2e_accessible_adapter.py` and `test_automation_identity.py` retain
product assertions through the shared operations. Automation protocol, identity
inventory, tracing and deliberate wrong-target/refusal checks are outside UI
acceptance; focused safety coverage belongs beneath the UI under the
[test scope mandate](../Mandates/Test-Scope-Mandate.md). Product cases retain
the shared runtime ownership and input guards without testing those guards.

| Area | Local UI responsibility | Installed responsibility |
| --- | --- | --- |
| Feedback | Formatting/link/undo, Unicode/length boundaries, refused-send draft preservation | Author and retain a realistic report, reject empty submission and recover, preserve work across supporting-window/dialog transitions |
| Attachments | Count/size/name boundaries, atomic rejection, chooser Cancel, frozen snapshots | Real chooser handoff, remove unwanted file and retain intended attachment |
| Allowance | Preset/custom boundaries and commit paths | Persistence, last-change-wins and independent children |
| Requests | Duration/preset/custom/validation/duplicate-submit matrices | Genuine approval, no premature access, correct child, current balance, rest-of-day and retained choices |
| Application search/matching | Queries/filters, Save/Cancel/Reset, invalid drafts | Real catalogue, saved rules, broker rejection, reload limits and enforcement |
| Application access | All choices, unchanged autosave, wrong-row/modal refusal | Saved Allowed/Hard/Soft policy, actual launch and running-app effects |
| Help/About | Controls, link availability and text | Installed identity, return to work, station restrictions and manuals; no external-handler tour |
| Diagnostics/transport | Presentation; sending, retry, draft lifetime and report-close behavior with the existing fake sender | Real collection/cancellation/failure, sanitization and actual report-exit destinations; real sending is separate optional integration work |
| Countdown/animation | Panel/tooltip/menu behavior | Work until natural exhaustion, normal locking, independent saved preferences across session/reboot without policy changes |
| Language | Representative scripts, Save/Cancel/failure, inherited text and draft preservation | Account independence, offline/session persistence, native translated approvals, usable request surfaces and natural expiry |
| Reminders/presets | Editing, sorting, duplicate/invalid values, literal text versus translated triggers, Save/Cancel/empty list | Saved custom reminders, exact cross-surface readback, reboot and unchanged peer settings; warning delivery is distinct |
| Automation safety | Shared runtime guards apply; no dedicated tooling assertions | Every journey uses qualified shared guards; traces/per-keystroke sampling are not customer outcomes |

The isolated child preview covers desktop/fullscreen-request countdown
availability and refusal; Node covers production locked/greeter decisions.
It has no owned logind/GDM session, so those results do not establish public
locked/greeter observations. Task 052b0 qualified the
[installed observation](E2E-Building-Blocks.md#locked-and-inactive-child-countdown-qualification)
of the retained child's panel, independently of the greeter's Shell, plus
restoration on Ubuntu 26.04. Task 052b completed the UI obligation with accepted
host results and a passing installed check through that same shared observation;
no genuine lock or greeter state is manufactured in the preview.
This allocation neither reopens completed journeys nor adds a customer scenario.

The same isolated Shell owner checks the countdown explanation through
`child-request-tooltip` on the owner-pinned shared `child-panel` client. It
compares the public explanation's meaning and HH:MM:SS with independent
`child-remaining-time` value reads, allowing one display tick of lag. Task 181h
completed this local coverage; installed time accuracy and enforcement remain
under their existing owners.

Attachment fixtures replace only the external chooser's returned file list;
the frontend still reads/validates files and updates its draft. Local tests do
not replace the installed chooser handoff. Language/reminder fixtures likewise
do not prove native authentication or actual warning delivery.

### Feedback sending allocation

The developer chose existing network-free component previews for routine
feedback sending. Tasks **150a, 150, 151, 152, 153, 258, 262, 263, 189k, 255,
190a, 190o, 260, 190b, 190k and 261** are explicit **UI obligation** rows,
implemented in the existing `test_parent_feedback.py` and
`test_error_feedback.py` owners. Reuse their fake HTTP session and real editor,
encoding, retry and result handlers; add only missing assertions. No production
mock switch, alternate endpoint, server, inbox or sending authorization is
needed. Deterministic transport/backoff checks remain with
`tests/unit/test_feedback_transport.py`.

Use the existing [Parent preview](../../tests/ui/parent_component_preview.py)
and [request preview](../../tests/ui/request_component_preview.py), whose fake
`feedback_transport.requests.Session` replacement stays unconditional. The real
editor, multipart encoder, retry controller, result and dialog handlers run.
Reuse the finite synthetic drafts in their existing test owners and the declared
text/file inputs through [feedback helpers](../../tests/support/feedback.py)
(`attachment_choices`); diagnostics come from the test-local collector. Ordinary
anonymous success leaves reply empty; the reply-note branch uses
`first@example.invalid`. Extend only existing test-local response/release controls
when an owning UI task needs them. Keep one explicit Send per declared submission;
automatic retries retain its frozen content and identity, and uncertain input
must not be replayed. Request callbacks are recorded through the existing
[request helpers](../../tests/support/request_form.py).

Hold a fake retry response with the existing release file until the caller has
observed the required retry or Stop result, then release it in `finally`.
Release and transport receipts alone do not prove that the app handled the late
response. Parent retains its closed feedback surface: await its public submitted
status and check that no feedback or thanks window appeared before reopening;
then independently check the cleared draft, reply and customer files. Refreshed
diagnostics are a new attachment, not a retained customer file.

A child error report is destroyed on close, so its old status cannot witness
completion. Follow `test_child_stops_sending_report_before_late_response` in the
[error-report checks](../../tests/ui/test_error_feedback.py): establish report
closure and exactly one exit callback before releasing the pending reply, await
the real completion handler's existing nonsecret outcome diagnostic in the owned
preview log, then independently check that neither report nor thanks reopened
and the callback count stayed one. Keep late retry/success responses and expected
outcomes in the case; the diagnostic synchronizes the check and supplies no
installed exit or delivery credit.

Retain former cases **156, 157, 213, 216, 218, 219, 220 and 221** as allocation
references, pending with no E2E executable or installed acceptance. The launcher
carries the explicit `UI obligation;` scope marker through host-only selection,
prompts and completion; historical task 192 retains its exception. UI tasks
return `live_result=not_run` after focused host acceptance and ordinary close-out.
Installed tasks still require live acceptance, and host-only completion cannot
clear an outstanding failure. Allocation metadata names the existing UI owner
and remaining task without registering host tests as E2E executables.

Mock responses must not contact the real service. They establish anonymous
confirmation, success/clearing, retry/background completion, app-exit reset,
direct Stop and explicit Send without logs under declared responses. Recorded
request close/logout callbacks establish callback ordering, not an installed
desktop or GDM destination. Genuine installed error entry, collection failure
and recovery, confinement and public request-exit results remain with their
existing owners. Do not gate these local sending checks on an installed
request-error entry, Internet isolation or a missing public collection-failure trigger.

Real sending is a separate optional integration check under the
[live-delivery contract](../../tests/README.md#coverage-maintenance-workflow),
outside routine queue acceptance. A mock pass supplies no live-service or email
delivery result. No sending permission or recipient profile should be requested
for these routine UI obligations.

## Reuse of system coverage

System registers only standalone tests with assertions outside
current or planned E2E composition. A qualification that only exercises E2E
building blocks is not a system test, even before its consumer
is implemented. Keep its shared operations and focused qualification route;
do not register it and then add a scheduling exclusion. Register engineering
faults, internal OS/backend witnesses and essential harness safety checks in
their appropriate suite. Normal public recovery within such a distinct fault
history remains part of that test. Classify mixed checks by their assertions and
remove independent public-only qualification attempts already owned by E2E.

Keep each complete customer journey: its starting state, customer actions,
intermediate access/recovery results and final usable destination. Assess overlap
per assertion, not per feature name. Saving a rule in Parent and observing its
effect remains a customer result even when system tests also call the broker.
A reference to another suite cannot replace that observation in the journey.

Remove repeated engineering cases, steps and acceptance matrices instead. Reuse
their maintained operations for setup; do not create another qualification
wrapper or rerun an unchanged matrix merely to consume it. Extend an existing
owner only for a concrete missing assertion. A pending declaration or a helper
without executable assertions establishes no coverage.

| Existing owner | Work not to duplicate | Customer journey retained |
| --- | --- | --- |
| [Extension recovery system coverage](../SystemDesign/Screen-Time.md#extension-recovery-verification-boundaries), system 295–301 alongside system 281/282 | Individual/global disablement, repeated interference/backoff, native extension errors/reporting, and boot/Parent/kiosk/login/unlock recovery are standalone system faults; reuse existing adapter rollback and host/private-bus guards | Existing ordinary setup, approval, countdown and retained-session journeys remain unchanged; no new E2E case or engineering prerequisite is added |
| `test_baseline_fixtures_cleanup_safety` shared reconciliation, interrupted-placement, foreign/tampered-input and missing-baseline checks | Per-profile copies of unchanged idempotence, owned-update, retry and refusal matrices in tasks 109p/116p/126p; check only a genuinely new package, scope, confinement or ownership boundary | Real installation and restored-profile readback remain required; later Snap/Flatpak launches, enforcement and game use/expiry retain complete acceptance |
| `test_authorization.test_requester_disconnect_during_approval` (system 255) | Engineering obligation 147: both requester disconnects, cancellation/no writes, released transaction, fresh authenticated recovery and other-account isolation | Cases 171–175 still observe leaving an actual pending graphical approval and its public result |
| `test_core.test_parent_disable_cannot_interleave_with_admitted_approval`, `test_approval_cannot_snapshot_parent_disable_bridge_or_rollback`; `test_private_dbus_service.test_request_workers_dispatch_concurrently`; system 255 | Engineering obligation 148: real threaded broker conflict, Busy/no writes, final time/policy and successful retry; private-bus worker dispatch; installed bus/agent Busy/release and authenticated recovery. No separate task 177 or repeated concurrency qualifier. | Complete graphical approvals, pending-request interruptions and independent child/parent journeys retain their public results |
| Native command, whitespace, future-pattern, missing-launcher and catalogue system tests (272, 277–280) | Backend policy/UID/path/catalogue matrices and separate qualifiers for unchanged fixture mechanics | Parent edits and saved rules, declared launch routes, use/refusal, copied-executable/shared-launcher interactions and required peer access |
| Existing language selection and `language_persistence.PLAN` request readers | A second presentation-history qualifier (308a/309a) repeating saved Hebrew/custom-request/approver bindings | Tasks 308/309's complete restoration histories and original-work comparisons; 308b's missing translated approval and 310a's new panel projection remain distinct |
| Shared `PackageCommand`, match Save and Parent reopen/select operations | Complete catalogue update/remove/reinstall histories repeated in 123/123a qualifiers | Cases 110/111 implement missing verified fixture bindings and retain open drafts, actual package changes, Save, refreshed catalogue, retained rules and child launch results |
| `test_removal.test_remove_reboot_reinstall` (system 6); `test_install_smoke.test_previous_package_policy_preservation` (287) | Package files/ownership/service/PAM/migration matrices, internal snapshots and duplicate lifecycle qualifiers | Case 139's continuous install/configure/use/remove/use/reinstall/retained-settings/reapply/purge/defaults history; cases 136–138's real notices, activation and usable apps |
| Kiosk service/configuration recovery system checks; shared update-reentry building block | Reimplementation of their fault/recovery controls and unchanged qualification; update-reentry has no system registration | Actual unavailable result, restoration, genuine approval and usable return within each complete recipe |
| Delivered native fixture and grant/use/revoke scope in the [reuse map](E2E-Building-Blocks.md#cross-plan-baseline-reuse) | Rebuilding compatible fixtures or repeating the accepted finite native history for 313a/313 | Each later journey's own approval, access, expiry/revocation and retained-work results; different durations/providers/entry modes retain their missing qualification |

Obligations 147/148 remain with their executable lower-suite owners without
separate E2E implementation tasks; this allocation claims no new pass. Other engineering
obligations retain the gaps named in their briefs. Natural expiry, suspend,
calendar transitions, graphical authentication and retained work still need
their full installed journeys.

Task 035b adds only missing finite versioned asset/copy/Allowed-launch bindings;
case 189 owns matching denial, nonmatch use, refresh and rejected-save recovery.
FLOW19 uses the existing setup mode and a complete saved-set comparison, while
feature cases retain each tested policy transition's independent effects.
Removing a precursor history does not qualify a new provider or safety binding;
keep genuinely missing qualification explicit in its consumer.

Task 188r combines the missing Parent collection-failure projection and Retry
binding in one qualification. Former task 188p's separate failure setup/close
attempt is redundant; retain the failed result, usable controls, draft,
restoration and successful Retry together. No public failure/recovery trigger
is established, so the combined capability and complete case 208 remain pending.

Tasks 150o/150k's duplicate Send/dismiss/exit qualifiers remain absorbed into
former cases 220/221, now allocated to the
[mock-sending UI owner](#feedback-sending-allocation). Task 150 owns shared
component response/confirmation checks. The cooldown behavior and unfinished
tasks 187a/187o/187b/187k and 218/220 are retired; stable historical cases
176/178 remain pending and excluded with no executable or acceptance credit.
Immediate sequential requests with fresh authentication reuse the existing
panel-request history and broker tests, without another E2E task. Delayed-approval
modules retain their supporting history; E2E-048 stays excluded under its separate
save-failure decision and gains no acceptance here. Genuine installed request-error review/decline, Privacy and exit
bindings remain uncovered under FEED15 until a real public error route is
qualified; collection task 188k retains that entry gate. Mock close/logout callbacks do not qualify
their installed destinations. Pending-prompt transition
qualifiers 183a–e retain cancellation and safe return; cases 171–175 own the
fresh successful approval, balance and access recovery. No lower-layer pass
supplies those journeys, and changed provider/safety boundaries retain scoped
qualification.

Task 102's duplicate expiry/replacement qualifier is absorbed into cases
23/24/126/127. Their existing natural-lock, time-denial, retained-entry and
parameterized FLOW20 operations supply the composition; 197k and the game
owners retain missing bindings. Every case still captures its original work,
reaches real expiry, obtains real approval and independently observes recovery.
No earlier qualification or lower-suite pass supplies those complete results.

## Expiry coverage allocation

Customer scenarios retain their existing canonical tasks. The broker expiry
exploration plan and optional-extension proposal have been removed. Unimplemented
engineering extensions are merged into E2E queue tasks 172a–172h and 172j–172l, with no current
acceptance credit. Native-isolation research and proposal-specific handover are
retired; existing production-path assertions remain.
This allocation preserves coverage ownership and avoids duplicate qualification
workers or a second customer queue. Recipes own finite data and ordered results;
task status and executable bindings are unchanged.

| Scope | Single delivery owner | Later work must not repeat |
| --- | --- | --- |
| Approvals and extension-dependent timing | Existing core/adapter owners retain arithmetic, identity and failure-refusal coverage. TIME01, REQUEST08 and FLOW05 retain public observations on their declared surfaces. Current extension dependencies are documented in [Screen time](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement) | A second timing ledger, copied status/approval journey or authentication matrix. Retiring the proposals grants no installed acceptance and removes no executable coverage. |
| Current daily/grant/combined natural locks, denial, retained work and peer activity | Existing cases 22, 25–29; shared TIME04, lock-input and activity observations | A new baseline expiry journey or unchanged provider matrix. Existing cases receive only affected regressions after actual code changes. |
| Revocation at zero/positive daily time, Cancel, retained entry and peer continuity | Tasks 084/085, canonical single-desktop cases 17/19. Former tasks 143–149 and cases 18/20/112–115 are removed from execution and retained only in [Two desktops](../Two_Desktops.md). | A separate migration-only copy or reconstruction of the removed two-desktop tasks. Cases 17/19 switch to Parent before revocation; foreground immediate-lock acceptance belongs to the installed residual below. |
| Daily balance outlasting a soft-app grant | Task 182 owns positive FLOW18 preparation; task 206/case 164 owns uninterrupted expiry/no-lock/soft-access results | Task 182 must not add its optional second expiry wait. Tasks 207–212/cases 165–170 reuse preparation/observation and own only their different post-expiry transitions. |
| Idle and suspend before/after grant expiry | Task 164/case 122; LIFE03 tasks 166a/166; tasks 167/168/cases 124/125 | Another generic idle/suspend expiry suite. LIFE03 is implemented/qualified once; complete cases retain only their unique choices, policy, work and recovery composition. |
| Real usage-read outage/recovery | Task 172 (engineering obligation 143) under the installed session owners. Former task 171/obligation 142 is removed from execution; [Unlock desktop](../Unlock_Desktop.md) preserves that open question only. | A second identity-scoped reader-fault matrix or recreation of the removed entry-exposure qualifier. The open question is not a prerequisite for remaining session work. |
| Expiry-specific broker/timer failure, hang, owner replacement, stale work, lock completion, foreground revocation and policy races | Tasks 172a–172h and 172j–172l extend the `system_graphical_expiry` owner and system 282's shared mechanics. Foreground revocation has the distinct `session::test_foreground_revocation` binding (system 303), without replaying system 282 | System 303's foreground zero/positive daily revocation, bounded protected lock, original-work recovery and positive input passed on the session-selected Ubuntu 26.04 VM; Fedora remains unqualified. Pending approval and time-decision ordering are allocated separately below; other bindings remain planned. No customer-case credit. Reuse obligation 148’s existing concurrency assertions; no separate host preparation task or engineering suite. Tasks 169/170/173–175/178/179 retain their different residuals; task 172 owns reader faults. The former entry-exposure question is unscheduled in [Unlock desktop](../Unlock_Desktop.md). |
| Expiry while a genuine parent approval remains pending | `system_graphical_expiry`, `natural_expiry.APPROVAL_PLAN` / `PendingApprovalJourney` and `session::test_expiry_during_pending_approval` (system 304), reusing system 282's attached worker and activity/lock/recovery mechanics | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261107T163336Z-aa8348da`: two 300-second histories with challenge readiness at least 180 seconds before original expiry, timely natural lock, protected input, cancellation without grant changes, original-work recovery and unrelated foreground input. Collection, worker shutdown, owned cleanup and baseline restoration passed. Fedora remains unqualified. No customer-case or task 171 entry-exposure credit; background protection supplies no natural-lock latency claim. |
| Latest parent time decision versus an in-flight read and original expiry | Eight controlled commit/rollback order checks in `test_core`, deadline dispatch in `test_private_dbus_service`, and `session::test_policy_changes_before_expiry` (system 305) through `natural_expiry.PolicyOrderJourney` and `system_graphical_expiry` | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261107T234126Z-f7d43e80`: renewal, allowance and disablement each preserved original-desktop input and work past its unchanged 180-second deadline, followed by bounded restricted natural lock, both protected-input challenges, original-work recovery and peer continuity. Reuses existing Busy/conflict, stale-callback and system-282 mechanics. Collection, worker/callback shutdown, owned cleanup and baseline restoration passed. Fedora remains unqualified; no customer-case credit. |
| Scheduled expiry work after the original child session ends | `natural_expiry.SessionReplacementJourney`, `onpc_desktop_session::session_replacement` and `session::test_session_replacement_before_expiry` (system 306), through the existing `system_graphical_expiry` fixture and attached worker | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261108T013846Z-afcf0b18`: changing displayed countdown text before logout, a different same-account session with positive authoritative entitlement, continuous replacement input and retained work across the unchanged 600-second original deadline, and peer input/work before and after it. Collection, worker/callback closure, owned cleanup and baseline restoration passed. This qualifies pending scheduled work, not a deliberately held asynchronous completion. Fedora remains unqualified; no customer-case credit. |
| Broker crash before original expiry, protected outage and current-time recovery | `natural_expiry.BrokerCrashJourney`, the existing system-282 worker and `system_graphical_expiry.crash_history`; `session::test_broker_crash_before_expiry` (system 307). The product indicator's pending-lock callback boundary is covered in `tests/child/indicator_logic.test.mjs` | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261108T022958Z-c6ddedd9`: two identity-recorded SIGKILL faults, unchanged 180-second deadlines, foreground timely lock, both protected-input challenges, new-owner zero balance and unchanged expired grant before declared recovery time, original session/work and peer input/work. Collection, worker/callback shutdown and baseline restoration passed. This qualifies on-demand activation after a controlled outage, not automatic supervision or a deliberately held live lock callback. Fedora remains unqualified; no customer-case credit. |
| Deliberately stopped broker across original expiry and bounded recovery | `natural_expiry.STOP_PLAN` / `BrokerStopJourney`, `onpc_desktop_session::broker_stop` and `system_graphical_expiry.stop_history`; `session::test_broker_stop_before_expiry` (system 308), reusing system-282 mechanics | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261108T062038Z-4e988099`: one grant-only retained-desktop history, identity-recorded clean stop before the unchanged 180-second deadline, unchanged activation mask and service-start identity through timely lock and protected input, new-owner zero balance without grant replay, original child work recovered within original expiry plus 300 seconds, and the same peer session/work/input before and after. Collection, worker closure, owned cleanup and baseline restoration passed; VM off. Fedora remains unqualified; no automatic supervision or customer-case credit. |
| Stalled broker across original expiry and same-process recovery | `natural_expiry.BrokerStallJourney` and `system_graphical_expiry.stall_history`; `session::test_broker_stall_before_expiry` (system 309), reusing system-282's two crash-history mechanics | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261108T065535Z-ee8c3c20`: two real identity-recorded SIGSTOP/SIGCONT histories, original 180-second deadlines, timely foreground lock, both protected-input challenges, same-process zero balance without grant replay, original session/work recovery within expiry plus 300 seconds and foreground parent input/work. Collection, worker/callback closure, owned cleanup and baseline restoration passed; VM off. Fedora remains unqualified; no customer-case credit. |
| Native timer owner replacement across original expiry | `natural_expiry.TimerReplacementJourney` reuses `STOP_PLAN`; `system_graphical_expiry.timer_history`; `session::test_timer_replacement_before_expiry` (system 310) | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261108T075926Z-16e1908b`: one identity-recorded masked timer stop through unchanged 180-second expiry, timely lock and protected input; distinct bus/process/service owner, exhausted native child estimate, zero balance and unchanged expired grant before recovery time; original child work within expiry plus 300 seconds and the same parent session/input/work before and after. Collection, worker shutdown, owned cleanup and baseline restoration passed; VM off. Existing reliability and session-replacement owners retain retry, authorization and stale-work matrices; this adds no deliberately held reply. Fedora remains unqualified; no customer-case credit. |
| Delayed acknowledgement and missing reply at the real lock boundary | `natural_expiry.REPLY_PLAN` / `LockCompletionJourney`, `system_lock_reply` and `session::test_secure_lock_completion` (system 311), reusing the existing system-282 worker, protected-input and work observations | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261108T215106Z-aeda37d1`: two unchanged 180-second deadlines, actual product requests and native completion, timely protection and both protected-input challenges, delayed acknowledgement only after input, actual client failure while the missing reply remained held, original child session/work after both histories, and the same parent session/input/work before and after. A public child lock-setting gate prevents the native automatic action from preempting interception; it is restored before forwarding each real request and on owned cleanup. Normal facade, lock setting and native owner restoration, collection, worker shutdown and baseline restoration passed; VM off. No lock-retry owner or cancellation of an already dispatched lock is claimed. Fedora remains unqualified; no customer-case credit. |
| Games/fullscreen, expired app exceptions, remembered choices, repeated household routines, natural midnight/DST | Their current canonical tasks/recipes | Generic expiry, service-fault or provider qualification added before each consumer. Keep the different interaction's required public result and reuse shared mechanics. |
| Temporary native lock unavailability and renewal cancelling stale retries | `natural_expiry.LockRetryJourney`, existing `STOP_PLAN` and `system_lock_reply.retry_history`; `session::test_transient_lock_recovery` (system 312) | Passed on session-selected `onpc-Ubuntu26.04-1` in `20261108T230422Z-b787bea6`: real refused request and successful retry, protection by the original expiry plus 15 seconds, protected input, confirmed positive renewal before availability restoration, no stale request beyond the old window, continued child input and original child/parent work. The affected delayed/missing-reply regression (system 311) passed in `20261108T232640Z-cfc49665`. Collection, worker closure, normal lock-service restoration, owned cleanup and baseline restoration passed; VM independently off. Fedora and persistent outage protection remain unqualified; no customer-case credit. |
| Persistent lock-action outage in a surviving child desktop | `natural_expiry.LockOutageJourney`, existing `STOP_PLAN` and `system_lock_reply.outage_history`; `session::test_persistent_lock_outage` (system 313) | Characterization passed on session-selected `onpc-Ubuntu26.04-1` in `20261109T000907Z-148ad941`: the original 180-second grant crossed expiry plus 20 seconds under real lock refusals, followed by explicit revocation and another 20-second outage. Original-window Submit/readback remained usable after both boundaries, so protection is unsupported. Recovery restored lock availability, supported lock/protected input, original child work and the same parent session/input/work. Collection, worker closure, normal facade/setting/native-owner restoration and baseline restoration passed; VM independently off. Fedora remains unqualified. No protection or customer-case credit; return only with supported protection by the original deadline while ordinary work survives. |

Work implementing a pending full scenario must use its stable case ID,
recipe and canonical task; register and accept that case rather than an alias.
Close that row as part of the actual delivery, so it cannot be scheduled later
as duplicate implementation. When a later selected task encounters an already
accepted exact scope, reconcile its remaining work and reuse that completion
without rechecking old reports or rerunning it solely for a different label.
Partial operations and native probes do not close a complete customer case.
Different account/provider/input bindings or code changes require only their
affected qualification/regressions; no saved guest state transfers between runs.
Required task prerequisites and supported-route gates still apply. For example,
LIFE03 qualification is reused, but cases 124/125 each perform their own real
suspend/wake and observe their own deadline, access and retained-work results.
Cases 165–170 likewise each cross their original grant deadline before their
distinct action; case 164's pass supplies no state or expiry result to them.

For mixed journeys, retain the minimum ordered observations needed to prove
the distinct interaction, not a second generic expiry matrix. A native game
retained across lock, app-policy restoration after unlock, or natural midnight
is not supplied by a generic desktop lock pass. Current rows remain unchecked
until their remaining outcomes actually pass. Existing checked rows stay done.
This allocation does not advance or reorder the E2E queue.

Source destinations for any future engineering extensions are
[installed graphical expiry](../../tests/integration/system_graphical_expiry.py),
its [registered session test](../../tests/system/test_session_expiry.py),
[broker core regressions](../../tests/unit/test_core.py) and
[private D-Bus dispatch](../../tests/component/test_private_dbus_service.py).
Sharing an installed attempt does not merge the distinct assertions or give
obligation 143 completion credit before its residual passes. Obligation 142's
open question is unscheduled in [Unlock desktop](../Unlock_Desktop.md), with no
completion or acceptance claim.

### Expiry engineering contract

Tasks 172a–172h and 172j–172l own only uncovered expiry effects at the existing installed
session owner. Delivered panel-independent timed locking, fresh protected-input
challenges, original-work recovery and foreground peer observations stay done;
reuse those mechanics without rerunning unchanged qualification. Customer cases,
reader faults and ordinary concurrency keep their owners above. The removed
entry-exposure question stays only in [Unlock desktop](../Unlock_Desktop.md);
these expiry tasks must not restore it as a prerequisite.
Planned bindings are not executable selectors; register the actual affected
selection before execution. This planning merge changes no scenario IDs or status.

Every installed task requires Ubuntu 26.04 and Fedora 44. Follow the VM mandate’s
[timing rules](../Mandates/VM-Mandate.MD#timing-and-slow-vm-resilience) and
[shared observer budgets](../../tests/support/README.md). Retain TIME04’s sample
upper end plus 15 seconds and the existing engineering timed-lock bound. Declare
fault, effect and recovery windows before injection; outage time counts against
the original deadline. Prepare actors/observers before the measured boundary;
controlled events and independent identities establish ordering, never lucky
last-second actions. Do not reset allowance, usage or the grant clock to repair
the observed history.

Use maintained real-boundary fault injection and identity-recorded restoration,
one condition per attempt. Protected input, retained work and unaffected peer
input are independent observations; sent lock requests, hints, timer reads and
restarted services alone cannot pass. Positive-entitlement controls stay usable.
Restore only owned processes, sessions, grants, limits and fault state under the
existing cleanup contract. No second ledger, provider matrix, fault framework,
production hook, supervision policy or scheduler is introduced.

Task 172k may repair transient public lock-action retry within the existing
owned enforcement callback and timer, as required by repeated exhaustion
enforcement. This is not a separate expiry scheduler or fallback lock policy.
Keep one finite-timeout lock request in flight, bound every retry by the
original absolute timed-lock window, and revalidate the current verified
deadline, entitlement and session before each attempt. Cancel pending work on
secure lock, renewal, disablement, owner invalidation, session departure or
disposal. Retry spacing is an implementation choice within that bound; late
recovery cannot retroactively pass protection. Persistent unavailability keeps
172l's characterization-only scope. These settled results need no new behavior
choice; production edits retain the applicable code-review and validation mandates.

Current production behavior is tested first. Missing supported fault ownership
blocks a task. A production mismatch follows
[failure handling](../../tests/README.md#handling-test-failures); record expected
versus actual behavior and the return condition without weakening assertions.
Task 172l may document an unsupported secure-lock boundary after actual attempts,
but that is no passing protection result. No proposal-specific replacement or
extension-disabled acceptance gate is imported into these current-path tasks.

## Complete scenario-family review

Apply the [shared Snap acceptance boundary](E2E-Execution-Instructions.md#snap-acceptance-boundary)
to every family. Allowed Snap use remains in scope; denial/closure cases
88/90/94/95/96/97/239/242 remain pending and deferred without executables or
acceptance credit. Generic application effects in other families use their
declared native/Flatpak/game identities and do not add a Snap matrix or require
another Snap product-choice investigation.

The [inventory](../../tests/e2e/scenarios.json) owns stable IDs, executable bindings
and pending/excluded status. [Recipes](E2E-Scenario-Recipes.md) own finite inputs,
order and expected public results. Keep unique outcomes there rather than another
inventory here. Removed IDs must not be reused. Retired, merged or UI-only cases
gain no installed acceptance from historical runs or local passes.

Retain the minimum reliable actions and independent observations for the customer
goal. Avoid dialog tours, unchanged reads, focus/caret checks, geometry and control
matrices. Keep intermediate checks for separate results: no unintended access,
the intended child's policy, untouched peer state, retained work, cancellation
and exit destination. A final-state check cannot replace these.

Distinct histories remain where behavior differs: fresh/retained sessions,
upgrade/activation, remove/reinstall/purge, natural midnight/seasonal transitions,
live balances while deciding and each surface's reboot recovery. Required real
assets, public timing precision, continuous login observation and reproducible
public failure triggers remain gates. Qualification cannot supply missing results.

Feedback Send follows the [mock-sending allocation](#feedback-sending-allocation):
routine UI checks retain draft lifetime, dismissal and callback ordering under
declared responses, with no recipient or authorization gate. Background
completion opens no unsolicited window and needs no second Send. Internet loss
alone does not prove genuine installed diagnostic collection failure.

[Unsupported native gestures](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures)
remain excluded. Retained uncovered assertions must not disappear or become new
gesture work. Pure action availability and link-only checks stay UI-owned without
duplicate standalone installed journeys.

In particular, stable cases 161 (zero-total Revoke availability) and 190 (Parent
Help/About link availability) stay pending and excluded with no E2E executable;
local UI checks supply no customer pass. Daily-only revocation and installed
product-information journeys retain their distinct outcomes. Request cases
38–43 remain excluded by the native-gesture rule; their duration, authorization,
duplicate-submission and rest-of-day obligations remain uncovered. The complete
preset/custom matrix on both request surfaces is still pending local coverage.

## Shared operations

Both layers use the [Application UI API](Application-UI-API.md),
[shared facade](../../tests/support/application_ui.py), public-ID readers and
finite values in [accessible_ui.py](../../tests/e2e/accessible_ui.py). UI tests
execute the same [worker composites](../../tests/support/gui_blocks.py) through
private-session connections. Observe afresh; failed observations stop input.
Share file matrices and result comparisons. Extend shared operations before
adding another implementation; the [support guide](../../tests/support/README.md)
owns reuse.

Qualification checks the changed input/provider binding with necessary
independent-entry/refusal proof, not every local permutation of an unchanged
component. A supporting action or qualified capability is infrastructure, not
a complete customer outcome.
