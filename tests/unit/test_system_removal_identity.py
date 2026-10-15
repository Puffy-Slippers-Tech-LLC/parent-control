"""Private pytest roots; process-local UID and mount doubles, no host mounts."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_removal
import system_removal_identity as identity
import system_removal_ownership as ownership


@pytest.fixture
def machine(tmp_path, monkeypatch):
    home, state = tmp_path / 'home', tmp_path / 'state'
    home.mkdir(mode=0o755)
    state.mkdir(mode=0o755)
    (home / 'retained').write_bytes(b'foreign home contents')
    (state / 'record').write_bytes(b'product record before removal')
    marker = state / 'package-created-kiosk-uid'
    marker.write_bytes(b'12345\n')
    marker.chmod(0o600)
    monkeypatch.setattr(identity, 'HOME', home)
    monkeypatch.setattr(identity, 'STATE_ROOT', state)
    monkeypatch.setattr(identity, 'OWNER_UID', os.getuid())
    monkeypatch.setattr(identity, 'parents', Mock())
    monkeypatch.setattr(identity.guest, 'guard', Mock())
    monkeypatch.setattr(identity.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=os.getuid()))
    monkeypatch.setattr(identity.pwd, 'getpwuid', lambda uid: SimpleNamespace(
        pw_uid=uid, pw_name='foreign-ordinary', pw_dir='/ordinary-home', pw_shell='/bin/sh'))
    monkeypatch.setattr(identity.guest, 'commands', SimpleNamespace(run=Mock(), last_returncode=3))
    owners = {}
    real_metadata = identity.metadata

    def metadata(info):
        value = list(real_metadata(info))
        value[2:4] = owners.get((info.st_dev, info.st_ino), value[2:4])
        return tuple(value)

    def chown(fd, uid, gid):
        info = os.fstat(fd)
        owners[info.st_dev, info.st_ino] = (uid, gid)

    monkeypatch.setattr(identity, 'metadata', metadata)
    monkeypatch.setattr(ownership, 'metadata', metadata)
    monkeypatch.setattr(identity.os, 'fchown', chown)
    mounts = {}
    namespace = ['mnt:[fixture]']
    monkeypatch.setattr(system_removal, 'mount_inventory', lambda: (namespace[0], dict(mounts)))

    def run(command, **kwargs):
        if command[0] == 'mount':
            assert command == ['mount', '--bind', command[-1], command[-1]]
            assert not mounts
            mounts['42'] = (('42', '1', '0:1', '/', command[-1], 'rw'), ('none', 'none'))
        else:
            assert command == ['umount', '--', next(iter(mounts.values()))[0][4]]
            mounts.clear()
        return ''

    monkeypatch.setattr(identity.guest, 'run', Mock(side_effect=run))
    return SimpleNamespace(home=home, state=state, marker=marker, mounts=mounts,
                           namespace=namespace, run=run)


@pytest.mark.parametrize('variant', identity.IDENTITY_FILESYSTEM_VARIANTS)
@pytest.mark.parametrize('fail_body', [False, True])
def test_each_variant_preserves_foreign_witness_and_restores_owned_conflict(machine, variant, fail_body):
    record = Mock()
    original_marker = ownership.witness(machine.marker)
    target = machine.marker if variant == 'kiosk-marker-uid' else (
        machine.home if variant.startswith('home-') else machine.state)
    original = identity.metadata(target.lstat())
    backup = None
    try:
        with identity.identity_filesystem_conflict(variant, 23456, record) as conflict:
            assert conflict.target == target
            assert conflict.preflight == (variant in ('state-owner', 'state-link'))
            conflict.verify()
            if variant == 'kiosk-marker-uid':
                assert conflict.expected_marker_uid == 23456
                assert target.read_bytes() == b'23456\n'
            else:
                assert conflict.expected_marker_uid is None
                assert (conflict.root() / conflict.sentinel.name).read_bytes() == identity.SENTINEL_BYTES
                if variant.endswith('-link'):
                    backup = conflict.backup
                    assert target.is_symlink() and os.readlink(target) == backup.name
                elif variant.endswith('-owner'):
                    assert identity.metadata(target.lstat())[2] == 23456
                else:
                    # Bind mount ID changes while inode/device remain identical.
                    assert conflict.owned_mounts == machine.mounts
                    assert identity.metadata(target.lstat()) == original
            if fail_body:
                raise ValueError('body failure')
    except ValueError:
        assert fail_body
    assert identity.metadata(target.lstat()) == original
    assert ownership.witness(machine.marker) == original_marker
    assert (machine.home / 'retained').read_bytes() == b'foreign home contents'
    assert (machine.state / 'record').read_bytes() == b'product record before removal'
    assert not machine.mounts
    assert backup is None or not backup.exists()
    assert not any(p.name.startswith('.onpc-') for p in target.parent.iterdir())
    if target.is_dir():
        assert not any(p.name.startswith('.onpc-') for p in target.iterdir())
    assert json.loads(record.call_args.args[1])['variant'] == variant


def test_state_mount_allows_product_recovery_record_transition(machine):
    with identity.identity_filesystem_conflict('state-mount', 23456, Mock()) as conflict:
        (machine.state / 'record').write_bytes(b'product record removing')
        (machine.state / 'new-recovery-record').write_bytes(b'removing\n')
        conflict.verify()
    assert (machine.state / 'record').read_bytes() == b'product record removing'
    assert (machine.state / 'new-recovery-record').read_bytes() == b'removing\n'


def test_marker_allows_consumed_owned_rollback_directory(machine):
    baseline = machine.state / 'fapolicyd-before-install'
    baseline.mkdir()
    original_marker = ownership.witness(machine.marker)
    with identity.identity_filesystem_conflict('kiosk-marker-uid', 23456, Mock()) as conflict:
        before = machine.state.stat().st_nlink
        baseline.rmdir()
        assert machine.state.stat().st_nlink == before - 1
        conflict.verify()
    assert ownership.witness(machine.marker) == original_marker
    assert not baseline.exists()


@pytest.mark.parametrize('change', ['inode', 'owner', 'mode'])
def test_marker_state_ancestor_keeps_authoritative_identity_checks(machine, change):
    with pytest.raises(identity.guest.GuestError, match='parent-identity-changed'):
        with identity.identity_filesystem_conflict('kiosk-marker-uid', 23456, Mock()):
            if change == 'inode':
                machine.state.rename(machine.state.with_name('retained-state'))
                machine.state.mkdir()
                machine.marker.write_bytes(b'foreign marker')
            elif change == 'owner':
                fd = os.open(machine.state, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fchown(fd, 34567, os.getgid())
                finally:
                    os.close(fd)
            else:
                machine.state.chmod(0o700)
    assert machine.marker.read_bytes() == (b'foreign marker' if change == 'inode' else b'23456\n')


@pytest.mark.parametrize('change', ['sentinel-bytes', 'sentinel-replace', 'root-owner',
                                    'root-mode', 'root-xattr', 'root-replace',
                                    'parent-replace', 'mount-extra', 'mount-namespace'])
def test_foreign_change_blocks_cleanup_and_preserves_conflict(machine, change):
    if change == 'root-xattr' and not hasattr(os, 'setxattr'):
        pytest.skip('xattrs unavailable')
    with pytest.raises(identity.guest.GuestError):
        with identity.identity_filesystem_conflict('home-mount', 23456, Mock()) as conflict:
            sentinel = conflict.root() / conflict.sentinel.name
            if change == 'sentinel-bytes':
                sentinel.write_bytes(b'foreign modification')
            elif change == 'sentinel-replace':
                sentinel.rename(sentinel.with_name('retained-sentinel'))
                sentinel.write_bytes(b'foreign replacement')
            elif change == 'root-owner':
                os.fchown(conflict.fd, 34567, os.getgid())
            elif change == 'root-mode':
                machine.home.chmod(0o700)
            elif change == 'root-xattr':
                os.setxattr(machine.home, 'user.onpc-test', b'foreign')
            elif change == 'root-replace':
                machine.home.rename(machine.home.with_name('retained-root'))
                machine.home.mkdir()
            elif change == 'parent-replace':
                parent = machine.home.parent
                parent.rename(parent.with_name(parent.name + '-retained'))
                parent.mkdir()
            elif change == 'mount-extra':
                machine.mounts['43'] = (('43', '1', '0:1', '/', '/unexpected', 'rw'), ())
            else:
                machine.namespace[0] = 'mnt:[foreign]'
    assert machine.mounts  # Cleanup never unmounts after a foreign change.
    assert not any(call.args[0][0] == 'umount' for call in identity.guest.run.call_args_list)


def test_changed_link_and_retained_referent_are_preserved(machine):
    with pytest.raises(identity.guest.GuestError, match='link-identity-changed'):
        with identity.identity_filesystem_conflict('home-link', 23456, Mock()) as conflict:
            machine.home.unlink()
            machine.home.symlink_to('foreign-target')
    assert os.readlink(machine.home) == 'foreign-target'
    assert (conflict.backup / 'retained').read_bytes() == b'foreign home contents'


def test_changed_marker_is_preserved(machine):
    with pytest.raises(identity.guest.GuestError, match='marker-identity-changed'):
        with identity.identity_filesystem_conflict('kiosk-marker-uid', 23456, Mock()):
            machine.marker.write_bytes(b'34567\n')
    assert machine.marker.read_bytes() == b'34567\n'


@pytest.mark.parametrize('variant', identity.IDENTITY_FILESYSTEM_VARIANTS)
def test_callback_failure_restores_exact_conflict(machine, variant):
    original = ownership.witness(machine.marker)
    with pytest.raises(ValueError, match='record failed'):
        with identity.identity_filesystem_conflict(variant, 23456,
                                                 Mock(side_effect=ValueError('record failed'))):
            pytest.fail('must not yield')
    assert ownership.witness(machine.marker) == original
    assert machine.home.is_dir() and not machine.home.is_symlink()
    assert machine.state.is_dir() and not machine.state.is_symlink()
    assert not machine.mounts


def test_failed_link_publication_restores_original_root(machine, monkeypatch):
    original = machine.home.stat().st_ino
    monkeypatch.setattr(Path, 'symlink_to', Mock(side_effect=OSError('publication failed')))
    with pytest.raises(OSError, match='publication failed'):
        with identity.identity_filesystem_conflict('home-link', 23456, Mock()):
            pytest.fail('must not yield')
    assert machine.home.stat().st_ino == original
    assert sorted(p.name for p in machine.home.iterdir()) == ['retained']


def test_partial_marker_write_restores_original_bytes(machine, monkeypatch):
    original = ownership.witness(machine.marker)
    write = os.write
    calls = 0

    def partial_then_fail(fd, data):
        nonlocal calls
        calls += 1
        if calls == 1:
            return write(fd, data[:2])
        if calls == 2:
            raise OSError('partial write')
        return write(fd, data)

    monkeypatch.setattr(identity.os, 'write', partial_then_fail)
    with pytest.raises(OSError, match='partial write'):
        with identity.identity_filesystem_conflict('kiosk-marker-uid', 23456, Mock()):
            pytest.fail('must not yield')
    assert ownership.witness(machine.marker) == original


def test_partial_sentinel_write_removes_only_created_sentinel(machine, monkeypatch):
    write = os.write
    calls = 0

    def partial_then_fail(fd, data):
        nonlocal calls
        calls += 1
        if calls == 1:
            return write(fd, data[:3])
        raise OSError('partial sentinel')

    monkeypatch.setattr(identity.os, 'write', partial_then_fail)
    with pytest.raises(OSError, match='partial sentinel'):
        with identity.identity_filesystem_conflict('home-owner', 23456, Mock()):
            pytest.fail('must not yield')
    assert sorted(p.name for p in machine.home.iterdir()) == ['retained']


def test_mount_command_failure_after_kernel_success_recovers_only_own_mount(machine):
    def mount_then_fail(command, **kwargs):
        result = machine.run(command, **kwargs)
        if command[0] == 'mount':
            raise OSError('mount reporting failed')
        return result

    identity.guest.run.side_effect = mount_then_fail
    with pytest.raises(OSError, match='mount reporting failed'):
        with identity.identity_filesystem_conflict('home-mount', 23456, Mock()):
            pytest.fail('must not yield')
    assert not machine.mounts
    assert sorted(p.name for p in machine.home.iterdir()) == ['retained']


def test_guard_precedes_path_reads(machine, monkeypatch):
    monkeypatch.setattr(identity.guest, 'guard', Mock(side_effect=ValueError('guard')))
    with pytest.raises(ValueError, match='guard'):
        with identity.identity_filesystem_conflict('home-owner', 23456, Mock()):
            pytest.fail('must not yield')
    identity.parents.assert_not_called()


@pytest.mark.parametrize('variant,uid', [('unknown', 23456), ('home-owner', 0),
                                       ('home-owner', True)])
def test_invalid_selection_refuses_before_mutation(machine, variant, uid):
    with pytest.raises(identity.guest.GuestError):
        with identity.identity_filesystem_conflict(variant, uid, Mock()):
            pytest.fail('must not yield')
    assert sorted(p.name for p in machine.home.iterdir()) == ['retained']


def test_existing_nested_mount_is_never_adopted(machine):
    machine.mounts['41'] = (('41', '1', '0:1', '/', str(machine.home / 'nested')), ())
    with pytest.raises(identity.guest.GuestError, match='preexisting-mount'):
        with identity.identity_filesystem_conflict('home-mount', 23456, Mock()):
            pytest.fail('must not yield')
    identity.guest.run.assert_not_called()


@pytest.mark.parametrize('status', [0, 1, 2])
def test_marker_refuses_active_or_unknown_manager_status_without_mutation(machine, status):
    original = ownership.witness(machine.marker)
    identity.guest.commands.last_returncode = status
    with pytest.raises(identity.guest.GuestError, match='foreign-manager-not-inactive'):
        with identity.identity_filesystem_conflict('kiosk-marker-uid', 23456, Mock()):
            pytest.fail('must not yield')
    assert ownership.witness(machine.marker) == original


def test_missing_foreign_account_refused_without_mutation(machine, monkeypatch):
    monkeypatch.setattr(identity.pwd, 'getpwuid', Mock(side_effect=KeyError()))
    with pytest.raises(identity.guest.GuestError, match='foreign-account-missing'):
        with identity.identity_filesystem_conflict('home-owner', 23456, Mock()):
            pytest.fail('must not yield')
    assert sorted(p.name for p in machine.home.iterdir()) == ['retained']
