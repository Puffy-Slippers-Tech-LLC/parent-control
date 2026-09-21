"""Balance cleanup work across the existing branches without splitting fixtures.

Reviewed modules use pytest-private temporary trees, process-local doubles and
explicitly owned children/descriptors. test_environment disables shared caches
and aggregate retention registration. Keep future modules exclusive until their
fixtures and external resources have been reviewed; never omit their cases.
"""

from pathlib import PurePosixPath

from regression_ui import Bucket
from regression_resources import HOST_WORKERS


REVIEWED = frozenset('''
appsnapshot backing_verification baseline_guest child_preview dbus_harness e2e_asset_transfer
e2e_controller_qualification e2e_execution e2e_fixture_credentials
e2e_leased_recording e2e_recording e2e_suite e2e_watch e2e_worker execution_probe fixture fix_tests
graphical_attachment graphical_serial graphical_smoke graphical_transport
graphical_worker installed_journey desktop_session parent_about parent_setup prepare_baseline
probe_bus_client probe_channel probe_generation
regression screen_preview screenshot session_expiry system_accounts system_agent
system_caller system_enforcement system_probe_sandbox system_runner terminal
test_retention ui ui_artifacts ui_watch vm_control
'''.split())

# Installed journey/setup/About tests write only beneath tmp_path and replace
# guest operations with process-local doubles. About's matcher reads repository
# fixtures in its own Perl child; watcher sockets, processes and signals are
# mocked. These modules therefore share the same isolation as cleanup buckets.
# App-snapshot and suite tests use private locks with mocked libvirt sources;
# baseline-guest uses an in-memory guestfs double. Fix-tests owns every child it
# starts beneath a private checkout, and UI-watch uses recorded process doubles
# plus unique private sockets. They do not share mutable state across workers.

# Measured costs guide packing and dispatch only; never reuse passing results.
ESTIMATES = {'test_backing_verification_cleanup_safety.py': 11,
             'test_fix_tests_cleanup_safety.py': 14,
             'test_e2e_leased_recording_cleanup_safety.py': 10,
             'test_e2e_suite_cleanup_safety.py': 9,
             'test_graphical_lease.py': 7,
             'test_e2e_execution_cleanup_safety.py': 14,
             'test_e2e_recording_cleanup_safety.py': 8.5,
             'test_graphical_smoke_cleanup_safety.py': 4,
             'test_execution_probe_cleanup_safety.py': 3,
             'test_regression_cleanup_safety.py': 4,
             'test_test_retention_cleanup_safety.py': 4,
             'test_child_preview_cleanup_safety.py': 2,
             'test_appsnapshot_cleanup_safety.py': 1,
             'test_baseline_guest_cleanup_safety.py': 1,
             'test_ui_watch_cleanup_safety.py': 1}


def buckets(nodeids):
    if not nodeids or len(set(nodeids)) != len(nodeids):
        raise ValueError('cleanup inventory is empty or contains duplicate test IDs')
    files = {}
    for nodeid in nodeids:
        filename, separator, case = nodeid.partition('::')
        path = PurePosixPath(filename)
        if (not separator or not case or path.parts[:2] != ('tests', 'unit')
                or len(path.parts) != 3 or filename != path.as_posix()
                or not (path.name == 'test_graphical_lease.py'
                        or (path.name.startswith('test_') and path.name.endswith('cleanup_safety.py')))):
            raise ValueError('cleanup inventory contains an invalid test path')
        files.setdefault(filename, []).append(nodeid)
    modules, exclusive = [], []
    for path, ids in sorted(files.items()):
        ids = sorted(ids)
        filename = PurePosixPath(path).name
        reviewed = (filename == 'test_graphical_lease.py'
                    or filename.removeprefix('test_').removesuffix('_cleanup_safety.py') in REVIEWED)
        if not reviewed:
            exclusive.append(Bucket('Cleanup — ' + filename.removeprefix('test_').removesuffix('.py'),
                                    (path,), tuple(ids), 'cleanup-exclusive', 1 + len(ids) * .05))
        else:
            modules.append(Bucket(path, (path,), tuple(ids), 'cleanup',
                                  ESTIMATES.get(filename, .3 + len(ids) * .02)))
    groups = [[] for _ in range(min(HOST_WORKERS, len(modules)))]
    estimates = [0.0] * len(groups)
    for module in sorted(modules, key=lambda item: (-item.estimate, item.name)):
        index = min(range(len(groups)), key=lambda index: estimates[index])
        groups[index].append(module)
        estimates[index] += module.estimate
    result = [Bucket(f'Cleanup — Bucket {index + 1}',
                     tuple(path for module in group for path in module.paths),
                     tuple(node for module in group for node in module.nodeids),
                     'cleanup', estimates[index]) for index, group in enumerate(groups)]
    result.extend(exclusive)
    return result
