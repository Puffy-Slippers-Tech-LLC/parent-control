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
| Public GUI traversal, ownership and actions | [automation.py](automation.py), [accessible_ui.py](../e2e/accessible_ui.py), [public_atspi.py](../e2e/public_atspi.py) | Host previews and installed E2E share the public D-Bus reader, `AccessibleUI` traversal, complete immutable snapshots, scoped ID resolution, action selection and the uncertain-input latch. The host facade supplies its root, recorded preview owners, event wait and diagnostic names. Complete snapshots and indexes expire before input, retries and observer resets; mutable compatibility projections cannot seed indexes. |
| Maintainer-script machines | [package_scripts.py](package_scripts.py), [shell.py](shell.py) | `package_machine` and `machine` execute real scripts against temporary files and explicit command doubles. Path relocation alone is not a sandbox. |
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
| Nested-Shell input delivery | [mutter_input.py](../ui/mutter_input.py) | Pointer motion, press and release have separate dispatch intervals; pointer and keyboard actions complete the RemoteDesktop session before observation. Failure screenshots retain the pointer to distinguish placement from delivery. |

## Host and guest boundaries

Overlay About reads reuse `journey_blocks.overlay_license_read`,
`onpc_about::overlay_license` and the shared `AccessibleUI.clickable_link` reader.
The child-owned About scope and close proof precede normal Alt-F4; fresh absence
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

Shared kiosk/overlay duration selection waits for the ID-resolved control's
public pressed state after its single activation. An accepted action may still
be completing; every retry reacquires ownership and readiness before the exact
form readback. Missing results, cancellation and ownership changes remain
terminal and never replay the input.

Parent, kiosk and child-overlay entry use
`AccessibleUI.complete_language_setup` through the parent/request wrappers.
It resolves the owned startup
dialog by public ID, activates Continue once and checks fresh closure/readiness.
`Automation.complete_parent_language_setup` and
`Automation.complete_request_language_setup` expose the same operation to UI
consumers. Existing cases therefore retain their original scope. Preview launch
owns the existing process and private bus as before; setup adds no new resource,
storage or cleanup lifetime and leaves the existing parallel classifications intact.

Before opening an account selector, request account selection checks startup
language readiness in its owned snapshot. If setup is pending, it uses the shared
language helper and reacquires the selector after confirmed completion; a selector
that remains disabled still refuses input.
After choosing an account, it first confirms the chosen public UID and selector
description, with the offered list closed, in a fresh owned snapshot. A newly
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

For the retained Parent picker after session return, callers select
`custom_child_selection(..., route='keyboard')` and the matching
`onpc_allowance_boundaries::select_child` route before input. The public window
focus action targets `parent-child-selector`; a fresh owned snapshot requires
an active window and unique visible, sensitive native focus within that
ID-resolved selector. GTK delegates MenuButton focus to its internal toggle;
this is focus containment, not anonymous-node targeting. A consumed exact
focus receipt permits one Space. The separate `*-picker-presented` observation
requires the popup and UID-scoped choice before the existing focus/Enter/selected
readbacks. Failure is terminal and never falls back from a failed popup action.
Real GTK regression covers policy-page reads both alone and after input to
another owned preview window, which reproduced the direct-popup timeout.
`test_parent_child_picker_after_language_policy_reads` in the
[language UI tests](../ui/test_language_settings.py) preserves that preceding
input/return history. Active-window proof alone did not repair the live failure;
do not reduce this regression to a newly launched window or infer popup success
from focus/action acknowledgement.
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

Complete public snapshots batch live `Accessible.Name` queries for already
discovered nodes. Those values live only within the same observation as the
structural facts and expire on input, retry, reset and snapshot exit. Ordinary
`get_name()` result reads remain uncached; provider `GetItems` names never supply
these observations. Protected descendants are still excluded before querying.

Live nodes absent from `GetItems` batch their fallback role and, when constructing
observation facts, state queries with identity/name reads. These fallback states
expire with the snapshot; input guards continue using uncached `get_state_set()`.
Query errors and malformed states still refuse the complete observation, and
every pipeline remains bounded to 64 RPCs.

## Extend without hiding the scenario

Package lifecycle declarations reuse `journey_blocks.package_installation` in
case 2 and LIFE04 qualification; LIFE02, genuine upgrade and Chinese lifecycle
plans inherit that same fragment. It declares fresh administrator entry,
submission and separate readback without a reboot or wrong-entry exercise.
Callers retain phase boundaries, assertions and current/previous package binding;
`PackageCommand` and `package_install.submit_release` / `observe_release` own
the guarded command and independent result. The fragment adds no resource or
cleanup lifetime; existing unit/cleanup classifications remain applicable.

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
