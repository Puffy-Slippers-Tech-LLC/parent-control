import json
import configparser
import ctypes
import fcntl
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

_activation = runpy.run_path(str(Path(__file__).resolve().parents[2] / "debian/package_activation.py"))
activation_for = _activation["activation_for"]
changed_impacts = _activation["changed_impacts"]
generate = _activation["generate"]


@pytest.mark.parametrize('path', [
    'usr/lib/systemd/user/oh-no-parent-control-wellbeing.service',
    'usr/lib/systemd/user/default.target.wants/oh-no-parent-control-wellbeing.service',
    'usr/share/dbus-1/services/com.puffyslippers.OhNoParentControl.Wellbeing.service',
    *[f'{_activation["EXTENSION_PATH"]}/{name}' for name in (
        'wellbeingService.js', 'wellbeingLogic.mjs',
        'schemas/com.puffyslippers.oh-no-parent-control.child.gschema.xml',
        'schemas/gschemas.compiled')],
])
def test_user_manager_recovery_updates_require_a_fresh_manager(tmp_path, path):
    # Logout/login is insufficient with lingering or another active login.
    # Verify both classification and the upgrade decision consumed by packages.
    assert activation_for(path) == 'reboot'
    installed = tmp_path / path
    installed.parent.mkdir(parents=True)
    installed.write_text('old helper')
    old, new = tmp_path / 'old.json', tmp_path / 'new.json'
    generate(tmp_path, old, includes=[Path(path)])
    installed.write_text('updated helper')
    generate(tmp_path, new, includes=[Path(path)])
    assert changed_impacts(old, new) == ['reboot']
    installed.unlink()
    generate(tmp_path, old, includes=[Path(path)])
    assert changed_impacts(new, old) == ['reboot']


def test_shell_only_suppression_client_update_still_needs_session_renewal():
    assert activation_for(f'{_activation["EXTENSION_PATH"]}/wellbeingSuppression.js') == 'session-renewal'


@pytest.mark.parametrize('refresh', [False, True])
@pytest.mark.parametrize('fault', ['delayed', 'missing', 'command', 'timeout', 'update', 'malformed'])
def test_child_trust_wait_requires_committed_exact_records(tmp_path, monkeypatch, refresh, fault):
    wait = _activation['wait_child_trust']
    namespace = wait.__globals__
    records = [f'/{_activation["EXTENSION_PATH"]}/{name}.mjs 12 ' + digest * 64
               for name, digest in [('indicatorLogic', 'a'), ('diagnosticEvents', 'b')]]
    trust = tmp_path / 'child.trust'
    trust.write_text('# packaged\n' + '\n'.join(records) + '\n')
    complete = json.dumps([line.split() for line in records])
    state = dict(clock=0, reads=0, updates=0)

    def run(argv, **kwargs):
        assert 0 < kwargs['timeout'] <= 120 - state['clock']
        assert kwargs['check'] and kwargs['capture_output']
        assert kwargs['env']['LC_ALL'] == 'C'
        if argv == ['/usr/sbin/fapolicyd-cli', '--update']:
            state['updates'] += 1
            if fault == 'update':
                raise subprocess.CalledProcessError(1, argv)
            state['clock'] += 30
            return SimpleNamespace(stdout='')
        assert argv == [sys.executable, '-I', str(Path(namespace['__file__']).resolve()),
                        'read-child-trust']
        state['reads'] += 1
        if fault == 'command':
            raise subprocess.CalledProcessError(1, argv)
        if fault == 'timeout':
            raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
        if fault == 'malformed':
            return SimpleNamespace(stdout='["private invalid record"]')
        return SimpleNamespace(stdout=(complete if fault != 'missing' and state['reads'] > 1
                                       else '[]'))

    monkeypatch.setattr(namespace['subprocess'], 'run', run)
    monkeypatch.setattr(namespace['time'], 'monotonic', lambda: state['clock'])

    def sleep(delay):
        assert 0 < delay <= .25
        state['clock'] += 40

    monkeypatch.setattr(namespace['time'], 'sleep', sleep)
    if fault == 'delayed' or (fault == 'update' and not refresh):
        wait(trust, refresh=refresh)
        assert state['reads'] == 2
    else:
        with pytest.raises((TimeoutError, ValueError, subprocess.SubprocessError)):
            wait(trust, refresh=refresh)
    assert state['updates'] == int(refresh)
    if fault == 'update' and refresh:
        assert state['reads'] == 0


