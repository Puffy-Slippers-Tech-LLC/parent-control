"""Bounded accepted-plan proof, using the shared verified bundle transaction.

The small stable index is a locator, never substitute acceptance. Every generation
flattens its complete predecessor; missing proof or a full budget stops close-out.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid
from contextlib import ExitStack, contextmanager

# The fixed read-only launcher uses isolated Python; load only checkout siblings.
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import evidence_bundle as bundle
import document_checks
from document_checks import evidence_prose, local_destination, references, simple_inline_references
from execution_plan import plan_namespace


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _read(path):
    """Read a finite regular file without following links or accepting mutation."""
    path = Path(path)
    with bundle.retention.directory_descriptor(path.parent) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            bundle.safe(before, os.geteuid())
            if not stat.S_ISREG(before.st_mode) or before.st_size > bundle.MAX_MANIFEST:
                raise ValueError('plan evidence: expected a finite regular record')
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
                if sum(map(len, chunks)) > bundle.MAX_MANIFEST:
                    raise ValueError('plan evidence: record grew beyond its limit')
            if bundle.fingerprint(os.fstat(fd)) != bundle.fingerprint(before):
                raise ValueError('plan evidence: source changed while reading')
            return b''.join(chunks)
        finally:
            os.close(fd)


def _write(path, data):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic(path, data):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
    _write(temporary, data)
    if path.exists():
        info = path.lstat()
        bundle.safe(info, os.geteuid())
        temporary.chmod(stat.S_IMODE(info.st_mode))
    os.replace(temporary, path)
    with bundle.retention.directory_descriptor(path.parent) as fd:
        os.fsync(fd)


def _parent(plan, *, create=False):
    return bundle.plan_parent(plan.root, plan_namespace(plan.path), create=create)


def locator(plan):
    return _parent(plan).parent / 'accepted-evidence.json'


SOURCE_FILES = ('agent-result.json', 'prompt.txt', 'agent-commands.log', 'checkpoint.json',
                'nested.json', 'nested-closed')
TURN_FILES = (*SOURCE_FILES, 'agent-error.json', 'rejected-agent-result.json')


EvidenceUnavailable = bundle.EvidenceUnavailable


def _turn(path, task_id, *, plan=None):
    """Verify a closed turn before trusting or moving any of its members."""
    path = Path(path)
    if plan is not None and (path.parent.name != 'plan-turns'
            or path.parent.parent.parent != _parent(plan).parent
            or re.fullmatch(r'[0-9a-f]{32}', path.parent.parent.name) is None
            or re.fullmatch(r'[0-9a-f]{64}', path.name) is None):
        raise ValueError('plan evidence: retained turn belongs to another run owner')
    raw = _read(path / 'turn.json')
    value = bundle.decoded(raw)
    if (not isinstance(value, dict) or set(value) != {
            'schema', 'version', 'task_id', 'attempt', 'session', 'files', 'result_sha256'}
            or value['schema'] != 'onpc-plan-turn' or type(value['version']) is not int
            or value['version'] != 1 or value['task_id'] != task_id
            or value['attempt'] is not None and not isinstance(value['attempt'], str)
            or value['session'] is not None and (type(value['session']) is not int or value['session'] < 0)
            or not isinstance(value['files'], dict) or not value['files']
            or any(name not in TURN_FILES for name in value['files'])
            or any(not _hash(hashed) for hashed in value['files'].values())
            or value['result_sha256'] is not None and not _hash(value['result_sha256'])):
        raise ValueError('plan evidence: invalid retained turn')
    contents = {name: _read(path / name) for name in value['files']}
    if (path.name != _digest(bundle.encoded(value))
            or any(_digest(contents[name]) != hashed for name, hashed in value['files'].items())):
        raise ValueError('plan evidence: retained turn changed')
    if value['result_sha256'] is not None and value['files'].get('agent-result.json') != value['result_sha256']:
        raise ValueError('plan evidence: retained turn result changed')
    return value, dict(contents, **{'turn.json': raw})


def retain_turn(plan, run, state, result=None, *, publish=True):
    """Keep a closed response/error before the next session replaces its files.

    This records history, never acceptance. Malformed responses and provider
    failures retain their original bytes without manufacturing a valid result.
    The caller finishes nested owners before this handoff; failed cleanup must
    not be converted into a closed turn by this routine. A controller proceeding
    directly to preserve() may defer publication: the durable local turn is then
    published with acceptance instead of copying the cumulative archive twice.
    """
    run = Path(run)
    contents = {}
    for name in TURN_FILES:
        try:
            contents[name] = _read(run / name)
        except FileNotFoundError:
            continue
    # Older checkpoints and interrupted-before-execution turns may have no
    # response, but still retain prompt, command and cleanup provenance.
    if not contents:
        return None
    if 'nested-closed' not in contents:
        raise ValueError('plan evidence: turn cleanup has not finished')
    if result is not None:
        if ('agent-result.json' not in contents
                or bundle.decoded(contents['agent-result.json']) != result
                or result.get('task_id') != state['task_id']):
            raise ValueError('plan evidence: exact terminal result is missing or changed')
    value = dict(schema='onpc-plan-turn', version=1, task_id=state['task_id'],
        attempt=state.get('evidence_attempt'), session=state.get('task_sessions'),
        files={name: _digest(data) for name, data in contents.items()},
        result_sha256=_digest(contents['agent-result.json']) if 'agent-result.json' in contents else None)
    key = _digest(bundle.encoded(value))
    for previous in state.get('evidence_turns', []):
        saved, _ = _turn(previous, state['task_id'], plan=plan)
        # Controller checkpoints evolve after the closed turn is recorded.
        # Retrying that handoff keeps its first checkpoint, while changes to
        # response/command/cleanup bytes remain a distinct exact turn.
        if (saved['attempt'] == value['attempt'] and saved['session'] == value['session']
                and {name: hashed for name, hashed in saved['files'].items() if name != 'checkpoint.json'}
                    == {name: hashed for name, hashed in value['files'].items() if name != 'checkpoint.json'}):
            if publish:
                _publish_turn(plan, run, state, result, Path(previous))
            return Path(previous)
    parent = run / 'plan-turns'
    bundle.retention.ensure_directory(parent)
    target = parent / key
    # An interrupted copy is deliberately not adopted. The published state only
    # names fully written manifests, and an existing identical manifest verifies.
    if target.exists():
        saved, _ = _turn(target, state['task_id'], plan=plan)
        if saved != value:
            raise ValueError('plan evidence: retained turn identity conflicts')
    else:
        staging = parent / uuid.uuid4().hex
        bundle.retention.ensure_directory(staging)
        for name, data in contents.items():
            _write(staging / name, data)
        _write(staging / 'turn.json', bundle.encoded(value))
        with bundle.retention.directory_descriptor(staging) as fd:
            os.fsync(fd)
        os.rename(staging, target)
        with bundle.retention.directory_descriptor(parent) as fd:
            os.fsync(fd)
    state.setdefault('evidence_turns', []).append(str(target))
    if publish:
        _publish_turn(plan, run, state, result, target)
    return target


def _publish_turn(plan, run, state, result, target):
    """Extend existing bounded plan proof without accepting the terminal turn."""
    if result is not None:
        try:
            consume(plan, state, result)
        except EvidenceUnavailable:
            return recover(plan)
    previous = recover(plan)
    if previous is not None:
        if previous['schema'] != 1:
            raise ValueError('plan evidence: schema 2 publication requires the versioned producer')
        # Lost replies reuse their already verified publication, even when its
        # original report and this turn's first raw directory have rotated.
        manifest = bundle.inspect(plan.root, os.geteuid(), os.getegid(), previous['bundle'])['manifest']
        raw = str(target / 'turn.json')
        if any(entry['path'] == raw and entry['sha256'] == _digest(_read(raw))
               for entry in manifest['files']):
            return previous
    metadata = Path(run) / 'working-proof' / uuid.uuid4().hex
    bundle.retention.ensure_directory(metadata)
    old_raw = _read(locator(plan)) if previous else b''
    generation = 1
    if previous:
        ledger = bundle.decoded(bundle.inspect(plan.root, os.geteuid(), os.getegid(), previous['bundle'],
                                member=previous['ledger'], count=bundle.MAX_READ))
        generation = ledger['generation'] + 1
    _write(metadata / 'accepted-ledger.json', bundle.encoded(dict(schema=1, plan=plan.path,
        generation=generation, previous_index_sha256=_digest(old_raw),
        tasks=previous['tasks'] if previous else {})))
    sources = [str(target), str(metadata), *state.get('evidence_inputs', [])]
    references = _references(plan, result, state) if result is not None else []
    if result is None:
        # Queue/acceptance validation can reject an otherwise readable response.
        # Preserve its finite legacy selections without registering claims or
        # letting malformed structured declarations acquire reader authority.
        try:
            rejected = bundle.decoded(_read(target / 'agent-result.json'))
        except (FileNotFoundError, ValueError):
            rejected = None
        if (isinstance(rejected, dict) and rejected.get('task_id') == state['task_id']
                and isinstance(rejected.get('checks'), list) and len(rejected['checks']) <= 256):
            checks = []
            for check in rejected['checks']:
                if not isinstance(check, dict) or not isinstance(check.get('evidence'), str):
                    continue
                try:
                    structured = _structured(check['evidence'])
                except ValueError:
                    continue
                if structured is None:
                    checks.append(check)
            references = _references(plan, dict(checks=checks), state)
    try:
        _export(plan, run, state, sources, [previous['bundle']] if previous else [], references)
    except EvidenceUnavailable:
        # A rejected turn with expired proof remains truthful history. Only
        # accepted preservation enters the existing exact-reference renewal.
        return previous
    return recover(plan)


def _source(plan, run, state, result):
    """Bind and rehome the exact accepted session before publication can fail."""
    run = Path(run)
    saved = state.get('evidence_source')
    if saved is not None:
        if (not isinstance(saved, dict) or set(saved) != {'path', 'files', 'result_sha256'}
                or set(saved['files']) != set(SOURCE_FILES)):
            raise ValueError('plan evidence: invalid retained session source')
        source = Path(saved['path'])
        contents = {name: _read(source / name) for name in SOURCE_FILES}
        if (any(_digest(contents[name]) != saved['files'][name] for name in SOURCE_FILES)
                or _digest(contents['agent-result.json']) != saved['result_sha256']
                or bundle.decoded(contents['agent-result.json']) != result):
            raise ValueError('plan evidence: exact retained session source changed')
    else:
        candidates = [run]
        if state.get('recovery_run'):
            candidates.append(Path(state['recovery_run']))
        source = None
        for candidate in dict.fromkeys(candidates):
            try:
                raw = _read(candidate / 'agent-result.json')
            except FileNotFoundError:
                continue
            found = bundle.decoded(raw)
            if found.get('task_id') != result['task_id']:
                continue  # A later prerequisite owns this run's response.
            if found != result:
                raise ValueError('plan evidence: exact agent result is missing or changed')
            source = candidate
            break
        if source is None:
            raise ValueError('plan evidence: exact agent result is missing or changed')
        from detached_launcher import finish_nested
        finish_nested(plan.root, source)
        contents = {name: _read(source / name) for name in SOURCE_FILES}
        if bundle.decoded(contents['agent-result.json']) != result:
            raise ValueError('plan evidence: exact agent result changed during cleanup')
    parent = run / 'accepted-source'
    if source.parent != parent:
        bundle.retention.ensure_directory(parent)
        source = parent / uuid.uuid4().hex
        bundle.retention.ensure_directory(source)
        for name, data in contents.items():
            _write(source / name, data)
        with bundle.retention.directory_descriptor(source) as fd:
            os.fsync(fd)
    state['evidence_source'] = dict(path=str(source),
        files={name: _digest(data) for name, data in contents.items()},
        result_sha256=_digest(contents['agent-result.json']))
    return source


def carry(plan, run, state):
    """Rehome exact active and suspended inputs before older runs can rotate.

    This performs no selection or session and preserves task, acceptance and
    Git ownership. Legacy checkpoints without captured inputs remain untouched.
    """
    parent = Path(run) / 'plan-inputs'
    turns = []
    for previous in state.get('evidence_turns', []):
        source = Path(previous)
        value, contents = _turn(source, state['task_id'], plan=plan)
        turn_parent = Path(run) / 'plan-turns'
        target = turn_parent / _digest(bundle.encoded(value))
        if source != target:
            bundle.retention.ensure_directory(turn_parent)
            if target.exists():
                if _turn(target, state['task_id'], plan=plan)[0] != value:
                    raise ValueError('plan evidence: retained turn identity conflicts')
            else:
                staging = turn_parent / uuid.uuid4().hex
                bundle.retention.ensure_directory(staging)
                for name, data in contents.items():
                    _write(staging / name, data)
                with bundle.retention.directory_descriptor(staging) as fd:
                    os.fsync(fd)
                os.rename(staging, target)
                with bundle.retention.directory_descriptor(turn_parent) as fd:
                    os.fsync(fd)
        turns.append(str(target))
    if 'evidence_turns' in state:
        state['evidence_turns'] = turns
    if state.get('evidence_inputs'):
        bundle.retention.ensure_directory(parent)
    # Each restart moves its exact prior selections into the current registered
    # run. The preceding run is still retained when a new run is allocated.
    carried = []
    for value in state.get('evidence_inputs', []):
        source = Path(value)
        metadata = _read(source / 'inputs.json')
        selected = bundle.decoded(metadata)
        if selected.get('task_id') != state['task_id']:
            raise ValueError('plan evidence: captured inputs belong to another task')
        contents = {'inputs.json': metadata}
        for entry in selected['files']:
            name = entry['member']
            if Path(name).name != name:
                raise ValueError('plan evidence: invalid captured input member')
            data = _read(source / name)
            if _digest(data) != entry['sha256']:
                raise ValueError('plan evidence: captured inputs changed')
            contents[name] = data
        if source.parent != parent:
            source = parent / uuid.uuid4().hex
            bundle.retention.ensure_directory(source)
            for name, data in contents.items():
                _write(source / name, data)
        carried.append(str(source))
    if 'evidence_inputs' in state:
        state['evidence_inputs'] = carried
    pending = state.get('pending_completion')
    if pending is not None:
        with recovered(plan) as (published, _, read):
            accepted = published['tasks'].get(pending['task_id']) if published else None
            exact = (bundle.decoded(read(accepted['result'], count=bundle.MAX_READ)) == pending
                     if accepted else False)
        if not exact:
            _source(plan, run, state, pending)
    renewal = state.get('evidence_renewal')
    if renewal:
        _source(plan, run, renewal, renewal['result'])
    for suspended in state.get('suspended_tasks', {}).values():
        carry(plan, run, suspended)
    return state


def capture(plan, run, state):
    """Freeze exact task-selection files before an agent may remove its brief."""
    carry(plan, run, state)
    if 'reference_git_base' not in state and (plan.root / '.git').exists():
        commit = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=plan.root,
                                capture_output=True, text=True, check=True).stdout.strip()
        if not re.fullmatch('[0-9a-f]{40,64}', commit):
            raise ValueError('plan evidence: invalid document baseline revision')
        state['reference_git_base'] = commit
    parent = Path(run) / 'plan-inputs'
    bundle.retention.ensure_directory(parent)
    target = parent / uuid.uuid4().hex
    bundle.retention.ensure_directory(target)
    files, missing = [], []
    brief = Path(state['task']['brief'])
    brief = brief if brief.is_absolute() else plan.root / brief
    recovering = (state.get('phase') == 'recover'
                  or state.get('recovery_run') and state.get('in_flight')
                  or any(state.get(key) for key in ('pending_completion', 'git_reconciliation',
                                                   'result_recovery', 'evidence_renewal')))
    for index, value in enumerate(dict.fromkeys((plan.path, plan.queue, state['task']['brief']))):
        source = Path(value)
        source = source if source.is_absolute() else plan.root / source
        if not source.is_relative_to(plan.root):
            raise ValueError('plan evidence: input is outside the checkout')
        try:
            data = _read(source)
        except FileNotFoundError:
            if source != brief or not recovering:
                raise
            missing.append(dict(path=str(source), reason='missing during retained task recovery'))
            continue
        name = f'input-{index:04d}'
        _write(target / name, data)
        files.append(dict(path=str(source), sha256=_digest(data), member=name))
    _write(target / 'inputs.json', bundle.encoded(dict(task_id=state['task_id'],
        task=state['task'], session=state.get('task_sessions'), files=files, missing=missing)))
    state.setdefault('evidence_inputs', []).append(str(target))
    state['evidence_attempt'] = str(target)
    state.pop('evidence_source', None)  # The next response belongs to this new turn.
    captured_brief = any(entry['path'] == str(brief)
        for value in state['evidence_inputs']
        for entry in bundle.decoded(_read(Path(value) / 'inputs.json'))['files'])
    if not captured_brief:
        state['evidence_capture_requires_brief'] = True
    else:
        state.pop('evidence_capture_requires_brief', None)
    return target


def _index(path):
    try:
        data = _read(path)
    except FileNotFoundError:
        return None, b''
    value = bundle.decoded(data)
    if not isinstance(value, dict) or type(value.get('schema')) is not int:
        raise ValueError('plan evidence: invalid accepted index')
    if value['schema'] == 2:
        _index_v2(value)
    elif (value['schema'] != 1 or set(value) != {
            'schema', 'plan', 'bundle', 'sha256', 'selection_sha256', 'ledger', 'tasks'}
            or not isinstance(value['tasks'], dict)):
        raise ValueError('plan evidence: invalid accepted index')
    return value, data


def _ledger(record, plan):
    with bundle.verified_record(record, os.geteuid(), checkout=plan.root) as (verified, read):
        return _verified_ledger(record, plan, verified, read)


def _verified_ledger(record, plan, verified, read, *, ledger_path=None):
    """Validate all proof records within the archive's verified read scope."""
    candidates = []
    for entry in verified['manifest']['files']:
        if (entry['path'] == ledger_path if ledger_path is not None else
                Path(entry['path']).name == 'accepted-ledger.json'):
            data = read(entry['path'], count=bundle.MAX_READ)
            value = bundle.decoded(data)
            schema = value.get('schema') if isinstance(value, dict) else None
            keys = {'schema', 'plan', 'generation', 'previous_index_sha256', 'tasks'}
            if schema == 2:
                keys |= {'records', 'segments'}
            if (not isinstance(value, dict) or set(value) != keys
                    or type(schema) is not int or schema not in (1, 2) or value['plan'] != plan.path
                    or type(value['generation']) is not int or value['generation'] <= 0
                    or not isinstance(value['tasks'], dict)):
                raise ValueError('plan evidence: invalid accepted ledger')
            if schema == 2 and ledger_path is None:
                raise ValueError('plan evidence: schema 2 requires an exact ledger selector')
            candidates.append((value['generation'], entry['path'], value))
    if not candidates:
        raise ValueError('plan evidence: accepted ledger is missing')
    generation, ledger_path, value = max(candidates, key=lambda item: item[0])
    if sum(item[0] == generation for item in candidates) != 1:
        raise ValueError('plan evidence: ambiguous accepted ledger')
    files = {item['path']: item for item in verified['manifest']['files']}
    _validate_task_proofs(value, plan, files, read)
    if value['schema'] == 2:
        return value, None
    index = dict(schema=1, plan=plan.path, bundle=str(Path(record['path']) / 'evidence.zip'),
                 sha256=verified['sha256'], selection_sha256=verified['selection_sha256'],
                 ledger=ledger_path, tasks=value['tasks'])
    return value, index


