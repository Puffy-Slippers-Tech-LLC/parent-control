"""Observe live VM controller reports before guest-side Watch starts.

This is display metadata only. Report ownership, not a retained timestamp or
PID, determines liveness; it grants no VM, input or cancellation authority.
"""

from contextlib import contextmanager, ExitStack
import fcntl
import os
from pathlib import Path
import re

from test_storage import directory, watch_root


def registration(root, name):
    return directory('state', root=watch_root(root), create=False) / (
        'vm-controller-' + name.encode('ascii').hex() + '.json')


@contextmanager
def publishing(root, report):
    from detached_launcher import atomic, lock
    from vm_selection import WORKER, selected
    with ExitStack() as owner:
        try:
            if os.environ.get(WORKER) == '1':
                vm = selected()
                fd = owner.enter_context(lock(report / 'watch-owner'))
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                directory('state', root=watch_root(root))
                atomic(registration(root, vm.name),
                       dict(vm=vm.name, vm_id=vm.id, report=str(report)))
        except (OSError, ValueError):
            # Observation must not change the test's execution or verdict.
            owner.close()
        yield


def registered(root):
    from watch_output import read_json, JsonReader
    from vm_selection import vm_config
    from types import SimpleNamespace
    reader = JsonReader()
    try:
        paths = directory('state', root=root, create=False).glob('vm-controller-*.json')
        for path in paths:
            try:
                value = read_json(path, 8192)
                name = vm_config.validate_name(value['vm'])
                if path != registration(root, name):
                    continue
                identifier = value['vm_id']
                if identifier is not None and (not isinstance(identifier, str)
                        or re.fullmatch(r'[1-9][0-9]*', identifier) is None):
                    continue
                if progress(root, name, None, reader=reader) is None:
                    continue
                yield name, SimpleNamespace(name=name, id=identifier)
            except (OSError, ValueError, KeyError, TypeError):
                continue
    except (OSError, ValueError):
        return


def progress(root, name, current, *, reader):
    from watch_output import open_private
    from e2e_watch_protocol import progress_packet
    import json
    try:
        value = reader.read(registration(root, name), 8192)
        report = Path(value['report'])
        if (value['vm'] != name or not report.is_relative_to(root)
                or report.parent.name != 'reports'):
            return current
        with open_private(report / 'watch-owner') as owner:
            try:
                fcntl.flock(owner, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                return current
            categories = reader.read(report / 'progress.json')
            pending = next((item for item in categories if item.get('wait_reason')), None)
            if current and pending is None:
                return current
            operation = pending['wait_reason'] if pending else 'Preparing tests or collecting controller results'
            fallback = dict(current or dict(current=1, total=1, case_id='controller',
                title='VM controller', step=''))
            fallback.update(operation=operation)
            fallback.pop('operation_started_ns', None)
            return json.loads(progress_packet(fallback))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return current
