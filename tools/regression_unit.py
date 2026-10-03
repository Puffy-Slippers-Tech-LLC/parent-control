"""Balance reviewed unit modules without splitting their fixtures.

Kiosk locale cases in request_time_estimate, adapters, core, service_contract
and systemd_unit use process-local D-Bus/systemd doubles and tiny tmp_path
environment files. They launch no real agent, change no host locale and retain
their compatible classification; no new process, socket or cleanup owner.
The native-gettext locale check in localization uses its existing private
catalogues and synchronously waited subprocess; locale inventory is read-only.

Diagnostics-only broker cases retain process-local credentials/bus/thread doubles
and small private pytest log directories. Upgrade guard cases retain their
existing relocated, synchronously waited launcher processes. No system bus,
installed service, shared log directory or new cleanup lifetime is used; the
service_contract, diagnostic_privacy, systemd_unit and package_configuration
modules retain compatible overlap.
Shared reboot detection/startup cases add only private tiny marker files and
process-local main-loop/transport doubles to service_contract. They touch no
host reboot state or services and retain that compatible classification.

Update-required dialog and reboot tests use process-local GTK/Gio doubles only;
parent startup tests queue fake threads and idle callbacks. Package-marker cases
use the existing relocated fixture. The error_reporting, parent_main and
package_configuration compatible classifications still apply: no live reboot,
bus, display or new cleanup owner.
Update-modal automation identity checks add only synthetic public trees to
automation_ids; its compatible unit classification is unchanged.

The reviewed modules use process-local doubles, read-only checkout inputs and
private temporary trees. Their real subprocesses use private outputs, relocated
system paths, private sockets or recorded child identities. The launcher disables
shared pytest/Hypothesis caches and aggregate retention in every unit worker.
Unknown modules fail closed to exclusive execution; new modules must receive an
isolation/resource review and classification before their work is complete.

Child trust upgrade/retry/boot regressions use tiny private pytest machine trees,
synthetic boot IDs, and synchronously waited relocated maintainer-script/helper
children. They read immutable unit/launcher sources and mock every live service
and database command. Existing package_activation, package_configuration,
package_removal and systemd_unit classifications remain compatible; no shared
path, cache, socket, VM, privileged write or new process lifetime is introduced.

Private-version and updateversion regressions use tiny private metadata trees,
synchronously waited Make/dpkg children and stub builders. Publishing fixtures
retain their private Git remotes and mocked network/signing; local-source DSC
checks retain private byte fixtures and mocked sbuild. Existing bump_version,
build_package, publish, publishing_tests and ppa_build compatible classifications
still apply; no live package installation, build, service or shared cache is used.

Unified preference/language tests use tiny private temporary records and
process-local account/storage doubles. Their concurrency case owns two finite
threads, releases its private gate in finally, and joins both before returning.
Migration interruption and uninstall selection checks use those same private
trees without real services, processes, sockets or privileged writes. Existing
compatible preference, core, migration and uninstall classifications still apply.

Guest-probe additions to VM-control, snapshot, configuration and transport tests
use existing private pytest lease/scratch trees and process-local SSH/libvirt,
stream and clock doubles. They add no live guest, socket, display, credentials,
shared state or heavy construction; their compatible unit classifications hold.

Fresh-desktop, Shell-search and GDM recipient release bindings use tiny tmp_path
metadata and a restored process-local ROOT patch; no VM, shared file, socket or
display is accessed.

Regression session tests keep both session gates and cancellation records in
private pytest trees; recorded harmless children are released and reaped by
their fixture. Cross-scope reconnect tests remain safe for compatible overlap.
Public AT-SPI and observation-cache regressions use process-local bus doubles,
mock clocks and immutable synthetic trees; they open no real sockets or displays.
Missing-cache role/state batching checks use at most 32 synthetic nodes and those
same bus doubles; compatible classification and cleanup ownership are unchanged.
Language chooser action guards use those same in-memory trees and mocked actions;
scope restoration and uncertain-input checks add no resource or cleanup lifetime.
The complete supported-ID matrix reads immutable catalogue metadata and rejects
unlisted IDs before input in those same synthetic trees; classification stays
compatible, with no live UI, socket, setting or additional cleanup owner.
Runtime timeout evidence tests mock all OS commands and use private pytest
metadata; toggle entry tests keep bounded, waited Perl children and no live login.
Both existing compatible unit classifications remain valid.
Their asynchronous batch probe drains a private GLib context with synthetic
callbacks and restores the thread-default context; no shared loop or thread runs.
Native fixture cleanup probes compile in tmp_path and change signal masks only
inside their explicitly spawned synthetic GUI child, never in the test worker.
The UI cleanup crash probe owns one small Python child and tmp_path log/script;
the child disables core files and aborts only itself, with no display or bus.
UI timeout/cancellation probes run small synthetic pytest children in private
owned process groups, with tmp_path inputs and disabled caches. Each directly
spawned worker and foreign sentinel is pinned/waited; no GUI, bus or shared
process group is touched. Both unit and cleanup classifications stay compatible.
Timeout handoff qualification writes reports through shared storage beneath
its private checkout and drives finite repair/verification callbacks, no real
Codex agent. Descendant-exit receipts use private pidfds, never process scans.
Outside-group pipe probes add only recorded private children and bounded rescue
threads. Shell guardian probes use synthetic tmp_path runners and isolated
subreaper subprocesses; pytest itself never becomes a subreaper. Their private
short runtimes, inherited scratch locks and adopted children finish ownership
cleanup without a GUI, bus, host service or shared cache. Both cleanup modules
remain compatible in unit and cleanup scheduling.
Allowance qualification tests reuse bounded, synchronously reaped Perl children
with captured pipes and synthetic UI values. Fresh-thirty recorder cases use
only the existing private tmp_path collector; no additional shared resource.
Prerequisite-repair launcher tests reuse private checkout/session trees and the
existing recorded owner/agent doubles; they start no real Codex or VM process.
Model-routing and usage-recording checks use those same private trees and tiny
JSON records, in-memory renderer callbacks and recorded child doubles. No new
shared cache, network, bus, display or heavy fixture; compatible overlap remains.
Fix-tests argument forwarding checks reuse those recorded child doubles and
private test files; validation reads checkout inputs without running real tests
or touching a VM. Their compatible unit and cleanup classifications still apply.
Escalation and diagnostic handoff tests reuse these same finite synthetic children,
private JSON snapshots and recorded cancellation owners. No paid model, live
runner, VM, shared cache or new cleanup lifetime is introduced; overlap stays compatible.
Named qualification preparation coverage reads wrapper ASTs and mocks allocation,
builder execution and privilege checks; no builds, shared writes or VM access.
Attachment boundary tests retain private tmp_path files (<= 5 MiB+1 each),
bounded in-memory bytes and waited private Perl children; compatible in unit
and cleanup scheduling, with no build, shared cache, bus, display or VM.
Chooser delivery regressions add only tiny tmp_path acknowledgement files and
in-memory queued callbacks; the existing compatible unit classification applies.
ZIP reader checks use the same private trees and process-local transport doubles,
with archives bounded to 64 KiB; no new process, socket or shared resource.
Source-change checks add tiny private files and process-local write/transport
doubles, retaining compatible unit and cleanup scheduling.
Publisher branch/resume tests use tiny tmp_path Git repositories, bare remotes,
linked worktrees and local flock files. Git children finish synchronously;
signing, network, uploads and package builds are mocked. No shared repository,
credential store, activity lock, socket or display is used; compatible overlap
remains appropriate for the publish module.
Automatic main-update regressions add only private Git clones/remotes and
process-local confirmation/terminal doubles. Interrupted push/merge recovery
uses the same private journals; no real credentials, terminal or shared ref is
modified, and no heavy fixture construction is added.
Main monitoring handoff checks also use private pytest Git directories and
journals, including stale-record preservation, missing/reused release journals,
and atomic-save failure/retry. Only local Git subprocesses are used and reaped;
no shared journal or public endpoint is touched, so compatible overlap remains.
VM rename checks use private pytest provenance trees and process-local libvirt
doubles, including rollback and lock contention. No real VM, disk, socket,
display or shared controller state is accessed; compatible overlap remains.
VM queue checks join bounded in-process thread pools and mocked controllers,
with private retained logs and journals. Lease/legacy-journal tests hold only
tmp_path flock files; existing compatible VM, launcher and storage buckets apply.
Publishing Make-entrypoint checks copy the dispatcher and configuration into
tmp_path and synchronously reap Make/Python/stub-runner children. The configured
disk is never opened; no real tests, VM, shared cache or build is started, so
publishing_tests retains its compatible unit classification.
Baseline --y regressions use process-local input, privilege and VM doubles;
launcher prompt checks read strings and private report files. No real VM,
privileged helper, terminal, socket or shared storage is accessed, so existing
compatible baseline, setup and launcher classifications remain appropriate.
Shared preparation-picker and app-snapshot confirmation checks likewise use
process-local input/TTY doubles and the existing private launcher fixtures;
baseline, app-snapshot, VM-config and session modules remain compatible.
Fedora snapshot regressions use private tmp_path archives/locks and process-local
RPM builder, guestfs, package-manager and transport doubles. They run no actual
RPM build, VM, host package mutation, bus or display; artifact, system-runner,
system-guest, provenance, package-content and snapshot modules stay compatible.

Catalogue filter regressions reuse in-memory AT-SPI trees, finite transport
values and bounded, synchronously reaped Perl workers. Recorder probes retain
their private tmp_path evidence; no live VM, display, bus or shared state is
added. App-row and installed-journey modules retain compatible unit scheduling.
Legend guards and worker-order tests use the same in-memory trees and bounded,
waited Perl children; recorder tests use private tmp_path evidence. No new live
VM, display, bus, socket or shared cache; both existing buckets remain compatible.
Match Reset/invalid probes retain those memory doubles, finite decoder values
and waited Perl workers. Their new recorder plan uses function-private files;
unit and cleanup scheduling retain the existing compatible classifications.
Response read-retry probes add only private in-memory trees and bounded waits;
they introduce no shared resource or process ownership.
Child interaction wait probes execute the source functions with private clock
and GLib doubles; child_preview remains compatible without a real bus/display.
"""

