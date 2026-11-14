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
import uuid
from contextlib import ExitStack, contextmanager

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
PASS_NAMESPACE = 'run-tests-pass'
PASS_NAMESPACES = {'ordinary': PASS_NAMESPACE,
                   'repair-host': PASS_NAMESPACE + '-repair-host',
                   'repair-vm': PASS_NAMESPACE + '-repair-vm'}
PASS_MARKER = dict(version=1, implementation='ordinary-pass-v1')


def pass_namespace(scope):
    base, separator, group = scope.partition('/')
    if base not in PASS_NAMESPACES or separator and not re.fullmatch(
            r'[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)?', group):
        raise ValueError('invalid pass checkpoint scope')
    return PASS_NAMESPACES[base] + ('--' + group if separator else '')


def pass_namespaces(root):
    """Include retained group owners even after an inventory entry is removed."""
    result = dict(PASS_NAMESPACES)
    path = directory('state', root=root)
    for candidate in path.iterdir():
        for base, namespace in PASS_NAMESPACES.items():
            if candidate.name.startswith(namespace + '--'):
                scope = base + '/' + candidate.name[len(namespace) + 2:]
                if pass_namespace(scope) == candidate.name:
                    result[scope] = candidate.name
    return result


def _copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _pass_work(work):
    if (not isinstance(work, dict)
            or not {'category', 'options', 'cases', 'case', 'area'} <= work.keys()
            or not isinstance(work['category'], str) or not work['category']
            or not isinstance(work['options'], list)
            or any(not isinstance(value, str) for value in work['options'])
            or not isinstance(work['cases'], list)
            or type(work['area']) is not bool
            or work['case'] is not None and work['case'] not in work['cases']):
        raise ValueError('invalid pass work')
    completed_cases(json.dumps(work['cases']))


def _pass_execution(assignment):
    work = assignment['work']
    execution = assignment.get('execution', work)
    _pass_work(execution)
    if (execution['category'] != work['category'] or execution['options'] != work['options']
            or not set(execution['cases']) <= set(work['cases'])):
        raise ValueError('focused execution is outside its original assignment')
    if execution != work and execution['area'] and (
            work['category'] != 'system' or execution['case'].partition('::')[0] not in INDEPENDENT_SYSTEM_AREAS):
        raise ValueError('area retry requires an independent system area')
    return execution