def _validate_task_proofs(value, plan, files, read):
    """Keep the original exact result/input/cleanup checks in both versions."""
    for task, proof in value['tasks'].items():
        keys = {'result', 'sha256', 'inputs', 'cleanup', 'records', 'attempt'}
        if value['schema'] == 2:
            keys.add('record_refs')
        if (not isinstance(proof, dict) or set(proof) != keys
                or proof['cleanup'] is not True or proof['result'] not in files
                or files[proof['result']]['sha256'] != proof['sha256']
                or not proof['inputs'] or any(path not in files for path in proof['inputs'])
                or not isinstance(proof['records'], dict)
                or any(path not in files or files[path]['sha256'] != hashed
                       for path, hashed in proof['records'].items())):
            raise ValueError('plan evidence: accepted proof is missing or changed')
        capsule = Path(proof['result']).parent
        required = {'result.json', 'accepted-state.json', 'checkpoint.json', 'prompt.txt',
                    'agent-commands.log', 'nested.json', 'nested-closed', 'cleanup.json'}
        if not {str(capsule / name) for name in required}.issubset(proof['records']):
            raise ValueError('plan evidence: exact result, commands or cleanup is missing')
        captured_brief = False
        for input_path in proof['inputs']:
            inputs = bundle.decoded(read(input_path, count=bundle.MAX_READ))
            if inputs.get('task_id') != task or not isinstance(inputs.get('files'), list):
                raise ValueError('plan evidence: invalid selected input record')
            brief = Path(inputs['task']['brief'])
            brief = brief if brief.is_absolute() else plan.root / brief
            for entry in inputs['files']:
                name = entry.get('member', '')
                child = str(Path(input_path).parent / name)
                if (not name or Path(name).name != name or child not in files
                        or files[child]['sha256'] != entry.get('sha256')):
                    raise ValueError('plan evidence: exact selected inputs are missing or changed')
                captured_brief = captured_brief or entry['path'] == str(brief)
        if not captured_brief:
            raise ValueError('plan evidence: accepted proof lacks an exact captured task brief')
        result = bundle.decoded(read(proof['result'], count=bundle.MAX_READ))
        if (result.get('task_id') != task or result.get('status') != 'task_complete'
                or result.get('cleanup_complete') is not True):
            raise ValueError('plan evidence: result or cleanup does not match accepted proof')


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _index_v2(value):
    if (set(value) != {'schema', 'plan', 'generation', 'ledger', 'ledger_sha256', 'segments', 'tasks'}
            or value['schema'] != 2 or type(value['schema']) is not int
            or type(value['generation']) is not int or value['generation'] < 1
            or not isinstance(value['plan'], str) or not _hash(value['ledger_sha256'])
            or not isinstance(value['tasks'], dict) or not isinstance(value['ledger'], dict)
            or set(value['ledger']) != {'segment_id', 'original_path'}):
        raise ValueError('plan evidence: invalid schema 2 accepted index')
    segments = value['segments']
    if (not isinstance(segments, list) or not 1 <= len(segments) <= 3
            or any(not isinstance(item, dict) or set(item) != {
                'id', 'bundle', 'sha256', 'selection_sha256', 'allocation'} for item in segments)):
        raise ValueError('plan evidence: invalid accepted segments')
    ids = [item['id'] for item in segments]
    if (any(item not in ('00', '01', '02') for item in ids)
            or ids != sorted(set(ids)) or value['ledger']['segment_id'] not in ids):
        raise ValueError('plan evidence: invalid accepted segment IDs')
    bundle.path_text(value['ledger']['original_path'])
    for item in segments:
        allocation = item['allocation']
        if (not _hash(item['sha256']) or not _hash(item['selection_sha256'])
                or not isinstance(allocation, dict) or set(allocation) != {
                    'path', 'device', 'inode', 'mode', 'journal', 'run'}
                or any(type(allocation[key]) is not int or allocation[key] <= 0
                       for key in ('device', 'inode'))
                or type(allocation['mode']) is not int or allocation['mode'] != 0o700
                or not isinstance(allocation['run'], str)
                or re.fullmatch(r'[0-9a-f]{32}', allocation['run']) is None):
            raise ValueError('plan evidence: invalid accepted segment allocation')
        directory = bundle.path_text(item['bundle'])
        if directory != bundle.path_text(allocation['path']):
            raise ValueError('plan evidence: segment allocation does not match its bundle')
        bundle.path_text(allocation['journal'])


def _record_closure(records, roots):
    selected, visiting = {}, set()
    pending = [(reference, False) for reference in reversed(roots)]
    while pending:
        reference, leaving = pending.pop()
        if (not isinstance(reference, dict) or set(reference) != {'record_id', 'closure_sha256'}
                or not _hash(reference['record_id']) or not _hash(reference['closure_sha256'])):
            raise ValueError('plan evidence: invalid logical record reference')
        key = reference['record_id']
        if key not in records or records[key]['closure_sha256'] != reference['closure_sha256']:
            raise ValueError('plan evidence: logical record is missing or changed')
        if leaving:
            visiting.remove(key)
            selected[key] = records[key]
            continue
        if key in visiting:
            raise ValueError('plan evidence: cyclic logical record dependencies')
        if key in selected:
            continue
        visiting.add(key)
        pending.append((reference, True))
        pending.extend((dependency, False) for dependency in reversed(records[key]['dependencies']))
    return selected


