"""Private mount rows/files and bounded harmless wrapper shell children only."""

import json
import os
from pathlib import Path
import stat
import subprocess
import shlex
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_removal
import system_removal_faults as faults
from tests.support.package_scripts import Machine, prepared_lifecycle_machine, script_source
from tools.test_storage import scratch_descriptors


@pytest.mark.parametrize('target', ['bin', '../foreign', '/usr/bin'])
def test_native_tool_accepts_only_pinned_distribution_sbin_alias(tmp_path, monkeypatch, target):
    sbin, bindir = tmp_path / 'sbin', tmp_path / 'bin'
    bindir.mkdir()
    sbin.symlink_to(target)
    monkeypatch.setattr(faults, 'OWNER_UID', os.getuid())
    monkeypatch.setattr(faults, 'SBIN', sbin)
    monkeypatch.setattr(faults, 'BIN', bindir)
    monkeypatch.setattr(faults, 'TOOLS', {'usermod': sbin / 'usermod'})
    monkeypatch.setattr(faults, 'parents', lambda _: None)
    if target != 'bin':
        with pytest.raises(faults.guest.GuestError, match='unsafe-native-tool-alias'):
            faults.native_tool('usermod')
        return
    tool, aliases = faults.native_tool('usermod')
    assert tool == bindir / 'usermod'
    fault = faults.Fault('denial-publication', tool, (), aliases=aliases)
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
            if state.get('fail_bind_before'):
                raise faults.guest.GuestError('bind-failed')
            state['source'] = Path(argv[2])
            rows['42'] = (('42', '1', '8:1', argv[2], str(target), 'rw'),
                          ('ext4', '/dev/root', 'rw'))
            if state.get('fail_bind_after'):
                raise faults.guest.GuestError('bind-failed')
        elif argv[:3] == ['mount', '-o', 'remount,bind,ro']:
            row = rows['42']
            rows['42'] = ((*row[0][:5], 'ro'), row[1])
            if state.get('fail_remount'):
                raise faults.guest.GuestError('remount-failed')
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


@pytest.mark.parametrize('failure', [False, True])
def test_readonly_fault_records_same_mount_and_cleans_after_remount_failure(
        machine, monkeypatch, failure):
    machine.unlink()
    machine.mkdir(mode=0o700)
    fault, rows, operations, state = mount_double(monkeypatch, machine, directory=True)
    state['fail_remount'] = failure
    def exercise():
        with faults.mounted_fault(fault, machine, Mock(), readonly=True):
            assert rows['42'][0][5] == 'ro'
    if failure:
        with pytest.raises(faults.guest.GuestError, match='remount-failed'):
            exercise()
    else:
        exercise()
    assert not rows
    assert operations == [['mount', '--bind', str(machine), str(machine)],
        ['mount', '-o', 'remount,bind,ro', str(machine)], ['umount', '--', str(machine)]]


@pytest.mark.parametrize('after_mount', [False, True])
def test_failed_bind_restores_only_attributable_partial_mount(machine, monkeypatch, after_mount):
    fault, rows, commands, state = mount_double(monkeypatch, machine)
    state['fail_bind_after' if after_mount else 'fail_bind_before'] = True
    with pytest.raises(faults.guest.GuestError, match='bind-failed'):
        with faults.mounted_fault(fault, machine, Mock()):
            pytest.fail('must not yield')
    assert rows == {}
    assert len([command for command in commands if command[0] == 'umount']) == int(after_mount)


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


@pytest.mark.parametrize('variant', faults.INTERRUPTION_VARIANTS)
@pytest.mark.parametrize('operation', ['exact', 'prefix', 'suffix', 'different', 'empty'])
def test_wrapper_only_refuses_exact_current_native_command(tmp_path, monkeypatch, variant, operation):
    monkeypatch.setattr(faults.guest, 'package_path', lambda: Path('/package.deb'))
    original = tmp_path / 'original with spaces'
    original.write_text('#!/bin/sh\nprintf "delegated:%s\\n" "$#"\nexit 23\n')
    original.chmod(0o700)
    witness = tmp_path / 'witness with spaces'
    wrapper = tmp_path / 'wrapper'
    _, _, commands = faults.fault_command(variant)
    arguments = list(commands[0])
    wrapper.write_text(faults.wrapper_source(original, witness, arguments))
    wrapper.chmod(0o700)
    selected = {'exact': arguments, 'prefix': arguments[:-1], 'suffix': [*arguments, 'extra'],
                'different': ['--expiredate', '2', 'oh-no-parent-control'], 'empty': []}[operation]
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
    arguments = ['--expiredate', '1', 'oh-no-parent-control']
    wrapper.write_text(faults.wrapper_source(original, witness, arguments))
    wrapper.chmod(0o700)
    result = subprocess.run([str(wrapper), *arguments], capture_output=True, timeout=5)
    assert result.returncode != 79 and result.returncode != 0
    assert witness.read_bytes() == b'foreign'