# TIME01 tests add only immutable synthetic trees, process-local account/session,
# clock and transport doubles, and tiny private pytest reply files. Compatible
# overlap; actual worker checks reuse bounded synchronously reaped Perl children
# in challenges, and installed-journey keeps its existing private recorder trees.
# Fresh child denial checks retain private pytest evidence, process-local public
# UI/worker doubles and bounded waited Perl children. No live bus, VM, display
# or shared paths; accessible_e2e_ui, challenges and installed-journey modules
# retain their compatible classifications.

# Parent rejected-report checks use existing process-local AT-SPI doubles,
# private tmp_path recorder files and bounded, waited Perl children. No live
# guest, display, bus, shared cache or new allocation lifetime; their reviewed
# app-row/composition/launcher and installed-journey buckets stay compatible.
# Native command checks use process-local session/command doubles, tiny private
# recorder files and bounded waited Perl workers; no live guest/display/cache.
# The new e2e_native_app module and existing recorder/launcher buckets overlap.
# Native activity comparison uses frozen synthetic public values, private
# pytest reply/marker files, process-local transport doubles and waited Perl
# children. No live VM, display, socket, shared cache or new resource lifetime.

# Diagnostic export retains test_e2e_files_cleanup_safety's private tmp_path files,
# bounded in-memory archives and mocked SSH. Feedback composition retains private
# waited Perl children and memory doubles. Both existing compatible buckets apply.
# GNOME warning/privacy and Fedora system-info checks use process-local command
# doubles, existing private tmp_path logs and bounded in-memory archives. They
# launch no RPM/GNOME process and access no host package DB, bus or display;
# extension_manager, diagnostic_privacy and system_info remain compatible.
# Extension import and payload-policy observations use process-local command,
# clock, account and export doubles, with no live Shell, trust DB, bus, files,
# threads or host services. Existing extension_manager, core and service_contract
# compatible unit classifications remain appropriate.
# Localization wording checks reuse private compiled catalogues and waited
# Make/Node/GJS children. Importing feedback for size formatting constructs no
# widgets or workers. Controller presentation doubles remain process-local and
# restored after each test; existing compatible unit classifications apply.
# The diagnostic-report import-failure regression uses its existing tmp_path
# writer and restored process-local logger/command doubles; no additional shared
# service, bus, subprocess or cache. diagnostic collectors remain compatible.
# Broker address-family checks read immutable unit/payload inputs; payload
# fixtures retain their existing private build trees and resource admission.
# Sandbox socket probes use process-local doubles, including netlink; no real
# socket, systemd service, VM, display or shared state is touched. The existing
# systemd_unit, package_payload, rpm_packaging and sandbox cleanup buckets hold.

