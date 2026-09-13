"""Partition the discovered UI inventory without splitting shared fixtures.

Known modules have private compositor/bus/settings and per-attempt evidence.
Keep nested Shell in one job because it also publishes stable latest evidence.
New modules remain included, but run exclusively until their isolation is reviewed.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath


GROUPS = (
    ('Request behavior', ('test_request_form_component.py',), 6),
    ('Layout and overflow', ('test_request_layout.py', 'test_control_overflow.py'), 6),
    ('Feedback', ('test_parent_feedback.py', 'test_error_feedback.py'), 6),
    ('Preview and About', ('test_preview_smoke.py', 'test_about_release.py'), 6),
    ('Screen fidelity', ('test_screen_preview.py',), 12),
    ('Nested Shell', ('test_child_shell_lifecycle.py',), 30),
)


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
    for name, names, seconds in GROUPS:
        paths = tuple('tests/ui/' + name for name in names if 'tests/ui/' + name in files)
        if paths:
            ids = tuple(node for path in paths for node in files.pop(path))
            result.append(Bucket('UI — ' + name, paths, ids, 'ui', 20 + seconds * len(ids)))
    for path, ids in sorted(files.items()):
        result.append(Bucket('UI — ' + path.removeprefix('tests/ui/'), (path,), tuple(ids),
                             'ui-exclusive', 20 + 6 * len(ids)))
    return result