@pytest.mark.parametrize('persistent', [False, True])
def test_child_trust_initialization_contention_retries_within_original_deadline(
        tmp_path, monkeypatch, persistent):
    wait = _activation['wait_child_trust']
    namespace = wait.__globals__
    record = [f'/{_activation["EXTENSION_PATH"]}/indicatorLogic.mjs', '12', 'a' * 64]
    manifest = tmp_path / 'child.trust'
    manifest.write_text(' '.join(record) + '\n')
    state = dict(now=0, attempts=0)

    def run(argv, **kwargs):
        assert kwargs['check'] and kwargs['timeout'] == 120 - state['now']
        assert argv[-1] == 'read-child-trust'
        state['attempts'] += 1
        if persistent or state['attempts'] == 1:
            raise subprocess.CalledProcessError(75, argv, stderr='private details')
        return SimpleNamespace(stdout=json.dumps([record]))

    def sleep(delay):
        assert 0 < delay <= .25
        state['now'] += 40

    monkeypatch.setattr(namespace['subprocess'], 'run', run)
    monkeypatch.setattr(namespace['time'], 'monotonic', lambda: state['now'])
    monkeypatch.setattr(namespace['time'], 'sleep', sleep)
    if persistent:
        with pytest.raises(_activation['ChildTrustDeadline']):
            wait(manifest)
        assert state['now'] == 120 and state['attempts'] == 3
    else:
        wait(manifest)
        assert state['now'] == 40 and state['attempts'] == 2


def test_snapshot_cli_reports_only_retryable_initialization_status(monkeypatch, capsys):
    main = _activation['main']
    namespace = main.__globals__
    monkeypatch.setitem(namespace, 'child_trust_manifest', lambda: set())
    monkeypatch.setitem(namespace, 'read_child_trust', Mock(
        side_effect=_activation['ChildTrustBusy']('private database details')))
    monkeypatch.setattr('sys.argv', ['package-activation', 'read-child-trust'])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 75
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('fault', ['none', 'digest', 'size', 'source', 'path', 'missing'])
@pytest.mark.parametrize('published', [False, True])
def test_real_child_trust_snapshot_matches_exact_file_backend_records(tmp_path, fault, published):
    from tests.support.trust_database import live_database, replace_records
    path = '/' + str(_activation['EXTENSION_PATH']) + '/indicatorLogic.mjs'
    record = (path, '12', 'a' * 64)
    row = [path, '2', '12', 'a' * 64]
    if fault in ('digest', 'size', 'source', 'path'):
        index, value = {'digest': (3, 'b' * 64), 'size': (2, '13'),
                        'source': (1, '1'), 'path': (0, path + '.other')}[fault]
        row[index] = value
    database = tmp_path / 'database'
    # A duplicate with another trust source must neither satisfy nor hide the
    # exact file record. Unrelated keys never escape the reader.
    rows = [[path, '3', '12', 'a' * 64], ['/private/unrelated', '2', '1', 'c' * 64]]
    if fault != 'missing':
        rows.append(row)
    if published:
        # The legacy DB can contain an exact but retired record. Only the
        # metadata-selected generation may establish current trust.
        replace_records(database, [[path, '2', '12', 'a' * 64]])
    replace_records(database, rows, database_name='trust.slot_0' if published else 'trust.db',
                    metadata=b'generation=1\nname=trust.slot_0\nentries=3\npublish_time=1\n'
                    if published else None)
    with live_database(database):
        result = _activation['read_child_trust']({record}, database)
    assert result == ({record} if fault == 'none' else set())


@pytest.mark.parametrize('mixed_generation', [False, True])
@pytest.mark.parametrize('published', [False, True])
def test_snapshot_survives_overlapping_queued_refreshes(tmp_path, monkeypatch, mixed_generation, published):
    from tests.support.trust_database import live_database, replace_records
    read = _activation['read_child_trust']
    namespace = read.__globals__
    database = tmp_path / 'database'
    paths = [f'/{_activation["EXTENSION_PATH"]}/{name}.mjs' for name in ('a', 'b')]
    before = [(path, '2', '12', 'a' * 64) for path in paths]
    after = [(path, '2', '12', 'b' * 64) for path in paths]
    replace_records(database, before,
                    database_name='trust.slot_0' if published else 'trust.db',
                    metadata=b'generation=1\nname=trust.slot_0\n' if published else None)
    expected = {(paths[0], '12', 'a' * 64),
                (paths[1], '12', ('b' if mixed_generation else 'a') * 64)}
    lib = _activation['child_trust_lmdb']()
    cursor_get = lib.mdb_cursor_get
    metadata_get = lib.mdb_get
    mutations = []

    def publish_refresh():
        if not mutations:
            mutations.append(True)
            # The production transaction is already open. Complete two queued
            # refreshes, then force page reuse repeatedly while that read lives.
            subprocess.run([sys.executable, '-c',
                            'import json,sys; from tests.support.trust_database import replace_records; '
                            'replace_records(sys.argv[1], json.loads(sys.argv[2]), repeats=64, '
                            'database_name=sys.argv[3], '
                            'metadata=sys.argv[4].encode() if sys.argv[4] else None)',
                            str(database), json.dumps(after),
                            'trust.slot_1' if published else 'trust.db',
                            'generation=2\nname=trust.slot_1\n' if published else ''], check=True, timeout=15,
                           cwd=Path(__file__).resolve().parents[2], capture_output=True)

    def overlap(*args):
        publish_refresh()
        return cursor_get(*args)

    def publication_overlap(*args):
        result = metadata_get(*args)
        # Publish after the old name was read but before its DB is opened.
        # Metadata and records must still belong to the same read snapshot.
        publish_refresh()
        return result

    if published:
        lib.mdb_get = publication_overlap
    else:
        lib.mdb_cursor_get = overlap
    monkeypatch.setitem(namespace, 'child_trust_lmdb', lambda: lib)
    with live_database(database):
        result = read(expected, database)
        assert mutations
        assert result == ({(paths[0], '12', 'a' * 64)} if mixed_generation else expected)
        # The next poll gets a new snapshot, never a union of multiple generations.
        assert read(expected, database) == ({(paths[1], '12', 'b' * 64)} if mixed_generation else set())


