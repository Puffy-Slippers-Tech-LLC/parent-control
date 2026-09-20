"""Partition the discovered UI inventory without splitting shared fixtures.

Known modules have private compositor/bus/settings and per-attempt evidence.
Keep nested Shell in one job because it also publishes stable latest evidence.
New modules remain included, but run exclusively until their isolation is reviewed.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath


# Host collection and execution must select the same runnable inventory.
# Live spectator acceptance needs an independently active VM attempt and is
# selected explicitly, outside the aggregate's pre-VM host phase.
TIMEOUT_ARGS = ('--timeout', '1800s')
HOST_ARGS = (*TIMEOUT_ARGS, '-m', 'not live_e2e')


def selected_options(root, args):
    """Keep validated pytest options; collected IDs supply the worker targets.

    UI-only execution gets the host bucket timeout by default. Do not inherit
    host's marker filter: explicit selections must retain their exact scope.
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
    ('E2E spectator', ('test_e2e_watch.py',), 6),
)

# The adapter's Shell search has its own artifact/runtime root and outer
# hermetic compositor; it does not publish Nested Shell's stable latest paths.
# The spectator fixture uses process-local memfds and per-test output. Its live
# checks only read a running E2E feed and are excluded from host aggregates.
# Keep pairing identities separate even when buckets have the same reservation.
# A qualified build companion must never implicitly authorize other UI fixtures.
KINDS = ('ui-request', 'ui-layout', 'ui-feedback', 'ui-preview', 'ui-screen', 'ui-shell',
         'ui-accessible', 'ui-watch')


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
