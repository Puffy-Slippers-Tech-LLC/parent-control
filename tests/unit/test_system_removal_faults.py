"""Private mount rows/files and bounded harmless wrapper shell children only."""

import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_removal
import system_removal_faults as faults


@pytest.mark.parametrize('target', ['bin', '../foreign', '/usr/bin'])
def test_native_tool_accepts_only_pinned_distribution_sbin_alias(tmp_path, monkeypatch, target):
    sbin, bindir = tmp_path / 'sbin', tmp_path / 'bin'
    bindir.mkdir()
    sbin.symlink_to(target)
    monkeypatch.setattr(faults, 'OWNER_UID', os.getuid())
    monkeypatch.setattr(faults, 'SBIN', sbin)
    monkeypatch.setattr(faults, 'BIN', bindir)
    monkeypatch.setattr(faults, 'TOOLS', {'selinux': sbin / 'semodule'})
    monkeypatch.setattr(faults, 'parents', lambda _: None)
    if target != 'bin':
        with pytest.raises(faults.guest.GuestError, match='unsafe-native-tool-alias'):
            faults.native_tool('selinux')
        return
    tool, aliases = faults.native_tool('selinux')
    assert tool == bindir / 'semodule'
    fault = faults.Fault('mac-unload', tool, (), aliases=aliases)
    fault.verify_artifacts()
    sbin.unlink()
    sbin.symlink_to('foreign')
    with pytest.raises(faults.guest.GuestError, match='native-tool-alias'):
        fault.verify_artifacts()


@pytest.fixture
def machine(tmp_path, monkeypatch):
    monkeypatch.setattr(faults, 'OWNER_UID', os.getuid())
    monkeypatch.setattr(faults, 'parents', lambda path: None)
    monkeypatch.setattr(faults.guest, 'guard', Mock())
    target = tmp_path / 'target'
    target.write_bytes(b'unchanged\n')
    target.chmod(0o600)
    return target


def mount_double(monkeypatch, target, *, variant='denial-publication', directory=False):
    rows, operations = {}, []
    state = {'namespace': 'mnt:[123]', 'source': target, 'fail_unmount': False}
    native_identity = faults.identity
    def identity(path, **kwargs):
        if path == target and rows:
            return native_identity(state['source'], **kwargs)
        return native_identity(path, **kwargs)
    def inventory():
        return state['namespace'], dict(rows)
    def run(argv, **kwargs):
        operations.append(argv)
        if argv[:2] == ['mount', '--bind']:
            state['source'] = Path(argv[2])
            rows['42'] = (('42', '1', '8:1', argv[2], str(target), 'rw'),
                          ('ext4', '/dev/root', 'rw'))
        elif argv[:2] == ['umount', '--']:
            if state['fail_unmount']:
                raise faults.guest.GuestError('unmount-failed')
            rows.clear()
        else:
            pytest.fail('unexpected command')
    monkeypatch.setattr(system_removal, 'mount_inventory', inventory)
    monkeypatch.setattr(faults.guest, 'run', run)
    monkeypatch.setattr(faults, 'identity', identity)
    fault = faults.Fault(variant, target, native_identity(target, directory=directory),
                         directory=directory)
    return fault, rows, operations, state


@pytest.mark.parametrize('directory', [False, True])
@pytest.mark.parametrize('failure', ['none', 'preexisting', 'namespace', 'foreign-row',
                                     'foreign-file', 'body', 'record', 'unmount'])
