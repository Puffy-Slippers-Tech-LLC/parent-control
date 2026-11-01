"""Schedule retained tests without splitting module fixtures.

Retained modules use private pytest files, locks and process-local doubles.
Owned children are bounded and reaped; no live VM, service, display or shared
cache is acquired. Deleting tests adds no resource owner or overlap requirement.
Unknown modules remain exclusive pending review.
"""

from pathlib import PurePosixPath
from regression_ui import Bucket
from regression_resources import HOST_WORKERS


REVIEWED = frozenset("""
screen_preview
execution_probe
fixture
fixture_provision
package_purge
probe_bus_client
probe_channel
probe_generation
regression
vm_backup
vm_control
""".split())

ESTIMATES = {
             'test_graphical_lease.py': 8.5,
             'test_vm_control_cleanup_safety.py': 6.5,
             'test_execution_probe_cleanup_safety.py': 3,
             'test_regression_cleanup_safety.py': 4,
}


def work_units(path, ids, kind, estimate):
    """Keep each retained module and its fixtures together."""
    return [Bucket(path, (path,), tuple(ids), kind, estimate)]


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
