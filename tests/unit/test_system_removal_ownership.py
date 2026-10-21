"""Private pytest files and process-local ownership/mount doubles only."""

import json
import os
from pathlib import Path
import stat
from unittest.mock import Mock

import pytest

import system_removal
import system_removal_ownership as ownership


@pytest.fixture
def machine(tmp_path, monkeypatch):
    target = tmp_path / 'target'
    target.write_bytes(b'{"version": 1, "uid": 12345, "expires": null, "phase": "quarantined"}\n')
    target.chmod(0o600)
    monkeypatch.setattr(ownership, 'OWNER_UID', os.getuid())
    monkeypatch.setattr(ownership, 'parents', Mock())
    monkeypatch.setattr(ownership.guest, 'guard', Mock())
    monkeypatch.setattr(system_removal, 'mount_inventory', lambda: ('mnt:[fixture]', {}))
    # Simulate chown only for the private inode: no privileged host operations.
    owners = {}
    real_metadata = ownership.metadata

    def metadata(info):
        value = list(real_metadata(info))
        value[2:4] = owners.get((info.st_dev, info.st_ino), value[2:4])
        return tuple(value)

    def chown(fd, uid, gid):
        info = os.fstat(fd)
        owners[info.st_dev, info.st_ino] = (uid, gid)

    monkeypatch.setattr(ownership, 'metadata', metadata)
    monkeypatch.setattr(ownership.os, 'fchown', chown)
    return target


@pytest.mark.parametrize('variant', ownership.OWNERSHIP_VARIANTS)
@pytest.mark.parametrize('body_failure', [False, True])
def test_each_conflict_preserves_controls_and_restores_exact_inode(machine, variant, body_failure):
    original = ownership.witness(machine)
    record = Mock()
    backup = None
    try:
        with ownership.ownership_conflict(variant, machine, 23456, record) as conflict:
            conflict.verify()
            assert conflict.expected.metadata[:2] == ownership.witness(machine).metadata[:2]
            if variant.endswith('-link'):
                backup = conflict.backup
                assert machine.is_symlink()
                assert os.readlink(machine) == backup.name
                assert machine.read_bytes() == original.contents
                assert ownership.witness(backup) == original
            elif variant.endswith('-owner'):
                assert conflict.expected.metadata[2] == 23456
                assert stat.S_IMODE(conflict.expected.metadata[4]) == 0o600
                assert conflict.expected.contents == original.contents
            elif variant.endswith('-uid'):
                assert json.loads(machine.read_bytes()) == {
                    'version': 1, 'uid': 23456, 'expires': None, 'phase': 'quarantined'}
            else:
                assert machine.read_bytes() == original.contents + ownership.COMMENT
            if body_failure:
                raise ValueError('body failure')
    except ValueError:
        assert body_failure
    assert ownership.witness(machine) == original
    assert backup is None or not backup.exists()
    assert record.call_count == 1
    details = json.loads(record.call_args.args[1])
    assert details['variant'] == variant
    assert details['referent_inode'] == original.metadata[1]


@pytest.mark.parametrize('variant', ['systemd-user-edit', 'gdm-password-link'])
def test_replaced_conflict_is_preserved_and_cleanup_refused(machine, variant):
    displaced = machine.parent / 'displaced'
    with pytest.raises(ownership.guest.GuestError, match='conflict-identity-changed'):
        with ownership.ownership_conflict(variant, machine, 23456, Mock()) as conflict:
            machine.rename(displaced)
            machine.write_bytes(b'foreign replacement')
            replacement = ownership.witness(machine)
    assert ownership.witness(machine) == replacement
    assert displaced.exists()
    if conflict.backup:
        assert conflict.backup.exists()


