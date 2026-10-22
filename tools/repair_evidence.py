"""Bounded private failure copies that survive execution-journal rotation.

The repair launcher's registered run owns these small snapshots. Bulk captures
remain in execution storage; privileged reads use the installed artifact reader.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from detached_launcher import atomic, environment
from test_retention import directory


MAX_BYTES = 4 * 1024 * 1024
FILE_BYTES = 128 * 1024
MAX_FILES = 64


def controller_sources(extra=(), *, root=None):
    """Use the reviewed shared closure and specialized decision owners' bytes."""
    from plan_launcher import RESPONSE_VALIDATOR_SOURCES
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    names = (*RESPONSE_VALIDATOR_SOURCES, 'repair_evidence.py', 'fix_tests.py',
             'fix_tests_git.py', 'write_e2e.py', 'e2e_progress.py',
             'e2e_startup_cache.py', 'fix_tests_response.schema.json',
             'write_e2e_response.schema.json', *extra)
    return {name: hashlib.sha256((root / 'tools' / name).read_bytes()).hexdigest()
            for name in dict.fromkeys(names)}


def retain_turn(run, identity, *, require_cleanup=True):
    """Retain a complete controller handoff, separately from diagnostic tails.

    Files stay inside the launcher's existing registered allocation. References
    to bulk proof keep using the runner's cumulative capture publication.
    """
    from plan_evidence import _read
    run = Path(run)
    files = {}
    for name in ('agent-result.json', 'prompt.txt', 'agent-commands.log',
                 'agent-error.json', 'rejected-agent-result.json',
                 'developer-answers.json', 'nested.json', 'nested-closed',
                 'checkpoint.json'):
        try:
            files[name] = base64.b64encode(_read(run / name)).decode('ascii')
        except FileNotFoundError:
            continue
    if require_cleanup and 'nested-closed' not in files:
        raise ValueError('specialized evidence: nested cleanup has not finished')
    value = dict(schema=1, identity=identity, files=files)
    hashed = hashlib.sha256(_encoded(value)).hexdigest()
    path = run / f'specialized-turn-{hashed}.json'
    if path.exists():
        if _read(path) != _encoded(value):
            raise ValueError('specialized evidence: retained turn changed')
    else:
        _save(path, value)
    return dict(schema=1, path=str(path), sha256=hashed)


def _encoded(value):
    return json.dumps(value).encode('utf-8')


def _save(path, value):
    from plan_evidence import _atomic
    _atomic(path, _encoded(value))


def read_turn(reference):
    """Verify one exact capsule before carrying or replaying its response."""
    from plan_evidence import _read
    if (type(reference) is not dict or set(reference) != {'schema', 'path', 'sha256'}
            or type(reference['schema']) is not int or reference['schema'] != 1
            or type(reference['path']) is not str
            or type(reference['sha256']) is not str
            or re.fullmatch(r'[0-9a-f]{64}', reference['sha256']) is None):
        raise ValueError('specialized evidence: invalid retained turn reference')
    source = Path(reference['path'])
    if (not source.is_absolute() or '..' in source.parts
            or source.name != f'specialized-turn-{reference["sha256"]}.json'):
        raise ValueError('specialized evidence: invalid retained turn path')
    data = _read(source)
    if hashlib.sha256(data).hexdigest() != reference['sha256']:
        raise ValueError('specialized evidence: retained turn changed')
    value = json.loads(data)
    if (type(value) is not dict or set(value) != {'schema', 'identity', 'files'}
            or type(value['schema']) is not int or value['schema'] != 1
            or type(value['files']) is not dict or _encoded(value) != data):
        raise ValueError('specialized evidence: invalid retained turn')
    return value


def carry_turns(run, references):
    """Copy exact prior handoffs before the previous launcher run can rotate."""
    from plan_evidence import _read
    run = Path(run)
    carried = []
    for reference in references:
        value = read_turn(reference)
        source = Path(reference['path'])
        data = _encoded(value)
        target = run / source.name
        if target.exists():
            if _read(target) != data:
                raise ValueError('specialized evidence: carried turn conflicts')
        else:
            _save(target, value)
        carried.append(dict(reference, path=str(target)))
    return carried


