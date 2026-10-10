"""Native enforcement witnesses, used only inside the guarded installed guest."""

import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import sys
import threading
import time

import system_guest as guest
from system_caller import drop_identity
from system_assertions import call as broker_call, accepted

TARGET = Path('/opt/onpc-test-fixtures-command/native-fixture')
DESKTOP_ID = 'com.puffyslippers.ONPCTest.Command.desktop'
DESKTOP = Path('/usr/share/applications') / DESKTOP_ID
SPACE_TARGET = Path('/opt/onpc-test-fixtures-whitespace/native fixture')
SPACE_DESKTOP_ID = 'com.puffyslippers.ONPCTest.Whitespace.desktop'
SPACE_DESKTOP = Path('/usr/share/applications') / SPACE_DESKTOP_ID
PATTERN_TARGET = Path('/opt/onpc-test-fixtures-pattern/Versioned-1.AppImage')
PATTERN_DESKTOP_ID = 'com.puffyslippers.ONPCTest.Pattern.desktop'
PATTERN_DESKTOP = Path('/usr/share/applications') / PATTERN_DESKTOP_ID
RETENTION_TARGET = Path('/opt/onpc-test-fixtures-retention/native-fixture')
RETENTION_DESKTOP_ID = 'com.puffyslippers.ONPCTest.Retention.desktop'
RETENTION_DESKTOP = Path('/usr/share/applications') / RETENTION_DESKTOP_ID
RULES = Path('/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
COMPILED_RULES = Path('/etc/fapolicyd/compiled.rules')
FAPOLICYD = Path('/usr/sbin/fapolicyd')
IDENTITY = b'ONPC_TEST_LAUNCH_IDENTITY_VERIFIED\n'
READY = b'ONPC_TEST_APPLICATION_READY\n'
DENIED = b'ONPC_TEST_EXEC_DENIED\n'
FUTURE_TRUST = Path('/etc/fapolicyd/trust.d/onpc-system-future.trust')
CATALOG_PREFIX = 'com.puffyslippers.ONPCTest.Catalog.'
CATALOG_COMMAND = 'onpc-test-catalog-relative'
CATALOG_PARENT_COMMAND = 'onpc-test-catalog-parent-only'
CATALOG_SYSTEM_COMMAND = 'onpc-test-catalog-system'
CATALOG_FALLBACK_COMMAND = 'onpc-test-catalog-fallback'
CATALOG_LOCAL_BIN = Path('/usr/local/bin')
CATALOG_SYSTEM_BIN = Path('/usr/bin')


def catalog_entries():
    # A shared ID has distinct targets at every scope. The hidden child entry
    # must mask the system entry, while changing child must restore visibility.
    try:
        from baseline_assets import CATALOG_ENTRIES
    except ImportError:
        from tests.fixtures.baseline_assets import CATALOG_ENTRIES
    return CATALOG_ENTRIES


def fixture_metadata(path):
    return path.lstat()


def verify_fixture_files(declaration, identities, *, root=Path('/')):
    """Read-only baseline check; tests never repair reusable assets."""
    source = guest.PAYLOAD / 'fixtures/mechanical/onpc-test-application'
    guest.require(source.is_file() and not source.is_symlink(), 'enforcement:fixture-missing')
    for filename, (content, mode, role) in declaration.items():
        path = Path(filename)
        guest.require(path.is_relative_to(root), 'enforcement:baseline-fixture-root')
        account = identities[role] if role != 'system' else None
        uid, gid = (account.pw_uid, account.pw_gid) if account else (0, 0)
        info = fixture_metadata(path)
        guest.require(path.resolve() == path and stat.S_ISREG(info.st_mode)
                      and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == mode
                      and (info.st_uid, info.st_gid) == (uid, gid),
                      'enforcement:baseline-fixture-metadata; run tools/prepare-vm')
        for parent in path.parents:
            if not parent.is_relative_to(root):
                break
            data = fixture_metadata(parent)
            guest.require(data.st_uid in (0, uid) and not data.st_mode & 0o022,
                          'enforcement:baseline-fixture-parent')
        if isinstance(content, bytes):
            guest.require(path.read_bytes() == content, 'enforcement:baseline-launcher')
        else:
            guest.require(content == 'mechanical' and guest.sha(path) == guest.sha(source),
                          'enforcement:baseline-fixture-digest; run tools/prepare-vm')


def provision_catalog(accounts):
    """Verify the catalogue fixture captured by prepare-vm."""
    try:
        from baseline_assets import catalogue_files
    except ImportError:
        from tests.fixtures.baseline_assets import catalogue_files
    guest.guard()
    guest.enable_diagnostics()
    identities = {role: pwd.getpwuid(uid) for role, uid in accounts.items()}
    guest.require(set(identities) == {'child', 'other', 'parent'} and
                  len(set(accounts.values())) == 3 and
                  all(entry.pw_uid == accounts[role] and entry.pw_uid > 0
                      for role, entry in identities.items()), 'catalog:fixture-identities')
    verify_fixture_files(catalogue_files(identities, root=TARGET.parent / 'catalog',
                        system_dir=DESKTOP.parent, local_bin=CATALOG_LOCAL_BIN,
                        system_bin=CATALOG_SYSTEM_BIN), identities)
    guest.require(not (CATALOG_LOCAL_BIN / CATALOG_FALLBACK_COMMAND).exists(),
                  'catalog:fixture-collision')
    print('onpc-system: stage=native-catalog-fixture outcome=ready', flush=True)


def observe_catalog(accounts, record):
    """Read through the installed broker as parent, switching selected child."""
    guest.guard()
    root = TARGET.parent / 'catalog'
    for stage, role in (('child', 'child'), ('other', 'other'), ('child-again', 'child')):
        rows = call(accounts['parent'], 'ListApplications', '(u)', (accounts[role],))[0]
        expected = {'Shared': role if role == 'child' else 'system',
                    'ChildOnly' if role == 'child' else 'OtherOnly': role,
                    'Relative': 'system', 'DesktopPath': 'system',
                    'SystemPreferred': 'system', 'SystemFallback': 'system'}
        if role == 'other':
            expected['Masked'] = 'system'
        selected = [row for row in rows if row[0].startswith(CATALOG_PREFIX)]
        guest.require(len(selected) == len(expected) and
                      {row[0] for row in selected} == {
                          f'{CATALOG_PREFIX}{name}.desktop' for name in expected},
                      'catalog:scope-membership')
        for name, source in expected.items():
            row = next(row for row in selected if row[0] == f'{CATALOG_PREFIX}{name}.desktop')
            target = root / f'{source}-{name}'
            if name == 'Relative':
                home = Path(pwd.getpwuid(accounts[role]).pw_dir)
                target = home / ('.local/bin' if role == 'child' else 'bin') / CATALOG_COMMAND
            elif name == 'DesktopPath':
                target = root / 'desktop path' / CATALOG_COMMAND
            elif name == 'SystemPreferred':
                target = CATALOG_LOCAL_BIN / CATALOG_SYSTEM_COMMAND
            elif name == 'SystemFallback':
                target = CATALOG_SYSTEM_BIN / CATALOG_FALLBACK_COMMAND
            guest.require(row[1] == f'ONPC {source} {name}' and
                          row[4] == [str(target)], 'catalog:selected-target')
        system = [row for row in rows if row[0] == DESKTOP_ID]
        guest.require(len(system) == 1 and system[0][4] == [str(TARGET)], 'catalog:system-target')
        record(f'onpc.catalog.{stage}', 'passed')
        print(f'onpc-system: stage=catalog-{stage} outcome=passed', flush=True)


def call(uid, method, signature='()', args=()):
    reply = broker_call(uid, method, signature, args, category='enforcement:caller-reply')
    return accepted(reply, category='enforcement:broker-call-failed')


def native_paths(variant):
    # Requests select maintained fixtures, never caller-supplied executable paths.
    paths = {
        'command': (TARGET, DESKTOP, DESKTOP_ID),
        'whitespace': (SPACE_TARGET, SPACE_DESKTOP, SPACE_DESKTOP_ID),
        'pattern': (PATTERN_TARGET, PATTERN_DESKTOP, PATTERN_DESKTOP_ID),
        'retention': (RETENTION_TARGET, RETENTION_DESKTOP, RETENTION_DESKTOP_ID),
        'pattern-future': (PATTERN_TARGET.with_name('Versioned-2.AppImage'),
                           PATTERN_DESKTOP, PATTERN_DESKTOP_ID),
        'pattern-unrelated': (PATTERN_TARGET.with_name('Unrelated.AppImage'),
                              PATTERN_DESKTOP, PATTERN_DESKTOP_ID),
    }
    guest.require(isinstance(variant, str) and variant in paths,
                  'enforcement:fixture-variant')
    return paths[variant]


def provision_native(variant='command'):
    """Verify fixed native witnesses; installation belongs to prepare-vm."""
    guest.guard()
    target, desktop, _ = native_paths(variant)
    guest.require(variant in ('command', 'whitespace', 'pattern', 'retention'),
                  'enforcement:fixture-variant')
    guest.enable_diagnostics()
    declaration = {
        str(target): ('mechanical', 0o755, 'system'),
        str(desktop): (('[Desktop Entry]\nType=Application\nName=ONPC Native Fixture\n'
                       f'Exec="{target}"\nTerminal=false\n').encode(), 0o644, 'system'),
    }
    if variant == 'pattern':
        unrelated, _, _ = native_paths('pattern-unrelated')
        declaration[str(unrelated)] = ('mechanical', 0o755, 'system')
    verify_fixture_files(declaration, {})
    accounts = {role: pwd.getpwnam(name).pw_uid for role, name in (
        ('child', 'onpc-child-riley'), ('other', 'onpc-child-jordan'),
        ('parent', 'onpc-parent-jamie'))}
    guest.require(len(set(accounts.values())) == 3, 'enforcement:fixture-identities')
    print('onpc-system: stage=native-enforcement-fixture outcome=ready', flush=True)
    return accounts


def provision_future():
    """Create the next version only after the scenario witnesses active rules."""
    guest.guard()
    target, _, _ = native_paths('pattern-future')
    guest.require(PATTERN_TARGET.parent.is_dir() and not PATTERN_TARGET.parent.is_symlink() and
                  PATTERN_TARGET.is_file() and not PATTERN_TARGET.is_symlink() and
                  not target.exists() and not target.is_symlink(),
                  'enforcement:future-fixture-collision')
    # Exclusive creation preserves unexpected files, including dangling symlinks.
    with target.open('xb') as output, PATTERN_TARGET.open('rb') as source:
        shutil.copyfileobj(source, output)
    target.chmod(0o755)
    guest.require(guest.sha(target) == guest.sha(PATTERN_TARGET),
                  'enforcement:fixture-copy-digest')


class TrustRefreshDiagnostic:
    """Private, bounded resource counters; never retain names or signal a PID."""

    def __init__(self):
        self.started_ns = time.perf_counter_ns()
        self.process = None
        self.start_ticks = None
        try:
            fields = dict(line.split('=', 1) for line in guest.run(
                ['systemctl', 'show', 'fapolicyd.service', '--property=MainPID'],
                timeout=10).splitlines() if '=' in line)
            pid = fields.get('MainPID', '')
            if re.fullmatch(r'[1-9][0-9]{0,9}', pid):
                self.process = Path('/proc') / pid
                self.start_ticks = self.process_stat(self.process)['start_ticks']
        except Exception:
            # Instrumentation must not mask the original fixture outcome.
            self.process = None
        self.initial = self.snapshot()

    @staticmethod
    def read(path):
        with path.open('r', encoding='ascii') as stream:
            return stream.read(4096)

    @classmethod
    def process_stat(cls, path):
        # Discard comm, which can contain spaces or personal text. Linux stat
        # fields 14/15, 22 and 42 are CPU ticks, birth identity and I/O delay.
        fields = cls.read(path / 'stat').rsplit(')', 1)[1].split()
        return {name: int(fields[index]) for name, index in (
            ('user_ticks', 11), ('system_ticks', 12), ('start_ticks', 19),
            ('io_delay_ticks', 39))}

    @classmethod
    def counters(cls, path, allowed):
        result = {}
        for line in cls.read(path).splitlines():
            key, separator, value = line.partition(':')
            if separator and key in allowed:
                result[key] = int(value.split()[0])
        return result

    @classmethod
    def database_snapshot(cls, process):
        # Observe only the two fixed LMDB mappings. Never retain addresses,
        # unrelated mapped filenames, or database contents. A replaced inode
        # or a file larger than the daemon's mapping supports the stale
        # snapshot/map-growth hypothesis; matching mappings do not prove
        # the transaction lock is healthy.
        with (process / 'maps').open('r', encoding='ascii', errors='replace') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            return {'maps_truncated': True}
        result = {}
        for name in ('data.mdb', 'lock.mdb'):
            path = Path('/var/lib/fapolicyd') / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                result[name] = {'regular': False}
                continue
            mappings = []
            for line in raw.splitlines():
                fields = line.split(None, 5)
                if len(fields) != 6 or fields[5] not in (str(path), str(path) + ' (deleted)'):
                    continue
                start, end = (int(value, 16) for value in fields[0].split('-'))
                major, minor = (int(value, 16) for value in fields[3].split(':'))
                mappings.append({
                    'bytes': end - start, 'offset': int(fields[2], 16),
                    'writable': 'w' in fields[1], 'shared': fields[1].endswith('s'),
                    'deleted': fields[5].endswith(' (deleted)'),
                    'same_file': (major, minor, int(fields[4])) == (
                        os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)})
                if len(mappings) == 4:
                    break
            result[name] = {'file_bytes': info.st_size, 'mappings': mappings}
        return result

    def snapshot(self):
        result = {'elapsed_ns': time.perf_counter_ns() - self.started_ns,
                  'daemon_identity_unavailable': self.process is None}
        try:
            result['clock_ticks_per_second'] = os.sysconf('SC_CLK_TCK')
            result['cpu'] = [int(value) for value in
                             self.read(Path('/proc/stat')).splitlines()[0].split()[1:]]
            result['memory_kib'] = self.counters(Path('/proc/meminfo'),
                                                {'MemAvailable', 'SwapFree', 'Dirty', 'Writeback'})
            result['test'] = self.process_stat(Path('/proc/self'))
            if self.process is not None:
                current = self.process_stat(self.process)
                if current['start_ticks'] != self.start_ticks:
                    result['daemon_identity_changed'] = True
                    return result
                result['daemon'] = current
                result['daemon_io'] = self.counters(self.process / 'io',
                    {'rchar', 'wchar', 'syscr', 'syscw', 'read_bytes', 'write_bytes'})
                result['daemon_memory_kib'] = self.counters(self.process / 'status',
                    {'VmPeak', 'VmSize', 'VmRSS', 'VmData', 'VmSwap'})
                try:
                    result['database'] = self.database_snapshot(self.process)
                except Exception:
                    result['database_unavailable'] = True
                threads = []
                # Inspect only this daemon, at most 16 threads. Numeric kernel
                # counters and wait channels contain no command/file names.
                for thread in (self.process / 'task').iterdir():
                    if not thread.name.isdecimal():
                        continue
                    if len(threads) == 16:
                        result['threads_truncated'] = True
                        break
                    counters = self.process_stat(thread)
                    wait = self.read(thread / 'wchan').strip()
                    counters['wait'] = wait if re.fullmatch(r'[A-Za-z0-9_]{1,128}', wait) else 'unknown'
                    counters['tid'] = int(thread.name)
                    threads.append(counters)
                result['threads'] = threads
                result['daemon_identity_changed'] = (
                    self.process_stat(self.process)['start_ticks'] != self.start_ticks)
        except Exception:
            result['counters_unavailable'] = True
        return result


class TrustRefreshCompletion:
    """Keep the unlocked CLI reader out of the daemon's database rebuild."""

    def __init__(self):
        self.identity = self.service_identity()
        raw = guest.run(['journalctl', '--no-pager', '--unit=fapolicyd.service',
                         '--lines=1', '--output=json', '--output-fields=__CURSOR'], timeout=10)
        rows = [json.loads(line) for line in raw.splitlines()]
        guest.require(len(rows) == 1 and isinstance(rows[0], dict),
                      'enforcement:trust-journal-cursor')
        self.cursor = rows[0].get('__CURSOR', '')
        guest.require(isinstance(self.cursor, str) and
                      re.fullmatch(r'[A-Za-z0-9;=:_-]{1,1024}', self.cursor) is not None,
                      'enforcement:trust-journal-cursor')

    @staticmethod
    def service_identity(timeout=10, diagnostic=None):
        def retain(raw):
            # Keep the last observation even when this very identity check
            # discovers the daemon exited, before the next journal poll.
            try:
                metrics = {'initial': diagnostic.initial, 'observed': diagnostic.snapshot()}
                return raw + ('\ntrust_refresh=' + json.dumps(metrics, sort_keys=True) + '\n').encode()
            except Exception:
                return raw + b'\ntrust_refresh={"counters_unavailable":true}\n'

        raw = guest.run(['systemctl', 'show', 'fapolicyd.service',
                         '--property=MainPID,InvocationID,ActiveState'], timeout=timeout,
                        **({'diagnostic_stdout': retain} if diagnostic is not None else {}))
        fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        guest.require(fields.get('ActiveState') == 'active' and
                      re.fullmatch(r'[1-9][0-9]{0,9}', fields.get('MainPID', '')) is not None and
                      re.fullmatch(r'[0-9a-f]{32}', fields.get('InvocationID', '')) is not None and
                      fields['InvocationID'] != '0' * 32, 'enforcement:trust-daemon-identity')
        return fields['MainPID'], fields['InvocationID']

    def wait(self, deadline, diagnostic):
        # fapolicyd 1.3.6's --dump-db uses MDB_NOLOCK. A reader racing the
        # asynchronous --update can abort inside LMDB. "Updated" follows the
        # rebuild/sync in both supported fapolicyd versions; it is only a
        # sequencing barrier, never a substitute for the exact database row.
        def budget():
            remaining = deadline - time.monotonic()
            guest.require(remaining > 0, 'enforcement:future-not-trusted')
            return min(10, remaining)

        def retain(raw):
            # Polling needs no application/account text or additional storage.
            metrics = json.dumps({'initial': diagnostic.initial,
                                  'observed': diagnostic.snapshot()}, sort_keys=True)
            return (f'completion_bytes={len(raw)}\ntrust_refresh={metrics}\n').encode()

        while True:
            guest.require(self.service_identity(budget(), diagnostic) == self.identity,
                          'enforcement:trust-daemon-replaced')
            raw = guest.run(['journalctl', '--no-pager', '--unit=fapolicyd.service',
                             '--after-cursor=' + self.cursor, '--lines=1', '--output=json',
                             '--output-fields=MESSAGE,_PID,_SYSTEMD_INVOCATION_ID',
                             '_PID=' + self.identity[0],
                             '_SYSTEMD_INVOCATION_ID=' + self.identity[1], 'MESSAGE=Updated'],
                            timeout=budget(), diagnostic_stdout=retain)
            rows = [json.loads(line) for line in raw.splitlines()]
            complete = any(isinstance(row, dict) and row.get('MESSAGE') == 'Updated' and
                           row.get('_PID') == self.identity[0] and
                           row.get('_SYSTEMD_INVOCATION_ID') == self.identity[1] and
                           row.get('__CURSOR') != self.cursor and
                           isinstance(row.get('__CURSOR'), str) for row in rows)
            guest.require(self.service_identity(budget(), diagnostic) == self.identity,
                          'enforcement:trust-daemon-replaced')
            if complete:
                return
            time.sleep(min(0.25, budget()))


def collect_trust_refresh_failure(identity):
    """Failure-only kernel evidence; no service changes or raw audit text."""
    previous_returncode = guest.commands.last_returncode

    def retain(raw):
        # These observations are valid only with the terminal read outcome
        # below. Empty output from a failed journal command proves no absence.
        result = {'daemon_access_denials': [], 'daemon_oom': False}
        try:
            for line in raw.decode('utf-8', errors='replace').splitlines()[:100]:
                message = json.loads(line).get('MESSAGE', '')
                if not isinstance(message, str):
                    continue
                if re.search(r'\bKilled process ' + re.escape(identity[0]) + r' \(fapolicyd\)', message):
                    result['daemon_oom'] = True
                if ('comm="fapolicyd"' not in message or
                        re.search(r'\bpid=' + re.escape(identity[0]) + r'\b', message) is None or
                        not ('apparmor="DENIED"' in message or
                             re.search(r'\bavc:\s+denied\b', message))):
                    continue
                row = {}
                operation = re.search(r'\boperation="([a-z_]+)"', message)
                if operation and operation[1] in ('file_lock', 'open', 'mmap', 'signal', 'capable'):
                    row['operation'] = operation[1]
                row['database_data'] = '/var/lib/fapolicyd/data.mdb' in message
                row['database_lock'] = '/var/lib/fapolicyd/lock.mdb' in message
                result['daemon_access_denials'].append(row)
        except Exception:
            result['parse_unavailable'] = True
        return (json.dumps(result, sort_keys=True) + '\n').encode()

    try:
        guest.commands.run(['journalctl', '--no-pager', '--quiet', '--dmesg', '--boot',
                            '--since=-3 minutes', '--lines=100', '--output=json',
                            '--output-fields=MESSAGE'],
                           timeout=3, check=False, merge_stderr=False,
                           diagnostic_stdout=retain)
        # Do not use --grep here: its no-match exit status is also 1, making
        # an unavailable journal indistinguishable from no matching events.
        outcome = 'read' if guest.commands.last_returncode == 0 else 'failed'
        print('onpc-system: stage=trust-refresh-kernel outcome=' + outcome, flush=True)
    except Exception:
        # Evidence collection must preserve the original failure and reply.
        print('onpc-system: stage=trust-refresh-kernel outcome=unavailable', flush=True)
    finally:
        guest.commands.last_returncode = previous_returncode


def trust_database_metadata():
    """Read numeric LMDB metadata without writing data or the lock file.

    Called in a bounded child only after confirming the original daemon exited.
    MDB_NOLOCK is unsafe during a rebuild; this is not a readiness reader or a
    replacement for the existing completion barrier and exact trust-row check.
    The structures/functions are the public LMDB C API (lmdb.h).
    """
    import ctypes as c

    class Info(c.Structure):
        _fields_ = [('address', c.c_void_p), ('map_bytes', c.c_size_t),
                    ('last_page', c.c_size_t), ('last_txnid', c.c_size_t),
                    ('max_readers', c.c_uint), ('readers', c.c_uint)]

    class Statistics(c.Structure):
        _fields_ = [('page_bytes', c.c_uint), ('depth', c.c_uint),
                    ('branch_pages', c.c_size_t), ('leaf_pages', c.c_size_t),
                    ('overflow_pages', c.c_size_t), ('entries', c.c_size_t)]

    try:
        lib = c.CDLL('liblmdb.so.0')
    except OSError:
        lib = c.CDLL('liblmdb.so.0.0.0')
    pointer, uint = c.c_void_p, c.c_uint
    signatures = {
        'mdb_version': ([c.POINTER(c.c_int)] * 3, c.c_void_p),
        'mdb_env_create': ([c.POINTER(pointer)], c.c_int),
        'mdb_env_set_maxdbs': ([pointer, uint], c.c_int),
        'mdb_env_open': ([pointer, c.c_char_p, uint, uint], c.c_int),
        'mdb_env_info': ([pointer, c.POINTER(Info)], c.c_int),
        'mdb_env_stat': ([pointer, c.POINTER(Statistics)], c.c_int),
        'mdb_txn_begin': ([pointer, pointer, uint, c.POINTER(pointer)], c.c_int),
        'mdb_dbi_open': ([pointer, c.c_char_p, uint, c.POINTER(uint)], c.c_int),
        'mdb_stat': ([pointer, uint, c.POINTER(Statistics)], c.c_int),
        'mdb_txn_abort': ([pointer], None),
        'mdb_env_close': ([pointer], None),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = arguments, result

    env, txn, dbi = pointer(), pointer(), uint()
    result = {'outcome': 'unavailable'}
    version = [c.c_int() for _ in range(3)]
    lib.mdb_version(*(c.byref(part) for part in version))
    result['library_version'] = [part.value for part in version]
    readonly, nolock = 0x20000, 0x400000

    def check(stage, code):
        if code:
            # Numeric public error codes only; never library/error text.
            result.update(outcome='failed', stage=stage, code=int(code))
            raise ValueError('trust metadata unavailable')

    try:
        check('create', lib.mdb_env_create(c.byref(env)))
        check('maxdbs', lib.mdb_env_set_maxdbs(env, 2))
        check('open', lib.mdb_env_open(env, b'/var/lib/fapolicyd', readonly | nolock, 0))
        info, stats = Info(), Statistics()
        check('info', lib.mdb_env_info(env, c.byref(info)))
        check('stat', lib.mdb_env_stat(env, c.byref(stats)))
        result.update(map_bytes=info.map_bytes, last_page=info.last_page,
                      last_txnid=info.last_txnid, page_bytes=stats.page_bytes,
                      used_bytes=(info.last_page + 1) * stats.page_bytes)
        check('read-transaction', lib.mdb_txn_begin(env, None, readonly, c.byref(txn)))
        check('trust-db', lib.mdb_dbi_open(txn, b'trust.db', 0, c.byref(dbi)))
        check('trust-stat', lib.mdb_stat(txn, dbi, c.byref(stats)))
        result.update(outcome='read', trust_entries=stats.entries, trust_depth=stats.depth)
    except ValueError:
        pass
    finally:
        if txn:
            lib.mdb_txn_abort(txn)
        if env:
            lib.mdb_env_close(env)
    return result


def collect_trust_database_failure(identity):
    """Do not open the database while a live/replacement daemon can write it."""
    previous_returncode = guest.commands.last_returncode
    try:
        raw = guest.run(['systemctl', 'show', 'fapolicyd.service',
                         '--property=MainPID,InvocationID,ActiveState'], timeout=3)
        fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        if (fields.get('MainPID') != '0' or fields.get('ActiveState') != 'failed' or
                fields.get('InvocationID') != identity[1]):
            print('onpc-system: stage=trust-database-metadata outcome=not-exited', flush=True)
            return
        # The child rechecks the exited invocation before using MDB_NOLOCK.
        # No data rows, memory addresses, exceptions or arbitrary paths escape.
        guest.commands.run(['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_enforcement.py'),
                            'trust-database-metadata', identity[1]],
                           timeout=3, check=False, merge_stderr=False)
        outcome = 'collected' if guest.commands.last_returncode == 0 else 'failed'
        print('onpc-system: stage=trust-database-metadata outcome=' + outcome, flush=True)
    except Exception:
        print('onpc-system: stage=trust-database-metadata outcome=unavailable', flush=True)
    finally:
        guest.commands.last_returncode = previous_returncode


def trust_future():
    """Model a newly trusted app version without reconciling product rules.

    This is an explicit engineering mutation after the existing wildcard deny
    has been witnessed, not a prerequisite workaround for an unusable fixture.
    The fixed future file and trust entry belong to the outer VM attempt.
    """
    guest.guard()
    target, _, _ = native_paths('pattern-future')
    guest.require(target.is_file() and not target.is_symlink() and
                  guest.sha(target) == guest.sha(PATTERN_TARGET),
                  'enforcement:future-fixture-digest')
    for parent in FUTURE_TRUST.parents:
        info = parent.lstat()
        guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and
                      not info.st_mode & 0o022, 'enforcement:unsafe-trust-parent')
    guest.require(not FUTURE_TRUST.exists() and not FUTURE_TRUST.is_symlink(),
                  'enforcement:future-trust-collision')
    guest.run(['fapolicyd-cli', '--file', 'add', str(target), '--trust-file', FUTURE_TRUST.name])
    if guest.package_path().suffix == '.rpm':
        guest.run(['restorecon', str(FUTURE_TRUST)])
    diagnostic = TrustRefreshDiagnostic()
    completion = TrustRefreshCompletion()
    guest.run(['fapolicyd-cli', '--update'])
    expected = [str(target), str(target.stat().st_size), guest.sha(target)]
    # Ubuntu's debdb backend rehashes installed packages on --update. The
    # retained VM evidence shows a successful refresh taking about 40 seconds;
    # allow the guest command budget while still requiring the exact DB entry.
    deadline = time.monotonic() + 120
    try:
        completion.wait(deadline, diagnostic)
    except Exception:
        try:
            collect_trust_refresh_failure(completion.identity)
        except Exception:
            pass
        try:
            collect_trust_database_failure(completion.identity)
        except Exception:
            pass
        raise

    def trust_diagnostic(raw):
        # Each Ubuntu database dump is about 26 MB and collection retains
        # several copies. Keep every row for this exact path (including wrong
        # sizes/digests) and a fingerprint of the full observed database.
        # Interrupted output can end inside a UTF-8 path. Diagnostic decoding
        # must not replace the original interruption with a decoding error.
        rows = [line for line in raw.decode('utf-8', errors='replace').splitlines()
                if len(line.split()) >= 2 and line.split()[1] == str(target)]
        header = f'database_bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}\n'
        counters = diagnostic.snapshot()
        counters['dump_duration_ns'] = time.perf_counter_ns() - dump_started_ns
        # Reuse the owned command artifact: no background sampling or new
        # storage lifetime. Keep the initial counters with every database view.
        metrics = json.dumps({'initial': diagnostic.initial, 'observed': counters}, sort_keys=True)
        return (header + 'trust_refresh=' + metrics + '\n' + '\n'.join(rows) + '\n').encode('utf-8')

    while True:
        dump_started_ns = time.perf_counter_ns()
        rows = [row.split() for row in guest.run(
            ['fapolicyd-cli', '--dump-db'], diagnostic_stdout=trust_diagnostic).splitlines()]
        if any(len(row) == 4 and row[1:] == expected for row in rows):
            return
        guest.require(time.monotonic() < deadline, 'enforcement:future-not-trusted')
        time.sleep(0.25)