@pytest.mark.parametrize('metadata', [
    b'name=trust.slot_0\n', b'generation=1\n',
    b'generation=bad\nname=trust.slot_0\n',
    b'generation=1\nname=trust.slot_0\nname=trust.db\n',
    b'generation=1\ngeneration=2\nname=trust.slot_0\n',
    b'generation=1\nname=trust.meta\n', b'generation=1\nname=trust.slot_32\n',
    b'generation=1\nname=trust.slot_0\0\n', b'x' * 4096,
    b'generation=1\nname=trust.slot_1\n',  # published DB absent
])
def test_snapshot_refuses_invalid_publication_without_legacy_fallback(tmp_path, metadata):
    from tests.support.trust_database import live_database, replace_records
    record = ('/packaged.mjs', '12', 'a' * 64)
    database = tmp_path / 'database'
    replace_records(database, [[record[0], '2', *record[1:]]])
    replace_records(database, [], database_name='trust.slot_0', metadata=metadata)
    with live_database(database):
        with pytest.raises(ValueError, match='child trust publication'):
            _activation['read_child_trust']({record}, database)


@pytest.mark.parametrize('error', [FileNotFoundError, PermissionError])
def test_snapshot_refuses_unavailable_lock_without_unlocked_fallback(tmp_path, monkeypatch, error):
    read = _activation['read_child_trust']
    library = Mock()
    monkeypatch.setitem(read.__globals__, 'child_trust_lmdb', library)
    monkeypatch.setattr(read.__globals__['os'], 'open', Mock(side_effect=error))
    with pytest.raises(error):
        read(set(), tmp_path)
    library.assert_not_called()


@pytest.mark.parametrize('fault', ['none', 'library', 'open', 'transaction', 'close'])
def test_snapshot_guard_covers_open_through_close_and_releases_on_failure(
        tmp_path, monkeypatch, fault):
    read = _activation['read_child_trust']
    lock = tmp_path / 'lock.mdb'
    lock.touch()
    boundaries = []

    def guarded(boundary):
        boundaries.append(boundary)
        # POSIX exclusive locks conflict with OFD locks even in this process.
        # Closing this extra descriptor must not release the reader's guard.
        with lock.open('r+b') as stream:
            with pytest.raises(BlockingIOError):
                fcntl.lockf(stream, fcntl.LOCK_EX | fcntl.LOCK_NB, 1)
        if fault == boundary:
            raise ValueError('injected failure')
        return 0

    def create(out):
        ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 1
        return 0

    library = SimpleNamespace(
        mdb_env_create=create, mdb_env_set_maxdbs=lambda *args: 0,
        mdb_env_open=lambda *args: guarded('open'),
        mdb_txn_begin=lambda *args: guarded('transaction'),
        mdb_dbi_open=lambda *args: -30798,
        mdb_env_close=lambda *args: guarded('close'))

    def bind():
        guarded('library')
        return library

    monkeypatch.setitem(read.__globals__, 'child_trust_lmdb', bind)
    if fault == 'none':
        assert read(set(), tmp_path) == set()
    else:
        with pytest.raises(ValueError, match='injected failure'):
            read(set(), tmp_path)
    assert boundaries[0] == 'library'
    assert boundaries[-1] == ('library' if fault == 'library' else 'close')
    with lock.open('r+b') as stream:
        fcntl.lockf(stream, fcntl.LOCK_EX | fcntl.LOCK_NB, 1)


