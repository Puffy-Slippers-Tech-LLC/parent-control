"""Finite runner closures under the existing live producer and capture journal.

Callers choose closed files explicitly. Mutable outer handoffs are separate
records, and publication never changes a runner verdict or executes a check.
"""
import copy
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

if __package__:
    from . import (capture_publication as publication, evidence_bundle as bundle,
                   evidence_capture as capture, evidence_identity as logical,
                   regression_inputs, test_retention as retention)
else:
    import capture_publication as publication
    import evidence_bundle as bundle
    import evidence_capture as capture
    import evidence_identity as logical
    import regression_inputs
    import test_retention as retention


def _json(value):
    # Runner dataclasses include tuples and floating-point durations. Their
    # immutable payload retains normal JSON; logical identity hashes its bytes.
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


class ReportEvidence:
    def __init__(self, root, directory, *, store=None, workflow='regression',
                 terminal_context=None, recovery_allowlist=None):
        self.root, self.directory = Path(root), Path(directory)
        if store is None:
            token = os.environ.get(retention.VARIABLE)
            if token is None:
                raise ValueError('runner evidence: a live producer session is required')
            journal, run = json.loads(token)
            store = retention.Store(journal)
            if store.producer_binding()[3] != run:
                raise ValueError('runner evidence: active token run changed')
        self.store, self.workflow = store, workflow
        self.binding = store.producer_binding()
        allocation = self._allocation(self.directory)
        self.sources_sha256 = regression_inputs.identity(self.root)
        logical._hex(self.sources_sha256)
        invocation = os.environ.get('ONPC_RUNNER_INVOCATION')
        self.invocation = {} if invocation is None else json.loads(invocation)
        if type(self.invocation) is not dict:
            raise ValueError('runner evidence: invocation provenance must be an object')
        # Parsing/copying is provenance only. Authority has already been
        # authenticated by producer_binding and is issued again by capture.
        self.invocation = json.loads(_json(self.invocation))
        self.commands, self._prepared, self._result = [], None, None
        self.terminal_context = copy.deepcopy(terminal_context)
        if terminal_context is not None:
            logical._object(terminal_context, {'target', 'check', 'inputs', 'cleanup_resources'},
                            'producer terminal context')
            logical._text(terminal_context['check'])
            if terminal_context['target']:
                logical._text(terminal_context['target'])
        self.recovery_allowlist = copy.deepcopy(recovery_allowlist)
        if recovery_allowlist is not None:
            if type(recovery_allowlist) is not list or len(recovery_allowlist) > 256:
                raise ValueError('runner evidence: invalid recovery allowlist')
            for item in recovery_allowlist:
                logical._object(item, {'pattern', 'role'}, 'recovery selection')
                pattern = item['pattern']
                if (type(pattern) is not str or not pattern or pattern.startswith('/')
                        or '..' in pattern.split('/') or '\\' in pattern):
                    raise ValueError('runner evidence: invalid relative recovery pattern')
                logical._choice(item['role'], {'result', 'input', 'command', 'junit', 'tap',
                                              'cleanup', 'diagnostic', 'media'})
        self._start = self._start_record(allocation)

    def _start_record(self, allocation):
        """Register a real lifecycle dependency before the runner writes results.

        Its outstanding required charge protects this owner's report allocation
        even when later inventory preparation fails before another seal exists.
        Only complete terminal publication acknowledges this lifecycle record.
        """
        caller = capture._authenticated_caller()
        repository = capture._repository(self.root, caller)
        owner = capture._owner(self.store.path, self.binding[1], repository, caller)
        directory = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-runner-start-'))
        path = directory / 'startup.json'
        payload = dict(schema='onpc-runner-lifecycle', version=1, phase='started',
                       workflow=self.workflow, owner=owner, run=self.binding[3],
                       report_allocation=allocation, invocation=self.invocation)
        if self.terminal_context is not None or self.recovery_allowlist is not None:
            payload.update(terminal_context=self.terminal_context,
                           recovery_allowlist=self.recovery_allowlist)
        with path.open('xb') as stream:
            os.chmod(path, 0o600)
            stream.write(_json(payload))
            stream.flush()
            os.fsync(stream.fileno())
        with retention.directory_descriptor(directory) as fd:
            os.fsync(fd)
        member = self._member(path, 'result')
        checksum = member['sha256']
        consumer_id = logical.digest(dict(workflow=self.workflow, run=self.binding[3],
            directory=str(self.directory), phase='started', input_sha256=checksum))
        handle = capture.issue_session(self.store, repository=self.root,
            workflow=self.workflow, task='runner-start', check='report-start',
            target='' if self.terminal_context is None else self.terminal_context['target'],
            inputs_sha256=checksum, sources_sha256=self.sources_sha256,
            consumers={consumer_id: dict(consumer_id=consumer_id, revision_sha256=checksum)})
        context = capture.session_context(handle)
        record = logical.finalize_record(dict(schema=logical.SCHEMA, version=1,
            context=context, status='diagnostic', completeness='partial',
            members=[member], dependencies=[], cleanup=dict(state='pending',
                record_members=[], scope=dict(owner=context['owner'], resources=[]))))
        identifier = capture.finalize_capture(handle, record=record, consumer_ids=[consumer_id])
        return dict(handle=handle, record=record, consumer_id=consumer_id, capture_id=identifier)

    def _allocation(self, path):
        if self.store.producer_binding() is not self.binding:
            raise ValueError('runner evidence: producer session changed')
        with self.store.locked(self.binding[1], 'writer.lock'):
            state = self.store.read(self.binding[1])
        matches = [item for item in state['paths']
                   if path == Path(item['path']) or path.is_relative_to(item['path'])]
        if len(matches) != 1:
            raise ValueError('runner evidence: file must belong to one live owned allocation')
        return dict(matches[0], journal=str(self.store.path), run=self.binding[3])

    def command(self, record):
        if self._prepared is not None:
            raise ValueError('runner evidence: finalized commands are immutable')
        self.commands.append(json.loads(_json(record)))

    def _member(self, path, role):
        path = Path(path)
        allocation = self._allocation(path)
        # Shared capture's pinned opener validates every component and file
        # identity before payload access; no symlink or external root adoption.
        logical._path(str(path))
        probe = dict(original_path=str(path), source_allocation=allocation,
                     bytes=path.lstat().st_size)
        with self.store.locked(self.binding[1], 'writer.lock'):
            state = self.store.read(self.binding[1])
        with capture._source(probe, state, self.store, self.binding[3]) as (fd, info):
            checksum = capture._hash(fd, info.st_size)
        return dict(role=role, original_path=str(path), source_allocation=allocation,
                    bytes=info.st_size, sha256=checksum, required=True)

    def _read_owned(self, member):
        if member['bytes'] > logical.MAX_METADATA:
            raise ValueError('runner evidence: recovery metadata exceeds read bound')
        with self.store.locked(self.binding[1], 'writer.lock'):
            state = self.store.read(self.binding[1])
        with capture._source(member, state, self.store, self.binding[3]) as (fd, _):
            data = os.pread(fd, member['bytes'] + 1, 0)
        if len(data) != member['bytes'] or hashlib.sha256(data).hexdigest() != member['sha256']:
            raise ValueError('runner evidence: recovery metadata changed')
        return data

    def _declare_preparation(self, value):
        """Save finite preparation inputs under this existing lifecycle owner.

        This is a recovery input, never permission to adopt a declared path.
        Every member is still authenticated against the live source journal.
        """
        source = self._start['record']['members'][0]
        if self._member(source['original_path'], 'result') != {
                key: item for key, item in source.items() if key != 'member_id'}:
            raise ValueError('runner evidence: startup source changed')
        path = Path(source['original_path']).parent / 'terminal-preparation.json'
        data = _json(value)
        if len(data) > logical.MAX_METADATA:
            raise ValueError('runner evidence: terminal preparation exceeds metadata bound')
        try:
            existing = self._member(path, 'input')
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if self._read_owned(existing) != data:
                raise ValueError('runner evidence: terminal preparation changed')
            return path
        with retention.directory_descriptor(path.parent) as fd:
            info = os.fstat(fd)
            allocation = source['source_allocation']
            if (info.st_dev, info.st_ino) != (allocation['device'], allocation['inode']):
                raise ValueError('runner evidence: startup allocation was replaced')
            temporary = path.name + '.tmp'
            output = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW,
                             0o600, dir_fd=fd)
            with os.fdopen(output, 'wb') as stream:
                retention.private(os.fstat(stream.fileno()), regular=True)
                stream.truncate(0)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path.name, src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
        return path

    def checkpoint_members(self, members):
        """Persist the producer's growing finite inventory after file sync.

        This owner-local recovery input lives outside the exact-list collector.
        It cannot remove or replace an already registered immutable member.
        """
        if self._prepared is not None:
            raise ValueError('runner evidence: terminal inventory is already closed')
        if len(members) > 4096:
            raise ValueError('runner evidence: checkpoint inventory exceeds bound')
        saved = []
        with self.store.locked(self.binding[1], 'writer.lock'):
            state = self.store.read(self.binding[1])
        for item in members:
            member = self._member(item['path'], item['role'])
            with capture._source(member, state, self.store, self.binding[3]) as (fd, info):
                identity = capture._fingerprint(info)
                if capture._hash(fd, info.st_size) != member['sha256']:
                    raise ValueError('runner evidence: checkpoint member changed')
            saved.append(dict(member=member, identity=identity))
        saved.sort(key=lambda item: item['member']['original_path'])
        if len({item['member']['original_path'] for item in saved}) != len(saved):
            raise ValueError('runner evidence: duplicate checkpoint member')
        source = self._start['record']['members'][0]
        path = Path(source['original_path']).parent / 'producer-inventory.json'
        try:
            previous = json.loads(self._read_owned(self._member(path, 'input')))
        except FileNotFoundError:
            previous = None
        if previous is not None:
            if (previous.get('start_record_id') != self._start['record']['record_id']
                    or any(item not in saved for item in previous['members'])):
                raise ValueError('runner evidence: checkpoint replaced registered proof')
        data = _json(dict(schema=1, start_record_id=self._start['record']['record_id'], members=saved))
        if len(data) > logical.MAX_METADATA:
            raise ValueError('runner evidence: checkpoint metadata exceeds bound')
        with retention.directory_descriptor(path.parent) as fd:
            allocation = source['source_allocation']
            if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (allocation['device'], allocation['inode']):
                raise ValueError('runner evidence: checkpoint allocation changed')
            output = os.open(path.name + '.tmp', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(output, 'wb') as stream:
                retention.private(os.fstat(stream.fileno()), regular=True)
                stream.truncate(0)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(path.name + '.tmp', path.name, src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
        self._checkpoint_expected = {item['member']['original_path']: item['identity'] for item in saved}
        return path

    def finalize(self, *, categories, status=None, cleanup='pending', members=(),
                 sources_sha256=None, inputs=None, target='', check='report',
                 cleanup_resources=(), dependencies=(), command_log=None):
        """Seal, publish and acknowledge a finite closed terminal inventory.

        Retry on this object resumes its exact handles/records after a lost
        reply. Failure retains registered originals; no authentication retry or
        fallback reader is attempted. New outer results use another object.
        """
        if self._result is not None:
            return copy.deepcopy(self._result)
        if self._prepared is None:
            sources_sha256 = sources_sha256 or self.sources_sha256
            logical._hex(sources_sha256)
            logical._choice(cleanup, {'complete', 'failed', 'pending', 'not_applicable'})
            status = status or 'diagnostic'
            logical._choice(status, {'passed', 'failed', 'interrupted', 'not_run', 'diagnostic'})
            logical._text(check)
            if target:
                logical._text(target)
            cleanup_resources = sorted(copy.deepcopy(list(cleanup_resources)),
                                       key=lambda item: (item['kind'], item['id']))
            dependencies = copy.deepcopy(list(dependencies))
            for dependency in dependencies:
                logical._record(dependency)
            if command_log is not None:
                if type(command_log) is not list or len(command_log) > 4096:
                    raise ValueError('runner evidence: command ledger exceeds bound')
                command_log = json.loads(_json(command_log))
                if any(type(command) is not dict for command in command_log):
                    raise ValueError('runner evidence: invalid command ledger')
            self.store.producer_binding()
            members = [dict(path=str(item['path']), role=item['role']) for item in members]
            if not getattr(self, '_recovering', False):
                declaration = self._declare_preparation(dict(schema=1,
                    start_record_id=self._start['record']['record_id'], members=members,
                    commands=self.commands, categories=categories, status=status,
                    cleanup=cleanup, inputs=inputs, sources_sha256=sources_sha256,
                    target=target, check=check, cleanup_resources=cleanup_resources,
                    dependencies=dependencies, command_log=command_log))
                members.append(dict(path=str(declaration), role='input'))
            directory = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-runner-evidence-'))
            external = [self._member(item['path'], item['role']) for item in members]
            if len({(item['original_path'], item['role']) for item in external}) != len(external):
                raise ValueError('runner evidence: duplicate finalized member')
            prepared = [self._start, *getattr(self, '_recovery_dependencies', [])]
            records = [*dependencies, *[item['record'] for item in prepared]]
            # A command binds its exact selection/target separately from the
            # aggregate, which owns only its original explicit file inventory.
            items = [(command, False) for command in self.commands]
            aggregate_commands = getattr(self, '_recovered_commands',
                                         self.commands if command_log is None else command_log)
            items.append((dict(check=check, target=target, status=status, cleanup=cleanup,
                               cleanup_resources=cleanup_resources,
                               lifecycle_record_id=self._start['record']['record_id'],
                               categories=categories, commands=aggregate_commands), True))
            if len(items) + len(prepared) > capture.MAX_SELECTIONS:
                raise ValueError('runner evidence: too many terminal records')
            for index, (item, aggregate) in enumerate(items):
                payloads = dict(
                    result=item,
                    input=dict(inputs=inputs, categories=categories if aggregate else None,
                               invocation=self.invocation if aggregate else None,
                               selected_ids=item.get('selected_ids', []),
                               resumed_ids=item.get('resumed_ids', []),
                               argv=item.get('argv', item.get('guest_args', []))),
                    command=dict(commands=aggregate_commands) if aggregate else item,
                    cleanup=dict(state=item.get('cleanup', cleanup),
                                 provenance=item.get('provenance', 'aggregate' if aggregate else 'worker')))
                own = []
                for role, payload in payloads.items():
                    path = directory / f'{index:04d}-{role}.json'
                    with path.open('xb') as stream:
                        os.chmod(path, 0o600)
                        stream.write(_json(payload))
                        stream.flush()
                        os.fsync(stream.fileno())
                    own.append(self._member(path, role))
                selected = external if aggregate else [member for member in external
                    if member['original_path'] == item.get('log')]
                input_sha = next(member['sha256'] for member in own if member['role'] == 'input')
                consumer_id = logical.digest(dict(workflow=self.workflow, run=self.binding[3],
                    directory=str(self.directory), index=index, input_sha256=input_sha))
                consumers = {consumer_id: dict(consumer_id=consumer_id, revision_sha256=input_sha)}
                referenced = {reference['record_id'] for dependency in records
                              for reference in dependency['dependencies']}
                dependency_roots = [dependency for dependency in records
                                    if dependency['record_id'] not in referenced]
                handle = capture.issue_session(self.store, repository=self.root,
                    workflow=self.workflow, task='runner-terminal', check=item.get('check') or 'report',
                    target=item.get('target') or '', inputs_sha256=input_sha,
                    sources_sha256=sources_sha256, consumers=consumers,
                    dependencies=records if aggregate else ())
                context = capture.session_context(handle)
                record_status = item.get('status', status)
                cleanup_state = item.get('cleanup', cleanup)
                logical._choice(cleanup_state, {'complete', 'failed', 'pending', 'not_applicable'})
                record_members = own + selected
                cleanup_ids = sorted(logical.member_id(logical.record_id(context), member)
                    for member in record_members if member['role'] == 'cleanup')
                if cleanup_state == 'not_applicable':
                    cleanup_ids = []
                record = logical.finalize_record(dict(schema=logical.SCHEMA, version=1,
                    context=context, status=record_status,
                    completeness='complete' if cleanup_state == 'complete' and record_status not in
                        ('interrupted', 'diagnostic', 'not_run') else 'partial',
                    members=record_members,
                    dependencies=[dict(record_id=dep['record_id'], closure_sha256=dep['closure_sha256'])
                                  for dep in dependency_roots] if aggregate else [],
                    cleanup=dict(state=cleanup_state, record_members=cleanup_ids,
                                 scope=dict(owner=context['owner'],
                                            resources=item.get('cleanup_resources', [])))))
                records.append(record)
                prepared.append(dict(handle=handle, record=record, consumer_id=consumer_id))
            with retention.directory_descriptor(directory) as fd:
                os.fsync(fd)
            self._prepared = prepared
        identifiers = []
        expected = getattr(self, '_checkpoint_expected', {})
        selected_paths = {member['original_path'] for item in self._prepared
                          for member in item['record']['members']}
        if not expected.keys() <= selected_paths:
            raise ValueError('runner evidence: terminal omitted checkpointed proof')
        for item in self._prepared:
            identifier = capture.finalize_capture(item['handle'], record=item['record'],
                                                 consumer_ids=[item['consumer_id']])
            item['capture_id'] = identifier
            if expected:
                with self.store.locked(self.binding[1], 'writer.lock'):
                    state = self.store.read(self.binding[1])
                charge, = [charge for charge in state['captures'] if charge['capture_id'] == identifier]
                originals = {original['member_id']: original['identity']
                             for original in charge['intent']['originals']}
                for member in item['record']['members']:
                    if (member['original_path'] in expected
                            and originals[member['member_id']] != expected[member['original_path']]):
                        raise ValueError('runner evidence: checkpointed source identity changed during sealing')
            identifiers.append(identifier)
        caller = capture._authenticated_caller()
        targets = sorted({item['record']['context']['target'] for item in self._prepared
                          if item['record']['context']['target']})
        with bundle.Selection(self.root, caller['uid'], caller['gid'], targets, [], [],
                              captures=sorted(identifiers), include_host_captures=True) as selected:
            receipt = bundle.export(selected, expected=selected.selection_sha256)
        # Leave the start charge pending until every terminal acknowledgement
        # has succeeded, including truthful failed/interrupted terminal records.
        for item in [*self._prepared[1:], self._prepared[0]]:
            request = capture.inspect_capture(self.root, caller['uid'], caller['gid'], item['capture_id'])
            capture.acknowledge_capture(self.root, caller['uid'], caller['gid'], item['capture_id'],
                expected=request['request_sha256'], session_handle=item['handle'])
        records = [item['record'] for item in self._prepared]
        references = [dict(schema=1, workflow=self.workflow, record_id=record['record_id'],
                           member_id=member['member_id'], closure_sha256=record['closure_sha256'])
                      for record in records for member in record['members']]
        consumers = []
        for item in self._prepared:
            record = item['record']
            consumer = dict(schema='onpc-evidence-consumer', version=1,
                consumer_id=item['consumer_id'], owner=record['context']['owner'],
                revision_sha256=record['context']['inputs_sha256'],
                # Read-only failure history cannot satisfy a passing-evidence
                # consumer. Source retention still requires every member and
                # its verified terminal acknowledgement regardless of status.
                role='required_evidence' if record['status'] == 'passed' and
                    record['completeness'] == 'complete' and record['cleanup']['state'] == 'complete'
                    else 'historical_information',
                expected_context=record['context'], state='working',
                references=sorted([dict(kind='evidence', record_id=record['record_id'],
                    member_id=member['member_id'], closure_sha256=record['closure_sha256'])
                    for member in record['members']], key=logical.encoded))
            logical.validate_consumer(consumer)
            consumers.append(consumer)
        self._result = dict(schema=1, receipt=receipt, capture_ids=identifiers,
                            records=records, references=references, consumers=consumers)
        return copy.deepcopy(self._result)


def _recovery_inventory(evidence, allocation, declaration):
    """Read only one authenticated allocation and its finite declared members."""
    root = Path(allocation['path'])
    if evidence._allocation(root) != allocation:
        raise ValueError('runner evidence: recovery allocation registration changed')
    members, commands, total, entries = {}, [], 0, 0
    declared = {} if declaration is None else {item['path']: item['role']
                                               for item in declaration['members']}

    def add(path, role):
        nonlocal total
        if str(path) in members:
            if members[str(path)]['role'] != role:
                raise ValueError('runner evidence: conflicting recovery member roles')
            return
        member = evidence._member(path, role)
        total += member['bytes']
        if len(members) >= 4096 or total > logical.MAX_BYTES:
            raise ValueError('runner evidence: recovery inventory exceeds capture bounds')
        members[str(path)] = dict(path=str(path), role=role)

    checkpoint = Path(evidence._start['record']['members'][0]['original_path']).parent / 'producer-inventory.json'
    try:
        checkpoint_member = evidence._member(checkpoint, 'input')
    except FileNotFoundError:
        if getattr(evidence, 'recovery_allowlist', None) == [] and declaration is None:
            raise ValueError('runner evidence: exact producer recovery inventory is unavailable')
    else:
        saved = json.loads(evidence._read_owned(checkpoint_member))
        logical._object(saved, {'schema', 'start_record_id', 'members'}, 'producer inventory')
        if (saved['schema'] != 1 or saved['start_record_id'] != evidence._start['record']['record_id']
                or type(saved['members']) is not list or len(saved['members']) > 4096):
            raise ValueError('runner evidence: invalid producer recovery inventory')
        for item in saved['members']:
            logical._object(item, {'member', 'identity'}, 'producer inventory member')
            member = item['member']
            current = evidence._member(member['original_path'], member['role'])
            if current != member:
                raise ValueError('runner evidence: registered recovery proof changed')
            with evidence.store.locked(evidence.binding[1], 'writer.lock'):
                state = evidence.store.read(evidence.binding[1])
            with capture._source(member, state, evidence.store, evidence.binding[3]) as (_, info):
                if capture._fingerprint(info) != item['identity']:
                    raise ValueError('runner evidence: registered recovery identity changed')
            add(Path(member['original_path']), member['role'])
        evidence._checkpoint_expected = {
            item['member']['original_path']: item['identity'] for item in saved['members']}
        if getattr(evidence, 'recovery_allowlist', None) == []:
            with retention.directory_descriptor(root) as fd:
                expected = {str(Path(path).relative_to(root)) for path in members
                            if Path(path).is_relative_to(root)}
                if set(os.listdir(fd)) != expected:
                    raise ValueError('runner evidence: unregistered producer recovery file')
        add(checkpoint, 'input')
        for path, role in declared.items():
            add(Path(path), role)
        if getattr(evidence, 'recovery_allowlist', None) == []:
            return list(members.values()), []

    def walk(directory, fd, depth):
        nonlocal entries
        if depth > 32:
            raise ValueError('runner evidence: recovery directory depth exceeded')
        before = os.fstat(fd)
        names = os.listdir(fd)
        entries += len(names)
        if entries > 4096:
            raise ValueError('runner evidence: recovery directory entry bound exceeded')
        for name in sorted(names):
            if name in {'ssh-key', 'ssh-key.pub', 'known-hosts', 'password', 'vars.json',
                        'credentials', 'redaction-identities'} or name.endswith('.password'):
                continue
            path = directory / name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    opened = os.fstat(child)
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino) or (
                            opened.st_uid != os.geteuid() or opened.st_mode & 0o022
                            or retention.mount_id(child) != retention.mount_id(fd)):
                        raise ValueError('runner evidence: unsafe recovery directory')
                    walk(path, child, depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                if str(path) in members:
                    continue  # Already verified against the immutable checkpoint.
                allowlist = getattr(evidence, 'recovery_allowlist', None)
                if allowlist is not None and str(path) not in declared:
                    matches = [item['role'] for item in allowlist
                        if fnmatch.fnmatchcase(str(path.relative_to(root)), item['pattern'])]
                    if not matches:
                        continue
                    role = matches[0]
                    add(path, role)
                    continue
                role = declared.get(str(path), 'input' if name.startswith('inventory-') else
                    'command' if name.startswith('command-') or path.suffix == '.log' or name == 'schedule.jsonl' else
                    'result' if name in ('report.md', 'progress.json', 'failure.json', 'results.json') else 'diagnostic')
                add(path, role)
                if name.startswith('command-') and path.suffix == '.json':
                    try:
                        command = json.loads(evidence._read_owned(evidence._member(path, role)))
                    except json.JSONDecodeError:
                        continue  # Retain the actual interrupted bytes as diagnostics.
                    if type(command) is dict:
                        commands.append(command)
            else:
                raise ValueError('runner evidence: linked or special recovery member refused')
        current = os.stat(directory, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError('runner evidence: recovery directory was replaced')

    with retention.directory_descriptor(root) as fd:
        info = os.fstat(fd)
        retention.allocation_identity(info, allocation['mode'])
        if (info.st_dev, info.st_ino) != (allocation['device'], allocation['inode']):
            raise ValueError('runner evidence: recovery report allocation was replaced')
        walk(root, fd, 0)
    for path, role in declared.items():
        add(Path(path), role)  # Every external member still requires same-run ownership.
    # A process may disappear before terminal preparation was declared. The
    # coverage producer has exactly two finite outputs named by its closed log.
    for command in commands:
        if command.get('category') != 'coverage':
            continue
        log = command.get('log')
        if log not in members or not Path(log).is_relative_to(root):
            raise ValueError('runner evidence: coverage log is outside the authenticated report')
        data = evidence._read_owned(evidence._member(log, members[log]['role']))
        for line in data.decode('utf-8', errors='replace').splitlines():
            if line.startswith('run-tests: output='):
                output = Path(line.removeprefix('run-tests: output='))
                for name in ('coverage.xml', '.coverage'):
                    path = output / name
                    if path.exists() or command.get('status') == 'passed':
                        add(path, 'result')
    return list(members.values()), commands


def recover_pending(root, store):
    """Finish exact current-run runner captures before admitting a newer run.

    Requires existing public recovery to have finished and unmarked this owner.
    It neither clears recovery markers nor operates VMs or reruns checks. A
    source already superseded by another run refuses rather than adopting it.
    """
    if not store.path.exists():
        return []
    with store.opened() as fd, store.locked(fd, 'owner.lock', shared=True, blocking=False):
        with store.locked(fd, 'writer.lock', shared=True):
            state = store.read(fd)
            retention.finished_owner(fd, state)
            if state is None:
                return []
            pending = [charge for charge in state.get('captures', [])
                       if not charge.get('acknowledgement')]
            if any(not charge.get('acknowledgement') for entry in state['history']
                   for charge in entry.get('captures', [])):
                raise ValueError('runner evidence: pending source belongs to a superseded run')
            if not pending:
                return []
            if any(charge['intent']['record']['context']['task'] not in
                   ('runner-start', 'runner-terminal') for charge in pending):
                raise ValueError('runner evidence: non-runner pending capture requires its own recovery')
            original_run = state['run']
    results = []
    with store.session(run=original_run):
        binding = store.producer_binding()
        with store.locked(binding[1], 'writer.lock'):
            state = store.read(binding[1])
        charges = state.get('captures', [])
        starts = [charge for charge in charges if not charge.get('acknowledgement')
                  and charge['intent']['record']['context']['task'] == 'runner-start']
        if not starts:
            raise ValueError('runner evidence: pending source has no runner lifecycle')
        by_record = {charge['intent']['record']['record_id']: charge for charge in charges}

        def resume(charge):
            capture._charge_owner(store, binding[1], state, charge)
            intent = charge['intent']
            consumers = list(intent['consumers'])
            if len(consumers) != 1:
                raise ValueError('runner evidence: ambiguous retained runner consumer')
            handle = capture.resume_session(store, charge['capture_id'])
            capture.finalize_capture(handle, record=intent['record'], consumer_ids=consumers)
            return dict(handle=handle, record=intent['record'], consumer_id=consumers[0],
                        capture_id=charge['capture_id'])

        for charge in starts:
            start = resume(charge)
            context = start['record']['context']
            if context['repository']['root'] != str(root) or context['check'] != 'report-start':
                raise ValueError('runner evidence: foreign lifecycle context')
            source = start['record']['members']
            if len(source) != 1:
                raise ValueError('runner evidence: invalid startup member inventory')
            evidence = ReportEvidence.__new__(ReportEvidence)
            evidence.root, evidence.store, evidence.binding = Path(root), store, binding
            evidence.workflow, evidence.sources_sha256 = context['workflow'], context['sources_sha256']
            evidence._start, evidence._prepared, evidence._result = start, None, None
            evidence.commands, evidence._recovering = [], True
            payload = json.loads(evidence._read_owned(source[0]))
            startup_fields = {'schema', 'version', 'phase', 'workflow', 'owner', 'run',
                              'report_allocation', 'invocation'}
            if set(payload) != startup_fields:
                startup_fields |= {'terminal_context', 'recovery_allowlist'}
            logical._object(payload, startup_fields, 'runner startup')
            if (payload['schema'] != 'onpc-runner-lifecycle' or payload['version'] != 1
                    or payload['phase'] != 'started' or payload['workflow'] != context['workflow']
                    or payload['owner'] != context['owner'] or payload['run'] != original_run
                    or type(payload['invocation']) is not dict):
                raise ValueError('runner evidence: startup provenance changed')
            allocation = payload['report_allocation']
            evidence.terminal_context = payload.get('terminal_context')
            evidence.recovery_allowlist = payload.get('recovery_allowlist')
            logical.validate_allocation(allocation)
            evidence.directory, evidence.invocation = Path(allocation['path']), payload['invocation']
            if evidence._allocation(evidence.directory) != allocation:
                raise ValueError('runner evidence: foreign report allocation')
            reference = dict(record_id=start['record']['record_id'],
                             closure_sha256=start['record']['closure_sha256'])
            terminals = [item for item in charges
                if item['intent']['record']['context']['task'] == 'runner-terminal'
                and reference in item['intent']['record']['dependencies']]
            if len(terminals) > 1:
                raise ValueError('runner evidence: ambiguous retained terminal closure')
            if terminals:
                checkpoint = Path(source[0]['original_path']).parent / 'producer-inventory.json'
                try:
                    evidence._member(checkpoint, 'input')
                except FileNotFoundError:
                    pass
                else:
                    _recovery_inventory(evidence, allocation, None)
                closure, waiting = {}, [terminals[0]]
                while waiting:
                    item = waiting.pop()
                    record = item['intent']['record']
                    if record['record_id'] in closure:
                        continue
                    closure[record['record_id']] = item
                    for dependency in record['dependencies']:
                        child = by_record.get(dependency['record_id'])
                        if child is None or child['intent']['record']['closure_sha256'] != dependency['closure_sha256']:
                            raise ValueError('runner evidence: missing retained dependency')
                        waiting.append(child)
                evidence._prepared = [start, *[resume(item) for item in charges
                    if item['intent']['record']['record_id'] in closure
                    and item['capture_id'] != charge['capture_id']]]
                results.append(evidence.finalize(categories=[]))
                continue
            peers = [item for item in starts
                     if item['intent']['record']['context']['workflow'] == context['workflow']]
            exact_producer = evidence.terminal_context is not None and evidence.recovery_allowlist is not None
            if len(peers) != 1 and not exact_producer:
                raise ValueError('runner evidence: ambiguous unfinished report allocations')
            evidence._recovery_dependencies = [resume(item) for item in charges
                if item['capture_id'] != charge['capture_id'] and not item.get('acknowledgement')
                and item['intent']['record']['context']['workflow'] == context['workflow']
                and item['intent']['record']['context']['task'] == 'runner-terminal'] if not exact_producer else []
            declaration_path = Path(source[0]['original_path']).parent / 'terminal-preparation.json'
            try:
                declared_member = evidence._member(declaration_path, 'input')
            except FileNotFoundError:
                declared_member, declaration = None, None
            else:
                declaration = json.loads(evidence._read_owned(declared_member))
                preparation_fields = {'schema', 'start_record_id', 'members', 'commands',
                    'categories', 'status', 'cleanup', 'inputs', 'sources_sha256'}
                # Retained runner preparations predate target-specific producer
                # closures. Their original host/report context remains valid.
                if set(declaration) != preparation_fields:
                    preparation_fields |= {'target', 'check', 'cleanup_resources', 'dependencies'}
                    if 'command_log' in declaration:
                        preparation_fields.add('command_log')
                logical._object(declaration, preparation_fields, 'runner preparation')
                if declaration['schema'] != 1 or declaration['start_record_id'] != reference['record_id']:
                    raise ValueError('runner evidence: foreign terminal preparation')
                if (type(declaration['members']) is not list or len(declaration['members']) > 4096
                        or type(declaration['commands']) is not list
                        or len(declaration['commands']) > capture.MAX_SELECTIONS):
                    raise ValueError('runner evidence: invalid finite terminal preparation')
                paths = []
                for member in declaration['members']:
                    logical._object(member, {'path', 'role'}, 'runner preparation member')
                    logical._path(member['path'])
                    logical._choice(member['role'], {'result', 'input', 'command', 'junit', 'tap',
                                                     'cleanup', 'diagnostic', 'media'})
                    paths.append(member['path'])
                if len(paths) != len(set(paths)):
                    raise ValueError('runner evidence: duplicate recovery member declaration')
            members, commands = _recovery_inventory(evidence, allocation, declaration)
            if declared_member is not None:
                members.append(dict(path=str(declaration_path), role='input'))
            evidence._recovered_commands = commands if declaration is None else (
                declaration.get('command_log') if declaration.get('command_log') is not None
                else declaration['commands'])
            terminal_context = evidence.terminal_context or {}
            results.append(evidence.finalize(categories=[] if declaration is None else declaration['categories'],
                status='interrupted', cleanup='pending', members=members,
                inputs=terminal_context.get('inputs') if declaration is None else declaration['inputs'],
                target=terminal_context.get('target', '') if declaration is None else declaration.get('target', ''),
                check=terminal_context.get('check', 'report') if declaration is None else declaration.get('check', 'report'),
                cleanup_resources=terminal_context.get('cleanup_resources', ()) if declaration is None
                    else declaration.get('cleanup_resources', ()),
                dependencies=() if declaration is None else declaration.get('dependencies', ())))
        with store.locked(binding[1], 'writer.lock'):
            remaining = store.read(binding[1])
        if any(not charge.get('acknowledgement') for charge in remaining.get('captures', [])):
            raise ValueError('runner evidence: unresolved runner captures remain required')
    return results


def resolve_reference(root, reference, *, consumer=None, offset=0, count=None):
    """Resolve exact bytes through the workflow's current verified publication.

    The original capture slot and receipt generation may already have retired.
    The existing cumulative publication journal remains the only locator. A
    whole-member read exceeding the shared read bound requires explicit ranges.
    """
    logical._object(reference, {'schema', 'workflow', 'record_id', 'member_id', 'closure_sha256'},
                    'runner evidence reference')
    if type(reference['schema']) is not int or reference['schema'] != 1:
        raise ValueError('runner evidence: unsupported reference')
    for key in ('record_id', 'member_id', 'closure_sha256'):
        logical._hex(reference[key])
    logical._text(reference['workflow'])
    caller = capture._authenticated_caller()
    repository = capture._repository(Path(root), caller)
    namespace = publication._namespace(dict(record=dict(context=dict(
        repository=repository, workflow=reference['workflow']))))
    with bundle.identity(caller['uid'], caller['gid']):
        parent = bundle.plan_parent(root, namespace)
        store = retention.Store(parent / 'retention')
        with store.inspection(include_committed=True), store.opened() as fd:
            state = publication._read(fd)
            if state is None or state['published'] is None:
                raise ValueError('runner evidence: missing cumulative publication')
            matching = [request for request in state['published']['requests']
                        if request['record']['record_id'] == reference['record_id']]
            if len(matching) != 1:
                raise ValueError('runner evidence: exact record is unavailable')
            publication._validate(state, matching[0])
            record = state['published']['allocation']
            with bundle.verified_record(record, caller['uid'], checkout=root) as (verified, read):
                publication._verify_generation(state['published'], verified)
                selectors = {key: reference[key]
                             for key in ('record_id', 'member_id', 'closure_sha256')}
                _, member = bundle.resolve_member(verified['manifest'], consumer=consumer, **selectors)
                if count is None:
                    count = max(0, member['bytes'] - offset)
                return read(offset=offset, count=count, **selectors)