def _ledger_v2(value, plan, index):
    import evidence_identity as identities
    if (not isinstance(value, dict) or set(value) != {
            'schema', 'plan', 'generation', 'previous_index_sha256', 'tasks', 'records', 'segments'}
            or type(value['schema']) is not int or value['schema'] != 2
            or value['plan'] != plan.path or value['generation'] != index['generation']
            or type(value['generation']) is not int or not _hash(value['previous_index_sha256'])
            or not isinstance(value['records'], dict) or value['tasks'] != index['tasks']
            or not isinstance(value['segments'], list)):
        raise ValueError('plan evidence: invalid schema 2 accepted ledger')
    for key, logical in value['records'].items():
        identities.finalize_record(logical)
        if key != logical['record_id']:
            raise ValueError('plan evidence: ledger record key does not match its identity')
    assigned = {}
    segment_ids = []
    for segment in value['segments']:
        if (not isinstance(segment, dict) or set(segment) != {'id', 'record_ids'}
                or not isinstance(segment['record_ids'], list)
                or any(not _hash(key) for key in segment['record_ids'])
                or segment['record_ids'] != sorted(set(segment['record_ids']))):
            raise ValueError('plan evidence: invalid ledger segment records')
        segment_ids.append(segment['id'])
        for key in segment['record_ids']:
            if key in assigned:
                raise ValueError('plan evidence: record assigned to multiple segments')
            assigned[key] = segment['id']
    if (segment_ids != [item['id'] for item in index['segments']]
            or set(assigned) != set(value['records'])):
        raise ValueError('plan evidence: ledger segment closure does not match its records')
    all_references = []
    for task, proof in value['tasks'].items():
        if not isinstance(proof, dict) or not isinstance(proof.get('record_refs'), list) or not proof['record_refs']:
            raise ValueError('plan evidence: accepted task lacks logical record references')
        refs = proof['record_refs']
        ids = [ref.get('record_id') for ref in refs if isinstance(ref, dict)]
        if len(ids) != len(refs) or any(not _hash(key) for key in ids) or ids != sorted(set(ids)):
            raise ValueError('plan evidence: invalid accepted task record references')
        closure = _record_closure(value['records'], refs)
        covered = {}
        for logical in closure.values():
            for member in logical['members']:
                covered.setdefault(member['original_path'], []).append((logical, member))
        results = [(logical, member) for logical, member in covered.get(proof.get('result'), [])
                   if member['role'] == 'result' and member['sha256'] == proof.get('sha256')
                   and logical['context']['task'] == task and logical['context']['workflow'] == plan.path
                   and logical['status'] == 'passed' and logical['completeness'] == 'complete'
                   and logical['cleanup']['state'] == 'complete']
        if (not results or not isinstance(proof.get('records'), dict)
                or any(not any(member['sha256'] == hashed for _, member in covered.get(path, []))
                       for path, hashed in proof['records'].items())):
            raise ValueError('plan evidence: task proof lacks its exact logical result or supporting members')
        all_references.extend(refs)
    if set(_record_closure(value['records'], all_references)) != set(value['records']):
        raise ValueError('plan evidence: accepted ledger contains unclaimed records')
    return assigned


class _RecordUnavailable(LookupError):
    """Internal absence after the locator and ledger have been verified."""


@contextmanager
def _verified_index_v2(plan, index, *, record_id=None):
    """Pin the locator's exact ledger and only the requested dependency segments."""
    _index_v2(index)
    if index['plan'] != plan.path:
        raise ValueError('plan evidence: accepted index belongs to another plan')
    parent = _parent(plan)
    with ExitStack() as stack:
        state = stack.enter_context(bundle.retention.Store(parent / 'retention').inspection())
        if state is None:
            raise ValueError('plan evidence: accepted segments have no recorded owner')
        allocations = {}
        entries = [*state['history'], state]
        for number, record in bundle.retention.latest_allocations(entries):
            allocations[record['path']] = dict(record, journal=str(parent / 'retention'),
                                               run=entries[number]['run'])
        opened = {}
        def open_segment(segment_id):
            if segment_id in opened:
                return opened[segment_id]
            segment = next(item for item in index['segments'] if item['id'] == segment_id)
            directory = bundle.path_text(segment['bundle'])
            if directory.parent != parent or allocations.get(str(directory)) != segment['allocation']:
                raise ValueError('plan evidence: accepted segment has no exact recorded owner')
            verified, read = stack.enter_context(bundle.verified_record(
                segment['allocation'], os.geteuid(), checkout=plan.root))
            if (verified['sha256'] != segment['sha256']
                    or verified['selection_sha256'] != segment['selection_sha256']):
                raise ValueError('plan evidence: accepted segment changed')
            opened[segment_id] = verified, read
            return verified, read
        ledger_verified, ledger_read = open_segment(index['ledger']['segment_id'])
        raw = ledger_read(index['ledger']['original_path'], count=bundle.MAX_READ)
        if _digest(raw) != index['ledger_sha256']:
            raise ValueError('plan evidence: accepted ledger checksum mismatch')
        value = bundle.decoded(raw)
        assigned = _ledger_v2(value, plan, index)
        records = value['records']
        if record_id is None:
            required = records
        elif record_id not in records:
            raise _RecordUnavailable('plan evidence: requested logical record is absent')
        else:
            required = _record_closure(records, [dict(record_id=record_id,
                closure_sha256=records[record_id]['closure_sha256'])])
        tasks = value['tasks'] if record_id is None else {
            task: proof for task, proof in value['tasks'].items()
            if record_id in _record_closure(records, proof['record_refs'])}
        if not tasks:
            raise ValueError('plan evidence: requested record has no accepted task')
        task_records = _record_closure(records, [ref for proof in tasks.values() for ref in proof['record_refs']])
        for key, logical in task_records.items():
            verified, _ = open_segment(assigned[key])
            actual = {entry['record_id']: entry for entry in verified['manifest'].get('records', [])}
            if actual.get(key) != logical:
                raise ValueError('plan evidence: ledger logical record does not match its segment')
        files, readers, provenance = {}, {}, {}
        for verified, read in opened.values():
            for entry in verified['manifest']['files']:
                if entry['path'] in files and {
                        key: value for key, value in files[entry['path']].items() if key != 'member'} != {
                        key: value for key, value in entry.items() if key != 'member'}:
                    raise ValueError('plan evidence: conflicting original proof member')
                files[entry['path']], readers[entry['path']] = entry, read
            physical = {entry['member']: entry for entry in verified['manifest']['files']}
            logical_records = {item['record_id']: item for item in verified['manifest'].get('records', [])}
            for mapping in verified['manifest'].get('member_map', []):
                original_provenance = mapping['original_provenance']
                provenance[(mapping['record_id'], mapping['member_id'])] = original_provenance
                original = original_provenance['original_path']
                entry = dict(physical[mapping['physical_member']], path=original,
                             allocation=original_provenance['source_allocation'],
                             identity=original_provenance['identity'])
                if original in files and {
                        key: value for key, value in files[original].items() if key != 'member'} != {
                        key: value for key, value in entry.items() if key != 'member'}:
                    raise ValueError('plan evidence: conflicting logical original proof member')
                files[original] = entry
                def logical_read(path, *, mapping=mapping, read=read, logical_records=logical_records, **kwargs):
                    return read(record_id=mapping['record_id'], member_id=mapping['member_id'],
                        closure_sha256=logical_records[mapping['record_id']]['closure_sha256'], **kwargs)
                readers[original] = logical_read
        def read_original(path, **kwargs):
            if path not in readers:
                raise ValueError('plan evidence: exact proof member is missing')
            return readers[path](path, **kwargs)
        _validate_task_proofs(dict(value, tasks=tasks), plan, files, read_original)
        def read_member(key, member_id, *, count=bundle.MAX_READ):
            logical = required[key]
            members = [member for member in logical['members'] if member['member_id'] == member_id]
            if len(members) != 1:
                raise ValueError('plan evidence: requested logical member is absent')
            member = members[0]
            _, read = opened[assigned[key]]
            # Complete bytes and their logical mapping were verified when the
            # held archive scope opened. A diagnostic slice must not exclude
            # large media members from exact metadata/closure resolution.
            return read(record_id=key, member_id=member_id,
                        closure_sha256=logical['closure_sha256'], count=count)
        yield dict(index=index, ledger=value, records=required, read=read_member, provenance=provenance,
                   bundles=[str(Path(item['bundle']) / 'evidence.zip') for item in index['segments']
                            if item['id'] in opened])


class _ReferenceScope:
    def __init__(self, plan, document, workflow=None):
        self.plan, self.checkout = plan, Path(plan.root)
        self.workflow = workflow
        self.document = Path(document)
        if not self.document.is_absolute():
            self.document = self.checkout / self.document
        self.document = Path(os.path.abspath(self.document))
        if not self.document.is_relative_to(self.checkout):
            raise ValueError('plan evidence: declaring document escapes checkout')
        self._pinned = None

    @contextmanager
    def pinned(self):
        """Reuse verification only while its owner/archive descriptors stay held."""
        if self._pinned is not None:
            raise ValueError('plan evidence: reference scope is already pinned')
        with ExitStack() as stack:
            self._pinned = stack, {}
            try:
                yield self
            finally:
                self._pinned = None

    def locator(self):
        if self.workflow is None:
            return locator(self.plan)
        import runner_evidence
        return runner_evidence.reference_locator(self.checkout, self.workflow)

    @contextmanager
    def __call__(self, path, *, record_id):
        if self._pinned is not None:
            stack, opened = self._pinned
            key = str(path), record_id
            if key not in opened:
                opened[key] = (_read(path), stack.enter_context(self._open(path, record_id=record_id)))
            raw, verified = opened[key]
            if _read(path) != raw:
                raise ValueError('plan evidence: locator changed during resolution')
            yield verified
            if _read(path) != raw:
                raise ValueError('plan evidence: locator changed during resolution')
            return
        with self._open(path, record_id=record_id) as verified:
            yield verified

    @contextmanager
    def _open(self, path, *, record_id):
        if path != locator(self.plan):
            raise ValueError('plan evidence: locator is outside the trusted plan scope')
        raw = _read(path)
        value = bundle.decoded(raw)
        if not isinstance(value, dict) or value.get('schema') != 2:
            raise ValueError('plan evidence: legacy locator cannot satisfy an exact reference')
        journal = _parent(self.plan).parent / 'retention'
        with bundle.retention.directory_descriptor(journal) as fd, \
                _verified_index_v2(self.plan, value, record_id=record_id) as verified:
            info = os.fstat(fd)
            owner = dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode,
                         uid=info.st_uid, gid=info.st_gid)
            for logical in [verified['records'][record_id]]:
                declared = logical['context']['owner']
                if (declared['journal'] != str(journal) or declared['identity'] != owner
                        or declared['caller'] != dict(uid=os.geteuid(), gid=os.getegid())):
                    raise ValueError('plan evidence: logical owner does not match the trusted journal')
            yield verified
            if _read(path) != raw:
                raise ValueError('plan evidence: locator changed during resolution')


def reference_scope(plan, *, document, workflow=None):
    """Authorize one validated plan locator; JSON provenance grants no access."""
    return _ReferenceScope(plan, document, workflow)


def resolve_reference(reference, *, consumer, read_scope, count=bundle.MAX_READ):
    """Resolve an immutable selector inside a trusted caller-owned read scope."""
    import evidence_identity as identities
    if type(count) is not int or not 0 <= count <= bundle.MAX_READ:
        raise ValueError('plan evidence: invalid member read bound')
    identities.validate_consumer(consumer)
    destination, selector = identities.parse_reference(reference)
    if selector is None:
        raise identities.MalformedEvidence('plan evidence: an exact evidence selector is required')
    if not callable(read_scope) or not hasattr(read_scope, 'checkout') or not hasattr(read_scope, 'document'):
        raise identities.MalformedEvidence('plan evidence: expected a trusted explicit read scope')
    checkout = Path(read_scope.checkout)
    destination = Path(destination)
    if destination.is_absolute():
        raise identities.MalformedEvidence('plan evidence: locator destination must be relative')
    path = Path(os.path.abspath(Path(read_scope.document).parent / destination))
    if not path.is_relative_to(checkout):
        raise identities.MalformedEvidence('plan evidence: locator escapes checkout')
    expected_reference = dict(kind='evidence', **selector)
    if expected_reference not in consumer['references']:
        raise identities.EvidenceContextError('plan evidence: selector is not declared by its consumer')
    if getattr(read_scope, 'workflow', None) is not None:
        if path != read_scope.locator():
            raise identities.EvidenceContextError('plan evidence: locator is outside the trusted runner scope')
        import runner_evidence
        return runner_evidence.resolve_reference(checkout,
            dict(schema=1, workflow=read_scope.workflow, **selector), consumer=consumer,
            count=count, metadata=True)
    try:
        with read_scope(path, record_id=selector['record_id']) as verified:
            record = verified['records'][selector['record_id']]
            if record['closure_sha256'] != selector['closure_sha256']:
                raise identities.EvidenceIntegrityError('plan evidence: requested closure changed')
            with bundle.retention.directory_descriptor(checkout) as fd:
                info = os.fstat(fd)
                repository = dict(root=str(checkout), device=info.st_dev, inode=info.st_ino, uid=os.geteuid())
            if any(item['context']['repository'] != repository for item in verified['records'].values()):
                raise identities.EvidenceContextError('plan evidence: evidence belongs to another checkout')
            identities.match_context(record, consumer)
            member = next((item for item in record['members'] if item['member_id'] == selector['member_id']), None)
            if member is None:
                raise bundle.LogicalEvidenceUnavailable([selector])
            data = verified['read'](selector['record_id'], selector['member_id'], count=count)
            return dict(record=record, member=member, closure=verified['records'],
                        provenance=verified['provenance'][(selector['record_id'], selector['member_id'])],
                        data=data, data_complete=len(data) == member['bytes'],
                        bundles=verified['bundles'])
    except _RecordUnavailable:
        raise bundle.LogicalEvidenceUnavailable([selector]) from None


