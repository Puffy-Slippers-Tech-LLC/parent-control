"""Latest VM case timings for local and transferred executions."""

import ast
from collections import defaultdict
from contextlib import ExitStack
import fcntl
import hashlib
import json
import math
import os
import runpy
import sys
import time
import uuid

if __package__:
    from . import test_storage, test_retention
    from .vm_recording import case_identity
    from .vm_selection import selected
else:
    import test_storage
    import test_retention
    from vm_recording import case_identity
    from vm_selection import selected


def descriptions(root):
    """Checked-in human scenarios, independent of execution and timing history."""
    result = {}
    for name in ('system_case_steps.json', 'system_check_steps.json'):
        path = root / 'tests/integration' / name
        if not path.is_file():
            continue  # Related worktrees may predate scenario metadata.
        for identifier, value in json.loads(path.read_text()).items():
            result['system', int(identifier) if identifier.isdecimal() else identifier] = value
    path = root / 'tests/e2e/scenario_steps.json'
    if not path.is_file():
        return result
    scenarios = json.loads(path.read_text())
    inventory = json.loads((root / 'tests/e2e/scenarios.json').read_text())
    for scenario in inventory['scenarios']:
        value = scenarios[scenario['id']]
        for variant in scenario['variants']:
            result['e2e', variant['coverage_id']] = {
                **value, **value.get('variants', {}).get(variant['id'], {})}
    return result


def describe_case(record, catalogue):
    value = catalogue.get((record['category'], record['id']))
    if value:
        record.update(description=value.get('summary', record['title']),
                      steps=value['steps'], expected=value['expected'],
                      execution_revision=value.get('execution_revision', 1))
    return record


def metadata(root, category, nodeid):
    identity = case_identity(root, category, dict(nodeid=nodeid))
    if identity is None:
        return None
    identifier, title = identity
    description = ''
    if category == 'system' and not nodeid.startswith('check_'):
        sys.path.insert(0, str(root / 'tests/integration'))
        try:
            from system_case_ids import identity_for_event
        finally:
            sys.path.pop(0)
        case = identity_for_event(nodeid)
        function = case.case_id.split('[')[0]
        # Locate the registered function without importing executable guest code.
        candidates = sorted((root / 'tests/system').glob('test_*.py'))
        source = None
        for candidate in candidates:
            tree = ast.parse(candidate.read_text())
            match = next((item for item in tree.body
                          if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                          and item.name == function), None)
            if match:
                source = candidate
                description = ast.get_docstring(match) or ''
                break
        if source is None:
            return None
    elif category == 'e2e' and nodeid.startswith('--qualify-'):
        if __package__:
            from .vm_recording import E2E_QUALIFICATIONS
        else:
            from vm_recording import E2E_QUALIFICATIONS
        source = root / E2E_QUALIFICATIONS[nodeid][2]
        description = ast.get_docstring(ast.parse(source.read_text())) or ''
    elif category == 'e2e':
        document = json.loads((root / 'tests/e2e/scenarios.json').read_text())
        scenario_id, variant_id = nodeid.split('/', 1)
        scenario = next(item for item in document['scenarios'] if item['id'] == scenario_id)
        variant = next(item for item in scenario['variants'] if item['id'] == variant_id)
        source = root / variant['executable']['path']
        description = '\n'.join(step['description'] for steps in scenario['phases'].values()
                                for step in steps)
    else:
        source = root / 'tests/integration' / (nodeid.removesuffix('.py') + '.py')
        if not source.is_file():
            return None
        description = ast.get_docstring(ast.parse(source.read_text())) or ''
    return describe_case(dict(id=identifier, title=title, category=category,
                              case_file=str(source.relative_to(root)),
                              description=description or title), descriptions(root))


def _name(*parts):
    key = json.dumps(parts, separators=(',', ':'))
    return 'vm-time-' + hashlib.sha256(key.encode()).hexdigest() + '.json'


def _revision_prefix(record):
    return _name(record['category'], record['id'], record['vm'],
                 record.get('execution_revision', 1)).removesuffix('.json') + '-'


