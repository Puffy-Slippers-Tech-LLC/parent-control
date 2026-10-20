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
import uuid

import evidence_bundle as bundle
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
        published = recover(plan)
        accepted = published['tasks'].get(pending['task_id']) if published else None
        exact = (bundle.decoded(bundle.inspect(plan.root, os.geteuid(), os.getegid(), published['bundle'],
                    member=accepted['result'], count=bundle.MAX_READ)) == pending) if accepted else False
        if not exact:
            _source(plan, run, state, pending)
    for suspended in state.get('suspended_tasks', {}).values():
        carry(plan, run, suspended)
    return state


def capture(plan, run, state):
    """Freeze exact task-selection files before an agent may remove its brief."""
    carry(plan, run, state)
    parent = Path(run) / 'plan-inputs'
    bundle.retention.ensure_directory(parent)
    target = parent / uuid.uuid4().hex
    bundle.retention.ensure_directory(target)
    files, missing = [], []
    brief = Path(state['task']['brief'])
    brief = brief if brief.is_absolute() else plan.root / brief
    recovering = (state.get('phase') == 'recover'
                  or state.get('recovery_run') and state.get('in_flight')
                  or any(state.get(key) for key in ('pending_completion', 'git_reconciliation', 'result_recovery')))
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
    if (not isinstance(value, dict) or set(value) != {
            'schema', 'plan', 'bundle', 'sha256', 'selection_sha256', 'ledger', 'tasks'}
            or value['schema'] != 1 or not isinstance(value['tasks'], dict)):
        raise ValueError('plan evidence: invalid accepted index')
    return value, data


