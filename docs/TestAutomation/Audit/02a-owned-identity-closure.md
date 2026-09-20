# 02a — Close remaining owned identity and absence contracts

**Recommended model: GPT-6 Astra. Effort: high.** This is the remaining owned
adapter work from task 02, not a new audit or external-provider task.

**Prerequisite:** [02 inventory and first fixes](02-owned-ui-and-inventory.md)
and [shared preflight](README.md). **Status:** Complete; owned identity, complete-read,
effective-sensitivity and selected-account contracts passed final verification.
**Next:** [02b](02b-spectator-ui.md). Parent task 02 remains incomplete.

## Completion checkpoint

The shared readers now retry only complete public-tree acquisition within their
existing bounded accessibility waits. They discard the whole incomplete read;
they do not relax ownership, ambiguity or missing-ID failures, and input remains
single-dispatch under the existing uncertainty latch. The standard UI fixture
and both direct request-form adapters supply that wait. The earlier case-specific
Close retry was removed in favor of this shared contract.

Before the final shared read correction, the nine-file focused unit selection
recorded below passed **573 tests and 21 subtests**. The added pre-action
regression then passed independently (**1 passed**) by injecting one incomplete
tree and requiring
recovery with exactly one action dispatch. The previously failing kiosk error
feedback node then passed independently in **104.59s** after its cleanup gate
passed **1,476 tests and 3 subtests**. Its earlier failure artifact remains
`/var/tmp/onpc-ui-preview-hwdx5t6z`.

The exact reordered frozen selection was then run without source edits:

```sh
tools/run-ui-tests --timeout 3600s -v -x --tb=short 'tests/ui/test_preview_smoke.py' 'tests/ui/test_automation_identity.py' 'tests/ui/test_e2e_accessible_adapter.py::test_standard_user_startup_denial_has_specific_public_result' 'tests/ui/test_e2e_accessible_adapter.py::test_empty_parent_functional_adapter_at_display_scales' 'tests/ui/test_e2e_accessible_adapter.py::test_parent_functional_adapter_at_display_scales' 'tests/ui/test_screen_preview.py' 'tests/ui/test_about_release.py' 'tests/ui/test_parent_feedback.py' 'tests/ui/test_error_feedback.py' 'tests/ui/test_control_overflow.py' 'tests/ui/test_request_form_component.py::test_responsive_form_accepts_semantic_selection_and_submission' 'tests/ui/test_request_form_component.py::test_expanded_form_keeps_request_reachable' 'tests/ui/test_request_form_component.py::test_footer_estimate_tracks_custom_edits_and_preserves_validation' 'tests/ui/test_request_form_component.py::test_mute_control_stays_hidden_with_remembered_preferences' 'tests/ui/test_request_layout.py'
```

Its cleanup gate passed **1,476 tests and 3 subtests**. All **79 UI cases passed
in 2739.98s (45:39)**, including both Parent scales, inherited sensitivity,
screen custom-dimension recovery, all About/feedback/overflow cases, both shared
request forms, the recovered kiosk pre-action read and every layout case. The
run's pytest evidence root is `/var/tmp/pytest-of-edgar/pytest-1244`; relevant
retained files include
`test_parent_loading_state_disa0/loading-public-state.json` and
`test_request_error_review_rest0/request-False-service-failure.jsonl` beneath
that root. Earlier incomplete-read evidence remains in
`/var/tmp/onpc-ui-preview-7a9hsyi8/parent-public-state.json` and
`/var/tmp/onpc-ui-preview-79o91fhz/parent-public-state.json`.

O1–O3 and R1 are closed in task 02's inventory. Settings D5, external terminal
return D3 and child Shell consumer L9 remain assigned to their existing later
tasks and were not qualified here. Parent task 02 remains incomplete until 02b.
No VM, installation, portal, broad-suite, staging or commit operation was
performed.

## Previous implementation checkpoint (superseded)

The shared GTK focus implementation publishes `focus.<automation-id>` on the
nearest identified native window/dialog, then reacquires and verifies the
target. Both screen-preview variants passed in a frozen run, including custom
dimensions, invalid-input recovery and cancellation. Evidence:
`/var/tmp/onpc-ui-preview-279imxro` (kiosk) and
`/var/tmp/onpc-ui-preview-siangq86` (child overlay). Preserve earlier failure
artifacts below. Do not edit sources during preview runs: previews reload on
source changes and invalidate the run.

Application/surface and per-application launch-owner binding, strict fresh
absence, selected-account UID readback and missing-fixture handling remain in
place. New negative coverage includes dialog owner relations, Shell tooltip/menu
sibling scoping, duration selection/availability and focus-target disappearance.
Focus now keeps input uncertainty latched if post-action reacquisition raises.
Feedback dismissal callers explicitly declare their surrounding surface; the
retained remembered-mute test now uses complete absence on both request forms.