def test_snapshot_refuses_exclusive_initialization_lock(tmp_path, monkeypatch):
    lock = tmp_path / 'lock.mdb'
    lock.touch()
    read = _activation['read_child_trust']
    library = Mock()
    monkeypatch.setitem(read.__globals__, 'child_trust_lmdb', library)
    with lock.open('r+b') as stream:
        fcntl.lockf(stream, fcntl.LOCK_EX | fcntl.LOCK_NB, 1)
        with pytest.raises(_activation['ChildTrustBusy']):
            read(set(), tmp_path)
    library.assert_not_called()


def test_snapshot_guard_permission_denial_is_fatal_not_retryable(tmp_path, monkeypatch):
    import errno
    read = _activation['read_child_trust']
    (tmp_path / 'lock.mdb').touch()
    library = Mock()
    monkeypatch.setitem(read.__globals__, 'child_trust_lmdb', library)
    monkeypatch.setattr(read.__globals__['fcntl'], 'fcntl', Mock(
        side_effect=PermissionError(errno.EACCES, 'private details')))
    with pytest.raises(PermissionError):
        read(set(), tmp_path)
    library.assert_not_called()


def test_live_writer_survives_reader_after_unrelated_lock_descriptor_close(tmp_path):
    from tests.support.trust_database import replace_records
    database = tmp_path / 'database'
    record = ('/packaged.mjs', '12', 'a' * 64)
    refreshes = []

    def after_refresh():
        refreshes.append(True)
        # Model fanotify closing an event descriptor in fapolicyd: POSIX locks
        # on this inode vanish although the writer's LMDB environment is live.
        with (database / 'lock.mdb').open('rb'):
            pass
        subprocess.run([sys.executable, '-c',
                        'import json,runpy,sys; from pathlib import Path; '
                        'helper=runpy.run_path(sys.argv[1]); '
                        'record=tuple(json.loads(sys.argv[3])); '
                        'assert helper["read_child_trust"]({record}, Path(sys.argv[2])) == {record}',
                        str(Path(_activation['__file__'])), str(database), json.dumps(record)],
                       check=True, timeout=15, capture_output=True)

    # The second refresh must still acquire the shared writer mutex. LMDB
    # 0.9.31 returns EINVAL here if the first reader destroyed that mutex.
    replace_records(database, [[record[0], '2', *record[1:]]], repeats=2,
                    after_refresh=after_refresh)
    assert len(refreshes) == 2


def test_wait_child_trust_refresh_cli_routes_to_helper(monkeypatch):
    main = _activation['main']
    wait = Mock()
    monkeypatch.setitem(main.__globals__, 'wait_child_trust', wait)
    monkeypatch.setattr('sys.argv', ['package-activation', 'wait-child-trust', '--refresh'])
    main()
    wait.assert_called_once_with(refresh=True)


@pytest.mark.parametrize('fedora', [False, True])
def test_trust_reader_loads_supported_distribution_soname(monkeypatch, fedora):
    bind = _activation['child_trust_lmdb']
    library = Mock()
    load = Mock(side_effect=[OSError('absent'), library] if fedora else [library])
    monkeypatch.setattr(bind.__globals__['ctypes'], 'CDLL', load)
    assert bind() is library
    assert [call.args[0] for call in load.call_args_list] == (
        ['liblmdb.so.0', 'liblmdb.so.0.0.0'] if fedora else ['liblmdb.so.0'])


def test_snapshot_cli_returns_only_matched_manifest_records(monkeypatch, capsys):
    main = _activation['main']
    expected = {('/packaged.mjs', '12', 'a' * 64)}
    reader = Mock(return_value=expected)
    monkeypatch.setitem(main.__globals__, 'child_trust_manifest', lambda: expected)
    monkeypatch.setitem(main.__globals__, 'read_child_trust', reader)
    monkeypatch.setattr('sys.argv', ['package-activation', 'read-child-trust'])
    main()
    reader.assert_called_once_with(expected)
    assert json.loads(capsys.readouterr().out) == [list(next(iter(expected)))]


def test_both_packages_require_the_snapshot_runtime_library():
    root = Path(__file__).resolve().parents[2]
    depends = next(line for line in (root / 'debian/control').read_text().splitlines()
                   if line.startswith('Depends:'))
    assert 'liblmdb0' in {item.strip() for item in depends.split(',')}
    assert 'Requires:       lmdb-libs' in (root / 'rpm/oh-no-parent-control.spec.in').read_text()


