"""Bounded runner progress, separate from reports and repair conversations.

The owning activity lock serializes updates. Only completed, nonfailed cases
can be omitted; an in-flight case is deliberately never committed as passed.
"""

import hashlib
import json
import os
import time

if __package__:
    from .regression_events import completed_cases
    from .test_retention import Store, private, ensure_directory
    from .test_storage import directory
else:
    from regression_events import completed_cases
    from test_retention import Store, private, ensure_directory
    from test_storage import directory

EXCLUDE = 'ONPC_TEST_COMPLETED_CASES'


def request_record(root, namespace, value=None):
    """Remember the latest public selection so bare --resume restores it."""
    if namespace not in ('run-tests', 'fix-tests'):
        raise ValueError('invalid checkpoint namespace')
    path = directory('state', root=root) / (namespace + '-request')
    ensure_directory(path)
    store = Store(path)
    with store.opened() as fd, store.locked(fd, 'gate'):
        if value is not None:
            store.save(fd, value)
            return value
        try:
            source = os.open('current.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            return None
        with os.fdopen(source) as stream:
            private(os.fstat(stream.fileno()), regular=True)
            if os.fstat(stream.fileno()).st_size > 65536:
                raise ValueError('resume request is oversized')
            return json.load(stream)


def resume_arguments(root, argv):
    if '--resume' not in argv or any(arg in ('--help', '-h', '--list', '--stop', '--collect-only') for arg in argv):
        return argv
    from vm_selection import vm_config
    args, selector = vm_config.extract_selector(argv)
    if any(arg not in ('--resume', '--stop-on-error') for arg in args):
        return argv
    previous = request_record(root, 'run-tests')
    if previous is None:
        return argv
    saved, _ = vm_config.extract_selector(previous['argv'])
    if selector is None:
        saved = previous['argv']
    else:
        saved = [*saved, '--vm', selector]
    saved = [arg for arg in saved if arg != '--resume']
    if '--stop-on-error' in args and '--stop-on-error' not in saved:
        saved.insert(0, '--stop-on-error')
    return ['--resume', *saved]


class Checkpoint:
    def __init__(self, root, selections, *, resume=False, namespace='run-tests', binding=None):
        from test_commands import CATEGORIES, suite_inventory, AGGREGATES
        from vm_selection import VARIABLE, BATCH
        groups = {}
        for kind, args in selections:
            if kind in AGGREGATES:
                expanded = [(name, entry['args']) for name, entry in suite_inventory([kind]).items()]
            else:
                expanded = [(kind, args)]
            for name, options in expanded:
                groups.setdefault(name, []).append(list(options))
        # Repeated category groups are valid selections. Retain every group's
        # selectors instead of silently binding resume to only the last one.
        logical = {kind: options[0] if len(options) == 1 else options
                   for kind, options in groups.items()}
        self.children = []
        self.dirty = False
        self.synced = time.monotonic()
        def scope(kind):
            return CATEGORIES[kind].scope if kind in CATEGORIES else 'host'
        host = [(kind, args) for kind, args in logical.items() if scope(kind) == 'host']
        vm = [(kind, args) for kind, args in logical.items() if scope(kind) == 'vm']
        if namespace == 'run-tests' and host and vm:
            self.children = [Checkpoint(root, groups, resume=resume, namespace=namespace, binding=binding)
                             for groups in (host, vm)]
            self.state = dict(version=1, categories={kind: entry for child in self.children
                                                     for kind, entry in child.state['categories'].items()})
            self.selected = set(logical)
            return
        host_only = not vm
        if host_only:
            binding = ''
        elif binding is None:
            binding = os.environ.get(VARIABLE, os.environ.get(BATCH, ''))
        identity = hashlib.sha256(binding.encode()).hexdigest()[:24]
        self.name = 'current.json'
        self.store = Store(directory('state', root=root) /
                           f'{namespace}-{"host" if host_only else "vm"}-{identity}')
        ensure_directory(self.store.path)
        with self.store.opened() as fd:
            try:
                source = os.open(self.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            except FileNotFoundError:
                state = None
            else:
                with os.fdopen(source) as stream:
                    private(os.fstat(stream.fileno()), regular=True)
                    if os.fstat(stream.fileno()).st_size > 16 * 1024 * 1024:
                        raise ValueError('resume checkpoint is oversized')
                    state = json.load(stream) if resume else None
            if resume and state is not None:
                if (not isinstance(state, dict) or state.get('version') != 1
                        or not isinstance(state.get('categories'), dict)
                        or any(not isinstance(entry, dict) or not isinstance(entry.get('args'), list)
                               or not isinstance(entry.get('passed'), list)
                               or type(entry.get('complete')) is not bool
                               for entry in state['categories'].values())):
                    raise ValueError('invalid resume checkpoint')
                if any(kind not in state['categories'] or state['categories'][kind]['args'] != args
                       for kind, args in logical.items()):
                    raise ValueError('resume selection differs from checkpoint; start without --resume to reset it')
                for entry in state['categories'].values():
                    completed_cases(json.dumps(entry['passed']))
                    if type(entry['complete']) is not bool:
                        raise ValueError('invalid resume category state')
                if (type(state.get('round', 1)) is not int or state.get('round', 1) < 1
                        or state.get('pending') not in (None, 'all', *state['categories'])):
                    raise ValueError('invalid resume repair progress')
                self.state = state
            else:
                self.state = dict(version=1, categories={kind: dict(args=args, passed=[], complete=False)
                                                        for kind, args in logical.items()})
                self.store.save(fd, self.state, name=self.name)
        self.selected = set(logical)
        self.excluded = {kind: self.passed(kind) for kind in self.selected}
        for kind in self.selected:
            self.snapshot(kind)

    def entry(self, kind):
        return self.state['categories'].get(kind) if kind in self.selected else None

    def passed(self, kind):
        entry = self.entry(kind)
        return set(entry['passed']) if entry else set()

    def complete(self, kind):
        entry = self.entry(kind)
        return bool(entry and entry['complete'])

    def snapshot_name(self, kind):
        return 'completed-' + hashlib.sha256(kind.encode()).hexdigest()[:24] + '.json'

    def snapshot(self, kind):
        with self.store.opened() as fd:
            try:
                info = os.stat(self.snapshot_name(kind), dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                private(info, regular=True)
            self.store.save(fd, sorted(self.excluded[kind]), name=self.snapshot_name(kind))

    def environment(self, kind):
        if self.children:
            return next(child.environment(kind) for child in self.children if child.entry(kind) is not None)
        return '@' + str(self.store.path / self.snapshot_name(kind))

    def save(self):
        if self.children:
            for child in self.children:
                child.save()
            return
        with self.store.opened() as fd:
            self.store.save(fd, self.state, name=self.name)
        self.dirty = False
        self.synced = time.monotonic()

    def event(self, kind, event, failed):
        if self.children:
            for child in self.children:
                if child.entry(kind) is not None:
                    child.event(kind, event, failed)
            return
        entry = self.entry(kind)
        if entry is None:
            return
        nodeid = event.get('nodeid')
        passed = set(entry['passed'])
        if event['kind'] == 'failure':
            passed.discard(nodeid)
            entry['complete'] = False
            if nodeid in self.excluded[kind]:
                self.excluded[kind].remove(nodeid)
                self.snapshot(kind)
        elif event['kind'] == 'finished' and nodeid not in failed:
            passed.add(nodeid)
        else:
            return
        entry['passed'] = sorted(passed)
        self.dirty = True
        if event['kind'] == 'failure' or time.monotonic() - self.synced >= 1:
            self.save()

    def finish(self, categories):
        for kind in self.selected:
            items = [item for item in categories if item.retry_category == kind and item.count_overall]
            if items and all(item.state == 'Passed' for item in items):
                self.entry(kind)['complete'] = True
        self.save()