def _timing_names(record):
    category, identifier, vm = record['category'], record['id'], record['vm']
    # A file move can keep the same case identity and execution revision.
    source = hashlib.sha256(record['case_file'].encode()).hexdigest()
    return (_revision_prefix(record) + source + '.json', _name(category, identifier, vm),
            _name(category, identifier))


def _recording_keys(record, default=None):
    keys = record.get('recording_stores')
    if not isinstance(keys, list):
        keys = [record.get('recording_store', default)]
    return [key for key in keys if key is None or isinstance(key, str)]


def _case_link(root, record):
    path = root / record['case_file']
    if path.is_relative_to(root / 'tests') and path.resolve() == path and path.is_file():
        return path.as_uri()
    return None


def _read(fd, name):
    source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(source) as stream:
        info = os.fstat(stream.fileno())
        test_retention.private(info, regular=True)
        if info.st_size > 256 * 1024:
            raise ValueError('VM timing metadata too large')
        return json.load(stream)


def save(root, record):
    watch_root = test_storage.watch_root(root)
    recording_key = test_storage.storage_root(root).name if watch_root != root else None
    recording_keys = [recording_key]
    directory = test_storage.directory('state', root=watch_root)
    fd = test_retention.directory(directory)
    temporary = '.vm-time-' + uuid.uuid4().hex
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        test_retention.private(os.fstat(fd))
        name = _timing_names(record)[0]
        try:
            previous = _read(fd, name)
        except FileNotFoundError:
            pass
        else:
            if isinstance(previous, dict):
                completed_at = previous.get('completed_at')
                if (type(completed_at) in (float, int) and -math.inf < completed_at < math.inf
                        and completed_at >= record['completed_at']):
                    return
                recording_keys.extend(_recording_keys(previous))
        record = dict(record, recording_stores=list(dict.fromkeys(recording_keys)))
        out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      0o600, dir_fd=fd)
        with os.fdopen(out, 'w') as stream:
            json.dump(record, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)


def _state_directories(roots):
    for storage_root in roots:
        try:
            directory = test_storage.directory('state', root=storage_root, create=False)
        except FileNotFoundError:
            continue
        yield storage_root, directory


def delete(root, record):
    """Remove a published revision's timings, preserving newer runs and recordings."""
    old_names = _timing_names(record)[1:]
    prefix = _revision_prefix(record)
    revision = record.get('execution_revision', 1)
    candidates = []
    roots = (root, *test_storage.remote_operation_roots(root))
    with ExitStack() as locks:
        for _, directory in _state_directories(roots):
            fd = test_retention.directory(directory)
            locks.callback(os.close, fd)
            fcntl.flock(fd, fcntl.LOCK_EX)
            test_retention.private(os.fstat(fd))
            versioned = (name for name in os.listdir(fd)
                         if name.startswith(prefix) and name.endswith('.json'))
            for name in (*old_names, *versioned):
                try:
                    before = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    saved = _read(fd, name)
                except FileNotFoundError:
                    continue
                if (any(saved[key] != record[key] for key in ('category', 'id', 'vm'))
                        or saved.get('execution_revision', 1) != revision
                        or _case_link(root, saved) is None or name not in _timing_names(saved)):
                    continue
                if saved['completed_at'] > record['completed_at']:
                    raise ValueError('Run time changed; refresh the table before deleting it.')
                candidates.append((fd, name, before))
        for fd, name, before in candidates:
            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError('Run time file changed; refresh before deleting it.')
        for fd, name, _ in candidates:
            os.unlink(name, dir_fd=fd)
        for fd in {fd for fd, _, _ in candidates}:
            os.fsync(fd)