def remove_retention_launcher(identity):
    """Remove only the fixed guest fixture witnessed before policy activation."""
    guest.guard()
    desktop = RETENTION_DESKTOP
    current = desktop.lstat()
    guest.require(not desktop.parent.is_symlink() and stat.S_ISREG(current.st_mode) and
                  current.st_nlink == 1 and all(
                      getattr(current, field) == getattr(identity, field) for field in (
                          'st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_uid', 'st_gid',
                          'st_size', 'st_mtime_ns', 'st_ctime_ns')),
                  'enforcement:launcher-identity-changed')
    desktop.unlink()
    guest.require(not desktop.exists() and not desktop.is_symlink(),
                  'enforcement:launcher-removal-failed')


def launch_as(uid, variant='command'):
    """One directly owned PID becomes the one-shot fixture; no child to discover."""
    guest.guard()
    target, _, _ = native_paths(variant)
    drop_identity(uid)
    sys.stdout.buffer.write(IDENTITY)
    sys.stdout.buffer.flush()
    try:
        os.execv(str(target), [str(target)])
    except OSError as error:
        if error.errno not in (errno.EACCES, errno.EPERM):
            raise guest.GuestError('enforcement:exec-failed') from None
        sys.stdout.buffer.write(DENIED)
        sys.stdout.buffer.flush()
        return 77


