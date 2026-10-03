"""Balance cleanup work across the existing branches without splitting fixtures.

Reviewed modules use pytest-private temporary trees, process-local doubles and
explicitly owned children/descriptors. test_environment disables shared caches
and aggregate retention registration. Keep future modules exclusive until their
fixtures and external resources have been reviewed; never omit their cases.
"""
# Fresh child denial recorder/worker coverage uses only existing private pytest
# evidence and waited Perl doubles. No new cleanup resource or live access;
# challenges and installed-journey remain compatible in cleanup and unit scopes.
# Panel focus/Enter order checks reuse challenges' same waited Perl API double
# and private evidence; no new process, display, bus or shared cleanup resource.
# Shell approval adds sealed-input doubles and private installed-recorder files
# to challenges/installed-journey; both unit and cleanup overlap remain compatible.
# The approval observer rendezvous uses the same attempt-private input/ack files
# and synchronous transport doubles; it adds no independent cleanup lifetime.

# Explicit VM-name forwarding retains private journals and process-local API
# doubles; cleanup checks add no real guest, desktop, socket or shared cache.
# App-snapshot --y/VM-picker/confirmation regressions use process-local input
# and TTY doubles with the existing private launcher fixture; appsnapshot stays
# compatible, without real VM operations, privilege, shared locks or storage.
# Root guest probes reuse those private lease/scratch trees and mocked transport
# streams; snapshot connection checks mock SSH and the clock. Both existing
# VM-control and app-snapshot cleanup buckets remain compatible.
# VM input-file checks use private pytest files/FIFO and in-memory descriptor,
# stdin and SSH doubles, without touching a live VM, host stdin or shared state.
# vm_control_cleanup_safety retains its existing compatible cleanup classification.
# Restored-off maintenance audits use the same private lease/disk fixtures and
# mocked VM/guest inspection, with no live VM, socket or shared state. Existing
# VM-control compatible scheduling remains appropriate in both inventories.
# Missing console-timeout preparation checks use only the existing in-memory
# guestfs fixture; baseline_fixtures retains compatible unit/cleanup scheduling.
# Fedora snapshot backend/proof checks retain private tmp_path locks and mocked
# builders, guestfs and VM transport. App-snapshot, system-runner and suite
# cleanup classifications stay compatible; no real build, VM or shared resource.
# VM rename refusal/rollback coverage uses private pytest records and mocked
# libvirt calls; the existing compatible vm_control classification still applies.
# Per-VM leases, moved lease identity and legacy-journal refusal checks retain
# only private tmp_path locks/journals and process-local libvirt doubles. Storage,
# qualification and VM-control modules keep their compatible classification.
# Never-started recovery in graphical_smoke_cleanup_safety uses private rig
# journals and mocked VM APIs, without live processes, displays or shared paths.
# Its existing compatible cleanup classification remains appropriate.
# Sandbox address-family refusal/netlink checks use process-local socket and guest
# doubles only. Existing private staging/drop-in fixtures and descriptor cleanup
# are unchanged; system_probe_sandbox remains compatible with unit and cleanup.

from pathlib import PurePosixPath

# TIME03 deadline/recorder additions retain private tmp_path collectors and
# process-local worker, clock and UI doubles; both existing classifications hold.
# VM Internet cleanup uses only pytest-private journals and process-local
# libvirt/filter/SSH doubles; it is compatible with other cleanup/unit buckets.
# LIFE06 Parent composition adds process-local UI doubles and private recorder
# replies to vm_internet; it opens no real display, bus, socket or guest.
# Native fixture placement/readback and source-keyed input tests own only private
# pytest files, process-local guest/SSH/GTK doubles and bounded waited Perl
# children. No real ownership mutation, VM, bus, display, shared path or cache;
# compatible overlap in cleanup and unit scheduling.
# Chinese asset checks use private/in-memory files, locale/font bytes and mocked
# transports only. No live package manager, VM, display, shared path or cache;
# the new module is compatible in both unit and cleanup inventories.
# Catalogue filter recorder additions reuse that installed-journey private
# evidence and process-local UI/worker doubles. No new cleanup resource or live
# access is added; its compatible unit and cleanup classifications remain.
# Legend recorder startup/comparison adds only existing private tmp_path records
# and process-local worker/UI doubles; installed-journey remains compatible in
# cleanup and unit scheduling, with no new owned resource or live access.

from regression_ui import Bucket
# TIME01 worker and recorder additions in challenges/installed-journey use only
# existing private pytest evidence and waited Perl children with mocked secrets.
# No live VM/display/bus or new shared resource; both classifications stay compatible.
# Access-choice recorder coverage keeps the installed-journey matrix's private
# evidence and process-local doubles; unit and cleanup compatibility is unchanged.
from regression_resources import HOST_WORKERS