def load(root):
    """Read only logged cases; optional recordings retain their existing owner."""
    remote_roots = {path.name: path for path in test_storage.remote_operation_roots(root)}
    directories = list(_state_directories((root, *remote_roots.values())))
    if not directories:
        return []
    registry = root / 'tests/integration/system_case_ids.py'
    # Watch may display several checkouts at different revisions. Use each
    # checkout's own retirement map, not this process's imported registry.
    identities = runpy.run_path(str(registry)) if registry.is_file() else {}
    unbound = identities.get('UNBOUND_CASES', {})
    titles = {case.numeric_id: case.title for case in identities.get('CASES', ())}
    catalogue = descriptions(root)
    latest = {}
    recording_keys = defaultdict(set)
    for storage_root, directory in directories:
        default = storage_root.name if storage_root != root else None
        for row in _load(root, directory, unbound, titles, catalogue):
            key = row['category'], row['id'], row['vm']
            recording_keys[key].update(_recording_keys(row, default))
            if key not in latest or row['completed_at'] > latest[key]['completed_at']:
                latest[key] = row
    recording_roots = {None: (root, None)}
    if remote_roots:
        from host_dispatch import tool_host
        try:
            host = tool_host(root).name
        except (OSError, ValueError):
            pass
        else:
            recording_roots.update({key: (path, host) for key, path in remote_roots.items()})
    for key, row in latest.items():
        row.pop('recording_store', None)
        row.pop('recording_stores', None)
        locations = (recording_roots[store] for store in recording_keys[key] if store in recording_roots)
        row['recording'] = _latest_recording(row, locations)
    return sorted(latest.values(), key=lambda row: (-row['seconds'], row['title'], row['vm']))


def _load(root, directory, unbound, titles, catalogue):
    from tools.recording_storage import case_identity

    fd = test_retention.directory(directory)
    try:
        test_retention.private(os.fstat(fd))
        for name in os.listdir(fd):
            if not name.startswith('vm-time-') or not name.endswith('.json'):
                continue
            try:
                record = _read(fd, name)
                if not isinstance(record, dict):
                    continue
                revision = record.get('execution_revision', 1)
                if (record['category'] not in ('system', 'e2e')
                        or not case_identity(record['id'])
                        or type(revision) is not int or revision < 1
                        or not isinstance(record['seconds'], (float, int))
                        or not math.isfinite(record['seconds']) or record['seconds'] < 0
                        or type(record['completed_at']) not in (float, int)
                        or not math.isfinite(record['completed_at'])
                        or any(not isinstance(record[key], str) for key in
                               ('title', 'case_file', 'description', 'vm'))
                        or name not in _timing_names(record)):
                    raise ValueError('Invalid VM timing record')
                if (record['category'] == 'system' and
                        unbound.get(record['id'], (None,))[0] == 'retired'):
                    # Consolidated cases no longer appear as tiny standalone
                    # work. Preserve their stored history and recordings.
                    continue
                current = catalogue.get((record['category'], record['id']))
                if current is None and record['category'] == 'e2e' and type(record['id']) is int:
                    # Retired scenario IDs are absent from the E2E inventory.
                    continue
                current = current or {}
                if revision != current.get('execution_revision', 1):
                    # A former fragment is not a measurement or recording of
                    # the new combined history. Retain its files as history.
                    continue
                if record['category'] == 'system' and record['id'] in titles:
                    record['title'] = titles[record['id']]
                case_link = _case_link(root, record)
                if case_link is None:
                    continue
                record['case_link'] = case_link
                yield describe_case(record, catalogue)
            except (OSError, ValueError, KeyError, TypeError):
                continue
    finally:
        os.close(fd)


def _latest_recording(record, locations):
    clips = (_recording(record, path, host) for path, host in locations)
    latest = max((clip for clip in clips if clip is not None), default=None)
    if latest is None:
        return None
    _, uri, duration = latest
    # Older clocks began at pytest start. Keep the matching clip's duration
    # as a lower bound without rewriting the stored timing.
    if (not record.get('includes_preparation') and type(duration) in (int, float)
            and math.isfinite(duration) and duration >= 0):
        record['seconds'] = max(record['seconds'], duration)
    return uri


