# UI and installed E2E coverage

The `ui` category owns exhaustive behavior that can be established in a component
preview without executing product backend logic. Installed E2E keeps a small
representative check that the component works in the packaged application, plus
every distinct backend, persistence, authorization, lifecycle and operating-system
integration result. A preview pass alone does not establish those installed results.

Allocate individual assertions, not whole features. Move an existing assertion
only after its UI owner is executable; do not remove an unimplemented obligation.
Pending UI matrices below belong to their existing capability task, before its
customer case. They do not create another queue or confer acceptance credit.

## Duplicate review and allocation

| Cases / area | Full GUI owner | Installed E2E scope |
| --- | --- | --- |
| 152, feedback formatting | `test_parent_feedback.py`: all block and inline formats, links, clear/reapply, undo/redo, Unicode and retained draft | Type text, bold one selection, append an emoji; retain reply, one real attachment, return from a directly launched supporting window, dialog preservation and app-exit reset. This does not activate a product link. |
| 153, feedback validation | `test_parent_feedback.py` and `test_e2e_accessible_adapter.py`: local states, 5000/5001 ASCII and emoji, hidden characters, excessive formatting, rejected-send preservation | Reject one empty send, edit body/reply, reopen and observe recovery; never send valid feedback |
| 154, attachments | `test_parent_feedback.py`: count, individual/total size, filename and atomic-rejection boundaries; real file reads and frozen attachment snapshot after source mutation | Real chooser Open with two files, Cancel preservation, remove one attachment and read the remaining file |
| 158–159, daily allowance | `test_preview_smoke.py` and `test_control_overflow.py`: full preset matrix through shared click/type/Enter/saved-value selection, Custom focus, custom boundaries and local commit paths; no popup/highlight/cancellation checks | 158: preset 15, custom 1, invalid 1441; retain child switching, saved-value reload and restart. 159: click → `15m` → Enter → saved 15 minutes, then Custom through the same block, real rapid saves, ordering and single-instance behavior |
| 38–43, request forms | `test_request_form_component.py` owns local duration validation; the complete preset/custom matrix on both surfaces remains uncompleted and carries no acceptance credit from the removed gesture tasks | Cases excluded from scheduling by the [unsupported native-gesture rule](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures). Preserve their duration, authorization, duplicate-submission and rest-of-day assertions as uncovered; do not recreate gesture tasks. Other ordinary request/approval cases continue independently. |
| 184, application search/filter | `test_preview_smoke.py::test_catalogue_complete_query_match_access_matrix`: five queries × four match-mode subsets × eight access subsets, exact empty results, restored complete rows and no policy writes | One exact-name search, one combined precise/Allowed filter, then clear against the real catalogue |
| 185–186, application matching | `test_preview_smoke.py::test_match_editor_valid_save_cancel_matrix`: precise/wildcard × absolute/basename Save and Cancel through shared blocks; `test_match_editor_invalid_reset_matrix`: empty/whitespace/unrelated absolute/basename drafts × old precise/wildcard × Cancel/Reset, exact explanations, retained drafts, unchanged Cancel and immediate default save | Real saved custom rule, representative local refusal and immediate Reset, cross-directory broker rejection, reopen/restart persistence and actual launch/enforcement |
| Application access choices, PARENT16 | `test_preview_smoke.py::test_app_access_choices_save_and_independent_readback`: all three choices, unchanged Allowed without another save, wrong-row/modal refusal and independent entry through the shared access composite | Native fixture A's Allowed/Hard/Soft autosaves and exact public row readback; actual enforcement and full match/access composition stay with their separate tasks |
| 151, 190–193, Help/About | `test_about_release.py`, `test_preview_smoke.py`, `test_e2e_accessible_adapter.py`, `test_request_form_component.py::test_overlay_about_license_shared_reader_and_unchanged_form`; Parent content/clickability is delivered by 185p and full overlay Help/About clickability/return by 185o | Owned About information and external-link clickability only, unchanged app return, kiosk restrictions and installed command manuals; no link invocation, URI/destination inspection or external handlers |
| 205–207, error reporting | `test_error_feedback.py`: local presentation and report callback permutations; `test_preview_smoke.py::test_rejected_parent_rule_report_review_and_confirmed_policy`: confirmed precise/wildcard restoration, automatic report, synthetic draft, Privacy and normal closure through shared blocks | Complete case 205 and request-surface error routing, destinations and exits |
| 155–157, 208–222, diagnostics/transport | Local presentation is UI; existing feedback UI tests cover callback success/failure states | Preserve actual collection, cancellation, service/network failures, sanitization and transport/lifetime checks; these execute different code from a stubbed preview |
| Layout, scaling and automation identity | Existing parent/child/kiosk/layout/accessibility UI tests | No repeated layout or scale matrix in E2E |
| Personal language settings | `test_language_settings.py`: English, German and Simplified Chinese on Parent, overlay and kiosk; first-run/session defaults, saved startup, commit-before-close, Cancel, read/save failure and retry, accessible labels and dynamic errors; Parent Hebrew public logical Text and Cancel-to-Save keyboard focus. Selected-child desktop defaults and reboot-required presentation have component coverage; agent preparation is a transport double, not native approval evidence. Existing GTK direction/alignment engineering and draft/scale coverage remain. | Tasks 300 and 306–310 follow the [acceptance mapping](E2E-Scenario-Recipes.md#personal-language-acceptance-decomposition): Chinese latest-install/reboot/two native approvals; account/offline persistence; Parent, overlay and kiosk Hebrew logical text/dialogs; panel refresh/countdown/natural expiry. Each missing surface/result binding has a bounded prerequisite. Apply the mandate's no-visual acceptance rule for this and future tasks; geometry remains prohibited. Chinese assets remain in prepare-baseline and desktop language in DESK13. Actual native text is required on both Chinese approvals; Hebrew requires qualified public logical text/identity/keyboard observations on each surface. No installed acceptance is claimed by this allocation. |

Parent's inherited About/feedback matrix is owned by
`test_language_settings.py::test_parent_dialog_inherited_text_keyboard_and_retained_hebrew_draft`:
English → Hebrew → English, two visits per dialog/language, public logical text,
both keyboard directions and the exact retained mixed-script body/reply. It
executes the shared installed text/navigation blocks. Task 307b qualified that
fixed installed binding; task 307 still owns its complete policy/history assertions.

The attachment UI fixture substitutes only the external chooser's returned file
list. The real frontend reads the files, validates them and updates the dialog.
The installed case remains responsible for the actual chooser handoff. The full
matrix must not be restored to the installed case as a substitute for UI coverage.

## Complete scenario-family review

This review includes ready and pending variants in the
[executable inventory](../../tests/e2e/scenarios.json), their recipes and unfinished
task briefs. Families grouped below have the same allocation decision; numeric
case IDs in the table above identify the overlapping slices.

| Families | Review result |
| --- | --- |
| E2E-001 | Runner smoke; keep installed infrastructure coverage |
| E2E-002, 026, 027 | Installation, package removal and upgrade; keep installed coverage |
| E2E-003, 004, 017, 040 | Account and authorization boundaries; keep real account/session coverage |
| E2E-005–010, 019–025, 036, 038, 043, 044, 048–052 | Time, enforcement, session, timezone, policy and lifecycle behavior; GUI setup is shared infrastructure, not duplicate acceptance |
| E2E-011–013, 015, 016, 018, 037, 039 | Desktop integration, authentication, exit and saved preferences; retain each distinct installed result |
| E2E-014 | Native double-click cases excluded from scheduling; preserve uncovered assertions and independent local duration validation as specified above |
| E2E-030, 031, 035, 041, 042, 045 | Split local matrices and installed integration as specified above |
| E2E-032, 033, 046, 047 | Real feedback/diagnostic transport and lifetime behavior; retain backend coverage |

The retired/superseded 028, 029 and 034 allocations, including retired numeric
IDs 140–150, remain with their documented engineering owners. No retired case
becomes customer acceptance through this review.

All current `tests/ui/test_*.py` modules were reviewed. The screen-preview,
UI-watcher, E2E-watcher and fixture-GUI modules exercise the test harness itself;
they do not duplicate product E2E assertions. The live E2E spectator remains an
explicit opt-in check. The catalogue query/filter matrix is executable through
the shared installed worker composites and public-ID adapter. Outstanding request
matrices above remain TODO. The valid Save/Cancel and invalid/Reset match-editor
matrices are executable through the shared editor and text blocks.

## Shared operations

Both layers use the same public-ID readers and finite values in
[`accessible_ui.py`](../../tests/e2e/accessible_ui.py). Feedback host tests execute
the installed worker's actual `onpc_text`, `onpc_format` and
`onpc_feedback_states` composites through
[`gui_blocks.py`](../../tests/support/gui_blocks.py). The host adapter supplies
the private-display keyboard transport; each observation is executed afresh and
failed observations stop input. It does not duplicate the worker's GUI sequence.

Attachment fixtures reuse the shared declared file matrix and public result
comparisons. Allowance cases select a small subset of the same boundary sequence
used by qualification. New UI and E2E work must extend these shared operations
before adding a second implementation of the same action.

Full matrix qualification probes remain explicitly selected engineering
diagnostics. They are not routine customer cases or members of the default E2E
category. Qualify a changed input/provider route with its independent-entry and
refusal checks; do not make every local value permutation a prerequisite for an
otherwise unchanged installed component smoke check.

The [task queue](E2E-Task-Queue.md) still owns order and close-out. This allocation
review changes neither historical passes nor the current next-task pointer.
