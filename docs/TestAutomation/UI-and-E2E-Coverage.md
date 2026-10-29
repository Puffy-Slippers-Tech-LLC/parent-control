# UI and installed E2E coverage

Allocate assertions by the result they establish. UI tests own local functional
behavior a preview can establish without product backend execution. Installed
E2E owns customer outcomes: persistence, authorization, enforcement, lifecycle and
OS integration. Both follow the [UI mandate](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope).
A preview pass does not establish installed behavior; packaging a control does
not require duplicating its local matrix in E2E.

## Duplicate review and allocation

Remove incidental GUI assertions. Move retained functional assertions only after
the new owner is executable; pending obligations remain uncovered until then.
Local coverage gives no customer acceptance credit.

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
| Diagnostics/transport | Presentation and callback matrices | Real collection/cancellation/failure, sanitization, authorized service acceptance, retry and lifetime |
| Countdown/animation | Panel/tooltip/menu behavior | Work until natural exhaustion, normal locking, independent saved preferences across session/reboot without policy changes |
| Language | Representative scripts, Save/Cancel/failure, inherited text and draft preservation | Account independence, offline/session persistence, native translated approvals, usable request surfaces and natural expiry |
| Reminders/presets | Editing, sorting, duplicate/invalid values, literal text versus translated triggers, Save/Cancel/empty list | Saved custom reminders, exact cross-surface readback, reboot and unchanged peer settings; warning delivery is distinct |
| Automation safety | Shared runtime guards apply; no dedicated tooling assertions | Every journey uses qualified shared guards; traces/per-keystroke sampling are not customer outcomes |

Attachment fixtures replace only the external chooser's returned file list;
the frontend still reads/validates files and updates its draft. Local tests do
not replace the installed chooser handoff. Language/reminder fixtures likewise
do not prove native authentication or actual warning delivery.

## Reuse of system and integration coverage

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
| `test_authorization.test_requester_disconnect_during_approval` (system 255) | Engineering obligation 147: both requester disconnects, cancellation/no writes, released transaction, fresh authenticated recovery and other-account isolation | Cases 171–175 still observe leaving an actual pending graphical approval and its public result |
| Native command, whitespace, future-pattern, missing-launcher and catalogue system tests (272, 277–280) | Backend policy/UID/path/catalogue matrices and separate qualifiers for unchanged fixture mechanics | Parent edits and saved rules, declared launch routes, use/refusal, copied-executable/shared-launcher interactions and required peer access |
| `test_removal.test_remove_reboot_reinstall` (system 6); `test_install_smoke.test_previous_package_policy_preservation` (287) | Package files/ownership/service/PAM/migration matrices, internal snapshots and duplicate lifecycle qualifiers | Case 139's continuous install/configure/use/remove/use/reinstall/retained-settings/reapply/purge/defaults history; cases 136–138's real notices, activation and usable apps |
| Kiosk service/configuration recovery and update-reentry integration checks | Reimplementation of their fault/recovery controls and unchanged qualification | Actual unavailable result, restoration, genuine approval and usable return within each complete recipe |
| Delivered native fixture and grant/use/revoke scope in the [reuse map](E2E-Building-Blocks.md#cross-plan-baseline-reuse) | Rebuilding compatible fixtures or repeating the accepted finite native history for 313a/313 | Each later journey's own approval, access, expiry/revocation and retained-work results; different durations/providers/entry modes retain their missing qualification |

Obligation 147 remains scheduled in its system owner without a separate E2E
implementation task; this allocation claims no new pass. Other engineering
obligations retain the gaps named in their briefs. Natural expiry, suspend,
calendar transitions, graphical authentication and retained work still need
their full installed journeys.

## Complete scenario-family review

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

Feedback Send retains authorization/profile gates, service confirmation, draft
lifetime, dismissal and original-flow exit. Offline completion opens no unsolicited
window and needs no second Send. Internet loss alone does not prove diagnostic
collection failure.

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