@pytest.mark.parametrize('change', ['bytes', 'replacement', 'metadata'])
def test_referent_changes_are_preserved_and_cleanup_refused(machine, change):
    with pytest.raises(ownership.guest.GuestError, match='referent-identity-changed'):
        with ownership.ownership_conflict('systemd-user-link', machine, 23456, Mock()) as conflict:
            backup = conflict.backup
            if change == 'replacement':
                backup.rename(backup.parent / 'displaced-original')
                backup.write_bytes(b'foreign referent')
            elif change == 'bytes':
                backup.write_bytes(b'changed referent')
            else:
                backup.chmod(0o640)
            changed = ownership.witness(backup)
    assert machine.is_symlink()
    assert ownership.witness(backup) == changed


def test_same_inode_conflict_edit_is_preserved(machine):
    with pytest.raises(ownership.guest.GuestError, match='conflict-identity-changed'):
        with ownership.ownership_conflict('systemd-user-edit', machine, 23456, Mock()):
            machine.write_bytes(b'foreign edit')
            changed = ownership.witness(machine)
    assert ownership.witness(machine) == changed


def test_changed_link_text_is_preserved(machine):
    with pytest.raises(ownership.guest.GuestError, match='conflict-identity-changed'):
        with ownership.ownership_conflict('gdm-hook-link', machine, 23456, Mock()) as conflict:
            machine.unlink()
            machine.symlink_to('foreign-link-target')
            changed = ownership.witness(machine)
    assert ownership.witness(machine) == changed
    assert conflict.backup.exists()


def test_atomic_restore_never_overwrites_new_destination(machine, monkeypatch):
    rename = ownership.rename_exclusive
    original = ownership.witness(machine)
    with pytest.raises(FileExistsError):
        with ownership.ownership_conflict('systemd-user-link', machine, 23456, Mock()) as conflict:
            def substitute_then_rename(source, destination):
                destination.write_bytes(b'foreign race winner')
                return rename(source, destination)

            monkeypatch.setattr(ownership, 'rename_exclusive', substitute_then_rename)
    assert machine.read_bytes() == b'foreign race winner'
    assert ownership.witness(conflict.backup) == original


def test_exclusive_backup_never_overwrites_collision(machine, monkeypatch):
    collision = machine.parent / '.onpc-removal-owned-collision'
    collision.write_bytes(b'foreign sibling')
    monkeypatch.setattr(ownership.uuid, 'uuid4', lambda: type('ID', (), {'hex': 'collision'})())
    original, foreign = ownership.witness(machine), ownership.witness(collision)
    with pytest.raises(FileExistsError):
        with ownership.ownership_conflict('systemd-user-link', machine, 23456, Mock()):
            pytest.fail('must not yield')
    assert ownership.witness(machine) == original
    assert ownership.witness(collision) == foreign


@pytest.mark.parametrize('payload', [
    b'{"kiosk_uid": 12345}', b'{"uid": 12345}', b'[]',
    b'{"version": 1, "uid": "12345", "expires": null, "phase": "quarantined"}',
    b'{"version": 1, "uid": 23456, "expires": null, "phase": "quarantined"}',
    b'{"version": true, "uid": 12345, "expires": null, "phase": "quarantined"}',
    b'{"version": 1, "uid": 12345, "expires": -1, "phase": "quarantined"}',
    b'{"version": 1, "uid": 12345, "expires": true, "phase": "quarantined"}',
    b'{"version": 1, "uid": 12345, "expires": null, "phase": "unknown"}',
    b'{"version": 1, "uid": 12345, "expires": null, "phase": "quarantined", "extra": 1}',
])
def test_invalid_record_rejected_before_mutation(machine, payload):
    machine.write_bytes(payload)
    original = ownership.witness(machine)
    with pytest.raises(ownership.guest.GuestError, match='unsafe-record-uid'):
        with ownership.ownership_conflict('confinement-record-uid', machine, 23456, Mock()):
            pytest.fail('must not yield')
    assert ownership.witness(machine) == original


