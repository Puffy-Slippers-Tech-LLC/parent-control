"""No native launch before guest/credential checks; reuse owned command cleanup."""

from unittest.mock import Mock
from types import SimpleNamespace
import os
import threading

import pytest

import system_enforcement as enforcement
from tests.support.installed_catalog import installed_catalog_tree


@pytest.mark.parametrize('interrupted', [False, True])
def test_sender_loss_fault_retains_late_close_for_owned_retry(interrupted):
    client = SimpleNamespace(_context=Mock(), _pending=None, _connection=Mock())
    client._connection.is_closed.return_value = False
    def start():
        client._pending = 'close'
    client._start_close = Mock(side_effect=start)
    client._wait = Mock(side_effect=KeyboardInterrupt if interrupted else None)
    if interrupted:
        with pytest.raises(KeyboardInterrupt):
            enforcement._lose_probe_sender(client)
    else:
        assert not enforcement._lose_probe_sender(client)
    assert client._pending == 'close'
    client._context.pop_thread_default.assert_called_once()
    def finish(deadline):
        client._pending = None
        client._connection.is_closed.return_value = True
    client._wait.side_effect = finish
    assert enforcement._lose_probe_sender(client)
    client._start_close.assert_called_once()
    assert enforcement._lose_probe_sender(client)
    client._start_close.assert_called_once()


@pytest.mark.parametrize('entry', ['native_probe_storage_lifecycle', '_in_broker_mount'])
def test_storage_guest_refusal_precedes_owner_and_namespace_access(monkeypatch, entry):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock(
        side_effect=enforcement.guest.GuestError('guard-refused')))
    opened = Mock()
    monkeypatch.setattr(enforcement.os, 'open', opened)
    with pytest.raises(enforcement.guest.GuestError, match='guard-refused'):
        getattr(enforcement, entry)(Mock())
    opened.assert_not_called()


@pytest.mark.parametrize('field,value', [('MainPID', '0'), ('MainPID', '../12'),
                                       ('InvocationID', 'invalid'), ('ActiveState', 'inactive'),
                                       ('ProtectSystem', 'no'), ('RuntimeDirectoryPreserve', 'no')])
def test_storage_identity_refuses_invalid_or_unprotected_broker(monkeypatch, field, value):
    fields = dict(MainPID='12', InvocationID='a' * 32, ActiveState='active',
                  ProtectSystem='strict', RuntimeDirectoryPreserve='yes')
    fields[field] = value
    monkeypatch.setattr(enforcement.guest, 'run', Mock(
        return_value='\n'.join(f'{key}={item}' for key, item in fields.items())))
    with pytest.raises(enforcement.guest.GuestError, match='broker-storage-identity'):
        enforcement._broker_storage_identity()


