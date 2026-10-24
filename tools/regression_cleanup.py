"""Balance cleanup work across the existing branches without splitting fixtures.

The baseline busy check uses its existing private managed lock instead of a raw
self-held flock. Snapshot enumeration uses its existing in-memory domain double.
No shared resource or new owner is added; compatible overlap is unchanged.

Shared host journal pacing retains each real sync and its error before the
next transaction step. It adds only process-local timing state, no new path,
process, service or cleanup owner; storage/recording modules remain compatible.

Fedora installed-system reboot-renewal checks retain fixture_provision's
pytest-private files and in-memory native/lease/transport doubles. No VM,
subprocess, service, display, socket, shared cache or new cleanup owner is added;
the compatible cleanup classification remains valid. UI gains no resources.

Reviewed modules use pytest-private temporary trees, process-local doubles and
explicitly owned children/descriptors. test_environment disables shared caches
and aggregate retention registration. Keep future modules exclusive until their
fixtures and external resources have been reviewed; never omit their cases.
"""
# Trusted-native baseline reconciliation uses the existing in-memory guestfs
# doubles and private records; enforcement adds closed one-shot variants only.
# No live trust DB, VM, bus, socket or process owner is added; both existing
# unit and cleanup compatible classifications remain applicable.
# Task completion no longer archives/carries turns; expiry regressions use only
# private checkpoints and missing paths. Existing owned cleanup children and
# compatible unit/cleanup classifications remain; no UI or shared resource added.
# Repair conversation doubles reuse pytest-private result files and the existing
# waited owner process; they add no shared socket, service or subprocess owner.
# write_e2e_cleanup_safety's app-server double retains the existing private
# pipes, recorded child/nested-test owners and waited cleanup. No live model,
# VM, shared cache or new lifetime is introduced; compatible in both inventories.
# Interrupt/resume and broken-input regressions reuse these recorded test owners,
# private pipes and bounded waits. Fixture teardown cancels and waits for failed
# runs too; existing compatible classifications remain appropriate.
# Clipboard baseline reconciliation and snapshot freshness checks use in-memory
# XML and existing process-local libvirt doubles. Baseline-guest and app-snapshot
# remain compatible in both inventories; no live guest or new resource is added.
# Concurrent write_e2e limit adjustments and answered-blocker completion add a
# tiny pytest-private bare Git remote and finite waited Git commands. Joined
# threads and owned agent cleanup remain
# unchanged; no network, shared cache, VM or new cleanup owner is added. Existing
# compatible unit and cleanup classifications remain appropriate.
# Atomic publication/deferred retirement extends test_retention with small private
# journals, files, local locks and synchronous interruption/metadata doubles. All
# descriptors close in their fixture; no process, VM, service, cache or shared
# path is added, so its existing compatible cleanup classification remains valid.
# Overlapping inspection probes retain only fixture-private lock descriptors;
# synchronous reentry adds no process or shared resource in either inventory.
# Aggregate dispatcher retention uses real stores below tmp_path and fixture-local
# scratch; test_test_retention_cleanup_safety remains compatible in both inventories.
# Its deferred archive verification regression reuses tiny private report-history
# files and real descriptor locks, with no new process or shared resource.
# Its retention-discard lease checks also use a pytest-private VM-pool runtime
# and synthetic UUID, with one bounded joined thread for queued acquisition;
# no live VM/coordinator or shared lock path is accessed. Dispatcher doubles
# open only their real private child retention session.
# E05 publication reuse uses private fixture journals and descriptor locks only;
# it adds no shared mutable resource or cleanup owner and remains compatible.
# No-op pruning/sync checks retain private journals and synchronous fsync
# observation; they add no child, shared path or new resource lifetime.
# Capture retirement and resumable-publication checks add only private journals,
# files and local descriptors with synchronous interruption doubles. They own no
# child, VM, display, socket, bus, service or shared cache; compatible in both inventories.
# E04 complete-closure retirement histories use tiny
# pytest-private files/archives and real local descriptor locks with synchronous
# failure/privilege doubles. They add no child, VM, service, shared cache/path,
# display, bus or socket; existing compatible cleanup and unit overlap holds.
# Batch-input transfer coverage adds paired private journals/local locks and
# synchronous verifier/interruption doubles to those same fixtures. No live VM,
# shared path or child lifetime is added; its compatible classification holds.
# Unrelated-package package_authority/package_install checks use private markers,
# recorder files, package/metadata doubles and bounded waited Perl/Python children.
# No live package manager, VM, bus, display, shared cache or new cleanup owner;
# their existing compatible unit and cleanup classifications remain appropriate.
# Installed-snapshot provisioning uses private real file/descriptor trees with
# process-local ownership mapping and transport/recorder doubles. Descriptors
# close on every path; no VM, shared path, bus or new child lifetime is acquired.
# Asset-transfer/package-install/installed-journey remain compatible in both
# inventories; renamed comparison endpoints retain the same private lifetime.
# ui_cleanup_safety's preview wait-cancellation checks use private tmp_path logs
# and process-local Popen/clock doubles, without changing real signal handlers
# or starting children. Its existing compatible unit/cleanup scheduling holds.
# Parent/Child App/kiosk fresh-install clean_install checks use private evidence and
# recorder/transfer/transport doubles with bounded waited Perl children. No VM,
# bus, display, shared path or new cleanup owner; compatible in both inventories.
# Restart-modal customer_reboot checks retain private pytest evidence, synthetic
# UI/transport trees and bounded waited Perl/isolated-Python children. No live
# guest, display, socket or new cleanup owner; compatible in unit and cleanup.
# Repair Git close-out uses tiny pytest-private checkouts/bare remotes and finite
# waited local Git children, including diagnostic overlap/restart checks.
# Per-case close-out reuses that same bounded runner double and reads only its
# private bare remote/checkpoint; resource ownership and teardown are unchanged.
# Its two-VM pipeline variant adds private FIFO/read leases and finite waited
# process doubles; VM reservations stay stubbed and both inventories remain compatible.
# It adds no external network, shared Git state, VM,
# bus/display or asynchronous owner; compatible unit/cleanup scheduling holds.
# Repair resume checks reuse fix_tests_cleanup_safety's private checkpoint trees
# and recorded, waited test/agent doubles. They create no new shared cleanup
# owner, VM, display or socket; compatible unit and cleanup scheduling holds.
# Repair workers stub VM reservations before entering their real lifecycle;
# attachment checks retain private receipts and the same waited child owners.
# Repair panel checks add private metadata and in-memory terminal/clock doubles
# around the same recorded, waited children; compatible in both inventories.
# Non-case diagnostic/repair replay uses those same private checkpoints and
# waited children, including resumed entry. It changes no resource lifetime;
# fix_tests_cleanup_safety remains compatible in both inventories.
# Repair/E2E source-restart checks reuse private launcher checkpoints, current
# results and the same identity-recorded, waited child doubles.
# They acquire no model, VM, external service, shared cache, bus/display or new
# cleanup owner; repair and E2E cleanup modules stay compatible in both inventories.
# Session-limit resume reuses its private checkpoints and finite recorded child
# doubles. Semantic journey-plan/evidence checks use private JSON/in-memory
# observations, without live VM or graphical services; both existing compatible
# cleanup classifications and reservations remain appropriate.
# Failure-context snapshots add only small files in those same private launcher
# runs. Existing test children remain recorded and waited; no live artifact
# reader, privilege, VM or additional cleanup owner is introduced. Compatible.
# Fresh child denial recorder/worker coverage uses only existing private pytest
# evidence and waited Perl doubles. No new cleanup resource or live access;
# challenges and installed-journey remain compatible in cleanup and unit scopes.
# Task 042's storage/desktop preflight checks use tiny pytest-private files and
# process-local registry/package/lease doubles. Challenges retains its existing
# waited Perl children. No live VM, build, shared cache, bus, display or new
# owner; storage, desktop-session and challenges retain compatible cleanup.
# Panel focus/Enter order checks reuse challenges' same waited Perl API double
# and private evidence; no new process, display, bus or shared cleanup resource.
# Shell approval adds sealed-input doubles and private installed-recorder files
# to challenges/installed-journey; both unit and cleanup overlap remain compatible.
# The approval observer rendezvous uses the same attempt-private input/ack files
# and synchronous transport doubles; it adds no independent cleanup lifetime.
# Inherited-descriptor command cleanup uses only process/pidfd doubles; caller
# descriptors remain caller-owned on interruption. No shared resource is added.
# Pidfd-acquisition refusal owns one finite Python Popen child and private pipe;
# only that direct unreaped child is killed/waited, with finally cleanup. No
# process scan or shared fixture is added; unit/cleanup overlap stays compatible.
# C04a removes the unconsumed private retained-manager history recovery doubles.
# Remaining controller/process ownership checks keep their existing private
# fixtures and compatible unit/cleanup classifications; no new owner is added.
# system_runner diagnostic-filter checks use bounded in-memory output, private
# pytest logs and mocked children/pidfds. Existing interruption ownership and
# compatible cleanup/unit scheduling remain; no real process or VM is started.
# Retained in-flight removal refusal dispatch in system_runner also uses only
# private pytest logs and process-local transport/command doubles. It starts no
# real subprocess and adds no shared state or independent cleanup lifetime;
# compatible classification holds in both cleanup and unit inventories.
# Finalization history dispatch/replay adds private phase/result files and VM
# doubles only to system_runner; its compatible cleanup classification holds.
# C04a2's retired MAC history and current quarantine-record bindings retain
# those same private runner files and transport doubles. No cleanup ownership,
# shared resource or process lifetime changes; both inventory classifications
# remain compatible and exact recorded-owner refusal checks remain active.

