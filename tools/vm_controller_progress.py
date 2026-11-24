"""Observe live VM controller reports before guest-side Watch starts.

This is display metadata only. Report ownership, not a retained timestamp or
PID, determines liveness; it grants no VM, input or cancellation authority.
"""

from contextlib import contextmanager, ExitStack
import fcntl
from functools import lru_cache
import json
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


@lru_cache(maxsize=64)
def _standalone_case(root, dispatch, category, case):
    # The dispatch identity pins this description until the case leaves the VM.
    from vm_run_times import metadata
    if category == 'system' and (root / 'tests/integration' / (case + '.py')).is_symlink():
        return None
    try:
        item = metadata(root, category, case)
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, StopIteration):
        from vm_recording import case_identity
        identifier, title = case_identity(root, category, dict(nodeid=case))
        item = dict(id=identifier, title=title, description='')
    if item is None:
        return None
    return dict(current=1, total=1, case_id=str(item['id']), title=item['title'],
                step='', operation='', description=' '.join(item['description'].split())[:1024])


def _standalone_selection(root, dispatch, category, args):
    if category == 'system':
        from test_commands import system_check_selection
        case = system_check_selection(args)
    elif category == 'e2e':
        from vm_recording import E2E_QUALIFICATIONS
        case = next((arg for arg in args if arg in E2E_QUALIFICATIONS), None)
    else:
        return None
    return _standalone_case(root, dispatch, category, case) if case else None


def progress(root, name, current, *, reader, show_operation=True):
    if current and not show_operation:
        return current
    from watch_output import open_private
    from e2e_watch_protocol import progress_packet
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
            if not current:
                for item in categories:
                    if item.get('state') == 'Running':
                        current = _standalone_selection(root, report, item.get('retry_category'),
                                                        item.get('selection_args') or ())
                        if current:
                            break
            # The live report keeps the VM visible between case publications,
            # even when both optional feeds are off.
            pending = (next((item for item in categories if item.get('wait_reason')), None)
                       if show_operation else None)
            if current and pending is None:
                return current
            fallback = dict(current or dict(current=1, total=1, case_id='controller',
                title='VM controller', step=''))
            if show_operation:
                fallback['operation'] = (pending['wait_reason'] if pending else
                                         'Preparing tests or collecting controller results')
            else:
                fallback['operation'] = ''
            fallback.pop('operation_started_ns', None)
            description = fallback.pop('description', '')
            return dict(json.loads(progress_packet(fallback)), description=description)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return current
