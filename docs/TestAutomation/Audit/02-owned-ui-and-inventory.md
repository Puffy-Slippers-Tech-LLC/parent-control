# 02 — Inventory callable paths and finish owned UI identity

**Recommended model: GPT-6 Astra. Effort: high.** This slice needs cross-layer
identity review and a complete accounting of reachable legacy paths.

**Prerequisite:** [01](01-legend-expansion.md) and [shared preflight](README.md).
**Status:** Complete; inventory and owned-identity slices 02a–02b are closed.
**Next:** [03](03-authentication-surfaces.md).

## Scope and work

Read [public guest adapter](../../../tests/e2e/accessible_ui.py),
[preview adapter](../../../tests/support/accessible_ui.py),
[automation contract](../../../tests/support/automation.py),
[preview launch](../../../tests/support/preview.py), and relevant product ID
definitions. Trace callers across `tests/e2e`, `tests/support`, `tests/ui`,
`tests/integration` and the launch/setup helpers. Include exported operations,
middleware, fallback/error/absence paths and retained entry points, even when
their scenarios are pending. Text search is a lead, not proof of compliance.

Maintain a compact current inventory in this brief: callable symbol, caller or
consumer, owning application/surface, selector/input mechanism, required ID,
disposition, and responsible task. Seed it with these families:

| Family | Initial condition to review | Owner |
| --- | --- | --- |
| Parent, About, denial, empty state, picker and popup absence | Recent ID edits need review and verification | 02 |
| Shared request form, kiosk, feedback and child controls | Preserve shared IDs and explicit account identity | 02 |
| Preview readiness, `wait_for_application`, Mutter keyboard/click entry | ID readiness, owned launch and coordinate refusal must survive | 02 |
| GDM, password recipient, Polkit/keyring middleware | Legacy selectors and recipient proofs need migration | 03 |
| Desktop/session/search, terminal, document viewer | Legacy selectors and provider mappings need migration | 04 |
| Perl image/pointer callers and `shell_overview.set_overview` | Prohibited routes remain callable | 05 |
| GUI fixture instances, native owner and runtime payload | Identity/lifecycle/mechanical review pending | 06 |

Resolve owned product/preview findings in this task; assign external and transport
findings to 03–05 without duplicating implementation. Audit any additional surface
against the existing provider catalogue, including file choosers/editors if found.
Record an explicit owner for every new finding before ending the session.

Verify recent changes to empty explanation reads, UID-scoped popup absence and
`parent-access-denied-window`. Preserve independent picker focus readback and
separate Enter commit, explicit child/approver identities, and ambiguous/wrong
surface refusal. Add missing product IDs through public accessibility before
implementing consumers; never place owned-product gaps in the provider backlog.

Check preview launch defaults return their owned process/log, name-based
application discovery is absent, `wait_for_application=True` refuses before
spawning, and `mutter_input.click_at` refuses before backend access. Preserve
normal keyboard delivery and disconnect-failure checks. Keep readiness owned by
the calling ID adapter and cleanup safe after discovery failure.

## Verification and completion

Use focused units first, including:

```sh
tools/run-unit-tests -q 'tests/unit/test_automation_ids.py' 'tests/unit/test_accessible_e2e_ui.py' 'tests/unit/test_mutter_input.py' 'tests/unit/test_ui_cleanup_safety.py' 'tests/unit/test_support.py'
```

Add changed owned-surface unit files to the literal selection. Where an owned ID
or interaction changes, run its relevant host UI file through `tools/run-ui-tests`
after the automatic safety gate. Source/string checks alone cannot establish
public exposure. Keep all final files in task 07/08's verification scope.

Complete when each reviewed entry has a disposition and owner, owned gaps are
fixed and checked, and no route is called compliant merely because it is unused
or has old passing tests. Record the number of unresolved paths by family;
subsequent tasks reduce this same scope rather than starting a replacement audit.

## Current callable inventory