@pytest.mark.parametrize('fault', ['none', 'replaced', 'same-mount', 'setns', 'readonly', 'operation'])
def test_storage_namespace_worker_is_joined_and_descriptors_close(monkeypatch, tmp_path, fault):
    namespace = tmp_path / 'namespace'
    namespace.write_bytes(b'namespace')
    opened, threads, operations = [], [], []
    main_thread = threading.get_ident()
    real_open = os.open
    real_stat = os.stat

    def open_descriptor(path, flags):
        fd = real_open(namespace if path.endswith('/ns/mnt') else tmp_path, flags)
        opened.append(fd)
        return fd

    def stat_namespace(path, *args, **kwargs):
        if path == '/proc/thread-self/ns/mnt':
            inode = namespace.stat().st_ino
            return SimpleNamespace(st_ino=inode if fault == 'same-mount' or
                                   threading.get_ident() != main_thread else inode + 1)
        return real_stat(path, *args, **kwargs)

    def enter(*args):
        threads.append(threading.get_ident())
        if fault == 'setns':
            raise PermissionError('namespace-refused')

    def operation():
        operations.append(threading.get_ident())
        if fault == 'operation':
            raise KeyboardInterrupt
        return 'verified'

    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    identities = iter([('12', 'a' * 32),
                       ('13' if fault == 'replaced' else '12', 'a' * 32), ('12', 'a' * 32)])
    monkeypatch.setattr(enforcement, '_broker_storage_identity', lambda: next(identities))
    monkeypatch.setattr(os, 'open', open_descriptor)
    monkeypatch.setattr(os, 'stat', stat_namespace)
    monkeypatch.setattr(os, 'unshare', enter)
    monkeypatch.setattr(os, 'setns', enter)
    monkeypatch.setattr(os, 'fchdir', enter)
    monkeypatch.setattr(os, 'chroot', enter)
    monkeypatch.setattr(os, 'chdir', enter)
    monkeypatch.setattr(os, 'statvfs', lambda path: SimpleNamespace(
        f_flag=0 if fault == 'readonly' else os.ST_RDONLY))
    if fault == 'none':
        assert enforcement._in_broker_mount(operation) == ('verified', ('12', 'a' * 32))
    else:
        error = (KeyboardInterrupt if fault == 'operation' else
                 PermissionError if fault == 'setns' else enforcement.guest.GuestError)
        with pytest.raises(error):
            enforcement._in_broker_mount(operation)
    assert all(identity != main_thread for identity in threads + operations)
    assert not any(thread.name == 'onpc-probe-storage' and thread.is_alive()
                   for thread in threading.enumerate())
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)
    if fault not in {'none', 'operation'}:
        assert not operations


@pytest.mark.parametrize('fault', ['none', 'prepare', 'stop', 'start', 'restart', 'replacement', 'fresh'])
def test_storage_lifecycle_keeps_exact_owner_and_cleans_after_failure(monkeypatch, tmp_path, fault):
    from oh_no_parent_control import probe_generation as generation

    root = tmp_path / 'probes'
    root.mkdir(mode=0o700)
    source = tmp_path / 'witness'
    source.write_bytes(b'native witness fixture')
    source.chmod(0o755)
    monkeypatch.setattr(generation, 'RUNTIME_ROOT', str(root))
    monkeypatch.setattr(generation, 'WITNESS_SOURCE', str(source))
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    incarnation = 1
    seen = []
    records = {}
    current = lambda: ('12', f'{incarnation:032x}')
    monkeypatch.setattr(enforcement, '_broker_storage_identity', current)

    def within(operation):
        seen.append(operation.__self__)
        if fault == 'prepare' or fault == 'fresh' and len(seen) == 4:
            # Real owner exists before partial preparation fails.
            operation()
            raise enforcement.guest.GuestError('prepare-failed')
        return operation(), current()

    def run(argv, **kwargs):
        nonlocal incarnation
        assert argv[0] == 'systemctl' and argv[2] == enforcement.guest.BROKER
        if argv[1] == fault:
            raise enforcement.guest.GuestError('service-failed')
        if argv[1] in {'start', 'restart'}:
            incarnation += 1
        if argv[1] == 'stop' and fault == 'replacement':
            witness = next(root.iterdir()) / 'witness'
            witness.rename(witness.with_name('saved'))
            witness.write_bytes(b'foreign replacement')
        return 'inactive' if argv[1] == 'show' else ''

    monkeypatch.setattr(enforcement, '_in_broker_mount', within)
    monkeypatch.setattr(enforcement.guest, 'run', run)
    if fault == 'none':
        enforcement.native_probe_storage_lifecycle(records.__setitem__)
        assert seen[0] is seen[1] is seen[2] and seen[3] is not seen[0]
        assert records['onpc.probe.storage.restart-preserved']
    else:
        with pytest.raises((enforcement.guest.GuestError, generation.GenerationRefused)):
            enforcement.native_probe_storage_lifecycle(records.__setitem__)
    if fault == 'replacement':
        assert not records['onpc.probe.storage.cleanup-complete']
        directory = next(root.iterdir())
        assert (directory / 'witness').read_bytes() == b'foreign replacement'
        # Reconcile only the test's own replacement; original owner retries.
        (directory / 'witness').unlink()
        (directory / 'saved').rename(directory / 'witness')
        assert seen[0].close(settled=True)
    else:
        assert records['onpc.probe.storage.cleanup-complete']
    assert not list(root.iterdir())


