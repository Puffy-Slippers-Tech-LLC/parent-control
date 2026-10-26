"""Bounded private failure copies that survive execution-journal rotation.

The repair launcher's registered run owns these small snapshots. Bulk captures
remain in execution storage; privileged reads use the installed artifact reader.
"""

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
             'fix_tests_git.py', 'fix_tests_queue.py', 'write_e2e.py', 'e2e_progress.py',
             'e2e_startup_cache.py', 'fix_tests_response.schema.json',
             'write_e2e_response.schema.json', *extra)
    return {name: hashlib.sha256((root / 'tools' / name).read_bytes()).hexdigest()
            for name in dict.fromkeys(names)}


def read_failure(path):
    """Read the current runner's exact failure record without archive lookup."""
    from plan_evidence import _read
    return json.loads(_read(Path(path)))


def capture(root, destination, handoff_path, output):
    """Preserve reports and the failed attempt's command tails before retrying.

    Never follow free-form prompt paths. Discover only runner handoff records,
    adjacent report logs, structured failed-attempt raw_directory fields and
    the installed-system runner's fixed evidence-directory marker.
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
            # System preparation can fail before any case result exists. Its
            # runner still finalizes this evidence marker after owned cleanup.
            match = re.fullmatch(r'check-system: \[evidence:(.+)\]', line)
            if match:
                path = source(match[1])
                raw = path.parent
                if (path.name == 'evidence'
                        and raw.parent == storage / 'privileged/allocations'
                        and re.fullmatch(r'onpc-system-[A-Za-z0-9_-]+', raw.name)):
                    raw_directories.add(raw)
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
            failed_sequences = []
            if raw.name.startswith('onpc-system-'):
                save(raw / 'evidence/result.json')
                provenance = save(raw / 'commands.json')
                try:
                    records = json.loads(provenance or 'null')
                except ValueError:
                    records = None  # A bounded tail may not contain complete JSON.
                if isinstance(records, list):
                    failed_sequences = [record['sequence'] for record in records
                        if isinstance(record, dict) and record.get('check') is True
                        and type(record.get('exit_status')) is int
                        and record['exit_status'] != 0
                        and type(record.get('sequence')) is int
                        and record['sequence'] > 0]
            names = read(private, listing=True)
            # Cleanup/readiness commands may follow the failed installation.
            # Prioritize its exact streams before the recent-output fallback.
            for sequence in failed_sequences[-8:]:
                for suffix in ('-stderr.txt', '.txt'):
                    name = f'command-{sequence:04d}{suffix}'
                    if name in names:
                        save(private / name)
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