def test_mount_lifetime_preserves_foreign_state_and_joins_cleanup(
        machine, monkeypatch, tmp_path, directory, failure):
    if directory:
        machine.unlink()
        machine.mkdir(mode=0o700)
    fault, rows, commands, state = mount_double(monkeypatch, machine, directory=directory)
    if failure == 'preexisting':
        rows['99'] = (('99', '1', '8:1', '/', str(machine), 'rw'), ('ext4', '/dev/root', 'rw'))
    def record(*args):
        if failure == 'record':
            raise RuntimeError('record-failed')
    def exercise():
        with faults.mounted_fault(fault, machine, record):
            if failure == 'namespace':
                state['namespace'] = 'mnt:[456]'
            elif failure == 'foreign-row':
                rows['99'] = rows.pop('42')
            elif failure == 'foreign-file':
                replacement = tmp_path / 'replacement'
                if directory:
                    replacement.mkdir(mode=0o700)
                else:
                    replacement.write_bytes(b'foreign')
                    replacement.chmod(0o600)
                state['source'] = replacement
            elif failure == 'body':
                raise RuntimeError('body-failed')
            elif failure == 'unmount':
                state['fail_unmount'] = True
    if failure == 'none':
        exercise()
    else:
        with pytest.raises((faults.guest.GuestError, RuntimeError)):
            exercise()
    unmounts = [command for command in commands if command[0] == 'umount']
    assert len(unmounts) == (1 if failure in ('none', 'body', 'record', 'unmount') else 0)
    if failure == 'preexisting':
        assert commands == []
    assert all('-l' not in command and '-f' not in command for command in commands)


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'writable', 'wrong-owner'])
def test_target_identity_refuses_substitution(machine, monkeypatch, tmp_path, kind):
    if kind == 'symlink':
        link = tmp_path / 'link'
        link.symlink_to(machine)
        machine = link
    elif kind == 'hardlink':
        os.link(machine, tmp_path / 'link')
    elif kind == 'writable':
        machine.chmod(0o666)
    else:
        monkeypatch.setattr(faults, 'OWNER_UID', os.getuid() + 1)
    with pytest.raises(faults.guest.GuestError, match='unsafe-target'):
        faults.identity(machine)


@pytest.mark.parametrize('backend', ['selinux', 'apparmor'])
@pytest.mark.parametrize('operation', ['exact', 'prefix', 'suffix', 'different', 'empty'])
def test_wrapper_only_refuses_exact_native_unload(tmp_path, backend, operation):
    original = tmp_path / 'original with spaces'
    original.write_text('#!/bin/sh\nprintf "delegated:%s\\n" "$#"\nexit 23\n')
    original.chmod(0o700)
    witness = tmp_path / 'witness with spaces'
    wrapper = tmp_path / 'wrapper'
    arguments = faults.unload_arguments(backend)
    wrapper.write_text(faults.wrapper_source(original, witness, arguments))
    wrapper.chmod(0o700)
    selected = {'exact': arguments, 'prefix': arguments[:1], 'suffix': [*arguments, 'extra'],
                'different': ['-i', 'onpc-kiosk'], 'empty': []}[operation]
    result = subprocess.run([str(wrapper), *selected], capture_output=True, timeout=5)
    assert result.returncode == (79 if operation == 'exact' else 23)
    if operation == 'exact':
        assert witness.read_bytes() == faults.WITNESS
        assert stat.S_IMODE(witness.stat().st_mode) == 0o600
        assert result.stdout == b''
    else:
        assert not witness.exists()
        assert result.stdout == f'delegated:{len(selected)}\n'.encode()


def test_wrapper_refuses_existing_witness_without_overwriting(tmp_path):
    original, witness = tmp_path / 'original', tmp_path / 'witness'
    witness.write_bytes(b'foreign')
    wrapper = tmp_path / 'wrapper'
    arguments = faults.unload_arguments('selinux')
    wrapper.write_text(faults.wrapper_source(original, witness, arguments))
    wrapper.chmod(0o700)
    result = subprocess.run([str(wrapper), *arguments], capture_output=True, timeout=5)
    assert result.returncode != 79 and result.returncode != 0
    assert witness.read_bytes() == b'foreign'


@pytest.mark.parametrize('variant', ['denial-publication', 'account-finalization'])
@pytest.mark.parametrize('prepared', [False, True])
def test_self_bind_trigger_requires_removal_intent(machine, monkeypatch, tmp_path,
                                                  variant, prepared):
    state, marker = tmp_path / 'state', tmp_path / 'marker'
    state.write_text(json.dumps({'removing': prepared}))
    marker.write_bytes(b'removing\n')
    state.chmod(0o600)
    marker.chmod(0o600)
    monkeypatch.setattr(faults, 'STATE', state)
    monkeypatch.setattr(faults, 'MARKER', marker)
    fault = faults.Fault(variant, machine, faults.identity(machine))
    if prepared:
        fault.verify_triggered()
    else:
        with pytest.raises(faults.guest.GuestError, match='transition-not-observed'):
            fault.verify_triggered()