def generate_reference(*, consumer, selector, read_scope):
    """Generate only a verified exact member destination, relative to its document."""
    reference, _ = _generated_reference(consumer, selector, read_scope)
    return reference


def _generated_reference(consumer, selector, read_scope):
    import evidence_identity as identities
    identities.validate_consumer(consumer)
    identities._object(selector, {'kind', 'record_id', 'member_id', 'closure_sha256'}, 'selector')
    if selector not in consumer['references'] or selector['kind'] != 'evidence':
        raise identities.EvidenceContextError('plan evidence: undeclared exact member')
    destination = os.path.relpath(read_scope.locator(), read_scope.document.parent)
    reference = destination + '#onpc-evidence-v1:' + ':'.join(
        selector[key] for key in ('record_id', 'member_id', 'closure_sha256'))
    resolved = resolve_reference(reference, consumer=consumer, read_scope=read_scope, count=0)
    return reference, resolved


def collect_document_references(plan, declaration):
    """Collect explicit occurrences only; prose never manufactures a claim/context."""
    import evidence_identity as identities
    identities._object(declaration, {'document', 'sha256', 'references'}, 'document declaration')
    identities._text(declaration['document'])
    identities._hex(declaration['sha256'])
    path = document_checks.checkout_document(plan.root, declaration['document'])
    text = document_checks.read_text(path)
    if _digest(text.encode('utf-8')) != declaration['sha256']:
        raise ValueError('plan evidence: document changed since declaration')
    claims = declaration['references']
    if type(claims) is not list or not 1 <= len(claims) <= 256:
        raise ValueError('plan evidence: expected 1..256 explicit document references')
    links = list(references(text))
    by_start = {link.start: link for link in links}
    selected, seen = [], set()
    for claim in claims:
        identities._object(claim, {'start', 'consumer', 'selector', 'workflow'}, 'document claim')
        identities._integer(claim['start'])
        identities.validate_consumer(claim['consumer'])
        if claim['workflow'] is not None:
            identities._text(claim['workflow'])
        if claim['start'] in seen or claim['start'] not in by_start:
            raise ValueError('plan evidence: duplicate or absent declared link occurrence')
        seen.add(claim['start'])
        selected.append((by_start[claim['start']], claim))
    # A reference definition can serve several claims. Rewriting it must not
    # silently change an undeclared use or a use requesting another member.
    spans = {(link.destination_start, link.destination_end) for link, _ in selected}
    if any(link.start not in seen and (link.destination_start, link.destination_end) in spans
           for link in links):
        raise ValueError('plan evidence: shared definition has undeclared uses')
    return path, text, selected


class ReferenceRefused(ValueError):
    """Finite policy findings, without link text or private reader errors."""
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics[:16]
        super().__init__('reference gate: ' + json.dumps(self.diagnostics, sort_keys=True))


def _claim_bytes(text, link):
    # Include surrounding result/target wording, not merely the clickable label.
    start = text.rfind('\n', 0, link.start) + 1
    end = text.find('\n', link.end)
    end = len(text) if end < 0 else end
    # Destinations are identity, not result wording. Preserve every other byte;
    # reference definitions live outside the claim's use-site line.
    if start <= link.destination_start < link.destination_end <= end:
        return (text[start:link.destination_start] + text[link.destination_end:end]).encode('utf-8')
    return text[start:end].encode('utf-8')


def check_document_references(plan, declaration, *, contracts, retained=(), active=False,
                              active_consumers=()):
    """Apply owning roles to finite declared occurrences, without granting a pass.

    `contracts` comes from the workflow owner, independently of document JSON.
    Previous bindings are owner-retained classification, never caller-selected
    proof. Exact identity/ownership resolution still belongs to existing readers.
    """
    with ExitStack() as stack:
        return _check_document_references(plan, declaration, contracts=contracts,
            retained=retained, active=active, active_consumers=active_consumers, stack=stack)


def _check_document_references(plan, declaration, *, contracts, retained, active, active_consumers, stack):
    import evidence_identity as identities
    import evidence_policy as policy
    path, text, selected = collect_document_references(plan, declaration)
    decisions, anchors, scopes = [], {}, {}
    if (not isinstance(contracts, dict) or len(contracts) > 256 or len(retained) > 256
            or type(active) is not bool or len(active_consumers) > 256):
        raise ValueError('plan evidence: invalid finite owning contracts')
    for link, claim in selected:
        consumer = claim['consumer']
        contract = contracts.get(consumer['consumer_id'])
        arguments = dict(document=declaration['document'], line=link.line,
            reference=text[link.start:link.end], claim=_claim_bytes(text, link),
            consumer=consumer, contract=contract,
            active=active or consumer['consumer_id'] in active_consumers)
        # Role authority is checked before any I/O or availability exception.
        initial = policy.assess_reference([], **arguments)
        if initial.blocked:
            decisions.append(initial)
            continue
        if consumer['revision_sha256'] != _digest(arguments['claim']):
            decisions.append(policy.assess_reference(policy.Condition.STALE,
                expected=consumer['revision_sha256'], actual=_digest(arguments['claim']), **arguments))
            continue
        conditions, actual = [], None
        try:
            if claim['selector'] is not None:
                workflow = claim['workflow']
                if workflow not in scopes:
                    scopes[workflow] = stack.enter_context(reference_scope(plan,
                        document=declaration['document'], workflow=workflow).pinned())
                scope = scopes[workflow]
                _, resolved = _generated_reference(consumer, claim['selector'], scope)
                _document_source(plan, path, link, resolved, (consumer, scope))
            else:
                target = local_destination(link.destination)
                if target is None or claim['workflow'] is not None:
                    raise identities.EvidenceContextError('plan evidence: expected local instruction reference')
                if ((target.fragment or '').startswith('onpc-evidence')
                        or consumer['role'] == 'optional_presentation'
                        and 'output/test-runs/' in target.path):
                    raise identities.EvidenceContextError('plan evidence: evidence cannot use presentation authority')
                actual = dict(kind='document', destination=os.path.normpath(target.path),
                              fragment=target.fragment or '')
                if actual not in consumer['references'] or any(
                        item['kind'] == 'evidence' for item in consumer['references']):
                    raise identities.EvidenceContextError('plan evidence: undeclared document destination')
                condition = document_checks.link_condition(path, text, link, anchors=anchors)
                if condition is not None:
                    conditions.append(condition)
        except (OSError, ValueError) as error:
            conditions.append(policy.condition_for_exception(error))
        binding = initial.binding
        previous = next((item for item in retained if item == binding), None)
        if previous is None:
            previous = next((item for item in retained
                if isinstance(item, policy.ReferenceBinding)
                and item.consumer_id == consumer['consumer_id']), None)
        decisions.append(policy.assess_reference(conditions, retained=previous,
            expected=consumer['references'], actual=actual, **arguments))
    return decisions


def require_document_references(plan, declaration, **options):
    decisions = check_document_references(plan, declaration, **options)
    failures = [item.diagnostic.payload() for item in decisions if item.blocked]
    if failures:
        raise ReferenceRefused(failures)
    return decisions


def _document_source(plan, path, link, resolved, scope):
    """An old spelling must select the proven member, never another existing report."""
    import evidence_identity as identities
    target = local_destination(link.destination)
    if target is None:
        raise ValueError('plan evidence: evidence destination must be local')
    source = Path(os.path.abspath(path.parent / target.path))
    if target.fragment is not None:
        # Strict parser refuses generic headings, malformed selectors and URL tricks.
        actual = resolve_reference(link.destination, consumer=scope[0], read_scope=scope[1], count=0)
        if (actual['record'] != resolved['record'] or actual['member'] != resolved['member']):
            raise ValueError('plan evidence: existing link selects another member')
    member = resolved['member']
    if target.fragment is None and str(source) != member['original_path']:
        error = identities.EvidenceContextError('plan evidence: destination is not the selected original member')
        error.expected_identity = _digest(member['original_path'].encode('utf-8'))
        error.actual_identity = _digest(str(source).encode('utf-8'))
        raise error
    source = Path(member['original_path'])
    if not source.is_relative_to(plan.root):
        raise ValueError('plan evidence: original destination escapes checkout')
    if any(parent.is_symlink() for parent in (source, *source.parents)):
        raise ValueError('plan evidence: original destination follows a symlink')
    try:
        source.lstat()
    except FileNotFoundError:
        return  # Exact archive was already verified; no recreated original.
    # Reappearance is not archive-only authority. Normal source discovery holds
    # the live owner and verifies its allocation and complete file identity.
    with bundle.Selection(plan.root, os.geteuid(), os.getegid(),
            [resolved['record']['context']['target']] if resolved['record']['context']['target'] else [],
            [], [], references=[str(source)], plan_namespace=plan_namespace(plan.path)) as selected:
        entry = selected.files[str(source)][0]
        if (entry['sha256'] != member['sha256'] or entry['bytes'] != member['bytes']
                or entry['allocation'] != member['source_allocation']
                or entry['identity'] != resolved['provenance']['identity']):
            raise ValueError('plan evidence: live original does not match selected proof')


def _queue_destination_allowed(text, link, state):
    if state is None:
        return False
    offset = 0
    for line in text.splitlines(keepends=True):
        cells = line.split('|')
        if (len(cells) >= 8 and cells[1].strip() in ('[ ]', '[x]')
                and (cells[2].strip() == state['task_id']
                     or state.get('queue_before', {}).get(cells[2].strip()) is True)):
            start = offset + sum(len(cell) + 1 for cell in cells[:6])
            if any(start + item.destination_start == link.destination_start
                   and start + item.destination_end == link.destination_end
                   for item in simple_inline_references(cells[6])):
                return True
        offset += len(line)
    return False


def preview_document_links(plan, declaration, *, state=None):
    """Verify finite declared claims and return destination-only edits; never write."""
    with ExitStack() as stack:
        return _preview_document_links(plan, declaration, state=state, stack=stack)


def _preview_document_links(plan, declaration, *, state, stack):
    import evidence_policy as policy
    import evidence_identity as identities
    path, text, selected = collect_document_references(plan, declaration)
    edits, scopes = {}, {}
    for link, claim in selected:
        try:
            workflow = claim['workflow']
            if workflow not in scopes:
                scopes[workflow] = stack.enter_context(reference_scope(plan,
                    document=declaration['document'], workflow=workflow).pinned())
            scope = scopes[workflow]
            destination, resolved = _generated_reference(claim['consumer'], claim['selector'], scope)
            _document_source(plan, path, link, resolved, (claim['consumer'], scope))
        except (ValueError, OSError) as error:
            condition = policy.condition_for_exception(error)
            context = claim['consumer']['expected_context']
            error.reference_diagnostic = policy.Diagnostic(policy.Severity.BLOCK, condition,
                declaration['document'], link.line,
                getattr(error, 'expected_identity', identities.record_id(context) if context is not None else None),
                getattr(error, 'actual_identity',
                    claim['selector'].get('record_id') if isinstance(claim['selector'], dict) else None),
                policy.RECOVERY_ACTIONS[condition]).payload()
            raise
        before = text[link.destination_start:link.destination_end]
        if (path == plan.root / plan.queue and before != destination
                and not _queue_destination_allowed(text, link, state)):
            error = ValueError('plan evidence: protected queue destination is outside authorized Estimate cells')
            error.reference_diagnostic = policy.Diagnostic(policy.Severity.BLOCK, policy.Condition.PROTECTED,
                declaration['document'], link.line, None, None,
                policy.RECOVERY_ACTIONS[policy.Condition.PROTECTED]).payload()
            raise error
        edit = dict(start=link.destination_start, end=link.destination_end, before=before,
                    after=destination, selector=claim['selector'],
                    member_sha256=resolved['member']['sha256'])
        span = (edit['start'], edit['end'])
        if span in edits and edits[span] != edit:
            raise ValueError('plan evidence: shared definition has conflicting claims')
        edits[span] = edit
    # Canonical JSON detaches caller-owned mutable inputs from the preview.
    preview = dict(schema='onpc-evidence-link-preview', version=1,
                   declaration=declaration, edits=sorted(edits.values(), key=lambda item: item['start']))
    preview['sha256'] = bundle.digest(bundle.encoded(preview))
    return bundle.decoded(bundle.encoded(preview))