@pytest.mark.parametrize('refuse_admission', [False, True])
@pytest.mark.parametrize('lose_sender', [False, True])
def test_native_probe_guest_refusal_precedes_bus_import_and_files(
        monkeypatch, refuse_admission, lose_sender):
    guard = Mock(side_effect=enforcement.guest.GuestError('guard-refused'))
    diagnostics, backend = Mock(), Mock()
    monkeypatch.setattr(enforcement.guest, 'guard', guard)
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', diagnostics)
    monkeypatch.setattr(enforcement, 'record_execution_backend', backend)
    with pytest.raises(enforcement.guest.GuestError, match='guard-refused'):
        enforcement.native_probe_lifecycle(Mock(), refuse_admission=refuse_admission,
                                           lose_sender=lose_sender)
    diagnostics.assert_not_called()
    backend.assert_not_called()


@pytest.mark.parametrize('boundary', ['guard', 'identity'])
@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'pattern-future', 'pattern-unrelated', 'retention'])
def test_refused_boundary_prevents_exec(monkeypatch, capsys, boundary, variant):
    guard, identity, execute = Mock(), Mock(), Mock()
    (guard if boundary == 'guard' else identity).side_effect = enforcement.guest.GuestError('refused')
    monkeypatch.setattr(enforcement.guest, 'guard', guard)
    monkeypatch.setattr(enforcement, 'drop_identity', identity)
    monkeypatch.setattr(enforcement.os, 'execv', execute)
    with pytest.raises(enforcement.guest.GuestError, match='refused'):
        enforcement.launch_as(1001, variant)
    execute.assert_not_called()
    assert capsys.readouterr().out == ''
    if boundary == 'guard':
        identity.assert_not_called()


@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'pattern-future', 'pattern-unrelated', 'retention'])
def test_success_replaces_same_process_with_one_shot_target(monkeypatch, capsys, variant):
    class Replaced(BaseException):
        pass

    events = []
    monkeypatch.setattr(enforcement.guest, 'guard', lambda: events.append('guard'))
    monkeypatch.setattr(enforcement, 'drop_identity', lambda uid: events.append(('identity', uid)))

    def execute(path, args):
        events.append(('exec', path, args))
        raise Replaced()

    monkeypatch.setattr(enforcement.os, 'execv', execute)
    with pytest.raises(Replaced):
        enforcement.launch_as(1001, variant)
    target, _, _ = enforcement.native_paths(variant)
    assert events == ['guard', ('identity', 1001),
                      ('exec', str(target), [str(target)])]
    assert capsys.readouterr().out.encode() == enforcement.IDENTITY


@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'retention'])
def test_guest_refusal_prevents_fixture_files(monkeypatch, tmp_path, variant):
    monkeypatch.setattr(enforcement, 'TARGET', tmp_path / 'native/fixture')
    monkeypatch.setattr(enforcement, 'DESKTOP', tmp_path / 'fixture.desktop')
    monkeypatch.setattr(enforcement, 'SPACE_TARGET', tmp_path / 'spaces/native fixture')
    monkeypatch.setattr(enforcement, 'SPACE_DESKTOP', tmp_path / 'spaces.desktop')
    monkeypatch.setattr(enforcement, 'PATTERN_TARGET', tmp_path / 'pattern/Versioned-1.AppImage')
    monkeypatch.setattr(enforcement, 'PATTERN_DESKTOP', tmp_path / 'pattern.desktop')
    monkeypatch.setattr(enforcement, 'RETENTION_TARGET', tmp_path / 'retention/fixture')
    monkeypatch.setattr(enforcement, 'RETENTION_DESKTOP', tmp_path / 'retention.desktop')
    monkeypatch.setattr(enforcement.guest, 'guard', Mock(side_effect=enforcement.guest.GuestError('refused')))
    with pytest.raises(enforcement.guest.GuestError, match='refused'):
        enforcement.provision_native(variant)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('variant', ['/usr/bin/true', '../command', '', None, [], 1])