def test_wrapper_exact_command_triggers_only_once(tmp_path):
    witness, wrapper = tmp_path / 'witness', tmp_path / 'wrapper'
    arguments = ['--expiredate', '1', 'oh-no-parent-control']
    wrapper.write_text(faults.wrapper_source(tmp_path / 'original', witness, arguments))
    wrapper.chmod(0o700)
    first = subprocess.run([str(wrapper), *arguments], capture_output=True, timeout=5)
    before = witness.stat()
    second = subprocess.run([str(wrapper), *arguments], capture_output=True, timeout=5)
    assert first.returncode == 79
    assert second.returncode not in (0, 79)
    assert witness.read_bytes() == faults.WITNESS
    assert witness.stat().st_ino == before.st_ino
    assert witness.stat().st_mtime_ns == before.st_mtime_ns


@pytest.mark.parametrize('variant', faults.INTERRUPTION_VARIANTS)
@pytest.mark.parametrize('value', [None, b'foreign', faults.WITNESS])
def test_fault_requires_exact_current_native_witness(machine, tmp_path, variant, value):
    witness = tmp_path / 'witness'
    if value is not None:
        witness.write_bytes(value)
        witness.chmod(0o600)
    expected = faults.identity(machine)
    fault = faults.Fault(variant, machine, expected, wrapper=expected, witness=witness)
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


def test_observed_trigger_replacement_refuses_cleanup(machine, monkeypatch, tmp_path):
    witness = tmp_path / 'witness'
    witness.write_bytes(faults.WITNESS)
    witness.chmod(0o600)
    fault, _, operations, _ = mount_double(monkeypatch, machine)
    fault.wrapper, fault.witnesses = fault.expected, (witness,)
    with pytest.raises(faults.guest.GuestError, match='trigger-witness-changed'):
        with faults.mounted_fault(fault, machine, Mock()):
            fault.verify_triggered()
            witness.rename(tmp_path / 'displaced-witness')
            witness.write_bytes(faults.WITNESS)
            witness.chmod(0o600)
    assert not any(command[0] == 'umount' for command in operations)


def test_xattr_change_refuses_cleanup_even_when_native_bytes_match(machine, monkeypatch):
    os.setxattr(machine, 'user.onpc-fixture', b'original')
    fault, _, operations, _ = mount_double(monkeypatch, machine)
    with pytest.raises(faults.guest.GuestError, match='cleanup-ownership-changed'):
        with faults.mounted_fault(fault, machine, Mock()):
            os.setxattr(machine, 'user.onpc-fixture', b'foreign')
    assert not any(command[0] == 'umount' for command in operations)


def test_interruption_entry_guard_precedes_all_actions(monkeypatch):
    monkeypatch.setattr(faults.guest, 'guard', Mock(side_effect=faults.guest.GuestError('identity')))
    identify = Mock()
    monkeypatch.setattr(faults, 'identity', identify)
    with pytest.raises(faults.guest.GuestError, match='identity'):
        with faults.interruption_fault('denial-publication', Mock()):
            pass
    identify.assert_not_called()


@pytest.mark.parametrize('variant', faults.INTERRUPTION_VARIANTS)
@pytest.mark.parametrize('suffix', ['.deb', '.rpm'])
def test_setup_preserves_native_tool_and_retains_owned_private_evidence(
        machine, monkeypatch, tmp_path, variant, suffix):
    monkeypatch.setattr(faults.guest, 'package_path', lambda: Path('/package' + suffix))
    monkeypatch.setattr(faults, 'TOOLS', dict.fromkeys(faults.TOOLS, machine))
    monkeypatch.setattr(faults.guest, 'PAYLOAD', tmp_path)
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    machine.chmod(0o755)
    before = faults.identity(machine)
    _, rows, operations, _ = mount_double(monkeypatch, machine, variant=variant)
    with faults.interruption_fault(variant, Mock()) as fault:
        assert len(rows) == 1
        assert fault.witness.parent.parent == private
        assert fault.artifacts[0][0].read_bytes() == before[-1]
        assert stat.S_IMODE(fault.wrapper[4]) == 0o755
        _, _, commands = faults.fault_command(variant)
        for arguments in commands:
            result = subprocess.run([str(fault.artifacts[1][0]), *arguments],
                                    capture_output=True, timeout=5)
            assert result.returncode == 79
        fault.verify_triggered()
    assert faults.identity(machine) == before
    assert len(operations) == 2
    assert fault.witness.read_bytes() == faults.WITNESS


