"""Schedule retained tests without splitting module fixtures.

Retained modules use private pytest files, locks and process-local doubles.
Owned children are bounded and reaped; no live VM, service, display or shared
cache is acquired. Deleting tests adds no resource owner or overlap requirement.
Unknown modules remain exclusive pending review.

The extension-manager transport cases own private Unix socketpairs/pipes and
GLib sources; their credential-drop subprocess is mocked. Every descriptor and
source is released within its case; no live bus, account or shared path is used.

Kiosk approval safety uses process-local clocks/observation doubles and bounded,
reaped Perl children with captured pipes. Credential-reader checks use tiny
pytest-private canary files and process-local caller doubles, never real host
configuration. No bus, display, VM or shared cache is opened; unit overlap is safe.
"""

from pathlib import PurePosixPath
from regression_cleanup import ESTIMATES as CLEANUP_ESTIMATES, work_units
from regression_resources import HOST_WORKERS
from regression_ui import Bucket


REVIEWED = frozenset("""
system_first_configure
system_removal_faults
build_package
build_test_artifacts
publish
publishing_tests
ppa_build
sync_whatsnew
about_dialog
baseline_snap_safety
baseline_flatpak_safety
adapters
app_policy
app_termination
apt_removal_notice
broker_properties
broker_state_machine
catalog
catalog_scope
child_preview
config
core
data_migration
diagnostic_export
diagnostic_privacy
diagnostic_report
diagnostics
error_reporting
execution_policy
execution_policy_ready
execution_probe_cleanup_safety
extension_manager
fedora_execution_policy
fedora_pam
feedback_collection
feedback_transport
floating_islands
graphical_lease
installer
kiosk_confinement
kiosk_approval_safety
kiosk_login
kiosk_model
kiosk_rendering
licensing
lightning
localization
logs
package_activation
package_configuration
package_command_safety
package_content
package_inputs
package_os_gate
package_payload
package_purge_cleanup_safety
package_removal
package_transaction_notice
pam_runtime_cap
parent_client
parent_main
parent_native_surface
preferences
prepared_kiosk_pam
privileged_test_runner
probe_bus_client_cleanup_safety
probe_channel_cleanup_safety
probe_generation_cleanup_safety
publish_source_integrity
regression
regression_cleanup_safety
release_signing
request_selections
request_time_estimate
rpm_packaging
service_contract
session_limit_check
system_guest
system_info
systemd_unit
test_checkpoint
test_launchers
test_runner_policy
thunder
uninstall
unit_test_launcher
usage_query_retry
vm_backup_cleanup_safety
vm_control_cleanup_safety
vm_pool
whats_new
""".split())

TARGET_BATCH_SECONDS = 90

# vm_control_cleanup_safety retains module-local guest doubles and private lease
# files. Its live-probe check uses a unique abstract socket and drains its thread
# before releasing the lease; no libvirt or shared endpoint is accessed.

ESTIMATES = {
    **CLEANUP_ESTIMATES,
    'test_test_launchers.py': 6,
    'test_regression.py': 30,
    'test_broker_properties.py': 20,
    'test_broker_state_machine.py': 20,
    'test_package_payload.py': 15,
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
    modules, exclusive = [], []
    for path, ids in sorted(files.items()):
        filename = PurePosixPath(path).name
        reviewed = (len(PurePosixPath(path).parts) == 3
                    and filename.removeprefix('test_').removesuffix('.py') in REVIEWED)
        bucket = Bucket('Unit — ' + path.removeprefix('tests/unit/'), (path,), tuple(ids),
                        'unit' if reviewed else 'unit-exclusive',
                        ESTIMATES.get(filename, .3 + len(ids) * (
                            .02 if filename.endswith('_cleanup_safety.py') else .05)))
        if reviewed:
            modules.extend(work_units(path, ids, bucket.kind, bucket.estimate))
        else:
            exclusive.append(bucket)
    groups = [[] for _ in range(min(HOST_WORKERS, len(modules)))]
    estimates = [0.0] * len(groups)
    for module in sorted(modules, key=lambda item: (-item.estimate, item.name)):
        index = min(range(len(groups)), key=lambda index: estimates[index])
        # Queue short batches rather than pinning the entire inventory to four
        # workers. A free worker can then take the next batch when estimates
        # differ from actual runtimes. An oversized module keeps its fixtures.
        if groups[index] and estimates[index] + module.estimate > TARGET_BATCH_SECONDS:
            index = len(groups)
            groups.append([])
            estimates.append(0.0)
        groups[index].append(module)
        estimates[index] += module.estimate
    result = [Bucket(f'Unit — Bucket {index + 1}',
                     tuple(path for module in group for path in module.paths),
                     tuple(node for module in group for node in module.nodeids),
                     'unit', estimates[index]) for index, group in enumerate(groups)]
    return result + exclusive