def test_unknown_variant_cannot_select_executable_or_write_fixture(monkeypatch, variant):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    identity, execute, diagnostics = Mock(), Mock(), Mock()
    monkeypatch.setattr(enforcement, 'drop_identity', identity)
    monkeypatch.setattr(enforcement.os, 'execv', execute)
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', diagnostics)
    with pytest.raises(enforcement.guest.GuestError, match='fixture-variant'):
        enforcement.launch_as(1001, variant)
    with pytest.raises(enforcement.guest.GuestError, match='fixture-variant'):
        enforcement.provision_native(variant)
    identity.assert_not_called()
    execute.assert_not_called()
    diagnostics.assert_not_called()


@pytest.mark.parametrize('fault', ['guard', 'existing', 'dangling', 'directory-symlink', 'source-symlink'])
def test_future_creation_refuses_without_overwriting(monkeypatch, tmp_path, fault):
    target = tmp_path / 'pattern/Versioned-1.AppImage'
    target.parent.mkdir()
    target.write_bytes(b'fixture')
    future = target.with_name('Versioned-2.AppImage')
    sentinel = tmp_path / 'sentinel'
    sentinel.write_bytes(b'preserved')
    monkeypatch.setattr(enforcement, 'PATTERN_TARGET', target)
    guard = Mock(side_effect=enforcement.guest.GuestError('refused') if fault == 'guard' else None)
    monkeypatch.setattr(enforcement.guest, 'guard', guard)
    if fault == 'existing':
        future.write_bytes(b'preserved')
    elif fault == 'dangling':
        future.symlink_to(tmp_path / 'missing')
    elif fault == 'directory-symlink':
        alias = tmp_path / 'alias'
        alias.symlink_to(target.parent, target_is_directory=True)
        monkeypatch.setattr(enforcement, 'PATTERN_TARGET', alias / target.name)
    elif fault == 'source-symlink':
        target.unlink()
        target.symlink_to(sentinel)
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*'))
    with pytest.raises(enforcement.guest.GuestError):
        enforcement.provision_future()
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*')) == before
    assert sentinel.read_bytes() == b'preserved'
    if fault == 'existing':
        assert future.read_bytes() == b'preserved'


@pytest.mark.parametrize('variant', ['pattern-future', 'pattern-unrelated'])
def test_companion_launch_variant_cannot_provision_its_shared_directory(monkeypatch, variant):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    diagnostics = Mock()
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', diagnostics)
    with pytest.raises(enforcement.guest.GuestError, match='fixture-variant'):
        enforcement.provision_native(variant)
    diagnostics.assert_not_called()


@pytest.mark.parametrize('fault', ['guard', 'replacement', 'symlink', 'hardlink',
                                 'edited', 'directory', 'parent-symlink', 'missing'])
def test_launcher_removal_preserves_unexpected_files(monkeypatch, tmp_path, fault):
    desktop = tmp_path / 'fixture.desktop'
    desktop.write_text('owned launcher')
    identity = desktop.lstat()
    sentinel = tmp_path / 'sentinel'
    sentinel.write_text('preserved')
    monkeypatch.setattr(enforcement, 'RETENTION_DESKTOP', desktop)
    monkeypatch.setattr(enforcement.guest, 'guard', Mock(
        side_effect=enforcement.guest.GuestError('refused') if fault == 'guard' else None))
    if fault == 'replacement':
        desktop.rename(tmp_path / 'original')
        desktop.write_text('replacement')
    elif fault in ('symlink', 'directory', 'missing'):
        desktop.unlink()
        if fault == 'symlink':
            desktop.symlink_to(sentinel)
        elif fault == 'directory':
            desktop.mkdir()
    elif fault == 'hardlink':
        (tmp_path / 'alias').hardlink_to(desktop)
    elif fault == 'edited':
        desktop.write_text('changed launcher')
    elif fault == 'parent-symlink':
        alias = tmp_path / 'alias'
        alias.symlink_to(tmp_path, target_is_directory=True)
        monkeypatch.setattr(enforcement, 'RETENTION_DESKTOP', alias / desktop.name)
    before = sorted(path.name for path in tmp_path.iterdir())
    with pytest.raises((enforcement.guest.GuestError, FileNotFoundError)):
        enforcement.remove_retention_launcher(identity)
    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert sentinel.read_text() == 'preserved'
    if fault in ('guard', 'replacement', 'hardlink', 'edited', 'parent-symlink'):
        assert desktop.read_text() == {
            'replacement': 'replacement', 'edited': 'changed launcher',
        }.get(fault, 'owned launcher')


