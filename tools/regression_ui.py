"""Partition the discovered UI inventory without splitting shared fixtures.

Known modules have private compositor/bus/settings and per-attempt evidence.
Keep nested Shell in one job because it also publishes stable latest evidence.
New modules remain included, but run exclusively until their isolation is reviewed.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath


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
    return args, ['--timeout', command[2], *options]


def serial_options(options):
    """A per-invocation failure limit must not become a per-bucket limit."""
    return '-x' in options or any(arg.startswith('--maxfail=') and int(arg.split('=')[1]) > 0
                                  for arg in options)


GROUPS = (
    ('Request behavior', ('test_request_form_component.py',), 6),
    ('Layout and overflow', ('test_request_layout.py', 'test_control_overflow.py'), 6),
    ('Feedback', ('test_parent_feedback.py', 'test_error_feedback.py'), 6),
    ('Preview and About', ('test_preview_smoke.py', 'test_about_release.py'), 6),
    ('Screen fidelity', ('test_screen_preview.py',), 12),
    ('Nested Shell', ('test_child_shell_lifecycle.py',), 30),
    ('Accessible adapter', ('test_e2e_accessible_adapter.py',), 12),
    ('Test spectators', ('test_e2e_watch.py', 'test_ui_watch.py'), 6),
    ('Automation identity', ('test_automation_identity.py',), 12),
    ('Fixture GUI', ('test_fixture_gui.py',), 30),
)

# The adapter's Shell search has its own artifact/runtime root and outer
# hermetic compositor; it does not publish Nested Shell's stable latest paths.
# The spectator fixture uses process-local memfds and per-test output. Its live
# checks only read a running E2E feed and are excluded from host aggregates.
# Automation identity uses the standard private preview session. Fixture GUI
# builds its payload and Flatpak installation below its private pytest root;
# both use the worker's private compositor, accessibility bus and runtime.
# Keep pairing identities separate even when buckets have the same reservation.
# Feedback replacement uses the adapter bucket's private preview, compositor and
# accessibility bus; keyboard input and app cleanup stay inside that fixture.
# Preview allowance focus and rejected-draft reload checks reuse that bucket's
# private Parent process, keyboard/display and optional tmp_path event log;
# child reselection adds no shared resources or extra process.
# The held allowance save uses a tmp_path release file and event log within
# that same private preview; finally releases its existing broker worker.
# Public reader connections belong to each private preview bus and close before
# fixture teardown; alias resolution and selection waits add no shared resource.
# A qualified build companion must never implicitly authorize other UI fixtures.
KINDS = ('ui-request', 'ui-layout', 'ui-feedback', 'ui-preview', 'ui-screen', 'ui-shell',
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