@pytest.mark.parametrize('value', [None, b'foreign', faults.WITNESS])
def test_mac_fault_requires_exact_native_unload_witness(machine, tmp_path, value):
    witness = tmp_path / 'witness'
    if value is not None:
        witness.write_bytes(value)
        witness.chmod(0o600)
    expected = faults.identity(machine)
    fault = faults.Fault('mac-unload', machine, expected, wrapper=expected, witness=witness)
    if value == faults.WITNESS:
        fault.verify_triggered()
    else:
        with pytest.raises((faults.guest.GuestError, FileNotFoundError)):
            fault.verify_triggered()


def test_fixture_replacement_refuses_cleanup(machine, monkeypatch, tmp_path):
    original = tmp_path / 'original'
    original.write_bytes(b'original')
    original.chmod(0o600)
    fault, _, operations, _ = mount_double(monkeypatch, machine)
    fault.artifacts = ((original, faults.identity(original)),)
    with pytest.raises(faults.guest.GuestError, match='fixture-identity-changed'):
        with faults.mounted_fault(fault, machine, Mock()):
            original.write_bytes(b'foreign')
    assert not any(command[0] == 'umount' for command in operations)


def test_interruption_entry_guard_precedes_all_actions(monkeypatch):
    monkeypatch.setattr(faults.guest, 'guard', Mock(side_effect=faults.guest.GuestError('identity')))
    identify = Mock()
    monkeypatch.setattr(faults, 'identity', identify)
    with pytest.raises(faults.guest.GuestError, match='identity'):
        with faults.interruption_fault('mac-unload', Mock()):
            pass
    identify.assert_not_called()


@pytest.mark.parametrize('backend', ['selinux', 'apparmor'])
def test_mac_setup_preserves_native_tool_and_retains_owned_private_evidence(
        machine, monkeypatch, tmp_path, backend):
    state = tmp_path / 'state'
    state.write_text(json.dumps({'backend': backend}))
    state.chmod(0o600)
    monkeypatch.setattr(faults, 'STATE', state)
    monkeypatch.setattr(faults, 'TOOLS', {backend: machine})
    monkeypatch.setattr(faults.guest, 'PAYLOAD', tmp_path)
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    machine.chmod(0o755)
    before = faults.identity(machine)
    _, rows, operations, _ = mount_double(monkeypatch, machine, variant='mac-unload')
    with faults.interruption_fault('mac-unload', Mock()) as fault:
        assert len(rows) == 1
        assert fault.witness.parent.parent == private
        assert fault.artifacts[0][0].read_bytes() == before[-1]
        assert stat.S_IMODE(fault.wrapper[4]) == 0o755
        fault.witness.write_bytes(faults.WITNESS)
        fault.witness.chmod(0o600)
        fault.verify_triggered()
    assert faults.identity(machine) == before
    assert len(operations) == 2
    assert fault.witness.read_bytes() == faults.WITNESS


def test_parent_symlink_is_refused_without_following(tmp_path, monkeypatch):
    monkeypatch.setattr(faults, 'OWNER_UID', os.getuid())
    # Test the closest ancestor only: the link must refuse before /tmp matters.
    link = tmp_path / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(faults.guest.GuestError, match='unsafe-parent'):
        faults.parents(link / 'file')


@pytest.mark.parametrize('ancestor,owner,mode,accepted', [
    ('/var/tmp', 0, 0o1777, True),
    ('/var/tmp', 0, 0o0777, False),
    ('/var/tmp', 1, 0o1777, False),
    ('/tmp', 0, 0o1777, False),
    ('/var/tmp/private', 0, 0o1777, False),
])
def test_only_fixed_root_owned_sticky_guest_scratch_ancestor_is_allowed(
        monkeypatch, ancestor, owner, mode, accepted):
    selected = Path(ancestor)
    monkeypatch.setattr(faults, 'OWNER_UID', 0)
    def lstat(path):
        return SimpleNamespace(st_uid=owner if path == selected else 0,
                               st_mode=stat.S_IFDIR | (mode if path == selected else 0o755))
    monkeypatch.setattr(Path, 'lstat', lstat)
    if accepted:
        faults.parents(selected / 'allocation/private/original')
    else:
        with pytest.raises(faults.guest.GuestError, match='unsafe-parent'):
            faults.parents(selected / 'allocation/private/original')