@pytest.mark.parametrize('backend', ['debdb', 'rpmdb,file', 'debdb,file'])
def test_child_file_backend_is_enabled_reversibly_only_when_missing(tmp_path, backend):
    prepare = _activation['prepare_child_trust_backend']
    config = tmp_path / 'fapolicyd.conf'
    record = tmp_path / 'record'
    original = f'# distribution configuration\ntrust = {backend}\nintegrity = none\n'.encode()
    config.write_bytes(original)
    for attempt in range(2):
        action = prepare(config, record)
        assert action == ('changed' if backend == 'debdb' and attempt == 0 else 'none')
        _activation['complete_child_trust_backend'](record)
    if backend == 'debdb':
        assert (record / 'before').read_bytes() == original
        assert config.read_bytes() == (record / 'after').read_bytes()
        assert config.read_bytes() == original.replace(b'debdb', b'debdb,file')
        # Retry after snapshotting but before applying the configuration.
        config.write_bytes(original)
        assert prepare(config, record) == 'changed'
        config.write_bytes(b'trust = debdb,file\nintegrity = sha256\n')
        with pytest.raises(ValueError, match='modified'):
            prepare(config, record)
        assert b'integrity = sha256' in config.read_bytes()
    else:
        assert config.read_bytes() == original
        assert not record.exists()


@pytest.mark.parametrize('legacy', [False, True])
def test_backend_activation_survives_same_boot_retry_and_recovers_legacy_failure(tmp_path, legacy):
    prepare = _activation['prepare_child_trust_backend']
    config, record = tmp_path / 'config', tmp_path / 'record'
    original = b'trust = debdb\n'
    config.write_bytes(original)
    old_boot = '11111111-1111-1111-1111-111111111111'
    new_boot = '22222222-2222-2222-2222-222222222222'
    if legacy:
        record.mkdir()
        (record / 'before').write_bytes(original)
        (record / 'after').write_bytes(original.replace(b'debdb', b'debdb,file'))
        config.write_bytes((record / 'after').read_bytes())
    assert prepare(config, record, old_boot) == 'changed'
    assert prepare(config, record, old_boot) == 'changed'
    assert (record / 'activation').read_text().strip() == old_boot
    assert prepare(config, record, new_boot) == 'none'
    _activation['complete_child_trust_backend'](record)
    assert prepare(config, record, old_boot) == 'none'
    # Restoring the original configuration requires activation again.
    config.write_bytes(original)
    assert prepare(config, record, new_boot) == 'changed'


@pytest.mark.parametrize('fault', ['symlink', 'invalid'])
def test_backend_activation_refuses_substituted_receipt(tmp_path, fault):
    prepare = _activation['prepare_child_trust_backend']
    config, record = tmp_path / 'config', tmp_path / 'record'
    config.write_text('trust = debdb\n')
    prepare(config, record)
    receipt = record / 'activation'
    if fault == 'symlink':
        receipt.unlink()
        receipt.symlink_to(config)
    else:
        receipt.write_text('invalid\n')
    with pytest.raises(ValueError):
        prepare(config, record)
    assert config.read_text() == 'trust = debdb,file\n'


@pytest.mark.parametrize('failed_flush', range(1, 9))
def test_backend_durability_failure_preserves_rollback_and_allows_retry(
        tmp_path, monkeypatch, failed_flush):
    prepare = _activation['prepare_child_trust_backend']
    config, record = tmp_path / 'config', tmp_path / 'record'
    original, replacement = b'trust = debdb\n', b'trust = debdb,file\n'
    config.write_bytes(original)
    boot = '11111111-1111-1111-1111-111111111111'
    real_fsync = os.fsync
    calls = 0

    def fail_flush(descriptor):
        nonlocal calls
        calls += 1
        if calls == failed_flush:
            raise OSError('injected persistence failure')
        real_fsync(descriptor)

    with monkeypatch.context() as patch:
        patch.setattr(prepare.__globals__['os'], 'fsync', fail_flush)
        with pytest.raises(OSError, match='persistence failure'):
            prepare(config, record, boot)
    # The final directory flush follows replacement; every earlier failure
    # must leave the original configuration intact. Rollback is already durable
    # when replacement happens, and retry completes either interrupted state.
    assert config.read_bytes() == (replacement if failed_flush == 8 else original)
    if config.read_bytes() == replacement:
        assert (record / 'before').read_bytes() == original
        assert (record / 'after').read_bytes() == replacement
        assert (record / 'activation').read_text().strip() == boot
    assert prepare(config, record, boot) == 'changed'
    assert config.read_bytes() == replacement
    assert (record / 'before').read_bytes() == original
    assert (record / 'activation').read_text().strip() == boot