def observe_launch(uid, allowed, variant='command'):
    native_paths(variant)
    raw = guest.commands.run(
        ['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_enforcement.py')],
        input=json.dumps({'uid': uid, 'variant': variant}).encode(),
        timeout=30, check=False, merge_stderr=False)
    expected = IDENTITY + (READY if allowed else DENIED)
    guest.require(raw == expected and guest.commands.last_returncode == (0 if allowed else 77),
                  'enforcement:expected-allow' if allowed else 'enforcement:expected-denial')


def record_rules(stage, uid, blocked, record, variant='command'):
    # Keep the actual source and compiled rules in the existing private text
    # diagnostics, including on assertion failure; public properties use roles.
    target, _, _ = native_paths(variant)
    clause = (f'sha256hash={guest.sha(target)}' if variant == 'whitespace' else
              f'path={target}')
    expected = f'deny_syslog perm=execute uid={uid} : {clause}'
    texts = []
    for label, path in (('source', RULES), ('compiled', COMPILED_RULES)):
        guest.require(path.is_file() and not path.is_symlink(), 'enforcement:rules-missing')
        raw = path.read_bytes()
        (guest.commands.directory / f'native-{variant}-{stage}-{label}.txt').write_bytes(raw)
        texts.append(raw.decode().splitlines())
        record(f'onpc.native.{variant}.{stage}.{label}.sha256', guest.sha(path))
    guest.require(all((expected in lines) == blocked for lines in texts),
                  'enforcement:rule-state')
    if variant == 'pattern':
        unrelated, _, _ = native_paths('pattern-unrelated')
        future, _, _ = native_paths('pattern-future')
        allow = f'allow perm=execute uid={uid} : path={unrelated}'
        deny = f'deny_syslog perm=execute uid={uid} : dir={target.parent}/'
        future_deny = f'deny_syslog perm=execute uid={uid} : path={future}'
        guest.require(all((deny in lines) == blocked and (allow in lines) == blocked
                          and future_deny not in lines
                          and (not blocked or lines.index(allow) < lines.index(deny))
                          for lines in texts), 'enforcement:pattern-rule-state')
    return tuple(tuple(lines) for lines in texts)


