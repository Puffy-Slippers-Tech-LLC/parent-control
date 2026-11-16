"""Runner progress contains clear completions, never retained execution claims."""

import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from contextlib import ExitStack

if __package__:
    from .regression_events import completed_cases
    from .test_retention import Store, ensure_directory, private
    from .test_storage import directory
else:
    from regression_events import completed_cases
    from test_retention import Store, ensure_directory, private
    from test_storage import directory

EXCLUDE = 'ONPC_TEST_COMPLETED_CASES'
ONLY = 'ONPC_TEST_RETRY_CASE'
INDEPENDENT_SYSTEM_AREAS = ('authorization', 'enforcement', 'session')
SAVE_INTERVAL = 5


def _copy(value):
    return json.loads(json.dumps(value))


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _clear_cases(values):
    result = set()
    for case in values if isinstance(values, list) else []:
        try:
            result.update(completed_cases(json.dumps([case]), replay_oversized=True))
        except ValueError:
            pass
    return result


def _state_directory(root):
    from test_results import VARIABLE
    selected = os.environ.get(VARIABLE)
    if selected:
        path = Path(selected) / 'checkpoints'
        ensure_directory(path)
        return path
    return directory('state', root=root)


def pass_namespace(scope):
    return 'test-pass-' + hashlib.sha256(scope.encode()).hexdigest()[:24]


def _read_progress(store):
    with store.opened() as fd:
        try:
            source = os.open('current.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(source) as stream:
                private(os.fstat(stream.fileno()), regular=True)
                if os.fstat(stream.fileno()).st_size > 16 * 1024 * 1024:
                    return {}
                value = json.load(stream)
                return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}