from pathlib import PurePosixPath
# LIFE06 Parent composition retains vm_internet_cleanup_safety's private
# journals/replies and process-local UI/libvirt doubles; compatible scheduling.
# Native preparation uses private tmp_path files, restored ownership/GTK/SSH
# doubles and waited bounded Perl children; no live VM, bus, display or shared
# cache. Existing fixture build tests retain build resource admission. Named
# fixture-input hashing uses tiny private files; both cleanup/unit reviews hold.

# TIME03 uses fake clocks and process-local guard/UI doubles, private tmp_path
# records and bounded waited Perl children. No VM, bus, display or shared cache.
# VM Internet ownership/recovery checks use only tiny tmp_path journals and
# in-memory libvirt/SSH/UI doubles, with no sockets, live VM or host mutations.
# Watch transport regressions use private socketpairs, managed short socket
# paths, sealed frame mappings and owned fixture processes with tmp_path logs.
# They remain compatible with other unit modules; no live VM/display/bus is used.

# Case 49's added request/countdown checks use private values, pytest trees and
# bounded owned Perl doubles. Kiosk-valid-duration and installed-journey modules
# retain compatible unit scheduling; no live display, bus, VM or shared cache.
# Overlay form-stream checks reuse kiosk-entry's private command files and
# process-local transport/clock doubles; shell-panel adds only bounded in-memory
# JSON chunks. Both modules retain compatible scheduling and existing ownership.
# Panel keyboard qualification uses the same private trees and process-local
# Component focus doubles; actual key order is checked by the owned Perl double.
from regression_cleanup import ESTIMATES as CLEANUP_ESTIMATES, work_units