def record_execution_backend(record):
    """Identify the installed dependency; this does not witness live policy."""
    version = package_version('fapolicyd')
    guest.require(re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]{0,127}', version) is not None,
                  'enforcement:backend-version')
    # Validate before publishing command-derived text. Never put arbitrary
    # command output, paths supplied by an account, or rule data in properties.
    digest = guest.sha(FAPOLICYD)
    record('onpc.enforcement.fapolicyd.package-version', version)
    record('onpc.enforcement.fapolicyd.executable.sha256', digest)


def package_version(name):
    """Query the installed platform database; never infer a dependency version."""
    guest.require(name in {'fapolicyd', 'systemd'}, 'enforcement:dependency-name')
    command = (['rpm', '-q', '--queryformat', '%{EPOCHNUM}:%{VERSION}-%{RELEASE}', name]
               if guest.package_path().suffix == '.rpm' else
               ['dpkg-query', '-W', '-f=${Version}', name])
    return guest.run(command, timeout=10)


def _lose_probe_sender(client):
    """Test-only transport fault, reusing the retained client's bounded close.

    Do not mark the client logically closing: model external transport loss
    while retaining its original connection and callbacks for the adapter.
    An interrupted/late close is collected on the next call to this helper.
    """
    client._context.push_thread_default()
    try:
        if client._pending is None and not client._connection.is_closed():
            client._start_close()
        client._wait(time.monotonic() + 2)
        return client._pending is None and client._connection.is_closed()
    finally:
        client._context.pop_thread_default()


