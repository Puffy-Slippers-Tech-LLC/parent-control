"""Balance cleanup work across the existing branches without splitting fixtures.

Reviewed modules use pytest-private temporary trees, process-local doubles and
explicitly owned children/descriptors. test_environment disables shared caches
and aggregate retention registration. Keep future modules exclusive until their
fixtures and external resources have been reviewed; never omit their cases.
"""

# Explicit VM-name forwarding retains private journals and process-local API
# doubles; cleanup checks add no real guest, desktop, socket or shared cache.
# VM rename refusal/rollback coverage uses private pytest records and mocked
# libvirt calls; the existing compatible vm_control classification still applies.
# Per-VM leases, moved lease identity and legacy-journal refusal checks retain
# only private tmp_path locks/journals and process-local libvirt doubles. Storage,
# qualification and VM-control modules keep their compatible classification.

from pathlib import PurePosixPath

# TIME03 deadline/recorder additions retain private tmp_path collectors and
# process-local worker, clock and UI doubles; both existing classifications hold.

from regression_ui import Bucket
from regression_resources import HOST_WORKERS


REVIEWED = frozenset('''
appsnapshot backing_verification baseline_guest challenges child_preview clean_install customer_reboot dbus_harness e2e_asset_transfer
e2e_controller_qualification e2e_execution e2e_files e2e_fixture_credentials
e2e_keyring_fixture e2e_leased_recording e2e_recording e2e_startup_cache e2e_suite
e2e_watch e2e_worker execution_probe fixture fix_tests
graphical_attachment graphical_serial graphical_smoke graphical_transport
graphical_worker installed_journey desktop_session package_authority package_install parent_about parent_setup prepare_baseline product_free_entry
probe_bus_client probe_channel probe_generation qualification_storage
regression repeated_operations screen_preview screenshot session_expiry system_accounts system_agent
system_caller system_enforcement system_probe_sandbox system_runner storage_migration terminal
test_retention test_storage ui ui_artifacts ui_watch vm_control vm_watch_session write_e2e
'''.split())

# Online snapshot, baseline CPU and maintenance recovery/rollback regressions
# Per-VM spectator publication cleanup uses private tmp_path registrations and
# mocked servers; it touches no live sockets, processes, VM leases or displays.
# retain private tmp_path journals and VM/transport doubles. No new shared
# resource or heavy fixture is introduced; their reviewed buckets still apply.
# Resume refusal and delayed-clock checks use those same private journals and
# VM/SSH/time doubles, with no live guest, host clock or process mutation.
# Restored-network checks mock link updates, carrier waits and replacement;
# both schedulers retain their private, compatible classification.
# Maintenance viewer carrier/identity checks use in-memory XML and API doubles.
# Synthetic file checks use private tmp_path trees, mocked SSH and a bounded
# isolated Python import child; no accounts, VM, sockets, caches or shared writes.
# Attachment boundary profiles add <= 5 MiB+1 files in private tmp_path trees;
# their independent readback/cleanup remains compatible with other buckets.
# ZIP reader/refusal additions retain private trees and bounded in-memory ZIPs;
# no new process, account, socket or shared resource in either scheduler.
# Source-change checks use tiny private files and process-local transport/write
# doubles, retaining compatible cleanup and unit scheduling.
# Diagnostic-export checks retain pytest-private Downloads and bounded ZIP bytes
# (at most 16 MiB expanded), mocked SSH and waited isolated import children.
# They add no shared files, caches, accounts, buses, displays or live VM access.
# Installed journey/setup/About tests write only beneath tmp_path and replace
# guest operations with process-local doubles. About's matcher reads repository
# fixtures in its own Perl child; watcher sockets, processes and signals are
# mocked. These modules therefore share the same isolation as cleanup buckets.
# The ineligible-approver plan uses those same private journey/fixture doubles;
# it introduces no real account, VM, socket, process or shared cache in host tests.
# Fresh-thirty allowance adds recorder cases within that same private collector
# and mocked guest lifetime, retaining compatible installed-journey scheduling.
# Parent privacy adds a plan to those function-private recorder/VM doubles;
# unit and cleanup scheduling retain the same compatible isolation.
# Prerequisite-repair launcher cases retain the existing private checkout and
# identity-recorded owner/agent fixture, with no new cleanup or shared resource.
# Routing/restart and usage-recording cases use the same private owner/agent
# doubles and tiny JSON files; both unit and cleanup classifications stay compatible.
# App-snapshot and suite tests use private locks with mocked libvirt sources;
# baseline-guest uses an in-memory guestfs double; update/reboot checks mock all
# package/VM operations and use tmp_path for guest entry records. Fix-tests owns every child it
# starts beneath a private checkout, and UI-watch uses recorded process doubles
# plus unique private sockets. Keyring/VM watcher safety uses process-local
# doubles and socket pairs. Storage, migration and startup-cache checks use
# private trees and journals; write-E2E owns its children in a private checkout.
# Both launchers' paused-question tests keep decisions and observer locks in that checkout,
# and fixture teardown cancels/reaps only those recorded workflow children.
# They do not share mutable state across workers.
# Suite package-identity fixtures also use tiny private Debian archives and
# bounded, read-only dpkg-deb children; no compiler, package install or VM.
# Challenge/repeated-operation contracts use isolated Perl API doubles. Clean
# install, package authority/install, product-free entry and reboot contracts
# mock all system/guest mutations and write evidence only into pytest-private
# trees. Their unit classification applies to the cleanup phase too.
# UI crash logging owns one small Python child and private tmp_path script/log.
# It disables core files before self-abort; no global crash files, bus or display.
# Native fixture ownership checks compile only into tmp_path. Their synthetic
# child blocks/waits for SIGTERM locally; no worker signal mask is changed.

