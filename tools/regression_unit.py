"""Balance reviewed unit modules without splitting their fixtures.

The reviewed modules use process-local doubles, read-only checkout inputs and
private temporary trees. Their real subprocesses use private outputs, relocated
system paths, private sockets or recorded child identities. The launcher disables
shared pytest/Hypothesis caches and aggregate retention in every unit worker.
Unknown modules fail closed to exclusive execution; new modules must receive an
isolation/resource review and classification before their work is complete.

Regression session tests keep both session gates and cancellation records in
private pytest trees; recorded harmless children are released and reaped by
their fixture. Cross-scope reconnect tests remain safe for compatible overlap.
Public AT-SPI and observation-cache regressions use process-local bus doubles,
mock clocks and immutable synthetic trees; they open no real sockets or displays.
Their asynchronous batch probe drains a private GLib context with synthetic
callbacks and restores the thread-default context; no shared loop or thread runs.
Native fixture cleanup probes compile in tmp_path and change signal masks only
inside their explicitly spawned synthetic GUI child, never in the test worker.
The UI cleanup crash probe owns one small Python child and tmp_path log/script;
the child disables core files and aborts only itself, with no display or bus.
Allowance qualification tests reuse bounded, synchronously reaped Perl children
with captured pipes and synthetic UI values. Fresh-thirty recorder cases use
only the existing private tmp_path collector; no additional shared resource.
Prerequisite-repair launcher tests reuse private checkout/session trees and the
existing recorded owner/agent doubles; they start no real Codex or VM process.
Model-routing and usage-recording checks use those same private trees and tiny
JSON records, in-memory renderer callbacks and recorded child doubles. No new
shared cache, network, bus, display or heavy fixture; compatible overlap remains.
Named qualification preparation coverage reads wrapper ASTs and mocks allocation,
builder execution and privilege checks; no builds, shared writes or VM access.
Attachment boundary tests retain private tmp_path files (<= 5 MiB+1 each),
bounded in-memory bytes and waited private Perl children; compatible in unit
and cleanup scheduling, with no build, shared cache, bus, display or VM.
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
"""

from pathlib import PurePosixPath

from regression_cleanup import ESTIMATES as CLEANUP_ESTIMATES, work_units
from regression_resources import HOST_WORKERS
from regression_ui import Bucket


REVIEWED = frozenset("""
about_dialog accessible_e2e_ui accessible_observation adapters app_policy app_termination appsnapshot_cleanup_safety apt_removal_notice
authentication_evidence automation_ids backing_verification_cleanup_safety baseline_guest_cleanup_safety broker_properties
broker_state_machine build_package build_test_artifacts bump_version catalog catalog_scope challenges_cleanup_safety child_preview
child_preview_cleanup_safety clean_install_cleanup_safety codex_test_rules config core coverage_generation customer_reboot_cleanup_safety data_migration
dbus_harness_cleanup_safety desktop_session_cleanup_safety dev_privileges dev_tool_installation
diagnostic_export diagnostic_privacy diagnostic_report diagnostics document_checks
dynamic_account_fixture e2e_app_rows e2e_asset_transfer_cleanup_safety e2e_broker_startup_observations
e2e_case_composition e2e_command_help e2e_controller_qualification_cleanup_safety e2e_desktop_keyring
e2e_desktop_session e2e_disabled_child e2e_evidence e2e_feedback_read e2e_fresh_desktop
e2e_execution_cleanup_safety e2e_files_cleanup_safety e2e_fixture_credentials_cleanup_safety e2e_gdm_helper
e2e_gdm_navigation e2e_gdm_pixels e2e_gdm_product_free e2e_gdm_recipient
e2e_install_helper e2e_install_password_observation e2e_installation_boundary
e2e_installation_observations e2e_inventory e2e_keyring_fixture_cleanup_safety
e2e_kiosk_eligible_choices e2e_kiosk_valid_duration e2e_kiosk_entry e2e_kiosk_no_approver e2e_kiosk_no_child e2e_leased_recording_cleanup_safety
e2e_license_viewer
e2e_matched_screens e2e_needle_inputs e2e_observation_transport e2e_parent_search_launch
e2e_plan e2e_pointer_helper e2e_progress
e2e_provenance e2e_recording_cleanup_safety e2e_recording_credentials e2e_runner
e2e_request_choices e2e_request_exit e2e_secret_variables e2e_serial_helper
e2e_serial_observation e2e_shell_search e2e_shell_search_results e2e_shutdown
e2e_startup_cache_cleanup_safety e2e_startup_observations e2e_suite_cleanup_safety
e2e_terminal e2e_terminal_provider e2e_toggle e2e_vt6_authentication e2e_vt6_command e2e_vt6_controller
e2e_vt6_diagnostic e2e_vt6_pixels e2e_vt6_prompt e2e_vt6_recipient e2e_vt6_shell e2e_watch
e2e_watch_cleanup_safety e2e_worker_cleanup_safety error_reporting execution_policy
execution_policy_ready execution_probe_cleanup_safety extension_manager feedback_collection
feedback_transport fix_tests fix_tests_cleanup_safety fixture_cleanup_safety fixture_gui_adapter floating_islands
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
regression_selection regression_session regression_ui regression_ui_selection regression_unit
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
# Both launchers' blocker decisions use checkout-private question locks/files and bounded threads;
# pause/reconnect tests own all fake agent children. No live Codex/VM is used.
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
# Its standalone observer check runs one bounded isolated Python child with
# captured pipes in tmp_path; invalid arguments stop before UI/account access.
# It needs no display, bus, shared cache, process cleanup or build admission.
# Their existing compatible unit classifications remain applicable.
# Parent custom-save ordering tests hold callbacks in memory and use mocked
# widgets only; they add no timers, threads, filesystem or display resources.
# Public AT-SPI transport tests use in-memory RPC/connection doubles only;
# traversal caches and object identities are local to each test instance.
# Parent continuous-activity checks mock session identity, privilege transitions
# and gsettings calls; diagnostic checks mock the read-only screen-saver query.
# Neither touches the host session, settings, bus or display.

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