# Repair-budget/routing probes use finite synthetic agents, private tmp_path
# handoffs and recorded owners. Case-ID/VM-queue metadata probes use only private
# files and mocked controllers. Existing compatible classifications remain valid;
# no live model, VM, display, shared cache or new cleanup authority is used.
from regression_resources import HOST_WORKERS
from regression_ui import Bucket


# Access-choice adapter/recorder additions retain process-local doubles and
# private tmp_path evidence; no new VM, socket, display or process ownership.
# Localization uses tiny tmp_path PO/MO trees and bounded, synchronously reaped
# Make/gettext children. Package compilation targets each fixture's DESTDIR;
# no checkout outputs, GUI, bus, service or shared locale changes are involved.
# Production-language parity adds bounded, reaped Node and GJS children reading those
# private MO files. Payload comparisons reuse the existing fixture admission
# and DESTDIR; neither addition introduces shared mutable state.
# The expanded catalogue adds small private MO headers and a bounded, reaped
# Node resolver parity check; existing localization/payload classifications apply.
# Full POT parity covers every non-English catalogue and bounded plural residues
# in the same private MO tree. Node/GJS results and vectors remain pytest scratch;
# no shared output, bus, display, network or new process lifetime is introduced.
# Expanded language-action guards retain finite case inputs, process-local
# accessibility doubles and independent checked-state/readback assertions.
# Overlay/panel checks use process-local accessibility/session doubles and
# bounded, reaped Perl children; evidence stays in each pytest tmp_path.
# Overlay invalid/Escape/FLOW04 checks extend that same lifetime and introduce
# no live session, display, shared cache, socket or additional cleanup inventory.
# The added challenge/installed-journey cleanup rows retain the same isolation.
# Overlay Cancel case checks use private evidence/doubles and reaped Perl workers;
# verification-only action selection adds no shared resource or cleanup lifetime.
# Overlay About uses process-local public-tree doubles, private evidence and
# bounded reaped Perl workers, with no live VM/display or shared mutable state.
# Website/privacy reader and worker-order matrices extend those same private
# lifetimes; no new module, shared resource or cleanup classification is needed.
# Shell prompt tests use process-local protected-tree/session doubles, private
# recorder files and bounded waited Perl children; no live VM, GUI or shared state.
# Shell approval extends these existing modules with protected field doubles,
# private recorder evidence and waited Perl workers; classifications still hold.
# Approval readiness streams and Enter acknowledgements reuse those private
# files and synchronous doubles; no observer thread, live bus or shared owner.
REVIEWED = frozenset("""
localization
e2e_overlay_prompt
e2e_shell_panel
e2e_overlay_valid_choices
e2e_overlay_license
e2e_overlay_cancel
vm_internet_cleanup_safety baseline_fixtures_cleanup_safety
about_dialog accessible_e2e_ui accessible_observation adapters app_policy app_termination appsnapshot_cleanup_safety apt_removal_notice chinese_language_assets_cleanup_safety
authentication_evidence automation_ids backing_verification_cleanup_safety baseline_guest_cleanup_safety broker_properties
broker_state_machine build_package build_test_artifacts bump_version catalog catalog_scope challenges_cleanup_safety child_preview
child_preview_cleanup_safety clean_install_cleanup_safety codex_test_rules config core coverage_generation customer_reboot_cleanup_safety data_migration
dbus_harness_cleanup_safety desktop_session_cleanup_safety dev_privileges dev_tool_installation
diagnostic_export diagnostic_privacy diagnostic_report diagnostics document_checks
dynamic_account_fixture e2e_app_rows native_fixtures_cleanup_safety e2e_asset_transfer_cleanup_safety e2e_broker_startup_observations
e2e_case_composition e2e_command_help e2e_countdown e2e_controller_qualification_cleanup_safety e2e_desktop_keyring
e2e_desktop_session e2e_disabled_child e2e_evidence e2e_feedback_read e2e_fresh_desktop
e2e_execution_cleanup_safety e2e_files_cleanup_safety e2e_fixture_credentials_cleanup_safety e2e_gdm_helper
e2e_gdm_navigation e2e_gdm_pixels e2e_gdm_product_free e2e_gdm_recipient
e2e_install_helper e2e_install_password_observation e2e_installation_boundary
e2e_installation_observations e2e_inventory e2e_keyring_fixture_cleanup_safety
e2e_kiosk_eligible_choices e2e_kiosk_valid_duration e2e_kiosk_entry e2e_kiosk_no_approver e2e_kiosk_no_child e2e_leased_recording_cleanup_safety
e2e_license_viewer
e2e_matched_screens e2e_needle_inputs e2e_observation_transport e2e_parent_search_launch e2e_native_grid_usable e2e_native_app e2e_app_activity
e2e_plan e2e_pointer_helper e2e_progress e2e_real_interval
e2e_provenance e2e_recording_cleanup_safety e2e_recording_credentials e2e_runner
e2e_request_choices e2e_request_exit e2e_secret_variables e2e_serial_helper
e2e_serial_observation e2e_shell_search e2e_shell_search_results e2e_shutdown
e2e_startup_cache_cleanup_safety e2e_startup_observations e2e_suite_cleanup_safety
e2e_terminal e2e_terminal_provider e2e_toggle e2e_vt6_authentication e2e_vt6_command e2e_vt6_controller
e2e_vt6_diagnostic e2e_vt6_pixels e2e_vt6_prompt e2e_vt6_recipient e2e_vt6_shell e2e_watch
e2e_watch_cleanup_safety e2e_worker_cleanup_safety error_reporting execution_policy
execution_policy_ready execution_probe_cleanup_safety extension_manager feedback_collection
feedback_transport fedora_pam fix_tests fix_tests_cleanup_safety fixture_cleanup_safety fixture_gui_adapter floating_islands
graphical_attachment_cleanup_safety graphical_backend graphical_expiry graphical_host_policy
graphical_lease graphical_serial_cleanup_safety graphical_smoke graphical_smoke_cleanup_safety
graphical_transport_cleanup_safety graphical_worker graphical_worker_cleanup_safety guest_inputs
installed_journey_cleanup_safety installer integration_harness kiosk_model kiosk_rendering
launcher_render licensing lightning logs mutter_input package_activation package_authority_cleanup_safety package_configuration package_inputs
package_content package_install_cleanup_safety
package_os_gate package_payload package_removal package_transaction_notice pam_runtime_cap
parent_about_cleanup_safety parent_about_worker parent_access_worker parent_client
parent_discovery_worker parent_grid_pixels parent_main parent_needles
parent_setup_cleanup_safety ppa_build preferences prepare_baseline
prepare_baseline_cleanup_safety prepare_baseline_tool prepare_vm prepare_vm_contract
preview_screen privileged_test_runner probe_bus_client_cleanup_safety
probe_channel_cleanup_safety probe_generation_cleanup_safety product_free_entry_cleanup_safety provision publish
publish_source_integrity publishing_tests public_atspi qualification_storage_cleanup_safety read_only_launcher regression regression_cleanup
regression_cleanup_safety regression_inputs regression_resources regression_schedule
regression_selection regression_session regression_ui regression_ui_selection regression_unit rpm_packaging
regression_unit_selection release_signing repeated_operations_cleanup_safety request_selections request_time_estimate
screen_preview_cleanup_safety screenshot_cleanup_safety screenshot_export_policy
screenshot_export_safety service_contract session_expiry session_expiry_cleanup_safety
session_limit_check setup_entrypoint setup_privileges shell_overview storage_migration_cleanup_safety support
support_architecture support_shell system_accounts_cleanup_safety system_agent
system_agent_cleanup_safety system_assertions system_caller system_caller_cleanup_safety
system_diagnostics system_enforcement system_enforcement_cleanup_safety system_guest
system_info system_probe_decision system_probe_sandbox_cleanup_safety system_qualification
system_remote_accounts system_runner system_runner_cleanup_safety system_snapshots systemd_unit
terminal_cleanup_safety test_account_password test_activity test_artifacts test_launchers
test_retention_cleanup_safety test_runner_policy test_storage_cleanup_safety thunder ui_artifacts_cleanup_safety
ui_cleanup_safety ui_watch ui_watch_cleanup_safety uninstall unit_test_launcher usage_query_retry verify_test_traceability
vm_config vm_control_cleanup_safety vm_transport vm_watch_session_cleanup_safety watch_activity watch_output
write_e2e write_e2e_cleanup_safety
""".split())