def test_removed_private_mac_variant_is_rejected_before_path_access(monkeypatch):
    monkeypatch.setattr(faults.guest, 'guard', Mock())
    package = Mock(side_effect=AssertionError('must not inspect package'))
    monkeypatch.setattr(faults.guest, 'package_path', package)
    with pytest.raises(faults.guest.GuestError, match='unknown-variant'):
        with faults.interruption_fault('mac-unload', Mock()):
            pytest.fail('must not yield')
    package.assert_not_called()


@pytest.mark.parametrize('distribution,suffix,backend', [
    ('ubuntu', '.deb', 'apparmor'), ('fedora', '.rpm', 'selinux'),
])
def test_current_prepare_remove_hits_expiry_fault_after_real_journal_then_retries(
        tmp_path, monkeypatch, distribution, suffix, backend):
    root = tmp_path / 'lifecycle'
    root.mkdir(mode=0o700)
    native = prepared_lifecycle_machine(root, monkeypatch, backend, installed=False)
    migration = native.migration
    monkeypatch.setattr(faults.guest, 'package_path', lambda: Path('/package' + suffix))
    tool, _, commands = faults.fault_command('denial-publication')
    assert tool.name == 'usermod'
    original, wrapper, witness = (tmp_path / name for name in ('original', 'wrapper', 'triggered'))
    original.write_text('#!/bin/sh\nprintf "delegated:%s\\n" "$*"\n')
    original.chmod(0o700)
    original_stat, original_bytes = original.stat(), original.read_bytes()
    wrapper.write_text(faults.wrapper_source(original, witness, commands[0]))
    wrapper.chmod(0o700)
    run = migration.run
    observed = []

    def intercepted(arguments):
        if arguments[0] == tool.name:
            # The caller is the real lifecycle set_expiry(), not a synthetic
            # invocation reconstructed from the wrapper's own match table.
            observed.append(list(arguments))
            result = subprocess.run([str(wrapper), *arguments[1:]], capture_output=True,
                                    text=True, timeout=5, pass_fds=scratch_descriptors())
            result.check_returncode()
        return run(arguments)

    monkeypatch.setattr(migration, 'run', intercepted)
    with pytest.raises(subprocess.CalledProcessError) as failure:
        migration.prepare_remove()
    assert failure.value.returncode == 79
    assert observed == [['usermod', '--expiredate', '1', 'oh-no-parent-control']]
    assert witness.read_bytes() == faults.WITNESS
    assert stat.S_IMODE(witness.stat().st_mode) == 0o600
    assert json.loads(migration.EXPIRY.read_bytes()) == {
        'version': 1, 'uid': 1006, 'expires': None, 'phase': 'quarantined'}
    assert native.expires is None
    assert migration.state() is None and not migration.DISABLED.exists()
    # A nonmatching expiry restoration remains an ordinary delegated command.
    delegated = subprocess.run([str(wrapper), '--expiredate', '-1', migration.USER],
                               capture_output=True, text=True, timeout=5,
                               pass_fds=scratch_descriptors())
    assert delegated.returncode == 0 and delegated.stdout.startswith('delegated:')
    witness_before = witness.stat()
    repeated = subprocess.run([str(wrapper), *commands[0]], capture_output=True,
                              timeout=5, pass_fds=scratch_descriptors())
    assert repeated.returncode not in (0, 79)
    assert witness.stat().st_ino == witness_before.st_ino
    assert witness.stat().st_mtime_ns == witness_before.st_mtime_ns
    monkeypatch.setattr(migration, 'run', run)
    migration.prepare_remove()
    assert native.expires == 1
    migration.rollback()
    assert native.expires is None and not migration.EXPIRY.exists()
    assert original.stat().st_ino == original_stat.st_ino
    assert original.read_bytes() == original_bytes