def test_record_callback_failure_restores_original(machine):
    original = ownership.witness(machine)
    with pytest.raises(ValueError, match='record failed'):
        with ownership.ownership_conflict('gdm-hook-link', machine, 23456,
                                          Mock(side_effect=ValueError('record failed'))):
            pytest.fail('must not yield')
    assert ownership.witness(machine) == original


def test_failed_link_publication_restores_original(machine, monkeypatch):
    original = ownership.witness(machine)
    monkeypatch.setattr(Path, 'symlink_to', Mock(side_effect=OSError('publication failed')))
    with pytest.raises(OSError, match='publication failed'):
        with ownership.ownership_conflict('gdm-password-link', machine, 23456, Mock()):
            pytest.fail('must not yield')
    assert ownership.witness(machine) == original
    assert list(machine.parent.iterdir()) == [machine]


@pytest.mark.parametrize('variant', ['systemd-user-edit', 'systemd-user-link'])
def test_failed_initial_conflict_witness_restores_known_changes(machine, monkeypatch, variant):
    original = ownership.witness(machine)
    reader = ownership.witness
    failed = False

    def fail_conflict(path):
        nonlocal failed
        value = reader(path)
        if path == machine and value != original and not failed:
            failed = True
            raise OSError('witness failed')
        return value

    monkeypatch.setattr(ownership, 'witness', fail_conflict)
    with pytest.raises(OSError, match='witness failed'):
        with ownership.ownership_conflict(variant, machine, 23456, Mock()):
            pytest.fail('must not yield')
    assert ownership.witness(machine) == original
    assert list(machine.parent.iterdir()) == [machine]


def test_partial_write_failure_restores_only_known_prefix(machine, monkeypatch):
    original = ownership.witness(machine)
    write = os.write
    calls = 0

    def partial_then_fail(fd, data):
        nonlocal calls
        calls += 1
        if calls == 1:
            return write(fd, data[:4])
        if calls == 2:
            raise OSError('write failed')
        return write(fd, data)

    monkeypatch.setattr(ownership.os, 'write', partial_then_fail)
    with pytest.raises(OSError, match='write failed'):
        with ownership.ownership_conflict('confinement-record-uid', machine, 23456, Mock()):
            pytest.fail('must not yield')
    assert ownership.witness(machine) == original


def test_failed_publication_preserves_unrelated_replacement(machine, monkeypatch):
    original = ownership.witness(machine)

    def foreign_publication(path, target):
        path.write_bytes(b'foreign publication')
        raise OSError('publication failed')

    monkeypatch.setattr(Path, 'symlink_to', foreign_publication)
    with pytest.raises(ownership.guest.GuestError, match='partial-path-occupied'):
        with ownership.ownership_conflict('gdm-password-link', machine, 23456, Mock()):
            pytest.fail('must not yield')
    assert machine.read_bytes() == b'foreign publication'
    backups = [p for p in machine.parent.iterdir() if p != machine]
    assert len(backups) == 1
    assert ownership.witness(backups[0]) == original


def test_guard_runs_before_any_path_inspection(machine, monkeypatch):
    monkeypatch.setattr(ownership.guest, 'guard', Mock(side_effect=ValueError('guard')))
    reader = Mock(side_effect=AssertionError('path inspected'))
    monkeypatch.setattr(ownership, 'witness', reader)
    with pytest.raises(ValueError, match='guard'):
        with ownership.ownership_conflict('systemd-user-edit', machine, 23456, Mock()):
            pytest.fail('must not yield')
    reader.assert_not_called()
    ownership.parents.assert_not_called()