# Interrupted write-e2e close-out recovery reuses private pytest checkouts and
# waited launcher/agent doubles. No live VM, display, cache or shared mutation;
# the existing compatible unit and cleanup classifications remain applicable.

# Baseline mode/update/reboot tests mock every VM/package
# mutation. Version checks spawn only bounded read-only dpkg comparisons with
# no shared mutable files, sockets, displays, package locks or heavy fixtures.
# These modules remain compatible in both unit and cleanup scheduling.
# Synthetic-file guest import checks add only a bounded isolated Python child
# with captured pipes; private tmp_path files and mocked SSH retain compatibility.
# Online restore, explicit recovery and CPU rollback additions use the same
# private VM doubles and tiny tmp_path XML/credential files; no real VM, socket,
# display, account or process is touched. Both scheduler classifications hold.
# Resume refusal and delayed-clock checks retain that isolation: real journals
# are tmp_path-local and VM/SSH/time operations are process-local doubles.
# Restored-network checks also mock link updates, carrier waits and ownership
# replacement; they use no real network, VM or timer resource.
# Maintenance viewer carrier/identity checks use only in-memory XML and API doubles.
# Explicit VM selection adds registry reads and private launcher-binding records.
# Public command refusals own short-lived, waited children with captured pipes;
# they stop before authorization, session allocation, sockets or live VM access.
# Installer desktop-entry checks keep each VM's icon/entry in tmp_path. Existing
# unit and cleanup classifications remain compatible; no build admission needed.
# Snapshot/suite/maintenance cleanup tests use private VM doubles;
# qualification storage uses private retention trees. Repair
# loop and write-E2E tests use private checkouts and recorded child identities;
# UI watcher tests use private sockets/memfds. E2E case contracts use API doubles
# or isolated Perl workers. Storage and startup-cache checks use private test
# trees and retention journals. None operates the installed product or test VM.
# Package-build cleanup uses a synthetic checkout and private scratch directory;
# launcher rendering uses in-memory terminals, private PTYs and temporary logs.
# Combined watcher output tests use private storage/locks and mocked launches;
# they never start a runner, desktop service or VM, and need no exclusive resource.
# Its Make alias check waits for one harmless shell fixture in a private checkout.
# Checkout discovery adds tiny private Git worktrees and a joined background
# thread; it has no shared Git state, runtime socket, cache, desktop or VM.
# Multi-VM transport isolation uses bounded, joined private threads/queues and
# process-local API doubles; registry tests use tmp_path, with no live VM/socket.
# Both launchers' blocker decisions use checkout-private question locks/files and bounded threads;
# pause/reconnect tests own all fake agent children. No live Codex/VM is used.
# Host restart/recovery additions use private retention/activity locks and
# identity-recorded, waited session/repair doubles. VM queue selection only
# reads configuration; no live VM, display, bus, shared cache or heavy fixture.
# Existing compatible classifications remain valid for these modules.
# VM selector regressions edit only private tmp_path JSON registries and mock
# dispatch. Reconnect coverage reuses the recorded, waited session child; the
# configured-identity fixture reads checkout JSON without touching VM resources.
# Existing compatible unit, cleanup and viewer classifications still apply.
# Challenge, install, reboot and package-authority contracts mock host/guest
# mutations; app-row, feedback and no-approver reads use accessibility doubles.
# Ineligible-approver fixture checks use only in-memory NSS/AccountsService
# doubles; its journey adds private tmp_path evidence, with no live VM or bus.
# Feedback replacement also runs short, isolated Perl API-double children with
# captured pipes and a timeout; it writes no shared files or caches.
# Feedback block semantics also validate standalone imports in a bounded,
# waited isolated Python child; no shared files, caches, sockets or buses.
# Package-content tests build small archives in tmp_path and run only bounded,
# read-only dpkg-deb children. Suite tests use the same private archive fixtures
# with mocked VM operations; neither needs build admission or exclusive state.
# LIFE01 checks in e2e_toggle use the same bounded Perl children and private
# tmp_path contexts; accessible_e2e_ui uses in-memory trees and mocked transport.
# Jordan FLOW16 adds private recorder requests and in-memory child receipts;
# existing compatible unit classifications and cleanup partitions still apply.
# Its standalone observer check runs one bounded isolated Python child with
# captured pipes in tmp_path; invalid arguments stop before UI/account access.
# It needs no display, bus, shared cache, process cleanup or build admission.
# Their existing compatible unit classifications remain applicable.
# Fedora packaging compiles only the same three small native helpers as the
# existing package-payload fixture, in a module-private tmp_path tree. Source
# archives, authselect models and concurrent-build tests use private outputs,
# waited children or bounded joined threads; no host account, package database,
# VM, network, bus, display, shared cache or package install is touched. These
# modules and the changed package support fixtures remain compatible in unit.
# RPM builder checks add private recipe/spec contexts and process-local Podman
# doubles only. They neither pull images nor use real container storage/network;
# setup entrypoint children keep their trace and VM registry in private trees.
# COPR recipe checks use a private source checkout and bounded, waited children
# with DNF/RPM command doubles. Shared storage owns scratch beneath that checkout;
# no real dependency install, container cache, network or host package DB is used.
# Installer RPM coverage uses tmp_path package/command doubles and bounded,
# waited Make children. It adds no real RPM database, DNF transaction, network,
# privileged process or shared cache; installer remains compatible in unit.
# RPM post-transaction parity checks execute rendered shell in the existing
# private package machine with account/service doubles and bounded, waited
# children. No installed product or shared resources; rpm_packaging stays unit.
# Fedora readiness regressions reuse those command doubles and existing staged
# Fedora/Ubuntu payload fixtures. Unit parsing and activation comparisons add
# only private files; no real systemd, SELinux policy, VM or extra build fixture.
# The packaging modules retain their compatible unit classifications.
# Configuration exclusion and dual policy-file regressions use only private
# fixture trees and bounded command/launcher doubles. No live bus, service,
# daemon or VM; configuration and execution_policy remain compatible units.
# File-backend preparation/rollback cases in package_activation and removal use
# private tiny configuration trees; no live daemon or shared host configuration.
# Root maintenance logout checks use process-local account/session/command
# doubles; no real identity changes, session, bus or display. Trust-readiness
# checks use private tiny manifests and fake command/clock results. Existing
# e2e_desktop_session and package_activation compatible classifications hold.
# Child-module trust checks reuse private staged payloads and relocated lifecycle
# machines, tiny hashes/files and waited command doubles. They touch no host
# trust database, service, bus, VM or shared cache; existing packaging, activation,
# configuration and removal modules remain compatible, with no added build load.
# VM input-file regressions use tiny private pytest files, a sparse oversized
# sentinel, private FIFO and process-local stdin/transport doubles. No real VM,
# host service, socket or input descriptor is changed; vm_control_cleanup_safety
# and vm_config retain compatible scheduling in unit and cleanup inventories.
# Restored-off maintenance recovery uses private lease journals, tiny fixture
# disks and mocked VM/inspection calls, including a simulated restart during
# audit. It adds no live VM or shared resource; vm_control remains compatible.
# Missing console-timeout preparation checks use the existing in-memory guestfs
# fixture only; baseline_fixtures retains compatible unit/cleanup scheduling.
# Readiness removal/retry tests use the same private shell machine and bounded
# command doubles, including ActiveState; they do not contact host systemd.
# Parent privacy link coverage extends the existing in-memory accessibility
# matrix and bounded, waited Perl doubles. Launcher and recorder checks retain
# private tmp_path files and mocked VM/transport; no shared resource is added.
# Manual baseline retirement regressions use the existing private rig, synthetic
# ownership records and mocked domain APIs. No live VM, mount, process or socket
# is touched; prepare_baseline remains compatible and needs no build admission.
# Never-started graphical cleanup uses private rig journals and mocked libvirt
# APIs only; graphical_smoke_cleanup_safety stays compatible in both schedulers.
# Parent custom-save ordering tests hold callbacks in memory and use mocked
# widgets only; they add no timers, threads, filesystem or display resources.
# Public AT-SPI transport tests use in-memory RPC/connection doubles only;
# traversal caches and object identities are local to each test instance.
# UI timing regressions in test_regression use in-memory clocks/sinks and
# synchronous doubles plus one waited pytest subprocess in private tmp_path.
# Its pipe descriptor closes at session end; no display, bus or shared file.
# Wait-trace retry/deadline/interrupt tests use in-memory predicates and clocks;
# tracing preserves the unit and UI inventory resource classifications.
# Protocol query/occupancy and stream-write timing checks use in-memory clocks,
# sinks and synchronous transport doubles in test_regression; no added resource.
# Parent continuous-activity checks mock session identity, privilege transitions
# and gsettings calls; diagnostic checks mock the read-only screen-saver query.
# Neither touches the host session, settings, bus or display.
# Preparation retry and named-VM activity regressions use private tmp_path
# journals/locks, bounded waited Python children and mocked VM/SSH controllers.
# Baseline, test_activity, app-snapshot, retention and graphical recovery retain
# compatible scheduling; there are no shared guests, displays or heavy builds.
# Retention-budget diagnostic checks use tiny private tmp_path input/log trees
# and process-local read-failure doubles. test_storage_cleanup_safety remains
# compatible; no live evidence, VM, process or shared storage owner is touched.