@pytest.mark.parametrize('fault', ['symlink', 'record-link', 'source', 'duplicate', 'inactive-trust'])
def test_child_file_backend_refuses_unsafe_or_unowned_changes(tmp_path, fault):
    prepare = _activation['prepare_child_trust_backend']
    config = tmp_path / 'fapolicyd.conf'
    record = tmp_path / 'record'
    config.write_bytes(b'trust = debdb\n')
    if fault == 'symlink':
        config.rename(tmp_path / 'original')
        config.symlink_to(tmp_path / 'original')
    elif fault == 'record-link':
        record.symlink_to(tmp_path / 'missing')
    elif fault == 'source':
        config.write_bytes(b'trust = administrator\n')
    elif fault == 'duplicate':
        config.write_bytes(b'trust = debdb\ntrust = file\n')
    else:
        (tmp_path / 'fapolicyd.trust').write_bytes(b'/administrator/file 12 ' + b'a' * 64)
    original = config.read_bytes()
    with pytest.raises(ValueError):
        prepare(config, record)
    assert config.read_bytes() == original


@pytest.mark.parametrize('contents', ['', '# no records\n', '/unexpected/module.mjs 1 ' + 'a' * 64])
def test_child_trust_wait_refuses_missing_or_unscoped_manifest(tmp_path, monkeypatch, contents):
    wait = _activation['wait_child_trust']
    path = tmp_path / 'manifest'
    path.write_text(contents)
    run = Mock()
    monkeypatch.setattr(wait.__globals__['subprocess'], 'run', run)
    with pytest.raises(ValueError):
        wait(path)
    run.assert_not_called()


@pytest.mark.parametrize('error,expected', [
    (ValueError('private manifest text'), 'manifest-or-read'),
    (OSError('private path'), 'manifest-or-read'),
    (subprocess.CalledProcessError(7, ['private'], stderr='private database'), 'cli-exit status=7'),
    (subprocess.TimeoutExpired(['private'], 30), 'cli-timeout'),
    (UnicodeDecodeError('utf8', b'\xff', 0, 1, 'private'), 'output-decoding'),
    (_activation['ChildTrustDeadline']({('/owned/indicatorLogic.mjs', '12', 'a' * 64)}),
     'deadline modules=indicatorLogic.mjs'),
])
def test_child_trust_failure_diagnostics_are_bounded(error, expected):
    assert _activation['child_trust_failure'](error) == expected


def test_child_trust_contains_only_packaged_modules_and_refreshes_final_hashes(tmp_path):
    import hashlib
    extension = tmp_path / _activation['EXTENSION_PATH']
    extension.mkdir(parents=True)
    modules = {'indicatorLogic.mjs': b'export const indicator = 1;\n',
               'diagnosticEvents.mjs': b'export const diagnostic = 2;\n'}
    for name, contents in modules.items():
        (extension / name).write_bytes(contents)
    (extension / 'extension.js').write_text('import module;')
    (extension / 'metadata.json').write_text('{}')
    output = tmp_path / 'manifest.json'
    trust = tmp_path / _activation['EXTENSION_TRUST_PATH']
    for replacement in (b'export const indicator = 1;\n', b'export const indicator = 3;\n'):
        modules['indicatorLogic.mjs'] = replacement
        (extension / 'indicatorLogic.mjs').write_bytes(replacement)
        generate(tmp_path, output)
        lines = [line for line in trust.read_text().splitlines() if not line.startswith('#')]
        assert lines == [f'/{_activation["EXTENSION_PATH"]}/{name} {len(contents)} '
                         f'{hashlib.sha256(contents).hexdigest()}'
                         for name, contents in sorted(modules.items())]
        entries = {item['path']: item for item in json.loads(output.read_text())['files']}
        entry = entries[str(_activation['EXTENSION_TRUST_PATH'])]
        assert entry['activation'] == 'none'
        assert entry['sha256'] == hashlib.sha256(trust.read_bytes()).hexdigest()


def test_make_generates_activation_manifest_from_relocated_debian_helper(tmp_path):
    root = Path(__file__).resolve().parents[2]
    broker = tmp_path / 'usr/libexec/oh-no-parent-control-broker'
    broker.parent.mkdir(parents=True)
    broker.write_text('staged broker fixture')
    subprocess.run(['make', '--no-print-directory', '_generate-package-activation-manifest',
                    f'DESTDIR={tmp_path}'], cwd=root, check=True, capture_output=True, text=True)
    manifest = json.loads((tmp_path / 'usr/share/oh-no-parent-control/package-activation.json').read_text())
    assert manifest['files'] == [{
        'path': 'usr/libexec/oh-no-parent-control-broker',
        'sha256': _activation['file_digest'](broker),
        'activation': 'process-restart',
    }]