class PassCheckpoint:
    """One live coordinator; only clear completed cases survive its lifetime."""

    def __init__(self, root, selection, pool, families, *, resume=False, identity=None, scope='ordinary'):
        self.root, self.selection, self.pool = root, _copy(selection), _copy(pool)
        self.families, self.resume, self.identity = _copy(families), resume, identity
        self.store = Store(_state_directory(root) / pass_namespace(scope))
        self.resources = ExitStack()

    def __enter__(self):
        try:
            return self._open()
        except BaseException:
            self.resources.close()
            raise

    def _open(self):
        from test_results import ResultStore, VARIABLE
        from vm_case_queue import work_key
        ensure_directory(self.store.path)
        self.fd = self.resources.enter_context(self.store.opened())
        self.resources.enter_context(self.store.locked(self.fd, 'gate', blocking=False))
        previous = _read_progress(self.store) if self.resume else {}
        self.results = ResultStore()
        self.state = dict(selection=self.selection, pool=self.pool, run=uuid.uuid4().hex,
                          **{'pass': uuid.uuid4().hex}, families={}, host_passed=[])
        if self.identity:
            self.state.update(self.identity)
        for family, items in self.families.items():
            passed = {}
            saved_work = _mapping(_mapping(previous.get('families')).get(family)).get('completed', [])
            completed = {key for key in saved_work if isinstance(key, str)} if isinstance(saved_work, list) else set()
            scopes = {}
            for work in items:
                key = (work['category'], json.dumps(work['options']))
                scopes.setdefault(key, set()).update(work['cases'])
            for (category, options), cases in scopes.items():
                if cases:
                    self.results.reconcile(category, family, cases, options=json.loads(options))
            for category in dict.fromkeys(work['category'] for work in items):
                current = {case for item in items if item['category'] == category for case in item['cases']}
                saved = _mapping(_mapping(_mapping(previous.get('families')).get(family)).get('passed')).get(category, [])
                clear = _clear_cases(saved)
                if os.environ.get(VARIABLE):
                    clear |= self.results.passed(category, family)
                passed[category] = sorted(clear & current)
            if os.environ.get(VARIABLE):
                for work in items:
                    if not work['cases'] and self.results.complete(work['category'], family, work['options']):
                        completed.add(work_key(work))
            self.state['families'][family] = dict(items={work_key(work): work for work in items},
                                                  passed=passed, claims={}, completed=sorted(completed))
        self.save()
        return self

    def __exit__(self, *_):
        self.resources.close()

    def save(self):
        self.store.save(self.fd, dict(families={family: dict(
            passed=partition['passed'], completed=partition['completed'])
            for family, partition in self.state['families'].items()}))

    def claims(self, family=None):
        return [claim for name, partition in self.state['families'].items()
                if family is None or name == family for claim in partition['claims'].values()]

    def passed(self, family, category):
        return set(self.state['families'][family]['passed'].get(category, []))

    def pending(self, family):
        from vm_case_queue import work_key
        partition = self.state['families'][family]
        active = {work_key(claim['work']) for claim in self.claims(family)}
        return [work for key, work in partition['items'].items()
                if key not in active and key not in partition['completed'] and (not work['cases']
                    or not set(work['cases']) <= self.passed(family, work['category']))]

    def retry(self, family, case, *, area=False):
        for category, passed in self.state['families'][family]['passed'].items():
            self.state['families'][family]['passed'][category] = [
                node for node in passed if node != case
                and not (area and node.partition('::')[0] == case.partition('::')[0])]

    def claim(self, family, vm, work, *, execution=None):
        if any(claim['work']['category'] == work['category']
               and set(claim['work']['cases']) & set(work['cases']) for claim in self.claims(family)):
            return None
        assignment = dict(run=self.state['run'], **{'pass': self.state['pass']},
                          assignment=uuid.uuid4().hex, attempt=uuid.uuid4().hex,
                          family=family, vm=vm, work=_copy(work), execution=_copy(execution or work))
        self.state['families'][family]['claims'][assignment['assignment']] = assignment
        return assignment

    def accept(self, assignment, evidence, status, *, interrupted=False):
        partition = self.state['families'][assignment['family']]
        if not isinstance(evidence, dict):
            partition['claims'].pop(assignment['assignment'], None)
            return
        if (partition['claims'].get(assignment['assignment']) != assignment
                or any(evidence.get(key) != assignment[key]
                       for key in ('run', 'pass', 'assignment', 'attempt', 'family', 'vm'))):
            partition['claims'].pop(assignment['assignment'], None)
            return None
        work = assignment['execution']
        observed = {key: evidence.get(key, []) for key in ('passed', 'failed')}
        if any(not isinstance(values, list) or any(not isinstance(case, str) or case not in work['cases']
               for case in values) for values in observed.values()):
            partition['claims'].pop(assignment['assignment'], None)
            return None
        partition['claims'].pop(assignment['assignment'], None)
        passed, failed = set(observed['passed']), set(observed['failed'])
        current = self.passed(assignment['family'], work['category'])
        partition['passed'][work['category']] = sorted((current | passed) - failed)
        if not work['cases'] and status == 0 and evidence.get('cleanup') is True:
            from vm_case_queue import work_key
            partition['completed'] = sorted(set(partition['completed']) | {work_key(assignment['work'])})
        self.save()
        return (set(work['cases']) <= set(partition['passed'][work['category']])
                if work['cases'] else status == 0 and evidence.get('cleanup') is True)

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
    if any(arg not in ('--resume', '--record') for arg in args):
        return argv
    previous = request_record(root, 'run-tests')
    if not isinstance(previous, dict) or not isinstance(previous.get('argv'), list):
        return argv
    saved, binding = vm_config.extract_selector(previous['argv'])
    return ['--resume', *[arg for arg in args if arg == '--record'],
            *[arg for arg in saved if arg not in ('--resume', '--record')],
            *(['--vm', selector or binding] if selector or binding else [])]


