"""Bounded runner progress, separate from reports and repair conversations.

The owning activity lock serializes updates. Only completed, nonfailed cases
can be omitted; an in-flight case is deliberately never committed as passed.
"""

import hashlib
import json
import os
from pathlib import Path
import sys
import time
import re
import shlex
import stat

if __package__:
    from .regression_events import completed_cases
    from .test_retention import Store, private, ensure_directory
    from .test_storage import directory
else:
    from regression_events import completed_cases
    from test_retention import Store, private, ensure_directory
    from test_storage import directory

EXCLUDE = 'ONPC_TEST_COMPLETED_CASES'
ONLY = 'ONPC_TEST_RETRY_CASE'
INDEPENDENT_SYSTEM_AREAS = ('authorization', 'enforcement', 'session')
SAVE_INTERVAL = 5
RESUME_SELECTION_MISMATCH = 'resume selection differs from checkpoint; start without --resume to reset it'
SCHEDULING_VERSION = 1
SCHEDULING_IMPLEMENTATION = 'pipeline-v1'


def scheduling_marker():
    return dict(version=SCHEDULING_VERSION, implementation=SCHEDULING_IMPLEMENTATION)


def admit_scheduling_state(state):
    """Admit only this implementation, without translating ownership or credit.

    Markerless records belong to the one immediately preceding pipeline format.
    Adding its explicit marker is lossless: selection, family passes, claims,
    source owners, transaction references and charged admissions stay verbatim.
    A replacement must supply a separately reviewed lossless translation or
    refuse; changing this constant must never silently adopt markerless records.
    Impact-based admission changes the implementation contract too: a missing or
    stale impact decision must remain a hold, never an implicit isolated failure.
    """
    if not isinstance(state, dict):
        raise ValueError('invalid scheduling state')
    # The legacy identity is intentionally literal, independent of the current
    # implementation constants. A future cutover cannot relabel old records.
    marker = state.get('scheduling', dict(version=1, implementation='pipeline-v1'))
    if (not isinstance(marker, dict) or set(marker) != {'version', 'implementation'}
            or type(marker.get('version')) is not int
            or marker != scheduling_marker()
            or 'version' in state and (type(state['version']) is not int or state['version'] != 1)):
        original = marker.get('implementation') if isinstance(marker, dict) else None
        raise ValueError('incompatible scheduling state'
                         + (f' ({original})' if isinstance(original, str) else '')
                         + '; finish retained repair/Git transactions with the original supported '
                         'implementation before switching, or use the existing --reset recovery '
                         'contract only when abandonment is explicitly authorized')
    return dict(state, scheduling=dict(marker))


def _read_scheduling_record(path):
    """Read existing private metadata without creating or rewriting anything."""
    try:
        source = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(source) as stream:
        info = os.fstat(stream.fileno())
        # Launcher JSON uses the caller's umask inside its private run directory;
        # progress Store files separately enforce their stricter 0600 contract.
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_mode & 0o7113):
            raise ValueError('unsafe scheduling metadata ownership or mode')
        if info.st_size > 16 * 1024 * 1024:
            raise ValueError('scheduling record is oversized')
        value = json.load(stream)
        if value is None:
            raise ValueError('invalid scheduling record')
        return value