The station failure at `/var/tmp/onpc-ui-preview-f3jqk3ta` was mechanical.
A diagnostic rerun at `/var/tmp/onpc-ui-preview-rnxej1pb` showed all eight duration
buttons had `CHECKED=false`, only 1800 had `PRESSED=true`, and all were disabled.
The reader and doubles now use `PRESSED` for duration toggles, retaining exact
selection and all availability/custom/notice/mute assertions. The live station
projection passed twice afterward. Switch/checkbox checks still use `CHECKED`.

Dialog publication needed `Gtk.AccessibleList.new_from_list(children)` for
`CONTROLS`: an ordinary Python list produced a `G_VALUE_HOLDS_POINTER` warning
and no public inverse owner (`/var/tmp/onpc-ui-preview-t_vygtz5`). GTK supplies
`CONTROLLED_BY`. Public feedback/About ownership and unmap removal now pass;
nested privacy ownership and draft reopening passed too. The narrow command
below passed **2 tests**; logs at `/var/tmp/onpc-ui-preview-ceenkymm` and
`/var/tmp/onpc-ui-preview-1he6bjxz` contain no warning:

```sh
tools/run-ui-tests --timeout 600s -q -x --tb=short 'tests/ui/test_automation_identity.py::test_parent_feedback_and_about_publish_public_ids' 'tests/ui/test_parent_feedback.py::test_feedback_draft_and_optional_attachment'
```

`Frontends.md` now describes native focus, boxed relation publication, fresh
absence, selected UID IDs and toggle-state mapping. Terminal return remains
explicitly unqualified under D3/task 04. Final inventory closure still waits for
the remaining owned UI verification.

Latest focused units: **567 passed, 21 subtests passed**:

```sh
tools/run-unit-tests -q --tb=short 'tests/unit/test_automation_ids.py' 'tests/unit/test_accessible_e2e_ui.py' 'tests/unit/test_mutter_input.py' 'tests/unit/test_ui_cleanup_safety.py' 'tests/unit/test_support.py' 'tests/unit/test_e2e_kiosk_entry.py' 'tests/unit/test_e2e_terminal.py' 'tests/unit/test_kiosk_rendering.py' 'tests/unit/test_parent_main.py'
```

Latest frozen owned UI selection stopped at **8 passed, 1 failed**, after the
automatic cleanup gate passed **1,476 tests and 3 subtests**:

```sh
tools/run-ui-tests --timeout 2400s -v -x --tb=short 'tests/ui/test_automation_identity.py' 'tests/ui/test_e2e_accessible_adapter.py::test_standard_user_startup_denial_has_specific_public_result' 'tests/ui/test_e2e_accessible_adapter.py::test_empty_parent_functional_adapter_at_display_scales' 'tests/ui/test_e2e_accessible_adapter.py::test_parent_functional_adapter_at_display_scales' 'tests/ui/test_screen_preview.py' 'tests/ui/test_about_release.py' 'tests/ui/test_parent_feedback.py' 'tests/ui/test_error_feedback.py' 'tests/ui/test_control_overflow.py' 'tests/ui/test_request_form_component.py::test_responsive_form_accepts_semantic_selection_and_submission' 'tests/ui/test_request_form_component.py::test_expanded_form_keeps_request_reachable' 'tests/ui/test_request_form_component.py::test_footer_estimate_tracks_custom_edits_and_preserves_validation' 'tests/ui/test_request_form_component.py::test_mute_control_stays_hidden_with_remembered_preferences' 'tests/ui/test_preview_smoke.py' 'tests/ui/test_request_layout.py'
```

The selection collected 79 cases. All four identity cases, both denial dismissal
cases and both empty-Parent scales passed. The next case,
`test_parent_functional_adapter_at_display_scales[1.0]`, failed at
`ui.run('about', version)` after its preceding picker/settings checks. The stack
is `open_about → about → id_target → find_id → find_all_ids → nodes(strict=True)`;
a null node raised `ui:incomplete-tree`. Artifact:
`/var/tmp/onpc-ui-preview-7_1qts0i`; the application log is empty. A dbind GetItems
warning also appeared in captured output. Diagnose the fresh observation and
actual public state before classifying the failure. Preserve complete absence,
ownership and all behavioral checks; do not simply ignore incomplete trees.
The second Parent scale and all later cases did not execute in this run.

No tests remain running at handoff; the last run exited 1 before the handoff
request was handled. No staging or commits were performed by this session.
The index changed externally between initial preflight reads, then stayed at
`364fce9585a28299c8c58367759a080a466789141fcac9ac3f7d9298a7056368`
during implementation/testing. At final handoff checks it changed externally
again to `082f290313cae8a6b611b9fdba1ec9fbb83fb8f0a1251764f3d76e566d71720f`;
inspection confirmed the source fixes were now staged, with only checkpoint/
inventory/README updates unstaged. No index-restoring action was taken.
Preserve the actual current index rather than restoring an earlier checksum.
Resume 02a, then advance to 02b only after its completion checks pass.

## Frozen remaining scope