class Checkpoint:
    @staticmethod
    def worker_result(root, binding):
        identity = hashlib.sha256(('run-tests:' + binding).encode()).hexdigest()[:24]
        return _read_progress(Store(_state_directory(root) / ('runner-progress-' + identity))).get('queue_evidence')

    def __init__(self, root, selections, *, resume=False, namespace='run-tests', binding=None):
        from test_commands import CATEGORIES, suite_inventory, AGGREGATES, execution_selections
        from test_results import ResultStore, VARIABLE as RESULTS, REPAIR_QUEUE
        from vm_selection import VARIABLE, vm_config
        self.root = root
        self.executed_passes = {}
        self.collections = {}
        self.retry_case = self.retry_area = None
        self.dirty, self.synced = False, time.monotonic()
        groups = {}
        for kind, args in selections:
            expanded = ([(name, entry['args']) for name, entry in suite_inventory([kind]).items()]
                        if kind in (*AGGREGATES, 'publish') else [(kind, args)])
            for name, options in execution_selections(root, expanded):
                groups.setdefault(name, []).append(list(options))
        logical = {kind: options[0] if len(options) == 1 else options for kind, options in groups.items()}
        self.selected = set(logical)
        vm = any(CATEGORIES[kind].scope == 'vm' for kind in logical if kind in CATEGORIES)
        self.vm = (binding or os.environ.get(VARIABLE, '')) if vm else ''
        self.family = vm_config.load(self.vm).family if self.vm else 'host'
        identity = hashlib.sha256((namespace + ':' + self.vm).encode()).hexdigest()[:24]
        self.store = Store(_state_directory(root) / ('runner-progress-' + identity))
        ensure_directory(self.store.path)
        previous = _read_progress(self.store) if resume and not os.environ.get(RESULTS) else {}
        self.results = ResultStore() if os.environ.get(RESULTS) else None
        self.name = 'current.json'
        self.state = dict(categories={})
        for kind, args in logical.items():
            old = _mapping(previous.get('categories')).get(kind, {})
            if not isinstance(old, dict):
                old = {}
            saved = old.get('passed', [])
            passed = _clear_cases(saved)
            if self.results:
                passed |= self.results.passed(kind, self.family)
                complete = self.results.complete(kind, self.family, args)
                if (self.family == 'host' and not os.environ.get(REPAIR_QUEUE)
                        and any(record['category'] == kind and not record['case']
                                and record.get('options') == args for record in self.results.failures())):
                    # Validate the failed enclosing command, while leaving its
                    # already clear case results intact in the round store.
                    passed, complete = set(), False
            else:
                complete = (old.get('complete') is True and resume and old.get('args') == args
                            and isinstance(saved, list) and len(passed) == len(saved))
            self.state['categories'][kind] = dict(args=args, passed=sorted(passed), complete=complete)
        self.excluded = {kind: self.passed(kind) for kind in self.selected}
        for kind in self.selected:
            self.snapshot(kind)
        self.save()

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
        self.entry(kind)['complete'] = False
        self.entry(kind)['passed'] = sorted(self.passed(kind) - {case})
        self.excluded[kind].discard(case)
        self.snapshot(kind)

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
        return '@' + str(self.store.path / self.snapshot_name(kind))

    def save(self):
        with self.store.opened() as fd:
            self.store.save(fd, self.state, name=self.name)
        self.dirty = False
        self.synced = time.monotonic()

    def event(self, kind, event, failed):
        entry = self.entry(kind)
        if entry is None:
            return
        if event['kind'] == 'collection':
            self.collections.setdefault(kind, set()).update(event.get('nodeids', []))
            self.collections[kind].update(event.get('resumed_nodeids', []))
            return
        nodeid = event.get('nodeid')
        if not isinstance(nodeid, str):
            return
        passed = set(entry['passed'])
        if event['kind'] == 'failure':
            passed.discard(nodeid)
            entry['complete'] = False
            if nodeid in self.excluded[kind]:
                self.excluded[kind].remove(nodeid)
                self.snapshot(kind)
            if os.environ.get('ONPC_TEST_VM_WORKER'):
                print('Runner case failed: ' + json.dumps(dict(category=kind, case=nodeid)), flush=True)
        elif event['kind'] == 'finished' and nodeid not in failed:
            # A legitimate pytest parameter ID can exceed snapshot limits.
            # Leave it queued for replay instead of writing an unreadable state.
            completed = completed_cases(json.dumps([nodeid]), replay_oversized=True)
            if completed <= passed:
                return
            passed.update(completed)
            self.executed_passes.setdefault(kind, set()).update(completed)
        else:
            return
        entry['passed'] = sorted(passed)
        if self.results is not None:
            self.results.record(kind, self.family, nodeid,
                1 if event['kind'] == 'failure' else 0,
                vm=self.vm, options=entry['args'], detail=str(event.get('detail', ''))[-16000:])
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
                if self.results is not None:
                    if kind in self.collections:
                        self.results.reconcile(kind, self.family, self.collections[kind], options=self.entry(kind)['args'])
                    self.results.record(kind, self.family, '', 0, vm=self.vm, options=self.entry(kind)['args'], complete=True)
                    if self.family == 'host':
                        self.results.finish_command(kind, self.entry(kind)['args'], family=self.family)
            elif self.results is not None and any(item.state == 'Failed' for item in items):
                if not any(record['category'] == kind and record['family'] == self.family
                           for record in self.results.failures()):
                    self.results.record(kind, self.family, '', 1, vm=self.vm, options=self.entry(kind)['args'])
        self.save()