def native_probe_lifecycle(record, *, refuse_admission=False, lose_sender=False):
    """Qualify the installed adapter against systemd; never claim policy receipt.

    The failure case validates the real waiting peer, then withholds admission.
    Recovery owns that same attempt; no stop/kill, replacement adapter or replay.
    The outer guarded controller retains diagnostics and restores the testbed if
    bounded recovery cannot settle it.
    """
    guest.guard()
    guest.enable_diagnostics()
    record_execution_backend(record)
    version = package_version('systemd')
    guest.require(re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]{0,127}', version) is not None,
                  'probe:manager-version')
    record('onpc.probe.systemd.package-version', version)
    record('onpc.probe.systemd.executable.sha256', guest.sha(Path('/usr/lib/systemd/systemd')))
    previous_path = sys.path[:]
    sys.path[:0] = ['/usr/lib/oh-no-parent-control', '/usr/lib/oh-no-parent-control/broker']
    try:
        from oh_no_parent_control import execution_probe as probe
        from gi.repository import Gio
    finally:
        sys.path[:] = previous_path

    root = Path('/run/oh-no-parent-control/probes')
    metadata = root.lstat()
    guest.require(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == 0 and
                  stat.S_IMODE(metadata.st_mode) == 0o700, 'probe:runtime-provisioning')

    class RefusingProbe(probe.ExecutionProbe):
        binding_observed = False

        def _admission_binding(self, *args):
            super()._admission_binding(*args)
            self.binding_observed = True
            raise probe.ChannelRefused('installed qualification withholds admission')

    class LostSenderProbe(probe.ExecutionProbe):
        sender_lost = False

        def _release(self, result):
            if not self.sender_lost:
                # Never discard the pin until the complete native observation
                # is copied. Earlier-loss refusal is qualified locally only.
                if not (result.create_outcome == 'replied' and result.terminal_observed and
                        result.native_verified and result.admission is not None):
                    return super()._release(result)
                self.sender_lost = _lose_probe_sender(self._client)
                if not self.sender_lost:
                    return result
            return super()._release(result)

    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    adapter_type = (RefusingProbe if refuse_admission else
                    LostSenderProbe if lose_sender else probe.ExecutionProbe)
    adapter = adapter_type(connection)
    result = None
    try:
        result = adapter.run_native()
        # Publish bounded enums/booleans and adapter-owned coordinates only.
        record('onpc.probe.initial.outcome', result.outcome)
        record('onpc.probe.initial.create-error-name', result.create_error_name)
        record('onpc.probe.initial.cleanup-complete', result.cleanup_complete)
        record('onpc.probe.initial.native-verified', result.native_verified)
        record('onpc.probe.initial.terminal-observed', result.terminal_observed)
        record('onpc.probe.initial.channel-result', result.channel_result)
        record('onpc.probe.unit', result.unit)
        record('onpc.probe.manager', result.manager)
        record('onpc.probe.job', result.job)
        guest.require(result.generation is not None, 'probe:generation-missing')
        record('onpc.probe.witness.sha256', result.generation.sha256)
        guest.require(not result.executed, 'probe:receipt-promoted')
        if refuse_admission:
            guest.require(adapter.binding_observed and not result.native_verified and
                          result.admission is None and result.channel_result == '',
                          'probe:expected-admission-refusal')
            guest.require(adapter.pending is not None and not result.cleanup_complete,
                          'probe:expected-retained-attempt')
            guest.require(adapter._generation.verify() == result.generation,
                          'probe:retained-witness')
        else:
            guest.require(result.native_verified and result.outcome == 'identity-unproven' and
                          result.channel_result == 'executed' and result.terminal_observed and
                          result.admission is not None and
                          result.admission.peer.invocation == result.invocation,
                          'probe:expected-native-witness')
    finally:
        deadline = time.monotonic() + 20
        while adapter.pending is not None and time.monotonic() < deadline:
            recovered = adapter.recover()
            if recovered is not None:
                result = recovered
            if adapter.pending is not None:
                time.sleep(0.05)
        record('onpc.probe.cleanup-complete', adapter.pending is None)
        if adapter.pending is not None:
            # Keep exact owned coordinates in private JUnit evidence. The outer
            # controller, not a guessed unit-name operation, owns VM recovery.
            record('onpc.probe.pending.unit', adapter.pending.unit)
            record('onpc.probe.pending.job', adapter.pending.job)
            record('onpc.probe.pending.create-error-name', adapter.pending.create_error_name)
        guest.require(adapter.pending is None, 'probe:cleanup-incomplete')
    if lose_sender:
        record('onpc.probe.sender-lost', adapter.sender_lost)
        guest.require(adapter.sender_lost and not connection.is_closed(), 'probe:sender-loss-missing')
    guest.require(result is not None and result.cleanup_complete and result.client_closed and
                  result.reference_released and not result.executed, 'probe:cleanup-evidence')
    record('onpc.probe.effective-job-timeout-usec', result.job_timeout_usec)
    guest.require(result.job_timeout_usec == 4_000_000, 'probe:effective-job-timeout')
    guest.require(not Path(result.generation.directory).exists(), 'probe:generation-not-collected')
    current = root.lstat()
    guest.require((current.st_dev, current.st_ino, current.st_mode, current.st_uid, current.st_gid) ==
                  (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_uid, metadata.st_gid),
                  'probe:runtime-root-changed')