@pytest.mark.parametrize('unsafe', ['link', 'hardlink', 'writable', 'mount', 'parent'])
def test_unsafe_original_is_refused_without_mutation(machine, monkeypatch, unsafe):
    original = machine.read_bytes()
    if unsafe == 'link':
        saved = machine.parent / 'saved'
        machine.rename(saved)
        machine.symlink_to(saved.name)
    elif unsafe == 'hardlink':
        os.link(machine, machine.parent / 'alias')
    elif unsafe == 'writable':
        machine.chmod(0o666)
    elif unsafe == 'mount':
        monkeypatch.setattr(system_removal, 'mount_inventory', lambda: (
            'mnt:[fixture]', {'42': (('42', '0', '0:1', '/', str(machine)), ())}))
    else:
        monkeypatch.setattr(ownership, 'parents', Mock(side_effect=ownership.guest.GuestError('unsafe-parent')))
    with pytest.raises(ownership.guest.GuestError):
        with ownership.ownership_conflict('systemd-user-edit', machine, 23456, Mock()):
            pytest.fail('must not yield')
    assert machine.read_bytes() == original
    assert sorted(p.name for p in machine.parent.iterdir()) == (
        ['saved', 'target'] if unsafe == 'link' else
        ['alias', 'target'] if unsafe == 'hardlink' else ['target'])


def test_mount_change_refuses_cleanup(machine, monkeypatch):
    with pytest.raises(ownership.guest.GuestError, match='mount-identity-changed'):
        with ownership.ownership_conflict('systemd-user-edit', machine, 23456, Mock()):
            changed = ownership.witness(machine)
            monkeypatch.setattr(system_removal, 'mount_inventory', lambda: ('mnt:[replacement]', {}))
    assert ownership.witness(machine) == changed


@pytest.mark.parametrize('variant,uid', [('unknown', 23456), ('systemd-user-edit', 0),
                                       ('systemd-user-edit', True)])
def test_invalid_selection_refused(machine, variant, uid):
    original = ownership.witness(machine)
    with pytest.raises(ownership.guest.GuestError):
        with ownership.ownership_conflict(variant, machine, uid, Mock()):
            pytest.fail('must not yield')
    assert ownership.witness(machine) == original


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_historic_variants_bind_current_authorities(distribution):
    targets = ownership.ownership_targets(distribution)
    assert set(targets) == set(ownership.OWNERSHIP_VARIANTS)
    assert targets['systemd-user-edit'] == targets['gdm-password-link']
    assert targets['systemd-user-edit'].name == (
        'fedora-authselect.json' if distribution == 'fedora' else 'malcontent-pam-before-install')
    assert targets['systemd-user-link'].name == 'installed-child-extension-trust'
    assert targets['gdm-hook-link'] == Path('/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules')
    for variant in ownership.OWNERSHIP_VARIANTS:
        assert ownership.ownership_reason(variant, distribution)
        if variant.startswith('confinement-record-'):
            assert targets[variant].name == 'kiosk-configuration-account.json'


def test_fedora_selection_edit_preserves_valid_json_and_original_inode(machine):
    machine = machine.rename(machine.parent / 'fedora-authselect.json')
    document = {'version': 1, 'original': ['sssd', 'with-faillock'],
                'files': {'system-auth': 'a' * 64}, 'phase': 'installed'}
    machine.write_text(json.dumps(document))
    original = ownership.witness(machine)
    with ownership.ownership_conflict('systemd-user-edit', machine, 23456, Mock()) as conflict:
        assert json.loads(conflict.expected.contents) == {**document, 'original': []}
        assert conflict.expected.metadata[:2] == original.metadata[:2]
    assert ownership.witness(machine) == original


@pytest.mark.parametrize('expires', [None, 0, 99999])
@pytest.mark.parametrize('phase', ['quarantined', 'releasing'])
def test_current_expiry_authority_retains_prior_expiry_and_phase(machine, expires, phase):
    document = {'version': 1, 'uid': 12345, 'expires': expires, 'phase': phase}
    machine.write_text(json.dumps(document))
    original = ownership.witness(machine)
    with ownership.ownership_conflict('confinement-record-uid', machine, 23456, Mock()) as conflict:
        assert json.loads(conflict.expected.contents) == {**document, 'uid': 23456}
    assert ownership.witness(machine) == original