def test_catalog_guest_refusal_precedes_account_or_file_access(monkeypatch):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock(side_effect=enforcement.guest.GuestError('refused')))
    lookup = Mock()
    monkeypatch.setattr(enforcement.pwd, 'getpwuid', lookup)
    with pytest.raises(enforcement.guest.GuestError, match='refused'):
        enforcement.provision_catalog({'child': 1001})
    lookup.assert_not_called()


@pytest.mark.parametrize('fault', ['launcher', 'dangling-launcher', 'ancestor-symlink',
                                 'ancestor-file', 'target-directory', 'binary',
                                 'dangling-binary', 'binary-ancestor-symlink',
                                 'binary-ancestor-file', 'system-binary',
                                 'dangling-system-binary', 'system-ancestor-symlink',
                                 'system-ancestor-file', 'fallback-shadow'])
def test_catalog_collision_preserves_existing_files(installed_catalog_tree, tmp_path, fault):
    tree = installed_catalog_tree
    home = tmp_path / 'child'
    preserved = tmp_path / 'preserved'
    preserved.mkdir()
    sentinel = preserved / 'sentinel'
    sentinel.write_text('unchanged')
    if fault in ('launcher', 'dangling-launcher'):
        directory = home / '.local/share/applications'
        directory.mkdir(parents=True)
        path = directory / (enforcement.CATALOG_PREFIX + 'ChildOnly.desktop')
        if fault == 'launcher':
            path.write_text('existing launcher')
        else:
            path.symlink_to(preserved / 'missing')
    elif fault == 'ancestor-symlink':
        (home / '.local').symlink_to(preserved, target_is_directory=True)
    elif fault == 'ancestor-file':
        (home / '.local').write_text('existing file')
    elif fault in ('binary', 'dangling-binary'):
        # Use a later planned command to prove complete preflight, including
        # account binaries, occurs before earlier launchers/targets are written.
        directory = tmp_path / 'parent/.local/bin'
        directory.mkdir(parents=True)
        path = directory / enforcement.CATALOG_PARENT_COMMAND
        if fault == 'binary':
            path.write_text('existing binary')
        else:
            path.symlink_to(preserved / 'missing')
    elif fault == 'binary-ancestor-symlink':
        (home / 'bin').symlink_to(preserved, target_is_directory=True)
    elif fault == 'binary-ancestor-file':
        (home / 'bin').write_text('existing file')
    elif fault in ('system-binary', 'dangling-system-binary', 'fallback-shadow'):
        directory = tree.local_bin if fault == 'fallback-shadow' else tree.system_bin
        directory.mkdir()
        path = directory / enforcement.CATALOG_FALLBACK_COMMAND
        if fault == 'dangling-system-binary':
            path.symlink_to(preserved / 'missing')
        else:
            path.write_text('existing binary')
    elif fault == 'system-ancestor-symlink':
        tree.system_bin.symlink_to(preserved, target_is_directory=True)
    elif fault == 'system-ancestor-file':
        tree.system_bin.write_text('existing file')
    else:
        (tree.target.parent / 'catalog').symlink_to(preserved, target_is_directory=True)
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*'))
    with pytest.raises(enforcement.guest.GuestError, match='catalog:(fixture-collision|unsafe-directory)'):
        enforcement.provision_catalog(tree.accounts)
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*')) == before
    assert sentinel.read_text() == 'unchanged'
    if fault == 'launcher':
        assert path.read_text() == 'existing launcher'
    if fault in ('binary', 'system-binary', 'fallback-shadow'):
        assert path.read_text() == 'existing binary'
    tree.chown.assert_not_called()