@pytest.mark.parametrize('distribution,suffix', [('ubuntu', '.deb'), ('fedora', '.rpm')])
def test_rendered_removal_and_abort_callbacks_hit_current_faults_then_restore(
        tmp_path, monkeypatch, distribution, suffix):
    machine = Machine(tmp_path, distribution)
    machine.kiosk()
    monkeypatch.setattr(faults.guest, 'package_path', lambda: Path('/package' + suffix))
    monkeypatch.setattr(faults, 'OWNER_UID', os.getuid())
    monkeypatch.setattr(faults, 'parents', lambda _: None)
    tool, _, commands = faults.fault_command('pam-restoration')
    target = tmp_path / tool.relative_to('/')
    original = tmp_path / 'original-distro-pam'
    original_identity = faults.identity(target)
    target.rename(original)
    remove_witness, restore_witness = tmp_path / 'remove-hit', tmp_path / 'restore-hit'
    restore_wrapper = tmp_path / 'restore-wrapper'
    restore_wrapper.write_text(faults.wrapper_source(original, restore_witness, commands[1]))
    restore_wrapper.chmod(0o700)
    target.write_text(faults.wrapper_source(restore_wrapper, remove_witness, commands[0]))
    target.chmod(0o700)
    try:
        removal = machine.run('prerm', 'remove')
        assert removal.returncode == 79, removal.stderr
        assert remove_witness.read_bytes() == faults.WITNESS
        assert not restore_witness.exists()
        mask = tmp_path / 'run/systemd/system/oh-no-parent-control-broker.service'
        guard = tmp_path / 'var/lib/oh-no-parent-control/uninstall-broker-mask'
        assert mask.is_symlink() and guard.exists()
        aborted = machine.run('postinst', 'abort-remove')
        assert aborted.returncode == 79, aborted.stderr
        assert restore_witness.read_bytes() == faults.WITNESS
        assert mask.is_symlink() and guard.exists()
        assert 'uninstall --restore' in machine.commands
        # verify is deliberately not selected by either fault command.
        verified = subprocess.run([str(target), '--distribution', distribution, 'verify'],
                                  capture_output=True, text=True, timeout=5,
                                  env={**os.environ, 'AUDIT_ROOT': str(tmp_path)},
                                  pass_fds=scratch_descriptors())
        assert verified.returncode == 0
        before = {path: (path.stat().st_ino, path.stat().st_mtime_ns)
                  for path in (remove_witness, restore_witness)}
        for phase, action in (('prerm', 'remove'), ('postinst', 'abort-remove')):
            repeated = machine.run(phase, action)
            assert repeated.returncode not in (0, 79)
        assert all((path.stat().st_ino, path.stat().st_mtime_ns) == value
                   for path, value in before.items())
    finally:
        target.unlink()
        original.rename(target)
    assert faults.identity(target) == original_identity
    assert machine.run('postinst', 'abort-remove').returncode == 0
    assert not os.path.lexists(mask) and not guard.exists()
    assert machine.run('prerm', 'remove').returncode == 0

    # The renderer chooses deluser/userdel; intercept that command only, leaving
    # the maintained Machine's remaining shell adapters and finalizer intact.
    tool, _, commands = faults.fault_command('account-finalization')
    assert tool.name == machine.delete_account
    delete_original = tmp_path / 'original-delete'
    delete_original.write_text('#!/bin/sh\n'
        'printf "delete-delegated:%s\\n" "$*" >> "$AUDIT_ROOT/commands"\n'
        'rm "$AUDIT_ROOT/account"\n')
    delete_original.chmod(0o700)
    delete_identity = faults.identity(delete_original)
    delete_wrapper, delete_witness = tmp_path / 'delete-wrapper', tmp_path / 'delete-hit'
    delete_wrapper.write_text(faults.wrapper_source(delete_original, delete_witness, commands[0]))
    delete_wrapper.chmod(0o700)
    source = (tool.name + '() { ' + shlex.quote(str(delete_wrapper)) + ' "$@"; }\n' +
              script_source('postrm', distribution))
    failed = machine.run_source(source, 'remove')
    assert failed.returncode == 79, failed.stderr
    assert delete_witness.read_bytes() == faults.WITNESS
    assert (tmp_path / 'account').exists()
    assert (tmp_path / 'home/oh-no-parent-control').exists()
    assert (tmp_path / 'var/lib/oh-no-parent-control/package-created-kiosk-uid').exists()
    assert faults.identity(delete_original) == delete_identity
    repeated = machine.run_source(source, 'remove')
    assert repeated.returncode not in (0, 79)
    assert (tmp_path / 'account').exists()
    # Restore the maintained command adapter and finish the actual rendered
    # callback; the previous original executable was never rewritten.
    retried = machine.run('postrm', 'remove')
    assert retried.returncode == 0, retried.stderr
    assert not (tmp_path / 'account').exists()
    assert not (tmp_path / 'home/oh-no-parent-control').exists()
    assert not (tmp_path / 'var/lib/oh-no-parent-control/package-created-kiosk-uid').exists()
    assert faults.identity(delete_original) == delete_identity


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