def guard_scheduling_run(run):
    """Preflight a repair allocation before retention, copying or execution.

    Callers hold its existing workflow ownership. This reader neither adopts a
    source fence nor grants recovery authority; their native ownership guards
    still apply. It accepts only current pipeline records and never starts a
    historical scheduler. The returned marker may be published as scheduling.json
    after all preflight succeeds. Other records remain in their native formats.
    """
    run = Path(run)
    marker = _read_scheduling_record(run / 'scheduling.json')
    admit_scheduling_state({} if marker is None else {'scheduling': marker})
    allocations = [run, *sorted(run.glob('pipeline-*'))]
    for allocation in allocations:
        if allocation.is_symlink():
            raise ValueError('retained scheduling allocation contains a symlink')
        if not allocation.is_dir():
            continue
        nested = _read_scheduling_record(allocation / 'scheduling.json')
        if nested is not None:
            admit_scheduling_state({'scheduling': nested})
        state = _read_scheduling_record(allocation / 'checkpoint.json')
        if state is not None:
            admit_scheduling_state(state)
            if not isinstance(state.get('repairs'), dict):
                raise ValueError('invalid retained repair checkpoint')
        limits = _read_scheduling_record(allocation / 'limits.json')
        if limits is not None:
            admit_scheduling_state(limits)
            if (any(type(limits.get(key)) is not int or limits[key] < 0
                    for key in ('started', 'completed'))
                    or limits.get('tasks') is not None
                    and (type(limits['tasks']) is not int or limits['tasks'] < 1)):
                raise ValueError('invalid retained task admissions')
        for name in ('vm.json', 'pipeline.json', 'repair-source-resume.json', 'repair-pending.json'):
            value = _read_scheduling_record(allocation / name)
            if value is not None:
                admit_scheduling_state(value)
        waiting = _read_scheduling_record(allocation / 'repair-queue.json')
        if waiting is not None and (not isinstance(waiting, list)
                                   or any(not isinstance(ticket, str) for ticket in waiting)):
            raise ValueError('invalid retained repair queue')
    pipelines = _read_scheduling_record(run / 'pipelines.json')
    if pipelines is not None:
        admit_scheduling_state(pipelines)
        if any(not isinstance(value, dict) for key, value in pipelines.items() if key != 'scheduling'):
            raise ValueError('invalid retained pipeline state')
    families = run / 'family-cases'
    if families.is_symlink():
        raise ValueError('retained family queues contain a symlink')
    for path in sorted(families.glob('*.json')):
        state = _read_scheduling_record(path)
        admit_scheduling_state(state)
        if (state.get('version') != 1 or not isinstance(state.get('completed'), list)
                or not isinstance(state.get('claims'), dict) or not isinstance(state.get('items'), dict)):
            raise ValueError('invalid retained family case queue')
    return scheduling_marker()


def guard_scheduling_checkpoints(root):
    """Check all participating progress formats before any scope is reset.

    Mixed host/VM selections and family queues create several checkpoints. A
    later incompatible scope must refuse before an earlier scope is rewritten.
    Request records and unrelated workflow state are deliberately not progress.
    """
    try:
        path = directory('state', root=root, create=False)
    except FileNotFoundError:
        return
    for candidate in sorted(path.iterdir()):
        if not re.fullmatch(r'(?:run-tests(?:-family)?|fix-tests)-(?:host|vm)-[0-9a-f]{24}', candidate.name):
            continue
        state = _read_scheduling_record(candidate / 'current.json')
        if state is not None:
            admit_scheduling_state(state)
            if state.get('version') != 1 or not isinstance(state.get('categories'), dict):
                raise ValueError('invalid resume checkpoint')


def family_claims_pending(root, vm_name):
    """Inspect retained ownership without changing queue progress or VM state."""
    return _family_claims(root, vm_name, recover=False)


def recover_family_claims(root, vm_name):
    """Return interrupted work to pending after maintained VM cleanup.

    The caller holds that VM's reservation and has verified its cleanup. No
    case gains completion credit; unresolved work can run again safely.
    """
    return _family_claims(root, vm_name, recover=True)