def _broker_storage_identity():
    raw = guest.run(['systemctl', 'show', guest.BROKER,
                     '--property=MainPID,InvocationID,ActiveState,ProtectSystem,RuntimeDirectoryPreserve'],
                    timeout=10)
    fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    guest.require(fields.get('ActiveState') == 'active' and
                  fields.get('ProtectSystem') == 'strict' and
                  fields.get('RuntimeDirectoryPreserve') == 'yes' and
                  re.fullmatch(r'[1-9][0-9]{0,9}', fields.get('MainPID', '')) is not None and
                  re.fullmatch(r'[0-9a-f]{32}', fields.get('InvocationID', '')) is not None,
                  'probe:broker-storage-identity')
    return fields['MainPID'], fields['InvocationID']


def _in_broker_mount(operation):
    """Read-pin the guarded broker namespace; never signal its discovered PID.

    Unshare filesystem state in a dedicated joined thread before setns/chroot.
    No caller thread changes namespace/root, even if the operation fails. The
    retained root FD prevents absolute paths from using the old root mount.
    This qualifies mount restrictions, not the broker's capabilities/seccomp.
    """
    guest.guard()
    identity = _broker_storage_identity()
    descriptors = []
    try:
        namespace = os.open(f'/proc/{identity[0]}/ns/mnt', os.O_RDONLY | os.O_CLOEXEC)
        descriptors.append(namespace)
        root = os.open(f'/proc/{identity[0]}/root', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        descriptors.append(root)
        guest.require(_broker_storage_identity() == identity, 'probe:broker-replaced')
        expected = os.fstat(namespace).st_ino
        guest.require(expected != os.stat('/proc/thread-self/ns/mnt').st_ino,
                      'probe:broker-mount-not-isolated')
        results, errors = [], []

        def worker():
            try:
                os.unshare(os.CLONE_FS)
                os.setns(namespace, os.CLONE_NEWNS)
                os.fchdir(root)
                os.chroot('.')
                os.chdir('/')
                guest.require(os.stat('/proc/thread-self/ns/mnt').st_ino == expected,
                              'probe:broker-mount-mismatch')
                guest.require(os.statvfs('/usr').f_flag & os.ST_RDONLY,
                              'probe:strict-mount-not-readonly')
                results.append(operation())
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=worker, name='onpc-probe-storage')
        thread.start()
        try:
            thread.join()
        finally:
            # Do not close descriptors or hand off while the owned worker lives.
            while thread.is_alive():
                thread.join()
        if errors:
            raise errors[0]
        guest.require(len(results) == 1, 'probe:storage-worker-result')
        guest.require(_broker_storage_identity() == identity, 'probe:broker-replaced')
        return results[0], identity
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def native_probe_storage_lifecycle(record):
    """Preserve one exact owner across stop/start and restart; never adopt residue."""
    guest.guard()
    guest.enable_diagnostics()
    previous_path = sys.path[:]
    sys.path[:0] = ['/usr/lib/oh-no-parent-control', '/usr/lib/oh-no-parent-control/broker']
    try:
        from oh_no_parent_control.probe_generation import ProbeGeneration
    finally:
        sys.path[:] = previous_path
    # Retain before prepare, including partial creation and worker failure.
    owner, fresh = ProbeGeneration(), ProbeGeneration()
    try:
        identity, broker = _in_broker_mount(owner.prepare)
        record('onpc.probe.storage.witness.sha256', identity.sha256)
        record('onpc.probe.storage.generation', identity.token)
        guest.require(not owner.close(settled=False) and owner.verify() == identity,
                      'probe:unsettled-storage-not-retained')
        guest.require(_broker_storage_identity() == broker, 'probe:broker-replaced')
        guest.run(['systemctl', 'stop', guest.BROKER], timeout=20)
        guest.require(guest.run(['systemctl', 'show', guest.BROKER,
                                 '--property=ActiveState', '--value'], timeout=10) == 'inactive',
                      'probe:broker-not-stopped')
        guest.require(owner.verify() == identity, 'probe:storage-lost-on-stop')
        record('onpc.probe.storage.stop-preserved', True)
        guest.run(['systemctl', 'start', guest.BROKER], timeout=30)
        preserved, started = _in_broker_mount(owner.verify)
        guest.require(preserved == identity and started[1] != broker[1],
                      'probe:storage-start-identity')
        guest.run(['systemctl', 'restart', guest.BROKER], timeout=30)
        preserved, restarted = _in_broker_mount(owner.verify)
        guest.require(preserved == identity and restarted[1] != started[1],
                      'probe:storage-restart-identity')
        other, current = _in_broker_mount(fresh.prepare)
        guest.require(current == restarted and other.token != identity.token and
                      owner.verify() == identity, 'probe:storage-residue-adopted')
        record('onpc.probe.storage.restart-preserved', True)
        record('onpc.probe.storage.fresh-independent', True)
    finally:
        # These owners never dispatch a unit or open a channel: settlement is
        # certain after the worker joins. No recursive cleanup or broker-PID kill.
        fresh_closed = owner_closed = False
        try:
            try:
                fresh_closed = fresh.close(settled=True)
            finally:
                owner_closed = owner.close(settled=True)
        finally:
            record('onpc.probe.storage.cleanup-complete', fresh_closed and owner_closed)
        guest.require(fresh_closed and owner_closed, 'probe:storage-cleanup-incomplete')
    guest.require(_broker_storage_identity() == restarted, 'probe:broker-replaced')


