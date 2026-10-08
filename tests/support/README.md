# Shared test support

Start here before adding fixture code. These are opt-in helpers on top of
pytest, unittest, Hypothesis, Gio, Dogtail and the existing language runners.
Tests own scenarios and assertions; helpers own repeated setup, transport and
cleanup. [Architecture regressions](../unit/test_support_architecture.py) prevent
helpers and test cases from importing collected case modules.

Temporary storage follows the
[test storage mandate](../../docs/Mandates/Test-Storage-Mandate.md): use the
shared allocation helpers, never a producer-selected `/tmp` or custom root.

## Find an existing helper

| Need | Reuse | Contract |
| --- | --- | --- |
| Temporary storage and retained evidence | [test_storage.py](../../tools/test_storage.py), [test_retention.py](../../tools/test_retention.py) | Launchers configure disk scratch for pytest fixtures. Retained evidence uses a registered allocation in its owning journal; short sockets use `short_runtime` or `runtime_directory`. |
| Checkout paths and script imports | [paths.py](paths.py), [modules.py](modules.py) | Normal imports use `pyproject.toml`'s `pythonpath`. `load_module(name, path)` loads a fresh standalone script with a unique test-only name; failures restore the registry. |
| Broker configuration and recording adapters | [configuration.py](configuration.py), [broker.py](broker.py) | Fresh mutable state, explicit clocks/callbacks/failures and no OS calls. |
| Unit orchestration without GTK construction | [objects.py](objects.py) | Bind actual class methods to explicit state instead of copying method source. |
| Private D-Bus broker | [dbus.py](dbus.py) | Import `private_service` and call/wait helpers; real Gio serialization on the component suite's private buses, with recording adapters. |
| Preview process lifecycle | [preview.py](preview.py) | `preview_applications` owns only its Popen handles/logs, enables Python's fault handler before startup imports, cleans up failed discovery, attempts every owned child and reports cleanup failures. Fatal Python/native signals leave Python thread tracebacks in the existing preview log; Python 3.14 also emits the current native stack when supported by the runtime build. `tests/ui/conftest.py` owns the compositor, accessibility and `request_display_scale` fixtures; layout/overflow tests discover scaling there instead of importing a collected case. |
| Preview event observations | [events.py](events.py) | `read_events` returns complete JSON-lines records, waits for an unfinished final line, and refuses corrupt complete records. |
| Update-required dialog | [update_required.py](update_required.py) | Parent and request previews replace only the reboot transport with a recording refusal; public modal/buttons remain real and the host is never rebooted. |
| Product UI ownership, inventory and operations | [application_ui.py](application_ui.py), [automation.py](automation.py), [accessible_ui.py](../e2e/accessible_ui.py) | Host previews and installed E2E share the Application UI API facade, owner/PID pins, scoped inventory/node projection, canonical setters and ordinary actions. Cases own finite inputs and independent outcomes. Complete observations expire before input, retries and observer resets; missing/ambiguous owners and unavailable controls refuse. |
| External GUI providers | [public_atspi.py](../e2e/public_atspi.py), [accessible_ui.py](../e2e/accessible_ui.py) | Authentication, real file choosers and supporting desktop tools retain qualified public provider observations/actions and secret-recipient guards. Product controls never fall back to this route after an API refusal. |
| Maintainer-script machines | [package_scripts.py](package_scripts.py), [shell.py](shell.py) | `package_machine` and `Machine` execute real scripts against temporary files and explicit command doubles. `Machine` binds Ubuntu/Fedora OS, hook, service and account adapters; `run_rpm` executes embedded erase callbacks and the installed abort-remove callback in an isolated shell. Removal/purge cases own their distro/action matrix; Debian package notices and PAM-selection cases stay Ubuntu-only. Path relocation alone is not a sandbox. |
| Terminal and pipe capture | [terminal.py](terminal.py) | `capture` drains output while the child runs, bounds execution and signals only its owned Popen handle. Return codes and terminal color behavior are retained. |
| Graphical Perl helper probes | [perl.py](perl.py) | `run_perl` supplies the maintained library path, captured streams and a deadline. Tests declare their public testapi doubles and assert secret exclusion. |
| Real needle pixel matching | [needle_matcher.py](needle_matcher.py) | `match_image` reuses the installed os-autoinst matcher for GDM and VT6 regressions. Synthetic mutations test refusals; they do not establish live input qualification. VT6 also requires its [exact pixel gate](../e2e/README.md#visible-vt6-installation-terminal). |
| Simulated VM baseline and lease | [vm_baseline.py](vm_baseline.py), [vm_runner.py](vm_runner.py) | Real temporary files and mocked VM operations. Import both `rig` and `lease_rig` when using the latter. Direct simulated `Lease` constructors instead request the explicitly imported `local_preparation_source` fixture, so they hash archived sources without reading the development checkout. JUnit builders retain selected identities and intentional faults. |
| Synthetic E2E evidence and provenance | [e2e_evidence.py](e2e_evidence.py), [e2e_provenance.py](e2e_provenance.py) | `attempt`, `source`, `assets` and `lease` exercise real validators with declared synthetic inputs. |
| Offline asset transfer | [e2e_transfer.py](e2e_transfer.py) | `GuestFiles` uses pytest-private files for actual upload bytes, metadata, corruption and partial-failure tests. It acquires no VM or cleanup ownership. |
| Recorder and offline credential fixtures | [e2e_recording.py](e2e_recording.py), [e2e_credentials.py](e2e_credentials.py) | Recorder `session` uses an imported evidence `attempt`; credential `attempt` can be aliased locally. Preserve privacy canaries and cleanup results. |
| Redacted authentication evidence | [authentication.py](authentication.py) | `collect_local` executes the real collector with account/OS reads replaced. |
| Catalog scope and screenshot metadata | [installed_catalog.py](installed_catalog.py), [screens.py](screens.py) | Temporary real catalog discovery; synthetic PNG headers for metadata validation, not pixel acceptance. |
| Child indicator unit adapter | [indicator.mjs](../child/support/indicator.mjs) | Fresh Node VM context and explicit platform doubles; nested-Shell tests retain real lifecycle/input coverage. |
| External desktop input delivery | [mutter_input.py](../ui/mutter_input.py) | Supporting desktop/provider operations retain their qualified input transport and owned session cleanup. Product panel and GTK controls use the Application UI API facade. |

## Host and guest boundaries

Synthetic implementation contracts remain separate from product UI operations.
`tests/ui/test_translation_widget_contracts.py` constructs helper GTK objects to
check translation weak-reference/context lifetime and native Pango attributes;
it launches no product frontend and supplies no customer API acceptance. It
reuses the existing private-display bucket without another compositor owner.
Product surface observations and input continue to use the shared Application
UI API under the [UI mandate](../../docs/Mandates/UI-Automation-Mandate.MD#application-ui-api).

Parent inherited About/feedback observations use
`AccessibleUI.parent_dialog_presentation` with explicit surface/language and
public API text/name comparisons. The `synthetic-rtl` body/reply profile remains
bounded synthetic input, read exactly before new input after reopening.
`onpc_text::replace_text` owns its normal Application UI API text operation,
including fresh owner/surface checks. Dialog checks read translated content and retained
draft values without a focus-traversal acceptance sequence.
Closing the dialog permits ordinary Parent Preferences
and reopening of the retained draft, without private translation/draft access.
These operations add no storage, process, bus or cleanup owner. Existing private
unit/cleanup fixtures and private UI preview/display classifications apply.
The fixed Parent English → Hebrew → English dialog binding passed
`check_e2e_parent_dialog_language` on Ubuntu 26.04 in
`20261005T183953Z-3eaae8af`, with all four required regressions, collection and
owned cleanup. The [catalogue](../../docs/TestAutomation/E2E-Building-Blocks.md#parent-inherited-dialog-qualification)
owns exact scope and retained reports; other frontends and complete cases remain separate.

Feedback's wrong-window close qualification distinguishes an indeterminate
negative read from a positively present dialog with `absent_id(...,
incomplete_raises=True)`. Neither releases input. The existing adapter failure
diagnostic retains only finite absence reasons, never UI text, object paths or
raw exception values. Synthetic-tree and isolated-payload regressions cover the
distinction and private-value exclusion; these use existing in-memory/private
child-process resources and do not change scheduling or cleanup ownership.

All named qualification inputs select current package sources by default through
`named_input()`; `package_source=True` remains an equivalent explicit spelling.
Fixture and upgrade consumers also include their fixture source identity.
Snapshot acquisition derives
the version from that package; preparing the current app snapshot does not
refresh an older immutable qualification bundle. The launcher builds missing
source-bound inputs and preserves valid existing bundles. Host launcher checks
cover matching consumer/preparation bindings, failed preparation before VM
dispatch and reuse without replacing inputs.

`journey_blocks.allowance_selection`, `onpc_allowance_selection::select` and
`gui_blocks.select_allowance` share one Parent allowance block.
`AccessibleUI.select_allowance` selects the canonical offered duration or
`custom` through the scoped `parent-daily-limit-selector` API value.
The retained `allowance_keyboard` observation name independently
reads the final saved value or available Custom editor. Existing preset/custom
helpers delegate to that input block; the name does not select keyboard input.
See the
[mandatory sequence](../../docs/Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception).
Cases own desired values and subsequent save/persistence assertions.
Fresh surface/child/selector identity and enabled-state checks remain.
Input errors preserve the
uncertain-input latch; readback never replays input.
Custom result observation waits for its editor to become logically available,
then uses `setText` and `activate` for normal validation and saving.
The adapter retains the same private preview display and VM lifetimes.
Unit probes use existing private doubles and waited Perl;
UI tests use the existing private display. No new process, storage or cleanup
owner is introduced; existing unit/UI parallelism classifications apply.

Ordinary Parent launch prepares the bound GNOME desktop through the public
`org.gnome.Shell.OverviewActive` property. If the overview is open, the shared
launcher requests closure once and independently waits for the closed result
before invoking Parent. This releases GNOME's startup input grab; GTK's active
window state alone cannot establish compositor focus while Overview is open.
Launch preparation retains session/prompt guards and refuses uncertain input
without replay. It introduces no new resource owner or baseline setting.

`AccessibleUI.read_language` reuses LANG01 ownership/choice reads and bounded
public language values. Qualification values and immutable policy
comparisons stay in `ParentRtlJourney`; other surfaces still need live qualification.
These operations add no process, storage, bus or cleanup owner. Unit/cleanup
probes keep private node/recorder fixtures and waited Perl children; GTK coverage
uses the existing private preview/display. Existing classifications apply.
Follow the mandate's no-visual acceptance rule; logical text is no pixel verdict.

Enabled Riley Hebrew policy observations reuse `parent_language_state`,
language-aware `time_explanation` / `duration_projection` and the controller's
complete enabled-state decoder. `ParentHebrewPolicyJourney` declares the fixed
English capture and comparison endpoints through `language_composition.language_policy`.
Chooser round trips share `onpc_parent::language_presentation_roundtrip` with
the RTL qualification; callers retain their policy assertions. These add no
resource or cleanup owner. Source-bound named inputs prepare both the new slice
and its public-time regression without replacing valid inputs.

Overlay About reads reuse `journey_blocks.overlay_license_read`,
`onpc_about::overlay_license` and the shared `AccessibleUI.clickable_link` reader.
The child-owned About scope and close proof precede the ordinary API close request; fresh absence
and active form return precede caller-declared immutable request comparisons in
`KioskRequestJourney`. Host and installed workers never activate these links.
The finite `links='browser-links'` fragment checks website and privacy through
`AccessibleUI.read_overlay_link`, with the same independent entry/return
boundaries; `overlay_license.BROWSER_LINKS_PLAN` declares its comparisons.
The finite `links='information'` binding composes Help, owned About entry and
all five About link readers. `overlay_license.INFORMATION_PLAN` and
`onpc_request_flow::overlay_information` qualify two independent round trips;
the shared fragment and `KioskRequestJourney` retain caller-owned capture and
return endpoints. Help is rechecked before entering About from the open menu.

`AccessibleUI.allowance_preset` owns the PARENT05 observation scope for both
direct preview calls and registered operations. Composed child, control, save
and label checks reuse a complete tree until input or a pending/failed read
invalidates it. Each independent call starts fresh; cancellation discards the
scope and retains any uncertain-input latch. The scope adds no process, bus,
storage or cleanup owner, so existing unit and UI parallel classifications apply.

Shared kiosk/overlay duration selection sets the canonical duration value and
waits for its independent public value readback. An accepted action may still
be completing; every retry reacquires ownership and readiness before the exact
form readback. Missing results, cancellation and ownership changes remain
terminal and never replay the input.

Multilingual request-history bindings use `AccessibleUI.language_history_request`
with explicit child, language, approver and request values. Station operations,
including Jordan's Custom text input, belong to `KIOSK_SESSION_OPERATIONS`;
overlay operations retain their child-desktop account. Qualify account routing
through the standalone observer entry, not only direct calls on a preview reader.
Both surfaces emit the existing form diagnostics, which `UiObservations.call`
decodes separately from its single final reply. The
[history regressions](../unit/test_language_persistence_cleanup_safety.py)
cover account/environment routing, chunked output and missing, replayed or late
records without relaxing terminal refusal.

Parent, kiosk and child-overlay entry use
`AccessibleUI.complete_language_setup` through the parent/request wrappers.
It resolves the owned startup
dialog by public ID, activates Continue once and checks fresh closure/readiness.
`Automation.complete_parent_language_setup` and
`Automation.complete_request_language_setup` expose the same operation to UI
consumers. Existing cases therefore retain their original scope. Preview launch
owns the existing process and private bus as before; setup adds no new resource,
storage or cleanup lifetime and leaves the existing parallel classifications intact.

Before setting an account selector, request account selection checks startup
language readiness in its owned snapshot. If setup is pending, it uses the shared
language helper and reacquires the selector after confirmed completion; a selector
that remains disabled still refuses input.
The declared input language can already be Chinese from the child's desktop
setting. Reacquisition must retain that child and language after startup Save;
do not route an already translated form through an English-only account binding.
`kiosk-language-jordan-jamie-chinese` supplies case 254's finite approver input.
Its synthetic-tree/decoder regression covers startup Save, failed Save, changed
language, wrong child, incomplete offered accounts and translated result refusal.
It adds no resource owner; existing unit and cleanup classifications apply.
After choosing an account, it first confirms the chosen public UID and selector
description in a fresh owned snapshot. A newly
selected child's language dialog may disable the form; this read does not require
enabled controls. Only that proof permits the shared language helper's separate
Continue input. Discard the successful selection snapshot before observing
language readiness: a complete traversal can read the old readiness marker
before the new child's UID and translated description. Missing selection,
language completion or full form readback
keeps the selection terminal and prevents replay.
`test_selected_child_snapshot_cannot_supply_later_language_readiness` in the
[restoration regressions](../unit/test_kiosk_language_restoration_cleanup_safety.py)
models the mixed-time traversal and failed Save. Keep this transition test when
optimizing snapshot reuse; a complete tree is not a simultaneous view of all
widget properties.

The station restoration qualification's return to Parent reuses
`onpc_parent::launch` with the fresh `return-desktop` receipt. Its separate
`return-parent-window` checkpoint uses the existing `switch-parent` observer
to require the owned active window before policy reads and child-picker input.
Shell desktop discovery and readable background controls do not establish
window activation. A failed command or active-window read stops the sequence;
neither is retried through another input route.

For the retained Parent picker after session return, shared child selection
sets `parent-child-selector` to the declared UID through the Application UI API
and independently reads selected-child identity and ready policy controls.
The shared Python recipe and Perl worker expose one selection route. Retained
`open`/`focus`/`selected` stage names mean the canonical setter, selected-UID
readback and ready-policy readback; they do not inject keys.
No popup, semantic focus or native focus proof is required. Failure is terminal
and never falls back to a different input route. Real GTK coverage preserves
policy-page reads both alone and after work in another owned preview window.
`test_parent_child_picker_after_language_policy_reads` in the
[language UI tests](../ui/test_language_settings.py) preserves that preceding
input/return history. Do not reduce this regression to a newly launched window
or infer selected-child success from setter acknowledgement.
The additional preview uses the existing private bus/display and owned cleanup;
UI parallel classification remains private. Unit doubles and waited Perl retain
their existing unit/cleanup classifications. Policy collection explicitly waits
for the public App Limits control before reading its rows.

Account selection acquires its initial complete snapshot through the bounded
read wait. A defunct node discards the whole request observation; the same wait
may reacquire before input or during offered/selected-value readback, retaining
the original deadline. Persistent staleness refuses, and no selector or choice
action runs inside a retry predicate. Fresh ownership, prompt and usability
checks still apply after reacquisition.
Parent wrong-entry qualification uses that same bounded read wait: query errors
and stale trees invalidate the observation, and only a fresh complete surface
refusal passes. Wrong ownership and an actually present request form remain
terminal; the refusal check delivers no input.

Native command launch acquires its session, desktop, window-absence and prompt
proofs inside the shared bounded read wait. A query error discards that complete
observation and retries only the preflight; a complete refusal remains terminal.
The launch command runs once outside the wait, with the uncertain-input latch
set before submission and independent window/activity readback afterward.

Dedicated chooser checks opt out of automatic setup with
`launch_ui(..., complete_language_setup=False)`. The host and future installed
language tests reuse `AccessibleUI.language_scope`, `open_language_preferences`,
`choose_language`, `save_language`, `cancel_language` and
`language_save_completed`; the existing `localization_review.switch_language`
facade delegates to these operations too. They resolve only public IDs and
observe checked choices, readiness and closure independently of input success.
The Parent chooser reader discards a snapshot containing a defunct node and
reacquires through the shared bounded read wait. The original deadline, complete
ownership checks and input guards remain in force; persistent staleness refuses
and reacquisition never replays a language choice, Save or Cancel.
`parent_language_management` projects visible labels from the owned Screen Limits
page separately from the switch's accessible name. Callers compare each against
independent literal expectations; the English title and accessible name use
different capitalization. The read adds no input or resource owner.
`parent_language_state` retains the disabled/zero projection and adds explicit
Riley/Jordan enabled 60-minute English/Chinese bindings. The shared
`time_explanation` / `reach_time_explanation` read the declared language's public
text and durations; `app_rows(include_names=True)` includes bounded public names
in the same complete owned policy snapshot. Page navigation waits for public
App Limits readiness before reading. Callers own per-child immutable policy/name
captures, zero-grant assertions and finite elapsed-time comparisons.
`child_selection` shares the stale-safe closed-picker wait with `selected_child`
and independently resolves the selected UID/name. Parent language selection
bindings use that identity-only proof before their language-aware policy read,
without entering PARENT03's English-only allowance reader.
Normal Parent relaunch starts with the first alphabetically listed child; it
does not restore the closed window's selection. Bind the untouched reopened
state to that child, then select each declared child explicitly and compare
against its own immutable capture. Language persistence must not accidentally
assert child-selector persistence or invoke automatic first-run Save.
`language_fixture.py` supplies preview-only saved/read/save outcomes and tiny
caller-owned release files; it is not a substitute for installed persistence.
`read_kiosk_language` shares the bounded chooser reader while requiring the
dedicated station application. Its untouched first read reuses
`initial_kiosk_child` inside the same owned snapshot as the chooser; the fixed
Chinese first-presentation reader uses that same selected-child/result-child
identity guard. Parent-only child-control helpers do not accept kiosk IDs.
`ChinesePresentationMixin` owns the immutable notice/chooser/form comparisons
without inheriting an upgrade history. `ChineseCurrentInstallJourney` qualifies
the single current-package composition; `PackageCommand.package_identities` and
`observe_current_install` independently bind completion, version, same boot and
pre-existing preservation. The worker's `chinese_desktop_renewal`,
`chinese_initial_notice` and `chinese_initial_form` leaves serve both histories.
These add no live owner beyond the existing guarded envelope.

Installed-snapshot prerequisite checks use an owned installed observation:
`ChineseNativeAuthJourney` verifies assets at the public Parent checkpoint.
The product-free package-command context requires transferred package inputs
that this installed entry does not have. Retain
`test_installed_asset_checkpoint_verifies_without_package_transfer` in the
[native authentication regressions](../unit/test_chinese_native_auth_cleanup_safety.py)
when reusing or moving prerequisite actions; it exercises the actual recorder
and refuses missing assets before a reply.

`kiosk_language_form` independently reads button
labels and accessible names plus REQUEST03 values; neither reader performs
automatic startup Save. `kiosk_language_policy` observes the declared child's
settings, balances and application rows through public Parent controls.
Its Save-completion receipt establishes idle controls; `settings` separately
reads the allowance-bearing policy values. The receipt is not a settings snapshot.
`journey_blocks.language_selection` / `onpc_parent::language_selection` share
the chooser fragment across Parent and kiosk recipes. Callers retain literal
language expectations, response order and preservation endpoints. The
`installed-language` preview profile binds only synthetic account names to the
installed reader; it provides no installed persistence or policy evidence and
adds no resource or cleanup lifetime.

`read_overlay_language` and `overlay_language_operation` bind the same chooser
mechanics to the child application and active Riley session, retaining the shared
request IDs. Untouched and reopened reads require the fixed child's public UID;
the station reader continues to refuse child ownership. Shared
`kiosk_language_form(..., overlay=True)` reads translated REQUEST03 fields and
separate visible/accessibility text after independently observed readiness.
`kiosk_language_policy(child=CHILD)` reads Riley's saved allowance and app rows
through Parent; qualification comparisons permit natural daily-time usage.
The overlay preview's `installed-language` account projection and session double
qualify GTK readers only. They establish no installed persistence or policy result,
and add no resource lifetime or parallelism conflict.

Selected-child kiosk LANG01 reads bind `child` explicitly through the selected
public UID on every chooser boundary, including the post-Save/Cancel receipt.
`kiosk_language_form(language, child=...)` reads each child's translated form;
the default remains Jordan. `select_kiosk_account(..., child=..., language=...,
result_language=...)` separately binds the owning child/input language, exact
offered UID set, translated choice meanings and literal account names, then
independently reads the selected UID and resulting language. Approver changes
require equal input/result languages. Unknown selection or chooser effects are
terminal and are never replayed. The Riley operation aliases carry that identity
through registration and decoder validation; policy and per-child preservation
comparisons remain caller-owned. These mechanics add no resource or cleanup
lifetime; the existing preview process/display classification still applies.

Host support never establishes installed or customer acceptance. Guest execution
uses [system_assertions.py](../integration/system_assertions.py) for real-caller
batches, validated broker replies and authoritative account snapshots, and
[system_accounts.py](../integration/system_accounts.py) for the accepted guarded
identity creation/deletion protocol. The latter refuses collisions and identity
replacement and observes both NSS and AccountsService.

Register guest dependencies in `system_runner.AREA_SELECTED_HELPERS` so selected
staging and source provenance include them. Full selections stage identical
source/target declarations once; conflicting target declarations are refused
before copying files. Reuse the
[installed runner contracts](../integration/README.md#reusable-implementation-contracts)
for live ownership/transport/recovery and the [E2E contracts](../e2e/README.md)
for real graphical input, credentials, private collection and evidence gates.
These development helpers activate on the next invocation; there is no product
integration or saved-data migration.

External-provider public snapshots batch live `Accessible.Name` queries for already
discovered nodes. Those values live only within the same observation as the
structural facts and expire on input, retry, reset and snapshot exit. Ordinary
`get_name()` result reads remain uncached; provider `GetItems` names never supply
these observations. Protected descendants are still excluded before querying.

External-provider nodes absent from `GetItems` batch their fallback role and, when constructing
observation facts, state queries with identity/name reads. These fallback states
expire with the snapshot; input guards continue using uncached `get_state_set()`.
Query errors and malformed states still refuse the complete observation, and
every pipeline remains bounded to 64 RPCs.

Product snapshots instead come from the shared Application UI API inventory and
element operations. Their names, text, canonical values and capabilities remain
scoped to the pinned application/surface. Host and guest consumers must not
consult the accessibility tree to fill a missing product value or retry an API
refusal through a provider. Read waits may reacquire observations; input never
runs inside those retry predicates.

`ApplicationUI` opens its own connection to the current
`DBUS_SESSION_BUS_ADDRESS`, preserving isolation between private preview buses
and installed user sessions. Its idempotent `close()` closes only that owned
connection; injected clients/connections remain caller-owned. Preview fixture
teardown closes the catalog alongside its external provider reader. Endpoint
owner/PID pins last for the catalog lifetime and require deliberate rebinding
after a product restart.

## Extend without hiding the scenario

Personal-language histories use
[`language_composition.language_journey`](../e2e/language_composition.py) with
caller-declared checks. Use `public_language_value` for complete literal chooser
and request-form comparisons, and `language_policy` for named immutable policy
captures and later comparisons. Recipes supply the expected labels, excluded
labels, account values, capture endpoints and elapsed-time budget; the shared
check preserves zero-grant and naturally decreasing daily-balance assertions.
Keep those values in the consumer instead of copying a comparison subclass.

`public_language_value` also compares declared chooser/dialog presentations and
feedback projections, with optional caller-named `capture`/`same` endpoints.
It copies nested public values and refuses missing or repeated captures before
the recorder reply. Parent dialog visits share `onpc_parent::dialog_visit` and
`dialog_close`; recipes retain visit count, language, direction and assertions.
Case 256 composes these with the enabled-policy and Preferences roundtrip
operations. Its safety checks use private files/values and waited Perl children,
compatible in both unit and cleanup inventories; no new live owner is introduced.

`offline_language_actions` reuses the lease's existing Internet isolation and
recovery owner. Bind its stages to public installed-policy observations before
the action. An installed-snapshot history has no transferred installer, so its
connectivity checkpoint must not require a package-command context. The
[language-history regressions](../unit/test_language_persistence_cleanup_safety.py)
exercise the real recorder boundary, require refusal before connectivity input
when policy observation fails, and check independent recovery. These helpers
add no storage, process or cleanup owner.

Continuous package histories use `package_lifecycle.record_lifecycle_journey`
with caller-declared operations, actions and comparison endpoints. Its shared
journey composes the existing package/transfer/recorder envelope and runs public
checks before publishing a reply. `journey_checks.access_choice`,
`policy_projection` and `request_choices` bind literal expectations and immutable
named captures; saved settings/rows are separate from naturally changing usage
and explicitly checked grants. Missing captures, changed results and replay
refuse. Recipes keep values, order, phase boundaries and assertion names.
`journey_blocks.prefixed_stages` and `custom_allowance` pair with
`onpc_journey::scope`, `onpc_parent::named_management`,
`onpc_gdm::named_login` and `onpc_allowance_boundaries::custom_value` for repeated
independent entries and ordinary edits. Prefixes rename checkpoints, not account
identity; declared challenges and independent selection/readback remain required.
These add no storage, process or cleanup owner. The existing private unit and
cleanup classifications remain applicable.

Package lifecycle declarations reuse `journey_blocks.package_installation` in
case 2 and LIFE04 qualification; LIFE02, genuine upgrade and Chinese lifecycle
plans inherit that same fragment. It declares fresh administrator entry,
submission and separate readback without a reboot or wrong-entry exercise.
Callers retain phase boundaries, assertions and current/previous package binding;
`PackageCommand` and `package_install.submit_release` / `observe_release` own
the guarded command and independent result. The fragment adds no resource or
cleanup lifetime; existing unit/cleanup classifications remain applicable.

`restart_notice.RestartNoticeJourney` adds the three fresh-install modal bindings
over that package fragment and the shared fresh-desktop/station entries.
`AccessibleUI.restart_notice`, `restart_action`, `restart_closed` and
`restart_usable` share the public-ID route with the real GTK modal test.
The notice can arrive before the request's own-account load; the exact application
owner and, for the overlay, active fixture session bind that early read.
Language setup is permitted only in the postboot usability operation.
`JourneyPlan.modal_reboots` pairs an exact surface read with the adjacent fresh
GDM result. `UiObservations.submit_restart` consumes once; a bounded terminal
stream permits transport uncertainty only after the exact boot/surface readiness
record. Independent boot-change and fresh-GDM observations supply acceptance.
No command reboot fallback or input retry is allowed.
The existing customer-reboot unit/cleanup module retains private fixtures and
waited Perl/isolated-Python subprocesses with bounded timeouts; the existing
error-feedback UI module retains its private display and stubbed reboot callback.
These additions share no VM or product process and add no host resource owner.
The existing unit, cleanup and UI classifications remain applicable.

Native activity transitions reuse `journey_blocks.native_activity_entry` /
`onpc_app_rows::native_activity_entry` for
launch/use/capture and `native_activity_resume` for an independently observed
original window's next submission. Cases 44/45 and overlay qualifications share
the entry operation; callers retain transition, immutable comparison endpoints,
reread and close. Invocation prefixes determine both controller checkpoints and
actual worker titles. The helpers add no process, storage or cleanup owner and
never relaunch during resume. Keep the existing complete-order/failure-stop
checks alongside an independent caller with renamed prefixes.

Shell authentication declarations reuse `request_flow.overlay_authentication`
for Cancel or fixed approval, paired with `onpc_request_flow::shell_cancel` /
`shell_approve`. Tasks 048c/048d compose this fragment with
`KioskRequestJourney`; form preservation, desktop return, activity endpoints and
assertion phases remain caller-owned. Declaration checkpoint renaming alone
does not parameterize the approval worker or qualify another request/provider
binding; use the [catalogue scope](../../docs/TestAutomation/E2E-Building-Blocks.md#overlay-approval-and-automatic-return-qualification).

E2E declaration fragments and worker execution have matching shared owners:
`journey_blocks.parent_reopen` / `onpc_lifecycle::reopen` for LIFE01,
`request_flow.daily_station_entry` / `onpc_request_flow::daily_station_entry`
for the qualified 15-minute preset and station entry, and
`match_rules.match_edit` / `onpc_app_rows::match_edit` for editor replacement and
Save. They preserve caller-owned phase boundaries, expected values and exits;
the [catalogue](../../docs/TestAutomation/E2E-Building-Blocks.md) owns binding
scope and qualification. Reuse these fragments in both cases and qualifications
instead of copying their stage maps or creating a plan-only comparison subclass.

Keep expected outcomes, case tables, fault injection and independent oracles in
the owning tests. The broker state-machine model intentionally has independent
state and assertions. Standard `tmp_path`, `monkeypatch`, `unittest.mock` and
`TemporaryDirectory` already supply reusable behavior and need no style wrapper.

Build external authentication tree fixtures from the qualified provider's
catalogue and observed message branch, independently of the adapter's expected
strings. Bind the provider version, locale and authenticating/session roles:
Chinese MATE in the kiosk uses the super-user explanation, not its same-user
or multiple-identity explanations. The independent `native_tree` fixture and
`test_chinese_kiosk_refuses_other_native_explanation_branches` in the
[native authentication regressions](../unit/test_chinese_native_auth_cleanup_safety.py)
preserve that distinction and refusal before secret input. A fixture copied
from the adapter's oracle cannot detect a shared wrong expectation.

Import fixtures explicitly instead of loading every helper as a global plugin.
Include dependency fixtures in the consumer too; aliases can disambiguate names.
Helpers must not import collected cases, mutate the desktop at import time or
infer process ownership from names/environment variables.

Preserve test names, parameter IDs, requirement links, refusal cases, deadlines,
privacy canaries and cleanup checks during extraction. Validate affected callers
at the [lowest effective scope](../README.md#all-established-regressions), retaining
required acceptance and selectors; extraction alone does not require unrelated suites.
Cleanup changes require their isolated safety regressions before protected
operations. See [test maintenance](../README.md)
for authorized launchers and evidence boundaries.