# Explicit VM-name forwarding retains private journals and process-local API
# doubles; cleanup checks add no real guest, desktop, socket or shared cache.
# App-snapshot --y/VM-picker/confirmation regressions use process-local input
# and TTY doubles with the existing private launcher fixture; appsnapshot stays
# compatible, without real VM operations, privilege, shared locks or storage.
# App-snapshot list/default selection and queue dispatch checks add only
# process-local scheduler/command doubles to that fixture. Unit and cleanup
# classifications remain compatible; no worker or guest is started.
# Online-only preparation/default-overwrite checks use the same private suite,
# launcher and dispatcher doubles, retaining compatible unit/cleanup overlap.
# Root guest probes reuse those private lease/scratch trees and mocked transport
# streams; snapshot connection checks mock SSH and the clock. Both existing
# VM-control and app-snapshot cleanup buckets remain compatible.
# Retained-app diagnostic boundaries extend the same private plan/request
# fixtures and dispatcher doubles; no real guest or new cleanup owner is added.
# Revocation diagnostic boundaries use those same private request/dispatcher
# fixtures; VM-control retains compatible unit and cleanup scheduling.
# Clipboard snapshot-policy checks use process-local configuration and XML only;
# app-snapshot's existing compatible cleanup classification remains appropriate.
# VM input-file checks use private pytest files/FIFO and in-memory descriptor,
# stdin and SSH doubles, without touching a live VM, host stdin or shared state.
# vm_control_cleanup_safety retains its existing compatible cleanup classification.
# Retained-unlock capture uses a joined local thread around mocked transport
# calls and pytest-private evidence; no live process, VM, bus or shared cache.
# Keeper scratch-lifetime coverage in vm_watch_session_cleanup_safety uses only
# private tmp_path logs and process/socket/descriptor doubles; compatible unit
# and cleanup scheduling remains valid, with no live child or shared resource.
# Maintenance denial reproduction uses the same private worker/lease/credential
# fixtures and mocked VM calls. Its failure and detach checks add no shared
# resource; those existing compatible classifications remain applicable.
# Retained-entry boundary validation adds only plan values and private request
# files to vm_control_cleanup_safety; no VM, display, bus or shared cache is used.
# Kiosk approval boundary/dispatch checks reuse those private files and in-memory
# plans. Retained-form probes add only in-memory UI/lease doubles and private
# result files, with no live VM or new cleanup owner; compatible classification holds.
# Baseline app-effects boundary/dispatch checks reuse private request/evidence
# files and mocked workers, credentials and leases; compatible scheduling holds.
# The failed-form public estimate refresh adds only a finite mocked UI leaf to
# that same probe; it adds no host resource or process lifetime.
# Native evidence capture uses in-memory journal/transport doubles and private
# result files; no real journal, guest, bus or new retention owner is used.
# Transfer-refusal prefix/refusal checks use those same private plan/request
# fixtures and retain the compatible VM-control classification.
# Remembered-return prefix checks reuse those private fixtures and dispatcher
# doubles; the existing compatible classification remains valid.
# Return-diagnostic dispatch adds no resources beyond those reviewed fixtures.
# Restored-off maintenance audits use the same private lease/disk fixtures and
# mocked VM/guest inspection, with no live VM, socket or shared state. Existing
# VM-control compatible scheduling remains appropriate in both inventories.
# Auto-baseline recovery uses those same private journals/locks and VM doubles,
# including refusal/interruption and repeat checks; compatible scheduling holds.
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
# Interrupted snapshot cleanup reuses that rig with private synthetic snapshot
# records and off-domain API doubles; no new resource or cleanup lifetime.
# Live interrupted-start recovery, explicit route selection and early identity
# persistence add only existing private rig journals and process-local libvirt,
# progress and log doubles. Graphical-smoke, VM-control and E2E-suite modules
# retain compatible cleanup scheduling: no live VM, process, socket or cache.
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
# pytest files, process-local guest/SSH/GTK doubles and bounded waited Python/Perl
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