def _family_claims(root, vm_name, *, recover):
    import test_activity
    from vm_case_queue import work_key
    def read(store, fd):
        try:
            source = os.open('current.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            return None
        with os.fdopen(source) as stream:
            private(os.fstat(stream.fileno()), regular=True)
            if os.fstat(stream.fileno()).st_size > 16 * 1024 * 1024:
                raise ValueError('family queue recovery checkpoint is oversized')
            state = json.load(stream)
        state = admit_scheduling_state(state)
        if (not isinstance(state, dict) or state.get('version') != 1
                or not isinstance(state.get('categories'), dict)
                or not isinstance(state.get('queue_completed', []), list)
                or any(not isinstance(value, str) for value in state.get('queue_completed', []))):
            raise ValueError('invalid retained family case progress')
        for entry in state['categories'].values():
            if (not isinstance(entry, dict) or not isinstance(entry.get('args'), list)
                    or not isinstance(entry.get('passed'), list) or type(entry.get('complete')) is not bool):
                raise ValueError('invalid retained family case progress')
            completed_cases(json.dumps(entry['passed']))
        claims, items = state.get('queue_claims', {}), state.get('queue_items', {})
        if not isinstance(claims, dict) or not isinstance(items, dict):
            raise ValueError('invalid retained family case claims')
        for key, owner in claims.items():
            item = items.get(key)
            if (not isinstance(key, str) or not isinstance(owner, str) or not isinstance(item, dict)
                    or not {'category', 'case', 'cases', 'options', 'area'} <= item.keys()
                    or not isinstance(item['category'], str) or item['category'] not in state['categories']
                    or not isinstance(item['cases'], list) or not isinstance(item['options'], list)
                    or any(not isinstance(value, str) for value in (*item['cases'], *item['options']))
                    or type(item['area']) is not bool
                    or (item['case'] is not None and item['case'] not in item['cases'])
                    or work_key(item) != key):
                raise ValueError('invalid retained family case claims')
        return state

    guard_scheduling_checkpoints(root)
    paths = [path for path in directory('state', root=root).glob('run-tests-family-vm-*')
             if re.fullmatch(r'run-tests-family-vm-[0-9a-f]{24}', path.name)]
    candidates = []
    for path in paths:
        store = Store(path)
        with store.opened() as fd:
            state = read(store, fd)
            if state is not None and vm_name in state.get('queue_claims', {}).values():
                candidates.append(path)
    if not recover or not candidates:
        return len(candidates)
    recovered = 0
    with test_activity.exclusive_vm_progress():
        for path in candidates:
            store = Store(path)
            with store.opened() as fd:
                state = read(store, fd)
                if state is None:
                    continue
                claims = state.get('queue_claims', {})
                owned = [key for key, owner in claims.items() if owner == vm_name]
                for key in owned:
                    item = state['queue_items'][key]
                    category = state['categories'][item['category']]
                    category['passed'] = [case for case in category['passed'] if case != item['case']]
                    category['complete'] = False
                    state['queue_completed'] = [value for value in state.get('queue_completed', []) if value != key]
                    del claims[key]
                    recovered += 1
                if owned:
                    store.save(fd, state, name='current.json')
    return recovered


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


def incompatible_resume(previous):
    return ValueError('new parameters are not compatible with --resume; previous parameters: '
                      + shlex.join(previous))


def compatible_vm(selector, previous):
    """Compare registry identities without acquiring or operating any VM."""
    from vm_selection import vm_config
    if previous is None:
        return False
    configured = vm_config.registry()
    def names(value):
        if value in ('all', 'all-enabled'):
            return {vm.name for vm in vm_config.execution(value)[1]}
        return {vm_config.resolve(token, configured).name for token in value.split(',')}
    try:
        return names(selector) == names(previous)
    except ValueError:
        return False


def compatible_arguments(supplied, saved):
    """Compare repeated arguments in groups, inheriting omitted saved arguments."""
    def normalized(values):
        return [part for value in values for part in
                (value.split('=', 1) if value.startswith('--') and '=' in value
                 and not value.startswith('--ignore=') else [value])]
    supplied, saved = normalized(supplied), normalized(saved)
    for flag in ('--stop-on-error', '--reverse'):
        if flag in supplied and flag not in saved:
            return False
    supplied = [arg for arg in supplied if arg not in ('--stop-on-error', '--reverse')]
    saved = [arg for arg in saved if arg not in ('--stop-on-error', '--reverse')]
    if not supplied:
        return True
    if saved and saved[0] in ('unit', 'component', 'ui'):
        from test_launcher import _arguments
        category = saved[0]
        if not supplied[0].startswith('-'):
            if supplied[0] != category:
                return False
            supplied = supplied[1:]
        ignores = [arg for arg in supplied if arg.startswith('--ignore=')]
        old_ignores = [arg for arg in saved if arg.startswith('--ignore=')]
        if ignores and set(ignores) != set(old_ignores):
            return False
        supplied = [arg for arg in supplied if not arg.startswith('--ignore=')]
        try:
            targets, options, timeout = _arguments(supplied, category)
            old_targets, old_options, old_timeout = _arguments(
                [arg for arg in saved[1:] if not arg.startswith('--ignore=')], category)
        except ValueError:
            return False
        keys = {option.partition('=')[0] for option in options}
        return (((targets == [f'tests/{category}'] and f'tests/{category}' not in supplied)
                 or targets == old_targets)
                and (timeout is None or timeout == old_timeout)
                and all([option for option in options if option.partition('=')[0] == key]
                        == [option for option in old_options if option.partition('=')[0] == key]
                        for key in keys))
    # Check each repeated option together with its values, never token membership
    # (which could accept a value belonging to a different option).
    def groups(values):
        result = [[]]
        for token in values:
            if token.startswith('-'):
                result.append([])
            result[-1].append(token)
        return result
    supplied, saved = groups(supplied), groups(saved)
    return (saved[0][:len(supplied[0])] == supplied[0]
            and all(any(old[:len(group)] == group for old in saved[1:])
                    and all(old[:len(group)] == group for old in saved[1:] if old[0] == group[0])
                    for group in supplied[1:]))


def resume_arguments(root, argv):
    if '--resume' not in argv or any(arg in ('--help', '-h', '--list', '--stop', '--collect-only') for arg in argv):
        return argv
    from vm_selection import vm_config
    args, selector = vm_config.extract_selector(argv)
    previous = request_record(root, 'run-tests')
    if previous is None:
        return argv
    saved, binding = vm_config.extract_selector(previous['argv'])
    controls = [arg for arg in args if arg in ('--resume-case-only', '--resume-area-only')
                or arg.startswith('--resume-case=')]
    supplied = [arg for arg in args if arg not in ('--resume', *controls)]
    saved = [arg for arg in saved if arg != '--resume']
    if (not compatible_arguments(supplied, saved)
            or selector is not None and not compatible_vm(selector, binding)):
        raise incompatible_resume(previous['argv'])
    return ['--resume', *saved, *controls, *(['--vm', binding] if binding is not None else [])]


class Checkpoint:
    def __init__(self, root, selections, *, resume=False, namespace='run-tests', binding=None,
                 recover_missing=False):
        from test_commands import CATEGORIES, suite_inventory, AGGREGATES, execution_selections
        from vm_selection import VARIABLE, BATCH
        groups = {}
        unexpanded = []
        self.retry_case = None
        self.retry_area = None
        for kind, args in selections:
            if kind in (*AGGREGATES, 'publish'):
                expanded = [(name, entry['args']) for name, entry in suite_inventory([kind]).items()]
            else:
                expanded = [(kind, args)]
            unexpanded.extend(expanded)
            for name, options in execution_selections(root, expanded):
                groups.setdefault(name, []).append(list(options))
        # Repeated category groups are valid selections. Retain every group's
        # selectors instead of silently binding resume to only the last one.
        logical = {kind: options[0] if len(options) == 1 else options
                   for kind, options in groups.items()}
        whole_system = [(kind, args) for kind, args in unexpanded
                        if kind == 'system'] == [('system', [])]
        def new_entry(kind, args):
            entry = dict(args=args, passed=[], complete=False)
            if kind == 'system':
                entry['whole_inventory'] = whole_system
            return entry
        self.children = []
        self.dirty = False
        self.synced = time.monotonic()
        def scope(kind):
            return CATEGORIES[kind].scope if kind in CATEGORIES else 'host'
        host = [(kind, args) for kind, args in logical.items() if scope(kind) == 'host']
        vm = [(kind, args) for kind, args in logical.items() if scope(kind) == 'vm']
        if recover_missing and (not resume or namespace != 'run-tests' or host
                                or len(logical) != 1 or not binding):
            raise ValueError('missing-category recovery requires one bound VM category on resume')
        if namespace == 'run-tests' and host and vm:
            guard_scheduling_checkpoints(root)
            self.children = [Checkpoint(root, [(kind, args) for kind, args in unexpanded
                                               if scope(kind) == target],
                                        resume=resume, namespace=namespace, binding=binding)
                             for target in ('host', 'vm')]
            self.state = admit_scheduling_state(dict(version=1, categories={
                kind: entry for child in self.children for kind, entry in child.state['categories'].items()}))
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
                    # Even a fresh selection must inspect the retained format
                    # before replacing its records.
                    retained = json.load(stream)
                    state = admit_scheduling_state(retained)
                    self.dirty = 'scheduling' not in retained
            if state is not None:
                if (not isinstance(state, dict) or state.get('version') != 1
                        or not isinstance(state.get('categories'), dict)
                        or any(not isinstance(entry, dict) or not isinstance(entry.get('args'), list)
                               or not isinstance(entry.get('passed'), list)
                               or type(entry.get('complete')) is not bool
                               for entry in state['categories'].values())):
                    raise ValueError('invalid resume checkpoint')
                for entry in state['categories'].values():
                    passed = completed_cases(json.dumps(entry['passed']), replay_oversized=True)
                    if len(passed) != len(entry['passed']):
                        # Older writers could persist pytest's oversized generated
                        # parameter IDs. Replay only those cases; retain all other
                        # passes and never certify the category from partial state.
                        entry['passed'] = sorted(passed)
                        entry['complete'] = False
                        self.dirty = True
                    if type(entry['complete']) is not bool:
                        raise ValueError('invalid resume category state')
                if (type(state.get('round', 1)) is not int or state.get('round', 1) < 1
                        or state.get('pending') not in (None, 'all', *state['categories'])
                        or any('whole_inventory' in entry and type(entry['whole_inventory']) is not bool
                               for entry in state['categories'].values())):
                    raise ValueError('invalid resume repair progress')
                # Only fully validated state can identify a different selection.
                # Repair launchers may replay that selection from scratch, but
                # malformed progress must retain its refusal and evidence.
                additions = False
                if resume and whole_system and 'system' in state['categories']:
                    entry = state['categories']['system']
                    old = entry['args']
                    current = groups['system']
                    provenance = entry.get('whole_inventory')
                    old_groups = [old] if len(old) == 1 and isinstance(old[0], str) else old
                    # Whole-system requests may gain standalone checks, while
                    # lifecycle selectors and retained ordering stay unchanged.
                    additions = (provenance is True and bool(old_groups) and old != logical['system']
                                 and all(isinstance(item, list) and item in current for item in old_groups)
                                 and [item for item in current if item in old_groups] == old_groups
                                 and all(len(item) == 1 and isinstance(item[0], str)
                                         and re.fullmatch(r'check_[a-z][a-z0-9_]*', item[0])
                                         for item in current if item not in old_groups)
                                 and len(old_groups) < len(current))
                if resume and any((kind not in state['categories'] and not recover_missing)
                       or (kind in state['categories'] and state['categories'][kind]['args'] != args
                           and not (kind == 'system' and additions))
                       for kind, args in logical.items()):
                    raise ValueError(RESUME_SELECTION_MISMATCH)
                if resume and 'system' in logical and 'system' in state['categories']:
                    # Isolated launcher workers expose tools/, not the tests package.
                    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/integration'))
                    try:
                        from system_case_ids import UNBOUND_CASES, identity_for_event
                    finally:
                        sys.path.pop(0)
                    entry = state['categories']['system']
                    retired = {node for node in entry['passed']
                               if (identity := identity_for_event(node)) is not None
                               and UNBOUND_CASES.get(identity.numeric_id, (None,))[0] == 'retired'}
                    if retired:
                        # Retired results cannot certify their replacement cases.
                        # Keep valid passes and unknown IDs for the inventory guard,
                        # and let current unfinished work run under its own identity.
                        entry.update(passed=sorted(set(entry['passed']) - retired), complete=False)
                        self.dirty = True
                        print(f'run-tests: removed {len(retired)} explicitly retired system results '
                              'from resume progress; current unfinished cases remain pending.', flush=True)
                if additions:
                    state['categories']['system'].update(args=logical['system'], complete=False,
                                                        whole_inventory=True)
                    self.dirty = True
                if namespace == 'run-tests':
                    if not resume:
                        # Attempt/round metadata belongs to the execution being
                        # reset, unlike other categories' retained case passes.
                        state = admit_scheduling_state(dict(version=1, categories=state['categories']))
                    for kind, args in logical.items():
                        if not resume or kind not in state['categories']:
                            # Reset only requested categories. A diagnostic in
                            # another suite must not erase this suite's passes.
                            state['categories'][kind] = new_entry(kind, args)
                            state.pop('queue_attempt', None)
                            self.dirty = True
                            if resume:
                                print(f'fix-tests: missing {kind} runner checkpoint; replaying '
                                      'unfinished work without saved passes; other categories retained.',
                                      flush=True)
                if namespace == 'run-tests-family':
                    claims = state.get('queue_claims', {})
                    if (not isinstance(claims, dict) or any(not isinstance(key, str)
                            or not isinstance(owner, str) for key, owner in claims.items())):
                        raise ValueError('invalid retained family case claims')
                    if not resume:
                        if claims:
                            raise ValueError('family cases remain claimed; use --resume with the original '
                                             'selection to finish or recover their VM owners before a fresh run')
                        state = admit_scheduling_state(dict(version=1, categories={
                            kind: new_entry(kind, args) for kind, args in logical.items()}))
                        self.dirty = True
                if not resume and namespace not in ('run-tests', 'run-tests-family'):
                    state = admit_scheduling_state(dict(version=1, categories={
                        kind: new_entry(kind, args) for kind, args in logical.items()}))
                    self.dirty = True
                self.state = state
                if self.dirty:
                    self.store.save(fd, self.state, name=self.name)
                    self.dirty = False
            else:
                self.state = admit_scheduling_state(dict(version=1, categories={
                    kind: new_entry(kind, args) for kind, args in logical.items()}))
                self.store.save(fd, self.state, name=self.name)
        self.selected = set(logical)
        self.excluded = {kind: self.passed(kind) for kind in self.selected}
        # Repair-run failures are omitted from execution, never awarded pass credit.
        omitted = json.loads(os.environ.get('ONPC_REPAIR_FAILED_CASES', '{}'))
        for kind in self.selected:
            self.excluded[kind].update(completed_cases(json.dumps(omitted.get(kind, []))))
        for kind in self.selected:
            self.snapshot(kind)
        self.synced = time.monotonic()

    def entry(self, kind):
        return self.state['categories'].get(kind) if kind in self.selected else None

    def retry(self, kind, case, *, area=False):
        completed_cases(json.dumps([case]))
        if self.selected != {kind}:
            raise ValueError('case retry requires one category')
        phase = case.partition('::')[0]
        if area and (kind != 'system' or phase not in INDEPENDENT_SYSTEM_AREAS):
            raise ValueError('area retry requires an independent system area')
        self.retry_case = case
        self.retry_area = phase if area else None
        self.event(kind, dict(kind='failure', nodeid=case), set())

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
            # A legitimate pytest parameter ID can exceed snapshot limits.
            # Leave it queued for replay instead of writing an unreadable state.
            completed = completed_cases(json.dumps([nodeid]), replay_oversized=True)
            if completed <= passed:
                return
            passed.update(completed)
        else:
            return
        entry['passed'] = sorted(passed)
        self.dirty = True
        # This is a full inventory rewrite plus file/directory synchronization.
        # Batch routine passes like the report, rather than turning fast unit
        # completions into a sustained stream of growing durable snapshots.
        # Failure and finalization still save all pending progress immediately.
        if event['kind'] == 'failure' or time.monotonic() - self.synced >= SAVE_INTERVAL:
            self.save()

    def finish(self, categories):
        for kind in self.selected:
            items = [item for item in categories if item.retry_category == kind and item.count_overall]
            if not self.retry_case and items and all(item.state == 'Passed' for item in items):
                self.entry(kind)['complete'] = True
        self.save()