def _impact_source(source):
    if (not isinstance(source, dict) or not isinstance(source.get('digest'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', source['digest'])
            or type(source.get('generation')) is not int or source['generation'] < 0):
        raise ValueError('invalid repair impact source/input identity')


def _repair_execution(ticket, execution):
    _pass_work(execution)
    if any(execution[field] != ticket['work'][field] for field in ('category', 'options')):
        raise ValueError('repair target is outside the original selected work')
    case_based = bool(ticket['work']['cases']) or ticket['work']['category'] in (
        'unit', 'component', 'ui', 'fixture-runtime')
    if case_based and (len(execution['cases']) != 1 or execution['area']
                       or execution['case'] != execution['cases'][0]):
        raise ValueError('bounded repair requires one exact case')


def validate_impact_decision(decision):
    """Validate bounded triage; isolation requires positive scoped evidence."""
    if (not isinstance(decision, dict)
            or set(decision) != {'impact', 'reason', 'scope', 'evidence', 'classification'}
            or decision['impact'] not in ('yes', 'no', 'unsure')
            or decision['classification'] not in ('test_issue', 'app_issue', 'uncertain')
            or not isinstance(decision['reason'], str) or not decision['reason'].strip()
            or len(decision['reason']) > 4000
            or any(not isinstance(decision[field], list) or len(decision[field]) > 32
                   or any(not isinstance(value, str) or not value.strip() or len(value) > 2000
                          for value in decision[field]) for field in ('scope', 'evidence'))
            or decision['impact'] == 'no' and (not decision['scope'] or not decision['evidence'])):
        raise ValueError('invalid repair impact decision; no requires positive scoped evidence')
    return _copy(decision)


def _repair_impact(ticket):
    """Optional triage is untrusted until its complete binding is validated."""
    impact = ticket.get('impact')
    try:
        if (not isinstance(impact, dict)
                or set(impact) != {'ticket', 'attempt', 'source', 'evidence_digest', 'decision'}
                or impact['ticket'] != ticket['id'] or impact['attempt'] != ticket['attempt']
                or not isinstance(impact['evidence_digest'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', impact['evidence_digest'])):
            return None
        _impact_source(impact['source'])
        validate_impact_decision(impact['decision'])
    except ValueError:
        return None
    return impact


def _repair_tickets(state):
    """Validate optional failure records without creating another completion ledger."""
    from vm_case_queue import work_key
    tickets = state.get('repairs', [])
    if not isinstance(tickets, list):
        raise ValueError('invalid ordinary pass repair FIFO')
    assignments = {identity for partition in state['families'].values()
                   for collection in ('claims', 'completed')
                   for assignment in partition[collection].values()
                   for identity in (assignment['assignment'], assignment['attempt'])}
    issued = {state['run'], state['pass'], *assignments}
    failures = set()
    required = {'id', 'transaction', 'run', 'pass', 'selection', 'family', 'vm', 'work',
                'assignment', 'attempt', 'source', 'case', 'status', 'cleanup'}
    for ticket in tickets:
        if (not isinstance(ticket, dict) or not required <= ticket.keys()
                or set(ticket) - required - {'execution', 'impact', 'attempts', 'outcome', 'repair_ref', 'resolution'}):
            raise ValueError('invalid ordinary pass repair ticket')
        for field in ('id', 'transaction', 'assignment', 'attempt'):
            if not isinstance(ticket[field], str) or not re.fullmatch(r'[0-9a-f]{32}', ticket[field]):
                raise ValueError('invalid ordinary pass repair identity')
        if (ticket['id'] in issued or ticket['transaction'] in issued
                or ticket['id'] == ticket['transaction']
                or ticket['assignment'] == ticket['attempt']
                or {ticket['assignment'], ticket['attempt']} & {state['run'], state['pass']}
                or {ticket['id'], ticket['transaction']} & {ticket['assignment'], ticket['attempt']}):
            raise ValueError('duplicate ordinary pass repair identity')
        issued.update((ticket['id'], ticket['transaction']))
        if not isinstance(ticket['family'], str) or not isinstance(ticket['vm'], str):
            raise ValueError('invalid ordinary pass repair family or VM')
        partition = state['families'].get(ticket['family'], {})
        _pass_work(ticket['work'])
        host = ticket['family'] == '' and ticket['vm'] == ''
        if (ticket['run'] != state['run'] or ticket['pass'] != state['pass']
                or ticket['selection'] != state['selection']
                or not host and (state['pool'].get(ticket['vm']) != ticket['family']
                    or partition.get('items', {}).get(work_key(ticket['work'])) != ticket['work'])
                or not ticket['source'] or not isinstance(ticket['source'], (str, dict))
                or type(ticket['status']) is not int or not ticket['status']
                or type(ticket['cleanup']) is not bool):
            raise ValueError('invalid ordinary pass repair assignment')
        execution = _pass_execution(ticket)
        if (set(ticket['work']) != {'category', 'options', 'cases', 'case', 'area'}
                or set(execution) != {'category', 'options', 'cases', 'case', 'area'}
                or ticket['case'] is not None and (not isinstance(ticket['case'], str)
                                                  or ticket['case'] not in execution['cases'])
                or ticket['case'] is None and execution['cases']):
            raise ValueError('repair failure is outside its original execution')
        failure = (ticket['assignment'], ticket['attempt'], ticket['case'])
        if failure in failures:
            raise ValueError('duplicate ordinary pass repair failure')
        failures.add(failure)
        for attempt in ticket.get('attempts', []):
            if (not isinstance(attempt, dict)
                    or set(attempt) != {'ticket', 'attempt', 'purpose', 'source', 'execution',
                                       'status', 'accepted'}
                    or attempt['ticket'] != ticket['id']
                    or not isinstance(attempt['attempt'], str)
                    or not re.fullmatch(r'[0-9a-f]{32}', attempt['attempt'])
                    or attempt['purpose'] not in ('recheck', 'diagnostic', 'verification')
                    or type(attempt['accepted']) is not bool
                    or attempt['accepted'] and (attempt['status'] != 0 or attempt['purpose'] == 'diagnostic')
                    or attempt['status'] is not None and type(attempt['status']) is not int):
                raise ValueError('invalid bounded repair attempt reference')
            _impact_source(attempt['source'])
            _repair_execution(ticket, attempt['execution'])
        if ticket.get('outcome') not in (None, 'resolved', 'leave_failed', 'suspended'):
            raise ValueError('invalid repair outcome')
        if ticket.get('outcome') == 'resolved':
            reference = ticket.get('resolution')
            if (not isinstance(reference, dict) or reference not in ticket.get('attempts', [])
                    or reference.get('accepted') is not True
                    or reference.get('purpose') == 'verification' and not ticket.get('repair_ref')):
                raise ValueError('resolved repair lacks its accepted attempt or close-out reference')
        if 'repair_ref' in ticket and (not isinstance(ticket['repair_ref'], str)
                or not Path(ticket['repair_ref']).is_absolute()):
            raise ValueError('invalid repair continuation reference')
        # Retain invalid optional triage for diagnosis; it cannot authorize
        # isolation because impact() validates the full envelope on every read.
    return tickets


class GroupCheckpoint:
    """Sequential group cursor and admissions; case credit stays in PassCheckpoint."""

    def __init__(self, root, groups, pool, *, resume=False, identity=None, scope='ordinary',
                 ungrouped_selection=None):
        self.root, self.groups, self.pool = root, _copy(groups), sorted(pool)
        for group in self.groups:
            group['vms'].sort()
        self.resume, self.identity, self.scope = resume, identity, scope
        self.ungrouped_selection = ungrouped_selection
        self.store = Store(directory('state', root=root) / (PASS_NAMESPACES[scope] + '-groups'))
        self.resources = ExitStack()

    @staticmethod
    def validate(state, *, scope=None):
        if (not isinstance(state, dict) or set(state) - {'ungrouped'} != {
                'version', 'scope', 'run', 'pass', 'groups', 'pool', 'workers', 'outcomes'}
                or 'ungrouped' in state and (state['ungrouped'] is not True
                    or not isinstance(state.get('groups'), list) or len(state['groups']) != 1)
                or type(state['version']) is not int or state['version'] != 1
                or not isinstance(state['scope'], str) or state['scope'] not in PASS_NAMESPACES
                or scope is not None and state['scope'] != scope
                or any(not isinstance(state[key], str) or not re.fullmatch(r'[0-9a-f]{32}', state[key])
                       for key in ('run', 'pass')) or state['run'] == state['pass']
                or not isinstance(state['groups'], list) or not state['groups']
                or not isinstance(state['pool'], list)
                or any(not isinstance(name, str) or not name for name in state['pool'])
                or len(state['pool']) != len(set(state['pool']))
                or any(not isinstance(state[key], list) or len(state[key]) != len(state['groups'])
                       for key in ('workers', 'outcomes'))):
            raise ValueError('invalid sequential test group checkpoint')
        keys = set()
        for group, workers, outcome in zip(state['groups'], state['workers'], state['outcomes'], strict=True):
            if (not isinstance(group, dict) or set(group) != {'key', 'category', 'args', 'vm_tag', 'vms'}
                    or not isinstance(group['key'], str) or group['key'] in keys
                    or not re.fullmatch(r'[a-z0-9.-]+', group['key'])
                    or not isinstance(group['category'], str)
                    or not isinstance(group['args'], list)
                    or any(not isinstance(arg, str) for arg in group['args'])
                    or group['vm_tag'] is not None and (not isinstance(group['vm_tag'], str)
                        or not re.fullmatch(r'[a-z0-9-]+', group['vm_tag']))
                    or not isinstance(group['vms'], list)
                    or any(not isinstance(name, str) or name not in state['pool'] for name in group['vms'])
                    or workers is not None and (not isinstance(workers, list)
                        or any(not isinstance(name, str) or name not in group['vms'] for name in workers)
                        or len(workers) != len(set(workers))
                        or bool(group['vms']) != bool(workers))
                    or outcome is not None and (not isinstance(outcome, dict)
                        or set(outcome) != {'status', 'source_changed', 'terminal_failed'}
                        or type(outcome['status']) is not int or outcome['status'] not in (0, 1)
                        or any(type(outcome[key]) is not bool for key in ('source_changed', 'terminal_failed'))
                        or workers is None)):
                raise ValueError('invalid sequential test group entry')
            keys.add(group['key'])

    def __enter__(self):
        try:
            ensure_directory(self.store.path)
            self.fd = self.resources.enter_context(self.store.opened())
            self.resources.enter_context(self.store.locked(self.fd, 'gate', blocking=False))
            previous = _read_scheduling_record('current.json', strict=True, dir_fd=self.fd)
            if previous is not None:
                self.validate(previous, scope=self.scope)
            if previous is not None and self.resume:
                def selection(groups):
                    return [{key: value for key, value in group.items() if key != 'vms'}
                            for group in groups]
                if (selection(previous['groups']) != selection(self.groups)
                        or not set(self.pool) <= set(previous['pool'])
                        or self.identity is not None and self.identity != {
                            key: previous[key] for key in ('run', 'pass')}):
                    raise ValueError(RESUME_SELECTION_MISMATCH)
                self.state = previous
                # Unentered groups have no admission or case ownership to
                # preserve. Refresh their eligible candidates within the
                # original allowed pool before a future admission is saved.
                for index, group in enumerate(self.groups):
                    if self.state['workers'][index] is None:
                        self.state['groups'][index]['vms'] = group['vms']
                self.save()
            else:
                ungrouped = False
                if previous is None and self.resume and self.identity is not None:
                    with PassCheckpoint.saved(self.root, scope=self.scope) as saved:
                        if saved is not None:
                            if (len(self.groups) != 1
                                    or self.identity != {key: saved.state[key] for key in ('run', 'pass')}
                                    or self.ungrouped_selection != saved.state['selection']
                                    or self.pool != sorted(saved.state['pool'])
                                    or self.groups[0]['vms'] != self.pool):
                                raise ValueError(RESUME_SELECTION_MISMATCH)
                            ungrouped = True
                for scope in pass_namespaces(self.root):
                    if scope == self.scope or scope.startswith(self.scope + '/'):
                        if ungrouped and scope == self.scope:
                            continue  # Keep the original validated case/repair owner.
                        with PassCheckpoint.saved(self.root, scope=scope) as saved:
                            if saved is not None and (saved.claims() or saved.repair_tickets()):
                                raise ValueError('test group has unfinished owners; use --resume or owned recovery')
                self.state = dict(version=1, scope=self.scope, run=uuid.uuid4().hex, **{'pass': uuid.uuid4().hex},
                    groups=self.groups, pool=self.pool, workers=[None] * len(self.groups),
                    outcomes=[None] * len(self.groups))
                if self.identity is not None:
                    self.state.update(self.identity)
                if ungrouped:
                    self.state.update(ungrouped=True, workers=[self.pool])
                self.save()
            return self
        except BaseException:
            self.resources.close()
            raise

    def __exit__(self, *_):
        self.resources.close()

    def save(self):
        self.validate(self.state, scope=self.scope)
        self.store.save(self.fd, self.state)

    def group_identity(self, index):
        if self.state.get('ungrouped'):
            return {key: self.state[key] for key in ('run', 'pass')}
        return dict(run=self.state['run'], **{'pass': uuid.uuid5(
            uuid.UUID(self.state['pass']), self.groups[index]['key']).hex})

    def group_scope(self, index):
        return self.scope if self.state.get('ungrouped') else self.scope + '/' + self.groups[index]['key']


class PassCheckpoint:
    """One group's case-credit record, held exclusively until its pass exits.

    Reports and VM checkpoints are bounded attempt evidence. Only accept()
    grants family credit, and recovery only relinquishes an original claim.
    Legacy pipeline/repair progress keeps its original format and authority.
    """

    def __init__(self, root, selection, pool, families, *, resume=False, identity=None,
                 scope='ordinary'):
        self.root = root
        self.selection = _copy(selection)
        self.pool = _copy(pool)
        self.families = _copy(families)
        self.resume = resume
        if not isinstance(scope, str):
            raise ValueError('invalid ordinary pass checkpoint scope')
        self.scope = scope
        if identity is not None and (not isinstance(identity, dict) or set(identity) != {'run', 'pass'}
                or any(not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{32}', value)
                       for value in identity.values()) or identity['run'] == identity['pass']):
            raise ValueError('invalid requested pass identity')
        self.identity = identity
        self.store = Store(directory('state', root=root) / pass_namespace(scope))
        self._lifetime = None
        self.fd = None

    @staticmethod
    def validate(state, *, scope=None):
        from vm_case_queue import work_key
        def token(value):
            return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{32}', value)
        if (not isinstance(state, dict) or type(state.get('version')) is not int or state['version'] != 1
                or state.get('scheduling') != PASS_MARKER
                or type(state['scheduling'].get('version')) is not int):
            raise ValueError('incompatible ordinary pass state; finish with its original supported '
                             'implementation or use the existing explicitly authorized --reset contract')
        if (not isinstance(state.get('scope', 'ordinary'), str)
                or not pass_namespace(state.get('scope', 'ordinary'))
                or scope is not None and state.get('scope', 'ordinary') != scope
                or not token(state.get('run')) or not token(state.get('pass'))
                or state['run'] == state['pass']
                or not isinstance(state.get('selection'), list)
                or any(not isinstance(group, list) or len(group) != 2
                       or not isinstance(group[0], str) or not isinstance(group[1], list)
                       or any(not isinstance(arg, str) for arg in group[1]) for group in state['selection'])
                or not isinstance(state.get('pool'), dict)
                or any(not isinstance(vm, str) or not vm or not isinstance(family, str) or not family
                       for vm, family in state['pool'].items())
                or type(state.get('host_complete')) is not bool
                or not isinstance(state.get('host_passed', []), list)
                or any(not isinstance(kind, str) for kind in state.get('host_passed', []))
                or not isinstance(state.get('families'), dict)
                or set(state['families']) != set(state['pool'].values())):
            raise ValueError('invalid ordinary pass identity or selection')
        issued, workers = {state['run'], state['pass']}, set()
        for family, partition in state['families'].items():
            if (not isinstance(partition, dict) or not isinstance(partition.get('items'), dict)
                    or not isinstance(partition.get('order'), list)
                    or any(not isinstance(key, str) for key in partition['order'])
                    or len(set(partition['order'])) != len(partition['order'])
                    or set(partition['order']) != set(partition['items'])
                    or not isinstance(partition.get('claims'), dict)
                    or not isinstance(partition.get('completed'), dict)
                    or any(not isinstance(key, str) for key in partition['completed'])
                    or not set(partition['completed']) <= set(partition['items'])
                    or not isinstance(partition.get('passed'), dict)):
                raise ValueError('invalid ordinary pass family partition')
            inventory = {}
            retired = partition.get('retired', [])
            if (not isinstance(retired, list) or not set(retired) <= set(partition['items'])
                    or any(not isinstance(key, str) for key in retired)):
                raise ValueError('invalid retired ordinary pass work')
            for key, work in partition['items'].items():
                _pass_work(work)
                if work_key(work) != key:
                    raise ValueError('invalid ordinary pass work identity')
                inventory.setdefault(work['category'], set()).update([] if key in retired else work['cases'])
            for category, passed in partition['passed'].items():
                if category not in inventory or not completed_cases(json.dumps(passed)) <= inventory[category]:
                    raise ValueError('ordinary pass credit is outside its inventory')
            for key, receipt in partition['completed'].items():
                work = partition['items'][key]
                if (not isinstance(receipt, dict) or receipt.get('run') != state['run']
                        or receipt.get('pass') != state['pass'] or receipt.get('selection') != state['selection']
                        or receipt.get('family') != family or state['pool'].get(receipt.get('vm')) != family
                        or receipt.get('work') != work or not token(receipt.get('assignment'))
                        or not token(receipt.get('attempt')) or not receipt.get('source')
                        or not isinstance(receipt['source'], (str, dict))
                        or receipt.get('cleanup') is not True or receipt.get('diagnostic') is not False
                        or type(receipt.get('status')) is not int or receipt['status'] != 0
                        or completed_cases(json.dumps(receipt.get('passed'))) != set(_pass_execution(receipt)['cases'])
                        or not set(receipt['passed']) <= set(partition['passed'].get(work['category'], []))):
                    raise ValueError('ordinary pass completion lacks case evidence')
                if (receipt['assignment'] in issued or receipt['attempt'] in issued
                        or receipt['assignment'] == receipt['attempt']):
                    raise ValueError('duplicate ordinary pass completion identity')
                issued.update((receipt['assignment'], receipt['attempt']))
            active = set()
            for key, assignment in partition['claims'].items():
                if (key not in partition['items']
                        or not isinstance(assignment, dict)
                        or assignment.get('run') != state['run'] or assignment.get('pass') != state['pass']
                        or assignment.get('selection') != state['selection']
                        or assignment.get('family') != family
                        or state['pool'].get(assignment.get('vm')) != family
                        or assignment.get('work') != partition['items'][key]
                        or not token(assignment.get('assignment')) or not token(assignment.get('attempt'))
                        or assignment['assignment'] in issued or assignment['attempt'] in issued
                        or assignment['assignment'] == assignment['attempt']
                        or assignment['vm'] in workers
                        or not assignment.get('source')
                        or not isinstance(assignment['source'], (str, dict))):
                    raise ValueError('invalid ordinary pass claim identity')
                _pass_execution(assignment)
                identities = {(assignment['work']['category'], case) for case in assignment['work']['cases']}
                if active & identities:
                    raise ValueError('overlapping ordinary pass claims')
                active.update(identities)
                issued.update((assignment['assignment'], assignment['attempt']))
                workers.add(assignment['vm'])
        _repair_tickets(state)
        return state

    def _open(self):
        if self._lifetime is not None:
            raise ValueError('ordinary pass coordinator is already open')
        ensure_directory(self.store.path)
        lifetime = ExitStack()
        try:
            self.fd = lifetime.enter_context(self.store.opened())
            lifetime.enter_context(self.store.locked(self.fd, 'gate', blocking=False))
            state = _read_scheduling_record('current.json', strict=True, dir_fd=self.fd)
            if state is not None:
                self.validate(state, scope=self.scope)
            self._lifetime = lifetime
            return state
        except BaseException:
            lifetime.close()
            self.fd = None
            raise

    def __enter__(self):
        from vm_case_queue import work_key
        state = self._open()
        try:
            # Do not silently adopt another scheduler's accepted progress. Fresh
            # ordinary passes may leave settled historical family records alone.
            guard_scheduling_checkpoints(self.root)
            if self.identity is not None:
                for scope, namespace in pass_namespaces(self.root).items():
                    if scope == self.scope:
                        continue
                    previous = _read_scheduling_record(
                        directory('state', root=self.root) / namespace / 'current.json', strict=True)
                    if previous is not None and self.identity == {
                            key: previous[key] for key in ('run', 'pass')}:
                        raise ValueError('requested pass identity belongs to another checkpoint scope; '
                                         'resume its original supported workflow')
            for path in directory('state', root=self.root).glob('run-tests-family-vm-*'):
                previous = _read_scheduling_record(path / 'current.json')
                if previous and (set(previous.get('queue_claims', {}).values()) & set(self.pool)
                        or self.resume and state is None
                        and (previous.get('queue_completed') or any(
                            entry.get('passed') or entry.get('complete')
                            for entry in previous.get('categories', {}).values()))):
                    raise ValueError('retained pipeline family progress requires the original supported '
                                     'implementation; finish its VM owners or use the existing '
                                     'explicitly authorized --reset recovery contract')
            partitions = {family: dict(order=list(dict.fromkeys(work_key(work) for work in items)),
                                      items={work_key(work): work for work in items},
                                      claims={}, completed={}, passed={})
                          for family, items in self.families.items()}
            fresh = dict(version=1, scheduling=dict(PASS_MARKER), run=uuid.uuid4().hex,
                         **{'pass': uuid.uuid4().hex}, selection=self.selection, pool=self.pool,
                         host_complete=False, families=partitions, scope=self.scope)
            if self.identity is not None:
                fresh.update(self.identity)
            self.validate(fresh)
            if state is not None and self.resume:
                if self.identity is not None and self.identity != {key: state[key] for key in ('run', 'pass')}:
                    raise ValueError('saved pass identity differs from the selected run')
                if state['selection'] != self.selection or state['pool'] != self.pool:
                    raise ValueError(RESUME_SELECTION_MISMATCH)
                for family, partition in partitions.items():
                    previous = state['families'][family]
                    if previous['order'] != partition['order'] or previous['items'] != partition['items']:
                        self._resume_inventory(previous, partition, state.get('repairs', []))
                self.state = state
                self.save()
            else:
                if state is not None and any(ticket.get('outcome') not in ('resolved', 'leave_failed')
                                              for ticket in state.get('repairs', [])):
                    raise ValueError('ordinary pass has pending repairs; use --resume to preserve their transactions')
                if state is not None and any(partition['claims'] for partition in state['families'].values()):
                    raise ValueError('ordinary pass has uncertain claims; use --resume or recover their original VM owners')
                self.state = fresh
                self.save()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self._lifetime is not None:
            self._lifetime.close()
            self._lifetime = None
            self.fd = None

    def _resume_inventory(self, previous, current, repairs=()):
        """Retain qualified cases across the existing narrow inventory changes."""
        from vm_case_queue import work_key
        from test_commands import selections
        groups = [group for kind, args in self.selection
                  for group in (selections(self.root, args) if kind == '_guest' else [(kind, args)])]
        whole_system = [args for kind, args in groups if kind == 'system'] == [[]]
        # Registry retirement and the failed ticket's own changed identities
        # permit bounded replacement. Unrelated missing work still refuses.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/integration'))
        try:
            from system_case_ids import UNBOUND_CASES, identity_for_event
        finally:
            sys.path.pop(0)
        retired = {case for work in previous['items'].values() if work['category'] == 'system'
                   for case in work['cases']
                   if (identity := identity_for_event(case)) is not None
                   and UNBOUND_CASES.get(identity.numeric_id, (None,))[0] == 'retired'}
        failed = [ticket['work'] for ticket in repairs if ticket['family']
                  and ticket.get('outcome') not in ('resolved', 'leave_failed')
                  and work_key(ticket['work']) in previous['items']]
        def same_selection(left, right):
            return all(left[field] == right[field] for field in ('category', 'options'))
        def selected_cases(work):
            return {case for item in current['items'].values() if same_selection(item, work)
                    for case in item['cases']}
        keys, translated = [], {}
        for key in previous['order']:
            if key in previous.get('retired', []):
                continue
            work = previous['items'][key]
            missing = {case for ticket in failed if same_selection(ticket, work)
                       for case in ticket['cases'] if case not in selected_cases(work)}
            cases = [case for case in work['cases'] if case not in retired | missing]
            changed = cases != work['cases']
            if changed and not cases:
                continue
            item = dict(work, cases=cases, case=(cases[-1] if work['case'] in retired | missing else work['case']))
            mapped = work_key(item)
            if current['items'].get(mapped) != item:
                replacement = next((candidate for candidate in current['items'].values()
                    if work in failed and same_selection(candidate, work)
                    and set(cases) <= set(candidate['cases'])), None)
                if replacement is None:
                    raise ValueError('resume pass inventory differs from checkpoint; original selection required')
                mapped = work_key(replacement)
            if mapped not in keys:
                keys.append(mapped)
            translated[key] = mapped
        additions = [work for key, work in current['items'].items() if key not in keys]
        if ([key for key in current['order'] if key in keys] != keys
                or any(not any(same_selection(work, ticket) for ticket in failed)
                       and (not whole_system or work['category'] != 'system'
                            or len(work['cases']) != 1
                            or not re.fullmatch(r'check_[a-z][a-z0-9_]*', work['cases'][0]))
                       for work in additions)):
            raise ValueError('resume pass inventory differs from checkpoint; original selection required')
        current['claims'] = previous['claims']
        current['passed'] = {category: sorted(set(passed) & {case for work in current['items'].values()
                                                           if work['category'] == category for case in work['cases']})
                             for category, passed in previous['passed'].items()}
        current['completed'] = {}
        for key, receipt in previous['completed'].items():
            if key in translated:
                # Retired cases lose credit; the original assignment receipt
                # must not be rewritten to claim a different execution.
                if translated[key] == key:
                    current['completed'][key] = receipt
        # Keep immutable ownership records for removed cases until their original
        # worker and repair transaction finish. They are never normal work or credit.
        retained = set(previous['claims']) | {work_key(ticket['work']) for ticket in repairs
                    if ticket['family'] and work_key(ticket['work']) in previous['items']}
        for key in previous['order']:
            if key in retained and key not in current['items']:
                current['items'][key] = previous['items'][key]
                current['order'].append(key)
                current.setdefault('retired', []).append(key)
        previous.update(current)

    @classmethod
    @contextmanager
    def saved(cls, root, *, scope='ordinary'):
        """Open retained claims for maintained recovery, under the same gate."""
        checkpoint = cls(root, [], {}, {}, scope=scope)
        try:
            checkpoint.state = checkpoint._open()
            yield checkpoint if checkpoint.state is not None else None
        finally:
            checkpoint.__exit__(None, None, None)

    def save(self):
        if self.fd is None:
            raise ValueError('ordinary pass requires exclusive coordinator ownership')
        self.validate(self.state, scope=self.scope)
        self.store.save(self.fd, self.state)

    def claims(self, family=None):
        return [_copy(assignment) for name, partition in self.state['families'].items()
                if family is None or family == name for assignment in partition['claims'].values()]

    def passed(self, family, category):
        return set(self.state['families'][family]['passed'].get(category, []))

    def pending(self, family):
        partition = self.state['families'][family]
        active = {(assignment['work']['category'], case) for assignment in partition['claims'].values()
                  for case in assignment['work']['cases']}
        return [_copy(partition['items'][key]) for key in partition['order']
                if key not in partition['claims'] and key not in partition.get('retired', [])
                and (partition['items'][key]['cases'] or key not in partition['completed'])
                and not (partition['items'][key]['cases']
                         and set(partition['items'][key]['cases']) <= self.passed(
                             family, partition['items'][key]['category']))
                and not active & {(partition['items'][key]['category'], case)
                                  for case in partition['items'][key]['cases']}]

    def retry(self, family, case, *, area=False):
        partition = self.state['families'][family]
        matches = [work for work in partition['items'].values() if case in work['cases']]
        if not matches:
            raise ValueError('case retry is outside the selected family inventory')
        if area and (case.partition('::')[0] not in INDEPENDENT_SYSTEM_AREAS
                     or any(work['category'] != 'system' for work in matches)):
            raise ValueError('area retry requires an independent system area')
        for work in matches:
            category = work['category']
            partition['passed'][category] = sorted(self.passed(family, category) - {case})
        partition['completed'] = {key: receipt for key, receipt in partition['completed'].items()
                                  if case not in receipt['passed']}
        self.save()

    def claim(self, family, vm, work, source, *, execution=None):
        from vm_case_queue import work_key
        if self.state['pool'].get(vm) != family:
            raise ValueError('VM is outside the ordinary pass family pool')
        if any(assignment['vm'] == vm for assignment in self.claims()):
            return None
        if not source or not isinstance(source, (str, dict)):
            raise ValueError('invalid ordinary pass source/input identity')
        if work not in self.pending(family):
            return None
        assignment = dict(run=self.state['run'], **{'pass': self.state['pass']},
                          assignment=uuid.uuid4().hex, attempt=uuid.uuid4().hex, vm=vm,
                          family=family, selection=_copy(self.state['selection']),
                          work=_copy(work), source=_copy(source))
        if execution is not None:
            assignment['execution'] = _copy(execution)
            _pass_execution(assignment)
        self.state['families'][family]['claims'][work_key(work)] = assignment
        self.save()
        return _copy(assignment)

    def _claimed(self, assignment):
        from vm_case_queue import work_key
        if not isinstance(assignment, dict):
            raise ValueError('invalid ordinary pass assignment')
        partition = self.state['families'].get(assignment.get('family'), {})
        work = assignment.get('work')
        key = work_key(work)
        if partition.get('claims', {}).get(key) != assignment:
            raise ValueError('stale or mismatched ordinary pass assignment')
        return partition, key

    def repair_tickets(self):
        """Return failures in observed order, independent of family completion."""
        return _copy([ticket for ticket in self.state.get('repairs', [])
                      if ticket.get('outcome') not in ('resolved', 'leave_failed')])

    def host_failure(self, work, source, status, *, case=None):
        """Record one bounded host operation without inventing VM ownership."""
        _pass_work(work)
        _impact_source(source)
        if type(status) is not int or not status:
            raise ValueError('host failure requires a failing status')
        ticket = dict(id=uuid.uuid4().hex, transaction=uuid.uuid4().hex,
                      run=self.state['run'], **{'pass': self.state['pass']},
                      selection=_copy(self.selection), family='', vm='', work=_copy(work),
                      assignment=uuid.uuid4().hex, attempt=uuid.uuid4().hex,
                      source=_copy(source), case=case, status=status, cleanup=True)
        candidate = _copy(self.state)
        candidate.setdefault('repairs', []).append(ticket)
        self.validate(candidate)
        self.state = candidate
        self.save()
        return _copy(ticket)

    def begin_attempt(self, ticket_id, purpose, source, execution, *, selected_cases=None):
        if purpose not in ('recheck', 'diagnostic', 'verification'):
            raise ValueError('invalid bounded repair purpose')
        ticket = self._repair_ticket(ticket_id)
        if ticket.get('outcome') in ('resolved', 'leave_failed'):
            raise ValueError('repair ticket is already settled')
        _impact_source(source)
        _repair_execution(ticket, execution)
        if ticket['family']:
            partition = self.state['families'][ticket['family']]
            selected_cases = {case for key, work in partition['items'].items()
                              if key not in partition.get('retired', [])
                              and all(work[field] == execution[field] for field in ('category', 'options'))
                              for case in work['cases']}
        if execution['cases'] and (selected_cases is None
                and not set(execution['cases']) <= set(ticket['work']['cases'])
                or selected_cases is not None and not set(execution['cases']) <= set(selected_cases)):
            raise ValueError('repair target is outside the current original selection')
        reference = dict(ticket=ticket_id, attempt=uuid.uuid4().hex, purpose=purpose,
                         source=_copy(source), execution=_copy(execution), status=None, accepted=False)
        ticket.setdefault('attempts', []).append(reference)
        self.save()
        return _copy(reference)

    def finish_attempt(self, ticket_id, reference, evidence, status, *, source):
        ticket = self._repair_ticket(ticket_id)
        attempt = next((value for value in ticket.get('attempts', [])
                        if value['attempt'] == reference.get('attempt')), None)
        if attempt != reference or type(status) is not int:
            raise ValueError('stale bounded repair attempt')
        execution = attempt['execution']
        expected = {field: ticket[field] for field in (
            'run', 'pass', 'selection', 'family', 'vm', 'work', 'assignment')}
        expected.update(attempt=attempt['attempt'], source=attempt['source'], execution=execution)
        qualified = (isinstance(evidence, dict) and evidence.get('cleanup') is True
                     and evidence.get('diagnostic') is False
                     # VM controllers execute captured inputs. Their receipt
                     # stays bound to those inputs, not a later checkout.
                     and (bool(ticket['vm']) or source == attempt['source'])
                     and all(evidence.get(field) == value for field, value in expected.items())
                     and set(execution['cases']) == completed_cases(json.dumps(evidence.get('passed', []))))
        attempt.update(status=status, accepted=bool(not status and qualified
                                                   and attempt['purpose'] != 'diagnostic'))
        self.save()
        return _copy(attempt)

    def settle_repair(self, ticket_id, outcome, *, reference=None, repair_ref=None):
        ticket = self._repair_ticket(ticket_id)
        if outcome not in ('resolved', 'leave_failed', 'suspended'):
            raise ValueError('invalid repair outcome')
        if outcome == 'resolved' and not any(value == reference and value['accepted']
                for value in ticket.get('attempts', [])):
            raise ValueError('resolution requires an accepted bounded attempt')
        if outcome == 'resolved' and reference['purpose'] == 'verification' and repair_ref is None:
            raise ValueError('verified resolution requires completed repair close-out reference')
        ticket['outcome'] = outcome
        if outcome == 'resolved':
            ticket['resolution'] = _copy(reference)
        if repair_ref is not None:
            ticket['repair_ref'] = repair_ref
        if outcome == 'resolved' and ticket['family']:
            from vm_case_queue import work_key
            partition = self.state['families'][ticket['family']]
            work = next((work for key, work in partition['items'].items()
                         if key not in partition.get('retired', [])
                         and all(work[field] == reference['execution'][field] for field in ('category', 'options'))
                         and set(reference['execution']['cases']) <= set(work['cases'])), None)
            if work is None:
                raise ValueError('resolved repair target is no longer selected')
            partition['passed'][work['category']] = sorted(self.passed(
                ticket['family'], work['category']) | set(reference['execution']['cases']))
            receipt = {field: _copy(ticket[field]) for field in (
                'run', 'pass', 'selection', 'family', 'vm', 'work', 'assignment')}
            receipt.update(work=_copy(work), attempt=reference['attempt'], source=reference['source'],
                execution=reference['execution'], passed=reference['execution']['cases'],
                cleanup=True, diagnostic=False, status=0)
            partition['completed'][work_key(work)] = receipt
            original_key = work_key(ticket['work'])
            original = partition['claims'].get(original_key)
            if original is not None and original['assignment'] == ticket['assignment']:
                del partition['claims'][original_key]
        self.save()
        return _copy(ticket)

    def enqueue_failure(self, assignment, evidence, status, *, case=None):
        """Persist an exact claimed failure before its source reader is released.

        Only identity, original selectors and bounded result metadata survive;
        subprocess commands and arbitrary report payloads are never copied.
        This records no acceptance and does not release the original VM claim.
        """
        self._claimed(assignment)
        execution = _pass_execution(assignment)
        if (type(status) is not int or not status or not isinstance(evidence, dict)
                or any(evidence.get(field) != value for field, value in assignment.items())
                or evidence.get('diagnostic') is not False
                or type(evidence.get('cleanup')) is not bool
                or not isinstance(evidence.get('passed'), list)
                or not completed_cases(json.dumps(evidence['passed'])) <= set(execution['cases'])):
            raise ValueError('missing, stale, mismatched or diagnostic repair failure evidence')
        case = execution['case'] if case is None else case
        for ticket in self.state.get('repairs', []):
            if (ticket['assignment'], ticket['attempt'], ticket['case']) == (
                    assignment['assignment'], assignment['attempt'], case):
                if ticket['status'] != status or ticket['cleanup'] != evidence['cleanup']:
                    raise ValueError('mismatched repeated repair failure evidence')
                return _copy(ticket)
        fields = ('run', 'pass', 'selection', 'family', 'vm', 'work',
                  'assignment', 'attempt', 'source', 'execution')
        ticket = {field: _copy(assignment[field]) for field in fields if field in assignment}
        ticket.update(id=uuid.uuid4().hex, transaction=uuid.uuid4().hex, case=case,
                      status=status, cleanup=evidence['cleanup'])
        candidate = _copy(self.state)
        candidate.setdefault('repairs', []).append(ticket)
        self.validate(candidate)
        self.state = candidate
        self.save()
        return _copy(ticket)

    def _repair_ticket(self, ticket_id):
        for ticket in self.state.get('repairs', []):
            if ticket['id'] == ticket_id:
                return ticket
        raise ValueError('unknown ordinary pass repair ticket')

    def record_impact(self, ticket_id, decision, *, source, evidence_digest):
        """Bind triage to current source/inputs, without changing failed identity."""
        ticket = self._repair_ticket(ticket_id)
        _impact_source(source)
        validate_impact_decision(decision)
        if not isinstance(evidence_digest, str) or not re.fullmatch(r'[0-9a-f]{64}', evidence_digest):
            raise ValueError('invalid repair impact evidence digest')
        impact = dict(ticket=ticket_id, attempt=ticket['attempt'], source=_copy(source),
                      evidence_digest=evidence_digest, decision=_copy(decision))
        candidate = _copy(self.state)
        next(value for value in candidate['repairs'] if value['id'] == ticket_id)['impact'] = impact
        self.validate(candidate)
        self.state = candidate
        self.save()
        return _copy(impact)

    def impact(self, ticket_id, *, source, evidence_digest):
        """Missing or changed triage always keeps the admission decision unsure."""
        ticket = self._repair_ticket(ticket_id)
        impact = _repair_impact(ticket)
        try:
            _impact_source(source)
        except ValueError:
            source = None
        if (source is not None and impact is not None and impact['ticket'] == ticket_id
                and impact['attempt'] == ticket['attempt'] and impact['source'] == source
                and impact['evidence_digest'] == evidence_digest):
            return _copy(impact['decision'])
        return dict(impact='unsure', reason='Impact triage is missing or stale.',
                    scope=[], evidence=[], classification='uncertain')

    def accept(self, assignment, evidence, status, *, interrupted=False):
        partition, key = self._claimed(assignment)
        if (type(status) is not int or not isinstance(evidence, dict)
                or any(evidence.get(field) != value for field, value in assignment.items())
                or evidence.get('diagnostic') is not False
                or type(evidence.get('cleanup')) is not bool
                or not isinstance(evidence.get('passed'), list)):
            raise ValueError('missing, stale, mismatched or diagnostic ordinary pass evidence')
        passed = completed_cases(json.dumps(evidence['passed']))
        if interrupted and (status != 130 or evidence.get('failed')):
            raise ValueError('interrupted evidence cannot conceal a failure or grant an attempt pass')
        work = assignment['work']
        execution = _pass_execution(assignment)
        if not passed <= set(execution['cases']):
            raise ValueError('ordinary pass evidence is outside its assigned work')
        # A late audit/teardown failure accepts no new credit and leaves the
        # original claim intact for maintained original-VM recovery.
        if not evidence['cleanup']:
            return False
        retained = self.passed(assignment['family'], work['category'])
        if status and not interrupted:
            passed.discard(execution['case'])
            retained.discard(execution['case'])
            partition['completed'] = {candidate: receipt for candidate, receipt in partition['completed'].items()
                                      if receipt['work']['category'] != work['category']
                                      or execution['case'] not in receipt['passed']}
        elif not status and not set(execution['cases']) <= passed | retained:
            raise ValueError('successful ordinary pass attempt lacks teardown-complete case evidence')
        partition['passed'][work['category']] = sorted(retained | passed)
        if not status:
            partition['completed'][key] = dict(evidence, status=status, passed=sorted(set(execution['cases'])))
            del partition['claims'][key]
        self.save()
        return status == 0

    def recover(self, assignment, *, cleanup):
        partition, key = self._claimed(assignment)
        if cleanup is not True:
            raise ValueError('ordinary pass recovery requires successful original VM cleanup')
        del partition['claims'][key]
        self.save()


def scheduling_marker():
    return dict(version=SCHEDULING_VERSION, implementation=SCHEDULING_IMPLEMENTATION)


def repair_scheduling_marker():
    return dict(version=2, implementation='repair-shared-v1')


def admit_repair_scheduling_state(state):
    """Refuse old repair rounds and charges without reinterpreting their records."""
    if (not isinstance(state, dict)
            or state.get('scheduling') != repair_scheduling_marker()
            or type(state['scheduling'].get('version')) is not int):
        raise ValueError('incompatible repair scheduling state; finish retained repair/Git '
                         'transactions with the original supported implementation before switching, '
                         'or use the existing --reset recovery contract only when abandonment '
                         'is explicitly authorized')
    return dict(state, scheduling=repair_scheduling_marker())


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


def _read_scheduling_record(path, *, strict=False, dir_fd=None):
    """Read existing private metadata without creating or rewriting anything."""
    try:
        source = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    except FileNotFoundError:
        return None
    with os.fdopen(source) as stream:
        info = os.fstat(stream.fileno())
        if strict:
            private(info, regular=True)
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
    """Validate an ordinary runner allocation without adopting repair state."""
    run = Path(run)
    # Repair journals never enter through the ordinary bounded-worker format,
    # even when a caller accidentally uses this general preflight boundary.
    repair_paths = [*run.glob('pipeline-*'), *(run / name for name in (
        'checkpoint.json', 'pipelines.json', 'family-cases', 'pipeline.json',
        'repair-queue.json', 'repair-pending.json', 'repair-source-resume.json'))]
    if any(path.exists() or path.is_symlink() for path in repair_paths):
        return guard_repair_scheduling_run(run)
    marker = _read_scheduling_record(run / 'scheduling.json')
    admit_scheduling_state({} if marker is None else {'scheduling': marker})
    limits = _read_scheduling_record(run / 'limits.json')
    if limits is not None:
        admit_scheduling_state(limits)
        if (any(type(limits.get(key)) is not int or limits[key] < 0
                for key in ('started', 'completed'))
                or limits.get('tasks') is not None
                and (type(limits['tasks']) is not int or limits['tasks'] < 1)):
            raise ValueError('invalid retained task admissions')
    return scheduling_marker()


def guard_repair_scheduling_run(run):
    """Preflight a repair allocation before retention, copying or execution.

    Callers hold its existing workflow ownership. This reader neither adopts a
    source fence nor grants recovery authority; their native ownership guards
    still apply. It accepts only current shared repair records and never starts a
    historical scheduler. The returned marker may be published as scheduling.json
    after all preflight succeeds. Other records remain in their native formats.
    """
    run = Path(run)
    marker = _read_scheduling_record(run / 'scheduling.json')
    if marker is not None:
        admit_repair_scheduling_state({'scheduling': marker})
    # These records belong exclusively to the removed per-VM scheduler. Even a
    # current top-level marker cannot turn their rounds or budgets into ours.
    legacy = [*run.glob('pipeline-*'), *(run / name for name in (
        'pipelines.json', 'family-cases', 'pipeline.json', 'repair-queue.json'))]
    if any(path.exists() or path.is_symlink() for path in legacy):
        admit_repair_scheduling_state({})
    for name in ('checkpoint.json', 'limits.json', 'vm.json', 'repair-source-resume.json',
                 'repair-pending.json'):
        state = _read_scheduling_record(run / name)
        if state is None:
            continue
        # A missing allocation marker must not adopt retained payloads, even if
        # a single nested record happens to claim the current identity.
        admit_repair_scheduling_state({'scheduling': marker})
        if name == 'vm.json':
            if not isinstance(state, dict) or set(state) != {'vm'}:
                raise ValueError('invalid retained repair VM binding')
            binding = state['vm']
            if binding is None or isinstance(binding, str) and binding:
                continue
            if (not isinstance(binding, dict) or set(binding) != {'concurrency', 'vms'}
                    or type(binding['concurrency']) is not int or binding['concurrency'] < 1
                    or not isinstance(binding['vms'], list) or not binding['vms']
                    or any(not isinstance(vm, str) or not vm for vm in binding['vms'])
                    or len(binding['vms']) != len(set(binding['vms']))):
                raise ValueError('invalid retained repair VM binding')
            continue
        if name == 'repair-source-resume.json':
            if (not isinstance(state, dict) or set(state) != {'run'}
                    or not isinstance(state['run'], str) or not Path(state['run']).is_absolute()):
                raise ValueError('invalid retained repair source resume identity')
            continue
        admit_repair_scheduling_state(state)
        if name == 'checkpoint.json' and not isinstance(state.get('repairs'), dict):
            raise ValueError('invalid retained repair checkpoint')
        if name == 'limits.json' and (
                any(type(state.get(key)) is not int or state[key] < 0
                    for key in ('started', 'completed'))
                or state.get('tasks') is not None
                and (type(state['tasks']) is not int or state['tasks'] < 1)):
            raise ValueError('invalid retained task admissions')
    return repair_scheduling_marker()


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
    for scope, namespace in pass_namespaces(root).items():
        ordinary_path = path / namespace
        if ordinary_path.exists() or ordinary_path.is_symlink():
            private(ordinary_path.lstat())
        ordinary = _read_scheduling_record(ordinary_path / 'current.json', strict=True)
        if ordinary is not None:
            PassCheckpoint.validate(ordinary, scope=scope)
    for scope, namespace in PASS_NAMESPACES.items():
        groups_path = path / (namespace + '-groups')
        if groups_path.exists() or groups_path.is_symlink():
            private(groups_path.lstat())
        groups = _read_scheduling_record(groups_path / 'current.json', strict=True)
        if groups is not None:
            GroupCheckpoint.validate(groups, scope=scope)
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
    guard_scheduling_checkpoints(root)
    # Recovery owns only authoritative shared claims. The normal admission
    # guard refuses incompatible legacy progress; explicit reset retires those
    # old records only after its maintained owned cleanup succeeds.
    ordinary = 0
    for scope, namespace in pass_namespaces(root).items():
        ordinary_path = directory('state', root=root) / namespace
        if not ordinary_path.exists():
            continue
        state = _read_scheduling_record(ordinary_path / 'current.json', strict=True)
        if state is None:
            continue
        PassCheckpoint.validate(state, scope=scope)
        owned = [assignment for partition in state['families'].values()
                 for assignment in partition['claims'].values() if assignment['vm'] == vm_name]
        if recover:
            if not owned:
                continue
            # Take the coordinator's gate before touching any queue. An active
            # coordinator's in-memory claims cannot race standalone recovery.
            with PassCheckpoint.saved(root, scope=scope) as checkpoint:
                if checkpoint is not None:
                    owned = [assignment for assignment in checkpoint.claims() if assignment['vm'] == vm_name]
                    if owned:
                        with test_activity.exclusive_vm_progress():
                            for assignment in owned:
                                checkpoint.recover(assignment, cleanup=True)
                        ordinary += len(owned)
        else:
            ordinary += len(owned)
    return ordinary


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