def apply_document_links(plan, preview, *, state=None):
    """Apply an authorized preview only after rechecking its exact document and proof."""
    if (not isinstance(preview, dict) or set(preview) != {'schema', 'version', 'declaration', 'edits', 'sha256'}
            or preview['schema'] != 'onpc-evidence-link-preview'
            or type(preview['version']) is not int or preview['version'] != 1):
        raise ValueError('plan evidence: invalid document preview')
    if preview['sha256'] != bundle.digest(bundle.encoded(
            {key: value for key, value in preview.items() if key != 'sha256'})):
        raise ValueError('plan evidence: document preview or exact proof changed')
    fresh = preview_document_links(plan, preview['declaration'], state=state)
    if fresh != preview:
        raise ValueError('plan evidence: document preview or exact proof changed')
    path, text, _ = collect_document_references(plan, preview['declaration'])
    updated = text
    for edit in reversed(fresh['edits']):
        updated = updated[:edit['start']] + edit['after'] + updated[edit['end']:]
    if updated == text:
        return False
    if document_checks.read_text(path) != text:
        raise ValueError('plan evidence: document changed before rewrite')
    _atomic(path, updated.encode('utf-8'))
    return True


@contextmanager
def _verified_index(plan, index):
    """Read legacy proof within the same pinned scope that verified its ledger."""
    if index.get('schema') == 2:
        with _verified_index_v2(plan, index):
            yield None, None
            return
    if index['plan'] != plan.path:
        raise ValueError('plan evidence: accepted index belongs to another plan')
    path = Path(index['bundle'])
    if path.parent.parent != _parent(plan):
        raise ValueError('plan evidence: accepted bundle belongs to another owner')
    # Inspect the published allocation, not a source allocation from its manifest.
    # Keep its verified descriptor open for subsequent proof reads as well.
    store = bundle.retention.Store(_parent(plan) / 'retention')
    with store.inspection() as state:
        records = [record for _, record in bundle.retention.latest_allocations([*state['history'], state])
                   if record['path'] == str(path.parent)]
        if len(records) != 1:
            raise ValueError('plan evidence: accepted index does not match verified proof')
        with bundle.verified_record(records[0], os.geteuid(), checkout=plan.root) as (verified, read):
            actual = _verified_ledger(records[0], plan, verified, read)[1]
            if (actual['sha256'] != index['sha256']
                    or actual['selection_sha256'] != index['selection_sha256']):
                raise ValueError('plan evidence: accepted bundle changed')
            if actual != index:
                raise ValueError('plan evidence: accepted index does not match verified proof')
            yield verified, read


def _verify_index(plan, index):
    with _verified_index(plan, index):
        pass


def _replacement_closure(plan, current, intent):
    """A new locator must keep every member the previous locator required.

    Run under the publication owner/writer, before publishing the locator. The
    journal, rather than paths in a document, supplies both allocation identities.
    A renewed task may select a later result, but its earlier proof still survives.
    """
    if current is None:
        return
    original = intent['original']
    records = ([] if original is None else [record for _, record in
        bundle.retention.latest_allocations([*original['history'], original])])
    matches = [record for record in records
               if str(Path(record['path']) / 'evidence.zip') == current.get('bundle')]
    if current.get('schema') != 1 or len(matches) != 1:
        raise ValueError('plan evidence: previous locator has no exact publication owner')
    with bundle.verified_record(matches[0], os.geteuid(), checkout=plan.root) as (old, read):
        if _verified_ledger(matches[0], plan, old, read)[1] != current:
            raise ValueError('plan evidence: previous locator does not match retained proof')
        with bundle.verified_record(intent['staging'], os.geteuid(), checkout=plan.root) as (new, _):
            files = {entry['path']: entry for entry in new['manifest']['files']}
            for entry in old['manifest']['files']:
                replacement = files.get(entry['path'], {})
                if ({key: value for key, value in entry.items() if key != 'member'} !=
                        {key: value for key, value in replacement.items() if key != 'member'}):
                    raise ValueError('plan evidence: replacement omits or changes required proof')
            directories = {entry['path']: entry for entry in new['manifest'].get('directories', [])}
            for entry in old['manifest'].get('directories', []):
                if directories.get(entry['path']) != entry:
                    raise ValueError('plan evidence: replacement omits or changes required directory proof')


@contextmanager
def recovered(plan):
    """Recover publication, then hold one verified read scope; never cache proof."""
    parent = _parent(plan)
    index_path = parent.parent / 'accepted-evidence.json'
    store = bundle.retention.Store(parent / 'retention')
    if store.path.exists():
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with store.retirement(fd) as authorize, store.locked(fd, 'writer.lock', publication=True):
                intent = bundle.retention.read_publication(store, fd)
                if intent is not None and intent['phase'] == 'committed':
                    current_state = store.read(fd)
                    bundle.retention.finished_owner(fd, current_state)
                    replacement_state, _ = bundle.retention.publication_states(intent)
                    if current_state not in (intent['original'], replacement_state):
                        raise ValueError('plan evidence: publication owner changed; index preserved')
                    bundle.retention.committed_publication_audit(intent,
                        lambda record: _ledger(record, plan))
                    ledger, replacement = _ledger(intent['staging'], plan)
                    current, raw = _index(index_path)
                    if current != replacement:
                        if _digest(raw) != ledger['previous_index_sha256']:
                            raise ValueError('plan evidence: accepted index changed during publication')
                        _replacement_closure(plan, current, intent)
                        _atomic(index_path, bundle.encoded(replacement))
                bundle.retention.recover_publication(store, fd,
                    verify=lambda record: _ledger(record, plan), authorize=authorize)
    index, _ = _index(index_path)
    if index is None:
        yield None, None, None
    else:
        with _verified_index(plan, index) as (verified, read):
            yield index, verified, read


def recover(plan):
    with recovered(plan) as (index, _, _):
        return index


def _navigation_reference(plan, source):
    """Control locators describe mutable state; they are not retained payloads."""
    if source == locator(plan):
        return True
    parts = source.relative_to(plan.root / 'output/test-runs').parts
    return (len(parts) == 6 and parts[:2] == ('host', 'plans')
            and re.fullmatch(r'[0-9a-f]{64}', parts[2]) is not None
            and parts[3:] == ('evidence', 'retention', 'capture-publication.json'))


def _references(plan, result, state):
    """Only explicit checkout-storage references are inputs to proof publication."""
    texts = [(check['evidence'], None) for check in result['checks']
             if _structured(check['evidence']) is None]
    queue = (plan.root / plan.queue).read_text()
    texts.append((queue, state['task_id']))
    found = set()
    for text, selected in texts:
        # Parse the whole queue so reference definitions outside the selected
        # row resolve, while only that row contributes publication inputs.
        selected_lines = {number for number, line in enumerate(text.splitlines(), 1)
                          if selected is None or re.match(
                              r'^\| \[[ x]\] \| ' + re.escape(selected) + r' \|', line)}
        values = [(link.destination, True) for link in references(text)
                  if link.line in selected_lines]
        prose = evidence_prose(text)
        if selected is not None:
            prose = '\n'.join(line for number, line in enumerate(prose.splitlines(), 1)
                              if number in selected_lines)
        # Code-delimited and bare storage paths are intentional legacy evidence
        # inputs, not another Markdown parser. Examples and link labels are masked
        # by the shared syntax owner before this compatibility route runs.
        legacy = re.finditer(
            r'`([^`\n]+)`|((?:/[^\s`<>\[\]()]+)?output/test-runs/[^\s`<>\[\](),;]+)', prose)
        values += [(code or bare.rstrip('.:!?\'"'), False)
                   for code, bare in (match.groups() for match in legacy)
                   if not code or re.match(r'^(?:/|\.{1,2}/|output/test-runs/)', code)]
        for value, markdown in values:
            if markdown:
                target = local_destination(value)
                if target is None:
                    continue
                value = target.path
            else:
                # Legacy code/prose names are literal filesystem paths, not
                # URLs. Keep '?' and '%' bytes; retain the old #fragment suffix.
                value = value.split('#', 1)[0]
            if 'output/test-runs/' not in value:
                continue
            source = Path(value)
            if not source.is_absolute():
                base = ((plan.root / plan.queue).parent
                        if (markdown and selected is not None) or value.startswith('../') else plan.root)
                source = base / source
            # Resolve lexical '..' without following any source symlink.
            source = Path(os.path.abspath(source))
            if not source.is_relative_to(plan.root / 'output/test-runs'):
                raise ValueError('plan evidence: reference escapes checkout storage')
            if not _navigation_reference(plan, source):
                found.add(str(source))
    return sorted(found)


def _structured(text):
    """Recognize the explicit versioned handoff; ordinary prose stays legacy."""
    if not isinstance(text, str) or not text.lstrip().startswith('{'):
        return None
    try:
        value = bundle.decoded(text)
    except ValueError:
        if 'onpc-plan-evidence' in text:
            raise ValueError('plan evidence: malformed structured handoff') from None
        return None
    if not isinstance(value, dict) or value.get('schema') != 'onpc-plan-evidence':
        return None
    if (set(value) != {'schema', 'version', 'reference', 'consumer', 'record'}
            or type(value['version']) is not int or value['version'] != 1):
        raise ValueError('plan evidence: unsupported structured handoff')
    return value


def consume(plan, state, result, *, register=True):
    """Register exact producer-issued references through authenticated readers.

    Producer declarations select context; they gain authority only after the
    runner's verified cumulative publication matches that complete context and
    closure. Registration also binds the ordinary task, attempt and check claim.
    """
    import evidence_identity as identities
    import runner_evidence
    registrations = dict(state.get('evidence_consumers', {}))
    for number, check in enumerate(result.get('checks', [])):
        declaration = _structured(check['evidence'])
        if declaration is None:
            continue
        consumer = declaration['consumer']
        identities.validate_consumer(consumer)
        reference = declaration['reference']
        if (not isinstance(reference, dict) or set(reference) != {
                'schema', 'workflow', 'record_id', 'member_id', 'closure_sha256'}):
            raise ValueError('plan evidence: invalid runner reference')
        context = consumer['expected_context']
        record = identities.finalize_record(declaration['record'])
        # Only the installed controllers' own post-cleanup terminal captures
        # establish installed acceptance. The generic regression command is a
        # supporting invocation record, including harness qualification runs.
        installed = (context is not None and context['target'] and (
            context['workflow'] == 'system' and context['check'] == 'system'
            or context['workflow'] == 'e2e' and context['check'] == 'invocation'))
        selected = dict(kind='evidence', **{key: reference[key]
            for key in ('record_id', 'member_id', 'closure_sha256')})
        if (not isinstance(context, dict) or context['target'] != check['target']
                or reference['workflow'] != context['workflow']
                or selected not in consumer['references']
                or record['record_id'] != reference['record_id']
                or record['closure_sha256'] != reference['closure_sha256']
                or record['context'] != context
                or record['status'] != check['result']
                or check['kind'] == 'installed' and not installed
                or consumer['state'] not in ('working', 'suspended', 'accepted')
                or check['result'] == 'passed' and consumer['role'] != 'required_evidence'):
            raise identities.EvidenceContextError('plan evidence: structured check scope or verdict mismatch')
        binding = dict(task_id=state['task_id'], task=state['task'],
            attempt=state.get('evidence_attempt'), check=number)
        key = identities.digest(binding)
        registered = dict(binding=binding, claim_sha256=_digest(bundle.encoded(check)),
                          reference=reference, consumer=consumer)
        if key in registrations and registrations[key] != registered:
            raise identities.EvidenceContextError('plan evidence: registered check claim changed')
        # count=0 verifies the complete archive/closure without materializing a
        # potentially large required-media member into the controller's memory.
        runner_evidence.resolve_reference(plan.root, reference, consumer=consumer, count=0)
        registrations[key] = registered
    if register and registrations:
        state['evidence_consumers'] = registrations
    return registrations