# Fedora product-free Parent composition extends only private files and
# in-memory lease/transport/setup doubles in parent_setup_cleanup_safety.
# No new cleanup owner or shared resource; compatible cleanup/unit scheduling
# remains appropriate, and the UI inventory gains no resource.
# Dual-target fixture_execution source-edit proof retains private journal/bundle
# state and its existing bounded waited descendant; no new resource owner is
# added, so existing compatible cleanup/unit classifications remain valid.
# Idle refresh and independent-runtime uncertainty checks keep the same private
# fixture journals/lease files and synchronous doubles. The existing compatible
# fixture_execution, fixture_provision and vm_control cleanup buckets still apply.


# DESK13 shares those private doubles/evidence and waited Perl lifetimes; its
# installed attempt adds no cleanup owner beyond the product-free envelope.
# Host/VM repair-session overlap uses private workflow directories and waited
# test/agent doubles. The fixture cancels only its recorded owners; fix_tests
# remains compatible in both cleanup and unit scheduling, with no live VM/GUI.
# Checkpoint replacement/refusal checks reuse its private trees and the same
# finite, waited test/agent doubles; no shared state or new cleanup owner is added.
# Upgrade asset checks share those private file/child lifetimes. They add no
# live resource or cleanup owner; compatible unit and cleanup scheduling applies.
# Unavailable-Fedora-release checks reuse those files and process-local doubles;
# no allocation/build/service starts, so both compatible classifications hold.
# Upgrade command checks share private pytest evidence and waited Perl children.
# No added live resource or cleanup owner; unit and cleanup overlap is compatible.
# Fedora package/transfer/platform regressions retain those same private files,
# process-local command/account/OS doubles and bounded waited Perl children.
# Existing package_authority, package_upgrade, e2e_asset_transfer,
# Riley's native fixture readback uses private descriptor trees and ownership
# doubles, adding no VM, bus, shared path or lifecycle owner; compatible here
# and in the unit inventory.
# Qualification clock/secret checks retain pytest-private collector files and
# process-local clock doubles; graphical-smoke safety remains compatible in
# this prerequisite inventory and the unit inventory.
# native_fixtures and desktop_language cleanup classifications stay compatible;
# live attempts inherit the unchanged envelope's lease and collection owner.
# Chinese lifecycle shares private pytest/recorder files and waited Perl only;
# its live attempt inherits the existing envelope's lease and cleanup owner.
# The current-only history inherits that same owner; host regressions retain
# private decoder/recorder files and waited Perl, with compatible overlap.
# Chinese native authentication uses the same private host resources and the
# installed envelope's unchanged live lease, worker and collection ownership.
# Parent language inherits the unchanged installed envelope's lease/collection
# cleanup; host checks own private pytest files and waited Perl children only.
# Inherited Parent dialogs reuse those private fixtures and the unchanged live
# envelope; no new lease, storage, process or cleanup owner is added.
# Kiosk language uses those same private doubles, files and waited children;
# public observations add no live owner beyond the existing installed envelope.
# Overlay language inherits that envelope and owns only private pytest files,
# process-local account/session doubles and waited Perl children on the host.
# Selected-child restoration uses the same private tree/decoder/recorder doubles
# and bounded waited Perl children, without a new live or cleanup owner.
# Offline language composition uses private probe/isolation doubles and recorder
# fixtures; its live recovery reuses the existing lease's Internet journal.
# package_lifecycle host checks use those same private records, native-package,
# account/UI/clock doubles and bounded waited Perl workers. No package operation,
# VM, bus, display, shared cache or new owned process is used. Its cleanup and
# unit classification is compatible; live composition inherits the existing
# continuous envelope's lease, worker and collection cleanup ownership.
# Shared comparison/capture checks and renamed entry/edit probes keep the same
# private pytest records and synchronously waited Perl children; extraction adds
# no live operation, resource owner or cleanup lifetime in either inventory.
# Its hour-budget boundary checks use only process-local worker/clock doubles
# and the existing private evidence files. No real hour wait, VM, socket or new
# resource owner is added; e2e_worker and package_lifecycle stay compatible.
# Package purge guards use private pytest machine trees and process-local
# package/PAM/ownership doubles; the one shared-cleanup shell is relocated,
# bounded and waited. No host package, identity, service or shared path changes.
# Compatible in both unit and cleanup inventories.
# Log-purge identity/mount refusal cases use private pytest trees and metadata
# doubles; relocated shells wait for their two short Python callbacks. No real
# mounts, shared paths/caches or host package operation; package_purge retains
# its compatible cleanup and unit classifications.
# Desktop lock plans extend desktop_session's private recorder/checkpoint files
# only. The same pytest allocation owns cleanup; no VM/display/process owner is
# acquired. Compatible here and in the unit inventory.
# DESK07 keeps that lifetime: count/clock/transport doubles and private durable
# replies introduce no new process, display, socket or cleanup owner.
# vm_backup's combined-preparation and snapshot-removal checks keep all locks,
# disks, registries and durable journals under private pytest trees. Package and
# VM operations are doubles; no live service or additional cleanup owner exists.
# Restore-bootstrap refusals retain these private disk/metadata/journal fixtures.
# Interrupted-backup ownership checks likewise use only private journals/doubles.
# e2e_watch's borrowed-feed checks add only observer/context doubles, retaining
# its compatible classification without a collector, socket or child process.
# Failed installed-setup collection uses parent_setup's existing private attempt
# files and transport/guard doubles only. No live VM, process or cleanup owner
# is added, so its unit and cleanup classifications remain compatible.
# Overlay reminder facade/journey/registration fixtures keep API/transport/clock
# doubles and durable replies private to pytest. Their bounded Perl children
# are synchronously waited; no settings, VM, bus, display or shared cache owner
# is introduced. Compatible here and in the unit inventory.
# Saved fullscreen preference coverage keeps those same private fixtures and
# waited Perl children; it adds no resource or cleanup lifetime.
# Kiosk reminder journey/registration use the same private fixture boundaries
# and synchronously waited Perl children, without a live or shared resource.
# Natural-expiry journey/registration likewise owns only private pytest replies,
# process-local doubles and bounded waited Perl children; compatible in unit
# and cleanup, with no new protected operation or cleanup lifetime.
# VM-control's natural-expiry reproduction binding uses its existing process-local
# argument/lease doubles only; the compatible unit/cleanup ownership is unchanged.
# Fixture producer safety owns only tiny pytest-private storage/locks and small
# bounded, waited Python descendants. No shared fixture cache, VM, bus, display,
# socket or external service; compatible in cleanup and unit inventories.
# Bundle failure/publication checks use the same relocated producer roots,
# tiny inert payloads, synchronous target doubles and bounded waited Python
# lease/assembly children; no shared producer, container, VM or display.
# Execution fixture publication/handoff uses only pytest-private relocated
# journals, tiny inert bundles, local descriptors and bounded waited Python
# children. No shared build/cache, VM, display, socket or service is acquired;
# the same compatible ownership applies in the unit inventory.
# Fixture provisioning uses pytest-private descriptor trees and in-memory
# transport/native/lease doubles. No VM, service, shared cache or child process;
# compatible here and in the unit inventory.
REVIEWED = frozenset('''
fixture_provision
fixture_execution fixture_handoff
fixture_producer fixture_bundle
e2e_natural_expiry
kiosk_reminder_journey
overlay_reminder
overlay_reminder_journey
package_lifecycle
package_purge
package_upgrade
upgrade_assets
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
test_retention test_storage ui ui_artifacts ui_watch vm_backup vm_control vm_watch_session write_e2e
'''.split())

