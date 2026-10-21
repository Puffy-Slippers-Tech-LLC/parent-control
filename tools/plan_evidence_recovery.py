"""Controller-only, exact evidence disclosure transactions for ordinary plans.

Call while the launcher gate and inactive owner are held, before restart guards.
The selected brief supplies a reviewed request; a proof verifier supplies bundle
and acceptance verification. This route never changes Git ownership or grants
acceptance, and does not relax the ordinary queue comparison rules.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

import detached_launcher as launcher
from execution_plan import closeout_structure, evidence_references, local_file
from launcher_runtime import capacity_session_recovery


PROTECTED_FIELDS = (
    'task_id', 'title', 'brief', 'acceptance', 'targets', 'task', 'queue_before',
    'queue_structure', 'task_sessions', 'total_sessions', 'session_limit',
    'stage_baseline', 'protected_staged', 'suspended_tasks', 'replan_baseline',
    'consolidation_obligations', 'pending_completion', 'commit_intent',
    'pull_intent', 'git_reconciliation', 'result_recovery', 'evidence_inputs', 'evidence_attempt',
    'evidence_capture_requires_brief',
    'evidence_source',
    'evidence_recovery',
)
LABEL_SUFFIX = ' — detailed proof unavailable; retained accepted completion'
LINK = re.compile(r'(?<![!\\])\[([^\[\]\\\n]+)\]\(([^()\s<>\\|]+)\)')
REQUEST = re.compile(r'^```plan-evidence-recovery\n(.*?)\n```[ \t]*$', re.M | re.S)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def protected_digest(state):
    """Bind material checkpoint state while allowing the final session handoff."""
    return digest(encoded({key: state[key] for key in PROTECTED_FIELDS if key in state}))


def _read(path, maximum=4 * 1024 * 1024):
    path = Path(path)
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('evidence recovery refuses symlinked inputs')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_size > maximum):
            raise ValueError('evidence recovery needs a bounded caller-owned regular input')
        data = os.read(fd, maximum + 1)
        if len(data) != info.st_size:
            raise ValueError('evidence recovery input changed while reading')
        return data
    finally:
        os.close(fd)


def _checkout_path(root, value):
    if not isinstance(value, str):
        raise ValueError('evidence recovery path must be checkout relative')
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not value:
        raise ValueError('evidence recovery path must be checkout relative')
    return root / path


def request_from_brief(plan, state):
    task = state.get('task', {})
    if not task:
        return None
    brief = Path(task.get('brief', ''))
    if not brief.exists() and (capacity_session_recovery(state) or state.get('phase') == 'complete' or any(state.get(key) for key in (
            'in_flight', 'pending_completion', 'git_reconciliation', 'result_recovery', 'evidence_renewal'))):
        return None  # Ordinary interrupted completion owns a removed brief.
    try:
        relative = str(brief.relative_to(plan.root))
    except ValueError:
        raise ValueError('evidence recovery selected brief escaped the checkout') from None
    text = local_file(plan.root, relative).read_text()
    matches = REQUEST.findall(text)
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError('evidence recovery needs one reviewed request')
    from evidence_bundle import decoded
    request = decoded(matches[0])
    if (not isinstance(request, dict) or set(request) != {
            'version', 'plan', 'queue', 'task', 'baseline_sha256', 'queue_sha256',
            'authorization', 'corrections'} or request['version'] != 1):
        raise ValueError('invalid evidence recovery request')
    return request


def _links(before, after, kind, plan):
    """Only exact simple links change; surrounding claims stay literal."""
    from document_checks import without_code
    old = list(LINK.finditer(without_code(before)))
    new = list(LINK.finditer(without_code(after)))
    if len(old) != len(new) or not old:
        raise ValueError('evidence recovery must preserve the simple link count')
    old_position = new_position = 0
    changed = disclosures = 0
    for left, right in zip(old, new):
        if before[old_position:left.start()] != after[new_position:right.start()]:
            raise ValueError('evidence recovery cannot change surrounding claims')
        old_position, new_position = left.end(), right.end()
        if left.group() == right.group():
            continue
        changed += 1
        disclosure = kind == 'historical-disclosure' and right[1] == left[1] + LABEL_SUFFIX
        if right[1] != left[1] and not disclosure:
            raise ValueError('evidence recovery needs the exact disclosure or unchanged label')
        if disclosure:
            disclosures += 1
            destination = (plan.root / plan.queue).parent / left[2]
            if destination.exists():
                raise ValueError('historical disclosure requires unavailable original proof')
        if left[2] == right[2]:
            raise ValueError('evidence recovery must replace an evidence destination')
    if before[old_position:] != after[new_position:] or not changed:
        raise ValueError('evidence recovery needs exact evidence link replacements')
    if kind == 'historical-disclosure' and not disclosures:
        raise ValueError('historical evidence recovery needs an explicit proof-loss disclosure')


def _updated_state(state, corrections):
    updated = copy.deepcopy(state)
    for saved in (updated, *updated.get('suspended_tasks', {}).values()):
        rows = saved.get('queue_structure')
        if not isinstance(rows, list):
            raise ValueError('evidence recovery needs retained queue structures')
        for correction in corrections:
            matches = [row for row in rows if row[2] == correction['task_id']]
            if len(matches) != 1 or len(matches[0]) <= 7:
                raise ValueError('evidence recovery row is absent from a retained baseline')
            row = matches[0]
            # Suspended consumers normalize their own Estimate bookkeeping.
            if row[6] == '<selected task estimate>' and saved.get('task_id') == row[2]:
                continue
            if (row[6] != correction['before'] and not (
                    saved['queue_before'].get(row[2]) is True
                    and evidence_references(row[6]) == evidence_references(correction['before']))):
                raise ValueError('evidence recovery original claim differs from retained history')
            row[6] = correction['after']
    return updated


def _candidate(plan, state, request, queue, verify_proof, authority):
    if (request['plan'] != plan.path or request['queue'] != plan.queue
            or request['task'] != state.get('task')
            or request['baseline_sha256'] != protected_digest(state)
            or request['queue_sha256'] != digest(queue)):
        raise ValueError('evidence recovery request does not match its retained baseline')
    if any(state.get(key) for key in ('pending_completion', 'commit_intent', 'pull_intent',
                                    'git_reconciliation', 'result_recovery')):
        raise ValueError('finish the retained transaction before evidence recovery')
    authorization = request['authorization']
    if (not isinstance(authorization, dict) or set(authorization) not in (
            {'checkpoint', 'sha256', 'answer_sha256'},
            {'checkpoint', 'sha256', 'answer_sha256', 'bundle'})):
        raise ValueError('evidence recovery needs exact retained developer authorization')
    answer = json.loads(authority).get('answer')
    if (digest(authority) != authorization['sha256'] or not isinstance(answer, dict)
            or not isinstance(answer.get('answer'), str) or not answer['answer'].strip()
            or digest(encoded(answer)) != authorization['answer_sha256']):
        raise ValueError('evidence recovery retained developer authorization changed')
    recovery_authorization(authority, authorization)
    corrections = request['corrections']
    if not isinstance(corrections, list) or not corrections or len(corrections) > 16:
        raise ValueError('evidence recovery needs a finite correction list')
    queue_rows = []
    current_completion = {}
    for line in queue.decode().split('## Deferred future work', 1)[0].splitlines():
        if re.match(r'^\| \[[ x]\] \|', line):
            fields = [field.strip() for field in line.split('|')]
            if len(fields) <= 7 or fields[2] in current_completion:
                raise ValueError('evidence recovery queue is malformed')
            current_completion[fields[2]] = fields[1] == '[x]'
            fields[1] = '[ ]'
            queue_rows.append(fields)
    rows = {row[2]: row for row in queue_rows}
    before = state['queue_before']
    if current_completion != before or list(current_completion) != list(before):
        raise ValueError('evidence recovery cannot change completion or order')
    saved = {row[2]: row for row in state['queue_structure']}
    selected = state['task_id']
    completed = {key for key, done in before.items() if done is True}
    if (closeout_structure(queue_rows, selected, completed=completed) !=
            closeout_structure(state['queue_structure'], selected, completed=completed)):
        raise ValueError('evidence recovery cannot adopt unrelated queue changes')
    current = next(task for task in plan.tasks() if task.id == selected)
    if (current.title != state['task']['title'] or str(current.brief) != state['task']['brief']
            or current.acceptance_metadata() != {
                key: state['task'][key] for key in ('acceptance', 'targets')}):
        raise ValueError('evidence recovery cannot change selected acceptance')
    tasks = {task.id: task for task in plan.tasks()}
    for key, suspended in state.get('suspended_tasks', {}).items():
        record = suspended.get('task', {})
        if (key not in tasks or tasks[key].complete or key != suspended.get('task_id')
                or tasks[key].title != record.get('title')
                or str(tasks[key].brief) != record.get('brief')
                or tasks[key].acceptance_metadata() != {
                    field: record.get(field) for field in ('acceptance', 'targets')}):
            raise ValueError('evidence recovery cannot change suspended task acceptance')
    seen = set()
    text = queue.decode('utf-8')
    for correction in corrections:
        if not isinstance(correction, dict) or set(correction) != {
                'task_id', 'kind', 'before', 'after', 'proof'}:
            raise ValueError('invalid evidence correction')
        key, kind = correction['task_id'], correction['kind']
        if (key in seen or key not in rows or key == selected
                or kind not in ('historical-disclosure', 'retained-destination')
                or not isinstance(correction['before'], str)
                or not isinstance(correction['after'], str)
                or any('\n' in correction[field] or '|' in correction[field]
                       for field in ('before', 'after'))):
            raise ValueError('evidence recovery correction is not narrowly scoped')
        seen.add(key)
        if (not before[key] and (kind != 'retained-destination'
                                or key not in state.get('suspended_tasks', {}))):
            raise ValueError('evidence recovery cannot rewrite unfinished task evidence')
        if (rows[key][6] != correction['before'] or (
                saved[key][6] != correction['before'] and not (
                    before[key] and evidence_references(saved[key][6]) ==
                    evidence_references(correction['before'])))):
            raise ValueError('evidence recovery original claim changed')
        _links(correction['before'], correction['after'], kind, plan)
        verify_proof(correction, request)
        lines = text.splitlines(keepends=True)
        matches = [index for index, line in enumerate(lines)
                   if re.match(r'^\| \[[ x]\] \| ' + re.escape(key) + r' \|', line)]
        if len(matches) != 1:
            raise ValueError('evidence recovery row is ambiguous')
        fields = lines[matches[0]].split('|')
        if fields[6].strip() != correction['before']:
            raise ValueError('evidence recovery Estimate is ambiguous')
        fields[6] = ' ' + correction['after'] + ' '
        lines[matches[0]] = '|'.join(fields)
        text = ''.join(lines)
    return text.encode(), _updated_state(state, corrections)


def _bundle_path(plan, value):
    if not isinstance(value, str):
        raise ValueError('evidence recovery needs an exact bundle path')
    candidate = Path(value)
    return candidate if candidate.is_absolute() else plan.root / candidate


def _inspect_bundle(plan, path, **kwargs):
    import evidence_bundle
    return evidence_bundle.inspect(plan.root, os.geteuid(), os.getegid(), str(path), **kwargs)


def read_authorization(plan, request):
    """Read exact retained developer-answer bytes from verified shared storage."""
    authorization = request['authorization']
    if 'bundle' not in authorization:
        return _read(_checkout_path(plan.root, authorization['checkpoint']))
    bundle = _bundle_path(plan, authorization['bundle'])
    result = _inspect_bundle(plan, bundle)
    members = [entry for entry in result['manifest']['files']
               if entry['path'] == authorization['checkpoint']]
    if (len(members) != 1 or members[0]['sha256'] != authorization['sha256']
            or members[0]['bytes'] > 4 * 1024 * 1024):
        raise ValueError('evidence recovery authorization is not the exact retained member')
    payload = _inspect_bundle(plan, bundle, member=authorization['checkpoint'],
                              count=members[0]['bytes'])
    recovery_authorization(payload, authorization)
    return payload


def recovery_authorization(payload, authorization):
    """Return the exact accepted checkpoint, never a substitute check result."""
    checkpoint = json.loads(payload)
    if (digest(payload) != authorization['sha256']
            or digest(encoded(checkpoint.get('answer'))) != authorization['answer_sha256']
            or checkpoint.get('phase') != 'complete' or checkpoint.get('in_flight') is not False
            or not isinstance(checkpoint.get('queue_before'), dict)):
        raise ValueError('evidence recovery requires exact accepted-completion authorization')
    answer = checkpoint.get('answer')
    if not isinstance(answer, dict) or not isinstance(answer.get('answer'), str) or not answer['answer'].strip():
        raise ValueError('evidence recovery needs the retained developer answer')
    return checkpoint


def verify_proof(plan, correction, request):
    """Verify every changed link against its exact retained bundle provenance.

    Proof is ``{bundle, links: [{before, member, sha256}, ...]}``, in changed-link
    order. Historical disclosures name only the authorization checkpoint; exact
    report relocations name their original absolute member. Full bundle
    inspection verifies original identities, allocation provenance and all bytes.
    """
    proof = correction['proof']
    if (not isinstance(proof, dict) or set(proof) != {'bundle', 'links'}
            or not isinstance(proof['links'], list)):
        raise ValueError('evidence recovery needs finite exact bundle-link proof')
    bundle = _bundle_path(plan, proof['bundle'])
    result = _inspect_bundle(plan, bundle)
    members = {entry['path']: entry for entry in result['manifest']['files']}
    changes = [(left, right) for left, right in zip(
        LINK.finditer(correction['before']), LINK.finditer(correction['after']))
        if left.group() != right.group()]
    if len(changes) != len(proof['links']):
        raise ValueError('evidence recovery proof does not cover every changed link')
    authority = None
    for (left, right), record in zip(changes, proof['links']):
        if (not isinstance(record, dict) or set(record) != {'before', 'member', 'sha256'}
                or record['before'] != left[2]
                or ((plan.root / plan.queue).parent / right[2]).resolve() != bundle.resolve()
                or record['member'] not in members
                or members[record['member']]['sha256'] != record['sha256']):
            raise ValueError('evidence recovery replacement differs from exact bundle proof')
        original = str(((plan.root / plan.queue).parent / left[2]).resolve())
        if right[1] == left[1] + LABEL_SUFFIX:
            if (Path(original).exists() or original in members
                    or record['member'] != request['authorization']['checkpoint']
                    or record['sha256'] != request['authorization']['sha256']):
                raise ValueError('historical disclosure cannot invent missing detailed proof')
            if authority is None:
                authority = recovery_authorization(read_authorization(plan, request), request['authorization'])
            key = correction['task_id']
            if (authority['queue_before'].get(key) is not True
                    and authority.get('task_id') != key):
                raise ValueError('historical disclosure lacks retained accepted completion')
        elif record['member'] != original:
            raise ValueError('retained destination must preserve the exact original evidence')


def _publish_queue(path, payload):
    """Atomic text publication retaining the checkout file's executable mode."""
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary = path.with_name(path.name + '.evidence-' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _applied_state(state, transaction, receipt):
    """Carry the immutable transaction when the disposable source run rotates."""
    completed = dict(transaction, complete=True)
    marker = dict(request_sha256=digest(encoded(transaction['request'])),
                  receipt=str(receipt), receipt_sha256=digest(json.dumps(completed).encode()),
                  transaction=completed)
    return dict(state, evidence_recovery=marker)


def _applied_request(plan, state, previous, request):
    marker = state.get('evidence_recovery')
    if marker is None:
        return False
    if (not isinstance(marker, dict) or set(marker) != {
            'request_sha256', 'receipt', 'receipt_sha256', 'transaction'}
            or marker['request_sha256'] != digest(encoded(request))):
        raise ValueError('evidence recovery applied request identity changed')
    transaction = marker['transaction']
    if (not isinstance(transaction, dict) or transaction.get('complete') is not True
            or transaction.get('request') != request
            or digest(json.dumps(transaction).encode()) != marker['receipt_sha256']):
        raise ValueError('evidence recovery recorded transaction changed')
    receipt = Path(marker['receipt'])
    if receipt.name != 'evidence-recovery.json' or receipt.parent.parent != previous.parent:
        raise ValueError('evidence recovery transaction belongs to another owner')
    original = transaction['checkpoint_utf8'].encode()
    if (transaction['version'] != 1 or digest(original) != transaction['checkpoint_sha256']
            or protected_digest(json.loads(original)) != request['baseline_sha256']
            or digest(transaction['queue_before'].encode()) != request['queue_sha256']):
        raise ValueError('evidence recovery original transaction baseline changed')
    recovery_authorization(transaction['authorization_utf8'].encode(), request['authorization'])
    try:
        raw_receipt = _read(receipt, 16 * 1024 * 1024)
    except FileNotFoundError:
        if receipt.parent.exists():
            raise ValueError('evidence recovery original receipt is missing') from None
        # Its exact immutable record survives normal source-run rotation in the
        # controller checkpoint and later accepted proof, not a new allocation.
    else:
        if digest(raw_receipt) != marker['receipt_sha256']:
            pending = dict(transaction, complete=False)
            if receipt.parent == previous and json.loads(raw_receipt) == pending:
                return False  # Finish the exact interrupted original transaction.
            raise ValueError('evidence recovery original receipt changed')
        backup = receipt.parent / ('checkpoint-before-evidence-' + digest(original) + '.json')
        if json.loads(_read(backup)) != {'checkpoint_utf8': original.decode()}:
            raise ValueError('evidence recovery original checkpoint backup changed')
    # Session counts, acceptance and Git ownership remain the current saved
    # values. Validate current ordinary recovery plus the exact disclosed labels.
    plan.validate_recovery(state)
    for saved in (state, *state.get('suspended_tasks', {}).values()):
        rows = {row[2]: row for row in saved['queue_structure']}
        for correction in request['corrections']:
            row = rows.get(correction['task_id'])
            if row is None:
                raise ValueError('evidence recovery corrected baseline is missing')
            if row[6] == '<selected task estimate>' and saved.get('task_id') == row[2]:
                continue
            if (row[6] != correction['after'] and not (
                    saved['queue_before'].get(row[2]) is True
                    and evidence_references(row[6]) == evidence_references(correction['after']))):
                raise ValueError('evidence recovery corrected baseline changed')
    return True


def recover_evidence(plan, state, previous, *, verify_proof, read_authorization=None):
    """Apply or recover a reviewed transaction; caller holds launcher ownership.

    ``verify_proof(correction, request)`` must verify the exact replacement
    bundle and its original input/result/cleanup records, and that its disclosure
    uses the retained authorization's scope. It returns normally only on success.
    ``read_authorization(request)`` may resolve exact authorization bytes from a
    verified bundle. Without it, authorization.checkpoint names a live checkout
    file. Authorization bytes are retained in the transaction before publication.
    No request means no operation. The returned state changes only the reviewed
    Estimate cells in retained queue structures.
    """
    request = request_from_brief(plan, state)
    if request is None:
        return state
    checkpoint = previous / 'checkpoint.json'
    receipt = previous / 'evidence-recovery.json'
    raw = _read(checkpoint)
    if json.loads(raw) != state:
        raise ValueError('evidence recovery checkpoint changed before adoption')
    owner = previous.lstat()
    if (not stat.S_ISDIR(owner.st_mode) or owner.st_uid != os.geteuid()
            or stat.S_IMODE(owner.st_mode) != 0o700):
        raise ValueError('evidence recovery requires the private recorded run owner')
    # Nested test owners must be closed before this administrative transaction
    # can publish even a backup or intent. Refusal leaves queue/checkpoint and
    # transaction records untouched.
    launcher.finish_nested(plan.root, previous)
    if _applied_request(plan, state, previous, request):
        return state
    queue_path = local_file(plan.root, plan.queue)
    queue = _read(queue_path)
    if receipt.exists():
        transaction = json.loads(_read(receipt, 16 * 1024 * 1024))
        if transaction.get('version') != 1 or transaction.get('request') != request:
            raise ValueError('evidence recovery request differs from retained transaction')
        original = transaction['checkpoint_utf8'].encode()
        old_queue, new_queue = (transaction[key].encode() for key in ('queue_before', 'queue_after'))
        if digest(original) != transaction['checkpoint_sha256']:
            raise ValueError('evidence recovery original checkpoint changed')
        backup = previous / ('checkpoint-before-evidence-' + digest(original) + '.json')
        if json.loads(_read(backup)) != {'checkpoint_utf8': original.decode()}:
            raise ValueError('evidence recovery original checkpoint backup changed')
        authority = transaction['authorization_utf8'].encode()
        if transaction.get('complete') is True:
            # The ordinary guards own later sessions and queue close-out. The
            # immutable request/backup remain available after source expiration.
            if digest(authority) != request['authorization']['sha256']:
                raise ValueError('evidence recovery retained authorization changed')
            return _applied_state(state, transaction, receipt)
        candidate_queue, updated = _candidate(plan, json.loads(original), request,
                                             old_queue, verify_proof, authority)
        if queue not in (old_queue, new_queue) or candidate_queue != new_queue:
            raise ValueError('evidence recovery transaction payload changed')
        updated = _applied_state(updated, transaction, receipt)
        if raw not in (original, json.dumps(updated).encode()):
            raise ValueError('evidence recovery checkpoint changed during transaction')
    else:
        authority = (read_authorization(request) if read_authorization is not None else
                     _read(_checkout_path(plan.root, request['authorization']['checkpoint'])))
        new_queue, updated = _candidate(plan, state, request, queue, verify_proof, authority)
        transaction = dict(version=1, complete=False, request=request,
                           checkpoint_sha256=digest(raw), checkpoint_utf8=raw.decode(),
                           authorization_utf8=authority.decode(),
                           queue_before=queue.decode(), queue_after=new_queue.decode())
        updated = _applied_state(updated, transaction, receipt)
        backup = previous / ('checkpoint-before-evidence-' + digest(raw) + '.json')
        if backup.exists():
            if json.loads(_read(backup)) != {'checkpoint_utf8': raw.decode()}:
                raise ValueError('evidence recovery original checkpoint backup changed')
        else:
            launcher.atomic(backup, {'checkpoint_utf8': raw.decode()})
        launcher.atomic(receipt, transaction)
    if queue != new_queue:
        _publish_queue(queue_path, new_queue)
    launcher.atomic(checkpoint, updated)
    transaction['complete'] = True
    launcher.atomic(receipt, transaction)
    return updated