def _targets(run, state):
    """Read evidence from the retained execution selection as well as task targets."""
    targets = list(state['task']['targets'])
    try:
        saved = bundle.decoded(_read(Path(run) / 'vm.json'))
    except FileNotFoundError:
        return targets  # Legacy and host-only callers have no saved VM binding.
    if not isinstance(saved, dict) or set(saved) != {'vm'}:
        raise ValueError('plan evidence: invalid retained VM selection')
    binding = saved['vm']
    if binding is None:
        return targets
    if isinstance(binding, str):
        selected = [binding]
    elif (isinstance(binding, dict) and set(binding) == {'concurrency', 'vms'}
            and type(binding['concurrency']) is int and binding['concurrency'] > 0
            and isinstance(binding['vms'], list) and binding['vms']):
        selected = binding['vms']
    else:
        raise ValueError('plan evidence: invalid retained VM selection')
    if (any(not isinstance(target, str) or not target for target in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError('plan evidence: invalid retained VM selection')
    return list(dict.fromkeys([*targets, *selected]))


def _instruction_gate(plan, path, text, *, previous=None, declared=()):
    """Plan-owned reading links are required; unchanged history is not a scan.

    Startup calls this on the current master/brief instruction closure. At
    publication only new/changed claims are inspected against captured bytes.
    Evidence destinations are handled by authenticated collection, not stat().
    """
    import evidence_policy as policy
    old = set() if previous is None else {
        (_claim_bytes(previous, link), link.destination)
        for link in references(previous)}
    failures, anchors = [], {}
    for link in references(text):
        if link.start in declared:
            continue  # The independently declared role was checked first.
        target = local_destination(link.destination)
        if target is None or 'output/test-runs/' in target.path:
            continue
        if previous is not None and (_claim_bytes(text, link), link.destination) in old:
            continue
        condition = document_checks.link_condition(path, text, link, anchors=anchors)
        if condition is not None:
            failures.append(policy.Diagnostic(policy.Severity.BLOCK, condition,
                str(path.relative_to(plan.root)), link.line, None, None,
                'repair_required_instruction_reference').payload())
            if len(failures) == 16:
                break
    if failures:
        raise ReferenceRefused(failures)


def _declared_gate(plan, state):
    """A workflow may register finite independent contracts before a turn."""
    documents = state.get('reference_documents', [])
    if not isinstance(documents, list) or len(documents) > 256:
        raise ValueError('plan evidence: invalid scoped reference documents')
    import evidence_policy as policy
    saved = state.get('reference_bindings', [])
    if not isinstance(saved, list) or len(saved) > 256:
        raise ValueError('plan evidence: invalid finite retained bindings')
    retained = [policy.ReferenceBinding.from_payload(value) for value in saved]
    declared, bindings = {}, []
    for declaration in documents:
        decisions = require_document_references(plan, declaration,
            contracts=state.get('reference_contracts', {}),
            retained=retained,
            active_consumers=state.get('active_reference_consumers', ()))
        declared.setdefault(declaration['document'], set()).update(
            item['start'] for item in declaration['references'])
        bindings.extend(item.binding.payload() for item in decisions)
    if len(bindings) > 256:
        raise ValueError('plan evidence: too many retained reference bindings')
    if bindings:
        state['reference_bindings'] = bindings
    return declared


def preflight(plan, run, state):
    """Inspect only current instructions, active claims and existing capacity.

    This is early refusal, not reservation or acceptance. Publication and
    retirement still independently pin and verify their actual complete inputs.
    No historical queue catalogue, model, VM or new allocation is involved.
    """
    import evidence_policy as policy
    try:
        return _preflight(plan, run, state)
    except ReferenceRefused:
        raise
    except (ValueError, OSError) as error:
        condition = policy.condition_for_exception(error)
        raise ReferenceRefused([policy.Diagnostic(policy.Severity.BLOCK, condition,
            plan.path, 1, None, None, policy.RECOVERY_ACTIONS[condition]).payload()]) from None


def _preflight(plan, run, state):
    import runner_evidence
    declared = _declared_gate(plan, state)
    for value in (plan.path, state['task']['brief']):
        path = Path(value)
        path = path if path.is_absolute() else plan.root / path
        try:
            text = document_checks.read_text(path)
        except FileNotFoundError:
            if value == state['task']['brief'] and (state.get('phase') == 'recover'
                    or state.get('evidence_capture_requires_brief')):
                continue  # Existing recovery owns restoration of the captured brief.
            raise
        _instruction_gate(plan, path, text, declared=declared.get(str(path.relative_to(plan.root)), ()))
    seen = set()
    for registration in state.get('evidence_consumers', {}).values():
        consumer = registration['consumer']
        if consumer['role'] not in ('required_evidence', 'required_instruction'):
            continue
        key = _digest(bundle.encoded(dict(reference=registration['reference'], consumer=consumer)))
        if key not in seen:
            runner_evidence.resolve_reference(plan.root, registration['reference'], consumer=consumer, count=0)
            seen.add(key)
    # Read the same owner inventory/budgets used by publication, without opening
    # a transaction or charging an unknown future result. The cumulative bundle
    # itself is a lower bound for the next replacement, not a capacity promise.
    try:
        parent = _parent(plan)
    except FileNotFoundError:
        return dict(required=len(seen), projected_bytes=0)
    store = bundle.retention.Store(parent / 'retention')
    if not store.path.exists():
        return dict(required=len(seen), projected_bytes=0)
    with store.inspection() as retained:
        records = ([] if retained is None else [record for _, record in
            bundle.retention.latest_allocations([*retained['history'], retained])])
        existing = bundle.retention.publication_usage(records)
        index, _ = _index(locator(plan))
        projected = 0
        if index is not None:
            # The exact existing cumulative archive is the minimum carried
            # payload. Do not charge all retained generations a second time.
            archives = ([Path(index['bundle'])] if index['schema'] == 1 else
                        [Path(item['bundle']) / 'evidence.zip' for item in index['segments']])
            for archive in set(archives):
                if not any(archive.parent == Path(record['path']) for record in records):
                    raise ValueError('plan evidence: capacity input has no recorded publication')
                projected += archive.stat().st_size
        usage = existing + projected + bundle.retention.publication_capture_bytes(retained)
        if usage > bundle.retention.MAX_RETAINED_BYTES:
            import evidence_policy as policy
            raise ReferenceRefused([policy.Diagnostic(policy.Severity.BLOCK, policy.Condition.CAPACITY,
                plan.path, 1, None, None, 'use_owned_retention_recovery').payload()])
    return dict(required=len(seen), projected_bytes=projected)


def _git_document(plan, revision, value):
    """Read one finite immutable baseline blob, never the changing worktree."""
    if revision is None:
        # Older in-flight checkpoints have no pre-turn Git identity. Give them
        # no historical exception; validate every reference in their named docs.
        return ''
    if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{40,64}', revision):
        raise ValueError('plan evidence: missing exact document baseline')
    selected = subprocess.run(['git', '--literal-pathspecs', 'ls-tree', '-z', revision, '--', value],
        cwd=plan.root, capture_output=True, check=True).stdout
    if not selected:
        return ''  # A newly authored document has no earlier claims.
    entries = selected.rstrip(b'\0').split(b'\0')
    metadata = entries[0].split(b'\t', 1)[0].split()
    if (len(entries) != 1 or len(metadata) != 3 or metadata[0] not in (b'100644', b'100755')
            or metadata[1] != b'blob' or not re.fullmatch(b'[0-9a-f]{40,64}', metadata[2])):
        raise ValueError('plan evidence: document baseline is not one regular blob')
    size = subprocess.run(['git', 'cat-file', '-s', metadata[2].decode('ascii')],
        cwd=plan.root, capture_output=True, check=True).stdout.strip()
    if not size.isdigit() or int(size) > document_checks.MAX_BYTES:
        raise ValueError('plan evidence: document baseline exceeds its bound')
    data = subprocess.run(['git', 'cat-file', 'blob', metadata[2].decode('ascii')],
        cwd=plan.root, capture_output=True, check=True).stdout
    if len(data) != int(size):
        raise ValueError('plan evidence: document baseline blob changed')
    return data.decode('utf-8')


def publication_document_gate(plan, state, result=None):
    """Recheck authored instruction claims against their exact captured inputs."""
    declared = _declared_gate(plan, state)
    required = set()
    originals = {}
    for value in state.get('evidence_inputs', []):
        metadata = bundle.decoded(_read(Path(value) / 'inputs.json'))
        if metadata['task_id'] != state['task_id']:
            raise ValueError('plan evidence: captured document belongs to another task')
        for entry in metadata['files']:
            data = _read(Path(value) / entry['member'])
            if _digest(data) != entry['sha256']:
                raise ValueError('plan evidence: captured document changed')
            originals.setdefault(entry['path'], data.decode('utf-8'))
    # The response names a finite mutation scope. Other Markdown files need an
    # immutable pre-turn baseline too; unchanged old links are not requalified.
    paths = result.get('stage_paths', []) if result is not None else []
    if len(paths) > 256:
        raise ValueError('plan evidence: publication document selection exceeds its bound')
    for value in paths:
        if Path(value).suffix.lower() not in ('.md', '.markdown'):
            continue
        path = document_checks.checkout_document(plan.root, value)
        if str(path) not in originals and path.exists():
            originals[str(path)] = _git_document(plan, state.get('reference_git_base'), value)
    for value, before in originals.items():
        path = Path(value)
        if not path.is_relative_to(plan.root):
            raise ValueError('plan evidence: publication document escapes checkout')
        try:
            text = document_checks.read_text(path)
        except FileNotFoundError:
            if value == str(Path(state['task']['brief'])) or path == plan.root / state['task']['brief']:
                continue  # Accepted tasks retire their temporary brief.
            raise
        positions = declared.get(str(path.relative_to(plan.root)), ())
        _instruction_gate(plan, path, text, previous=before, declared=positions)
        old = {(_claim_bytes(before, link), link.destination) for link in references(before)}
        for link in references(text):
            target = local_destination(link.destination)
            if (target is None or 'output/test-runs/' not in target.path
                    or link.start in positions
                    or (_claim_bytes(text, link), link.destination) in old):
                continue
            source = Path(os.path.abspath(path.parent / target.path))
            if not source.is_relative_to(plan.root / 'output/test-runs'):
                raise ValueError('plan evidence: authored reference escapes checkout storage')
            if target.fragment and target.fragment.startswith('onpc-evidence'):
                raise ValueError('plan evidence: authored exact claim requires its owning declaration')
            if not _navigation_reference(plan, source):
                required.add(str(source))
    return sorted(required)


def preserve(plan, run, state, result):
    """Retain a validated completion before its run or acceptance reports rotate."""
    with recovered(plan) as (previous, _, read):
        if previous is not None and previous['schema'] == 2:
            raise ValueError('plan evidence: schema 2 publication requires the versioned producer')
        if (result.get('status') != 'task_complete' or result.get('cleanup_complete') is not True
                or result.get('task_id') != state['task_id']):
            raise ValueError('plan evidence: preservation requires accepted completion and cleanup')
        consume(plan, state, result)
        authored_references = publication_document_gate(plan, state, result)
        if previous and state['task_id'] in previous['tasks']:
            proof = previous['tasks'][state['task_id']]
            if bundle.decoded(read(proof['result'], count=bundle.MAX_READ)) == result:
                return previous
            if not state.get('evidence_attempt') or state['evidence_attempt'] == proof['attempt']:
                raise ValueError('plan evidence: accepted result changed')
        generation = (bundle.decoded(read(previous['ledger'], count=bundle.MAX_READ))['generation'] + 1
                      if previous else 1)
    inputs = state.get('evidence_inputs', [])
    if not inputs:
        raise ValueError('plan evidence: exact selected inputs were not captured before execution')
    run = Path(run)
    targets = _targets(run, state)
    source_run = _source(plan, run, state, result)
    result_data = _read(source_run / 'agent-result.json')
    if bundle.decoded(result_data) != result:
        raise ValueError('plan evidence: exact agent result is missing or changed')
    parent = run / 'accepted-proof'
    bundle.retention.ensure_directory(parent)
    capsule = parent / uuid.uuid4().hex
    bundle.retention.ensure_directory(capsule)
    _write(capsule / 'result.json', result_data)
    _write(capsule / 'accepted-state.json', bundle.encoded(state))
    for name in ('prompt.txt', 'agent-commands.log', 'checkpoint.json', 'nested.json', 'nested-closed'):
        _write(capsule / name, _read(source_run / name))
    _write(capsule / 'cleanup.json', bundle.encoded(dict(cleanup_complete=True,
        nested=bundle.decoded(_read(source_run / 'nested.json')))))
    input_members = []
    captured_brief = False
    brief = Path(state['task']['brief'])
    brief = brief if brief.is_absolute() else plan.root / brief
    for value in inputs:
        metadata = bundle.decoded(_read(Path(value) / 'inputs.json'))
        if metadata['task_id'] != state['task_id']:
            raise ValueError('plan evidence: captured inputs belong to another task')
        for entry in metadata['files']:
            if _digest(_read(Path(value) / entry['member'])) != entry['sha256']:
                raise ValueError('plan evidence: captured inputs changed')
            captured_brief = captured_brief or entry['path'] == str(brief)
        input_members.append(str(Path(value) / 'inputs.json'))
    if not captured_brief:
        raise ValueError('plan evidence: restore the missing brief and return continue; '
                         'a later session must capture its exact inputs before completion')
    old_raw = _read(locator(plan)) if previous else b''
    tasks = dict(previous['tasks']) if previous else {}
    records = {str(path): _digest(_read(path)) for path in capsule.iterdir()}
    tasks[state['task_id']] = dict(result=str(capsule / 'result.json'), sha256=_digest(result_data),
                                   inputs=input_members, cleanup=True, records=records,
                                   attempt=state.get('evidence_attempt'))
    _write(capsule / 'accepted-ledger.json', bundle.encoded(dict(schema=1, plan=plan.path,
        generation=generation, previous_index_sha256=_digest(old_raw), tasks=tasks)))
    turns = state.get('evidence_turns', [])
    for value in turns:
        _turn(value, state['task_id'], plan=plan)
    sources, bundles = [str(capsule), *inputs, *turns], ([previous['bundle']] if previous else [])
    references = [path for path in sorted(set(_references(plan, result, state)) | set(authored_references))
                  if path not in sources and path not in bundles]
    _export(plan, run, state, sources, bundles, references)
    return recover(plan)


def _export(plan, run, state, sources, bundles, references):
    """Share authenticated selection/publication for working and accepted proof."""
    _parent(plan, create=True)
    targets = _targets(run, state)
    sources, bundles = list(dict.fromkeys(sources)), list(dict.fromkeys(bundles))
    if targets and os.geteuid() != 0:
        # Privileged target journals remain behind the maintained authenticated
        # reader; the controller never adopts their directories or runs as root.
        command = ['pkexec', '--keep-cwd', '/usr/local/libexec/onpc-test-artifacts']
        operands = ['--plan', plan.path]
        for flag, values in (('--target', targets), ('--source', sources),
                             ('--bundle', bundles), ('--reference', references)):
            for value in values:
                operands.extend((flag, value))
        def helper(action, *extra):
            completed = subprocess.run([*command, action, *operands, *extra], cwd=plan.root,
                                       capture_output=True, text=True, check=False)
            if completed.returncode:
                if completed.returncode == 3:
                    try:
                        failure = bundle.decoded(completed.stderr)
                        paths = failure['paths']
                        valid = (set(failure) == {'error', 'paths'}
                                 and failure['error'] == 'evidence_unavailable'
                                 and isinstance(paths, list) and 0 < len(paths) <= 256
                                 and all(isinstance(path, str) and path in references for path in paths)
                                 and len(set(paths)) == len(paths))
                    except (ValueError, KeyError, TypeError):
                        valid = False
                    if valid:
                        raise EvidenceUnavailable(paths)
                raise ValueError('plan evidence: maintained artifact helper refused: ' + completed.stderr.strip())
            return bundle.decoded(completed.stdout)
        selected = helper('bundle-plan', '--summary')
        helper('bundle-export', '--expect', selected['selection_sha256'], '--defer-cleanup')
    else:
        with bundle.Selection(plan.root, os.geteuid(), os.getegid(), targets,
                              sources, bundles, plan_namespace=plan_namespace(plan.path),
                              references=references) as selected:
            bundle.export(selected, expected=selected.selection_sha256, defer_cleanup=True)


def rewrite_references(plan, state, index):
    """Replace selected and already-completed destinations with verified proof."""
    with _verified_index(plan, index) as (verified, _):
        files = {entry['path'] for entry in verified['manifest']['files']}
        inherited = {entry['path'] for entry in verified['manifest']['inherited']}
        directories = {entry['path'] for entry in verified['manifest'].get('directories', [])}
    path = plan.root / plan.queue
    lines = path.read_text().splitlines(keepends=True)
    destination = os.path.relpath(locator(plan), path.parent)
    changed = False
    for number, line in enumerate(lines):
        cells = line.split('|')
        if len(cells) < 8:
            continue
        selected = cells[2].strip() == state['task_id']
        completed = state.get('queue_before', {}).get(cells[2].strip()) is True
        if not selected and not completed:
            continue
        def replacement(link):
            nonlocal changed
            target = local_destination(link.destination)
            if target is None or 'output/test-runs/' not in target.path:
                return None
            value = target.path
            source = Path(value)
            source = Path(os.path.abspath(source if source.is_absolute() else path.parent / source))
            if source.is_relative_to(plan.root / 'output/test-runs') and _navigation_reference(plan, source):
                return None
            original = str(source)
            if (original not in files and original not in inherited
                    and not (selected and original in directories)):
                if not selected:
                    return None  # Historical loss needs its authorized disclosure route.
                raise ValueError('plan evidence: queue reference has no exact preserved proof')
            changed = True
            return destination
        estimate = cells[6]
        for link in reversed(list(simple_inline_references(estimate))):
            value = replacement(link)
            if value is not None:
                cells[6] = cells[6][:link.destination_start] + value + cells[6][link.destination_end:]
        lines[number] = '|'.join(cells)
    if changed:
        _atomic(path, ''.join(lines).encode())
    return changed


INVENTORY_DOCUMENTS = 2048
INVENTORY_ENTRIES = 8192
INVENTORY_BYTES = 32 * 1024 * 1024


def _inventory_documents(plan):
    """Discover tracked names only, with bounded output and no filesystem walk."""
    with subprocess.Popen(['git', 'ls-files', '-z', '--', ':(icase)*.md', ':(icase)*.markdown'],
            cwd=plan.root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as child:
        raw = child.stdout.read(document_checks.MAX_BYTES + 1)
        if len(raw) > document_checks.MAX_BYTES:
            child.kill()
            raise ValueError('inventory: tracked document selection exceeds its bound')
        if child.wait(timeout=30):
            raise ValueError('inventory: tracked document discovery refused')
    return [os.fsdecode(value) for value in raw.split(b'\0') if value]


def _inventory_occurrences(text):
    """Reuse parser offsets; legacy literal paths are data, never instructions."""
    parsed = list(references(text))
    for link in parsed:
        target = local_destination(link.destination)
        if target is not None and _inventory_path(target.path):
            yield link, False
    prose = evidence_prose(text)
    pattern = (r'`([^`\n]+)`|((?:(?:/|\.{1,2}/)[^\s`<>\[\]()]*)?'
               r'(?:output/test-runs/|/tmp/onpc-|/var/tmp/onpc-)[^\s`<>\[\](),;]*)')
    for match in re.finditer(pattern, prose):
        value = match[1] or match[2].rstrip('.:!?\'"')
        if not _inventory_path(value):
            continue
        start = match.start(1 if match[1] else 2)
        end = start + len(value)
        yield document_checks.Link(match.start(), match.end(), start, end, value,
            text.count('\n', 0, start) + 1, 'legacy', start, end), False
    # Examples are inventoried without interpreting or reading their destinations.
    masked = document_checks.without_examples(text)
    excluded = ''.join(char if char != masked[index] else ('\n' if char == '\n' else ' ')
                       for index, char in enumerate(text))
    for match in re.finditer(r'(?:[^\s`<>\[\]()]*/)?(?:output/test-runs/|/tmp/onpc-|/var/tmp/onpc-)'
                             r'[^\s`<>\[\](),;]*', excluded):
        value = match[0].rstrip('.:!?\'"')
        yield document_checks.Link(match.start(), match.start() + len(value), match.start(),
            match.start() + len(value), value, text.count('\n', 0, match.start()) + 1,
            'example', match.start(), match.start() + len(value)), True


def _inventory_path(value):
    return ('output/test-runs/' in value or value.startswith(('/tmp/onpc-', '/var/tmp/onpc-')))


def _inventory_original(plan, document, link):
    target = local_destination(link.destination) if link.kind not in ('legacy', 'example') else None
    value = target.path if target is not None else link.destination.split('#', 1)[0]
    path = Path(value)
    base = (document.parent if target is not None or value.startswith(('../', './')) else plan.root)
    return Path(os.path.abspath(base / path))


def _inventory_owners(plan):
    """Read only authenticated accepted snapshots, never a live checkpoint."""
    index, raw = _index(locator(plan))
    if index is None:
        return [], []
    owners, candidates = [], []
    def collect(files, read):
        candidates.extend(dict(path=item['path'], sha256=item['sha256'], bytes=item['bytes'],
                               plan=plan.path, locator_sha256=_digest(raw))
                          for item in files)
        for task in index['tasks'].values():
            path = str(Path(task['result']).parent / 'accepted-state.json')
            entry = next((item for item in files if item['path'] == path), None)
            if entry is None:
                raise ValueError('inventory: accepted owner snapshot is missing')
            state = bundle.decoded(read(path, count=bundle.MAX_READ))
            if not isinstance(state, dict):
                raise ValueError('inventory: invalid accepted owner snapshot')
            owners.append(dict(plan=plan, state=state, source_sha256=entry['sha256']))
    if index['schema'] == 1:
        with _verified_index(plan, index) as (verified, read):
            collect(verified['manifest']['files'], read)
    else:
        with _verified_index_v2(plan, index) as verified:
            members = [(record, member) for record in verified['records'].values()
                       for member in record['members']]
            files = [dict(path=member['original_path'], sha256=member['sha256'], bytes=member['bytes'])
                     for _, member in members]
            def read(path, *, count):
                matches = [(record, member) for record, member in members
                           if member['original_path'] == path]
                origins = {bundle.digest(bundle.encoded(dict(member={key: member[key] for key in (
                    'original_path', 'source_allocation', 'sha256', 'bytes')},
                    provenance=verified['provenance'][(record['record_id'], member['member_id'])])))
                    for record, member in matches}
                if len(origins) != 1:
                    raise ValueError('inventory: ambiguous accepted owner snapshot')
                record, member = min(matches, key=lambda item: (item[0]['record_id'], item[1]['member_id']))
                return verified['read'](record['record_id'], member['member_id'], count=count)
            collect(files, read)
    if _read(locator(plan)) != raw:
        raise ValueError('inventory: accepted locator changed during inspection')
    if len(owners) > 256 or len(candidates) > bundle.MAX_FILES:
        raise ValueError('inventory: accepted metadata exceeds its bound')
    return owners, candidates


def _inventory_owner(owner, root):
    """Validate optional legacy metadata before composition, without reading it."""
    import evidence_identity as identity
    import evidence_policy as policy
    identity._hex(owner['source_sha256'])
    if owner['plan'].root != root:
        raise identity.EvidenceContextError('inventory: owner belongs to another checkout')
    state = owner['state']
    if not isinstance(state, dict) or len(bundle.encoded(state)) > document_checks.MAX_BYTES:
        raise ValueError('inventory: invalid finite owner snapshot')
    declarations = state.get('reference_documents', [])
    contracts = state.get('reference_contracts', {})
    bindings = state.get('reference_bindings', [])
    active = state.get('active_reference_consumers', [])
    if (type(declarations) is not list or len(declarations) > 256
            or type(contracts) is not dict or len(contracts) > 256
            or type(bindings) is not list or len(bindings) > 256
            or type(active) is not list or len(active) > 256):
        raise ValueError('inventory: invalid finite owner declarations')
    for key, value in contracts.items():
        identity._hex(key)
        identity.validate_consumer(value)
        if key != value['consumer_id']:
            raise ValueError('inventory: conflicting contract identity')
    for value in active:
        identity._hex(value)
    for value in bindings:
        policy.ReferenceBinding.from_payload(value)
    for declaration in declarations:
        identity._object(declaration, {'document', 'sha256', 'references'}, 'document declaration')
        document_checks.checkout_document(root, declaration['document'])
        identity._hex(declaration['sha256'])
        claims = declaration['references']
        if type(claims) is not list or not 1 <= len(claims) <= 256:
            raise ValueError('inventory: invalid finite owner claims')
        for claim in claims:
            identity._object(claim, {'start', 'consumer', 'selector', 'workflow'}, 'document claim')
            identity._integer(claim['start'])
            identity.validate_consumer(claim['consumer'])
            if claim['selector'] is not None and claim['selector'] not in claim['consumer']['references']:
                raise ValueError('inventory: conflicting declared selector')
            if claim['workflow'] is not None:
                identity._text(claim['workflow'])
    return declarations


def _inventory_recovery(entry):
    """Non-executable next steps bound by the containing inventory occurrence.

    Prerequisites are outstanding verification, not inferred missing authority.
    This metadata never supplies a role, active relevance or a check verdict.
    """
    import evidence_policy as policy
    classification = entry['classification']
    prerequisites = []
    proposal = None
    if entry['disposition'] == 'resolved':
        action = ('preview_verified_destination' if classification in (
            'exact_live_proof', 'exact_archived_proof') else 'none')
    else:
        if entry['consumer'] is None:
            prerequisites.extend(('owning_consumer_context', 'active_dependency_relevance'))
        diagnostic = entry['diagnostic']
        if diagnostic is not None and 'recovery' in diagnostic:
            action = diagnostic['recovery']
        elif entry['availability'] not in ('unknown', 'present', 'not_inspected'):
            action = policy.RECOVERY_ACTIONS[policy.Condition(entry['availability'])]
        else:
            action = 'supply_owning_declaration'
        if entry['availability'] == 'missing':
            # This inventory plan never executes acceptance or fabricates proof.
            if diagnostic is None:
                action = 'resolve_exact_missing_proof'
                prerequisites.append('exact_required_proof' if entry['active'] is True else
                    'exact_archived_proof_or_explicit_unavailability')
            elif diagnostic['severity'] == 'block':
                prerequisites.append('exact_required_proof')
            if (entry['protected'] and entry['active'] is not True
                    and (diagnostic is None or diagnostic['severity'] == 'advisory')):
                proposal = dict(kind='historical-disclosure', status='pending', prerequisites=[
                    'completed_row_and_exact_before_after_links',
                    'verified_retained_accepted_completion_without_detailed_proof',
                    'inactive_controller_queue_and_checkpoint_baselines',
                    'retained_exact_developer_authorization'])
        if entry['candidate'] is not None and entry['candidate'].get('context_verified') is False:
            prerequisites.append('candidate_matches_exact_consumer_context')
    return dict(action=action, prerequisites=prerequisites, disclosure_proposal=proposal)


def inventory_references(plan, *, documents=None, catalogues=(), owners=(), candidates=(),
                         owner_findings=()):
    """Finite read-only discovery. Unknown context remains pending, never proof.

    ``owners`` is supplied by trusted host code from authenticated snapshots, not
    declaration JSON. The report is revalidated migration input, not authority.
    """
    import evidence_policy as policy
    names = sorted(set([*(_inventory_documents(plan) if documents is None else documents), *catalogues]))
    if len(names) > INVENTORY_DOCUMENTS or len(owners) > 256 or len(candidates) > bundle.MAX_FILES:
        raise ValueError('inventory: selection exceeds its finite bound')
    result = dict(schema='onpc-legacy-reference-inventory', version=1,
                  plan=plan.path, documents=[], entries=[], owner_findings=list(owner_findings))
    declarations = {}
    for owner in owners:
        try:
            records = _inventory_owner(owner, plan.root)
        except (KeyError, TypeError, OSError, ValueError) as error:
            result['owner_findings'].append(dict(plan=owner['plan'].path,
                source_sha256=owner['source_sha256'], condition=policy.condition_for_exception(error).value))
            continue
        for declaration in records:
            declarations.setdefault(declaration['document'], []).append((owner, declaration))
    total = 0
    for name in names:
        path = document_checks.checkout_document(plan.root, name)
        try:
            text = document_checks.read_text(path)
        except (OSError, ValueError) as error:
            result['documents'].append(dict(document=name, sha256=None,
                condition=policy.condition_for_exception(error).value))
            continue
        raw = text.encode('utf-8')
        total += len(raw)
        if total > INVENTORY_BYTES:
            raise ValueError('inventory: document bytes exceed their finite bound')
        hashed = _digest(raw)
        result['documents'].append(dict(document=name, sha256=hashed))
        lines = text.splitlines()
        decisions_cache = {}
        occurrences = {link.start: (link, example) for link, example in _inventory_occurrences(text)}
        all_links = {link.start: link for link in references(text)}
        for _, declaration in declarations.get(name, []):
            for claim in declaration['references']:
                if claim['start'] in all_links:
                    occurrences.setdefault(claim['start'], (all_links[claim['start']], False))
        for _, (link, example) in sorted(occurrences.items()):
            source = _inventory_original(plan, path, link)
            # Only bounded path/identity metadata is emitted, never claim text.
            entry = dict(document=name, line=link.line, start=link.start, end=link.end,
                destination_start=link.destination_start, destination_end=link.destination_end,
                document_sha256=hashed, claim_sha256=_digest(_claim_bytes(text, link)),
                reference_sha256=_digest(text[link.start:link.end].encode('utf-8')),
                original_path=str(source) if _inventory_path(str(source)) else None,
                consumer=None, claim_revision=None, role=None, active=None, original_identity=None,
                candidate=None, availability='unknown', classification='unresolved_context',
                disposition='pending', migration_owner='E12', protected=False,
                owner_source_sha256=None, diagnostic=None)
            # Queue shape is a protection marker, not inferred consumer authority.
            line = lines[link.line - 1]
            if re.match(r'^\| \[[ x]\] \|', line):
                entry['protected'] = True
            matches = [(owner, declaration, claim) for owner, declaration in declarations.get(name, [])
                       for claim in declaration['references'] if claim['start'] == link.start]
            current = [item for item in matches if item[1]['sha256'] == hashed]
            matches = current or matches
            distinct = {bundle.digest(bundle.encoded(dict(plan=owner['plan'].path,
                declaration=declaration, claim=claim,
                contracts=owner['state'].get('reference_contracts', {}),
                active=owner['state'].get('active_reference_consumers', []),
                bindings=owner['state'].get('reference_bindings', []))))
                for owner, declaration, claim in matches}
            if example:
                entry.update(classification='example', availability='not_inspected', disposition='resolved')
            elif len(distinct) > 1:
                entry.update(classification='wrong_or_ambiguous_destination', availability='conflict')
            elif matches:
                owner, declaration, claim = min(matches, key=lambda item: item[0]['source_sha256'])
                consumer = claim['consumer']
                state = owner['state']
                entry.update(consumer=consumer['consumer_id'], claim_revision=consumer['revision_sha256'],
                    role=consumer['role'], active=consumer['consumer_id'] in state.get('active_reference_consumers', []),
                    original_identity=consumer['expected_context'], owner_source_sha256=owner['source_sha256'])
                try:
                    if declaration['sha256'] != hashed:
                        entry.update(availability='stale', diagnostic=dict(condition='stale'))
                    else:
                        retained = [policy.ReferenceBinding.from_payload(item)
                                    for item in state.get('reference_bindings', [])]
                        key = next(iter(distinct))
                        if key not in decisions_cache:
                            decisions_cache[key] = check_document_references(owner['plan'], declaration,
                                contracts=state.get('reference_contracts', {}), retained=retained,
                                active_consumers=state.get('active_reference_consumers', []))
                        decisions = decisions_cache[key]
                        decision = decisions[declaration['references'].index(claim)]
                        if decision.diagnostic is not None:
                            entry.update(availability=decision.diagnostic.condition.value,
                                         diagnostic=decision.diagnostic.payload())
                        elif claim['selector'] is None:
                            entry.update(classification=consumer['role'] if consumer['role'] in (
                                'example', 'operational_path') else 'operational_path',
                                availability='present', disposition='resolved')
                        else:
                            with reference_scope(owner['plan'], document=name,
                                    workflow=claim['workflow']).pinned() as scope:
                                destination, resolved = _generated_reference(consumer, claim['selector'], scope)
                                _document_source(owner['plan'], path, link, resolved, (consumer, scope))
                                member = resolved['member']
                                try:
                                    Path(member['original_path']).lstat()
                                    live = True
                                except FileNotFoundError:
                                    live = False
                                entry.update(classification='exact_live_proof' if live else 'exact_archived_proof',
                                    availability='live' if live else 'archived', disposition='resolved',
                                    candidate=dict(destination=destination, selector=claim['selector'],
                                        record_id=resolved['record']['record_id'], sha256=member['sha256'],
                                        bytes=member['bytes'], closure_sha256=resolved['record']['closure_sha256']))
                except (OSError, ValueError) as error:
                    entry.update(availability=policy.condition_for_exception(error).value)
                if entry['disposition'] == 'pending':
                    condition = entry['availability']
                    if condition == 'missing':
                        entry.update(classification='unavailable_history', migration_owner='E13')
                    elif condition in ('identity', 'conflict'):
                        entry['classification'] = 'wrong_or_ambiguous_destination'
                    elif condition != 'stale':
                        entry['classification'] = 'refused'
            else:
                target = local_destination(link.destination)
                operational = False
                if (source.is_relative_to(plan.root / 'output/test-runs')
                        and (target is None or not target.fragment)):
                    try:
                        operational = _navigation_reference(plan, source)
                    except FileNotFoundError:
                        pass  # A clean checkout has no authenticated navigation owner yet.
                if operational:
                    entry.update(classification='operational_path', availability='not_inspected',
                                 disposition='resolved')
                else:
                    try:
                        if (not source.is_relative_to(plan.root / 'output/test-runs')
                                and not str(source).startswith(('/tmp/onpc-', '/var/tmp/onpc-'))):
                            entry['availability'] = 'identity'
                        elif any(parent.is_symlink() for parent in (source, *source.parents)):
                            entry['availability'] = 'integrity'
                        else:
                            source.lstat()
                            entry['availability'] = 'present'
                    except (OSError, ValueError) as error:
                        entry['availability'] = policy.condition_for_exception(error).value
                    if entry['availability'] == 'missing':
                        entry.update(classification='unavailable_history', migration_owner='E13')
                    elif entry['availability'] not in ('present', 'fragment'):
                        entry['classification'] = 'refused'
                retained = [item for item in candidates if item['path'] == str(source)]
                identities = {(item['sha256'], item['bytes']) for item in retained}
                if len(identities) == 1:
                    checksum, size = next(iter(identities))
                    entry['candidate'] = dict(original_path=str(source), sha256=checksum, bytes=size,
                        publications=[dict(plan=name, locator_sha256=checksum) for name, checksum in
                            sorted({(item['plan'], item['locator_sha256']) for item in retained})],
                        context_verified=False)
                elif len(identities) > 1:
                    entry.update(classification='wrong_or_ambiguous_destination', availability='conflict')
            entry['recovery'] = _inventory_recovery(entry)
            result['entries'].append(entry)
            if len(result['entries']) > INVENTORY_ENTRIES:
                raise ValueError('inventory: reference count exceeds its finite bound')
        if document_checks.read_text(path) != text:
            raise ValueError('inventory: document changed during inspection')
    counts = {}
    for entry in result['entries']:
        counts[entry['classification']] = counts.get(entry['classification'], 0) + 1
    result['owner_findings'].sort(key=lambda item: bundle.encoded(item))
    result['counts'] = counts
    result['sha256'] = bundle.digest(bundle.encoded(result))
    if len(bundle.encoded(result)) > document_checks.MAX_BYTES:
        raise ValueError('inventory: report exceeds its finite bound')
    return result


def retain_inventory(plan, report):
    """One normal bounded report allocation, with no new journal or input writes."""
    import tempfile
    with ExitStack() as stack:
        if bundle.retention.token() is None:
            stack.enter_context(bundle.retention.Store(
                bundle.storage.directory('state', root=plan.root) / 'standalone-reports').session())
        directory = Path(bundle.retention.allocate(tempfile.mkdtemp, prefix='onpc-reference-inventory-',
            dir=bundle.storage.directory('reports', root=plan.root)))
        path = directory / 'inventory.json'
        _write(path, bundle.encoded(report))
    return path


def main(argv=None):
    """Read-only, explicit semantic preview; no launcher or mutation options."""
    import sys
    from execution_plan import Plan
    import evidence_identity as identities
    parser = document_checks.Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--declarations')
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--catalogue', action='append', default=[])
    parser.add_argument('--owner-plan', action='append', default=[])
    try:
        args = parser.parse_args(argv)
        root = Path(__file__).resolve().parents[1]
        plan = Plan.load(root, args.plan)
        if args.inventory:
            import evidence_policy as policy
            if args.declarations or len(args.catalogue) > 256 or len(args.owner_plan) > 32:
                raise ValueError('inventory: invalid finite inspection request')
            owners, candidates, findings = [], [], []
            for name in sorted(set([plan.path, *args.owner_plan])):
                try:
                    selected = Plan.load(root, name)
                    records, files = _inventory_owners(selected)
                    owners.extend(records)
                    candidates.extend(files)
                except (OSError, ValueError) as error:
                    findings.append(dict(plan=name, condition=policy.condition_for_exception(error).value))
            report = inventory_references(plan, catalogues=args.catalogue, owners=owners,
                candidates=candidates, owner_findings=findings)
            path = retain_inventory(plan, report)
            print(json.dumps(dict(report=str(path), sha256=report['sha256'], counts=report['counts'],
                                  owner_findings=report['owner_findings']), sort_keys=True))
            return 0
        if not args.declarations or args.catalogue or args.owner_plan:
            raise ValueError('plan evidence: expected explicit declarations')
        declaration = bundle.decoded(document_checks.read_text(args.declarations))
        identities._object(declaration, {'schema', 'version', 'documents'}, 'document request')
        if (declaration['schema'] != 'onpc-evidence-documents'
                or type(declaration['version']) is not int or declaration['version'] != 1
                or type(declaration['documents']) is not list
                or not 1 <= len(declaration['documents']) <= 256):
            raise ValueError('plan evidence: expected 1..256 explicit document declarations')
        previews = [preview_document_links(plan, item) for item in declaration['documents']]
        print(json.dumps(dict(schema='onpc-evidence-link-previews', version=1, previews=previews),
                         sort_keys=True, separators=(',', ':')))
        return 0
    except (ValueError, OSError) as exc:
        # Do not echo raw declarations, link text, commands or private transcripts.
        diagnostic = getattr(exc, 'reference_diagnostic', None)
        if diagnostic is not None:
            print('evidence-links: ' + json.dumps(diagnostic, sort_keys=True), file=sys.stderr)
        else:
            print('evidence-links: semantic preview refused (' + type(exc).__name__ + ')', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