# VM backup/restore checks own pytest-private files and descriptor leases with
# process-local libvirt/launcher doubles and tiny QCOW2 images with waited
# qemu-img children; no live VM, privilege or bus. Unit/cleanup are compatible.
# Backup staging/exchange/deletion and setgid-parent checks use only recorded
# pytest-private directories and files, with process-local interruption doubles;
# red failures use launcher doubles. Both inventories remain compatible.
# Missing foreign images and interrupted network creation retain that private
# lifetime, with process-local network/UUID and host-command doubles only.
# Reconciliation and baseline-hash checks retain this lifetime, using private
# record files and injected interruptions without any live controller/guest.

# Missing-completion recovery uses private checkouts and waited owner/agent
# doubles under the existing write-e2e fixture. No live VM or shared mutable
# resource is added; cleanup and unit scheduling remain compatible.
# Diagnostic failure/blocker restarts use the same private checkpoints/question
# files and bounded waited agent doubles; no new resource or cleanup owner.
# The batch, separate-run checkpoint, cumulative-session restart, cross-session staging,
# missing-completion recovery and early worker-spawn failure cases use private bare
# Git remotes and finite waited Git commands; no network or shared state is added,
# so they stay compatible.
# Accepted-completion limit checks likewise use pytest-private bare remotes and
# waited local Git children; no shared resource or cleanup lifetime is added.
# First-session successful close-out likewise uses a pytest-private bare remote
# and waited local Git commands, retaining compatible unit/cleanup scheduling.
# Staging-failure recovery uses the same private remote allocation and waited Git
# children, preserving compatible scheduling without shared state or network.
# Prerequisite/consumer recovery adds only a tiny pytest-private bare remote and
# waited local Git children, preserving compatible unit/cleanup scheduling.
# Newly inserted queue-task recovery also uses a pytest-private bare remote and
# waited Git commands, retaining compatible unit/cleanup scheduling.
# Reopened-task recovery uses the same private remote allocation and waited local
# Git children; compatible unit/cleanup scheduling remains unchanged.
# Session-boundary handoff restart adds a tiny pytest-private bare remote and waited
# local Git children; existing owned worker cleanup is unchanged. No shared cache,
# socket, bus, display, service or live VM; bounded disk/CPU use stays compatible.
# Task-only limits and explicit scripted stops retain the same private state and
# owned, waited doubles, without new shared resources or cleanup lifetimes.
# Escalation restart adds a pytest-private bare remote for both task pushes and
# waited local Git commands; worker cleanup and compatible scheduling are unchanged.
# Previous-failure session handoff uses a tiny pytest-private bare remote and
# waited local Git children; cleanup and unit compatibility remain unchanged,
# with no network, shared state, live VM or additional asynchronous owner.
# Completion session summaries also use a tiny pytest-private bare remote and
# waited local Git children; existing cleanup ownership and compatibility hold.
# Completed-task compaction likewise uses a private remote and waited local Git
# children, with no shared paths, network, sockets, displays or live VM.
# Tiny disk/CPU demand and unchanged owned-agent cleanup preserve compatibility.
# Previous-launcher session exclusion adds a tiny pytest-private bare remote and
# waited local Git children; no shared state, network, sockets, displays or live
# VM is added, so compatible unit/cleanup scheduling and owned cleanup hold.
# Attached-limit adjustment checks likewise use a tiny pytest-private bare remote
# and waited local Git children; compatible scheduling and worker cleanup hold.
# Successful cancellation recovery adds a tiny pytest-private bare remote and
# waited local Git children; no network, shared state, sockets, displays or live
# VM is added. Bounded disk/CPU use and existing owned cleanup stay compatible.
# Escalation/restart/stall checks use the same bounded, waited agent doubles;
# there are no model calls, VM operations or additional shared resources.
# Fifth-session cap reset uses a tiny pytest-private bare remote and waited local
# Git commands; compatible overlap and existing worker cleanup remain unchanged.
# Optimization cadence/interruptions and completion commits reuse isolated Git
# checkouts with local identity and waited doubles; no host Git state or new
# cleanup resource is shared, so the existing compatible classification applies.

