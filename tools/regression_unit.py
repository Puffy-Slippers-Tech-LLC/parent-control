"""Balance reviewed unit modules without splitting their fixtures.

kiosk_rendering's lava-cache checks decode one bounded read-only shipped image
through GDK and compare bounded in-memory RGBA buffers. Native decoding uses
the launcher's private scratch/cache and process group; no window or display
is created. Generated caches use tmp_path and the scan takes a few seconds,
with tens of MiB of memory. It remains compatible unit work, with no cleanup
or UI inventory entry. VM latency cold-mode tests use only transport/reboot
doubles and private result files, retaining vm_control_cleanup_safety's
compatible unit and cleanup classifications.

Cross-distribution setup regressions extend setup_entrypoint, setup_privileges,
dev_tool_installation, graphical_host_policy and build_package with private
os-release/command fixtures, process-local platform/Polkit/package doubles and
bounded waited shell/Make children. No real package manager, VM, bus, display,
network or shared cache is added. Their compatible unit classifications remain
appropriate; cleanup and UI inventories gain no module or ownership mechanic.
DEB container regressions in build_package and setup_entrypoint and RPM route
fixtures in rpm_packaging use private metadata/workspaces and process-local
platform/Podman doubles; no real image store,
container, network or shared cache is acquired. Compatible unit scheduling and
the existing cleanup/UI inventory classifications remain unchanged.

graphical_smoke's standalone-import regression owns one bounded, waited isolated
Python child with bytecode disabled and a pytest-private working directory.
It imports controller code without VM, display, bus, network or shared mutations;
the existing compatible unit classification remains appropriate. No cleanup or
UI inventory gains a module.

Masked graphical recording checks in installed_journey_cleanup_safety use only
pytest-private reply files and process-local UI/recording-control doubles. No
encoder, VM, display, bus, shared cache or new cleanup owner is acquired; its
existing compatible unit/cleanup partition remains appropriate.

execution_plan_launcher uses tiny pytest-private Markdown/checkpoint/lock trees,
process-local Git/agent/cleanup doubles, recorded private nested-directory
identities with synchronous ownership doubles, in-memory VT panes and four finite
joined budget-update threads. Its relocated CLI check owns one bounded, waited Python
child without model inference. No VM, bus, display, network, shared mutable path
or cache, heavy build or cleanup-inventory resource is acquired; compatible unit
scheduling is appropriate. Cleanup and UI inventories gain no module.
Committed-baseline close-out checks reuse pytest-private checkouts and bare
remotes with finite, synchronously waited Git commands. They cover binary/link/
deletion fingerprints, executable-mode ownership and two-task push/advance/restart
behavior, including newer clean commits and refusal of staged/unstaged or
assume-unchanged work, without an external network, model process or shared Git mutation; compatible overlap stays
appropriate.
Installation and reliability plan adapters share those same private fixtures
for default-plan validation, owner attachment, stop and task-limit checks;
neither adapter test selects a real VM or starts an agent or Git operation.
Explicit replan checks reuse the existing pytest-private Git repositories and
local bare remote fixture, private checkpoint/lock trees and synchronous owned
cleanup. They add no external service, shared path or cleanup/UI inventory owner.
Explicit consolidation and cancelled-session reconciliation use the same tiny
private Git/checkpoint fixtures, finite waited Git reads and in-process launcher
doubles. Original-obligation propagation and refusal checks add no process,
service, VM, shared cache or cleanup owner; compatible scheduling remains valid.
Its detached adapter integration reuses the maintained private app-server double
with a tiny relocated Git checkout and the shared storage/retention libraries.
The public observer is bounded and reaped; its exact recorded worker is cancelled
through the shared owner/run contract and awaited before fixture teardown. It
adds no model inference, VM, external network, publication or new cleanup mechanic;
the same compatible unit classification applies.
Per-task Git close-out coverage now commits and pushes only between that private
checkout and a pytest-private bare remote, using bounded, waited Git children.
Pull/conflict regressions also use a tiny pytest-private peer checkout, with
bounded waited Git children and no external network. Failure/restart checks use
process-local pull/staging/commit/push doubles. No external
service, shared Git state, VM, bus, display or new cleanup owner is acquired;
the compatible unit and existing cleanup/UI classifications remain appropriate.

Fullscreen reminder qualification extends the existing overlay reminder facade,
journey and registration modules with private API/transport/recorder values and
bounded, synchronously waited Perl children. No VM, bus, display, shared cache
or new cleanup owner is added; their compatible unit/cleanup buckets still apply.

Provisioning visibility migration uses pytest-private descriptor/cache trees,
process-local systemd/version doubles and one explicitly forked, bounded,
waited child for abrupt-interruption recovery. All file/xattr mutations are
private; there is no live system bus, service, package account, VM, display or
shared cache. Its existing compatible unit bucket remains appropriate.

launcher_chat uses tiny pytest-private protocol/mailbox trees, in-memory VT
screens, a private PTY with restored terminal flags, and one bounded, waited
Codex schema-generator process (no model inference). It has no VM, network,
display, bus, shared mutable cache or cleanup-inventory entry; compatible.
Pane-wheel/scrollbar and shell-isolation coverage uses only bounded in-memory
VT rows. The shared screen double preserves its primary/alternate buffers on
resize, scrolls on bottom-edge line feeds and consumes OSC controls without
printing them, with no new resource or lifetime.
write_e2e_cleanup_safety's agent double now speaks app-server over its existing
private pipes. Its detached children, nested owner lifetimes, Git fixtures and
serial cleanup remain unchanged; existing unit/cleanup classifications apply.
Conversation race checks use deterministic in-process protocol orderings and
private mailboxes. Broken-input and interrupt cleanup checks reuse the same
recorded children and nested owners, with bounded waits and fixture teardown;
no new shared resource, service or cleanup lifetime is introduced.
Shared response-recovery checks reuse execution_plan_launcher's private
Markdown/checkpoint trees and process-local doubles, launcher_chat's in-memory
protocol, and write_e2e/fix_tests cleanup modules' finite, recorded agent/test
children. Repeated rejection and restart spend at most the existing five-session
budget per fixture. No real model, VM, display, bus, network, shared cache or
new cleanup owner is introduced; compatible unit/cleanup classifications remain.

Repair failure-context checks extend fix_tests with tiny pytest-private report,
queue and command files plus a process-local artifact-reader double. No live
Polkit, VM, bus, display, shared path/cache or new child lifetime is introduced;
its existing compatible unit classification remains appropriate.
Checkpoint replacement regressions reuse fix_tests_cleanup_safety's private
trees and finite, waited test/agent doubles. No shared checkpoint, live service
or new child lifetime is added; its compatible unit/cleanup classifications hold.
test_test_checkpoint's validation-order checks use its existing private files
only; its compatible unit classification is unchanged.

FLOW13 short-daily checks extend accessible_e2e_ui/toggle with in-memory UI
doubles, pytest-private recorder evidence and bounded waited Perl workers.
No VM, bus, display, shared path/cache or external service is added; their
existing compatible classifications and module grouping remain appropriate.

Riley native-grid checks extend e2e_native_grid_usable with private recorder
files, process-local UI/transport doubles and bounded waited Perl children.
Native fixture readback extends its existing private descriptor trees and
ownership doubles. No VM, bus, display, shared cache or new lifecycle owner;
the existing compatible unit/cleanup classifications remain applicable.
Qualification clock/secret checks use pytest-private collector files and a
process-local clock double, retaining the graphical-smoke safety module's
existing compatible classification without a shared clock or cleanup owner.

Kiosk-to-overlay FLOW12 extends e2e_overlay_valid_choices with private request
snapshots, recorder files and bounded waited Perl workers. No VM, display,
bus, shared cache or new cleanup owner; its compatible unit bucket still applies.
Composition review remains process-local source/metadata inspection.

Request-time estimate preview asset regressions use tiny pytest-private data
trees and process-local path/presenter doubles. No display, bus, subprocess or
shared mutable resource is added; the existing compatible unit bucket applies.

Case 46 extends e2e_overlay_cancel and e2e_kiosk_valid_duration with private
recorder/transport values, pytest-owned evidence and bounded waited Perl workers.
No live VM, display, bus, socket, shared cache or new cleanup owner; both retain
their existing compatible unit classification. Neither enters the cleanup inventory.

Unrelated-package qualification and shared comparisons extend package_authority/package_install cleanup
modules with process-local package/metadata doubles, private recorder/marker
files and bounded waited Perl/isolated Python children. No live package manager,
VM, bus, display, shared cache or new owner; existing compatible buckets apply.
Installed-snapshot asset provisioning uses private real descriptor/file trees
with process-local guest ownership mapping and transport/recorder doubles.
All descriptors close on success/refusal; no VM, shared path, bus or new child
lifetime is acquired. Asset-transfer/package-install/installed-journey modules
retain compatible unit/cleanup scheduling. Named comparison endpoints and
immutable nested witnesses use only private values.

Parent/Child App/kiosk fresh-install coverage retains clean_install_cleanup_safety's private
pytest evidence, process-local recorder/transfer/transport doubles and bounded
waited Perl workers. No VM, bus, display, shared path or new process lifetime;
its existing compatible unit and cleanup classifications remain appropriate.

Restart-modal coverage retains customer_reboot_cleanup_safety's private pytest
evidence, synthetic UI/transport trees and bounded waited Perl children. Its
isolated-Python payload check has no live UI, socket or product process. The
existing compatible unit and cleanup classifications remain appropriate.
Current-task exclusion recovery in write_e2e uses private checkpoint/queue trees
and process-local doubles, without launching agents or changing ownership;
its existing compatible classification remains appropriate.
The three-task batch, separate-run checkpoint, cumulative-session restart,
cross-session staging,
missing-completion recovery and early worker-spawn failure cases add tiny
pytest-private bare Git remotes and finite waited Git commands, without network
access or shared state;
its compatible unit and cleanup classifications remain appropriate.

Concurrent write_e2e limit adjustments and answered-blocker completion use a tiny
pytest-private bare Git remote and finite waited Git commands. Existing joined
threads and owned agent cleanup
remain unchanged; no network, shared cache, VM or new cleanup owner is added.
The existing compatible unit and cleanup classifications remain appropriate.

Diagnostic failure/blocker restart coverage reuses write_e2e's private checkpoints,
question files and bounded waited agent doubles. It adds no VM, network, shared
resource or cleanup owner; both existing compatible classifications still apply.

sync_whatsnew uses tiny private pytest Markdown/TOML/PO/catalogue trees, bounded waited
gettext/Make subprocesses and a private Codex double under the existing detached
worker/supervisor ownership. Children are reaped through that established owner;
no model, VM, display, shared cache or new cleanup mechanic is exercised; compatible.
Balanced translation lanes/context checks are process-local. Serial/default-parallel
transport cases each keep their own private Codex double and waited detached child;
the concurrency increase changes prompts/CLI configuration, not host test resources.

What's New uses tiny private pytest Markdown/TOML/preference/installation files, account and
transport doubles, and two finite joined threads. No live bus, display, service,
shared cache or cleanup inventory is added; whats_new is compatible. Release
preinst checks reuse the package_removal relocated, waited shell fixture on both
distributions; service_contract additions use process-local Gio doubles. Their
existing compatible classifications remain valid.
Parent release-note scheduling, acknowledgement and safe Markdown checks use
process-local callback/widget/transport doubles and strings in parent_main and
parent_client. No live GTK surface, bus, timer or subprocess is created; both
retain their compatible classifications without a cleanup inventory.
Parent startup identity, cancellation and panel-readiness checks use the same
process-local widget/worker doubles; no GTK surface, bus or child is created.
Origin-capture failure checks keep temporary files and per-file/directory fsync
inside those private machines; command doubles inject partial copies and each
waited shell cleans its own temporary file. No shared sync or new owner is added.

Case 159 rapid-edit guards in e2e_feedback_read use in-memory control doubles
and its existing waited private Perl children. No bus, display, shared path or
new cleanup owner is added; its compatible unit classification remains valid.

Kiosk notification startup in systemd_unit uses one bounded, synchronously
waited Python child with private tmp_path HOME/cache and bytecode disabled.
It loads GTK modules without creating a window, bus connection or main loop;
Apport is disabled in that child. Unit dependency checks only read checkout
files. The module retains compatible unit scheduling, with no live service,
shared cache, session mutation or additional cleanup owner.

Preview wait-cancellation checks in ui_cleanup_safety use private tmp_path logs
and process-local Popen/clock doubles. They add no process, signal handler, bus
or display; its existing compatible unit and cleanup classifications still apply.

VM artifact-selection regressions in test_test_launchers, test_regression,
test_system_guest and test_system_runner use private pytest files and process-local package/VM command
doubles only. No live VM, build, cache or new cleanup owner is introduced; their
existing compatible classifications remain valid.
Focused per-VM package preparation in test_test_launchers and test_vm_config
uses process-local package/probe doubles, private configuration and the existing
finite queue threads. No real build, guest, cache, socket or new cleanup owner
is added; test_regression_session only extends its private registry fixture.
These modules retain their compatible classifications.
Shared upgrade-pair preparation adds only in-process command/probe doubles in
test_test_launchers; both target bindings, failed preparation and explicit-input
conflicts add no real build, VM, cache, socket, process or cleanup owner. Existing
unit compatibility remains valid; cleanup and UI inventories are unchanged.
Recording-storage fixtures use synthetic labels with the same private
journals/socket leases; their existing unit and cleanup classifications apply.
Task 042's VM-specific named-input and snapshot/preflight regressions extend
test_test_storage_cleanup_safety and test_desktop_session_cleanup_safety with
tiny private files and process-local registry/package/lease doubles. Launcher
and challenges checks retain their existing doubles and waited Perl children.
No live VM, package build, shared cache, bus, display or new owner is introduced;
all four modules retain their compatible unit classifications.
Empty named-input recovery in test_test_storage_cleanup_safety uses tiny private
directories, real fixture-local retention journals and read-only descriptor
checks. It preserves existing identities and registers only new slots before
payloads. No shared cache, build, process, bus or display is added; its compatible
unit and cleanup classifications remain applicable.

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
The v1.4 package-configuration migration cases reuse the private maintainer
machine and its bounded, waited subprocess. The real state pass uses only that
machine's tiny records, lock and atomic writes under the fixture UID; no host
service, account, shared path or new cleanup lifetime is added. The existing
package_configuration compatible classification remains appropriate.
Core compatibility composition extends that machine with a relocated production
confinement helper and bounded waited Python/native-tool-double children. PAM,
policy, migration records and failure files stay under tmp_path; identity and
kernel policy tools are explicit doubles. No host PAM, MAC policy, service, bus,
VM or shared cache is touched. package_configuration remains compatible and
enters neither the cleanup nor UI inventory. prepare_vm's optional-PAM checks
use private files; system_first_configure's new witnesses use process-local
package/profile doubles. Their existing compatible classifications also apply.
Dependency-collection cases in diagnostics and service_contract mock all service
and journal commands and use the existing private event/report/rule files.
Admission native-cause and clipped-history archive cases use bounded in-memory
journal doubles and tmp_path log trees, including all 16 closed phase witnesses.
They add no child, shared cache, bus, display or cleanup owner; diagnostics keeps
its compatible unit classification and cleanup/UI inventories remain unchanged.
Pipe-limit cases launch one isolated Python child each, retain its Popen identity,
and reap it on completion, overflow or timeout; only private pipes are used,
with at most 512 KiB of generated output and no host service, bus or shared cache.
Trust
initialization retry cases in package_activation use command/clock doubles and
private manifests. No host journal/database or shared cleanup owner is added;
their existing compatible classifications remain appropriate.
Shared reboot detection/startup cases add only private tiny marker files and
process-local main-loop/transport doubles to service_contract. They touch no
host reboot state or services and retain that compatible classification.

VM selector and rolling preparation scheduling checks use private registry files,
bounded joined threads, process-local command doubles and the existing owned
session children. No live VM, setup, privilege or shared output is touched.
vm_config, prepare_baseline_tool, appsnapshot_cleanup_safety and regression_session
retain compatible unit scheduling; app-snapshot cleanup coverage stays compatible too.
Online-only snapshot/default-overwrite checks extend the same private launcher,
suite and dispatcher doubles; no live VM, privilege, process or shared state is added.
Revocation diagnostic boundaries and selector reload checks use existing private
request files and process-local UI/dispatcher doubles. VM-control, accessible UI
and installed-journey retain their current unit buckets; no real guest, process,
bus, display, shared cache or new cleanup owner is added.
Combined preparation and snapshot-free backup checks in vm_backup_cleanup_safety
use private registry/disks/journals and real advisory locks on those private files.
Build, app preparation and privilege dispatch are process-local doubles; no live
VM, host build, external service, bus/display or new cleanup owner is added.
The module retains compatible scheduling in the unit and cleanup inventories.
Restore-bootstrap refusal checks use those same private disks, metadata and
journals; they add no live service, subprocess or shared mutable resource.
Interrupted-backup ownership checks retain those same private journal fixtures.
Repeated baseline entry checks reuse one bounded, joined event thread with API
doubles; prepare_baseline keeps its existing compatible resource classification.
Borrowed watch-feed coverage in e2e_watch_cleanup_safety uses only process-local
observer doubles and context state; no collector, socket, display or subprocess
is created. Its compatible unit/cleanup classification remains unchanged.
Maintenance keeper scratch-lifetime coverage uses a private tmp_path log and
mocked sockets, process and descriptor handoff; vm_watch_session_cleanup_safety
adds no live child, VM, display or shared storage to either inventory.
Preparation-digest scheduling regressions add only private copied source/config
files to vm_config. No live VM or helper refresh runs; compatible overlap remains valid.

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

Trust-dump diagnostic regressions in system_enforcement, system_guest and
system_runner_cleanup_safety use bounded in-memory databases, pytest-private
logs and process/pidfd doubles. No real child, guest, shared path or cache is
added; existing compatible unit and cleanup classifications remain valid.
Native material-authority and preparation-child controls compile tiny private
fixtures, decode bounded in-memory records and use anonymous sockets with
atomically identified, bounded, reaped children. Descriptor closure, exact
lock/lease inodes and deadline cancellation are observed independently. Native
copy controls add private scratch inodes/xattr doubles and identity-owned
cleanup; original-slot controls use private clone projections. No shared path,
service, bus, display, network, VM or extra cleanup/UI inventory owner is added;
these modules qualify for compatible unit scheduling.
Caller result transport in kiosk_confinement uses private nonblocking pipes,
closed on success and refusal, with mocked runcon and pytest-private PAM inputs.
Bootstrap logger controls use managed short-runtime Unix sockets and close only
owned duplicates/clients; libc logging is doubled, so host logger state is untouched.
Endpoint/FD identity and symlink-trust controls add no shared service or cache.
Gate-view observer controls use pytest-private dentries, hard-linked source
stand-ins and proc-mount/root-identity doubles. They add no mounts, subprocesses,
shared paths or service access and retain compatible unit scheduling.
Inherited-descriptor command cleanup uses process/pidfd doubles and retains the
same compatible unit and cleanup classifications.
Pidfd-acquisition refusal also starts one finite direct Python child with a
private pipe, kills/reaps only its recorded Popen identity, and closes both
caller-owned descriptors in finally. No shared path or process scan is used.
Installed-journey failure collection and snapshot fixture checks use private
pytest trees and transport/lease doubles only. Cancellation opens no diagnostic
resource; existing unit/cleanup classifications and matrix partition remain valid.
Trust-refresh counter/privacy tests in system_enforcement use tiny private
synthetic proc trees and a systemctl double, with no live process or service
reads. They preserve the compatible unit classification and add no cleanup owner.
Trust-refresh sequencing tests use journal/systemctl doubles, a synthetic clock
and tiny private fixture files; they do not read host journals or launch commands.
The same compatible unit classification applies, without new shared resources.
Post-exit trust-metadata diagnostics use C API and command doubles only. They
open no host database, load no real library and spawn no process; the existing
system_enforcement compatible classification and cleanup inventory are unchanged.

Child trust upgrade/retry/boot regressions use tiny private pytest machine trees,
synthetic boot IDs, and synchronously waited relocated maintainer-script/helper
children. They read immutable unit/launcher sources and mock every live service
and database command. Existing package_activation, package_configuration,
package_removal and systemd_unit classifications remain compatible; no shared
path, cache, socket, VM, privileged write or new process lifetime is introduced.
Package trust snapshot tests use private tmp_path LMDB databases, bounded waited
Python writer children and command/clock doubles. Reader transactions overlap
only their owned fixture writers; no host database, journal, service, socket or
cache is touched. The small fixtures preserve compatible classification.
Lock-lifetime regressions acquire POSIX/OFD locks only on those private files;
descriptor-close fault injection and bounded reader children share only their
owned fixture writer. No live daemon or kernel tracing is used by these tests.

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
Notification preference/service checks use these same private records and
process-local credential/account doubles; compatible overlap remains valid.
Time grant preset boundary, approval and rollback checks use the same tiny
private records and synchronous doubles, with no new shared resources.

Guest-probe additions to VM-control, snapshot, configuration and transport tests
use existing private pytest lease/scratch trees and process-local SSH/libvirt,
stream and clock doubles. They add no live guest, socket, display, credentials,
shared state or heavy construction; their compatible unit classifications hold.
# Retained-app reproduction adds only finite plan/request fixtures and mocked
# dispatcher selections to vm_control_cleanup_safety. Native final-preflight
# retries use process-local trees, clocks and command doubles; no new resource.

Always-enabled clipboard checks use those same process-local configuration/libvirt
doubles and private fixtures. Graphical-lease, VM-config, baseline-guest and
app-snapshot unit classifications remain compatible; console reconciliation adds
only tiny in-memory XML trees, with no clipboard, live guest or new resource.

Fresh-desktop, Shell-search and GDM recipient release bindings use tiny tmp_path
metadata and a restored process-local ROOT patch; no VM, shared file, socket or
display is accessed.

Regression session tests keep both session gates and cancellation records in
private pytest trees; recorded harmless children are released and reaped by
their fixture. Cross-scope reconnect tests remain safe for compatible overlap.
Public AT-SPI and observation-cache regressions use process-local bus doubles,
mock clocks and immutable synthetic trees; they open no real sockets or displays.
Parent native-surface metadata tests use the same process-local GTK/Gio doubles
and fresh synthetic windows. Registration and coordinate-conversion guards add
no real bus, display, process or cleanup owner; compatible scheduling applies.
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
Default source-keyed input checks use tiny private pytest package/bundle trees
and read-only hashing. Storage and launcher modules retain compatible overlap;
there is no new process, VM, shared cache or cleanup owner.
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
# Overlay FLOW05/07 and immediate-exit parameters reuse those same private
# trees, recorder files and waited Perl children. No shared mutable cache,
# socket, display, service or process owner is added; compatible review holds.

# Parent rejected-report checks use existing process-local AT-SPI doubles,
# private tmp_path recorder files and bounded, waited Perl children. No live
# guest, display, bus, shared cache or new allocation lifetime; their reviewed
# app-row/composition/launcher and installed-journey buckets stay compatible.
# Native command checks use process-local session/command doubles, tiny private
# recorder files and bounded waited Perl workers; no live guest/display/cache.
# The new e2e_native_app module and existing recorder/launcher buckets overlap.
# Native startup evidence checks use bounded synthetic journal/service output
# and process-local command/AT-SPI doubles in e2e_native_app and
# e2e_native_grid_usable. No real journal, service, display or new cleanup owner;
# their compatible unit classifications remain valid.
# Native activity comparison uses frozen synthetic public values, private
# pytest reply/marker files, process-local transport doubles and waited Perl
# children. No live VM, display, socket, shared cache or new resource lifetime.
# Case 80 adds policy/balance reply checks and the two-child command composition
# in the same e2e_app_activity module with these private resources; compatible.
# FLOW09/FLOW14 Parent/child retention extends those same private recorder files,
# immutable values, transport doubles and bounded waited Perl children. Parent
# command guards reuse e2e_native_app's process-local doubles. No VM, display,
# bus, shared cache or cleanup owner is added; both remain compatible.

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
# Child preview presentation checks use private temporary modes/theme fixtures
# and waited shell children; no compositor, host settings or new cleanup owner.
# Keep test_child_preview in its existing compatible whole-module bucket.
# Headless command/dependency checks use waited shell children and local command
# doubles. Its cleanup regression uses two explicitly spawned helper groups,
# identity-checked cleanup and a private temporary directory; no display, bus,
# host setting or shared service. Both child-preview modules remain compatible.
# The diagnostic-report import-failure regression uses its existing tmp_path
# writer and restored process-local logger/command doubles; no additional shared
# service, bus, subprocess or cache. diagnostic collectors remain compatible.
# Failure-chain, rollback and async-reply privacy checks in diagnostic_privacy
# use bounded in-memory exceptions, mocked transactions/GLib callbacks and tiny
# private tmp_path log/runtime trees. Flatpak termination is entirely mocked;
# no real process, signal, bus, installed service or new cleanup owner is used.
# The module retains its reviewed compatible unit classification.
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
# TIME02's minute/final-second countdown module adds fake-clock/private-record ownership
# and bounded waited Perl children for worker order/refusal. It introduces no
# sockets, buses, displays, external service, shared cache or expensive workload;
# the existing compatible countdown unit classification remains applicable.
# PANEL01/02 adds only synthetic trees/JSON, private recorder files and the
# existing bounded waited Perl worker double in countdown/challenges modules.
# No shared paths/caches, sockets, buses, displays, external services or new
# cleanup owners; their unit and cleanup classifications remain applicable.
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

# Request release-note concurrency checks use in-memory broker/window doubles
# and mocked GLib scheduling only. Existing request_time_estimate compatible
# classification applies: no display, bus, subprocess, shared state or cleanup.


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
# DESK13 uses private API/session/transport doubles and pytest evidence, plus
# waited Perl probes. No live account, VM, bus, display or shared mutable path.
# Host/VM partition checks use process-local inventory doubles. Activity/session
# overlap and cancellation tests use private checkout locks and retained paths,
# with bounded child workers reaped by their fixtures. Queue VM operations are
# mocked; no live guest, shared cache, display or host service is introduced.
# Existing test_activity, regression_session, fix_tests and vm_config compatible
# classifications remain valid; no cleanup inventory change is needed.
# Upgrade asset checks use private tiny DEBs, waited dpkg/Perl children and
# process-local lease/transport doubles. No real VM, bus or shared mutable path.
# Missing-Fedora-predecessor checks reuse those private files and command
# doubles; refusal precedes output allocation, building or metadata commands.
# Their existing compatible unit and cleanup classifications remain valid.
# Upgrade command checks use private decoder/recorder files, process-local
# command/session doubles and waited Perl children; no shared VM, bus or GUI.
# Fedora E2E package/platform checks extend the same private pytest files and
# process-local package, account, transfer and os-release doubles. No real package
# database, build, VM, display, bus, shared cache or additional cleanup owner is
# used. Existing build_test_artifacts, e2e_inventory, e2e_provenance,
# e2e_desktop_session, e2e_asset_transfer_cleanup_safety,
# package_authority_cleanup_safety, package_upgrade_cleanup_safety,
# native_fixtures_cleanup_safety and desktop_language_cleanup_safety compatible
# unit classifications remain appropriate.
# Chinese lifecycle uses those private doubles, recorder files and waited Perl;
# no live bus, VM, GUI, shared cache or new cleanup resource.
# The current-only composition extends that module with the same private
# recorder/transport doubles and waited Perl; no resource classification change.
# Chinese native authentication shares those private doubles and waited Perl,
# with private recorder/decoder files; no additional live cleanup owner.
# Parent language checks use private public-tree/decoder/recorder doubles and
# waited Perl children; no shared VM, display, bus, cache or added live owner.
# Overlay language checks use private tree/decoder/recorder state and waited
# Perl children; no live account, VM, socket, display or shared mutable cache.
# Selected-child restoration owns private tree/decoder/recorder fixtures and
# bounded waited Perl children only; compatible in unit and cleanup inventories.
# Offline language composition uses private isolation/probe doubles and retained
# recorder fixtures with waited Perl children; no host network or VM mutations.
# Continuous package-lifecycle checks own private pytest records, process-local
# native package/account/UI/clock doubles and bounded waited Perl workers.
# Permission-denial checks never execute a host fixture; ordered reboot checks
# use VM doubles only. package_lifecycle_cleanup_safety is compatible in unit
# and cleanup scheduling, with no real package database, VM, bus, display,
# shared cache, ownership mutation or extra process lifetime.
# Extracted lifecycle checks and renamed worker scopes retain that classification:
# immutable capture/replay and recorder-durability tests use the same private
# trees/doubles; scoped Perl input probes are bounded and synchronously reaped.
# Hour-budget worker admission/expiry checks retain private evidence files and
# process-local clocks/worker doubles, without real waits or additional owners;
# e2e_worker_cleanup_safety remains compatible in unit and cleanup inventories.
# Maintenance denial reproduction extends the existing worker, graphical lease,
# credential and VM-control tests with mocked guests, private evidence and the
# same owned sockets/children; no live VM, shared bus or resource owner is added.
# Failed installed-setup collection retains parent_setup_cleanup_safety's
# private attempt trees and transport/guard doubles. Copy failures and cancelled
# setup add no live guest, process or cleanup owner; both inventories stay compatible.
# Transfer-refusal maintenance boundary checks reuse private plan/request values
# in vm_control_cleanup_safety; no new host resource or process lifetime.
# Retained failed-form estimate refresh checks use private accessible trees and
# public-setter doubles in e2e_kiosk_valid_duration; no live bus or display.
# Native diagnostic capture in vm_control_cleanup_safety uses private journal
# records and transport/lease doubles, with no live journal or new shared owner.
# Retained-unlock capture checks use private files, mocked SSH/bus/lease calls
# and one joined process-local thread; no live child, VM, display or shared cache.
# Remembered-return diagnostic prefix checks use the same private requests and
# dispatcher doubles; no live VM, bus, display, shared cache or new owner.
# Short return diagnostic worker checks in e2e_overlay_valid_choices use the
# existing bounded Perl children and private plan/request fixtures; compatible.
# Prompt snapshot facts in accessible_e2e_ui use process-local tree doubles and
# the existing bounded isolated payload children; no shared bus/display/cache.
# Finite application-state scope checks in public_atspi reuse mocked connections,
# local GVariants and private GLib contexts, without a live bus, display, process
# or shared cache. The existing compatible unit classification remains valid.
# Distribution admission boundaries create at most 257 tiny private pytest
# files and use an injected small byte ceiling. e2e_needle_inputs adds no shared
# cache, process, socket or live VM; its existing compatible classification holds.
# Shared removal parity and actual RPM erase callbacks use the existing private
# pytest machine trees, relocated system paths and bounded, waited shell children.
# Their service/account/PAM commands remain doubles, including abort-remove's
# separate shell. No host package database, VM, bus, display, shared state or new
# build fixture is touched; package_removal and rpm_packaging remain compatible.
# Installed removal assertions use private tmp_path filesystem trees, native
# account/session/command doubles and bounded synthetic responses. No live VM,
# account, service, PAM, package database, socket or display is changed; the
# system_removal module is compatible with other private unit work. Confinement
# removal residue checks likewise use private files and policy-list doubles;
# they never load or unload host MAC policy.
# Active-kiosk native-removal refusal coverage uses private generation/PAM files,
# invocation/UID/pidfd/census doubles and bounded command responses. It creates
# no process, session, service or package transaction on the development host.
# In-flight refusal's shared PAM/authselect snapshots use private files and
# synthetic ownership; loaded-policy and holder-lifetime checks use process-local
# preparation/SELinux/pidfd doubles only, with no real subprocess or policy read.
# system_runner's retained refusal dispatch likewise uses private logs and
# process-local transport doubles; its unit/cleanup classifications stay compatible.
# Sibling-isolation dispatch uses the same private JSON/VM doubles. Its host
# fixture checks use pytest-private inert files, process-local ownership/census
# doubles and immediately closed read-only descriptors; no host UID, process,
# mount, bus, socket, display, shared cache or external service is changed.
# Existing compatible classifications and small bounded resource demand hold.
# Focused rollback histories retain private files and mocked VM/native commands.
# Bind-mount ownership and transaction-watcher tests use synthetic mount rows
# and joined local threads with command doubles, never host mounts or packages;
# system_removal, system_runner and system_snapshots stay compatible. System
# watch progress regressions use in-memory packets and a mocked publication;
# they add no shared socket, display, VM or heartbeat process ownership.
# RPM post-erase/reinstall/purge coverage adds private files and synchronous
# command/thread doubles, including observer joins and interrupted reads. Target
# selection/cleanup uses mocked VM leases; these same classifications still apply.
# Interrupted-finalization cases and durable PAM workers use private files and
# process-local account/PAM/VM doubles. system_removal_faults also owns finite,
# waited harmless shell children; no host mount, policy, package, bus, socket,
# display, external service or shared cache is changed. Both new modules are
# compatible unit work, with small bounded CPU, memory and disk use.
# Read-only bind/remount recovery extends those same synthetic mount rows and
# private directory fixtures; it adds no live mount or shared cleanup owner.
# Ownership-conflict restoration checks use only private tmp_path inodes,
# process-local UID/mount doubles and no subprocess. They add no shared path,
# VM, mount, service, bus, socket, display, external service or cache ownership;
# system_removal_ownership is compatible bounded unit work. Identity/root
# conflict tests likewise use private roots, process-local UID and mount rows,
# and command doubles; no host mounts, accounts, services or shared caches.
# system_removal_identity and its stage-aware recovery checks are compatible.
# Mapped-module identity regressions use private map_files-shaped symlinks and
# stat/permission doubles; locked SELinux relabel tests use command doubles and
# existing private advisory locks, with no host /proc scan or MAC mutation.
# One real Linux layout check owns a finite direct Python child and nonleader
# thread mapping innocuous private data, reads only that recorded child's proc
# paths, and kills/waits that child and closes its private pipe in finally.
# A missing map_files capability must fail closed at that exact real alias;
# guest-root live checks own the positive target-stat proof in that case.
# Public purge safety checks use private pytest machine/source files and native
# package/PAM/ownership doubles; their relocated shared-cleanup shell is bounded
# and waited. No live package, account, service, bus, display or shared path is
# changed. package_purge_cleanup_safety is compatible in unit and cleanup scopes.
# Log-purge replacement/mount checks add only private tmp_path entries and
# process-local metadata doubles. Package-machine shells run two short, waited
# Python callbacks on that same tree, with fixture UID ownership and no shared
# cache, mount mutation, service or live package operation. Existing purge,
# removal and RPM packaging compatible classifications remain appropriate.
# Parent Hebrew observations add private text/focus doubles, recorder files and
# synchronously waited bounded Perl children to parent_language_cleanup_safety.
# No VM, shared bus/path or new resource owner; its compatible classification stays.
# Parent inherited-dialog checks extend the same private node/decoder/recorder
# fixtures and waited Perl children; no new resource or lifetime is introduced.
# Enabled Hebrew policy decoding/comparison extends those private fixtures and
# waited worker children; no shared path, VM, bus or additional resource owner.
# Parent presentation uses private recorder/decoder files and bounded waited
# Perl probes; no live VM, bus, display, shared cache or new cleanup owner.
# Resume regressions use small private pytest checkpoint files and one waited
# synthetic pytest child. Repair-loop checks reuse the recorded process doubles;
# they add no shared owner, VM, display, socket or expensive fixture. Both unit
# and cleanup classifications of fix_tests_cleanup_safety remain compatible.
# Repair panel checks reuse those recorded, waited process doubles and small
# private metadata files; terminal/clock/parser doubles stay process-local.
# No new shared resource or cleanup lifetime; existing overlap remains valid.
# Resume counter/selector checks use the same private reports, checkpoint trees,
# waited pytest children and scheduler doubles; compatible isolation is unchanged.
# Oversized-ID recovery uses private checkpoint JSON and bounded synthetic pytest
# children; it adds no shared owner or resource and stays compatible. Progress
# payload checks retain their existing resources, with short parameter IDs only.
# Report I/O checks use one private synthetic inventory and private JSON files;
# watch reader and session-frame checks use private files and synchronous doubles.
# They add no shared owner, process, display, socket or cleanup resource and keep
# regression, regression_session and watch_output compatible with host overlap.
# Publication/barrier failure and rejected-metadata replay checks use private
# files, process-local fsync doubles and in-memory displays; no live owner is
# cancelled and these checks retain the same compatible resource classification.
# Application UI projection tests use in-memory clients and tiny immutable
# inventories only. No real bus, display, process, storage or cleanup owner.
# Deferred-label and document-availability checks retain that compatible scope.
# Character/format boundary checks also use only those in-memory clients.
# Retired-state absence checks use in-memory nodes/errors only; compatible
# accessible_observation scheduling retains its existing resource ownership.
# Category diagnostic replay tests reuse fix_tests_cleanup_safety's private
# checkpoint trees and recorded, waited children. Both unit and cleanup
# compatibility remain unchanged; no shared owner or new resource is introduced.
# Session-limit resume adds only those same finite, waited process doubles and
# private checkpoints. UI/E2E product-route parity uses in-memory API clients;
# semantic evidence checks use private JSON and recorder doubles. No graphics,
# VM, network, shared file or new owner; existing compatible classifications apply.
# Launcher dispatch parameters use process-local synthetic package identities,
# avoiding repeated Make/source scans; real identity/refusal checks stay in
# test_storage_cleanup_safety. Installed-journey parameters retain function-local
# disk files and the real recorder, with collector-only checked sync calls.
# e2e_evidence keeps real file/directory sync and failure-before-registration
# coverage. Retention synchronization is untouched; all three remain compatible.
# Lock-surface additions reuse e2e_desktop_session's in-memory provider/session
# doubles and waited Perl probes, plus desktop_session_cleanup_safety's private
# pytest files. They introduce no display, bus, VM, socket or shared cache owner.
# DESK07 recipient proofs retain those doubles, waited Perl probes and private
# recorder files; no live session, display, socket or shared resource is added.
# kiosk_confinement uses tiny private policy/PAM/ELF-shaped trees and process-local
# identity, command and account doubles. Its bounded waited AppArmor compiler
# uses -Q -T, neither loads kernel policy nor writes shared caches. No host PAM,
# service, VM, session bus, display or cleanup owner; compatible unit scheduling.
# Native launcher checks compile nine tiny private binaries and redirect their
# final exec to a private observer, with bounded waited children and no daemon.
# The bubblewrap observer inherits one caller-owned private file descriptor;
# source/destination inventory checks use only private ELF-shaped files.
# Bubblewrap role-proof checks use credential, namespace, label and exec doubles;
# no host UID, namespace, MAC policy, VM or extra cleanup owner is changed.
# Manager/service denial proofs use private ELF/proc/audit records and command
# doubles; they add no live unit, namespace, audit setting or shared resource.
# Preserved password-helper metadata/census checks use private ELF/proc trees
# and xattr/pidfd doubles. One additional bounded native identity fixture uses
# private compilation/output; it changes no mounts, labels, PAM or host policy.
# Staging-detach checks compile one small private native binding fixture and
# synchronously wait for its bounded children. Mount/namespace calls are doubles;
# manifests and outputs stay in pytest-private trees. Existing compatible unit
# admission still applies; there is no cleanup/UI inventory or shared resource.
# Post-layout publication and descriptor-drift cases reuse those two fixtures.
# Native descriptor walks operate on pytest-private files; root ownership,
# mount identities, namespaces, tmpfs and SELinux labels are process-local
# doubles. Real unlink/rename/type/mode changes affect only fixture children.
# Every compiler/probe child has an explicit deadline and is synchronously
# reaped; invocation trees and manifests have no shared cache or persistent
# owner. The module remains compatible in the unit inventory; cleanup/UI
# inventories and live host resources are unchanged.
# Generic sibling cases add private FIFOs/symlinks and restore deliberately
# read-only fixture modes on every outcome. They open no FIFO, mount or bus;
# ownership, metadata-race and directory observations remain process-local.
# Classification/required-closure cases reuse those private trees and actual
# manager/gate publication, with deterministic lstat/readlink/enumeration faults.
# Selected-alias metadata and disappearance/reappearance affect only fixture
# children; broken diagnostic pipes are private and closed on every outcome.
# Healthy directory-alias publication also reuses the existing bounded native
# consumer (5-second probe, 30-second module compiler deadline), synchronously
# reaped with descriptor-balance assertions. No ambient special file is opened,
# and no new socket, cache, external service, cleanup/UI inventory entry or
# shared owner is added.
# Native cause diagnostics reuse the bounded binding fixture and its private
# manifests, descriptor/mount-identity witnesses and process-local syslog/kernel
# doubles. Logger failure and errno bounds add no persistent output or live
# namespace, mount, PAM, bus, socket or cache owner. Compiler/probe deadlines and
# synchronous child reaping remain unchanged; unit overlap stays compatible,
# with no cleanup or UI inventory changes.
# Preparation diagnostic shutdown checks own private broken pipes and bounded,
# waited Python children with bytecode writes disabled. Preparation is a local
# double; no host account, PAM, mount, policy or shared cache is accessed.
# Payload-refusal format checks reuse the existing private files and process-local
# command doubles, with no additional subprocess or resource ownership.
# Lua cwd-canary checks use the installed native Lua library in two bounded,
# waited Python children with a private cwd and module. The control permits its
# private module; the captured kiosk environment must reject it. No PipeWire,
# WirePlumber session, host Lua configuration, bus or shared cache is touched.
# Reproducibility checks run two bounded private policy generators with distinct
# hash seeds. The pidfd-failure check owns, kills and reaps one fork child and
# closes its private pipe; it never discovers or signals another process.
# Census lifecycle checks use private proc-shaped files and process-local pidfd,
# identity and clock-free snapshots; they inspect no live process or VM state.
# PAM lifecycle observers own bounded fork children, pipes and pidfds; their
# process-local subreaper setting is restored after every outcome. Only those
# recorded children are signalled and reaped; real PAM callbacks use doubles,
# with no installed policy, service or account mutation. Compatible scheduling.
# Snap activation precedence and the ordinary-user control use one private
# dbus-daemon per variant, a short_runtime socket, private service/config/marker
# files and bounded waited dbus-send clients. Each direct daemon is terminated
# and reaped in finally. No host bus, systemd manager or shared cache is touched;
# compatible unit scheduling.
# kiosk_login compiles one private PAM module and runs bounded, reaped helper
# children with pytest-owned configuration/lock/status files. Its abort check
# signals and joins only its own multiprocessing worker; the bounded helper
# exits itself and its inherited lock is observed released before fixture reuse.
# libpam loads only that private stack; AccountsService, NSS and syslog use
# process-local doubles. The interpreter-isolation probe executes the fixed
# helper as an ordinary account with a private cwd/PYTHONPATH and waited child.
# Manager credential checks reuse that compiled module and private confdir,
# loading only inert vendor permit/deny callbacks to verify kiosk exclusion and
# unchanged ordinary fallback. No host PAM files or live credentials are changed.
# Its native-boundary callback observer compiles one further small private
# executable (30-second deadline) and waits for each 5-second probe. Lock, PAM,
# namespace, mount, environment, MAC and logging calls are process-local doubles;
# the real production callback supplies ordering and return values. No new live
# resource or cleanup/UI classification is needed; compatible overlap remains.
# Wellbeing identity/environment cases compile a tiny private launcher with
# linker-wrapped NSS/exec observers and run bounded waited children. They read
# no live account or settings backend and preserve compatible unit scheduling.
# No real session, system bus, display, root lock, shared cache or service mutates.
# Admission/removal regressions use real advisory locks only on pytest-private
# files. Native PAM leases cover root-executor/session teardown intervals and
# the existing owned worker-abort case observes the inherited helper lease.
# Retained-handle reuse additionally mutates only that module's private lock
# inode/link/mode or removal marker and restores the exact owned inode before
# fixture reuse. Final preparation-lock checks reuse the native callback double;
# no new process, shared resource or cleanup/UI classification is introduced.
# Lifecycle interruption/recovery uses private PAM/record/marker files and
# fixed policy-command doubles; no host PAM, kernel policy or account changes.
# Installed admission's worker/status and routing-failure checks use process-local
# libpam, account and command doubles; no real PAM transaction or child starts.
# It is compatible with other unit modules; its module fixture stays together.
# e2e_kiosk_feedback_confinement uses pytest-private root-shaped record/mask
# files, process-local systemctl/public UI/transport doubles and no real service,
# VM, bus, socket, display or shared cache. Two bounded, waited Perl worker
# probes use process-local testapi doubles; small file I/O and CPU only;
# compatible, with no cleanup prerequisite inventory or additional owner.
# Disabled sound's scanner observer and its fork/pidfd fixtures are removed.
# Feedback preparation/order checks use the existing in-memory UI/transport
# doubles. Compatible unit scheduling still applies; cleanup/UI inventories
# acquire no module, process, shared path or service.
# e2e_kiosk_notification_wellbeing uses process-local public UI, user-manager,
# account/environment and transport doubles with tiny pytest-private files.
# Its two waited Perl workers have private testapi state. No real settings,
# bus, display, systemd unit, VM, shared cache or cleanup prerequisite is used;
# compatible, with fixtures kept in one module.
# system_kiosk_accounts uses tiny pytest-private cache/witness/mask-shaped files,
# account/service command doubles and synthetic metadata. It never reads a live
# AccountsService record or changes a host account, daemon, bus or runtime mask;
# compatible with other private unit work, with no owned child or shared cache.
# Both ordinary-role witnesses use those same private files and account/command
# doubles; expanded role/refusal/metadata cases add no resource or cleanup owner.
# system_kiosk_platform uses private proc/audit-shaped files and process-local
# command/account doubles. Fixture identity/cleanup checks touch only pytest
# directories; no live manager, module loader, bus, VM, mount or child lifetime.
# system_kiosk_scope uses pytest-private PAM/proc-shaped files, symlinks and
# process-local account/systemd doubles. Its lifecycle refusal checks start no
# real manager or child and use no shared cache, bus, display or host policy;
# small CPU/I/O work is compatible, with no cleanup prerequisite inventory.
# Retained-manager lifetime controls add append-only pytest-private records and
# process-local logind/systemd, transport and public-observer doubles. Composed
# two-entry/recovery checks run no live manager, VM, bus, display or subprocess;
# the existing scope/kiosk-entry/runner cleanup modules remain compatible.
# system_kiosk_ambient_history, system_kiosk_required_history and
# system_retained_history use only tiny pytest-private file/checkpoint trees,
# in-memory account/PAM/journal/manager/transport/public-entry doubles and
# synchronous fsyncs. No live manager, VM, mount, package, bus, display, network,
# child process or shared cache is acquired. Compatible unit overlap applies;
# the cleanup and UI inventories acquire no module or resource owner.
# Overlay reminder facade/journey/registration safety uses process-local API,
# transport and clock doubles, tiny pytest-private replies and bounded waited
# Perl workers. No live settings, bus, display, VM, shared cache or new cleanup
# owner is used; all three modules permit compatible unit/cleanup scheduling.
# Kiosk reminder journey/registration likewise use process-local immutable-value,
# recorder and command doubles, pytest-private replies and bounded waited Perl.
# They add no live settings, shared cache, bus, display, VM or cleanup ownership.
# Natural-expiry journey/registration safety uses private pytest reply files,
# process-local recorder/clock/transport doubles and bounded waited Perl workers.
# No live session, shared cache, bus, display, VM or cleanup owner is acquired;
# the same module is compatible in the unit and cleanup inventories.
# Natural-expiry observer/facade tests likewise keep clocks, public-node/transport
# doubles and small records process-local, without sockets, services or children.
# VM-control's fixed reproduction binding adds only mocks to its reviewed private
# fixture resources; no live maintenance lease or guest is acquired by host tests.
# First-configuration controller checks use tiny pytest-private wrapper/witness
# files, bounded waited harmless shell children and process-local PAM/command
# doubles. Their conversation owns only bounded libc response allocations.
# No live package manager, mount, account, VM, bus, display, service or shared
# cache is touched; system_first_configure is compatible unit work. Existing
# system_kiosk_admission classification remains applicable with no new owner.
# Recording units use pytest-private identity journals and short owned AF_UNIX
# sockets, in-process timeline/control doubles, and one bounded single-thread
# encoder child. Complete-playback checks run tiny fixture clips through serial
# bounded FFmpeg/FFprobe children with null decoded output. They own no VM,
# desktop, shared cache or external service.
# The recording storage safety module is reviewed in the cleanup inventory too.
# PAM environment history regressions use pytest-private paths and in-process
# command/account doubles. They acquire no VM, host PAM, bus or process owner.
# Earlier-package history checks use tiny pytest-private checkpoints and
# in-process account/clock/transport doubles. Existing runner staging reads
# immutable source files; no host bus, service, VM, cache or child is added.
# Trusted fixture qualification uses only private pytest files and process-local
# native/authentication doubles. Baseline trust reconciliation tests remain
# in-memory guestfs work, with no live trust DB, VM, bus, socket or new owner.
# Both compatible unit/cleanup classifications for baseline/enforcement hold.
# Native history route/controller/guest checks use pytest-private checkpoints,
# small local descriptors and process-local package, UI, transport and process
# doubles. Descriptors close on refusal; no native package, VM, service, bus,
# display, network or shared cache is acquired. Existing kiosk-entry checks
# remain compatible. These three new modules add no cleanup or UI inventory.
# Native-history receipt-size coverage owns one bounded 9-MiB pytest-private
# file and in-process pipe/clock doubles; the compatible classification holds.
# The native setup-barrier checks stat tiny unopened pytest-private FIFOs;
# they acquire no worker or live pipe reader and retain compatible isolation.
# Immutable-view primitives use pytest-private copy/receipt trees and owned FDs.
# Native probes compile in private scratch and run as bounded, waited children
# in their own user/mount namespaces with private propagation. Native clone
# workers use anonymous descriptor sockets and are bounded and reaped. They acquire no
# host mount, service, bus, display, VM, network or shared cache; compatible unit
# overlap is safe. Material selection adds only tiny pytest-private file/FD
# trees and process-local metadata/label doubles; it uses no process, shared
# cache, socket, bus, display or service. Its legacy-manager control briefly pins
# its own test process with a closed pidfd; it never signals or spawns a manager.
# None participates in cleanup/UI inventories.
# Retained projection uses only pytest-private files, symlinks and borrowed
# descriptors. Its 512-source control observes constant descriptor use without
# changing process limits. It adds no subprocess, live mount/bus, shared cache
# or cleanup/UI owner; the existing compatible unit resource class applies.
# Manager admission owns private compiled fixtures, typed bus/proc doubles and
# bounded waited probes. Its reexec witness owns one pipe-barrier child and
# pidfd, and signals only that recorded child. Host proofs use private descriptor
# trees and bounded compiled probes with preloaded read-only hashing libraries.
# Neither module opens a live bus, service, display, network or shared cache, or
# changes a host namespace/mount. No cleanup/UI inventory owner is introduced.
# Initial realization planning uses pytest-private files, descriptor copies and
# process-local metadata doubles under the existing runtime-copy cleanup owner.
# Receipt checks compile bounded private native probes and hash finite in-memory
# records. Preparation channels use private anonymous descriptor sockets and
# owned CLOEXEC descriptors; any native probes are bounded, waited children.
# No shared path, cache, bus, display, service, VM or new cleanup/UI owner is
# acquired. These three modules permit compatible unit overlap. Pin transaction
# expiry controls use a local clock double with the existing private mounts and
# unchanged owned-child/namespace cleanup; policy controls only inspect strings.
# The preparation service/entry own private descriptor trees and anonymous
# records. The service's alarm and import aliases are process-local and restored;
# entry controls launch no child. No host lock, bus, mount or service is touched,
# and neither module belongs to cleanup/UI inventories. Compatible overlap uses
# the same bounded disk/CPU class as the initial-copy and channel fixtures.
# Native plan/policy/publication controls use pytest-private real inode trees,
# bounded waited compilers/probes and process-local enforcement/clock/syscall
# doubles. Publication probes enter their own user namespace without mounts.
# Native realization additionally owns private user/mount namespaces, nested
# tmpfs mounts and anonymous descriptors, all detached/closed before probe exit.
# They add no host policy, live bus/service/display, VM, shared cache or new
# cleanup/UI owner. Their bounded CPU/disk use permits compatible unit overlap.
# Fresh startup uses pytest-private source/copy trees, bounded waited native
# compilers and one identity-owned preparation child in private user/mount
# namespaces. Its recursive mounts and descriptors die with each waited probe;
# policy/PAM observations are local doubles. It opens no live bus, display,
# service, VM or shared cache and adds no cleanup/UI inventory owner.
# Retained-record checks use private source/copy trees, sealed records and a
# bounded waited native probe in its own user namespace. Retained startup adds
# a waited private manager and gate with private mount namespaces and barrier
# pipes. The system bus, PAM identity and enforcing MAC are fixture boundaries;
# no live host service, UI, VM, shared cache or cleanup inventory is used.
# Composed failure witnesses add only independently opened fixture lock files,
# identity-recorded publication faults and one pipe-held, joined manager thread.
# All lock contention, record replacements and recursive-clone faults remain
# inside those private trees/namespaces; no host policy or shared lock is used.
# Manager lifetime composition adds original proc/task snapshots, per-field
# credential/namespace doubles and removal of that same joined private thread.
# Reexec/exit use the existing owned manager and barriers, including after setup
# closure; no additional process, shared service/cache or cleanup/UI owner is
# acquired. The compatible unit classification and bounded resource class hold.
# Writer/source composition adds phase-local probes of independently reopened
# private lock files, original-root/alias proof descriptors and finite host-file
# mutations in those same trees. Sequential retained admission adds one waited
# child with its own mount namespace; the parent alone owns and retires the
# original manager. No shared lock, service, cache, UI or cleanup owner is added;
# the existing bounded probe/compile resource class and compatible overlap hold.
# Receipt/publication composition keeps mutations and independent provenance
# snapshots in these same private trees. Failure cuts use process-local syscall
# doubles; real recursive mounts, descriptor censuses and child-reap checks use
# the existing bounded native probe owner. Failed/interrupted future exec uses
# that same parent-death-protected manager child and pidfd-bounded reap, not a new
# process owner. No shared path/cache/service or new cleanup/UI inventory owner
# is introduced; compatible unit overlap still holds.
# Measurement-refusal controls reuse these same private trees, anonymous
# channels, process-local alarms and bounded/reaped native children. No shared
# service, cache, display, persistent fixture or cleanup owner is added; the
# existing probe/compile admission and compatible classifications remain valid.
REVIEWED = frozenset("""
kiosk_pin_native kiosk_pin_storage kiosk_material_selection kiosk_required_material kiosk_retained_projection
kiosk_manager_admission kiosk_host_proof
kiosk_initial_realization kiosk_view_receipt kiosk_preparation_channel
kiosk_material_authority kiosk_preparation_child
kiosk_preparation_service kiosk_preparation_entry
kiosk_preparation_plan kiosk_native_realization kiosk_policy_authority kiosk_view_publication
kiosk_fresh_startup kiosk_retained_record kiosk_retained_startup
native_history_routes native_update_runner system_native_update
native_transaction_inputs native_transaction_preflight native_transaction_routes native_transaction_staging
system_trusted_fixtures
system_previous_upgrade
system_pam_variants
vm_recording
watch_recording
recording_storage_cleanup_safety
system_first_configure
e2e_natural_expiry
e2e_natural_expiry_cleanup_safety
kiosk_reminder_journey_cleanup_safety
kiosk_reminder_registration_cleanup_safety
overlay_reminder_cleanup_safety
overlay_reminder_journey_cleanup_safety
overlay_reminder_registration_cleanup_safety
system_kiosk_accounts
system_kiosk_platform
e2e_kiosk_notification_wellbeing
application_ui_support
test_checkpoint
parent_presentation_cleanup_safety
package_lifecycle_cleanup_safety
package_purge_cleanup_safety
system_removal
system_removal_faults
system_removal_identity
system_removal_ownership
system_kiosk_admission
parent_language_cleanup_safety
language_persistence_cleanup_safety
kiosk_language_cleanup_safety
kiosk_language_restoration_cleanup_safety
overlay_language_cleanup_safety
chinese_native_auth_cleanup_safety
chinese_kiosk_lifecycle_cleanup_safety
package_upgrade_cleanup_safety
upgrade_assets_cleanup_safety
desktop_language_cleanup_safety
localization
e2e_overlay_prompt
e2e_shell_panel
e2e_overlay_valid_choices
e2e_overlay_license
e2e_overlay_cancel
vm_internet_cleanup_safety baseline_fixtures_cleanup_safety
about_dialog accessible_e2e_ui accessible_observation adapters app_policy app_termination appsnapshot_cleanup_safety apt_removal_notice chinese_language_assets_cleanup_safety evidence_bundle
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
e2e_kiosk_eligible_choices e2e_kiosk_valid_duration e2e_kiosk_entry e2e_kiosk_feedback_confinement e2e_kiosk_no_approver e2e_kiosk_no_child e2e_leased_recording_cleanup_safety
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
feedback_transport fedora_pam fedora_execution_policy fix_tests fix_tests_cleanup_safety fixture_cleanup_safety fixture_gui_adapter floating_islands
graphical_attachment_cleanup_safety graphical_backend graphical_expiry graphical_host_policy
graphical_lease graphical_serial_cleanup_safety graphical_smoke graphical_smoke_cleanup_safety
graphical_transport_cleanup_safety graphical_worker graphical_worker_cleanup_safety guest_inputs
installed_journey_cleanup_safety installer integration_harness kiosk_confinement kiosk_login kiosk_model kiosk_rendering
execution_plan_launcher launcher_chat launcher_render licensing lightning logs mutter_input package_activation package_authority_cleanup_safety package_configuration package_inputs
package_content package_install_cleanup_safety
package_os_gate package_payload package_removal package_transaction_notice pam_runtime_cap
parent_about_cleanup_safety parent_about_worker parent_access_worker parent_client
parent_discovery_worker parent_grid_pixels parent_main parent_native_surface parent_needles
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
system_info system_kiosk_scope system_kiosk_ambient_history system_kiosk_required_history
system_retained_history system_probe_decision system_probe_sandbox_cleanup_safety system_qualification
system_remote_accounts system_runner system_runner_cleanup_safety system_snapshots systemd_unit
terminal_cleanup_safety test_account_password test_activity test_artifacts test_launchers
test_retention_cleanup_safety test_runner_policy test_storage_cleanup_safety thunder ui_artifacts_cleanup_safety
ui_cleanup_safety ui_watch ui_watch_cleanup_safety uninstall unit_test_launcher usage_query_retry verify_test_traceability
vm_backup_cleanup_safety vm_config vm_control_cleanup_safety vm_transport vm_watch_session_cleanup_safety watch_activity watch_output
write_e2e write_e2e_cleanup_safety whats_new sync_whatsnew
""".split())

# VM archive/restore safety uses only pytest-private sparse files, locks and
# libvirt/launcher doubles, plus tiny QCOW2 images and finite, waited qemu-img
# children. No live VM, privilege or shared storage; compatible overlap is
# reviewed in unit and cleanup inventories.
# Atomic backup directory exchanges, setgid inheritance and interrupted
# identity-bound retirement use only that module's pytest-private filesystem;
# red failure reporting uses process-local launcher doubles. Compatible overlap
# remains valid; no shared host paths, VM operations or extra subprocesses.
# Watch registry refresh uses the existing bounded discovery thread with private
# JSON and finite Git doubles; per-VM activity rebinding uses publication doubles.
# Neither adds a live host/VM resource or changes compatible unit scheduling.
# Missing foreign disk chains and network interruption/ownership checks add
# only private fixture files and process-local libvirt doubles; no new owner,
# service, cache or resource demand changes this compatible classification.
# Bookkeeping retirement, damaged journals and logical baseline bindings reuse
# private files and those doubles; interruption has no real controller/guest.
# Enabled-queue VM selection and baseline default-dispatch checks use explicit
# private JSON registries and launcher doubles; deployed scheduling edits no
# longer change their finite fixture assumptions. Compatible ownership remains.

# Interrupted write-e2e close-out recovery reuses private pytest checkouts and
# waited launcher/agent doubles. No live VM, display, cache or shared mutation;
# the existing compatible unit and cleanup classifications remain applicable.
# Escalation/restart/stall checks reuse those private checkouts and waited agent
# doubles, adding no model calls, VM operations or shared resources.
# Batch optimization and commit recovery use the same private checkouts, local
# Git identity/configuration and waited agent doubles; compatible overlap remains
# valid without touching the developer's Git index, history, hooks or identity.
# Push/retry checks add tiny pytest-private bare remotes and synchronously waited
# local Git children, with no network or shared remote; compatible overlap holds.
# Accepted-completion limit checks use the same private remotes and waited Git
# commands; unit/cleanup compatibility and existing owner cleanup stay unchanged.
# Fifth-session cap reset likewise uses a tiny pytest-private bare remote and
# waited local Git commands; no network, shared state or new worker lifetime.
# First-session successful close-out uses the same private remote allocation and
# waited local Git commands; its unit and cleanup classifications stay compatible.
# Staging-failure recovery also uses a pytest-private bare remote and waited local
# Git children; it adds no network, shared state or live VM resource.
# Prerequisite/consumer recovery uses the same tiny private remote and waited Git
# children; existing compatible unit and cleanup classifications remain valid.
# Newly inserted queue-task recovery uses the same private bare remote and waited
# Git commands; no shared resource or scheduling classification changes.
# Reopened-task recovery adds only a pytest-private bare remote and waited local
# Git commands; compatible overlap remains, without network or shared state.
# Session-boundary handoff restart uses a tiny pytest-private bare remote and waited
# local Git children; no shared cache, socket, bus, display, service or live VM,
# and bounded disk/CPU demand preserves compatible unit/cleanup scheduling.
# Escalation restart with two completed tasks uses the same pytest-private bare
# remote and waited local Git commands; compatible scheduling remains valid.
# Previous-failure session handoff adds a tiny pytest-private bare remote and
# waited local Git children; no network, shared state or live VM is added.
# Existing compatible unit and cleanup classifications remain valid.
# Completion session summaries likewise use a tiny pytest-private bare remote
# and waited local Git children; compatible unit/cleanup scheduling remains valid.
# Completed-task compaction uses the same private remote and waited local Git
# children; no shared paths, network, sockets, displays or live VM are added.
# Tiny disk/CPU demand and unchanged owned-agent cleanup preserve compatibility.
# Previous-launcher session exclusion adds a tiny pytest-private bare remote and
# waited local Git children; no shared state, network, sockets, displays or live
# VM is added, so compatible unit/cleanup scheduling and owned cleanup hold.
# Attached-limit adjustment checks likewise use a tiny pytest-private bare remote
# and waited local Git children; compatible scheduling and worker cleanup hold.
# Task-only limits and explicit scripted stops reuse those private checkpoints,
# owner lifetimes and waited doubles; no shared resource or extra child is added.
# Successful cancellation recovery adds a tiny pytest-private bare remote and
# waited local Git children; no network, shared state, sockets, displays or live
# VM is added. Bounded disk/CPU use and existing owned cleanup stay compatible.

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
# Package-payload notification imports use one additional serial, waited Python
# child in the existing private cwd. Both interpreters disable bytecode writes
# and graphical displays; GTK type registries are process-local, and captured
# pipes add no shared files, sockets or services. package_payload stays compatible.
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
# Scriptlet macro coverage adds bounded, waited `rpm --eval` children. They
# expand private text with explicit macros; no package database or transaction
# is opened. Relocated cleanup machines only decode literal percent escapes.
# Fedora readiness regressions reuse those command doubles and existing staged
# Fedora/Ubuntu payload fixtures. Unit parsing and activation comparisons add
# only private files; no real systemd, SELinux policy, VM or extra build fixture.
# The packaging modules retain their compatible unit classifications.
# Failed kiosk-manager recovery uses the same private package-machine files,
# bounded shell children and explicit systemctl doubles on both distributions.
# No live manager, user bus or journal is changed; package_configuration keeps
# its compatible classification and existing fixture ownership.
# Configuration exclusion and dual policy-file regressions use only private
# fixture trees and bounded command/launcher doubles. No live bus, service,
# daemon or VM; configuration and execution_policy remain compatible units.
# File-backend preparation/rollback cases in package_activation and removal use
# private tiny configuration trees; no live daemon or shared host configuration.
# Root maintenance logout checks use process-local account/session/command
# doubles; no real identity changes, session, bus or display. Trust-readiness
# checks use private tiny manifests and fake command/clock results. Existing
# e2e_desktop_session and package_activation compatible classifications hold.
# Publication-reader regressions use pytest-private LMDB databases and bounded,
# waited writer children, including concurrent slot publication. No live daemon,
# host trust database or shared path; package_activation stays compatible.
# Child-module trust checks reuse private staged payloads and relocated lifecycle
# machines, tiny hashes/files and waited command doubles. They touch no host
# trust database, service, bus, VM or shared cache; existing packaging, activation,
# configuration and removal modules remain compatible, with no added build load.
# VM input-file regressions use tiny private pytest files, a sparse oversized
# sentinel, private FIFO and process-local stdin/transport doubles. No real VM,
# host service, socket or input descriptor is changed; vm_control_cleanup_safety
# and vm_config retain compatible scheduling in unit and cleanup inventories.
# Retained-entry reproduction guards reuse vm_control_cleanup_safety's private
# request files and process-local plans; the compatible resource scope holds.
# Kiosk approval diagnostics extend the same private plan/request and dispatcher
# doubles, including retained-form read-before-Request refusal and private
# result files before password input. No live guest, display, bus,
# shared cache or new process owner; VM-control remains compatible.
# RetainedDesktopJourney extraction adds renamed comparison/capture regressions
# to e2e_desktop_session using only tiny private recorder files and in-memory
# values. Existing waited Perl probes are unchanged; no bus/display/VM, shared
# path/cache or new process/cleanup owner. Its compatible classification holds;
# cleanup and UI inventories gain no new module or resource lifetime.
# Restored-off maintenance recovery uses private lease journals, tiny fixture
# disks and mocked VM/inspection calls, including a simulated restart during
# audit. It adds no live VM or shared resource; vm_control remains compatible.
# Auto-baseline recovery likewise adds only private journals and VM doubles;
# its interruption/refusal checks remain compatible in both inventories.
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
# Interrupted snapshot cleanup adds private synthetic snapshot/record proofs
# and mocked off-domain APIs to that rig; no live VM or new resource owner.
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
# Interrupted-collection and inventory-guard regressions use in-memory pytest
# sessions/events and the existing tmp_path Report fixture. No subprocess,
# shared storage, display, socket or VM is added; regression/regression_cleanup
# retain compatible unit scheduling.
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
    # Measured 913 dispatch cases with synthetic source identities.
    'test_test_launchers.py': 6,
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
# Targeted unpublished-input recovery uses private journals/local locks and
# process-local command doubles. Batch-input transfers add paired journals and
# synchronous
# interruption/verification doubles. VM queue checks use existing private
# dispatch doubles; no live guest, bus, shared state or new child owner is added.
# Oversized recovery adds tiny private journals/local locks and mocked VM
# leases/live references; transfer fingerprints use bounded in-memory archives
# and private files. Retention and vm_transport stay compatible; no live guest,
# shared storage, process or additional resource lifetime is introduced.
# Evidence bundles and publication transactions use small pytest-private journals,
# ZIP files, descriptors and synchronous metadata/failure doubles. They start no
# subprocess, VM, network, display or service and mutate no shared cache/path;
# evidence_bundle and test_retention remain compatible with reviewed unit work.
# Target-journal catalogue checks use private paths and process-local identity/
# registry doubles; they neither switch credentials nor inspect real journals.
# Recovery-diagnostic export/rotation checks reuse those private journals and
# bounded ZIP fixtures, with no new shared resources or subprocesses.
# Aggregate dispatcher retention uses real stores below tmp_path and fixture-local
# scratch, preserving isolation without touching shared host scratch ownership.
# Native transaction input, preflight, route and staging checks use tiny private
# pytest files, synthetic native metadata and command/retention doubles. They do
# not access the installed package database, network, VM, shared trust/cache,
# socket or display. Native archive fixtures and isolated verification children
# (where used) finish within the owning test. Compatible unit overlap applies;
# no cleanup/UI inventory gains a module or a live resource owner.
# test_test_retention_cleanup_safety also preserves native completion manifests
# using its existing private journal/files; both unit and cleanup reviews retain
# compatible overlap and add no process or shared mutable resource.
# Native guest import closure uses one bounded, waited isolated Python child;
# preflight short-write coverage owns only an auto-closed anonymous descriptor.
# Both stay within these modules' existing compatible private resource scope.