class PackageActivationTests(unittest.TestCase):
    def _manifest(self, root: Path, name: str) -> Path:
        output = root / name
        generate(root, output)
        return output

    def test_broker_change_restarts_process_without_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broker = root / "usr/lib/oh-no-parent-control/broker/service.py"
            broker.parent.mkdir(parents=True)
            broker.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            broker.write_text("second", encoding="utf-8")
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["process-restart"])

    def test_app_termination_adapter_activates_with_broker_restart(self):
        self.assertEqual(
            activation_for(
                "usr/lib/oh-no-parent-control/broker/"
                "oh_no_parent_control/app_termination.py"
            ),
            "process-restart",
        )

    def test_shared_app_policy_matching_activates_with_broker_restart(self):
        self.assertEqual(activation_for(
            'usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/app_policy.py'),
            'process-restart')

    def test_broker_service_change_activates_with_broker_restart(self):
        self.assertEqual(
            activation_for(
                "usr/lib/systemd/system/oh-no-parent-control-broker.service"
            ),
            "process-restart",
        )

    def test_native_probe_payload_changes_restart_broker_without_reboot(self):
        for kind in ("gate", "witness"):
            path = f"usr/libexec/oh-no-parent-control-execution-probe-{kind}"
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                before = self._manifest(root, "old.json")
                payload = root / path
                payload.parent.mkdir(parents=True)
                payload.write_bytes(b"first")
                added = self._manifest(root, "added.json")
                self.assertEqual(changed_impacts(before, added), ["process-restart"])
                payload.write_bytes(b"second")
                changed = self._manifest(root, "changed.json")
                self.assertEqual(changed_impacts(added, changed), ["process-restart"])
                payload.unlink()
                removed = self._manifest(root, "removed.json")
                self.assertEqual(changed_impacts(changed, removed), ["process-restart"])

    def test_migration_runner_activates_during_postinst(self):
        self.assertEqual(
            activation_for("usr/libexec/oh-no-parent-control-migrate-state"),
            "none",
        )

    def test_probe_queue_timeout_add_change_remove_uses_boot_boundary(self):
        path = ("usr/lib/systemd/system/onpc-execution-probe-.service.d/"
                "oh-no-parent-control-timeout.conf")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = self._manifest(root, "old.json")
            payload = root / path
            payload.parent.mkdir(parents=True)
            payload.write_text("[Unit]\nJobTimeoutSec=4s\n")
            added = self._manifest(root, "added.json")
            self.assertEqual(changed_impacts(before, added), ["reboot"])
            payload.write_text("[Unit]\nJobTimeoutSec=3s\n")
            changed = self._manifest(root, "changed.json")
            self.assertEqual(changed_impacts(added, changed), ["reboot"])
            payload.unlink()
            removed = self._manifest(root, "removed.json")
            self.assertEqual(changed_impacts(changed, removed), ["reboot"])

    def test_uninstall_only_code_needs_no_installed_update_activation(self):
        for path in (
            "usr/libexec/oh-no-parent-control-uninstall",
            "etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice",
            "usr/lib/oh-no-parent-control/broker/oh_no_parent_control/uninstall.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(activation_for(path), "none")

    def test_package_completion_notice_activates_on_invocation(self):
        for path in (
            "usr/libexec/oh-no-parent-control-package-notice",
            "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice",
        ):
            with self.subTest(path=path):
                self.assertEqual(activation_for(path), "none")

    def test_execution_rule_change_reloads_with_broker_restart(self):
        self.assertEqual(activation_for("usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules"), "process-restart")
        self.assertEqual(
            activation_for(
                "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules"
            ),
            "process-restart",
        )

    def test_polkit_action_change_is_loaded_without_restart(self):
        self.assertEqual(
            activation_for(
                "usr/share/polkit-1/actions/"
                "tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy"
            ),
            "none",
        )

    def test_desktop_icon_change_activates_at_the_next_session(self):
        self.assertEqual(
            activation_for(
                "usr/share/icons/hicolor/512x512/apps/"
                "com.puffyslippers.OhNoParentControl.png"
            ),
            "session-renewal",
        )

    def test_child_overlay_desktop_identity_uses_the_product_icon_without_restart(self):
        root = Path(__file__).resolve().parents[2]
        desktop_id = "com.puffyslippers.OhNoParentControl.ChildRequest"
        installed_path = f"usr/share/applications/{desktop_id}.desktop"
        entry = configparser.ConfigParser(interpolation=None)
        entry.read(root / "data/applications" / f"{desktop_id}.desktop")
        desktop = entry["Desktop Entry"]
        self.assertEqual(desktop["Exec"], "/usr/bin/oh-no-parent-control-child")
        self.assertEqual(desktop["Icon"], "com.puffyslippers.OhNoParentControl")
        self.assertTrue(desktop.getboolean("NoDisplay"))
        self.assertFalse(desktop.getboolean("DBusActivatable"))
        self.assertEqual(activation_for(installed_path), "none")

    def test_account_logo_is_reapplied_by_provisioning(self):
        self.assertEqual(
            activation_for(
                "usr/share/oh-no-parent-control/kiosk_account_icon.png"
            ),
            "none",
        )

    def test_parent_titlebar_logo_needs_no_session_restart(self):
        self.assertEqual(
            activation_for(
                "usr/share/oh-no-parent-control/app_logo_titlebar.png"
            ),
            "none",
        )

    def test_session_payload_change_does_not_signal_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extension = (
                root / "usr/share/gnome-shell/extensions/"
                "oh-no-parent-control@tech.puffyslippers.com/extension.js"
            )
            extension.parent.mkdir(parents=True)
            extension.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            extension.write_text("second", encoding="utf-8")
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["session-renewal"])

    def test_pam_limit_helper_activates_on_invocation(self):
        self.assertEqual(
            activation_for(
                "usr/libexec/oh-no-parent-control-session-limit-check"
            ),
            "none",
        )

    def test_kiosk_login_integration_requires_reboot(self):
        self.assertEqual(
            activation_for("usr/libexec/oh-no-parent-control-login-check"),
            "reboot",
        )

    def test_pam_runtime_cap_module_activates_at_next_session(self):
        self.assertEqual(
            activation_for(
                "usr/lib/x86_64-linux-gnu/security/pam_oh_no_parent_control.so"
            ),
            "session-renewal",
        )

    def test_login_stack_change_requires_reboot(self):
        self.assertEqual(activation_for("usr/share/oh-no-parent-control/gdm-presession"), "reboot")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pam = root / "usr/share/pam-configs/oh-no-parent-control-session-limits"
            pam.parent.mkdir(parents=True)
            pam.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            pam.write_text("second", encoding="utf-8")
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["reboot"])

    def test_execution_readiness_boot_order_requires_reboot(self):
        self.assertEqual(
            activation_for(
                "usr/lib/systemd/system/display-manager.service.d/"
                "oh-no-parent-control.conf"
            ),
            "reboot",
        )

    def test_execution_readiness_helper_activates_on_invocation(self):
        self.assertEqual(
            activation_for(
                "usr/libexec/oh-no-parent-control-execution-policy-ready"
            ),
            "none",
        )

    def test_fedora_readiness_unit_add_change_remove_requires_reboot(self):
        self.assertEqual(activation_for(
            'usr/share/oh-no-parent-control/00-oh-no-parent-control-canary.rules'), 'reboot')
        path = 'usr/lib/systemd/system/oh-no-parent-control-execution-policy-ready.service'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = self._manifest(root, 'old.json')
            unit = root / path
            unit.parent.mkdir(parents=True)
            unit.write_text('[Service]\nType=oneshot\n')
            added = self._manifest(root, 'added.json')
            self.assertEqual(changed_impacts(before, added), ['reboot'])
            unit.write_text('[Service]\nType=oneshot\nTimeoutStartSec=90s\n')
            changed = self._manifest(root, 'changed.json')
            self.assertEqual(changed_impacts(added, changed), ['reboot'])
            unit.unlink()
            removed = self._manifest(root, 'removed.json')
            self.assertEqual(changed_impacts(changed, removed), ['reboot'])

    def test_execution_canary_contract_requires_reboot(self):
        self.assertEqual(
            activation_for("usr/libexec/oh-no-parent-control-execution-policy-probe"),
            "reboot",
        )

    def test_removed_file_keeps_its_old_activation_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gdm = root / "etc/gdm3/PreSession/Default"
            gdm.parent.mkdir(parents=True)
            gdm.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            gdm.unlink()
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["reboot"])

    def test_no_baseline_is_a_first_installation_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "usr/share/oh-no-parent-control").mkdir(parents=True)
            new = self._manifest(root, "usr/share/oh-no-parent-control/current.json")

            self.assertEqual(changed_impacts(root / "missing.json", new), ["reboot"])

    def test_generated_manifest_contains_hashes_and_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "usr/bin/oh-no-parent-control"
            target.parent.mkdir(parents=True)
            target.write_text("launcher", encoding="utf-8")
            manifest = self._manifest(root, "manifest.json")

            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["files"][0]["activation"], "none")
            self.assertEqual(len(data["files"][0]["sha256"]), 64)

    def test_includes_limit_generation_to_activation_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracked = root / "usr/lib/oh-no-parent-control/broker/service.py"
            ignored = root / "usr/bin/oh-no-parent-control"
            tracked.parent.mkdir(parents=True)
            ignored.parent.mkdir(parents=True)
            tracked.write_text("broker", encoding="utf-8")
            ignored.write_text("launcher", encoding="utf-8")

            manifest = root / "manifest.json"
            generate(root, manifest, [Path("usr/lib/oh-no-parent-control/broker")])

            paths = [entry["path"] for entry in json.loads(manifest.read_text())["files"]]
            self.assertEqual(paths, ["usr/lib/oh-no-parent-control/broker/service.py"])


if __name__ == "__main__":
    unittest.main()