Inventory reviewed on 2026-09-19. A row is a bounded call-path group, not a
scenario count or a count of individual functions. Symbols below are in
`tests/e2e/accessible_ui.py` unless a different file is named. `run` exports its
registered operation families through `UiObservations.observe` and the
`onpc_*.pm` workers under `tests/integration/graphical_smoke/lib`; direct imports,
unit harnesses and retained entry points also remain in scope. No pending
scenario is an execution guard. All external return conditions are in the
[provider catalogue](../E2E-Building-Blocks.md#functional-validation).

| Key / callable path | Caller or consumer | Owner / required public identity | Current mechanism and disposition | Task |
| --- | --- | --- | --- | --- |
| O1 `parent`, `about`, `open_about`, `settings`, `parent_page`, `parent_empty`, `child_id_control`, `focus`, `open_child_picker`, `child_highlighted`, `selected_child`, `read_label`, About branches of `window_ready_to_close`/`window_closed`, `management_denied`/`management_absent` | Parent discovery, About, terminal refusal; host adapter tests | Parent application; `parent-window`, `about-dialog`, `parent-access-denied-window`, UID-scoped child IDs | **Complete (02a).** Both full Parent scales, empty/denial and About return pass. Transient incomplete reads are wholly discarded within bounded waits; effective inherited sensitivity, complete ownership/absence and separate focus/readback/Enter passed the final 79-case run. This closes the owned denial side only; D3's external terminal return remains unqualified. | Complete (02a) |
| O2 `Automation.find_all/find/target/state/text/content/focus/reveal/activate`; `feedback_editor`, `type_feedback`, `dismiss_feedback_dialog` | All twelve host files; `child_shell_interaction` | Product window/dialog IDs from `owned_surface_id`; rich editor's WebKit `id` | **Complete for owned 02a scope.** Ownership, feedback/error/overflow, effective DISABLED publication, strict complete negative observations and bounded complete-tree pre-action retry passed. Ownership, ambiguity, missing-ID and input failures remain immediate; input dispatch remains single-shot. D5 and L9 have their recorded dispositions. | Complete (02a); D5/L9 recorded |
| O3 `kiosk_request_form`, `AccountDropdown.set_items/set_selected` | `kiosk_entry`, request-form host tests | `kiosk-request-form` and explicit child/approver UID identities | **Complete (02a).** Station projection, both shared forms' selected UID exposure, submission/validation, error feedback and remembered-mute absence pass. Exact duration selection continues to use GTK ToggleButton `PRESSED`. | Complete (02a) |
| O4 `e2e_watch_window_probe.inspect`, `test_e2e_watch.run_probe`, `e2e_watch_viewer.application` | Spectator branch in `tools/regression_ui.py`, including retained live variants | `org.onpc.E2EWatch`; `e2e-watch-window`, progress, status, display, output and close IDs | **Complete (02b).** The shared scoped adapter binds the declared application to the recorded preview PID. Waiting, progress, status, bounded VTE output, same-window retention/resumption, timer advance and close use public IDs and semantic action. Frame/cursor format, line layout/ellipsis, terminal color/read-only state and resize isolation remain mechanical checks. Cosmetic titles no longer gate. Live variants retain the same ID path but were not executed. | Complete (02b) |
| R1 `choice_order(...child-picker-order)` | Retained direct adapter entry; `test_child_collection_uses_an_independent_current_list` | `parent-child-choices`, `parent-child-choice-<uid>` | **Complete (02a).** UID collection passed at both Parent scales, ignores nested content IDs, tolerates not-yet-created fixture accounts and refuses unregistered rows. Duplicate/stale/cardinality guards remain; output order never calculates input. | Complete (02a) |
| R2 `preview_applications.launch`, `launch_request`, `boot_preview_session` | `launch_ui`, request fixtures, nested compositor setup | Explicit Popen handles and caller's public surface ID | Default returns process/log; forbidden name-based readiness refuses before spawn. Added live owned PID projection, retained reverse owned cleanup and spawn/discovery-failure cleanup. | 02; final checks 07 |
| R3 `mutter_input.press_key/reconnect/click_at` | `child_shell_interaction`, retained imports | ID-proved keyboard recipient; no coordinate target permitted | Keyboard delivery/disconnect checks retained; coordinate entry refuses before backend access. L9 now binds the caller to its owned request-button ID without direct overview state. | Complete (02/05) |
| R4 `main`, `greeter_account`, `session_environment`, `observation_environment`, `reset_atspi_client` | `UiObservations` fixed guest command | Explicit fixture UID and owned public bus; actual UI still needs IDs | Account/connection setup is transport metadata, not customer readiness. Preserve active local greeter selection, privilege drop, owned-socket checks and kiosk's observer reset; review alongside A1/O1. | 03 / 02a |
| A1 `greeter_list/navigation/prompt`, greeter `observe_absence`, retired greeter `choice_order`, GDM branches of `run` | GDM workers, serial return, kiosk entry | GDM app/greeter/account-list/account/recipient/password IDs | **Contained (03).** Every callable preflights the complete mapping before traversal, scopes lookup by IDs and uses semantic row focus. Labels/states only verify the ID target; positional collection/navigation refuses. Installed GDM remains provider-blocked. | Complete (03); provider blocked |
| A2 `password_recipient`; `fixture_credentials`; functional `onpc_password` recipient proofs | Parent/standard login and wrong-recipient qualification | GDM/Polkit app/surface/recipient/empty masked field IDs | **Contained (03/05).** The selected-recipient/password IDs own the sole focused, enabled, showing, empty masked-field proof. Wrong-recipient refusal, two fresh checks, secret sealing/single use and uncertainty latches passed unchanged. Legacy masked-image callers now refuse under L6/L7. | Complete (03/05); provider blocked |
| A3 `system_prompt_control/absent/handle_system_prompt`, `wait`, `run` preamble | Every non-greeter operation with prompt middleware; retained refusal entry point | gcr/keyring and Shell Polkit app/dialog/cancel/secret/recipient IDs | **Contained (03/05).** Both mappings preflight before traversal. Qualified keyring Cancel uses one semantic action and ID-scoped complete disappearance; Polkit presence and unknown/unqualified paths refuse. Worker coordinate emission and controller dispatch are removed; retained coordinate entry points refuse before acknowledgement/input. | Complete (03/05); provider blocked |
| D1 `desktop_result`, `session_menu_toggle/power/menu`, `choose_session_action`, `logout_confirm` | `onpc_desktop_session`, login/terminal workers | Shell desktop/panel/session menu/action IDs | **Contained (04/05).** Every adapter entry preflights the Shell application mapping and scopes qualified doubles through desktop, panel, session-menu or confirmation surface IDs. The controller performs semantic actions and exports no geometry; retained pointer entry points refuse. | Complete (04/05); provider blocked |
| D2 `launchable_result`, `search_query/ready/result/absence`, `wait_search`, `search_diagnostic`, search branches of `read_label`/`run` | Parent launch/access, `onpc_parent`, nested `e2e_search_probe` | Shell overview/search/result/web-suggestion IDs | **Contained (04/05).** Query, focus, launchability, web witness and stable launcher/window absence are ID-scoped; text/roles only verify identified nodes. Diagnostics report only identified logical controls. Missing application IDs refuse before traversal, including the retained nested probe. L5/L9 record the final input dispositions. | Complete (04/05); provider blocked |
| D3 `terminal_input/focus_terminal/help_terminal_text/help_shell_prompt/help_content/help_product_absent`, terminal/help `run` branches | `onpc_terminal`, `onpc_parent_terminal`, `onpc_command_help` | Terminal app/window/input-output IDs; product root IDs for exclusion | **Contained (04/05).** The registered terminal surface and input/output ID own active/focused input, bounded output and complete return/absence checks. Wrong-surface, duplicate, inactive and missing-provider cases refuse; product exclusion remains by product IDs. L10 records the final keyboard-input disposition. | Complete (04/05); provider blocked |
| D4 `license_content/read_document/open_license`, license branches of window close/return | `onpc_parent_about`, ABOUT02/03 | Registered viewer app/window/document/close IDs | **Contained (04/05).** The complete viewer mapping is required before the owned license link can launch its destination. Content, active-window readiness and complete return use viewer surface/document/close IDs plus the owned About destination; title/frame discovery is removed. L10 records the final close-input disposition. | Complete (04/05); provider blocked |
| D5 `test_installed_settings_users_publishes_builder_ids` | Host adapter file included in task 08 | Settings app/surface/search and Users IDs | **Contained (04).** The host probe records partial installed Builder IDs without activating `search_button` or any other Settings control. Its narrow run passed after the cleanup gate; the absent application/surface chain remains a provider blocker. | Complete (04); provider blocked |
| D6 `find_provider_control` catalogue entries for choosers, Files, archive, editor, PDF viewer and Settings date/time | FILE03–09, FEED06/08, ACCOUNT01/02, TIME05 | Exact native/portal/provider app/surface/control contracts in catalogue | **Contained (04).** Shared lookup still refuses every incomplete mapping before traversal. No additional executable chooser/editor selector was found; all named consumers and return conditions remain pending in the provider catalogue. | Complete (04); provider blocked |
| L1 `find/target/reveal/scroll_target/find_labelled_control/find_labelled_button/labelled_button`, raw-node action helpers | A1–D4 and direct retained unit callers | Registered scoped public ID for every route | **Complete (05).** Generic label/role entry points refuse before traversal. Functional paths resolve registered IDs first; bounded text/role projections only verify already identified nodes. | Complete (05) |
| L2 `pointer_target/pointer_glyph/stable_pointer`, `UiObservations` pointer validation, installed-journey `ui_pointer` dispatch | Session/search workers; former prompt rendezvous | Semantic action on identified control, no coordinates | **Complete (05).** Geometry helpers and coordinate observations refuse; coordinate payload production and installed dispatch are removed. | Complete (05) |
| L3 `onpc_journey.observe/seen/navigate_choice/service_system_prompt/click_target` | All graphical worker families, review branch too | ID observation/action and independent focus proof | **Complete (05).** Image observation, positional navigation, prompt-coordinate and pointer entry points refuse before acknowledgement or input. `seen` remains the ordered ID-adapter rendezvous; highlighting accepts only fresh semantic focus evidence. | Complete (05) |
| L4 `onpc_pointer.click` | Legacy Parent and GDM helpers | ID target/action | **Complete (05).** The retained callable refuses before image matching, framebuffer/backend access or input. | Complete (05) |
| L5 `onpc_parent.login/login_standard/open_app_grid/launch_from_app_grid/select_existing_child` | Retained smoke routes | GDM/Shell IDs and Parent UID choices | **Contained (05).** Legacy image/pointer routes refuse. Functional search preflights the Shell mapping and uses semantic ID focus; child selection retains UID-scoped focus/readback and Enter. | Complete (05); provider blocked |
| L6 legacy `onpc_gdm.wait_list/select_parent/dismiss_prompt/return_from_serial/return_after_reboot/reattach_after_setup/inspect_installed_parent/inspect_installed_standard/_return_from_serial`; `onpc_password.enter_password` | Smoke qualification, legacy Parent, serial return | GDM recipient/control IDs | **Contained (05).** Legacy GDM and image-secret entry points refuse before backend/secret/input. The functional GDM route remains blocked on its provider mapping; serial authentication remains separate. | Complete (05); provider blocked |
| L7 `onpc_vt6.authenticate/inspect_prompt` | `smoke.pm`, VT6 unit harnesses | Supported public account, recipient and secret-field IDs | **Contained (05).** Both graphical-console entry points latch once and refuse before console/image/secret/input. Return requires an installed ID-scoped recipient/input implementation; serial proof cannot qualify VT6. | Complete (05); provider blocked |
| L8 `smoke.pm.run/capture` direct image/click/key branches | Graphical smoke dispatcher and qualification modes | Same GDM/desktop identity contract as consumers | **Complete (05).** Capture and every nonfunctional legacy mode refuse before console/image/input; registered high-level functional routes remain. | Complete (05) |
| L9 `shell_overview.set_overview`, `child_shell_interaction._prepare_indicator_input/_activate_repeatedly/main/_overlay_surfaces/_overlay_closed` | Nested child interaction scenario and `tests/support/child_shell.py` launcher | Owned `child-request-button`, `child-countdown-menu`, overlay window/control IDs | **Complete (05).** Direct Shell state manipulation refuses. The nested child route resolves and semantically focuses its owned request-button ID before normal keyboard input while retaining owned-process, single-flight, one-overlay and reopen checks. | Complete (05) |
| L10 `onpc_parent_about.read_footer/close_window`, `onpc_terminal`, `onpc_command_help` and session/kiosk worker keys | About/footer, denial, help, switch/logout, station entry | Fresh ID-addressed active/focused recipient | **Contained (05).** Footer reachability uses semantic ID reveal; session operations use semantic ID actions. Remaining close, terminal, search and kiosk keys require a fresh ID-scoped active/focused recipient and remain blocked when the external provider mapping is absent. | Complete (05); provider blocked |
| F1 `FixtureUI.target/text/focus_draft/submit/move/closed`, `test_fixture_gui` | Native/game/Flatpak/Snap independent instances | `onpc-fixture-<kind>-<instance>` and child control IDs | Scoped IDs and public action/readback exist; ownership, closure/absence and native child lifecycle review pending. | 06 |
| F2 `onpc_test_application.c`, `gui_application.py`, `gui_runtime.py`, `build_test_applications.py` | Runtime payload tests, system enforcement mechanical fixture, setup prerequisites | Native executable/owned child, GUI instance IDs, separate mechanical fixture | Preserve offline payload closure, independent instances, mechanical marker and `installed_qualified=false`; review pending. | 06 |

Frozen remaining groups: **owned 0, authentication 0,
desktop/external 0, legacy/transport 0, fixture 2 (F1–F2)**.
D1–D6 are contained on recorded provider blockers, with live consumers pending;
the legacy rows are closed or safely provider-contained. R1–R4 record
implemented work without subtracting their unresolved caller obligations. O1–O4
are closed; their final broad verification remains assigned to tasks 07–09.
Later tasks update these keys, not a replacement inventory.

## Session evidence and split

The starting worktree and index were clean; index SHA256 was
`cc1942cf9382a62870390d3e171113f6e3ae6a5ed5746de378ba33c421494859`.
The expanded audit includes shared negative-read/ownership contracts and the
previously unlisted spectator consumer. Their remaining work is split into 02a
and 02b so neither becomes an unassigned owned-product/provider backlog item.
Both follow-up slices are complete; task 03 follows them.

Focused command:

```sh
tools/run-unit-tests -q 'tests/unit/test_automation_ids.py' 'tests/unit/test_accessible_e2e_ui.py' 'tests/unit/test_mutter_input.py' 'tests/unit/test_ui_cleanup_safety.py' 'tests/unit/test_support.py' 'tests/unit/test_e2e_kiosk_entry.py' 'tests/unit/test_e2e_terminal.py'
```

Initial final focused result: **450 passed**, including the additional live-launch-owner
and nested UID-content regressions. The earlier expanded invocation had 434 passed and one
mechanical double failure: the WebKit node lacked its now-required
`feedback-dialog` container. Adding that container retained the same transient
AX-ID/duplicate-ID assertions; no product behavior expectation changed.
An initial five-file invocation's final output was not retained and is not
counted; the complete seven-file invocation supersedes it.

The first whole adapter-file UI invocation was cancelled during its cleanup
gate (exit 130), before UI execution, after identifying D5. The selected owned
invocation uses literal test nodes, leaves D5's assertions intact, and does not
qualify external Settings or nested Shell search:

```sh
tools/run-ui-tests --timeout 1200s -q 'tests/ui/test_automation_identity.py' 'tests/ui/test_e2e_accessible_adapter.py::test_standard_user_startup_denial_has_specific_public_result' 'tests/ui/test_e2e_accessible_adapter.py::test_empty_parent_functional_adapter_at_display_scales' 'tests/ui/test_e2e_accessible_adapter.py::test_parent_functional_adapter_at_display_scales'
```

Cleanup prerequisite: 1,475 passed and 3 subtests passed. UI result: **8 passed,
1 failed**. Failure artifact: `/var/tmp/onpc-ui-preview-x4lnvsz0`. The feedback
dialog disappeared between an existence query and a second state query, which
raised `automation:missing-public-id:feedback-dialog`. Replaced that mechanical
check-then-query race with the existing single-lookup `showing` helper; expected
dialog closure is unchanged. O2 still requires strict negative observations.

The following affected checks are rerun on that correction and the final
focused-unit implementation:

```sh
tools/run-ui-tests --timeout 1200s -q 'tests/ui/test_automation_identity.py' 'tests/ui/test_about_release.py' 'tests/ui/test_request_form_component.py::test_responsive_form_accepts_semantic_selection_and_submission' 'tests/ui/test_request_form_component.py::test_expanded_form_keeps_request_reachable' 'tests/ui/test_screen_preview.py'
```

Rerun: **16 passed, 2 failed**; cleanup gate **1,476 passed, 3 subtests passed**.
Both failures were `automation:ambiguous-action:preview-screen-resolution-custom`
in the two screen-dialog variants, after the dialog and 125% scale choice had
been identified and operated successfully. Artifacts:
`/var/tmp/onpc-ui-preview-hc_1x4ie` and
`/var/tmp/onpc-ui-preview-0gznzidv`. The row is `Gtk.ListBoxRow`; the test assumed
a sole action. The first attempted correction used ID-reacquired semantic focus
and normal Enter, independently observed the custom fields, and retained invalid-dimension,
error-message, usable-action and cancel assertions. No action fallback or
uncertain-input replay was added.

Passing feedback identity retry artifact:
`/var/tmp/onpc-ui-preview-svjcn6ij/parent_component_preview.log`.
Shared request identity logs:
`/var/tmp/onpc-ui-preview-l2g8trv8/kiosk_preview.log` and
`/var/tmp/onpc-ui-preview-xw4ve4an/child_overlay_preview.log`.

Final affected retry command:

```sh
tools/run-ui-tests --timeout 1200s -q 'tests/ui/test_screen_preview.py'
```

Keyboard retry: **6 passed, 2 failed**, after **1,476 passed and 3 subtests
passed** in the cleanup gate. Both variants' `component.grab_focus()` raised
`GLib.GError` before Enter. Artifacts: `/var/tmp/onpc-ui-preview-j7l1e6gq` and
`/var/tmp/onpc-ui-preview-sw2y4uzq`. This route was not accepted or retried after
uncertain input. The final implementation instead publishes `row.activate` in
the owned GTK accessibility helper, emitting GTK's documented native row
activation signal. The test explicitly selects that action and independently
requires the custom fields before its unchanged validation/recovery assertions.

After the product helper change, reran the seven focused files above plus
`tests/unit/test_kiosk_rendering.py` and `tests/unit/test_parent_main.py` in the
same `tools/run-unit-tests -q` invocation: **529 passed, 21 subtests passed**.
Final screen-preview retry: **6 passed, 2 failed**; cleanup gate **1,476 passed,
3 subtests passed**. Both variants successfully activate `row.activate` and
observe the custom fields, then `ui.focus("preview-screen-width")` raises
`GLib.GError` from `component.grab_focus()`. Artifacts:
`/var/tmp/onpc-ui-preview-immxx3ih` and
`/var/tmp/onpc-ui-preview-bmt94obi`. No dimension input was entered; the
invalid-dimension and recovery assertions remain unpassed, not waived.

GTK's [AT-SPI component implementation](https://gitlab.gnome.org/GNOME/gtk/-/blob/gtk-4-22/gtk/a11y/gtkatspicomponent.c#L189)
returns `G_DBUS_ERROR_NOT_SUPPORTED` for both `GrabFocus` and `ScrollTo`.
Task 02a must resolve this shared owned-control focus/reveal contract before
rerunning the blocked cases; merely selecting the correct row action does not
complete the interaction. Preserve the working row action and failure evidence.
All recorded test invocations have finished; no suite is left running.
All modified files remain in tasks 07/08's final verification scope. No external
provider, installed customer journey or fixture runtime was qualified here.

Task 02b published the spectator IDs, registered its preview application owner,
and moved its normal functional reads and close action to the shared scoped
adapter. Focused watcher/protocol/activity/scheduler/cleanup and adapter units:
**303 passed**. The synthetic non-live UI run's automatic cleanup gate passed
**1,476 tests and 3 subtests**; its selected result was **1 passed, 2 live-E2E
variants deselected**. The passing preview log is
`/var/tmp/onpc-ui-preview-t_5g7sav/e2e_watch_window_probe.log`. The two live
variants remain explicit obligations requiring an independently active E2E run;
they were not executed and no VM or installed customer acceptance is claimed.