# Measured four-worker costs guide packing only; never reuse passing results.
# Recorder shards include their concurrent durable-write cost (higher than a
# single worker's elapsed time). Recalibrate from --durations=0 after growth.
ESTIMATES = {'test_backing_verification_cleanup_safety.py': 12,
             'test_fix_tests_cleanup_safety.py': 38,
             'test_write_e2e_cleanup_safety.py': 54,
             'test_installed_journey_cleanup_safety.py': 181,
             'test_e2e_leased_recording_cleanup_safety.py': 12,
             'test_e2e_suite_cleanup_safety.py': 21,
             'test_graphical_lease.py': 8.5,
             'test_e2e_execution_cleanup_safety.py': 20,
             'test_e2e_recording_cleanup_safety.py': 10,
             'test_test_storage_cleanup_safety.py': 17,
             'test_e2e_startup_cache_cleanup_safety.py': 10,
             'test_vm_control_cleanup_safety.py': 6.5,
             'test_e2e_controller_qualification_cleanup_safety.py': 2,
             'test_graphical_smoke_cleanup_safety.py': 2,
             'test_execution_probe_cleanup_safety.py': 3,
             'test_regression_cleanup_safety.py': 4,
             'test_test_retention_cleanup_safety.py': 16,
             'test_child_preview_cleanup_safety.py': 2,
             'test_appsnapshot_cleanup_safety.py': 1,
             'test_baseline_guest_cleanup_safety.py': 1,
             'test_ui_watch_cleanup_safety.py': 1}


def work_units(path, ids, kind, estimate):
    """Split only the reviewed function-isolated journey matrix into exact IDs.

    Its fixtures, recorder, evidence and mocks are all function-local. It has no
    shared module/class fixture, live guest, process or mutable output. Other
    modules remain whole, including unknown additions and their fixtures. Eight
    pieces leave enough packing choices alongside the slower launcher modules.
    Both unit and cleanup scheduling use this review and the same partition.
    """
    matrix = path == 'tests/unit/test_installed_journey_cleanup_safety.py'
    if not matrix or len(ids) < 32:
        return [Bucket(path, (path,), tuple(ids), kind, estimate)]
    groups = [[] for _ in range(8)]
    weights = [0.0] * len(groups)
    def weight(node):
        if '::test_shared_plan_records_before_input_and_latches_transition_failures[' in node:
            return 2.0 if '[None-' in node else 1.0
        return .05
    for node in sorted(ids, key=lambda node: (-weight(node), node)):
        index = min(range(len(groups)), key=lambda index: weights[index])
        groups[index].append(node)
        weights[index] += weight(node)
    total = sum(weights)
    return [Bucket(f'{path} [{index + 1}]', tuple(sorted(group)), tuple(sorted(group)),
                   kind, estimate * weights[index] / total)
            for index, group in enumerate(groups) if group]


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
            modules.extend(work_units(path, ids, 'cleanup',
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