def _recording(record, storage_root, host):
    from tools.recording_storage import Store

    try:
        with Store(root=storage_root, create=False).vm_owner(
                record['category'], record['id'], record['vm']) as owner:
            current = owner.state['current']
            provenance = owner.state['provenance']
            revision = record.get('execution_revision', 1)
            if (not current or record['vm'] not in provenance.get('vm_names', [])
                    or provenance.get('execution_revision', revision) != revision):
                return None
            # Validate identity without hashing video bytes on every refresh.
            video = owner._open(current, missing=True)
            if video is None:
                return None
            os.close(video)
            uri = (owner.store.path / current['name']).as_uri()
            if host:
                uri = 'onpc-recording://' + host + uri.removeprefix('file://')
            published_at = provenance.get('published_at')
            return published_at if isinstance(published_at, str) else '', uri, provenance.get('duration_seconds')
    except (OSError, ValueError, KeyError, TypeError):
        return None


class Tracker:
    """One execution attempt, accumulating lifecycle phases but never repairs."""

    def __init__(self, root, category):
        self.root, self.category = root, category
        self.starts, self.totals, self.metadata = {}, {}, {}
        self.pending = {}
        self.envelope_starts = {}

    def event(self, event):
        if self.category not in ('system', 'e2e'):
            return
        if event.get('kind') == 'collection':
            nodeids = event.get('nodeids')
            if not nodeids:
                return
            for nodeid in nodeids:
                try:
                    identity = case_identity(self.root, self.category, dict(nodeid=nodeid))
                except FileNotFoundError:
                    # Synthetic runner checkouts need not carry a catalogue.
                    identity = None
                if identity is not None:
                    self.pending.setdefault(identity[0], set()).add(nodeid)
                    # Bind descriptions and execution revisions before any
                    # case runs, rather than reinterpreting a finished case
                    # through checkout edits made during its execution.
                    self.metadata[nodeid] = metadata(self.root, self.category, nodeid)
            if not any(nodeids[0] in nodes for nodes in self.pending.values()):
                return
            # Recording starts here too: preparation belongs to the first
            # selected case, rather than to every case in the inventory.
            event = dict(kind='prepared', nodeid=nodeids[0])
        kind, nodeid = event.get('kind'), event.get('nodeid')
        if kind not in ('prepared', 'started', 'finished') or not nodeid:
            return
        vm = selected(required=False)
        if vm is None:
            return
        stamp = event.get('monotonic_ns')
        if kind in ('prepared', 'started'):
            if nodeid not in self.metadata:
                self.metadata[nodeid] = metadata(self.root, self.category, nodeid)
            if kind == 'prepared' and event.get('envelope') is True:
                info = self.metadata[nodeid]
                if info is not None:
                    started = self.starts.get(nodeid, (time.monotonic(), None))[0]
                    self.envelope_starts.setdefault((info['id'], vm.name), started)
            # A guest monotonic clock cannot measure host-side preparation.
            # Keep its original host start when pytest subsequently starts.
            self.starts.setdefault(nodeid, (time.monotonic(),
                                            stamp if kind == 'started' else None))
            return
        started = self.starts.pop(nodeid, None)
        if started is None:
            return
        elapsed = time.monotonic() - started[0]
        if type(stamp) is int and type(started[1]) is int and stamp >= started[1]:
            elapsed = (stamp - started[1]) / 1_000_000_000
        if nodeid not in self.metadata:
            self.metadata[nodeid] = metadata(self.root, self.category, nodeid)
        info = self.metadata[nodeid]
        if info is None:
            return
        key = info['id'], vm.name
        pending = self.pending.get(info['id'], set())
        pending.discard(nodeid)
        if event.get('envelope_pending') is True:
            return
        if key in self.envelope_starts:
            elapsed = time.monotonic() - self.envelope_starts.pop(key)
            self.totals[key] = elapsed
        else:
            self.totals[key] = self.totals.get(key, 0) + elapsed
        if pending:
            return
        save(self.root, dict(info, category=self.category, vm=vm.name,
                            seconds=self.totals[key], completed_at=time.time(),
                            includes_preparation=True))

    def finish(self):
        # Runner shutdown is not a case completion. Never publish a partial
        # attempt (including a short preparation phase displayed as 0m).
        self.starts.clear()
        self.envelope_starts.clear()