# Full fixture construction uses private native/Snap/Flatpak output and HOME/XDG
# trees, reads installed runtime inputs and owns its native child. Keep it out
# of ordinary unit packing: use the existing artifact CPU/RAM/I/O admission and
# companion policy, which already covers this same fixture builder.
BUILD_REVIEWED = frozenset({'test_applications'})

# Ordering hints only; default weight balances selected case counts. Keep whole
# module fixtures together; work_units owns the function-private exception.
ESTIMATES = {
    **CLEANUP_ESTIMATES,
    'test_regression.py': 30,
    'test_regression_schedule.py': 25,
    'test_regression_session.py': 15,
    'test_regression_ui_selection.py': 25,
    'test_broker_properties.py': 20,
    'test_broker_state_machine.py': 20,
    'test_package_payload.py': 15,
    'test_test_applications.py': 60,
}


def buckets(nodeids):
    if not nodeids or len(set(nodeids)) != len(nodeids):
        raise ValueError('Unit inventory is empty or contains duplicate test IDs')
    files = {}
    for nodeid in nodeids:
        filename, separator, case = nodeid.partition('::')
        path = PurePosixPath(filename)
        if (not separator or not case or path.parts[:2] != ('tests', 'unit')
                or '..' in path.parts or filename != path.as_posix()
                or not path.name.startswith('test_') or path.suffix != '.py'):
            raise ValueError('Unit inventory contains an invalid test path')
        files.setdefault(filename, []).append(nodeid)
    modules, builds, exclusive = [], [], []
    for path, ids in sorted(files.items()):
        filename = PurePosixPath(path).name
        reviewed = (len(PurePosixPath(path).parts) == 3
                    and filename.removeprefix('test_').removesuffix('.py') in REVIEWED)
        build = (len(PurePosixPath(path).parts) == 3
                 and filename.removeprefix('test_').removesuffix('.py') in BUILD_REVIEWED)
        bucket = Bucket('Unit — ' + path.removeprefix('tests/unit/'), (path,), tuple(ids),
                        'unit' if reviewed else 'artifacts' if build else 'unit-exclusive',
                        ESTIMATES.get(filename, .3 + len(ids) * (
                            .02 if filename.endswith('_cleanup_safety.py') else .05)))
        if reviewed:
            modules.extend(work_units(path, ids, bucket.kind, bucket.estimate))
        else:
            (builds if build else exclusive).append(bucket)
    groups = [[] for _ in range(min(HOST_WORKERS, len(modules)))]
    estimates = [0.0] * len(groups)
    for module in sorted(modules, key=lambda item: (-item.estimate, item.name)):
        index = min(range(len(groups)), key=lambda index: estimates[index])
        groups[index].append(module)
        estimates[index] += module.estimate
    result = [Bucket(f'Unit — Bucket {index + 1}',
                     tuple(path for module in group for path in module.paths),
                     tuple(node for module in group for node in module.nodeids),
                     'unit', estimates[index]) for index, group in enumerate(groups)]
    return result + builds + exclusive
# Completed-result discard tests use private pytest journals, local descriptor
# locks and process-local dispatcher/VM doubles. No live VM or shared storage;
# test_test_retention_cleanup_safety remains compatible in both inventories.