def verify_runner(root, handoff):
    """Authenticate the exact producer declarations without inferring verdicts."""
    import evidence_identity as logical
    from runner_evidence import resolve_reference
    if (type(handoff) is not dict or set(handoff) != {
            'schema', 'receipt', 'capture_ids', 'records', 'references', 'consumers'}
            or type(handoff['schema']) is not int or handoff['schema'] != 1
            or type(handoff['records']) is not list or not handoff['records']
            or len(handoff['records']) > logical.MAX_ENTRIES):
        raise ValueError('specialized evidence: invalid runner handoff')
    records = handoff['records']
    expected = []
    for record in records:
        logical._record(record)
        if not record['members']:
            raise ValueError('specialized evidence: runner record has no members')
        for member in record['members']:
            expected.append(dict(schema=1, workflow=record['context']['workflow'],
                record_id=record['record_id'], member_id=member['member_id'],
                closure_sha256=record['closure_sha256']))
    if (handoff['references'] != expected or len({record['record_id'] for record in records}) != len(records)
            or type(handoff['consumers']) is not list or len(handoff['consumers']) != len(records)):
        raise ValueError('specialized evidence: runner member inventory changed')
    for record, consumer in zip(records, handoff['consumers']):
        logical.validate_consumer(consumer)
        references = sorted([dict(kind='evidence', **{key: reference[key] for key in (
            'record_id', 'member_id', 'closure_sha256')}) for reference in expected
            if reference['record_id'] == record['record_id']], key=logical.encoded)
        role = ('required_evidence' if record['status'] == 'passed'
            and record['completeness'] == 'complete' and record['cleanup']['state'] == 'complete'
            else 'historical_information')
        if (consumer['expected_context'] != record['context'] or consumer['references'] != references
                or consumer['role'] != role or consumer['state'] != 'working'):
            raise ValueError('specialized evidence: runner consumer changed')
        reference = next(item for item in expected if item['record_id'] == record['record_id'])
        resolve_reference(root, reference, consumer=consumer, count=0)
    return handoff


def retain_runner(root, run, log):
    """Read full structured records before ordinary bounded log compaction."""
    from evidence_identity import MAX_METADATA
    from plan_evidence import _read
    handoffs = []
    with Path(log).open('rb') as stream:
        while line := stream.readline(MAX_METADATA + 1):
            if len(line) > MAX_METADATA:
                raise ValueError('specialized evidence: runner output line exceeds metadata bound')
            if not line.startswith(b'Runner evidence: '):
                continue
            value = verify_runner(root, json.loads(line.removeprefix(b'Runner evidence: ')))
            hashed = hashlib.sha256(_encoded(value)).hexdigest()
            path = Path(run) / f'runner-evidence-{hashed}.json'
            if path.exists():
                if _read(path) != _encoded(value):
                    raise ValueError('specialized evidence: retained runner handoff changed')
            else:
                _save(path, value)
            handoffs.append(value)
    return handoffs


def read_failure(root, path, handoffs):
    """Recover only the exact failure member; denied live reads never fall back."""
    from plan_evidence import _read
    from runner_evidence import resolve_reference
    if not handoffs:
        return json.loads(_read(Path(path)))  # Versioned legacy handoff route.
    matches = []
    for handoff in handoffs:
        verify_runner(root, handoff)
        for record, consumer in zip(handoff['records'], handoff['consumers']):
            for member in record['members']:
                if member['original_path'] == str(path) and member['role'] == 'result':
                    reference = next(item for item in handoff['references']
                                     if item['member_id'] == member['member_id'])
                    matches.append((reference, consumer))
    if len(matches) != 1:
        raise ValueError('specialized evidence: exact failure member is missing or ambiguous')
    reference, consumer = matches[0]
    return json.loads(resolve_reference(root, reference, consumer=consumer))