def native_policy_transition(accounts, record, variant='command'):
    """Hard/soft denial in both screen-time states, with UID isolation throughout."""
    guest.guard()
    target, desktop, desktop_id = native_paths(variant)
    guest.require(variant in ('command', 'whitespace', 'pattern', 'retention'),
                  'enforcement:fixture-variant')
    record_execution_backend(record)
    prefix = f'onpc.native.{variant}'
    record(f'{prefix}.fixture.sha256', guest.sha(target))
    parent, child, other = (accounts[role] for role in ('parent', 'child', 'other'))
    applications = call(parent, 'ListApplications', '(u)', (child,))[0]
    matches = [row for row in applications if row[0] == desktop_id]
    guest.require(len(matches) == 1 and matches[0][4] == [str(target)],
                  'enforcement:catalog-target')
    original = call(parent, 'GetPreferences', '(u)', (child,))[0]
    preferences = json.loads(original)
    guest.require(not preferences['apps'] and not preferences['parent_control_enabled'],
                  'enforcement:requires-clean-policy')
    other_before = call(parent, 'GetPreferences', '(u)', (other,))[0]
    original_limit = preferences['daily_time_limit_minutes']
    screen_time_attempted = False
    future_created = False
    launcher_identity = desktop.lstat() if variant == 'retention' else None
    if variant == 'pattern':
        future, _, _ = native_paths('pattern-future')
        guest.require(not future.exists() and not future.is_symlink(),
                      'enforcement:future-fixture-collision')
    try:
        # Clear and witness the hard denial before testing soft policy so stale
        # hard rules cannot satisfy the conditional-policy assertion.
        for stage, app_state in (('allowed', None), ('hard', 'permanent'),
                                 ('restored', None), ('soft', 'conditional'),
                                 ('soft-restored', None), ('enabled-allowed', None),
                                 ('enabled-hard', 'permanent'), ('enabled-restored', None),
                                 ('enabled-soft', 'conditional'), ('enabled-soft-restored', None)):
            enabled = stage.startswith('enabled-')
            if enabled and not screen_time_attempted:
                # SetPreferences deliberately cannot toggle screen-time control.
                # Mark before calling: even a failed reply can follow a write.
                screen_time_attempted = True
                call(parent, 'SetParentControl', '(ubu)', (child, True, original_limit))
                toggled = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
                guest.require(toggled['parent_control_enabled'] is True and
                              toggled['daily_time_limit_minutes'] == original_limit and
                              toggled['apps'] == preferences['apps'],
                              'enforcement:screen-time-readback')
            preferences['parent_control_enabled'] = enabled
            blocked = app_state is not None
            preferences['apps'] = ({desktop_id: {
                'state': app_state, 'targets': [str(target)],
                'patterns': [str(target.with_name('Versioned-*.AppImage'))] if variant == 'pattern' else [],
                'user_saved_match_rule': variant == 'pattern'}} if blocked else {})
            call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences)))
            saved = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
            guest.require(saved['parent_control_enabled'] is enabled and
                          saved['daily_time_limit_minutes'] == original_limit and
                          saved['apps'] == preferences['apps'],
                          'enforcement:policy-readback')
            rules_before = record_rules(stage, child, blocked, record, variant=variant)
            if variant == 'retention' and stage == 'hard':
                remove_retention_launcher(launcher_identity)
                applications = call(parent, 'ListApplications', '(u)', (child,))[0]
                guest.require(all(row[0] != desktop_id for row in applications),
                              'enforcement:launcher-still-listed')
                record(f'{prefix}.missing.catalog', 'absent')
                retained = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
                guest.require(retained == saved, 'enforcement:missing-policy-lost')
                # Exercise the public save's catalog reconciliation, not just
                # persistence before the next write. The executable stays put.
                call(parent, 'SetPreferences', '(us)', (child, json.dumps(retained)))
                retained = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
                guest.require(retained == saved, 'enforcement:missing-policy-lost')
                record_rules('missing', child, True, record, variant=variant)
                record(f'{prefix}.missing.saved-policy', 'retained')
            if variant == 'pattern' and stage == 'hard':
                provision_future()
                future_created = True
                record(f'{prefix}.future.fixture.sha256', guest.sha(future))
            observe_launch(child, not blocked, variant=variant)
            record(f'{prefix}.{stage}.child', 'denied' if blocked else 'allowed')
            observe_launch(other, True, variant=variant)
            record(f'{prefix}.{stage}.other', 'allowed')
            if variant == 'pattern':
                for launch_variant in ('pattern-unrelated', 'pattern-future'):
                    if launch_variant == 'pattern-future' and not future_created:
                        continue
                    allowed = launch_variant == 'pattern-unrelated' or not blocked
                    observe_launch(child, allowed, variant=launch_variant)
                    record(f'{prefix}.{stage}.{launch_variant}.child',
                           'allowed' if allowed else 'denied')
                    observe_launch(other, True, variant=launch_variant)
                    record(f'{prefix}.{stage}.{launch_variant}.other', 'allowed')
                if stage == 'hard':
                    # Trusted files can encounter a distribution allow before
                    # late wildcard guards. Prove the same future version stays
                    # denied after native trust admission, with no policy rescan.
                    trust_future()
                    observe_launch(child, False, variant='pattern-future')
                    observe_launch(other, True, variant='pattern-future')
                    record(f'{prefix}.future.trusted-child-denied', 'passed')
                    rules_after = record_rules('hard-future', child, True, record, variant=variant)
                    guest.require(rules_after == rules_before, 'enforcement:future-rules-changed')
                    record(f'{prefix}.future.unchanged-rules', 'passed')
            guest.require(call(parent, 'GetPreferences', '(u)', (other,))[0] == other_before,
                          'enforcement:other-preferences-changed')
            print(f'onpc-system: stage=native-{variant}-{stage} outcome=passed', flush=True)
    finally:
        # This is the scenario's policy restoration. Outer VM baseline cleanup
        # remains authoritative on failure; never hide the original exception.
        failed = sys.exc_info()[0] is not None
        restoration_error = None
        if screen_time_attempted:
            try:
                call(parent, 'SetParentControl', '(ubu)', (child, False, original_limit))
            except Exception as error:
                restoration_error = error
        # Restore app choices even if disabling screen time failed. The full
        # preference readback must still reject a retained enabled state.
        try:
            call(parent, 'SetPreferences', '(us)', (child, original))
            guest.require(call(parent, 'GetPreferences', '(u)', (child,))[0] == original,
                          'enforcement:policy-restore-mismatch')
            guest.require(call(parent, 'GetPreferences', '(u)', (other,))[0] == other_before,
                          'enforcement:other-preferences-changed')
        except Exception as error:
            restoration_error = restoration_error or error
        if restoration_error is not None:
            record(f'{prefix}.policy-restoration', 'failed')
            if not failed:
                raise restoration_error
        else:
            record(f'{prefix}.policy-restoration', 'passed')


def main():
    try:
        if len(sys.argv) == 3 and sys.argv[1] == 'trust-database-metadata':
            guest.guard()
            guest.require(re.fullmatch(r'[0-9a-f]{32}', sys.argv[2]) is not None and
                          sys.argv[2] != '0' * 32, 'enforcement:trust-diagnostic-identity')
            raw = guest.run(['systemctl', 'show', 'fapolicyd.service',
                             '--property=MainPID,InvocationID,ActiveState'], timeout=1)
            fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
            guest.require(fields.get('MainPID') == '0' and fields.get('ActiveState') == 'failed' and
                          fields.get('InvocationID') == sys.argv[2],
                          'enforcement:trust-diagnostic-not-exited')
            try:
                metadata = trust_database_metadata()
            except Exception:
                metadata = {'outcome': 'unavailable'}
            print(json.dumps(metadata, sort_keys=True), flush=True)
            return 0
        request = json.load(sys.stdin)
        guest.require(isinstance(request, dict) and set(request) == {'uid', 'variant'},
                      'enforcement:launch-request')
        return launch_as(request['uid'], request['variant'])
    except (guest.GuestError, OSError, ValueError, KeyError, TypeError):
        print('onpc-system: stage=native-launch outcome=failed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
