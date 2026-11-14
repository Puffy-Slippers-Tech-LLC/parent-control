"""Local latest VM case timings; no inventory entries or repair-session clocks."""

import ast
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


def _name(category, identifier, vm=None):
    key = json.dumps([category, identifier, vm] if vm is not None else
                     [category, identifier], separators=(',', ':'))
    return 'vm-time-' + hashlib.sha256(key.encode()).hexdigest() + '.json'


def _read(fd, name):
    source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(source) as stream:
        info = os.fstat(stream.fileno())
        test_retention.private(info, regular=True)
        if info.st_size > 256 * 1024:
            raise ValueError('VM timing metadata too large')
        return json.load(stream)


def save(root, record):
    directory = test_storage.directory('state', root=root)
    fd = test_retention.directory(directory)
    temporary = '.vm-time-' + uuid.uuid4().hex
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        test_retention.private(os.fstat(fd))
        name = _name(record['category'], record['id'], record['vm'])
        try:
            _read(fd, name)
        except FileNotFoundError:
            pass
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


def delete(root, record):
    """Remove a published pair's timings, preserving newer runs and recordings."""
    directory = test_storage.directory('state', root=root, create=False)
    fd = test_retention.directory(directory)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        test_retention.private(os.fstat(fd))
        candidates = []
        for name in (_name(record['category'], record['id']),
                     _name(record['category'], record['id'], record['vm'])):
            try:
                before = os.stat(name, dir_fd=fd, follow_symlinks=False)
                saved = _read(fd, name)
            except FileNotFoundError:
                continue
            if any(saved[key] != record[key] for key in ('category', 'id', 'vm')):
                continue  # A legacy record may belong to another VM.
            if saved['completed_at'] > record['completed_at']:
                raise ValueError('Run time changed; refresh the table before deleting it.')
            candidates.append((name, before))
        for name, before in candidates:
            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError('Run time file changed; refresh before deleting it.')
            os.unlink(name, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)


def load(root):
    """Read only logged cases; optional recordings retain their existing owner."""
    try:
        directory = test_storage.directory('state', root=root, create=False)
    except FileNotFoundError:
        return []
    registry = root / 'tests/integration/system_case_ids.py'
    # Watch may display several checkouts at different revisions. Use each
    # checkout's own retirement map, not this process's imported registry.
    identities = runpy.run_path(str(registry)) if registry.is_file() else {}
    unbound = identities.get('UNBOUND_CASES', {})
    titles = {case.numeric_id: case.title for case in identities.get('CASES', ())}
    catalogue = descriptions(root)
    fd = test_retention.directory(directory)
    rows = []
    try:
        test_retention.private(os.fstat(fd))
        for name in os.listdir(fd):
            if not name.startswith('vm-time-') or not name.endswith('.json'):
                continue
            try:
                record = _read(fd, name)
                from tools.recording_storage import case_identity
                if (record['category'] not in ('system', 'e2e')
                        or not case_identity(record['id'])
                        or name not in (_name(record['category'], record['id']),
                                        _name(record['category'], record['id'], record['vm']))
                        or not isinstance(record['seconds'], (float, int))
                        or not math.isfinite(record['seconds']) or record['seconds'] < 0
                        or type(record['completed_at']) not in (float, int)
                        or not math.isfinite(record['completed_at'])
                        or any(not isinstance(record[key], str) for key in
                               ('title', 'case_file', 'description', 'vm'))):
                    raise ValueError('Invalid VM timing record')
                if (record['category'] == 'system' and
                        unbound.get(record['id'], (None,))[0] == 'retired'):
                    # Consolidated cases no longer appear as tiny standalone
                    # work. Preserve their stored history and recordings.
                    continue
                current = catalogue.get((record['category'], record['id']), {})
                if record.get('execution_revision', 1) != current.get('execution_revision', 1):
                    # A former fragment is not a measurement or recording of
                    # the new combined history. Retain its files as history.
                    continue
                if record['category'] == 'system' and record['id'] in titles:
                    record['title'] = titles[record['id']]
                path = root / record['case_file']
                if (path.resolve() != path or not path.is_relative_to(root.resolve() / 'tests')
                        or not path.is_file()):
                    continue
                record['case_link'] = path.as_uri()
                record['recording'] = None
                from tools.recording_storage import Store
                try:
                    with Store(root=root, create=False).vm_owner(
                            record['category'], record['id'], record['vm']) as owner:
                        current = owner.state['current']
                        if current and record['vm'] in owner.state['provenance'].get('vm_names', []):
                            # Validate identity without hashing video bytes on every refresh.
                            video = owner._open(current, missing=True)
                            if video is not None:
                                os.close(video)
                                record['recording'] = (owner.store.path / current['name']).as_uri()
                                # Older clocks began at pytest start, after VM
                                # preparation. The retained clip supplies a
                                # lower bound without rewriting saved history.
                                duration = owner.state['provenance'].get('duration_seconds')
                                if (not record.get('includes_preparation')
                                        and type(duration) in (int, float)
                                        and math.isfinite(duration) and duration >= 0):
                                    record['seconds'] = max(record['seconds'], duration)
                except (OSError, ValueError):
                    pass
                rows.append(describe_case(record, catalogue))
            except (OSError, ValueError, KeyError, TypeError):
                continue
    finally:
        os.close(fd)
    # Legacy per-case records remain readable without rewriting saved history.
    latest = {}
    for row in rows:
        key = row['category'], row['id'], row['vm']
        if key not in latest or row['completed_at'] >= latest[key]['completed_at']:
            latest[key] = row
    return sorted(latest.values(), key=lambda row: (-row['seconds'], row['title'], row['vm']))


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