Resolve inventory **O1–O3** and finish R1's host exposure review. Preserve the
current surface-scoping, live launch-owner checks, form-local controls and
UID collection changes. Inspect the current diffs/index before editing; the
previous session's checksum is evidence, not a target to restore.

Start with the concrete shared focus/reveal blocker: the final screen-preview
run in task 02 passed six cases and failed both custom-dimension variants.
`row.activate` successfully reveals the fields, but focusing
`preview-screen-width` fails before typing. GTK's
[AT-SPI component provider](https://gitlab.gnome.org/GNOME/gtk/-/blob/gtk-4-22/gtk/a11y/gtkatspicomponent.c#L189)
rejects both `GrabFocus` and `ScrollTo`; audit all owned GTK consumers of these
operations. Provide supported native focus/reveal through public ID-addressed
owned controls or supported normal keyboard navigation, preserving ownership,
reachability and uncertain-input guards. Do not substitute geometry, roles,
labels, tree positions or an already-focused unrelated control. GTK Entry uses
a [specialized Action interface](https://gitlab.gnome.org/GNOME/gtk/-/blob/gtk-4-22/gtk/a11y/gtkatspiaction.c),
so adding a Gio action group directly to an entry does not by itself establish
public action exposure. Verify the chosen contract through live AT-SPI.
Keep the working `row.activate`, independent custom-field observation and all
invalid-dimension/recovery checks. Preserve artifacts
`/var/tmp/onpc-ui-preview-immxx3ih` and
`/var/tmp/onpc-ui-preview-bmt94obi`.

1. Trace owned guest entry points and every direct host adapter construction.
   Enforce the intended application and surface before accepting controls or
   result windows. The guest `find_id` primitive still permits desktop-wide
   searches, and preview `owner_pids` is a set of live launch handles, not a
   complete binding of each shared dialog to its intended originating surface.
   Check every namespace binding against real containment, including child
   tooltip/menu actors that may be siblings rather than indicator descendants.
   Preserve shared child/kiosk IDs. Resolve ownership using supported public
   identity/relationships and recorded launch metadata; never names, titles,
   frame roles, private product state or process discovery. Add required owned
   IDs in product code before consumers. Missing owned IDs are not provider gaps.
2. Close absence/closure gaps: `Automation.nodes` currently ignores query errors,
   so `find(...) is None` or `not showing(...)` can mistake an incomplete tree
   for disappearance. Add complete fresh negative observations with an explicit
   positive ID-addressed surrounding surface. Migrate owned callers, including
   feedback dialogs/attachments, Parent popup, About return and denial closure.
   Keep the single-lookup feedback close race correction. For the terminal/help
   return boundary, define the owned side and leave the external provider work
   explicitly in D3/task 04; do not accept silence as a surrounding surface.
3. Audit `focus`'s already-focused shortcut and action/reveal freshness. It must
   not accept an arbitrary focused node before checking its UID identity and
   owner. Reacquire IDs after reveal/focus, preserve independent picker focus
   readback and the separate Enter commit. Keep existing wrong-account,
   ambiguous, unreachable and uncertain-input checks.
4. Publish selected child/approver UID identities in
   `AccountDropdown.set_items/set_selected` before changing
   `AccessibleUI.kiosk_request_form`. Current choice buttons have explicit UID
   IDs, but selected projection still derives account identity from the
   selector description. Read selected identity by ID, then verify description
   as meaning. Preserve both request surfaces and all current duration,
   availability, custom-input, notice and mute assertions.
5. R1's retained `choice_order(...child-picker-order)` now selects UID IDs and
   ignores nested `-content` IDs. Verify actual public exposure/order and the
   contract for unrelated accounts without inventing positional identities or
   dropping existing cardinality/duplicate/stale checks. The collection result
   must never calculate input counts.
   Also handle fixture accounts that have not yet been created: the current
   retained collection resolves the entire fixture UID map before reading its
   rows, so an absent new-child account currently refuses the collection.

All external discovery, prompt middleware and legacy transport still belong to
03–05. Do not reuse those paths while resolving owned controls. In particular,
`test_installed_settings_users_publishes_builder_ids` (D5) remains unqualified;
do not run that case until task 04 contains/migrates it.

## Verification and completion

Run the exact focused seven-file unit selection recorded in task 02, adding any
changed product/control tests. Use host UI tests only after the automatic
cleanup gate. Run the affected owned files/nodes, including shared request
form, feedback/error/About, Parent picker/empty/denial and overflow. Verify all
new IDs through public AT-SPI; string/source tests cannot establish exposure.
The complete eleven-file run still belongs to task 08 after D5 is resolved.

Preserve task 02's failed-run artifacts and original behavioral assertions.
Report actual final statuses, artifacts and any remaining safety blockers.
Update O1–O3/R1 in the existing inventory, then mark this brief complete and
advance the README pointer to 02b. Do not mark parent 02 complete or execute 02b
in the same session. Apply shared diff/link/index-preservation close checks.