def capture(root, destination, handoff_path, output):
    """Preserve reports and the failed attempt's command tails before retrying.

    Never follow free-form prompt paths. Discover only runner handoff records,
    adjacent report logs and structured failed-attempt raw_directory fields.
    Missing/refused/truncated evidence stays explicit and cannot imply a pass.
    """
    root = Path(root)
    storage = root / 'output/test-runs'
    files, failures, seen = [], [], set()
    remaining = MAX_BYTES
    raw_directories = set()
    privileged_refused = False

    def source(value):
        path = Path(value)
        if (not path.is_absolute() or '..' in path.parts
                or not path.is_relative_to(storage)):
            raise ValueError('outside test storage')
        return path

    def read(path, *, listing=False):
        nonlocal privileged_refused
        path = source(path)
        try:
            # Pin every directory and refuse links/hard links/special files.
            parent = directory(path.parent)
            try:
                fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=parent)
            finally:
                os.close(parent)
            try:
                info = os.fstat(fd)
                if info.st_uid not in (0, os.geteuid()):
                    raise ValueError('foreign artifact owner')
                if listing:
                    if not stat.S_ISDIR(info.st_mode):
                        raise ValueError('not a directory')
                    return sorted(os.listdir(fd))
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('not a singly linked regular file')
                os.lseek(fd, max(0, info.st_size - FILE_BYTES), os.SEEK_SET)
                return os.read(fd, FILE_BYTES).decode('utf-8', errors='replace')
            finally:
                os.close(fd)
        except PermissionError:
            # This fixed read-only helper validates the complete privileged path.
            # A denial never causes another authentication attempt in this capture.
            if privileged_refused:
                raise ValueError('artifact reader previously refused')
            args = ['pkexec', '--keep-cwd', '/usr/local/libexec/onpc-test-artifacts',
                    'list' if listing else 'tail', str(path)]
            if not listing:
                args += ['--bytes', str(FILE_BYTES)]
            result = subprocess.run(args, cwd=root, env=environment(),
                                    capture_output=True, timeout=20, check=False)
            if result.returncode:
                privileged_refused = True
                raise ValueError('artifact reader refused')
            if listing:
                names = json.loads(result.stdout)
                if not isinstance(names, list) or any(type(name) is not str for name in names):
                    raise ValueError('invalid artifact listing')
                return names
            return result.stdout.decode('utf-8', errors='replace')

    def save(path):
        nonlocal remaining
        path = source(path)
        if path in seen or len(seen) >= MAX_FILES or remaining <= 0:
            return None
        seen.add(path)
        try:
            content = read(path)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            failures.append({'source': str(path), 'error': type(error).__name__})
            return None
        encoded = content.encode('utf-8')
        limit = min(FILE_BYTES, remaining)
        content = encoded[-limit:].decode('utf-8', errors='ignore')
        remaining -= len(content.encode('utf-8'))
        files.append({'source': str(path), 'tail': content,
                      'tail_limit_bytes': limit,
                      'may_be_truncated': len(encoded) >= FILE_BYTES or len(encoded) > limit})
        return content

    def attempts(content):
        for line in content.splitlines():
            try:
                value = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(value, dict):
                continue
            records = value.get('attempts', [])
            if not isinstance(records, list):
                continue
            for attempt in records:
                if (isinstance(attempt, dict) and attempt.get('outcome') != 'passed'
                        and isinstance(attempt.get('raw_directory'), str)):
                    path = source(attempt['raw_directory'])
                    if path.parent == storage / 'privileged/allocations':
                        raw_directories.add(path)

    try:
        pending = [source(handoff_path)]
    except ValueError:
        pending = []
        failures.append({'source': str(handoff_path), 'error': 'outside test storage'})
    reports = set()
    for path in pending:
        if path.parent in reports or len(reports) >= 8:
            continue
        reports.add(path.parent)
        save(path)
        # Queue results link the per-VM handoffs; reports own category logs.
        try:
            names = read(path.parent, listing=True)
            if 'results.json' in names:
                results = json.loads(save(path.parent / 'results.json') or '{}')
                if not isinstance(results, dict):
                    raise ValueError('invalid queue results')
                for result in results.values():
                    if isinstance(result, dict):
                        handoffs = result.get('handoffs', [])
                        if (not isinstance(handoffs, list)
                                or any(type(item) is not str for item in handoffs)):
                            raise ValueError('invalid queue handoffs')
                        pending.extend(source(item) for item in handoffs)
            for name in names:
                if re.fullmatch(r'category-[0-9]+\.log', name):
                    attempts(save(path.parent / name) or '')
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            failures.append({'source': str(path.parent), 'error': type(error).__name__})

    for raw in sorted(raw_directories):
        private = raw / 'private'
        try:
            names = read(private, listing=True)
            errors = [name for name in names
                      if re.fullmatch(r'command-[0-9]+-stderr\.txt', name)]
            outputs = [name for name in names
                       if re.fullmatch(r'command-[0-9]+\.txt', name)]
            # Error streams first: cleanup can add successful command outputs
            # after the operation that failed. Keep corresponding stdout too.
            for name in errors[-16:]:
                save(private / name)
                save(private / name.replace('-stderr', ''))
            for name in outputs[-8:]:
                save(private / name)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            failures.append({'source': str(private), 'error': type(error).__name__})

    atomic(destination, {'schema_version': 1, 'output_tail': output,
                         'files': files, 'read_failures': failures,
                         'bounded_tails': True,
                         'limit_reached': remaining <= 0 or len(seen) >= MAX_FILES})
    Path(destination).chmod(0o600)
    return str(destination)