def _ledger(record, plan):
    verified = bundle.inspect_record(record, os.geteuid(), checkout=plan.root)
    candidates = []
    for entry in verified['manifest']['files']:
        if Path(entry['path']).name == 'accepted-ledger.json':
            data = bundle.inspect_record(record, os.geteuid(), checkout=plan.root,
                                         member=entry['path'], count=bundle.MAX_READ)
            value = bundle.decoded(data)
            if (not isinstance(value, dict) or set(value) != {
                    'schema', 'plan', 'generation', 'previous_index_sha256', 'tasks'}
                    or value['schema'] != 1 or value['plan'] != plan.path
                    or type(value['generation']) is not int or value['generation'] <= 0
                    or not isinstance(value['tasks'], dict)):
                raise ValueError('plan evidence: invalid accepted ledger')
            candidates.append((value['generation'], entry['path'], value))
    if not candidates:
        raise ValueError('plan evidence: accepted ledger is missing')
    generation, ledger_path, value = max(candidates, key=lambda item: item[0])
    if sum(item[0] == generation for item in candidates) != 1:
        raise ValueError('plan evidence: ambiguous accepted ledger')
    files = {item['path']: item for item in verified['manifest']['files']}
    for task, proof in value['tasks'].items():
        if (not isinstance(proof, dict) or set(proof) != {'result', 'sha256', 'inputs', 'cleanup', 'records', 'attempt'}
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
            inputs = bundle.decoded(bundle.inspect_record(record, os.geteuid(), checkout=plan.root,
                member=input_path, count=bundle.MAX_READ))
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
        result = bundle.decoded(bundle.inspect_record(record, os.geteuid(), checkout=plan.root,
                               member=proof['result'], count=bundle.MAX_READ))
        if (result.get('task_id') != task or result.get('status') != 'task_complete'
                or result.get('cleanup_complete') is not True):
            raise ValueError('plan evidence: result or cleanup does not match accepted proof')
    index = dict(schema=1, plan=plan.path, bundle=str(Path(record['path']) / 'evidence.zip'),
                 sha256=verified['sha256'], selection_sha256=verified['selection_sha256'],
                 ledger=ledger_path, tasks=value['tasks'])
    return value, index


def _verify_index(plan, index):
    if index['plan'] != plan.path:
        raise ValueError('plan evidence: accepted index belongs to another plan')
    path = Path(index['bundle'])
    if path.parent.parent != _parent(plan):
        raise ValueError('plan evidence: accepted bundle belongs to another owner')
    verified = bundle.inspect(plan.root, os.geteuid(), os.getegid(), str(path))
    if (verified['sha256'] != index['sha256']
            or verified['selection_sha256'] != index['selection_sha256']):
        raise ValueError('plan evidence: accepted bundle changed')
    # Inspect the published allocation, not a source allocation from its manifest.
    store = bundle.retention.Store(_parent(plan) / 'retention')
    with store.inspection() as state:
        records = [record for _, record in bundle.retention.latest_allocations([*state['history'], state])
                   if record['path'] == str(path.parent)]
        if len(records) != 1 or _ledger(records[0], plan)[1] != index:
            raise ValueError('plan evidence: accepted index does not match verified proof')


def recover(plan):
    """Publish the verified locator before completing any committed retirement."""
    parent = _parent(plan)
    index_path = parent.parent / 'accepted-evidence.json'
    store = bundle.retention.Store(parent / 'retention')
    if store.path.exists():
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with store.locked(fd, 'writer.lock', publication=True):
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
                        _atomic(index_path, bundle.encoded(replacement))
                bundle.retention.recover_publication(store, fd,
                    verify=lambda record: _ledger(record, plan))
    index, _ = _index(index_path)
    if index is not None:
        _verify_index(plan, index)
    return index


def _references(plan, result, state):
    """Only explicit checkout-storage references are inputs to proof publication."""
    texts = [check['evidence'] for check in result['checks']]
    queue = (plan.root / plan.queue).read_text()
    texts += [line for line in queue.splitlines()
              if re.match(r'^\| \[[ x]\] \| ' + re.escape(state['task_id']) + r' \|', line)]
    found = set()
    for text in texts:
        values = re.findall(r'\]\(([^)]+)\)|`([^`]+)`', text)
        values = [a or b for a, b in values]
        values += re.findall(r'(?:/[^\s`<>\[\]()]+)?output/test-runs/[^\s`<>\[\](),;]+', text)
        for value in values:
            value = value.split('#', 1)[0]
            if 'output/test-runs/' not in value:
                continue
            source = Path(value)
            if not source.is_absolute():
                source = (plan.root / plan.queue).parent / source if value.startswith('../') else plan.root / source
            # Resolve lexical '..' without following any source symlink.
            source = Path(os.path.abspath(source))
            if not source.is_relative_to(plan.root / 'output/test-runs'):
                raise ValueError('plan evidence: reference escapes checkout storage')
            if source != locator(plan):
                found.add(str(source))
    return sorted(found)


def preserve(plan, run, state, result):
    """Retain a validated completion before its run or acceptance reports rotate."""
    previous = recover(plan)
    if (result.get('status') != 'task_complete' or result.get('cleanup_complete') is not True
            or result.get('task_id') != state['task_id']):
        raise ValueError('plan evidence: preservation requires accepted completion and cleanup')
    if previous and state['task_id'] in previous['tasks']:
        proof = previous['tasks'][state['task_id']]
        saved = bundle.inspect(plan.root, os.geteuid(), os.getegid(), previous['bundle'],
                               member=proof['result'], count=bundle.MAX_READ)
        if bundle.decoded(saved) == result:
            return previous
        if not state.get('evidence_attempt') or state['evidence_attempt'] == proof['attempt']:
            raise ValueError('plan evidence: accepted result changed')
    inputs = state.get('evidence_inputs', [])
    if not inputs:
        raise ValueError('plan evidence: exact selected inputs were not captured before execution')
    run = Path(run)
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
    generation = 1
    if previous:
        old = bundle.decoded(bundle.inspect(plan.root, os.geteuid(), os.getegid(), previous['bundle'],
                               member=previous['ledger'], count=bundle.MAX_READ))
        generation = old['generation'] + 1
    _write(capsule / 'accepted-ledger.json', bundle.encoded(dict(schema=1, plan=plan.path,
        generation=generation, previous_index_sha256=_digest(old_raw), tasks=tasks)))
    sources, bundles = [str(capsule), *inputs], ([previous['bundle']] if previous else [])
    for path in _references(plan, result, state):
        (bundles if Path(path).name == 'evidence.zip' else sources).append(path)
    _parent(plan, create=True)
    sources, bundles = list(dict.fromkeys(sources)), list(dict.fromkeys(bundles))
    if state['task']['targets'] and os.geteuid() != 0:
        # Privileged target journals remain behind the maintained authenticated
        # reader; the controller never adopts their directories or runs as root.
        command = ['pkexec', '--keep-cwd', '/usr/local/libexec/onpc-test-artifacts']
        operands = ['--plan', plan.path]
        for flag, values in (('--target', state['task']['targets']), ('--source', sources), ('--bundle', bundles)):
            for value in values:
                operands.extend((flag, value))
        def helper(action, *extra):
            completed = subprocess.run([*command, action, *operands, *extra], cwd=plan.root,
                                       capture_output=True, text=True, check=False)
            if completed.returncode:
                raise ValueError('plan evidence: maintained artifact helper refused: ' + completed.stderr.strip())
            return bundle.decoded(completed.stdout)
        selected = helper('bundle-plan', '--summary')
        helper('bundle-export', '--expect', selected['selection_sha256'], '--defer-cleanup')
    else:
        with bundle.Selection(plan.root, os.geteuid(), os.getegid(), state['task']['targets'],
                              sources, bundles, plan_namespace=plan_namespace(plan.path)) as selected:
            bundle.export(selected, expected=selected.selection_sha256, defer_cleanup=True)
    return recover(plan)


def rewrite_references(plan, state, index):
    """Replace selected and already-completed destinations with verified proof."""
    _verify_index(plan, index)
    verified = bundle.inspect(plan.root, os.geteuid(), os.getegid(), index['bundle'])
    files = {entry['path'] for entry in verified['manifest']['files']}
    inherited = {entry['path'] for entry in verified['manifest']['inherited']}
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
        def replace(match):
            nonlocal changed
            value = match[1]
            if 'output/test-runs/' not in value:
                return match[0]
            value = value.split('#', 1)[0]
            source = Path(value)
            source = Path(os.path.abspath(source if source.is_absolute() else path.parent / source))
            if source == locator(plan):
                return match[0]
            original = str(source)
            if (original not in files and original not in inherited
                    and not (selected and any(member.startswith(original + '/') for member in files))):
                if not selected:
                    return match[0]  # Historical loss needs its authorized disclosure route.
                raise ValueError('plan evidence: queue reference has no exact preserved proof')
            changed = True
            return match[0][:match.start(1) - match.start()] + destination + match[0][match.end(1) - match.start():]
        cells[6] = re.sub(r'(?<![!\\])\[[^\[\]\\\n]+\]\(([^()\s<>\\|]+)\)', replace, cells[6])
        lines[number] = '|'.join(cells)
    if changed:
        _atomic(path, ''.join(lines).encode())
    return changed