# Online snapshot, baseline CPU and maintenance recovery/rollback regressions
# Qualification/collector cleanup checks use pytest-private current reports,
# retention locks, synchronous VM/identity doubles and finite, waited Python
# command children with private pipes.
# Qualification storage, baseline guest and E2E execution/worker keep compatible
# unit and cleanup classifications; no live guest, helper, bus, display, socket,
# shared cache or new cleanup owner is introduced.
# Per-VM spectator publication cleanup uses private tmp_path registrations and
# mocked servers; it touches no live sockets, processes, VM leases or displays.
# retain private tmp_path journals and VM/transport doubles. No new shared
# resource or heavy fixture is introduced; their reviewed buckets still apply.
# Overlay FLOW05/07 recorder parameters use the existing private tmp_path
# evidence and process-local VM/transport doubles. They add no allocation or
# cleanup lifetime, external service, bus/display/socket or unowned child.
# The installed-journey/challenge cleanup classifications remain compatible.
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
# Unit/component/UI timeout probes share the same sequential tmp_path pytest
# inputs, pinned/waited children and private process groups. No new shared
# resource or concurrent child is added; retain this module's compatible bucket.
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
# Recorder shards use function-local disk files and checked collector sync calls;
# real disk sync/failure checks remain in e2e_evidence. Retention journal fsync
# stays real. The matrix has no shared fixture, cache or new cleanup owner and
# remains compatible in both inventories. Recalibrate from --durations=0 after growth.
# Preparation recovery additions use private journals and mocked lease/SSH
# lifecycle only. App-snapshot, graphical and retention cleanup stay compatible;
# neither host privileges nor a shared VM/display/storage root is touched.
# Retention-budget diagnostic checks use tiny private tmp_path input/log trees
# and process-local read-failure doubles. test_storage remains compatible in
# cleanup and unit inventories; no live evidence or shared owner is touched.
# Default source-keyed input checks preserve a synthetic old bundle in that
# same private pytest tree. Storage retains compatible unit/cleanup scheduling;
# no shared allocation, process, VM or additional cleanup lifetime is introduced.
# Repair-budget additions run finite synthetic agents under the existing recorded
# launcher owners and private tmp_path roots. They retain compatible unit/cleanup
# scheduling, bounded waits and teardown; no real model or VM is invoked.
# Shared response-rejection/restart cases reuse those private launcher trees,
# recorded synthetic agent/test children and bounded teardown. Cleanup finishes
# before correction; the five-session limit bounds repeated rejection. No new
# shared resource or owner; both launcher modules remain compatible here and in unit.
# Parent rejected-report recorder cases reuse function-local tmp_path evidence,
# UI/transport doubles and the existing durable-reply fault matrix. No guest,
# display, process or shared state is added; the unit/cleanup split stays valid.
# Case 49 adds only the existing private durable-recorder fixture and synthetic
# worker startup. Installed-journey cleanup remains compatible with unit/cleanup
# peers; no shared display, bus, VM, process group or allocation owner is added.
# Failure collection checks use process-local transport/lease doubles, including
# cancellation and diagnostic failure. No real journal or resource is acquired;
# installed-journey and parent-setup unit/cleanup partitions remain compatible.
# Masked graphical recording checks reuse private reply files and process-local
# UI/control doubles, including failure and cancellation. They acquire no encoder,
# guest, display, bus, shared cache or cleanup owner; both partitions stay compatible.
# Automatic fix-tests reload reuses the recorded worker via exec, private
# checkout/evidence and finite waited synthetic children. No VM, display,
# socket, external service or shared cache is added; unit/cleanup compatibility
# and the existing teardown owner remain valid. UI gains no resource owner.
ESTIMATES = {'test_backing_verification_cleanup_safety.py': 12,
             'test_fix_tests_cleanup_safety.py': 38,
             'test_write_e2e_cleanup_safety.py': 54,
             # Overlay qualification adds only private recorder/transport doubles;
             # its cleanup rows share no live VM, display, service or storage.
             # Measured 506 cases in four ~3-second workers with checked sync.
             'test_installed_journey_cleanup_safety.py': 12,
             'test_e2e_leased_recording_cleanup_safety.py': 12,
             'test_e2e_suite_cleanup_safety.py': 21,
             'test_graphical_lease.py': 8.5,
             'test_e2e_execution_cleanup_safety.py': 20,
             # Private result/log rotation keeps compatible ownership. Retain
             # the existing weight until the reduced module is measured again.
             'test_qualification_storage_cleanup_safety.py': 100,
             'test_e2e_recording_cleanup_safety.py': 10,
             # Output-ancestor/handoff checks mutate pytest-private metadata
             # only; no shared output, process or new cleanup owner is acquired.
             'test_test_storage_cleanup_safety.py': 17,
             'test_e2e_startup_cache_cleanup_safety.py': 10,
             'test_vm_control_cleanup_safety.py': 6.5,
             'test_e2e_controller_qualification_cleanup_safety.py': 2,
             'test_graphical_smoke_cleanup_safety.py': 2,
             'test_execution_probe_cleanup_safety.py': 3,
             'test_regression_cleanup_safety.py': 4,
             'test_test_retention_cleanup_safety.py': 16,
             # Headless cleanup uses private helper groups and recorded starts;
             # the unrelated sentinel survives. No compositor/shared resource.
             'test_child_preview_cleanup_safety.py': 2,
             'test_appsnapshot_cleanup_safety.py': 1,
             # Native readiness and policy receipt/retry checks in both baseline
             # modules add private service/guestfs doubles only;
             # no live daemon, VM, shared files or process/cleanup owner.
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
# Unpublished-input recovery adds only private journal/identity/refusal fixtures
# and process-local command doubles; the same compatible classification applies.
# Native-input completion-marker refusal uses the same private retained journal
# and tiny files. It adds no cleanup resource or process; compatible in both
# cleanup and unit inventories, with ordinary ownership/retention guards intact.
# Oversized execution recovery uses tiny pytest-private journals, real local
# locks and process-local VM-lease/reference doubles. No live VM, shared path
# or new subprocess is used; retention remains compatible in both inventories.
# Empty named-input recovery uses pytest-private directories, local retention
# journals and pinned read-only descriptors. No shared path, build, process or
# new cleanup owner is added; test_test_storage remains compatible in both inventories.
