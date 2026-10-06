"""Partition the discovered UI inventory without splitting shared fixtures.

Known modules have private compositor/bus/settings and per-attempt evidence.
Keep nested Shell in one job because it also publishes stable latest evidence.
New modules remain included, but run exclusively until their isolation is reviewed.

Child-desktop defaults and delayed upgrade replies in language_settings reuse
the owned request preview/display/bus and tmp_path events. Agent preparation is
a process-local transport double; no host agent/service/locale is touched.
The existing compatible Request behavior and Feedback buckets still apply.
The retained Parent picker regression adds a second sequentially closed preview
through the same owned preview_applications fixture, private display/bus and
tmp_path events. It introduces no shared service or cache; the existing Request
behavior bucket and its whole-module resource reservation remain appropriate.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath

# Update-required modal checks reuse Feedback's private preview/display/bus
# and tmp_path event logs. A shared transport double prevents all host reboot
# calls; no new process owner, privileged mutation or cleanup lifetime is added.
# The existing compatible whole-module Feedback bucket remains appropriate.
# Policy legend reads reuse preview_smoke's owned compositor/application and
# private event files, with the shared AT-SPI adapter. No new shared display,
# process, cache or service; the existing UI bucket classification applies.
# Access-choice GTK checks reuse those private previews, event files and waited
# Perl blocks; no new shared resource or cleanup lifetime is introduced.
# Rejected-rule reports reuse the same private preview/display, synthetic local
# broker/log collector and waited Perl blocks; the whole-module bucket applies.
# Parent first-run dismissal reuses each preview's private accessibility bus
# and recorded owner. The temporary reader is reset before launch returns; no
# new process, shared setting, file or cleanup lifetime is introduced.
# Native activity identity/readback adds only immutable public values to the
# existing fixture GUI's private display and owned payload processes; retain
# its whole-module fixture build reservation and compatible classification.
# Localization review keeps the existing private preview/display/bus and owned
# application lifecycle. Optional images read only the current worker's sealed
# spectator feed, close readers, and use registered retention allocations.
# Sequential language matrices and bounded drafts retain the Layout/Feedback
# reservations; no host settings, network, new process or shared mutable cache.
# Synthetic translation-helper contracts live in test_translation_widget_contracts
# and reuse the Identity bucket's private display/bus with one waited GTK 4 child.
# Moving these engineering assertions adds no session, service or cleanup owner.
# Chooser preview/modal checks use one waited GTK child, a NON_UNIQUE application
# and two windows on that same private display/bus, including fullscreen focus.
# They add no shared cache, setting, file, service or cleanup owner.
# The 62-choice catalogue matrix retains that one owned GTK child and private
# display; scrolling/native-name direction checks add no resource lifetime.
# RTL context/reversibility checks use one waited GTK child and unshown windows
# on that same Identity private display; no extra bus, cache or cleanup owner.
# Native script shaping uses one presented window in the same waited child and
# private display; its attributes/layout checks add no process or cleanup owner.
# Expanded-choice translated Save cases reuse the Request behavior bucket's owned
# preview and private event files, without network or host locale changes.
# Overlay valid-choice checks reuse the Request behavior bucket's private GTK
# preview/display/bus and waited Perl input blocks, with its owned cleanup.
# They introduce no shared setting, file, process or service lifetime.
# Child interaction waits dispatch bounded work on the existing private bus;
# no inspection listeners/sources or new process owners remain. Nested Shell
# retains its whole-module bucket and existing resource reservation.
# The panel localization cycle reuses that guardian-owned nested Shell and its
# serial overlay launches, public input/result guards and retained screenshots.
# It adds no process owner or persistent host settings; its finite nine-language
# cycle has an explicit 600-second child deadline within the same Shell bucket.
# Timing hooks retain bounded per-phase aggregates in the existing category
# stream through one non-inheritable pipe duplicate closed at session end.
# Wrappers/counters are worker-local, with no threads/files or UI reads; preview
# ownership, cleanup and all bucket reservations remain unchanged.
# Correlated operation/wait spans use the same stream and bounded nesting-local
# counters. They add no poller/thread, event dispatch, input or resource owner.
# Parent preview keyboard checks restore only the spawned child's simulated
# VS Code Snap overrides before GTK imports. They reuse Request behavior's
# private display/bus, public IDs and owned process; no host environment,
# monitor settings, shared cache or cleanup lifetime changes.
# Query/occupancy, worker CPU and stream-write diagnostics add bounded counters
# to the same worker-local timing recorder and retained stream. No new reads,
# threads, files, processes or resource owners; all UI reservations remain valid.
# Missing-cache traversal roles/states share the existing private bus pipeline
# (at most 64 RPCs). No threads, connections, processes or cleanup owners are
# added; snapshot-local values retain the compatible UI bucket reservations.
# Application UI catalogs open client connections to each worker's existing
# private session bus, never a new bus server. The owning fixture closes every
# catalog, including independent case readers, on success and failure. This
# adds no process, file, host service or shared mutable state; existing whole-
# module reservations and compatible bucket classifications remain appropriate.


# UI is host-only. The shared launcher always excludes VM-dependent live_e2e
# checks; aggregate arguments make the same boundary explicit in its inventory.
TIMEOUT_ARGS = ('--timeout', '1800s')
HOST_ARGS = (*TIMEOUT_ARGS, '-m', 'not live_e2e')


def selected_options(root, args):
    """Keep validated pytest options; collected IDs supply the worker targets.

    UI-only execution gets the host bucket timeout by default. The shared
    launcher combines caller marker filters with the host-only boundary.
    """
    from test_launcher import pytest_command
    args = list(args) if args[:1] == ['--timeout'] else [*TIMEOUT_ARGS, *args]
    command = pytest_command(root, args, 'ui')
    options = command[command.index('no:cacheprovider') + 1:command.index('--')]
    return args, ['--timeout', args[1], *options]


def serial_options(options):
    """A per-invocation failure limit must not become a per-bucket limit."""
    return '-x' in options or any(arg.startswith('--maxfail=') and int(arg.split('=')[1]) > 0
                                  for arg in options)


GROUPS = (
    # Language settings use the existing owned previews and private bus/display.
    # Tiny tmp_path event/release files gate one worker; finally releases it.
    # No host locale/settings mutation, network, new service or cleanup owner.
    # Request loading also gates its existing preview's preference callback on
    # a tmp_path release file; bounded main-loop polling adds no resource owner.
    ('Request behavior', ('test_request_form_component.py', 'test_language_settings.py'), 6),
    # App Limits language-review frames reuse the worker's spectator feed and
    # registered retention allocations; no new display, process or cleanup owner.
    ('Layout and overflow', ('test_request_layout.py', 'test_control_overflow.py'), 6),
    ('Feedback', ('test_parent_feedback.py', 'test_error_feedback.py'), 6),
    # Match invalid/Reset matrix shares the owned private preview/display and
    # bounded keyboard workers of the valid matrix; keep this module together.
    # Allowance keyboard checks reuse the same preview, guarded input and tiny
    # tmp_path event files; no new shared resource or cleanup owner.
    ('Preview smoke', ('test_preview_smoke.py',), 6),
    # About launches independent per-test applications. Give its module a
    # separate worker deadline so the long preview matrices cannot consume
    # its startup/check budget. Each module keeps its session fixtures intact.
    ('About', ('test_about_release.py',), 6),
    ('Screen fidelity', ('test_screen_preview.py',), 12),
    ('Nested Shell', ('test_child_shell_lifecycle.py',), 30),
    ('Accessible adapter', ('test_e2e_accessible_adapter.py',), 12),
    ('Test spectators', ('test_e2e_watch.py', 'test_ui_watch.py', 'test_watch.py'), 6),
    ('Automation identity', ('test_automation_identity.py', 'test_translation_widget_contracts.py'), 12),
    ('Fixture GUI', ('test_fixture_gui.py',), 30),
)

# The adapter's Shell search has its own artifact/runtime root and outer
# hermetic compositor; it does not publish Nested Shell's stable latest paths.
# The spectator fixture uses process-local memfds and per-test output. Its live
# checks only read a running E2E feed and are excluded from host aggregates.
# The combined watcher has private memfds, runtime sockets and tmp_path launcher
# locks/logs, on this same private display/bus; it starts no real runner or VM.
# The multi-VM grid uses up to five private synthetic memfds in this fixture;
# cells share only its private display/bus and add no libvirt or host resources.
# The stalled-VM check parks only a private transport thread; its event is
# released before owned feeds are closed and joined, including failure cleanup.
# Checkout terminal/flat-grid checks add three tiny private log/lock trees,
# four private UI sockets and three synthetic VM memfds. Tile double clicks
# and branch/tab changes stay on GTK's main thread on this private display.
# They retain the same spectator reservation and compatible scheduling.
# VM ID ordering adds only a tiny config in the same tmp_path; duplicate-tab
# handoff uses the existing synthetic feeds and starts no additional process.
# The singleton check adds
# plus one waited singleton peer on that same private display/bus. No real Git
# checkout, controller, desktop service or VM is started by the fixture.
# Automation identity uses the standard private preview session. Fixture GUI
# Parent Hebrew logical-text/Tab checks use Request behavior's existing private
# preview process, compositor, accessibility bus and event file. No new live
# owner, shared path, service or display; compatible UI classification stays.
# Parent dialog language/draft navigation reuses those private previews and
# events, with no external delivery or new resource/cleanup owner.
# Enabled Hebrew allowance/balances reuse the same private Parent preview and
# display; the finite return-to-English adds no owner or resource reservation.
# builds its payload and Flatpak installation below its private pytest root;
# both use the worker's private compositor, accessibility bus and runtime.
# Keep pairing identities separate even when buckets have the same reservation.
# The catalogue matrix uses the existing private Parent preview and event log,
# with finite scripted native rows. Its waited Perl children expand input only;
# no VM, system catalogue, network or shared settings are touched.
# About has its own private compositor, bus, XDG settings and retained preview
# logs. Both modules retain the existing UI resource reservation and compatible
# overlap; About gains no publishing companion permission or shared service.
# Feedback replacement uses the adapter bucket's private preview, compositor and
# accessibility bus; keyboard input and app cleanup stay inside that fixture.
# Synthetic duplication uses that same editor's clipboard on the private
# display; it adds no helper process or host clipboard access.
# Checked-event observation uses that same private GTK preview/accessibility
# bus, with scoped subscriptions and no added thread, display or shared cache.
# Combined-format/rejection checks retain this same private preview and bounded
# 1,200-line document, including close/reopen and decoration removal. No new
# processes, sockets, caches or shared state; the existing adapter budget applies.
# UTF-16 boundary checks retain this private preview/display and bounded 5,001-unit
# drafts; Unicode input adds no process, bus, clipboard service or shared cache.
# Their clipboard doubles reuse that private editor and display, with no host
# clipboard or added resource demand; the existing adapter classification applies.
# Preview allowance focus and rejected-draft reload checks reuse that bucket's
# private Parent process, keyboard/display and optional tmp_path event log;
# child reselection adds no shared resources or extra process.
# Full preset enumeration uses the same private Parent, bus and tmp_path log;
# its sequential actions add no shared resource or concurrent fixture demand.
# The held allowance save uses a tmp_path release file and event log within
# that same private preview; finally releases its existing broker worker.
# Public reader connections belong to each private preview bus and close before
# fixture teardown; alias resolution and selection waits add no shared resource.
# Station restriction adapter checks reuse the private request preview, its bus,
# display and tmp_path event log; they add no shared resources or fixture builds.
# A qualified build companion must never implicitly authorize other UI fixtures.
# Feedback block meaning/removal/undo checks use the existing private Parent,
# compositor and accessibility bus; bounded text and tree reads add no shared
# cache, socket, process or fixture build. Keep the Feedback classification.
# Shared GUI blocks add only short, waited, read-only Perl trace processes in
# Feedback/Accessible adapter; actual input stays on each private compositor.
# The attachment matrix uses pytest disk scratch (bounded 5 MiB files), a fake
# external chooser and the real frontend worker. No shared path/cache/service,
# additional display or heavy fixture build; retain both compatible buckets.
# Chooser delivery acknowledgements use tiny files beside that same private
# manifest, with no new process, bus, display or scheduling resource.
# Capture children inherit their private worker's owned group so emergency
# worker retirement cannot strand private PipeWire services. Each bucket still
# owns a separate group, compositor, bus and runtime; no host service is joined.
# Nested Shell additionally owns one small guardian subprocess per scenario.
# Its lifetime pipe and kernel subreaper scope contain only that private Shell
# launch and services; its socket runtime and scratch locks outlive forced pytest
# exit. It introduces no shared resource; keep the existing ui-shell reservation.
KINDS = ('ui-request', 'ui-layout', 'ui-feedback', 'ui-preview', 'ui-about', 'ui-screen', 'ui-shell',
         'ui-accessible', 'ui-watch', 'ui-identity', 'ui-fixture-gui')


@dataclass(frozen=True)
class Bucket:
    name: str
    paths: tuple[str, ...]
    nodeids: tuple[str, ...]
    kind: str
    estimate: float


def buckets(nodeids):
    if not nodeids or len(set(nodeids)) != len(nodeids):
        raise ValueError('UI inventory is empty or contains duplicate test IDs')
    files = {}
    for nodeid in nodeids:
        filename, separator, _ = nodeid.partition('::')
        path = PurePosixPath(filename)
        if (not separator or path.parts[:2] != ('tests', 'ui') or '..' in path.parts
                or not path.name.startswith('test_') or path.suffix != '.py'):
            raise ValueError('UI inventory contains an invalid test path')
        files.setdefault(filename, []).append(nodeid)
    result = []
    for (name, names, seconds), kind in zip(GROUPS, KINDS, strict=True):
        paths = tuple('tests/ui/' + name for name in names if 'tests/ui/' + name in files)
        if paths:
            ids = tuple(node for path in paths for node in files.pop(path))
            result.append(Bucket('UI — ' + name, paths, ids, kind, 20 + seconds * len(ids)))
    for path, ids in sorted(files.items()):
        result.append(Bucket('UI — ' + path.removeprefix('tests/ui/'), (path,), tuple(ids),
                             'ui-exclusive', 20 + 6 * len(ids)))
    return result
