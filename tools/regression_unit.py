"""Balance reviewed unit modules without splitting their fixtures.

The reviewed modules use process-local doubles, read-only checkout inputs and
private temporary trees. Their real subprocesses use private outputs, relocated
system paths, private sockets or recorded child identities. The launcher disables
shared pytest/Hypothesis caches and aggregate retention in every unit worker.
Unknown modules fail closed to exclusive execution; new modules must receive an
isolation/resource review and classification before their work is complete.
"""

from pathlib import PurePosixPath

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
e2e_execution_cleanup_safety e2e_fixture_credentials_cleanup_safety e2e_gdm_helper
e2e_gdm_navigation e2e_gdm_pixels e2e_gdm_product_free e2e_gdm_recipient
e2e_install_helper e2e_install_password_observation e2e_installation_boundary
e2e_installation_observations e2e_inventory e2e_keyring_fixture_cleanup_safety
e2e_kiosk_eligible_choices e2e_kiosk_entry e2e_kiosk_no_approver e2e_kiosk_no_child e2e_leased_recording_cleanup_safety
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
package_install_cleanup_safety
package_os_gate package_payload package_removal package_transaction_notice pam_runtime_cap
parent_about_cleanup_safety parent_about_worker parent_access_worker parent_client
parent_discovery_worker parent_grid_pixels parent_main parent_needles
parent_setup_cleanup_safety ppa_build preferences prepare_baseline
prepare_baseline_cleanup_safety prepare_baseline_tool prepare_vm prepare_vm_contract
preview_screen privileged_test_runner probe_bus_client_cleanup_safety
probe_channel_cleanup_safety probe_generation_cleanup_safety product_free_entry_cleanup_safety provision publish
publish_source_integrity publishing_tests qualification_storage_cleanup_safety read_only_launcher regression regression_cleanup
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
vm_config vm_control_cleanup_safety vm_transport vm_watch_session_cleanup_safety watch_activity
write_e2e write_e2e_cleanup_safety
""".split())

# Snapshot/suite/maintenance cleanup tests use the
# private VM doubles; qualification storage uses private retention trees. Repair
# loop and write-E2E tests use private checkouts and recorded child identities;
# UI watcher tests use private sockets/memfds. E2E case contracts use API doubles
# or isolated Perl workers. Storage and startup-cache checks use private test
# trees and retention journals. None operates the installed product or test VM.
# Package-build cleanup uses a synthetic checkout and private scratch directory;
# launcher rendering uses in-memory terminals, private PTYs and temporary logs.
# Challenge, install, reboot and package-authority contracts mock host/guest
# mutations; app-row, feedback and no-approver reads use accessibility doubles.

# Full fixture construction uses private native/Snap/Flatpak output and HOME/XDG
# trees, reads installed runtime inputs and owns its native child. Keep it out
# of ordinary unit packing: use the existing artifact CPU/RAM/I/O admission and
# companion policy, which already covers this same fixture builder.
BUILD_REVIEWED = frozenset({'test_applications'})

# Ordering hints only; default weight balances selected case counts. Keep whole
# modules together, including their module-scoped native build fixtures.
ESTIMATES = {
    'test_e2e_suite_cleanup_safety.py': 10,
    'test_fix_tests_cleanup_safety.py': 20,
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
                        ESTIMATES.get(filename, .3 + len(ids) * .05))
        (modules if reviewed else builds if build else exclusive).append(bucket)
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
