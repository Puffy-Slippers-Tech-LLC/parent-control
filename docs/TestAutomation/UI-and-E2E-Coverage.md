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
| 158–159, daily allowance | `test_preview_smoke.py` and `test_control_overflow.py`: presets, custom boundaries and local commit paths | 158: preset 15, custom 1, invalid 1441; retain child switching, saved-value reload and restart. 159: real rapid saves, ordering and single-instance behavior |
| 38–43, request forms | `test_request_form_component.py` plus tasks 070/070a: complete preset/custom validation on both surfaces | One 5-minute preset or one 1.25-minute custom request with 0.09 rejection per surface; retain real authorization, duplicate-submission protection and the distinct rest-of-day grant |
| 184, application search/filter | `test_preview_smoke.py::test_catalogue_complete_query_match_access_matrix`: five queries × four match-mode subsets × eight access subsets, exact empty results, restored complete rows and no policy writes | One exact-name search, one combined precise/Allowed filter, then clear against the real catalogue |
| 185–186, application matching | Tasks 078/078a: local empty/unrelated input, cancel/reset and display states in UI preview | Real saved custom rule, cross-directory broker rejection, reopen/restart persistence and actual launch/enforcement |
| 151, 190–193, Help/About | `test_about_release.py`, `test_preview_smoke.py`, `test_e2e_accessible_adapter.py`; Parent content/clickability is delivered by 185p; overlay coverage remains in 185o | Owned About information and external-link clickability only, unchanged app return, kiosk restrictions and installed command manuals; no link invocation, URI/destination inspection or external handlers |
| 205–207, error reporting | `test_error_feedback.py`: local presentation and report callback permutations | Real public error routing, actual destination and required exit behavior |
| 155–157, 208–222, diagnostics/transport | Local presentation is UI; existing feedback UI tests cover callback success/failure states | Preserve actual collection, cancellation, service/network failures, sanitization and transport/lifetime checks; these execute different code from a stubbed preview |
| Layout, scaling and automation identity | Existing parent/child/kiosk/layout/accessibility UI tests | No repeated layout or scale matrix in E2E |

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
| E2E-014, 030, 031, 035, 041, 042, 045 | Split local matrices and installed integration as specified above |
| E2E-032, 033, 046, 047 | Real feedback/diagnostic transport and lifetime behavior; retain backend coverage |

The retired/superseded 028, 029 and 034 allocations, including retired numeric
IDs 140–150, remain with their documented engineering owners. No retired case
becomes customer acceptance through this review.

All current `tests/ui/test_*.py` modules were reviewed. The screen-preview,
UI-watcher, E2E-watcher and fixture-GUI modules exercise the test harness itself;
they do not duplicate product E2E assertions. The live E2E spectator remains an
explicit opt-in check. The catalogue query/filter matrix is executable through
the shared installed worker composites and public-ID adapter. Outstanding request
and match-editor matrices above remain TODO.

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