# DESK13 shares those private doubles/evidence and waited Perl lifetimes; its
# installed attempt adds no cleanup owner beyond the product-free envelope.
# Host/VM repair-session overlap uses private workflow directories and waited
# test/agent doubles. The fixture cancels only its recorded owners; fix_tests
# remains compatible in both cleanup and unit scheduling, with no live VM/GUI.
REVIEWED = frozenset('''
desktop_language
vm_internet native_fixtures baseline_fixtures chinese_language_assets
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

# Missing-completion recovery uses private checkouts and waited owner/agent
# doubles under the existing write-e2e fixture. No live VM or shared mutable
# resource is added; cleanup and unit scheduling remain compatible.

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
# Fix-tests argument forwarding uses the same private checkout and reaped child
# doubles through retries/verification; no real tests, VM or shared resource.
# Escalation/diagnostic execution reuses those finite children and private JSON
# snapshots; cancellation waits for the recorded test double. Compatible in both
# inventories, with no live model, VM, shared cache or additional cleanup owner.
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
# Host recovery/restart additions keep retention/activity locks and evidence in
# tmp_path, with recorded, waited repair children and process-local VM doubles.
# Both unit and cleanup classifications remain compatible; no live VM,
# display, bus, shared cache or heavy construction is introduced.
# Suite package-identity fixtures also use tiny private Debian archives and
# bounded, read-only dpkg-deb children; no compiler, package install or VM.
# Challenge/repeated-operation contracts use isolated Perl API doubles. Clean
# install, package authority/install, product-free entry and reboot contracts
# mock all system/guest mutations and write evidence only into pytest-private
# trees. Their unit classification applies to the cleanup phase too.
# UI crash logging owns one small Python child and private tmp_path script/log.
# It disables core files before self-abort; no global crash files, bus or display.
# UI timeout/cancellation uses tmp_path pytest inputs and small private owned
# groups; recorded children/sentinels are pinned and reaped, with no shared
# process group, GUI, bus or cache. Compatible in cleanup and unit scheduling.
# Failure handoffs use shared report storage beneath the private checkout,
# followed by finite repair callbacks; descendants use recorded private pidfds.
# Pipe-holder probes own separate private sessions and bounded rescue threads;
# only their recorded pidfds are cleaned. Shell guardian probes use tmp_path
# synthetic runners, isolated subreaper subprocesses and private socket roots;
# kernel-adopted descendants are reaped before those roots are released. No
# pytest signal mask/subreaper setting, host service, GUI or shared cache changes.
# Both ui and child-preview cleanup modules remain compatible with unit work.
# Native fixture ownership checks compile only into tmp_path. Their synthetic
# child blocks/waits for SIGTERM locally; no worker signal mask is changed.

# Measured four-worker costs guide packing only; never reuse passing results.
# Recorder shards include their concurrent durable-write cost (higher than a
# single worker's elapsed time). Recalibrate from --durations=0 after growth.
# Preparation recovery additions use private journals and mocked lease/SSH
# lifecycle only. App-snapshot, graphical and retention cleanup stay compatible;
# neither host privileges nor a shared VM/display/storage root is touched.
# Retention-budget diagnostic checks use tiny private tmp_path input/log trees
# and process-local read-failure doubles. test_storage remains compatible in
# cleanup and unit inventories; no live evidence or shared owner is touched.
# Repair-budget additions run finite synthetic agents under the existing recorded
# launcher owners and private tmp_path roots. They retain compatible unit/cleanup
# scheduling, bounded waits and teardown; no real model or VM is invoked.
# Parent rejected-report recorder cases reuse function-local tmp_path evidence,
# UI/transport doubles and the existing durable-reply fault matrix. No guest,
# display, process or shared state is added; the unit/cleanup split stays valid.
# Case 49 adds only the existing private durable-recorder fixture and synthetic
# worker startup. Installed-journey cleanup remains compatible with unit/cleanup
# peers; no shared display, bus, VM, process group or allocation owner is added.
ESTIMATES = {'test_backing_verification_cleanup_safety.py': 12,
             'test_fix_tests_cleanup_safety.py': 38,
             'test_write_e2e_cleanup_safety.py': 54,
             # Overlay qualification adds only private recorder/transport doubles;
             # its cleanup rows share no live VM, display, service or storage.
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
    # Jordan FLOW16 uses the same private recorder files and VM/UI doubles as
    # Riley; its added parameters retain this unit/cleanup isolation review.
    # Match Reset/invalid plan adds only function-private recorder/transport
    # doubles and files; the same unit and cleanup partition remains compatible.
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
# Completed-result discard checks retain private pytest journals and local locks
# with mocked privileged dispatch. No live VM, workflow or shared path is touched;
# test_retention keeps its existing compatible unit and cleanup classification.
