"""Private confinement lifecycle machines; no host PAM or kernel policy changes."""
import importlib.util
import hashlib
import json
import fcntl
import os
from pathlib import Path
import select
import shutil
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT

NATIVE_RUN = subprocess.run

def module(path):
    spec = importlib.util.spec_from_file_location('private_' + path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture
def integration(tmp_path, monkeypatch):
    previous_umask = os.umask(0o022)
    helper = module(ROOT / 'packaging/kiosk_confinement.py')
    for name in ('PAYLOAD', 'PAM_LOCAL', 'PAM_VENDOR'):
        path = tmp_path / name
        path.mkdir()
        monkeypatch.setattr(helper, name, path)
    monkeypatch.setattr(helper, 'STATE', tmp_path / 'state.json')
    monkeypatch.setattr(helper, 'ADMISSION_LOCK', tmp_path / 'admission.lock')
    monkeypatch.setattr(helper, 'ADMISSION_DISABLED', tmp_path / 'removing')
    monkeypatch.setattr(helper, 'LEGACY_LOGIN_LOCK', tmp_path / 'legacy-login.lock')
    monkeypatch.setattr(helper, 'PREPARATION_LOCK', tmp_path / 'preparation.lock')
    monkeypatch.setattr(helper, 'PREVIOUS_ACTIVATION', tmp_path / 'previous-activation.json')
    proc = tmp_path / 'proc'
    proc.mkdir()
    monkeypatch.setattr(helper, 'PROCESSES', proc)
    # Keep all mode, link and ancestor checks; the private fixture substitutes
    # only the root identity and its isolated filesystem's ancestor permissions.
    original = Path.lstat

    def metadata(path):
        info = original(path)
        if path == tmp_path or path in tmp_path.parents:
            mode = info.st_mode & ~0o022
        else:
            mode = info.st_mode
        return SimpleNamespace(st_uid=0, st_mode=mode, st_nlink=info.st_nlink)

    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    original_fstat = os.fstat

    def descriptor_metadata(fd):
        info = original_fstat(fd)
        return SimpleNamespace(st_uid=0, st_mode=info.st_mode, st_nlink=info.st_nlink,
                               st_dev=info.st_dev, st_ino=info.st_ino)

    monkeypatch.setattr(helper.os, 'fstat', descriptor_metadata)
    (helper.PAYLOAD / 'config.json').write_text('{"backend":"selinux"}')
    (helper.PAYLOAD / 'onpc-kiosk.cil').write_text('; private policy fixture\n')
    (helper.PAM_LOCAL / 'gdm-password').write_text('session required pam_unix.so\n')
    (helper.PAM_VENDOR / 'systemd-user').write_text('session required pam_systemd.so\n')
    commands = []

    def run(args):
        commands.append(args)
        return SimpleNamespace(stdout='')

    monkeypatch.setattr(helper, 'run', run)
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: (_ for _ in ()).throw(KeyError(name)))
    try:
        yield helper, commands
    finally:
        os.umask(previous_umask)


def test_install_verify_remove_preserves_vendor_file(integration):
    helper, commands = integration
    original = (helper.PAM_LOCAL / 'gdm-password').read_text()
    vendor = (helper.PAM_VENDOR / 'systemd-user').read_bytes()
    helper.install()
    helper.load()
    helper.verify_pam(helper.state())
    helper.install()
    helper.remove()
    helper.finish_remove()
    assert (helper.PAM_LOCAL / 'gdm-password').read_text() == original
    assert not (helper.PAM_LOCAL / 'systemd-user').exists()
    assert (helper.PAM_VENDOR / 'systemd-user').read_bytes() == vendor
    assert not helper.STATE.exists()


def test_later_standalone_purge_accepts_already_removed_state_directory(integration, monkeypatch):
    helper, _ = integration
    helper.install()
    helper.remove()
    helper.finish_remove()
    monkeypatch.setattr(helper, 'STATE', helper.STATE.parent / 'already-removed' / 'state.json')
    assert helper.state() is None
    helper.finish_remove()


def test_install_reports_nested_unknown_module_without_mutating_policy_or_pam(
        integration, monkeypatch, capsys):
    helper, commands = integration
    target = helper.PAM_LOCAL / 'gdm-password'
    target.write_text('@include common-session\n')
    (helper.PAM_LOCAL / 'common-session').write_text(
        'session required pam_unix.so\n'
        'session optional pam_unreviewed.so private-argument\n')
    before = target.read_bytes()
    monkeypatch.setattr(helper.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(helper.sys, 'argv', ['integration', 'install'])
    assert helper.main() == 1
    diagnostic = capsys.readouterr().err
    assert 'reason=unsupported-pam-session-module module=other' in diagnostic
    assert 'source=kiosk-confinement line=' in diagnostic
    assert 'preserving ownership records' in diagnostic
    assert 'pam_unreviewed' not in diagnostic
    assert 'private-argument' not in diagnostic
    assert target.read_bytes() == before
    assert not helper.STATE.exists()
    assert not any(command[:2] == ['/usr/sbin/semodule', '-i'] for command in commands)


@pytest.mark.parametrize('error, expected', [
    (ValueError('unsafe-confinement-path'), 'reason=unsafe-confinement-path'),
    (ValueError('unsupported-pam-session-module:pam_exec.so'),
     'reason=unsupported-pam-session-module module=pam-exec'),
    (ValueError('unsupported-pam-session-module:/home/private/module.so'),
     'reason=unsupported-pam-session-module module=other'),
    (ValueError('private exception text'), 'reason=invalid-data'),
    (FileNotFoundError(2, 'private exception text', '/home/private/file'), 'reason=os-error errno=2'),
    (PermissionError(13, 'private exception text', '/home/private/file'), 'reason=os-error errno=13'),
    (subprocess.CalledProcessError(7, ['/usr/sbin/apparmor_parser', '/home/private/file'],
                                  stderr='private exception text'),
     'reason=command-failed status=7 command=apparmor-parser'),
    (subprocess.TimeoutExpired(['/usr/sbin/semodule', '-i', '/home/private/file'], 60,
                               stderr='private exception text'),
     'reason=command-timeout command=semodule'),
    (subprocess.CalledProcessError(-9, ['/home/private/program']),
     'reason=command-failed status=-9 command=other'),
    (RuntimeError('private exception text'), 'reason=unexpected-error'),
])
def test_failure_diagnostics_classify_errors_without_private_values(error, expected, capsys):
    helper = module(ROOT / 'packaging/kiosk_confinement.py')
    helper.report_failure(error)
    diagnostic = capsys.readouterr().err
    assert expected in diagnostic
    assert 'private' not in diagnostic
    assert 'Traceback' not in diagnostic
    assert 'preserving ownership records' in diagnostic


@pytest.mark.parametrize('error, expected', [
    (ValueError('untrusted-path'), 'reason=untrusted-path'),
    (ValueError('missing-executable'), 'reason=missing-executable'),
    (ValueError('manager-generation-stale'), 'reason=stale-manager-reboot-required'),
    (ValueError('generation-limit-reboot-required'), 'reason=generation-limit-reboot-required'),
    (ValueError('private exception text'), 'reason=verification'),
    (ValueError(['private exception text']), 'reason=verification'),
    (PermissionError(13, 'private exception text', '/home/private/file'), 'reason=os-error errno=13'),
    (subprocess.CalledProcessError(7, ['/home/private/program'],
                                  stderr='private exception text'), 'reason=command-failed status=7'),
    (subprocess.TimeoutExpired(['/home/private/program'], 5,
                               stderr='private exception text'), 'reason=command-timeout'),
    (RuntimeError('private exception text'), 'reason=verification'),
])
def test_preparation_failure_diagnostics_exclude_private_exception_data(error, expected, capfd):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    helper.report_preparation_failure(error, role='/home/private/role')
    diagnostic = capfd.readouterr().err
    assert expected in diagnostic
    assert 'outcome=denied role=other stage=arguments' in diagnostic
    assert 'private' not in diagnostic and 'Traceback' not in diagnostic


def test_preparation_failure_logs_the_actual_stage_and_shipped_source_line(
        preserved_password_preparation, monkeypatch, capfd):
    helper = preserved_password_preparation.helper

    def refuse(config, records):
        raise ValueError('untrusted-path')

    monkeypatch.setattr(helper, 'directory_layout', refuse)
    monkeypatch.setattr(helper.sys, 'argv', ['preparation', 'manager'])
    assert helper.main() == 1
    diagnostic = capfd.readouterr().err
    assert 'preparation outcome=denied role=manager stage=directory-layout reason=untrusted-path' in diagnostic
    assert 'source=kiosk-confinement line=' in diagnostic
    assert 'Traceback' not in diagnostic
    assert (preserved_password_preparation.runtime / 'bindings').read_text() == 'previous bindings\n'


@pytest.mark.parametrize('denied', [False, True])
def test_preparation_diagnostic_output_failure_does_not_change_admission(denied):
    # A real broken stderr pipe also exercises interpreter shutdown: buffered
    # diagnostics can otherwise turn successful preparation into exit 120.
    source = '''
import importlib.util
import sys

spec = importlib.util.spec_from_file_location('preparation', sys.argv[1])
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
denied = sys.argv[2] == 'denied'

def prepare(role):
    assert role == 'manager'
    helper.preparation_log('directory-view outcome=masked reason=writable-sibling-directory count=1')
    if denied:
        raise ValueError('untrusted-path')

helper.prepare = prepare
sys.argv = ['preparation', 'manager']
sys.exit(helper.main())
'''
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    try:
        result = subprocess.run(
            [sys.executable, '-I', '-B', '-c', source,
             str(ROOT / 'tools/kiosk_confinement.py'), 'denied' if denied else 'allowed'],
            stdout=subprocess.PIPE, stderr=write_fd, text=True, timeout=5)
    finally:
        os.close(write_fd)
    assert result.returncode == (1 if denied else 0)
    assert result.stdout == ''


def test_removal_preflight_restores_recreated_lock_label_without_manufacturing_legacy_inodes(integration):
    helper, commands = integration
    helper.install()
    helper.ADMISSION_LOCK.unlink()
    commands.clear()
    helper.remove(check=True)
    assert commands == [['/usr/sbin/restorecon', str(helper.ADMISSION_LOCK)]]
    assert not helper.LEGACY_LOGIN_LOCK.exists()
    assert not helper.PREPARATION_LOCK.exists()


@pytest.mark.parametrize('exclusive', [False, True])
def test_policy_load_refuses_admission_or_lifecycle_writer_before_read_or_mutation(integration, monkeypatch, exclusive):
    helper, commands = integration
    helper.install()
    before = helper.STATE.read_bytes()
    commands.clear()
    with helper.admission_barrier(exclusive=exclusive):
        monkeypatch.setattr(helper, 'state', lambda: pytest.fail('state read crossed a lifecycle lease'))
        with pytest.raises(ValueError, match='kiosk-admissions-active'):
            helper.load()
    assert helper.STATE.read_bytes() == before
    assert commands == []


def test_policy_load_keeps_configuration_and_removal_excluded_through_attestation(integration, monkeypatch):
    helper, commands = integration
    helper.install()
    commands.clear()
    original = helper.atomic

    def write(path, contents, mode):
        if path == helper.STATE:
            for operation in (helper.install, helper.remove, helper.finish_remove, helper.load):
                with pytest.raises(ValueError, match='kiosk-admissions-active'):
                    operation()
        original(path, contents, mode)

    monkeypatch.setattr(helper, 'atomic', write)
    helper.ADMISSION_LOCK.unlink()
    helper.load()
    assert commands == [['/usr/sbin/semodule', '-i', str(helper.PAYLOAD / 'onpc-kiosk.cil')],
                        ['/usr/sbin/restorecon', str(helper.ADMISSION_LOCK)]]
    assert 'removing' not in helper.state()
    assert not helper.LEGACY_LOGIN_LOCK.exists()
    assert not helper.PREPARATION_LOCK.exists()


@pytest.mark.parametrize('prepared', [False, True])
def test_install_refuses_native_preparation_before_policy_or_record_mutation(integration, prepared):
    helper, commands = integration
    helper.install()
    before = helper.STATE.read_bytes()
    commands.clear()
    with helper.admission_barrier(exclusive=False):
        if prepared:
            helper.PREPARATION_LOCK.touch(mode=0o600)
            with helper.PREPARATION_LOCK.open('rb') as native:
                fcntl.flock(native, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with pytest.raises(ValueError, match='kiosk-admissions-active'):
                    helper.install()
        else:
            with pytest.raises(ValueError, match='kiosk-admissions-active'):
                helper.install()
            assert not helper.PREPARATION_LOCK.exists()
    assert helper.STATE.read_bytes() == before
    assert commands == []


def test_install_preserves_existing_admission_and_excludes_preparation_through_attestation(integration, monkeypatch):
    helper, _ = integration
    helper.install()
    helper.PREPARATION_LOCK.touch(mode=0o600)
    original = helper.atomic
    observed = []

    def write(path, contents, mode):
        if path == helper.STATE:
            with helper.PREPARATION_LOCK.open('rb') as native:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(native, fcntl.LOCK_EX | fcntl.LOCK_NB)
            observed.append(path)
        original(path, contents, mode)

    monkeypatch.setattr(helper, 'atomic', write)
    with helper.admission_barrier(exclusive=False):
        helper.install()
    assert observed
    helper.verify_policy(helper.state())


def test_install_refuses_disappearing_preparation_inode_without_recreating_it(integration, monkeypatch):
    helper, commands = integration
    helper.install()
    helper.PREPARATION_LOCK.touch(mode=0o600)
    before = helper.STATE.read_bytes()
    commands.clear()
    original = helper.admission_barrier

    def interrupted(**kwargs):
        assert kwargs == dict(exclusive=False, preparation=True)
        helper.PREPARATION_LOCK.unlink()
        return original(**kwargs)

    monkeypatch.setattr(helper, 'admission_barrier', interrupted)
    with pytest.raises(ValueError, match='missing-preparation-lock'):
        helper.install()
    assert not helper.PREPARATION_LOCK.exists()
    assert helper.STATE.read_bytes() == before
    assert commands == []


@pytest.mark.parametrize('check', [False, True])
@pytest.mark.parametrize('lock_name', ['ADMISSION_LOCK', 'LEGACY_LOGIN_LOCK', 'PREPARATION_LOCK'])
def test_remove_refuses_inflight_root_pam_lease_before_uid_scan_or_mutation(integration, monkeypatch, check, lock_name):
    helper, commands = integration
    helper.install()
    before = helper.STATE.read_bytes()
    commands.clear()
    monkeypatch.setattr(helper, 'check_remove', lambda saved: pytest.fail('UID scan crossed a PAM lease'))
    lock = getattr(helper, lock_name)
    lock.touch(mode=0o600, exist_ok=True)
    with lock.open('rb') as worker:
        fcntl.flock(worker, fcntl.LOCK_SH | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='kiosk-admissions-active'):
            helper.remove(check=check)
    assert helper.STATE.read_bytes() == before
    assert not helper.ADMISSION_DISABLED.exists()
    assert commands == []


def test_prelease_upgrade_receipt_requires_boot_retirement_and_survives_reconfigure(integration, monkeypatch):
    helper, commands = integration
    helper.install()
    saved = helper.state()
    saved.pop('admission_protocol')
    helper.atomic(helper.STATE, json.dumps(saved), 0o600)
    monkeypatch.setattr(helper, 'boot_id', lambda: 'previous-boot')
    helper.install()
    helper.install()
    assert helper.state()['prelease_upgrade_boot_id'] == 'previous-boot'
    before = helper.STATE.read_bytes()
    commands.clear()
    with pytest.raises(ValueError, match='legacy-pam-reboot-required'):
        helper.remove()
    assert helper.STATE.read_bytes() == before
    assert commands == []
    monkeypatch.setattr(helper, 'boot_id', lambda: 'current-boot')
    helper.remove()
    helper.finish_remove()
    assert not helper.STATE.exists()


def test_first_confinement_deployment_over_installed_package_records_prelease_boot(integration, monkeypatch):
    helper, _ = integration
    helper.PREVIOUS_ACTIVATION.write_text('{}\n')
    monkeypatch.setattr(helper, 'boot_id', lambda: 'previous-boot')
    helper.install()
    assert helper.state()['prelease_upgrade_boot_id'] == 'previous-boot'
    with pytest.raises(ValueError, match='legacy-pam-reboot-required'):
        helper.remove()


@pytest.mark.parametrize('witness,reason', [
    ('uid', 'kiosk-processes-active'), ('thread-uid', 'kiosk-processes-active'),
    ('audit-uid', 'kiosk-processes-active'), ('apparmor-current', 'kiosk-executors-active'),
    ('selinux-pending', 'kiosk-executors-active'), ('deleted-module', 'legacy-pam-reboot-required'),
    ('replaced-module', 'legacy-pam-reboot-required'), ('ordinary-current-module', None),
    ('ordinary-current-module-thread', None),
    ('btrfs-device-alias', None), ('mapped-device-mismatch', 'legacy-pam-reboot-required'),
    ('missing-mapping', 'legacy-pam-reboot-required'),
])
def test_removal_census_covers_root_executors_and_all_threads(integration, monkeypatch, tmp_path, witness, reason):
    helper, _ = integration
    helper.install()
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=12345))

    def thread(tid):
        target = helper.PROCESSES / '42' / 'task' / str(tid)
        (target / 'attr').mkdir(parents=True)
        (target / 'status').write_text('Uid:\t0\t0\t0\t0\n')
        (target / 'loginuid').write_text('4294967295\n')
        (target / 'maps').write_text('')
        (target / 'attr/current').write_text('system_u:system_r:xdm_t:s0\n')
        (target / 'attr/exec').write_text('')
        return target

    target = thread(42)
    if witness in ('uid', 'thread-uid'):
        target = thread(43) if witness == 'thread-uid' else target
        (target / 'status').write_text('Uid:\t0\t12345\t0\t0\n')
    elif witness == 'audit-uid':
        (target / 'loginuid').write_text('12345\n')
    elif witness == 'apparmor-current':
        (target / 'attr/current').write_text('onpc-kiosk-gate (enforce)\n')
    elif witness == 'selinux-pending':
        (target / 'attr/exec').write_text('system_u:system_r:onpc_kiosk_gate_t:s0\n')
    else:
        if witness == 'ordinary-current-module-thread':
            target = thread(43)
        library = tmp_path / 'pam_oh_no_parent_control.so'
        library.write_bytes(b'private mapped library identity')
        info = library.stat()
        deleted = ' (deleted)' if witness == 'deleted-module' else ''
        # Actual Fedora Btrfs maps report 00:22 while pathname/map_files stat
        # report subvolume 00:24. Textual maps device is not object identity.
        device = '00:22' if witness == 'btrfs-device-alias' else '00:24'
        (target / 'maps').write_text(f'1000-2000 r--p 00000000 {device} {info.st_ino} {library}{deleted}\n')
        # Real procfs has maps under task/TID, but map_files only at /proc/TID.
        # Use real private files/symlinks so a nonexistent task/map_files lookup
        # fails, rather than making the erroneous path work through a stat mock.
        mapped = helper.PROCESSES / target.name / 'map_files/1000-2000'
        mapped.parent.mkdir(parents=True)
        assert not (target / 'map_files').exists()
        original_mapping = tmp_path / 'old-mapped-module'
        original_mapping.write_bytes(b'old private inode')
        if witness != 'missing-mapping':
            mapped.symlink_to(original_mapping if witness == 'replaced-module' else library)
        if witness == 'mapped-device-mismatch':
            original_stat = Path.stat
            def metadata(path, *args, **kwargs):
                value = original_stat(path, *args, **kwargs)
                return (SimpleNamespace(st_dev=value.st_dev + 1, st_ino=value.st_ino)
                        if path == mapped else value)
            monkeypatch.setattr(helper.Path, 'stat', metadata)
    if reason:
        with pytest.raises(ValueError, match=reason):
            helper.remove(check=True)
    else:
        helper.remove(check=True)
    assert not helper.ADMISSION_DISABLED.exists()


def test_unreadable_root_module_mapping_refuses_removal(integration, monkeypatch, tmp_path):
    helper, _ = integration
    library = tmp_path / 'pam_oh_no_parent_control.so'
    library.write_bytes(b'private module')
    thread = helper.PROCESSES / '42/task/43'
    thread.mkdir(parents=True)
    (thread / 'maps').write_text(f'1000-2000 r--p 00000000 00:22 123 {library}\n')
    original = Path.stat
    def metadata(path, *args, **kwargs):
        if path == helper.PROCESSES / '43/map_files/1000-2000':
            raise PermissionError('private map_files inaccessible')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(helper.Path, 'stat', metadata)
    with pytest.raises(PermissionError, match='inaccessible'):
        helper.check_root_pam_generation(thread)


def test_root_module_identity_uses_real_linux_nonleader_map_files(integration, monkeypatch, tmp_path):
    helper, _ = integration
    library = tmp_path / 'pam_oh_no_parent_control.so'
    library.write_bytes(b'innocuous private mapped data' + b'\0' * 4096)
    reader, writer = os.pipe()
    child = None
    source = '''import mmap, os, sys, threading
with open(sys.argv[1], 'rb') as stream:
    mapping = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
    def hold():
        os.write(int(sys.argv[2]), (str(threading.get_native_id()) + '\\n').encode())
        threading.Event().wait(10)
    thread = threading.Thread(target=hold)
    thread.start()
    thread.join(11)
'''
    try:
        child = subprocess.Popen([sys.executable, '-I', '-c', source, str(library), str(writer)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, pass_fds=(writer,))
        assert select.select([reader], [], [], 5)[0], 'owned mapping child did not become ready'
        tid = os.read(reader, 64).decode().strip()
        assert tid.isdecimal() and int(tid) != child.pid
        thread = Path('/proc') / str(child.pid) / 'task' / tid
        assert not (thread / 'map_files').exists()
        mappings = [line.split(maxsplit=5) for line in (thread / 'maps').read_text().splitlines()
                    if line.endswith(' ' + str(library))]
        assert len(mappings) == 1
        actual = Path('/proc') / tid / 'map_files' / mappings[0][0]
        assert actual.is_symlink()
        monkeypatch.setattr(helper, 'PROCESSES', Path('/proc'))
        # Resolving map_files can require CAP_CHECKPOINT_RESTORE/SYS_ADMIN even
        # for our child. Do not replace the kernel API with a positive double.
        try:
            helper.check_root_pam_generation(thread)
        except PermissionError as error:
            # An unprivileged host can prove the real lookup and fail-closed
            # outcome, while guest-root acceptance owns positive target stat.
            assert error.filename == str(actual)
        assert child.poll() is None
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
        os.close(reader)
        os.close(writer)


@pytest.mark.parametrize('fail_relabel', [False, True])
def test_selinux_removal_relabels_same_leased_inode_after_unload_with_durable_denials(
        integration, monkeypatch, fail_relabel):
    helper, _ = integration
    helper.install()
    inode = helper.ADMISSION_LOCK.stat().st_ino
    calls = []
    def run(args):
        calls.append(args)
        if args[:2] in (['/usr/sbin/semodule', '-r'], ['/usr/sbin/restorecon', '-F']):
            assert helper.state()['removing'] and helper.ADMISSION_DISABLED.exists()
            assert all((helper.PAM_LOCAL / name).read_text() == helper.removal_pam(record)
                       for name, record in helper.state()['pam'].items())
            assert helper.ADMISSION_LOCK.stat().st_ino == inode
            with helper.ADMISSION_LOCK.open('rb') as lease:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(lease, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if args[:2] == ['/usr/sbin/restorecon', '-F']:
            assert calls[-2] == ['/usr/sbin/semodule', '-r', 'onpc-kiosk']
            if fail_relabel:
                raise subprocess.CalledProcessError(1, args)
        return SimpleNamespace(stdout='onpc-kiosk 1.0\n')
    monkeypatch.setattr(helper, 'run', run)
    if fail_relabel:
        with pytest.raises(subprocess.CalledProcessError):
            helper.remove()
    else:
        helper.remove()
    assert helper.ADMISSION_LOCK.stat().st_ino == inode
    assert helper.ADMISSION_DISABLED.exists() and helper.state()['removing']
    assert calls[-1] == ['/usr/sbin/restorecon', '-F', str(helper.ADMISSION_LOCK)]
    if fail_relabel:
        calls.clear()
        unlink = helper.unlink_synced
        def recovered_unlink(path):
            if path == helper.ADMISSION_DISABLED:
                assert calls[0][:2] == ['/usr/sbin/semodule', '-i']
                helper.verify_pam(helper.state())
            return unlink(path)
        monkeypatch.setattr(helper, 'unlink_synced', recovered_unlink)
        helper.install()
        assert not helper.ADMISSION_DISABLED.exists()


@pytest.mark.parametrize('backend', ['selinux', 'apparmor'])
def test_remove_keeps_standalone_denials_until_account_deleted_and_abort_rearms_policy(integration, monkeypatch, backend):
    helper, commands = integration
    (helper.PAYLOAD / 'config.json').write_text(json.dumps({'backend': backend}))
    (helper.PAYLOAD / 'onpc-kiosk.apparmor').write_text('# private policy\n')
    original_read = Path.read_text

    def read(path, *args, **kwargs):
        if str(path) == '/sys/kernel/security/apparmor/profiles':
            return ''
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(helper.Path, 'read_text', read)
    helper.install()
    helper.remove()
    saved = helper.state()
    assert saved['removing'] is True
    assert helper.ADMISSION_DISABLED.read_text() == 'removing\n'
    for name, record in saved['pam'].items():
        source = (helper.PAM_LOCAL / name).read_text()
        assert source == helper.removal_pam(record)
        assert 'pam_oh_no_parent_control' not in source
        assert 'account requisite pam_succeed_if.so' in source
        assert 'session requisite pam_succeed_if.so' in source
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=12345))
    with pytest.raises(ValueError, match='kiosk-account-still-present'):
        helper.finish_remove()
    commands.clear()
    helper.install()
    helper.verify_pam(helper.state())
    assert not helper.ADMISSION_DISABLED.exists()
    assert not helper.state().get('removing')
    assert commands[0][:2] == (['/usr/sbin/semodule', '-i'] if backend == 'selinux'
                                else ['/usr/sbin/apparmor_parser', '-r'])


@pytest.mark.parametrize('failed_name', ['gdm-password', 'systemd-user'])
def test_interrupted_removal_pam_publication_retains_policy_and_recovers(integration, monkeypatch, failed_name):
    helper, commands = integration
    helper.install()
    atomic = helper.atomic

    def fail(path, *args):
        if path == helper.PAM_LOCAL / failed_name:
            raise OSError('injected write interruption')
        return atomic(path, *args)

    monkeypatch.setattr(helper, 'atomic', fail)
    commands.clear()
    with pytest.raises(OSError, match='injected'):
        helper.remove()
    assert helper.ADMISSION_DISABLED.exists()
    assert helper.state()['removing']
    assert commands == []  # no unload before both durable denial stacks
    monkeypatch.setattr(helper, 'atomic', atomic)
    helper.install()
    helper.verify_pam(helper.state())
    assert not helper.ADMISSION_DISABLED.exists()


def test_failed_policy_unload_retains_denials_and_owned_retry(integration, monkeypatch):
    helper, _ = integration
    helper.install()
    calls = []

    def unload(args):
        calls.append(args)
        if args[:2] == ['/usr/sbin/semodule', '-r']:
            raise subprocess.CalledProcessError(1, args)
        return SimpleNamespace(stdout='onpc-kiosk 1.0\n')

    monkeypatch.setattr(helper, 'run', unload)
    with pytest.raises(subprocess.CalledProcessError):
        helper.remove()
    assert helper.ADMISSION_DISABLED.exists()
    for name, record in helper.state()['pam'].items():
        assert (helper.PAM_LOCAL / name).read_text() == helper.removal_pam(record)
    monkeypatch.setattr(helper, 'run', lambda args: SimpleNamespace(stdout=''))
    helper.remove()
    helper.finish_remove()
    assert not helper.STATE.exists()


def test_finalization_preserves_foreign_pam_and_durable_denial(integration):
    helper, _ = integration
    helper.install()
    helper.remove()
    target = helper.PAM_LOCAL / 'gdm-password'
    target.write_text('# foreign change\n' + target.read_text())
    with pytest.raises(ValueError, match='modified-pam'):
        helper.finish_remove()
    assert target.read_text().startswith('# foreign change\n')
    assert helper.STATE.exists()
    assert helper.ADMISSION_DISABLED.exists()


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_postrm_embedded_finalizer_runs_after_payload_erasure(integration, distribution, tmp_path):
    helper, _ = integration
    helper.install()
    helper.remove()
    renderer = module(ROOT / 'packaging/render_lifecycle.py')
    postrm = renderer.render(ROOT, distribution, 'postrm')
    assert postrm.index('    remove_package_created_kiosk\n') < postrm.index(
        "/usr/bin/python3 -I - <<'ONPC_CONFINEMENT_FINISH_REMOVE'")
    embedded = renderer.embedded_confinement_finish_remove(ROOT)
    source = embedded.split('\n', 1)[1].rsplit('\nONPC_CONFINEMENT_FINISH_REMOVE', 1)[0]
    # Execute the embedded program itself with only private paths and fixture
    # ownership. No installed product helper, NSS account or kernel MAC calls.
    for name in ('STATE', 'PAYLOAD', 'ADMISSION_LOCK', 'ADMISSION_DISABLED', 'LEGACY_LOGIN_LOCK',
                 'PREPARATION_LOCK', 'PROCESSES', 'PREVIOUS_ACTIVATION', 'PAM_LOCAL', 'PAM_VENDOR'):
        original = getattr(module(ROOT / 'packaging/kiosk_confinement.py'), name)
        source = source.replace(f'{name} = Path({str(original)!r})',
                                f'{name} = Path({str(getattr(helper, name))!r})')
    source = source.replace("_CONFINEMENT_FILESYSTEM_ROOT = Path('/')",
                            f'_CONFINEMENT_FILESYSTEM_ROOT = Path({str(tmp_path)!r})')
    source = source.replace('_CONFINEMENT_OWNER_UID = 0',
                            f'_CONFINEMENT_OWNER_UID = {os.getuid()}')
    source = source.replace("pwd.getpwnam('oh-no-parent-control')",
                            "(_ for _ in ()).throw(KeyError('private-kiosk'))")
    # Removing policy bytes demonstrates the finalizer needs only its durable
    # record and standalone deny stacks after the package files have gone.
    (helper.PAYLOAD / 'onpc-kiosk.cil').unlink()
    result = subprocess.run([sys.executable, '-I', '-'], input=source,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert not helper.STATE.exists()
    assert not helper.ADMISSION_DISABLED.exists()
    assert (helper.PAM_LOCAL / 'gdm-password').read_text() == 'session required pam_unix.so\n'
    assert not (helper.PAM_LOCAL / 'systemd-user').exists()


@pytest.mark.parametrize('name', ['gdm-password', 'systemd-user'])
def test_missing_final_gate_denies_steady_state_but_can_repair_owned_original(integration, name):
    helper, commands = integration
    helper.install()
    saved = helper.state()
    before = saved['pam'][name]['before']
    target = helper.PAM_LOCAL / name
    if before is None:
        target.unlink()
    else:
        target.write_text(before)
    commands.clear()
    with pytest.raises(ValueError, match='modified-pam'):
        helper.load()
    assert commands == []
    helper.install()
    helper.verify_pam(helper.state())


def test_foreign_pam_edit_is_preserved(integration):
    helper, _ = integration
    helper.install()
    target = helper.PAM_LOCAL / 'gdm-password'
    target.write_text('session optional foreign.so\n')
    for operation in (helper.install, helper.load, helper.remove):
        with pytest.raises(ValueError, match='modified-pam'):
            operation()
    assert target.read_text() == 'session optional foreign.so\n'
    assert helper.STATE.exists()


def test_nonregular_or_linked_pam_is_refused_before_read(integration):
    helper, _ = integration
    target = helper.PAM_LOCAL / 'gdm-password'
    target.unlink()
    os.mkfifo(target, 0o600)
    with pytest.raises(ValueError, match='unsafe-confinement-file'):
        helper.install()
    target.unlink()
    target.write_text('session required pam_unix.so\n')
    os.link(target, helper.PAM_LOCAL / 'unexpected-link')
    with pytest.raises(ValueError, match='unsafe-confinement-file'):
        helper.install()


def test_vendor_update_requires_reconfiguration(integration):
    helper, _ = integration
    helper.install()
    vendor = helper.PAM_VENDOR / 'systemd-user'
    vendor.write_text(vendor.read_text() + '# security_update.so\nsession required pam_limits.so\n')
    with pytest.raises(ValueError, match='vendor-pam-changed'):
        helper.load()
    helper.install()
    helper.load()
    assert (helper.PAM_LOCAL / 'systemd-user').read_text() == (
        helper.MANAGER_CREDENTIALS + helper.PREFIX + vendor.read_text() + helper.BLOCK)


def test_failed_policy_update_cannot_attest_to_new_rules_with_old_domain_names(integration, monkeypatch):
    helper, _ = integration
    helper.install()
    helper.verify_policy(helper.state())
    (helper.PAYLOAD / 'onpc-kiosk.cil').write_text('; changed rules, same domain names\n')
    with pytest.raises(ValueError, match='policy-load-incomplete'):
        helper.verify_policy(helper.state())
    run = helper.run
    def fail(args):
        if args[:2] == ['/usr/sbin/semodule', '-i']:
            raise subprocess.CalledProcessError(1, args)
        return run(args)
    monkeypatch.setattr(helper, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        helper.install()
    with pytest.raises(ValueError, match='policy-load-incomplete'):
        helper.verify_policy(helper.state())
    monkeypatch.setattr(helper, 'run', run)
    helper.install()
    helper.verify_policy(helper.state())


@pytest.mark.parametrize('changed', ['config.json', 'onpc-kiosk.cil', 'legacy-record'])
def test_boot_load_refuses_unconfigured_payload_pair_without_reattesting(integration, changed):
    helper, commands = integration
    helper.install()
    if changed == 'legacy-record':
        saved = helper.state()
        saved.pop('loaded_config_sha256')
        helper.atomic(helper.STATE, json.dumps(saved), 0o600)
    else:
        path = helper.PAYLOAD / changed
        path.write_bytes(path.read_bytes() + b'\n')
    before = helper.STATE.read_bytes()
    commands.clear()
    with pytest.raises(ValueError, match='policy-load-incomplete'):
        helper.verify_policy(helper.state())
    with pytest.raises(ValueError, match='policy-load-incomplete'):
        helper.load()
    assert helper.STATE.read_bytes() == before
    assert commands == []
    helper.install()
    helper.load()
    assert helper.verify_policy(helper.state()) == helper.policy_payload(helper.state())[1]


@pytest.mark.parametrize('changed', ['config.json', 'onpc-kiosk.cil'])
def test_payload_pair_mutation_during_load_preserves_previous_attestation(integration, monkeypatch, changed):
    helper, _ = integration
    helper.install()
    before = helper.STATE.read_bytes()
    run = helper.run

    def mutate(arguments):
        result = run(arguments)
        if arguments[:2] == ['/usr/sbin/semodule', '-i']:
            path = helper.PAYLOAD / changed
            path.write_bytes(path.read_bytes() + b'\n')
        return result

    monkeypatch.setattr(helper, 'run', mutate)
    with pytest.raises(ValueError, match='policy-changed-during-load'):
        helper.load()
    assert helper.STATE.read_bytes() == before
    with pytest.raises(ValueError, match='policy-load-incomplete'):
        helper.verify_policy(helper.state())


def test_payload_pair_attestation_survives_identical_byte_replacement(integration):
    helper, _ = integration
    helper.install()
    expected = helper.verify_policy(helper.state())
    for name in ('config.json', 'onpc-kiosk.cil'):
        target = helper.PAYLOAD / name
        replacement = helper.PAYLOAD / (name + '.replacement')
        replacement.write_bytes(target.read_bytes())
        replacement.replace(target)
    helper.load()
    assert helper.verify_policy(helper.state()) == expected


@pytest.mark.parametrize('changed', ['config.json', 'onpc-kiosk.cil', 'identical-bytes'])
def test_boot_load_binds_initial_reload_pair_to_the_verified_snapshot(integration, monkeypatch, changed):
    helper, commands = integration
    helper.install()
    before = helper.STATE.read_bytes()
    commands.clear()
    verify = helper.verify_policy

    def replace_after_verification(saved):
        digests = verify(saved)
        for name in ('config.json', 'onpc-kiosk.cil') if changed == 'identical-bytes' else (changed,):
            path = helper.PAYLOAD / name
            replacement = helper.PAYLOAD / (name + '.replacement')
            contents = path.read_bytes()
            replacement.write_bytes(contents if changed == 'identical-bytes' else contents + b'\n')
            replacement.replace(path)
        return digests

    monkeypatch.setattr(helper, 'verify_policy', replace_after_verification)
    if changed == 'identical-bytes':
        helper.load()
        assert commands == [['/usr/sbin/semodule', '-i', str(helper.PAYLOAD / 'onpc-kiosk.cil')],
                            ['/usr/sbin/restorecon', str(helper.ADMISSION_LOCK)]]
        verify(helper.state())
    else:
        with pytest.raises(ValueError, match='policy-load-incomplete'):
            helper.load()
        assert commands == []
    assert helper.STATE.read_bytes() == before


@pytest.mark.parametrize('suffix', ['.dpkg-dist', '.rpmnew'])
def test_pending_distribution_pam_update_is_not_silently_ignored(integration, suffix):
    helper, _ = integration
    helper.install()
    active = helper.PAM_LOCAL / 'gdm-password'
    original = active.read_text()
    pending = active.with_name(active.name + suffix)
    pending.write_text('session required updated-distro-policy.so\n')
    for action in (helper.load, helper.install):
        with pytest.raises(ValueError, match='pending-distribution-pam-update'):
            action()
    assert active.read_text() == original
    assert pending.read_text() == 'session required updated-distro-policy.so\n'


def test_vendor_refresh_resumes_after_interrupted_pam_write(integration, monkeypatch):
    helper, _ = integration
    helper.install()
    vendor = helper.PAM_VENDOR / 'systemd-user'
    vendor.write_text(vendor.read_text() + '# updated.so\nsession required pam_limits.so\n')
    atomic = helper.atomic

    def fail(path, text, mode):
        if path == helper.PAM_LOCAL / 'systemd-user':
            raise OSError('simulated interruption')
        atomic(path, text, mode)

    monkeypatch.setattr(helper, 'atomic', fail)
    with pytest.raises(OSError):
        helper.install()
    monkeypatch.setattr(helper, 'atomic', atomic)
    helper.install()
    helper.load()
    assert 'previous_pam' not in helper.state()


def test_multiple_interrupted_vendor_updates_keep_actual_owned_generation(integration, monkeypatch):
    helper, _ = integration
    helper.install()
    vendor = helper.PAM_VENDOR / 'systemd-user'
    original = (helper.PAM_LOCAL / 'systemd-user').read_bytes()
    atomic = helper.atomic
    def fail(path, text, mode):
        if path == helper.PAM_LOCAL / 'systemd-user':
            raise OSError('simulated interruption')
        atomic(path, text, mode)
    monkeypatch.setattr(helper, 'atomic', fail)
    for revision in ('second', 'third'):
        vendor.write_text(f'# {revision}.so\nsession required pam_limits.so\n')
        with pytest.raises(OSError):
            helper.install()
        assert (helper.PAM_LOCAL / 'systemd-user').read_bytes() == original
    monkeypatch.setattr(helper, 'atomic', atomic)
    helper.install()
    helper.load()
    assert 'third.so' in (helper.PAM_LOCAL / 'systemd-user').read_text()


@pytest.mark.parametrize('control', ['sufficient', '[success=done default=ignore]',
                                     '[success=2 default=ignore]', 'unknown'])
def test_session_short_circuit_cannot_skip_gate(integration, control):
    helper, _ = integration
    (helper.PAM_LOCAL / 'common-session').write_text(f'session {control} pam_permit.so\n')
    with pytest.raises(ValueError, match='pam-can-skip'):
        helper.validate_stack('@include common-session\n')


@pytest.mark.parametrize('directive', ['@include\t', '@include  ', '@include\\\n\t'])
@pytest.mark.parametrize('rule', ['session optional pam_gnome_keyring.so auto_start\n',
                                  'session required pam_namespace.so\n',
                                  'session optional pam_exec.so /usr/bin/true\n'])
def test_every_supported_include_spelling_audits_pre_gate_callbacks(integration, directive, rule):
    helper, _ = integration
    (helper.PAM_LOCAL / 'nested').write_text(rule)
    with pytest.raises(ValueError, match='unsupported-pam'):
        helper.rendered(directive + 'nested\n')


@pytest.mark.parametrize('directive', ['@include\t', '@include\\\n\t'])
def test_include_whitespace_cannot_hide_early_success_or_manager_credentials(integration, directive):
    helper, _ = integration
    nested = helper.PAM_LOCAL / 'nested'
    nested.write_text('session sufficient pam_permit.so\n')
    with pytest.raises(ValueError, match='pam-can-skip'):
        helper.rendered(directive + 'nested\n')
    nested.write_text('auth optional pam_unix.so\n')
    with pytest.raises(ValueError, match='unsupported-manager-pam-credentials'):
        helper.rendered(directive + 'nested\n', service='systemd-user')


@pytest.mark.parametrize('source', ['@INCLUDE nested\n', '@include\n',
                                   '@include nested extra\n', 'session\x00 required pam_unix.so\n',
                                   'session required pam_unix.so \\\n'])
def test_unsupported_pam_syntax_is_refused_consistently(integration, source):
    helper, _ = integration
    for audit in (helper.session_rules, helper.guarded_sessions, helper.audit_manager_credentials):
        with pytest.raises(ValueError, match='pam-'):
            audit(source)


def test_continued_vendor_callback_is_guarded_without_rewriting_its_bytes(integration):
    helper, _ = integration
    source = '# vendor comment\nsession optional \\\n\tpam_gnome_keyring.so auto_start\n'
    assert helper.rendered(source) == (helper.PREFIX + '# vendor comment\n' +
                                      helper.KEYRING_GUARD + source.split('\n', 1)[1] + helper.BLOCK)
    helper.guarded_sessions(helper.rendered(source), verify=True)


def test_dangling_local_include_never_uses_vendor_fallback(integration):
    helper, _ = integration
    (helper.PAM_LOCAL / 'nested').symlink_to(helper.PAM_LOCAL / 'missing')
    (helper.PAM_VENDOR / 'nested').write_text('session required pam_unix.so\n')
    with pytest.raises(FileNotFoundError):
        helper.rendered('@include nested\n')


def test_normal_pam_jump_may_land_on_gate_and_substack_is_scoped(integration):
    helper, _ = integration
    helper.validate_stack('session [default=1] pam_permit.so\nsession requisite pam_deny.so\n')
    helper.validate_stack('session substack system-auth\n')


@pytest.mark.parametrize('directive', ['@include ', 'session include ', 'session substack '])
def test_lxc_cgroup_sessions_install_reload_and_restore_without_changing_vendor_rules(
        integration, directive):
    helper, commands = integration
    rule = 'session optional pam_cgfs.so -c freezer,memory,name=systemd\n'
    shared = ('session [default=1] pam_permit.so\n'
              'session requisite pam_deny.so\n'
              'session required pam_unix.so\n' + rule)
    sources = {
        helper.PAM_LOCAL / 'common-session': shared,
        helper.PAM_LOCAL / 'common-session-noninteractive': shared,
        helper.PAM_LOCAL / 'gdm-password': (
            directive + 'common-session\n'
            'session optional pam_gnome_keyring.so auto_start\n'),
        helper.PAM_VENDOR / 'systemd-user': directive + 'common-session-noninteractive\n',
    }
    for path, source in sources.items():
        path.write_text(source)
    helper.install()
    first = helper.STATE.read_bytes()
    helper.load()
    helper.install()
    assert helper.STATE.read_bytes() == first
    helper.verify_pam(helper.state())
    for name in ('gdm-password', 'systemd-user'):
        rendered = (helper.PAM_LOCAL / name).read_text()
        assert rendered.endswith(helper.BLOCK)
        assert directive + ('common-session\n' if name == 'gdm-password'
                            else 'common-session-noninteractive\n') in rendered
    for path in (helper.PAM_LOCAL / 'common-session',
                 helper.PAM_LOCAL / 'common-session-noninteractive',
                 helper.PAM_VENDOR / 'systemd-user'):
        assert path.read_text() == sources[path]
    assert any(command[:2] == ['/usr/sbin/semodule', '-i'] for command in commands)
    helper.remove()
    helper.finish_remove()
    for path, source in sources.items():
        assert path.read_text() == source
    assert not (helper.PAM_LOCAL / 'systemd-user').exists()
    assert not helper.STATE.exists()


@pytest.mark.parametrize('control', ['sufficient', '[success=done default=ignore]'])
def test_lxc_module_cannot_short_circuit_final_confinement_gate(integration, control):
    helper, commands = integration
    (helper.PAM_LOCAL / 'common-session').write_text(f'session {control} pam_cgfs.so\n')
    (helper.PAM_LOCAL / 'gdm-password').write_text('@include common-session\n')
    with pytest.raises(ValueError, match='pam-can-skip-confinement'):
        helper.install()
    assert not helper.STATE.exists()
    assert not any(command[:2] == ['/usr/sbin/semodule', '-i'] for command in commands)


def test_nested_include_change_cannot_introduce_short_circuit(integration):
    helper, _ = integration
    (helper.PAM_LOCAL / 'common-session').write_text('session required pam_unix.so\n')
    (helper.PAM_LOCAL / 'gdm-password').write_text('@include common-session\n')
    helper.install()
    (helper.PAM_LOCAL / 'common-session').write_text('session sufficient pam_permit.so\n')
    with pytest.raises(ValueError, match='pam-can-skip'):
        helper.load()


def test_keyring_guard_preserves_vendor_callback_for_other_users(integration):
    helper, _ = integration
    source = ('auth optional pam_gnome_keyring.so\n'
              'session optional pam_gnome_keyring.so auto_start\n')
    target = helper.PAM_LOCAL / 'gdm-password'
    target.write_text(source)
    helper.install()
    assert helper.KEYRING_GUARD + source.splitlines(keepends=True)[1] in target.read_text()
    helper.load()
    helper.remove()
    helper.finish_remove()
    assert target.read_text() == source


@pytest.mark.parametrize('control', ['optional', 'required', 'requisite'])
def test_namespace_open_and_close_are_guarded_without_changing_vendor_options(integration, control):
    helper, _ = integration
    # Even active init/cleanup configuration is unreachable: skip the entire
    # module on both session operations, preserving every option for others.
    source = f'session {control} pam_namespace.so unmount_on_close use_current_context\n'
    target = helper.PAM_LOCAL / 'gdm-password'
    target.write_text(source)
    helper.install()
    assert helper.NAMESPACE_GUARD + source in target.read_text()
    helper.load()
    helper.remove()
    helper.finish_remove()
    assert target.read_text() == source


def test_namespace_guard_cannot_be_skipped_or_nested(integration):
    helper, _ = integration
    with pytest.raises(ValueError, match='pam-jump-crosses-namespace-guard'):
        helper.rendered('session [success=1 default=ignore] pam_permit.so\n'
                        'session required pam_namespace.so\n')
    (helper.PAM_LOCAL / 'nested').write_text('session required pam_namespace.so\n')
    with pytest.raises(ValueError, match='unsupported-pam-namespace-placement'):
        helper.rendered('session include nested\n')


@pytest.mark.parametrize('rule', ['auth optional pam_exec.so /usr/bin/true\n',
                                  '-AUTH optional pam_unix.so\n',
                                  'auth include system-auth\n'])
def test_user_manager_credential_callbacks_refused_even_in_include(integration, rule):
    helper, _ = integration
    (helper.PAM_LOCAL / 'nested').write_text(rule)
    (helper.PAM_VENDOR / 'systemd-user').write_text('@include nested\n')
    with pytest.raises(ValueError, match='unsupported-(manager-pam-credentials|pam-spelling)'):
        helper.install()
    assert not helper.STATE.exists()


def test_user_manager_new_included_credentials_refused_at_admission(integration):
    helper, _ = integration
    nested = helper.PAM_LOCAL / 'nested'
    nested.write_text('account required pam_unix.so\n')
    (helper.PAM_VENDOR / 'systemd-user').write_text('@include nested\n')
    helper.install()
    nested.write_text('auth optional pam_unix.so\n')
    with pytest.raises(ValueError, match='unsupported-manager-pam-credentials'):
        helper.verify_pam(helper.state())


@pytest.mark.parametrize('control', ['include', 'substack'])
@pytest.mark.parametrize('module_name', ['pam_gnome_keyring.so auto_start',
                                        'pam_exec.so /usr/bin/true', 'unknown.so'])
def test_pre_gate_children_in_nested_stack_are_refused(integration, control, module_name):
    helper, _ = integration
    (helper.PAM_LOCAL / 'nested').write_text(f'session optional {module_name}\n')
    (helper.PAM_LOCAL / 'gdm-password').write_text(f'session {control} nested\n')
    with pytest.raises(ValueError, match='unsupported-pam'):
        helper.install()
    assert not helper.STATE.exists()


def test_guard_insertion_refuses_crossing_jump_in_included_stack(integration):
    helper, _ = integration
    (helper.PAM_LOCAL / 'nested').write_text('session [success=2 default=ignore] pam_permit.so\n')
    source = ('@include nested\nsession optional pam_gnome_keyring.so auto_start\n'
              'session required pam_unix.so\n')
    with pytest.raises(ValueError, match='pam-jump-crosses-keyring-guard'):
        helper.rendered(source)


@pytest.mark.parametrize('source', ['SESSION sufficient pam_permit.so\n',
    '-SESSION optional pam_gnome_keyring.so auto_start\n',
    'session OPTIONAL pam_gnome_keyring.so auto_start\n'])
def test_noncanonical_pam_case_is_refused(integration, source):
    helper, _ = integration
    with pytest.raises(ValueError, match='unsupported-pam-spelling'):
        helper.rendered(source)


def test_nested_update_cannot_jump_over_existing_keyring_guard(integration):
    helper, _ = integration
    nested = helper.PAM_LOCAL / 'nested'
    nested.write_text('session required pam_permit.so\n')
    (helper.PAM_LOCAL / 'gdm-password').write_text(
        '@include nested\nsession optional pam_gnome_keyring.so auto_start\n'
        'session required pam_unix.so\n')
    helper.install()
    nested.write_text('session [success=1 default=ignore] pam_permit.so\n')
    with pytest.raises(ValueError, match='pam-jump-crosses-keyring-guard'):
        helper.load()


def test_pam_include_cycles_refused_and_trusted_distro_symlinks_resolved(integration):
    helper, _ = integration
    target = helper.PAM_LOCAL / 'loop'
    target.write_text('@include loop\n')
    with pytest.raises(ValueError, match='invalid-pam-include'):
        helper.validate_stack('@include loop\n')
    target.unlink()
    target.symlink_to(helper.PAM_VENDOR / 'systemd-user')
    helper.validate_stack('@include loop\n')
    (helper.PAM_VENDOR / 'systemd-user').chmod(0o666)
    with pytest.raises(ValueError, match='unsafe'):
        helper.validate_stack('@include loop\n')


@pytest.fixture
def census_model(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tests/integration'))
    return module(ROOT / 'tests/integration/system_kiosk_confinement.py')


@pytest.mark.parametrize('fault', [False, True])
def test_appended_probe_restores_bytes_inode_mode_and_nanosecond_times(
        census_model, tmp_path, fault):
    path = tmp_path / 'package-input'
    path.write_bytes(b'original package bytes')
    path.chmod(0o640)
    os.utime(path, ns=(1_600_000_000_123_456_789, 1_600_000_001_987_654_321))
    before = path.stat()

    def exercise():
        with census_model.appended_probe(path, b'\nowned fault\n'):
            assert path.read_bytes() == b'original package bytes\nowned fault\n'
            if fault:
                raise RuntimeError('probe failed')

    if fault:
        with pytest.raises(RuntimeError, match='probe failed'):
            exercise()
    else:
        exercise()
    after = path.stat()
    for field in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid',
                  'st_size', 'st_atime_ns', 'st_mtime_ns'):
        assert getattr(after, field) == getattr(before, field)
    assert path.read_bytes() == b'original package bytes'


def test_appended_probe_refuses_symlink_without_changing_target(census_model, tmp_path):
    target = tmp_path / 'foreign'
    target.write_bytes(b'preserved bytes')
    path = tmp_path / 'package-input'
    path.symlink_to(target)
    with pytest.raises(OSError):
        with census_model.appended_probe(path, b'\nfault\n'):
            pytest.fail('symlink admitted')
    assert path.is_symlink() and target.read_bytes() == b'preserved bytes'


@pytest.fixture
def admission_model(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tests/integration'))
    return module(ROOT / 'tests/integration/system_kiosk_admission.py')


def test_restart_admission_gates_use_controls_and_exact_denials_without_routing_mutation(
        admission_model, monkeypatch):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'enable_diagnostics', Mock())
    identities = {
        helper.USERS['kiosk']: SimpleNamespace(pw_uid=41001, pw_shell='/usr/sbin/nologin'),
        helper.USERS['ordinary']: SimpleNamespace(pw_uid=41002),
    }
    monkeypatch.setattr(helper.pwd, 'getpwnam', identities.__getitem__)
    probe = Mock()
    mutation = Mock(side_effect=AssertionError('retained routing must stay unchanged'))
    monkeypatch.setattr(helper, 'probe', probe)
    monkeypatch.setattr(helper, 'set_routing', mutation)
    record = Mock()
    helper.verify_gates(record)
    assert [call.args for call in probe.call_args_list] == [
        ('gdm-password', 'ordinary', 0, 'gdm-password.ordinary-before', record),
        ('login', 'ordinary', 0, 'login.ordinary-before', record),
        ('sshd', 'ordinary', 0, 'sshd.ordinary-before', record),
        ('gdm-password', 'kiosk', 0, 'dedicated-before', record),
        ('login', 'kiosk', 6, 'login.denied', record),
        ('login', 'ordinary', 0, 'login.ordinary-after', record),
        ('sshd', 'kiosk', 6, 'sshd.denied', record),
        ('sshd', 'ordinary', 0, 'sshd.ordinary-after', record),
    ]
    mutation.assert_not_called()


def test_restart_admission_guest_refusal_precedes_identity_and_pam_workers(
        admission_model, monkeypatch):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock(side_effect=helper.guest.GuestError('identity')))
    identity, probe = Mock(), Mock()
    monkeypatch.setattr(helper.pwd, 'getpwnam', identity)
    monkeypatch.setattr(helper, 'probe', probe)
    with pytest.raises(helper.guest.GuestError, match='identity'):
        helper.verify_gates(Mock())
    identity.assert_not_called()
    probe.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'worker'])
def test_fedora_kiosk_account_probe_uses_real_gdm_domain_and_removes_owned_fixture(
        admission_model, tmp_path, monkeypatch, fault):
    import system_kiosk_confinement as confinement

    helper = admission_model
    guard = Mock()
    monkeypatch.setattr(helper.guest, 'guard', guard)
    monkeypatch.setattr(helper.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(helper.guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(confinement.shutil, 'copyfile',
                        lambda source, target: target.write_bytes(b'private interpreter fixture'))
    label = Mock()
    monkeypatch.setattr(helper.guest, 'run', label)

    def worker(argv, **options):
        assert argv[:2] == ['/usr/bin/runcon', 'system_u:system_r:xdm_t:s0']
        caller = Path(argv[2])
        assert caller.is_relative_to(tmp_path) and caller.stat().st_mode & 0o777 == 0o700
        assert label.call_args.args[0] == ['/usr/bin/chcon', '-t', 'xdm_exec_t', str(caller)]
        assert argv[3:] == ['-B', str(Path(helper.__file__).resolve()),
                           'pam-account', 'gdm-password', 'kiosk']
        assert options == {'timeout': 45, 'merge_stderr': False}
        if fault:
            raise helper.guest.GuestError('worker-failed')
        return b'{"account":0,"end":0}'

    monkeypatch.setattr(helper.guest.commands, 'run', worker)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='worker-failed'):
            helper.probe('gdm-password', 'kiosk', 0, 'dedicated', Mock())
    else:
        helper.probe('gdm-password', 'kiosk', 0, 'dedicated', Mock())
    guard.assert_called_once_with(expected_selinux='Enforcing')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('service,role', [('gdm-password', 'ordinary'),
                                         ('login', 'kiosk'), ('sshd', 'kiosk')])
def test_other_fedora_account_probes_preserve_the_original_caller_command(
        admission_model, monkeypatch, service, role):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'package_path', lambda: Path('package.rpm'))
    command = Mock(return_value=b'{"account":0,"end":0}')
    monkeypatch.setattr(helper.guest.commands, 'run', command)
    helper.probe(service, role, 0, 'control', Mock())
    command.assert_called_once_with([
        '/usr/bin/python3', '-B', str(Path(helper.__file__).resolve()),
        'pam-account', service, role], timeout=45, merge_stderr=False)


def test_fedora_caller_fixture_guard_refusal_precedes_any_fixture_write(
        census_model, tmp_path, monkeypatch):
    helper = census_model
    monkeypatch.setattr(helper.guest, 'guard', Mock(side_effect=helper.guest.GuestError('identity')))
    copy = Mock()
    monkeypatch.setattr(helper.shutil, 'copyfile', copy)
    with pytest.raises(helper.guest.GuestError, match='identity'):
        with helper.pam_caller_command(tmp_path, 'gdm-password'):
            pytest.fail('refused fixture admitted a worker')
    copy.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_fedora_kiosk_account_worker_refuses_an_unconfined_caller_before_pam(
        admission_model, monkeypatch):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(Path, 'read_text', lambda _: 'unconfined_u:unconfined_r:unconfined_t:s0\0')
    identity, library = Mock(), Mock()
    monkeypatch.setattr(helper.pwd, 'getpwnam', identity)
    monkeypatch.setattr(helper.ctypes, 'CDLL', library)
    with pytest.raises(helper.guest.GuestError, match='caller-context'):
        helper.pam_account('gdm-password', 'kiosk')
    identity.assert_not_called()
    library.assert_not_called()


@pytest.mark.parametrize('result', [b'{"account": 9, "end": 0}',
                                  b'{"account": 6, "end": 4}',
                                  b'{"account": true, "end": 0}', b'not-json'])
def test_installed_admission_never_counts_unavailable_or_malformed_worker_as_denial(
        admission_model, monkeypatch, result):
    helper = admission_model
    command = Mock(return_value=result)
    monkeypatch.setattr(helper.guest.commands, 'run', command)
    with pytest.raises(helper.guest.GuestError, match='kiosk-admission:'):
        helper.probe('sshd', 'kiosk', 6, 'ssh-denied', Mock())
    assert command.call_args.kwargs['timeout'] == 45
    assert command.call_args.args[0][-3:] == ['pam-account', 'sshd', 'kiosk']


@pytest.mark.parametrize('status', [0, 6])
@pytest.mark.parametrize('role', ['kiosk', 'ordinary', 'other'])
def test_installed_admission_uses_real_service_name_and_ends_denied_transactions(
        admission_model, monkeypatch, status, role):
    from unittest.mock import MagicMock
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    service = Mock()
    service.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
    directory = MagicMock()
    directory.__truediv__.return_value = service
    monkeypatch.setattr(helper, 'Path', Mock(return_value=directory))
    monkeypatch.setattr(helper.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(
        pw_uid=41001, pw_name=helper.USERS[role])))
    pam = Mock()
    pam.pam_start.return_value = 0
    pam.pam_acct_mgmt.return_value = status
    pam.pam_end.return_value = 0
    monkeypatch.setattr(helper.ctypes, 'CDLL', Mock(return_value=pam))
    assert helper.pam_account('sshd', role) == {'account': status, 'end': 0}
    helper.pwd.getpwnam.assert_called_once_with(helper.USERS[role])
    assert pam.pam_start.call_args.args[:2] == (b'sshd', helper.USERS[role].encode())
    pam.pam_start_confdir.assert_not_called()
    pam.pam_open_session.assert_not_called()
    assert pam.pam_end.call_args.args[1] == status


@pytest.mark.parametrize('fault', ['positive', 'denial-worker', 'unrepaired'])
def test_installed_admission_requires_positive_and_restores_mutation_on_failure(
        admission_model, monkeypatch, fault):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'enable_diagnostics', Mock())
    accounts = {
        helper.USERS['kiosk']: SimpleNamespace(pw_uid=41001, pw_name=helper.USERS['kiosk'],
                                               pw_shell='/usr/sbin/nologin'),
        helper.USERS['ordinary']: SimpleNamespace(pw_uid=41002),
    }
    monkeypatch.setattr(helper.pwd, 'getpwnam', accounts.__getitem__)
    values = {41001: helper.DEDICATED, 41002: ('ordinary', 'wayland')}
    monkeypatch.setattr(helper, 'routing', values.__getitem__)
    writes = []

    def set_routing(uid, value):
        writes.append(value)
        values[uid] = value

    monkeypatch.setattr(helper, 'set_routing', set_routing)
    monkeypatch.setattr(helper.guest, 'run', Mock(return_value='usepam yes\npamservicename sshd'))
    monkeypatch.setattr(helper.guest, 'package_path', Mock(return_value=Path('package.deb')))
    monkeypatch.setattr(helper.Path, 'is_file', Mock(return_value=True))
    stages = []

    def probe(service, role, expected, stage, record):
        stages.append((service, role, expected, stage))
        if fault == 'positive' and stage == 'dedicated-before':
            raise helper.guest.GuestError('positive-failed')
        if stage == 'alternate-session.denied' and fault == 'denial-worker':
            raise helper.guest.GuestError('worker-failed')

    monkeypatch.setattr(helper, 'probe', probe)
    with pytest.raises(helper.guest.GuestError):
        helper.verify(Mock())
    assert values == {41001: helper.DEDICATED, 41002: ('ordinary', 'wayland')}
    if fault == 'positive':
        assert not writes
        assert not any(expected == 6 for _, _, expected, _ in stages)
    else:
        assert stages[:4] == [(service, 'ordinary', 0, service + '.ordinary-before')
                              for service in helper.SERVICES] + [
                                  ('gdm-password', 'kiosk', 0, 'dedicated-before')]
        assert writes == [('ubuntu', 'wayland'), helper.DEDICATED]
        assert not any(stage.endswith('.retry') for _, _, _, stage in stages)


@pytest.mark.parametrize('service,context,label', [
    ('gdm-password', 'system_u:system_r:xdm_t:s0', 'xdm_exec_t'),
    ('systemd-user', 'system_u:system_r:init_t:s0', 'init_exec_t'),
])
@pytest.mark.parametrize('fault', [None, 'command', 'missing-result', 'empty-result'])
def test_final_pam_probe_enters_real_vendor_caller_without_policy_changes(
        census_model, tmp_path, monkeypatch, service, context, label, fault):
    from unittest.mock import Mock
    helper = census_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    original_read = Path.read_text
    original_is_file = Path.is_file
    def read(path, *args, **kwargs):
        if str(path) == '/usr/share/oh-no-parent-control/confinement/config.json':
            return '{"backend":"selinux"}'
        if str(path) == '/proc/self/attr/current':
            return 'unconfined_u:unconfined_r:unconfined_t:s0\0'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(Path, 'is_file', lambda path: (
        str(path) == '/usr/lib64/security/pam_oh_no_parent_control.so'
        if path.name == 'pam_oh_no_parent_control.so' else original_is_file(path)))
    monkeypatch.setattr(helper.shutil, 'copyfile',
                        lambda source, target: target.write_bytes(b'private interpreter fixture'))
    run = Mock()
    monkeypatch.setattr(helper.guest, 'run', run)
    commands = Mock()
    monkeypatch.setattr(helper.guest, 'commands', commands)
    def enter(argv, **kwargs):
        assert argv[:2] == ['/usr/bin/runcon', context]
        caller = Path(argv[2])
        assert caller.is_relative_to(tmp_path) and caller.stat().st_mode & 0o777 == 0o700
        assert run.call_args.args[0] == ['/usr/bin/chcon', '-t', label, str(caller)]
        request = json.loads(argv[-1])
        result_fd = request.pop('result_fd')
        assert request == {'command': ['/usr/bin/true'], 'directory': str(tmp_path),
                           'service': service, 'armed': True, 'fd_mode': 'file',
                           'expected_selinux': 'Enforcing'}
        assert kwargs == {'timeout': 90, 'merge_stderr': False, 'pass_fds': (result_fd,)}
        assert (tmp_path / service).read_text() == (
            'session required /usr/lib64/security/pam_oh_no_parent_control.so kiosk-confinement\n')
        if fault == 'command':
            raise helper.guest.GuestError('command:failed:runcon')
        if fault == 'empty-result':
            return b''
        os.write(result_fd, b'help output' if fault else
                 b'onpc-first-exec:{"status":126,"data":"7b7d"}')
        return b''
    commands.run.side_effect = enter
    if fault:
        with pytest.raises(helper.guest.GuestError):
            helper.first_exec(SimpleNamespace(), tmp_path, ['/usr/bin/true'],
                              service=service, fd_mode='file')
    else:
        assert helper.first_exec(SimpleNamespace(), tmp_path, ['/usr/bin/true'],
                                 service=service, fd_mode='file') == (126, b'{}')
    assert list(tmp_path.iterdir()) == [tmp_path / service]


def test_first_exec_pidfd_failure_reaps_its_own_child_and_closes_pipe(census_model, monkeypatch):
    import signal

    helper = census_model
    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(read_fd)
        os.close(write_fd)
        signal.pause()
        os._exit(0)
    os.close(write_fd)
    try:
        def unavailable(pid):
            assert pid == child
            raise OSError('pidfd unavailable')
        monkeypatch.setattr(helper.os, 'pidfd_open', unavailable)
        with pytest.raises(OSError, match='pidfd unavailable'):
            helper.wait_first_exec(child, read_fd, armed=True)
        with pytest.raises(ChildProcessError):
            os.waitpid(child, os.WNOHANG)
        with pytest.raises(OSError):
            os.fstat(read_fd)
    finally:
        # Only this test's unreaped fork child can still own this PID.
        try:
            waited, _ = os.waitpid(child, os.WNOHANG)
        except ChildProcessError:
            waited = child
        if waited == 0:
            os.kill(child, signal.SIGKILL)
            os.waitpid(child, 0)
        try:
            os.close(read_fd)
        except OSError:
            pass


def test_final_pam_probe_refuses_unknown_caller(census_model):
    helper = census_model
    with pytest.raises(helper.guest.GuestError, match='unsupported-pam-caller'):
        helper.caller_identity('sshd')


@pytest.mark.parametrize('fault', [None, 'close', 'label'])
def test_pam_lifecycle_teardown_retains_denials_after_real_callback_order(census_model, monkeypatch, fault):
    helper = census_model
    calls = []
    def callback(name, result=0):
        def run(handle, flags):
            calls.append((name, handle, flags))
            return result
        return run
    pam = SimpleNamespace(pam_close_session=callback('close', 1 if fault == 'close' else 0),
                          pam_setcred=callback('credentials', 7), pam_end=callback('end'))
    expected = 'system_u:system_r:onpc_kiosk_manager_pam_t:s0'
    monkeypatch.setattr(helper, 'lifecycle_label', lambda backend: 'init_t' if fault == 'label' else expected)
    denials = []
    monkeypatch.setattr(helper, 'lifecycle_denials', lambda: denials.append(len(calls)))
    if fault == 'label':
        with pytest.raises(helper.guest.GuestError, match='kiosk-lifecycle:'):
            helper.lifecycle_teardown(pam, 'handle', 'selinux', expected)
        assert not any(call[0] == 'end' for call in calls)
    else:
        stages = helper.lifecycle_teardown(pam, 'handle', 'selinux', expected)
        assert calls == [('close', 'handle', 0), ('credentials', 'handle', 4),
                         ('end', 'handle', 0x40000000)]
        assert denials == [0, 1, 2, 3]
        assert stages[1]['pam_status'] == (1 if fault == 'close' else 0)
        assert stages[2] == {'stage': 'delete-credentials', 'pam_status': 7}


@pytest.mark.parametrize('data', [b'', b'x' * 4097])
def test_pam_lifecycle_event_refuses_missing_and_oversize_protocol(census_model, data):
    helper = census_model
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, data)
        os.close(write_fd)
        write_fd = None
        with pytest.raises(helper.guest.GuestError, match='kiosk-lifecycle:event-'):
            helper.lifecycle_event(read_fd)
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)


def test_pam_lifecycle_denial_workers_reap_and_validate_exec_errno(census_model, monkeypatch):
    helper = census_model
    def denied(*args):
        raise PermissionError(13, 'private exec denial')
    monkeypatch.setattr(helper.os, 'execve', denied)
    helper.lifecycle_denials()


def test_pam_lifecycle_generation_diagnostic_records_bounded_system_path_differences(
        census_model, tmp_path, monkeypatch):
    import system_kiosk_accounts as accounts

    helper = census_model
    runtime = tmp_path / 'runtime'
    runtime.mkdir(mode=0o700)
    before, after = 'a' * 64, 'b' * 64
    manifests = {
        before: {'records': [{'path': '/usr/bin/required', 'sha256': 'before'}],
                 'preserved': [{'path': '/usr/lib/polkit-1/helper'}],
                 'layout': [{'path': '/usr/lib/removed-' + str(index), 'kind': 'file'}
                            for index in range(10)] +
                           [{'path': '/usr/lib/changed-' + str(index), 'kind': 'file'}
                            for index in range(10)]},
        after: {'records': [{'path': '/usr/bin/required', 'sha256': 'after'}],
                'preserved': [],
                'layout': [{'path': '/usr/lib/added-' + str(index), 'kind': 'directory'}
                           for index in range(10)] +
                          [{'path': '/usr/lib/changed-' + str(index), 'kind': 'directory'}
                           for index in range(10)]},
    }
    for generation, manifest in manifests.items():
        directory = runtime / generation
        directory.mkdir()
        (directory / 'records.json').write_text(json.dumps(manifest))

    def trusted(path, **options):
        return path if path.is_relative_to(runtime) else (
            runtime / path.relative_to('/run/oh-no-parent-control-confinement'))

    monkeypatch.setattr(helper.runpy, 'run_path', Mock(return_value={'trusted': trusted}))
    reader = Mock(side_effect=lambda path, **options: path.read_bytes())
    monkeypatch.setattr(accounts, 'owned_bytes', reader)
    events = {}
    helper.lifecycle_generation_diagnostic(before + '\n', after + '\n', events.__setitem__)
    assert events['onpc.kiosk.pam-lifecycle.manager-generation'] == before
    assert events['onpc.kiosk.pam-lifecycle.helper-generation'] == after
    result = json.loads(events['onpc.kiosk.pam-lifecycle.generation-diagnostic'])
    assert result['status'] == 'compared'
    assert result['records']['changed'] == {'count': 1, 'paths': ['/usr/bin/required']}
    assert result['preserved']['removed'] == {'count': 1, 'paths': ['/usr/lib/polkit-1/helper']}
    for change in ('added', 'removed', 'changed'):
        assert result['layout'][change]['count'] == 10
        assert len(result['layout'][change]['paths']) == 8
        assert all(path.startswith('/usr/') for path in result['layout'][change]['paths'])
    assert all(call.kwargs == {'private': True} for call in reader.call_args_list)


@pytest.mark.parametrize('fault', [None, 'waiting-label', 'finished', 'credential-status',
                                  'establish-status', 'invalid-generation', 'diagnostic-read'])
def test_pam_lifecycle_observer_pins_and_reaps_owned_executor_and_orphan(
        census_model, tmp_path, monkeypatch, fault):
    helper = census_model
    observer = os.getpid()
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: observer)
    # This existing plain-stack fixture declares no optional LXC callback.
    monkeypatch.setattr(helper, 'optional_cgfs_session', lambda backend: False)
    original_read = Path.read_text
    expected = 'onpc-kiosk-manager (enforce)'
    def read(path, *args, **kwargs):
        if path.name == 'current' and 'attr' in path.parts:
            return 'unconfined' if fault == 'waiting-label' else expected
        if path.name == 'generation':
            if fault in ('invalid-generation', 'diagnostic-read'):
                if str(observer) in path.parts:
                    return 'a' * 64 + '\n'
                return '../outside-runtime\n' if fault == 'invalid-generation' else 'b' * 64 + '\n'
            return 'private generation'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(helper.shutil, 'copyfile', lambda source, target: target.write_bytes(b'private executor'))
    diagnostic_source = Mock(side_effect=OSError('private diagnostic read failure'))
    if fault in ('invalid-generation', 'diagnostic-read'):
        monkeypatch.setattr(helper.runpy, 'run_path', diagnostic_source)
    # Keep the real observer/forks, PIDFDs, subreaper, pipe protocol, identity
    # checks and cleanup. The fixture replaces only the vendor/PAM executor.
    def executor(program, arguments, environment):
        request = json.loads(arguments[-1])
        child = os.fork()
        if child == 0:
            os.close(request['executor_release'])
            try:
                os.write(request['events'], (json.dumps({'phase': 'ready', 'pid': os.getpid(),
                    'parent': os.getppid()}) + '\n').encode())
                if os.read(request['helper_release'], 1) != b'T':
                    os._exit(1)
                stages = [{'stage': stage, 'pam_status': None if index == 0 else
                           7 if fault == 'credential-status' and index == 2 else 0}
                          for index, stage in enumerate(('parent-exited', 'close-session',
                                                        'delete-credentials', 'end'))]
                result = {'phase': 'finished', 'stages': stages,
                          'establish_status': 7 if fault == 'establish-status' else 0}
                if fault == 'finished':
                    result['stages'] = []
                os.write(request['events'], (json.dumps(result) + '\n').encode())
                os._exit(0)
            except BaseException:
                os._exit(124)
        os.close(request['helper_release'])
        os._exit(0 if os.read(request['executor_release'], 1) == b'E' else 1)
    monkeypatch.setattr(helper.os, 'execve', executor)
    events = []
    account = SimpleNamespace(pw_uid=os.getuid())
    if fault:
        category = ('kiosk-lifecycle:waiting-generation' if fault in (
            'invalid-generation', 'diagnostic-read') else 'kiosk-lifecycle:')
        with pytest.raises(helper.guest.GuestError, match=category):
            helper.verify_pam_lifecycle(account, 'private-unit', 'apparmor', tmp_path,
                                       lambda *event: events.append(event))
    else:
        helper.verify_pam_lifecycle(account, 'private-unit', 'apparmor', tmp_path,
                                   lambda *event: events.append(event))
        assert ('onpc.kiosk.pam-lifecycle.establish-credentials-status', 0) in events
        assert events[-1] == ('onpc.kiosk.pam-lifecycle.post-parent-close-setcred-end-denials', True)
    if fault in ('credential-status', 'establish-status'):
        # Boundary evidence is retained, while a failed delete callback still
        # refuses completed teardown qualification.
        assert events[-1] == ('onpc.kiosk.pam-lifecycle.post-parent-close-setcred-end-denials', True)
    if fault in ('invalid-generation', 'diagnostic-read'):
        assert events[-1] == ('onpc.kiosk.pam-lifecycle.generation-diagnostic',
                              '{"status":"unavailable"}')
        assert diagnostic_source.call_count == (fault == 'diagnostic-read')


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('permissive', [False, True])
def test_waiting_census_requires_enforcing_policy_without_a_password_helper(
        census_model, monkeypatch, backend, permissive):
    helper = census_model
    config = {'backend': backend}
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(pw_uid=1002)))
    monkeypatch.setattr(helper.Path, 'read_text', Mock(return_value=json.dumps(config)))
    failure = 'selinux-domain-not-enforcing' if backend == 'selinux' else 'apparmor-not-enforcing'
    enforcing = Mock(side_effect=ValueError(failure) if permissive else None)
    load = Mock(return_value={'enforcing': enforcing})
    monkeypatch.setattr(helper.runpy, 'run_path', load)
    manager = Mock(return_value=42)
    monkeypatch.setattr(helper, 'manager_pid', manager)
    opened = Mock(return_value=43)
    closed = Mock()
    monkeypatch.setattr(helper.os, 'pidfd_open', opened)
    monkeypatch.setattr(helper.os, 'close', closed)
    processes = Mock(return_value={'backend': backend})
    monkeypatch.setattr(helper, 'census_processes', processes)
    if permissive:
        with pytest.raises(ValueError, match=failure):
            helper.census()
        manager.assert_not_called()
        opened.assert_not_called()
        processes.assert_not_called()
        closed.assert_not_called()
    else:
        assert helper.census() == {'backend': backend}
        processes.assert_called_once()
        closed.assert_called_once_with(43)
    load.assert_called_once_with('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    enforcing.assert_called_once_with(config)


def test_census_stat_parser_handles_parentheses_in_comm(census_model, tmp_path):
    helper = census_model
    fields = ['S', '42'] + ['0'] * 17 + ['123']
    (tmp_path / 'stat').write_text('43 ((sd-pam)) ' + ' '.join(fields))
    (tmp_path / 'status').write_text('PPid:\t42\nUid:\t1002\t1002\t1002\t1002\n')
    assert helper.process_identity(tmp_path) == ('123', 42, ('1002',) * 4)


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'unconfined', 'old-pam-domain', 'process-replaced',
                                    'manager-replaced', 'root-leader-kiosk-thread', 'other-process-changed'])
def test_census_filters_other_users_but_checks_every_kiosk_process(
        census_model, tmp_path, monkeypatch, backend, fault):
    from types import SimpleNamespace
    helper = census_model
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    marker = 'root/usr/share/oh-no-parent-control/confinement/generation'
    roles = ['manager', 'app', 'service', 'wellbeing', 'pipewire', 'manager-pam']
    for pid, role in [(1, None), *enumerate(roles, 42)]:
        process = tmp_path / str(pid)
        process.mkdir()
        uid = '0' if role is None else '1002'
        fields = ['S', '1'] + ['0'] * 17 + [str(pid * 100)]
        (process / 'stat').write_text(f'{pid} (fixture) ' + ' '.join(fields))
        (process / 'status').write_text('PPid:\t1\nUid:\t' + '\t'.join([uid] * 4) + '\n')
        (process / 'ns').mkdir()
        (process / 'ns/mnt').symlink_to('mnt:[host]' if role is None else 'mnt:[private]')
        thread = process / 'task' / str(pid)
        thread.mkdir(parents=True)
        for name in ('stat', 'status', 'ns', 'root'):
            (thread / name).symlink_to(process / name)
        if role is None:
            if fault == 'root-leader-kiosk-thread':
                sibling = process / 'task/2'
                sibling.mkdir()
                (sibling / 'stat').symlink_to(process / 'stat')
                (sibling / 'status').write_text('PPid:\t1\nUid:\t1002\t1002\t1002\t1002\n')
            continue  # No readable root/labels: these must never be requested.
        (process / marker).parent.mkdir(parents=True)
        (process / marker).write_text('fixture generation')
        (process / 'cgroup').write_text('0::/user.slice/user-1002.slice/user@1002.service/init.scope')
        name = 'onpc-kiosk-' + role if backend == 'apparmor' else 'onpc_kiosk_' + role.replace('-', '_') + '_t'
        label = name + ' (enforce)' if backend == 'apparmor' else f'system_u:system_r:{name}:s0'
        if fault == 'unconfined' and role == 'pipewire':
            label = 'unconfined'
        if fault == 'old-pam-domain' and role == 'manager-pam':
            label = 'unconfined' if backend == 'apparmor' else 'system_u:system_r:init_t:s0'
        attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
        for target in (attribute, f'task/{pid}/{attribute}'):
            (process / target).parent.mkdir(parents=True)
            (process / target).write_text(label)
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda pid: pid)
    monkeypatch.setattr(helper.os, 'close', lambda fd: None)
    monkeypatch.setattr(helper, 'exited', lambda fd: False)
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: 99 if fault == 'manager-replaced' else 42)
    identity = helper.process_identity
    reads = {}
    def read_identity(path):
        value = identity(path)
        reads[path] = reads.get(path, 0) + 1
        changed = ((fault == 'process-replaced' and path.name == '43') or
                   (fault == 'other-process-changed' and path.name == '1'))
        return ('changed', *value[1:]) if changed and reads[path] > 1 else value
    monkeypatch.setattr(helper, 'process_identity', read_identity)
    def check():
        return helper.census_processes(SimpleNamespace(pw_uid=1002),
            {'apparmor_profiles': ['onpc-kiosk-' + role for role in roles], 'domains': roles},
            backend, tmp_path / '42', 42, 'user@1002.service', required_roles=roles)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-census:'):
            check()
    else:
        result = check()
        assert result['confined_thread_roles'] == {
            ('onpc-kiosk-' + role if backend == 'apparmor' else
             'onpc_kiosk_' + role.replace('-', '_') + '_t'): 1 for role in roles}


@pytest.fixture
def password_helper_census(census_model, tmp_path, monkeypatch):
    helper = census_model
    proc = tmp_path / 'proc'
    proc.mkdir()
    monkeypatch.setattr(helper, 'PROC', proc)
    generation = 'a' * 64 + '\n'
    marker = 'usr/share/oh-no-parent-control/confinement/generation'
    vendor_path = '/usr/lib/polkit-1/polkit-agent-helper-1'
    parent_path = '/usr/libexec/polkit-gnome-authentication-agent-1'
    expected = dict(path=vendor_path, mode=0o4755,
                    label='system_u:object_r:policykit_auth_exec_t:s0')
    config = {'backend': 'selinux', 'domains': ['manager', 'polkit'],
              'preserved_executables': [expected],
              'executables': [{'role': 'polkit', 'paths': [parent_path]}]}
    root = tmp_path / 'private-root'
    (root / marker).parent.mkdir(parents=True)
    (root / marker).write_text(generation)
    pinned = root / vendor_path.lstrip('/')
    pinned.parent.mkdir(parents=True)
    pinned.write_bytes(b'\x7fELFprivate vendor helper')
    pinned.chmod(0o4755)
    parent_executable = root / parent_path.lstrip('/')
    parent_executable.parent.mkdir(parents=True)
    parent_executable.write_bytes(b'\x7fELFprivate polkit agent')
    for pid, ppid, role, credentials in (
            (1, 0, None, ('0',) * 4),
            (42, 1, 'onpc_kiosk_manager_t', ('1002',) * 4),
            (43, 42, 'onpc_kiosk_polkit_t', ('1002',) * 4),
            (44, 43, 'policykit_auth_t', ('1002', '0', '0', '0'))):
        process = proc / str(pid)
        for tid in (pid, pid + 1000):
            thread = process / 'task' / str(tid)
            thread.mkdir(parents=True)
            fields = ['S', str(ppid)] + ['0'] * 17 + [str(tid * 100)]
            (thread / 'stat').write_text(f'{tid} (private helper) ' + ' '.join(fields))
            (thread / 'status').write_text('PPid:\t' + str(ppid) + '\nUid:\t' +
                                         '\t'.join(credentials) + '\n')
            (thread / 'ns').mkdir()
            (thread / 'ns/mnt').symlink_to('mnt:[host]' if pid == 1 else 'mnt:[private]')
            if role is not None:
                (thread / 'attr').mkdir()
                (thread / 'attr/current').write_text(f'system_u:system_r:{role}:s0')
                (thread / 'root').symlink_to(root)
            if pid == 44:
                (thread / 'exe').symlink_to(pinned)
                (thread / 'mountinfo').write_text(
                    f'25 24 0:1 / {vendor_path} ro,relatime - ext4 /dev/private ro\n')
        for name in ('stat', 'status', 'ns', 'attr', 'root'):
            (process / name).symlink_to(process / 'task' / str(pid) / name)
    manager, parent, process = (proc / str(pid) for pid in (42, 43, 44))
    (manager / 'mountinfo').write_text(
        f'25 24 0:1 / {vendor_path} ro,relatime - ext4 /dev/private ro\n')
    (parent / 'exe').symlink_to(parent_executable)
    manifest = tmp_path / 'records.json'
    manifest.write_text(json.dumps({'preserved': [dict(expected, uid=0, gid=0,
        sha256=helper.hashlib.sha256(pinned.read_bytes()).hexdigest())]}))
    manifest_path = Path('/run/oh-no-parent-control-confinement') / generation.strip() / 'records.json'
    original_read, original_fstat = Path.read_text, os.fstat
    monkeypatch.setattr(helper.Path, 'read_text', lambda path, *args, **kwargs:
                        original_read(manifest if path == manifest_path else path, *args, **kwargs))
    def descriptor_metadata(fd):
        info = original_fstat(fd)
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        return SimpleNamespace(**dict(values, st_uid=0, st_gid=0))
    monkeypatch.setattr(helper.os, 'fstat', descriptor_metadata)
    monkeypatch.setattr(helper.os, 'listxattr', lambda fd: [])
    monkeypatch.setattr(helper.os, 'getxattr', lambda fd, name: expected['label'].encode() + b'\0')
    opened, closed, enforcement = [], [], []
    def enforce(value):
        assert value is config
        enforcement.append(value)
    def preparation(path):
        assert path == '/usr/libexec/oh-no-parent-control-kiosk-confinement'
        return {'enforcing': enforce}
    monkeypatch.setattr(helper.runpy, 'run_path', preparation)
    def acquire(pid):
        opened.append(pid)
        return pid
    monkeypatch.setattr(helper.os, 'pidfd_open', acquire)
    monkeypatch.setattr(helper.os, 'close', closed.append)
    monkeypatch.setattr(helper, 'exited', lambda fd: False)
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: 42)
    return SimpleNamespace(helper=helper, config=config, generation=generation, manager=manager,
        parent=parent, process=process, pinned=pinned, parent_executable=parent_executable,
        manifest=manifest, opened=opened, closed=closed, enforcement=enforcement,
        account=SimpleNamespace(pw_uid=1002))


@pytest.mark.parametrize('fault', [
    None, 'inventory', 'generation-format', 'credentials', 'thread-parent', 'thread-label',
    'host-namespace', 'other-private-namespace', 'thread-generation', 'empty-threads',
    'parent-label', 'parent-credentials', 'parent-namespace', 'parent-generation', 'parent-executable',
    'executable-mode', 'executable-owner', 'executable-group', 'executable-type',
    'executable-hardlink', 'executable-capability', 'executable-label', 'executable-format',
    'record-hash', 'record-mode', 'helper-inode', 'visible-helper-inode', 'visible-inode-replaced',
    'missing-mount', 'writable-mount', 'duplicate-mount', 'manager-writable-mount',
    'parent-exited', 'parent-replaced', 'parent-thread-replaced', 'parent-task-added',
    'parent-label-changed', 'helper-label-changed', 'helper-namespace-changed', 'helper-generation-changed',
])
def test_password_helper_census_requires_exact_live_helper_parent_and_private_file(
        password_helper_census, monkeypatch, tmp_path, fault):
    model = password_helper_census
    helper, parent, process = model.helper, model.parent, model.process
    thread, parent_thread = process / 'task/1044', parent / 'task/1043'
    generation = model.generation
    if fault == 'inventory':
        model.config['preserved_executables'][0]['path'] = '/usr/bin/untrusted-helper'
    elif fault == 'generation-format':
        generation = 'unmeasured-generation\n'
    elif fault in ('credentials', 'thread-parent', 'parent-credentials'):
        target = parent_thread if fault == 'parent-credentials' else thread
        credentials = ('1002',) * 4 if fault == 'credentials' else ('0',) * 4 if fault == 'parent-credentials' else ('1002', '0', '0', '0')
        (target / 'status').write_text('PPid:\t' + ('999' if fault == 'thread-parent' else '42' if fault == 'parent-credentials' else '43') +
                                      '\nUid:\t' + '\t'.join(credentials) + '\n')
    elif fault in ('thread-label', 'parent-label'):
        target = parent_thread if fault == 'parent-label' else thread
        (target / 'attr/current').write_text('system_u:system_r:init_t:s0')
    elif fault in ('host-namespace', 'other-private-namespace', 'parent-namespace'):
        target = parent_thread if fault == 'parent-namespace' else thread
        (target / 'ns/mnt').unlink()
        (target / 'ns/mnt').symlink_to('mnt:[host]' if fault == 'host-namespace' else 'mnt:[foreign-private]')
    elif fault in ('thread-generation', 'parent-generation'):
        target = parent_thread if fault == 'parent-generation' else thread
        (target / 'root').unlink()
        marker = tmp_path / 'foreign-root/usr/share/oh-no-parent-control/confinement/generation'
        marker.parent.mkdir(parents=True)
        marker.write_text('b' * 64 + '\n')
        (target / 'root').symlink_to(tmp_path / 'foreign-root')
    elif fault == 'visible-helper-inode':
        (thread / 'root').unlink()
        root = tmp_path / 'foreign-root'
        marker = root / 'usr/share/oh-no-parent-control/confinement/generation'
        marker.parent.mkdir(parents=True)
        marker.write_text(generation)
        substitute = root / 'usr/lib/polkit-1/polkit-agent-helper-1'
        substitute.parent.mkdir(parents=True)
        substitute.write_bytes(model.pinned.read_bytes())
        (thread / 'root').symlink_to(root)
    elif fault in ('parent-executable', 'helper-inode'):
        substitute = tmp_path / 'foreign-executable'
        substitute.write_bytes(b'\x7fELFprivate substitute')
        target = parent if fault == 'parent-executable' else thread
        (target / 'exe').unlink()
        (target / 'exe').symlink_to(substitute)
    elif fault == 'executable-mode':
        model.pinned.chmod(0o755)
    elif fault in ('executable-owner', 'executable-group', 'executable-type'):
        original = helper.os.fstat
        field, value = (('st_mode', stat.S_IFDIR | 0o4755) if fault == 'executable-type' else
                        ('st_uid' if fault == 'executable-owner' else 'st_gid', 12345))
        monkeypatch.setattr(helper.os, 'fstat', lambda fd:
                            SimpleNamespace(**dict(vars(original(fd)), **{field: value})))
    elif fault == 'executable-hardlink':
        os.link(model.pinned, tmp_path / 'foreign-hardlink')
    elif fault == 'executable-capability':
        monkeypatch.setattr(helper.os, 'listxattr', lambda fd: ['security.capability'])
    elif fault == 'executable-label':
        monkeypatch.setattr(helper.os, 'getxattr', lambda fd, name: b'system_u:object_r:bin_t:s0')
    elif fault == 'executable-format':
        model.pinned.write_bytes(b'#!/bin/sh\nexit 0\n')
        model.pinned.chmod(0o4755)
    elif fault in ('record-hash', 'record-mode'):
        record = json.loads(model.manifest.read_text())
        record['preserved'][0]['sha256' if fault == 'record-hash' else 'mode'] = (
            'b' * 64 if fault == 'record-hash' else 0o755)
        model.manifest.write_text(json.dumps(record))
    elif fault in ('missing-mount', 'writable-mount', 'duplicate-mount', 'manager-writable-mount'):
        target = model.manager if fault == 'manager-writable-mount' else thread
        contents = (target / 'mountinfo').read_text()
        (target / 'mountinfo').write_text('' if fault == 'missing-mount' else
            contents.replace('ro,relatime', 'rw,relatime') if 'writable' in fault else contents * 2)
    elif fault == 'parent-exited':
        monkeypatch.setattr(helper, 'exited', lambda fd: fd == 43)
    elif fault in ('parent-replaced', 'parent-thread-replaced'):
        original = helper.process_identity
        observed = {}
        target = parent if fault == 'parent-replaced' else parent_thread
        def identity(path):
            value = original(path)
            observed[path] = observed.get(path, 0) + 1
            return ('changed', *value[1:]) if path == target and observed[path] > 1 else value
        monkeypatch.setattr(helper, 'process_identity', identity)
    elif fault == 'parent-task-added':
        original = Path.iterdir
        observed = []
        def entries(path):
            if path == parent / 'task':
                observed.append(path)
                if len(observed) == 2:
                    (path / '2043').mkdir()
            return original(path)
        monkeypatch.setattr(helper.Path, 'iterdir', entries)
    elif fault in ('parent-label-changed', 'helper-label-changed', 'helper-namespace-changed',
                   'helper-generation-changed', 'visible-inode-replaced'):
        original = helper.hashlib.file_digest
        def digest(stream, name):
            value = original(stream, name)
            if fault in ('parent-label-changed', 'helper-label-changed'):
                target = parent_thread if fault == 'parent-label-changed' else thread
                (target / 'attr/current').write_text('system_u:system_r:init_t:s0')
            elif fault == 'helper-namespace-changed':
                (thread / 'ns/mnt').unlink()
                (thread / 'ns/mnt').symlink_to('mnt:[foreign-private]')
            elif fault == 'helper-generation-changed':
                (thread / 'root/usr/share/oh-no-parent-control/confinement/generation').write_text('b' * 64 + '\n')
            else:
                replacement = model.pinned.with_name('replacement')
                replacement.write_bytes(model.pinned.read_bytes())
                replacement.chmod(0o4755)
                replacement.replace(model.pinned)
            return value
        monkeypatch.setattr(helper.hashlib, 'file_digest', digest)
    identity = helper.process_identity(process)
    threads = {item: helper.process_identity(item) for item in (process / 'task').iterdir()}
    if fault == 'empty-threads':
        threads.clear()
    def observe():
        return helper.password_helper_process(process, model.account, model.config, model.manager,
                                              generation, 'mnt:[host]', identity, threads)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-(password|census):'):
            observe()
    else:
        assert observe() is None
    assert model.opened == model.closed
    assert len(model.enforcement) == (0 if fault in ('inventory', 'generation-format') else 1)


@pytest.mark.parametrize('fault', [None, 'init-t', 'unknown-label', 'helper-replaced', 'thread-replaced'])
def test_full_census_admits_only_proven_vendor_helper_and_rechecks_its_lifetime(
        password_helper_census, monkeypatch, fault):
    model = password_helper_census
    helper, process = model.helper, model.process
    if fault in ('init-t', 'unknown-label'):
        (process / 'attr/current').write_text('system_u:system_r:' +
            ('init_t' if fault == 'init-t' else 'unconfined_t') + ':s0')
    elif fault in ('helper-replaced', 'thread-replaced'):
        original = helper.process_identity
        target = process if fault == 'helper-replaced' else process / 'task/1044'
        observed = {}
        def identity(path):
            value = original(path)
            observed[path] = observed.get(path, 0) + 1
            return ('changed', *value[1:]) if path == target and observed[path] > 1 else value
        monkeypatch.setattr(helper, 'process_identity', identity)
    def observe():
        return helper.census_processes(model.account, model.config, 'selinux', model.manager, 42,
                                       'user@1002.service', required_roles=('manager', 'polkit'))
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-census:'):
            observe()
    else:
        assert observe()['confined_thread_roles'] == {
            'onpc_kiosk_manager_t': 2, 'onpc_kiosk_polkit_t': 2, 'policykit_auth_t': 2}
    assert sorted(model.opened) == sorted(model.closed)


@pytest.mark.parametrize('field', [
    'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid', 'st_gid',
])
def test_password_helper_census_refuses_executable_change_during_hashing(
        password_helper_census, monkeypatch, field):
    model = password_helper_census
    helper, process = model.helper, model.process
    original = helper.os.fstat
    observations = []
    def metadata(fd):
        values = vars(original(fd))
        observations.append(fd)
        if len(observations) == 2:
            values[field] += 1
        return SimpleNamespace(**values)
    monkeypatch.setattr(helper.os, 'fstat', metadata)
    identity = helper.process_identity(process)
    threads = {item: helper.process_identity(item) for item in (process / 'task').iterdir()}
    with pytest.raises(helper.guest.GuestError, match='kiosk-password:executable-changed'):
        helper.password_helper_process(process, model.account, model.config, model.manager,
                                       model.generation, 'mnt:[host]', identity, threads)
    assert len(observations) == 2
    assert model.opened == model.closed


def test_password_helper_census_refuses_permissive_installed_policy_before_parent_probe(
        password_helper_census, monkeypatch):
    model = password_helper_census
    helper, process = model.helper, model.process
    def permissive(config):
        raise ValueError('selinux-domain-not-enforcing')
    monkeypatch.setattr(helper.runpy, 'run_path', lambda path: {'enforcing': permissive})
    identity = helper.process_identity(process)
    threads = {item: helper.process_identity(item) for item in (process / 'task').iterdir()}
    with pytest.raises(ValueError, match='selinux-domain-not-enforcing'):
        helper.password_helper_process(process, model.account, model.config, model.manager,
                                       model.generation, 'mnt:[host]', identity, threads)
    assert model.opened == model.closed == []


@pytest.mark.parametrize('preserved', [False, True])
@pytest.mark.parametrize('vendor_permissive', [False, True])
def test_selinux_global_enforcing_also_checks_preserved_vendor_helper_domain(
        monkeypatch, preserved, vendor_permissive):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    queried = []
    def compute(source, destination, cls, permission, decision):
        assert source == destination and cls == permission == 1
        queried.append(source.decode())
        decision._obj.flags = int(vendor_permissive and source == b'system_u:system_r:policykit_auth_t:s0')
        return 0
    library = SimpleNamespace(is_selinux_enabled=lambda: 1, security_getenforce=lambda: 1,
        string_to_security_class=lambda name: 1, string_to_av_perm=lambda cls, name: 1,
        security_compute_av_flags_raw=compute)
    monkeypatch.setattr(helper.ctypes, 'CDLL', lambda name, **kwargs: library)
    config = {'backend': 'selinux', 'domains': ['manager', 'polkit'],
              'preserved_executables': [{'path': '/usr/lib/polkit-1/polkit-agent-helper-1'}] if preserved else []}
    if preserved and vendor_permissive:
        with pytest.raises(ValueError, match='selinux-domain-not-enforcing'):
            helper.enforcing(config)
    else:
        helper.enforcing(config)
    assert queried == ['system_u:system_r:onpc_kiosk_manager_t:s0',
                       'system_u:system_r:onpc_kiosk_polkit_t:s0'] + (
                       ['system_u:system_r:policykit_auth_t:s0'] if preserved else [])


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'label', 'credentials', 'namespace', 'generation',
                                  'profile-entry', 'proof-write', 'initial-exec'])
def test_bwrap_probe_requires_real_app_boundary_before_arming_or_execution(
        census_model, monkeypatch, backend, fault):
    helper = census_model
    generation = 'a' * 64 + '\n'
    request = dict(backend=backend, uid=1002, gid=1002, namespace=42, generation=generation,
                   arguments=['/usr/bin/bwrap', '--version'], proof_fd=53)
    expected = ('onpc-kiosk-app (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_app_t:s0')
    change = Mock(return_value=-1 if fault == 'profile-entry' else 0)
    monkeypatch.setattr(helper.ctypes, 'CDLL', lambda *args, **kwargs:
                        SimpleNamespace(aa_change_profile=change))
    monkeypatch.setattr(helper, 'lifecycle_label', lambda value:
                        'unconfined' if fault == 'label' else expected)
    credentials = []
    monkeypatch.setattr(helper.os, 'setgroups', lambda value: credentials.append(('groups', value)))
    monkeypatch.setattr(helper.os, 'setgid', lambda value: credentials.append(('gid', value)))
    monkeypatch.setattr(helper.os, 'setuid', lambda value: credentials.append(('uid', value)))
    monkeypatch.setattr(helper, 'process_identity', lambda path:
                        ('start', 1, ('0',) * 4 if fault == 'credentials' else ('1002',) * 4))
    monkeypatch.setattr(helper.os, 'stat', lambda path:
                        SimpleNamespace(st_ino=43 if fault == 'namespace' else 42))
    monkeypatch.setattr(helper.Path, 'read_text', lambda path:
                        'foreign' if fault == 'generation' else generation)
    inherited = []
    monkeypatch.setattr(helper.os, 'set_inheritable', lambda fd, value: inherited.append((fd, value)))
    proofs = []
    diagnostics = []
    def write(fd, data):
        if fd == 2:
            diagnostics.append(json.loads(data))
            return len(data)
        assert fd == 53
        proofs.append(json.loads(data))
        return len(data) - int(fault == 'proof-write')
    monkeypatch.setattr(helper.os, 'write', write)
    executed = []
    def execute(path, arguments, environment):
        executed.append((path, arguments, environment))
        if fault == 'initial-exec':
            raise PermissionError(13, 'private denied fixture')
        raise RuntimeError('exec captured')
    monkeypatch.setattr(helper.os, 'execve', execute)
    monkeypatch.setattr(helper.os, '_exit', Mock(side_effect=RuntimeError('exit captured')))
    failed = fault not in (None, 'initial-exec') and not (fault == 'profile-entry' and backend == 'selinux')
    if failed:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            helper.bwrap_probe_child(request)
        assert not executed
    else:
        with pytest.raises(RuntimeError, match='exit captured' if fault == 'initial-exec' else 'exec captured'):
            helper.bwrap_probe_child(request)
        assert credentials == [('groups', []), ('gid', 1002), ('uid', 1002)]
        assert proofs == [dict(uid=1002, namespace=42, generation=generation, role=expected)]
        assert inherited == [(53, False)]
        assert executed == [('/usr/bin/bwrap', request['arguments'], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})]
        assert diagnostics == ([{'bwrap_setup': 'initial-exec', 'errno': 13}]
                               if fault == 'initial-exec' else [])
    assert change.call_count == int(backend == 'apparmor')


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'pid', 'role', 'operation', 'target', 'permissive',
                                  'old', 'old-time', 'missing', 'setup', 'setup-stderr',
                                  'unsupported-flags', 'success', 'token'])
def test_bwrap_attack_requires_fresh_exact_enforcing_kernel_denial(
        census_model, monkeypatch, backend, fault):
    helper = census_model
    target = '/usr/bin/xdg-dbus-proxy'
    if backend == 'apparmor':
        line = ('audit(1792000000.123:42): apparmor="DENIED" operation="mount" '
                'profile="onpc-kiosk-bwrap" name="/newroot' + target + '" pid=4200 error=-13')
    else:
        line = ('audit(1792000000.123:42): avc:  denied  { execute } for pid=4200 '
                'name="bwrap-canary" dev="tmpfs" ino=43 scontext=system_u:system_r:onpc_kiosk_bwrap_t:s0 '
                'tcontext=unconfined_u:object_r:user_tmp_t:s0 tclass=file permissive=0')
    changes = {'pid': ('pid=4200', 'pid=42001'),
               'role': ('onpc-kiosk-bwrap', 'onpc-kiosk-app') if backend == 'apparmor' else
                       ('onpc_kiosk_bwrap_t', 'onpc_kiosk_app_t'),
               'operation': ('operation="mount"', 'operation="open"') if backend == 'apparmor' else
                            ('{ execute }', '{ read }'),
               'target': (target, '/usr/bin/foreign') if backend == 'apparmor' else
                         ('name="bwrap-canary"', 'name="foreign"'),
               'permissive': ('apparmor="DENIED"', 'apparmor="ALLOWED"') if backend == 'apparmor' else
                             ('permissive=0', 'permissive=1')}
    if fault in changes:
        line = line.replace(*changes[fault])
    if fault == 'old-time':
        line = line.replace('1792000000.123', '1791999999.999')
    before = {line} if fault == 'old' else set()
    audit = Mock(return_value='' if fault == 'missing' else line)
    def wait(predicate, category):
        helper.guest.require(predicate(), category)
    monkeypatch.setitem(sys.modules, 'system_kiosk_platform',
                        SimpleNamespace(kernel_audit=audit, wait_for=wait))
    output = (b'{"bwrap_setup":"initial-exec","errno":13}' if fault == 'setup' else
              b'bwrap: Unknown option --as-pid-1' if fault == 'unsupported-flags' else
              b'canary' if fault == 'token' else b'bwrap: permission denied')
    info = b'' if fault == 'unsupported-flags' else b'{"child-pid":4200,"pid-namespace":1234}'
    records = []
    def exercise():
        stderr = (b'{"bwrap_setup":"initial-exec","errno":13}' if fault == 'setup-stderr' else
                  ('bwrap: execvp ' + target + ': Permission denied\n').encode() if backend == 'selinux' else b'')
        helper.require_bwrap_denial(0 if fault == 'success' else 1, output, info,
            b'canary', backend, target, before, 1792000000.0, lambda *item: records.append(item),
            stderr=stderr, source_inode=43)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            exercise()
        assert not records
    else:
        exercise()
        assert records == [('onpc.kiosk.bwrap.kernel-denial', line)]


@pytest.mark.parametrize('mode,name,context', [
    ('bind', 'bwrap-canary', 'unconfined_u:object_r:user_tmp_t:s0'),
    ('data', None, 'system_u:object_r:tmpfs_t:s0'),
    ('tmpfs-file', 'gst-plugin-scanner', 'system_u:object_r:tmpfs_t:s0'),
])
@pytest.mark.parametrize('fault', [None, 'name', 'context', 'device', 'inode', 'native-target', 'native-stage'])
def test_bwrap_selinux_correlates_native_target_with_each_observed_object_style(
        census_model, monkeypatch, mode, name, context, fault):
    helper = census_model
    target = '/usr/libexec/gstreamer-1.0/gst-plugin-scanner'
    # Only bind preserves the caller's measured inode. The other modes create
    # independent inodes: no equality to the source is claimed or required.
    inode = 43 if mode == 'bind' else 987
    object_name = '' if name is None else 'name="' + name + '" '
    line = ('audit(1792000000.123:42): avc:  denied  { execute } for pid=4200 ' + object_name +
            'dev="tmpfs" ino=' + str(inode) + ' scontext=system_u:system_r:onpc_kiosk_bwrap_t:s0 '
            'tcontext=' + context + ' tclass=file permissive=0')
    if fault == 'name':
        line = line.replace(object_name, 'name="foreign" ', 1) if object_name else line + ' name="foreign"'
    elif fault == 'context':
        line = line.replace('tcontext=' + context, 'tcontext=system_u:object_r:bin_t:s0')
    elif fault == 'device':
        line = line.replace('dev="tmpfs"', 'dev="vda1"')
    elif fault == 'inode':
        line = line.replace('ino=' + str(inode), 'ino=44' if mode == 'bind' else 'ino=0')
    stderr = ('bwrap: execvp ' + target + ': Permission denied\n').encode()
    if fault == 'native-target':
        stderr = stderr.replace(target.encode(), b'/usr/bin/foreign')
    elif fault == 'native-stage':
        stderr = b'bwrap: Failed to mount: Permission denied\n'
    monkeypatch.setitem(sys.modules, 'system_kiosk_platform', SimpleNamespace(
        kernel_audit=lambda backend: line,
        wait_for=lambda predicate, category: helper.guest.require(predicate(), category)))
    records = []
    def exercise():
        helper.require_bwrap_denial(1, b'', b'{"child-pid":4200}', b'canary', 'selinux',
            target, set(), 1792000000.0, lambda *item: records.append(item),
            stderr=stderr, mode=mode, source_inode=43)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            exercise()
        assert not records
    else:
        exercise()
        assert records == [('onpc.kiosk.bwrap.kernel-denial', line)]


@pytest.mark.parametrize('fault', [None, 'operation', 'target', 'mask', 'owner', 'native-stage'])
def test_bwrap_apparmor_tmpfs_file_requires_observed_owned_create_denial(
        census_model, monkeypatch, fault):
    helper = census_model
    target = '/usr/bin/xdg-dbus-proxy'
    line = ('audit(1792000000.123:42): apparmor="DENIED" operation="mknod" class="file" '
            'profile="onpc-kiosk-bwrap" name="/newroot' + target + '" pid=4200 '
            'requested_mask="c" denied_mask="c" fsuid=1002 ouid=1002')
    changes = {'operation': ('operation="mknod"', 'operation="open"'),
               'target': (target, '/usr/bin/foreign'),
               'mask': ('denied_mask="c"', 'denied_mask="w"'),
               'owner': ('ouid=1002', 'ouid=0')}
    if fault in changes:
        line = line.replace(*changes[fault])
    monkeypatch.setitem(sys.modules, 'system_kiosk_platform', SimpleNamespace(
        kernel_audit=lambda backend: line,
        wait_for=lambda predicate, category: helper.guest.require(predicate(), category)))
    records = []
    stderr = ("bwrap: Can't create file " + target + ': Permission denied\n').encode()
    if fault == 'native-stage':
        stderr = ('bwrap: execvp ' + target + ': Permission denied\n').encode()
    def exercise():
        helper.require_bwrap_denial(1, b'', b'{"child-pid":4200}', b'canary', 'apparmor',
            target, set(), 1792000000.0, lambda *item: records.append(item),
            stderr=stderr, mode='tmpfs-file', uid=1002)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            exercise()
        assert not records
    else:
        exercise()
        assert records == [('onpc.kiosk.bwrap.kernel-denial', line)]


@pytest.mark.parametrize('data', [b'', b'not-json', b'{}', b'[]', b'{"child-pid":true}',
                                 b'{"child-pid":1}', b'{"child-pid":"4200"}', b'x' * 4097])
def test_bwrap_native_info_requires_real_host_child_pid(census_model, data):
    with pytest.raises(census_model.guest.GuestError, match='kiosk-bwrap:native-child-info'):
        census_model.bwrap_child_pid(data)


def test_bwrap_diagnostics_keep_setup_stderr_and_bound_each_channel(census_model):
    records = []
    census_model.record_bwrap_probe(lambda *item: records.append(item), 'proxy-bind', 126,
        b'x' * 4097, b'{"child-pid":4200}', b'{"bwrap_setup":"initial-exec","errno":13}')
    assert records[0][0] == 'onpc.kiosk.bwrap.proxy-bind.probe'
    assert json.loads(records[0][1]) == {
        'status': 126, 'stdout': 'x' * 4096, 'native_info': '{"child-pid":4200}',
        'stderr': '{"bwrap_setup":"initial-exec","errno":13}', 'truncated': True}


@pytest.mark.parametrize('backend,row,expected', [
    ('apparmor', 'gdm3\t50.1-0ubuntu0.1\tamd64\tgdm3\t50.1-0ubuntu0.1',
     {'package': 'gdm3', 'version': '50.1-0ubuntu0.1', 'architecture': 'amd64',
      'source_package': 'gdm3', 'source_version': '50.1-0ubuntu0.1'}),
    ('selinux', 'pam\t0:1.7.2-2.fc44\tx86_64\tpam-1.7.2-2.fc44.src.rpm',
     {'package': 'pam', 'version': '0:1.7.2-2.fc44', 'architecture': 'x86_64',
      'source_rpm': 'pam-1.7.2-2.fc44.src.rpm'}),
])
def test_native_package_inventory_preserves_exact_binary_and_source_builds(
        census_model, backend, row, expected):
    assert census_model.native_package_rows(backend, row) == [expected]


@pytest.mark.parametrize('rows', ['', 'pam\t1.7\tx86_64', 'pam\t1.7\tx86_64\t',
                                  'pam\t1.7\tx86_64\tbad source',
                                  'pam\t1.7\tx86_64\tpam.src.rpm\npam\t1.7\tx86_64\tpam.src.rpm'])
def test_native_package_inventory_refuses_missing_or_ambiguous_source_identity(census_model, rows):
    with pytest.raises(census_model.guest.GuestError, match='kiosk-native:package-identity'):
        census_model.native_package_rows('selinux', rows)


@pytest.mark.parametrize('directive', ['@include ', 'session include ', 'session substack '])
@pytest.mark.parametrize('profile', ['active', 'plain', 'other-arguments', 'commented'])
def test_optional_cgfs_witness_selects_only_declared_exact_session_profile(
        census_model, integration, monkeypatch, directive, profile):
    installed, _ = integration
    rule = 'session optional pam_cgfs.so -c freezer,memory,name=systemd\n'
    if profile == 'plain':
        rule = 'session required pam_unix.so\n'
    elif profile == 'other-arguments':
        rule = 'session optional pam_cgfs.so -c memory\n'
    elif profile == 'commented':
        rule = '# ' + rule
    (installed.PAM_LOCAL / 'systemd-user').write_text(directive + 'shared-session\n')
    (installed.PAM_LOCAL / 'shared-session').write_text(rule)
    reader = Mock(return_value={'included_source': installed.included_source,
                                'pam_lines': installed.pam_lines})
    monkeypatch.setattr(census_model.runpy, 'run_path', reader)
    assert census_model.optional_cgfs_session('apparmor') == (profile == 'active')
    reader.reset_mock()
    assert not census_model.optional_cgfs_session('selinux')
    reader.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'absent', 'disappeared', 'missing-map', 'data-only', 'foreign-inode',
                                  'foreign-device', 'deleted', 'receipt', 'changed'])
def test_pam_cgfs_mapping_requires_native_executable_inode_and_receipt(
        census_model, tmp_path, monkeypatch, fault):
    helper = census_model
    native = tmp_path / 'pam_cgfs.so'
    native.write_bytes(b'\x7fELFprivate native callback')
    identity = native.stat()
    digest = helper.guest.sha(native)
    measured = {'role': 'library', 'path': str(native), 'sha256': digest}
    source = Mock(side_effect=[measured, {**measured, 'sha256': 'f' * 64}
                               if fault == 'changed' else measured])
    preparation = {'trusted': Mock(return_value=native), 'source_record': source}
    reader = Mock(return_value=preparation)
    monkeypatch.setattr(helper.runpy, 'run_path', reader)
    original_exists = os.path.lexists
    monkeypatch.setattr(helper.os.path, 'lexists', lambda path: fault not in ('absent', 'disappeared')
                        if str(path) == '/usr/lib/x86_64-linux-gnu/security/pam_cgfs.so'
                        else original_exists(path))
    device = f'{os.major(identity.st_dev):x}:{os.minor(identity.st_dev):x}'
    if fault == 'foreign-device':
        device = 'ff:ff'
    inode = identity.st_ino + (fault == 'foreign-inode')
    permissions = 'r--p' if fault == 'data-only' else 'r-xp'
    mapped = str(native) + (' (deleted)' if fault == 'deleted' else '')
    (tmp_path / 'maps').write_text('' if fault == 'missing-map' else
        f'1000-2000 {permissions} 00000000 {device} {inode} {mapped}\n')
    receipts = [{'path': str(native), 'sha256': '0' * 64 if fault == 'receipt' else digest}]
    if fault == 'absent':
        receipts = []
    events = {}
    if fault is not None:
        with pytest.raises(helper.guest.GuestError, match='kiosk-lifecycle:cgfs-'):
            helper.lifecycle_cgfs_mapping(tmp_path, receipts, events.__setitem__)
        assert not events
    else:
        helper.lifecycle_cgfs_mapping(tmp_path, receipts, events.__setitem__)
        assert json.loads(events['onpc.kiosk.pam-lifecycle.pam-cgfs-native-mapping']) == {
            'path': str(native), 'sha256': digest, 'device': device, 'inode': identity.st_ino}
        assert source.call_args_list[0].args == ('library', native)


@pytest.mark.parametrize('backend,present', [('apparmor', True), ('apparmor', False),
                                          ('selinux', True)])
def test_native_receipts_include_installed_optional_cgfs_bytes_and_package(
        census_model, tmp_path, monkeypatch, backend, present):
    helper = census_model
    # A finite private distro tree keeps package queries and every write off the host.
    library = '/usr/lib/x86_64-linux-gnu' if backend == 'apparmor' else '/usr/lib64'
    names = ['/usr/libexec/gdm-session-worker', '/usr/lib/systemd/systemd-executor',
             library + '/libpam.so.0', library + '/security/pam_namespace.so',
             library + '/security/pam_selinux.so', library + '/libselinux.so.1']
    if backend == 'apparmor':
        names.append(library + '/libapparmor.so.1')
    optional = library + '/security/pam_cgfs.so'
    for name in names + ([optional] if present else []):
        path = tmp_path / name.lstrip('/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'\x7fELF' + name.encode())
    def path(value):
        value = Path(value)
        return tmp_path / str(value).lstrip('/') if str(value).startswith('/usr/') else value
    monkeypatch.setattr(helper, 'Path', path)
    original_relative = Path.is_relative_to
    monkeypatch.setattr(Path, 'is_relative_to', lambda value, other:
                        original_relative(value, tmp_path / 'usr') if other == '/usr'
                        else original_relative(value, other))
    original_stat = Path.stat
    def metadata(value, **options):
        info = original_stat(value, **options)
        return SimpleNamespace(st_uid=0, st_mode=info.st_mode & ~0o022)
    monkeypatch.setattr(Path, 'stat', metadata)
    trusted = Mock(side_effect=lambda value, **options: value.resolve(strict=True))
    monkeypatch.setattr(helper.runpy, 'run_path', Mock(return_value={
        'inventory': lambda config: [], 'trusted': trusted}))
    commands = []
    def query(arguments):
        commands.append(arguments)
        if arguments[:2] == ['dpkg-query', '-S']:
            return '\n'.join(('libpam-cgfs:amd64' if value.endswith('/pam_cgfs.so') else
                              'native-input:amd64') + ': ' + value for value in arguments[2:])
        if arguments[:2] == ['dpkg-query', '-W']:
            return '\n'.join(name + '\t6.0.6-1ubuntu2\tamd64\tlxc\t6.0.6-1ubuntu2'
                             for name in arguments[3:])
        if arguments[:2] == ['rpm', '-qf']:
            return 'native-input\n'
        assert arguments[:2] == ['rpm', '-q']
        return 'native-input\t0:1.2-3.fc44\tx86_64\tnative-input-1.2-3.fc44.src.rpm\n'
    monkeypatch.setattr(helper.guest, 'run', query)
    events = {}
    files = helper.record_native_packages({'backend': backend}, events.__setitem__)
    included = backend == 'apparmor' and present
    actual = path(optional)
    if included:
        assert {'path': str(actual), 'sha256': helper.guest.sha(actual)} in files
    else:
        assert not any(item['path'].endswith('/pam_cgfs.so') for item in files)
    packages = json.loads(events['onpc.kiosk.native.packages'])
    assert any(item['package'] == 'libpam-cgfs:amd64' and item['version'] == '6.0.6-1ubuntu2'
               for item in packages) == included
    assert trusted.call_count == included


@pytest.mark.parametrize('fault', [None, 'alias-owner', 'original-ancestor',
                                  'target-ancestor', 'target-owner', 'parent-traversal'])
def test_native_inventory_validates_lexical_alias_and_every_target_path(tmp_path, monkeypatch, fault):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    for name in ('safe', 'aliases', 'links', 'unsafe'):
        (tmp_path / name).mkdir(mode=0o755)
    source = tmp_path / 'safe/program'
    source.write_bytes(b'\x7fELFprivate fixture')
    source.chmod(0o755)
    forward = tmp_path / 'links/forward'
    forward.symlink_to('../safe/program')
    alias = tmp_path / 'aliases/command'
    alias.symlink_to(forward if fault == 'target-owner' else '../links/forward')
    if fault == 'original-ancestor':
        alias.parent.chmod(0o777)
    elif fault == 'target-ancestor':
        forward.parent.chmod(0o777)
    elif fault == 'parent-traversal':
        alias.unlink()
        alias.symlink_to('../unsafe/../safe/program')
        (tmp_path / 'unsafe').chmod(0o777)
    original = Path.lstat

    def metadata(path):
        info = list(original(path))
        # Substitute privileged ownership only; private native files, aliases,
        # real target traversal and their deliberate unsafe modes stay intact.
        info[4] = (1000 if (fault == 'alias-owner' and path == alias or
                           fault == 'target-owner' and path == forward) else 0)
        if path == tmp_path or path in tmp_path.parents:
            info[0] &= ~0o022  # Isolate the fixture from its host /tmp ancestry.
        return os.stat_result(info)

    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    if fault is not None:
        with pytest.raises(ValueError, match='untrusted-path'):
            helper.source_record('service', alias)
    else:
        expected = {
            'role': 'service', 'path': str(source),
            'sha256': helper.hashlib.sha256(source.read_bytes()).hexdigest()}
        assert helper.source_record('service', alias) == expected
        directory_alias = tmp_path / 'bin'
        directory_alias.symlink_to('aliases', target_is_directory=True)
        assert helper.source_record('service', directory_alias / alias.name) == expected
        with pytest.raises(ValueError, match='substituted-path'):
            helper.trusted(alias)


def test_native_inventory_refuses_relative_symlink_cycles(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    source = tmp_path / 'program'
    source.symlink_to('../' + tmp_path.name + '/program')
    original = Path.lstat

    def metadata(path):
        info = list(original(path))
        info[4] = 0
        if path == tmp_path or path in tmp_path.parents:
            info[0] &= ~0o022
        return os.stat_result(info)

    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    with pytest.raises((OSError, RuntimeError)):
        helper.source_record('service', source)


def test_preparation_identity_is_stable_across_same_byte_reinstall(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    # Inventory identity and digest operate on real private ELF-shaped files;
    # privileged ancestor validation is separately exercised by integration.
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: Path(path).resolve(strict=True))
    source = tmp_path / 'program'
    source.write_bytes(b'\x7fELFprivate fixture')
    source.chmod(0o755)
    before = helper.source_record('service', source)
    source.unlink()
    source.write_bytes(b'\x7fELFprivate fixture')
    source.chmod(0o755)
    assert helper.source_record('service', source) == before
    source.write_bytes(b'\x7fELFchanged fixture')
    assert helper.source_record('service', source) != before


def test_inventory_deduplicates_distro_alias_and_rejects_conflicting_roles(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: Path(path).resolve(strict=True))
    source = tmp_path / 'pipewire'
    source.write_bytes(b'\x7fELFprivate fixture')
    source.chmod(0o755)
    alias = tmp_path / 'pipewire-pulse'
    alias.symlink_to(source)
    config = {'executables': [{'role': 'service', 'paths': [str(source), str(alias)]}]}
    assert len(helper.inventory(config)) == 1
    config['executables'].append({'role': 'manager', 'paths': [str(alias)]})
    with pytest.raises(ValueError, match='conflicting'):
        helper.inventory(config)


def test_inventory_binds_substitution_bytes_to_their_destination(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: Path(path).resolve(strict=True))
    native, launcher = tmp_path / 'native', tmp_path / 'launcher'
    for path, content in ((native, b'\x7fELFnative'), (launcher, b'\x7fELFlauncher')):
        path.write_bytes(content)
        path.chmod(0o755)
    config = {'executables': [
        {'role': 'bwrap', 'paths': [str(native)], 'source': str(launcher)},
        {'role': 'bwrap-native', 'paths': [str(launcher)], 'source': str(native)}]}
    before = {path: path.read_bytes() for path in (native, launcher)}
    records = helper.inventory(config)
    assert records == [dict(role=role, path=str(target), source=str(source),
                            sha256=helper.hashlib.sha256(before[source]).hexdigest())
                       for role, target, source in
                       (('bwrap', native, launcher), ('bwrap-native', launcher, native))]
    assert {path: path.read_bytes() for path in before} == before
    config['executables'].append({'role': 'bwrap', 'paths': [str(native)], 'source': str(native)})
    with pytest.raises(ValueError, match='conflicting'):
        helper.inventory(config)


@pytest.mark.parametrize('extra', [{'paths': ['one', 'two']}, {'optional': True},
                                   {'library_directory': '/usr/lib'}, {'source': ''},
                                   {'source': False}, {'source': 5}])
def test_inventory_refuses_ambiguous_substitution(extra):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    entry = dict(role='bwrap', paths=['one'], source='two')
    entry.update(extra)
    with pytest.raises(ValueError, match='invalid-executable-substitution'):
        helper.inventory({'executables': [entry]})


def test_blocked_shared_library_needs_no_executable_mode(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: Path(path).resolve(strict=True))
    library = tmp_path / 'libgstpython.so'
    library.write_bytes(b'\x7fELFprivate shared library')
    library.chmod(0o644)
    assert helper.source_record('blocked', library)['role'] == 'blocked'
    with pytest.raises(ValueError, match='unexpected-executable-mode'):
        helper.source_record('service', library)


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_vendor_password_helper_is_reserved_without_copying_setuid_executable(
        tmp_path, monkeypatch, distribution):
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    policy.generate(tmp_path / 'payload', distribution)
    config = json.loads((tmp_path / 'payload/config.json').read_text())
    assert config['preserved_executables'] == [{
        'path': '/usr/lib/polkit-1/polkit-agent-helper-1',
        'mode': 0o4755 if distribution == 'fedora' else 0o755,
        'label': 'system_u:object_r:policykit_auth_exec_t:s0' if distribution == 'fedora' else None,
    }]
    assert '/usr/lib/polkit-1' not in config['reserved_directories']
    assert not any(Path(path).name == 'polkit-agent-helper-1'
                   for entry in config['executables'] for path in entry['paths'])
    source = tmp_path / 'polkit-agent-helper-1'
    source.write_bytes(b'\x7fELFvendor password helper')
    source.chmod(0o4755)
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: Path(path).resolve(strict=True))
    with pytest.raises(ValueError, match='unexpected-executable-mode'):
        helper.source_record('polkit', source)
    assert stat.S_IMODE(source.stat().st_mode) == 0o4755


@pytest.fixture
def preserved_password_helper(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    source = tmp_path / 'vendor/polkit-1/polkit-agent-helper-1'
    source.parent.mkdir(parents=True)
    source.parent.parent.chmod(0o755)
    source.parent.chmod(0o755)
    source.write_bytes(b'\x7fELFprivate vendor password helper')
    original_lstat, original_fstat = Path.lstat, os.fstat

    def root_metadata(info, **changes):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        return SimpleNamespace(**dict(values, st_uid=0, st_gid=0, **changes))

    def metadata(path):
        info = original_lstat(path)
        # Keep actual private file types, modes, links and nanosecond identity.
        # Only root ownership and the external scratch ancestors are simulated.
        mode = info.st_mode & ~0o022 if path == tmp_path or path in tmp_path.parents else info.st_mode
        return root_metadata(info, st_mode=mode)

    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    monkeypatch.setattr(helper.os, 'fstat', lambda fd: root_metadata(original_fstat(fd)))
    monkeypatch.setattr(helper.os, 'listxattr', lambda fd: [])
    monkeypatch.setattr(helper.os, 'getxattr',
                        lambda fd, name: b'system_u:object_r:policykit_auth_exec_t:s0\0')

    def configure(distribution):
        source.chmod(0o4755 if distribution == 'fedora' else 0o755)
        return {'backend': 'selinux' if distribution == 'fedora' else 'apparmor',
                'preserved_executables': [{
                    'path': str(source), 'mode': 0o4755 if distribution == 'fedora' else 0o755,
                    'label': ('system_u:object_r:policykit_auth_exec_t:s0'
                              if distribution == 'fedora' else None)}]}

    return helper, source, configure


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_preserved_password_helper_measures_vendor_bytes_and_privilege_metadata(
        preserved_password_helper, distribution):
    helper, source, configure = preserved_password_helper
    config = configure(distribution)
    before = source.read_bytes()
    records, identities = helper.preserved_inventory(config)
    expected = config['preserved_executables'][0]
    assert records == [dict(path=str(source), sha256=helper.hashlib.sha256(before).hexdigest(),
                            mode=expected['mode'], uid=0, gid=0, label=expected['label'])]
    with source.open('rb') as stream:
        assert identities == {str(source): helper.file_identity(os.fstat(stream.fileno()))}
    assert source.read_bytes() == before
    assert stat.S_IMODE(source.stat().st_mode) == expected['mode']


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('fault,reason', [
    ('mode', 'unexpected-preserved-executable'),
    ('owner', 'unexpected-preserved-executable'),
    ('group', 'unexpected-preserved-executable'),
    ('directory', 'unexpected-file-type'),
    ('symlink', 'substituted-path'),
    ('hardlink', 'unexpected-preserved-executable'),
    ('capability', 'unexpected-preserved-executable'),
    ('script', 'unexpected-preserved-executable'),
])
def test_preserved_password_helper_refuses_unexpected_native_identity(
        preserved_password_helper, tmp_path, monkeypatch, distribution, fault, reason):
    helper, source, configure = preserved_password_helper
    config = configure(distribution)
    if fault == 'mode':
        source.chmod(0o6755)
    elif fault in ('owner', 'group'):
        original = helper.os.fstat
        def metadata(fd):
            values = vars(original(fd))
            return SimpleNamespace(**dict(values, **{
                'st_uid' if fault == 'owner' else 'st_gid': 12345}))
        monkeypatch.setattr(helper.os, 'fstat', metadata)
    elif fault == 'directory':
        source.unlink()
        source.mkdir(mode=0o755)
    elif fault == 'symlink':
        target = source.with_name('substitute')
        source.rename(target)
        source.symlink_to(target.name)
    elif fault == 'hardlink':
        os.link(source, tmp_path / 'helper-alias')
    elif fault == 'capability':
        monkeypatch.setattr(helper.os, 'listxattr', lambda fd: ['security.capability'])
    elif fault == 'script':
        source.write_bytes(b'#!/bin/sh\nexit 0\n')
        source.chmod(config['preserved_executables'][0]['mode'])
    with pytest.raises(ValueError, match=reason):
        helper.preserved_inventory(config)


@pytest.mark.parametrize('label,error', [
    (b'system_u:object_r:bin_t:s0\0', ValueError),
    (b'\xff', UnicodeDecodeError),
    (None, OSError),
])
def test_preserved_password_helper_refuses_wrong_or_unreadable_selinux_label(
        preserved_password_helper, monkeypatch, label, error):
    helper, _, configure = preserved_password_helper
    config = configure('fedora')
    def read_label(fd, name):
        assert name == 'security.selinux'
        if label is None:
            raise OSError('private fixture has no SELinux label')
        return label
    monkeypatch.setattr(helper.os, 'getxattr', read_label)
    with pytest.raises(error):
        helper.preserved_inventory(config)


@pytest.mark.parametrize('field', [
    'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid', 'st_gid',
])
def test_preserved_password_helper_refuses_change_during_measurement(
        preserved_password_helper, monkeypatch, field):
    helper, _, configure = preserved_password_helper
    config = configure('fedora')
    original = helper.os.fstat
    observations = []
    def metadata(fd):
        values = vars(original(fd))
        observations.append(fd)
        if len(observations) == 2:
            values[field] += 1
        return SimpleNamespace(**values)
    monkeypatch.setattr(helper.os, 'fstat', metadata)
    with pytest.raises(ValueError, match='preserved-executable-changed'):
        helper.preserved_inventory(config)
    assert len(observations) == 2


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_preserved_password_helper_reinstall_keeps_generation_and_refreshes_inode_assertion(
        preserved_password_helper, distribution):
    helper, source, configure = preserved_password_helper
    config = configure(distribution)
    records, identities = helper.preserved_inventory(config)
    replacement = source.with_name('replacement')
    replacement.write_bytes(source.read_bytes())
    replacement.chmod(config['preserved_executables'][0]['mode'])
    replacement.replace(source)
    installed_records, installed_identities = helper.preserved_inventory(config)
    assert installed_records == records
    assert installed_identities[str(source)][:2] != identities[str(source)][:2]
    source.write_bytes(b'\x7fELFchanged vendor password helper')
    source.chmod(config['preserved_executables'][0]['mode'])
    changed_records, _ = helper.preserved_inventory(config)
    assert changed_records != records


@pytest.fixture
def preserved_password_preparation(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    real_directory_layout, real_trusted = helper.directory_layout, helper.trusted
    real_inventory, real_source_record = helper.inventory, helper.source_record
    payload, runtime = tmp_path / 'payload', tmp_path / 'runtime'
    payload.mkdir()
    runtime.mkdir(mode=0o700)
    marker = tmp_path / 'kiosk-uid'
    marker.write_text('1002\n')
    marker.chmod(0o600)
    vendor = tmp_path / 'usr/lib/polkit-1/polkit-agent-helper-1'
    vendor.parent.mkdir(parents=True)
    (tmp_path / 'usr/share/oh-no-parent-control/confinement').mkdir(parents=True)
    vendor.write_bytes(b'\x7fELFprivate vendor password helper')
    vendor.chmod(0o755)
    for directory in [tmp_path / 'usr', *(tmp_path / 'usr').rglob('*')]:
        if directory.is_dir(): directory.chmod(0o755)
    path = '/usr/lib/polkit-1/polkit-agent-helper-1'
    entry = dict(path=path, mode=0o755, label=None)
    record = dict(entry, uid=0, gid=0, sha256=helper.hashlib.sha256(vendor.read_bytes()).hexdigest())
    identities = {path: (*helper.file_identity(vendor.stat())[:6], 0, 0)}
    config = dict(backend='apparmor', executables=[], preserved_executables=[entry])
    (payload / 'config.json').write_text(json.dumps(config))
    (payload / 'onpc-kiosk.apparmor').write_text('# private policy\n')
    (runtime / 'bindings').write_text('previous bindings\n')
    layout = [{'path': '/usr/lib', 'kind': 'tree'},
              {'path': '/usr/lib/polkit-1', 'kind': 'tree'},
              {'path': path, 'kind': 'file'},
              {'path': '/usr/share', 'kind': 'tree'},
              {'path': '/usr/share/oh-no-parent-control', 'kind': 'tree'},
              {'path': '/usr/share/oh-no-parent-control/confinement', 'kind': 'tree'},
              {'path': '/usr/share/oh-no-parent-control/confinement/generation', 'kind': 'file'}]
    manager_checks, reclaims = [], []
    real_manager_generation = helper.manager_generation
    monkeypatch.setattr(helper, 'RUNTIME', runtime)
    monkeypatch.setattr(helper.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(helper.os, 'umask', lambda mode: 0o022)
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1002))
    # These unit cases inject a post-measurement layout, keeping actual private
    # generation/tree/bindings writes. Inventory trust has independent coverage.
    def trusted(source, **kwargs):
        source = Path(source)
        if str(source) == '/var/lib/oh-no-parent-control/package-created-kiosk-uid':
            return marker
        if source.parent == helper.PAYLOAD and source.name != 'generation':
            return payload / source.name
        return source
    monkeypatch.setattr(helper, 'trusted', trusted)
    original_lstat = Path.lstat

    def metadata(source):
        physical = tmp_path / str(source).lstrip('/') if source == Path('/usr') or Path('/usr') in source.parents else source
        info = original_lstat(physical)
        if (source == tmp_path or tmp_path in source.parents or
                source == Path('/usr') or Path('/usr') in source.parents):
            values = list(info)
            values[4] = 0  # Model root-created generation files without host privileges.
            values[5] = 0
            return os.stat_result(values)
        if source in tmp_path.parents:
            values = list(info); values[4] = 0; values[0] &= ~0o022
            return os.stat_result(values)
        return info

    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    def verify(arguments, **kwargs):
        assert arguments == ['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'verify']
        contents = ((payload / 'config.json').read_bytes(),
                    (payload / 'onpc-kiosk.apparmor').read_bytes())
        return SimpleNamespace(returncode=0, stdout=' '.join(helper.hashlib.sha256(data).hexdigest()
                                                           for data in contents) + '\n')
    monkeypatch.setattr(helper.subprocess, 'run', verify)
    monkeypatch.setattr(helper, 'enforcing', lambda value: None)
    monkeypatch.setattr(helper, 'inventory', lambda value: [])
    monkeypatch.setattr(helper, 'preserved_inventory', lambda value: ([record], identities))
    def collect(value, records):
        assert records == [record]
        return layout
    monkeypatch.setattr(helper, 'directory_layout', collect)
    def invocation(backend):
        view = runtime / 'native-view'
        # A new native tmpfs starts empty for every preparation. Only this
        # fixture-owned invocation directory is replaced; generations persist.
        if view.exists(): shutil.rmtree(view)
        view.mkdir(mode=0o700)
        return view
    monkeypatch.setattr(helper, 'verify_invocation_root', invocation)
    monkeypatch.setattr(helper, 'runtime_label', lambda *args, **kwargs: None)
    monkeypatch.setattr(helper, 'manager_generation', lambda *args: manager_checks.append(args))
    monkeypatch.setattr(helper, 'reclaim_interrupted', lambda: reclaims.append(True))
    return SimpleNamespace(helper=helper, runtime=runtime, payload=payload, vendor=vendor,
        bindings=runtime / 'native-view/bindings', layout=layout, path=path, record=record,
        identities=identities, manager_checks=manager_checks, reclaims=reclaims,
        real_manager_generation=real_manager_generation,
        real_directory_layout=real_directory_layout, real_trusted=real_trusted,
        real_inventory=real_inventory, real_source_record=real_source_record)


@pytest.fixture
def classification_preparation(preserved_password_preparation, tmp_path, monkeypatch):
    """Use real trust, inventory classification and publication on private /usr."""
    scene = preserved_password_preparation
    helper = scene.helper
    old_trusted, old_lstat = helper.trusted, Path.lstat
    old_iterdir, old_readlink, old_stat, old_exists = Path.iterdir, os.readlink, Path.stat, Path.exists
    faults, failures, visited = {}, {}, []
    root = tmp_path / 'usr'
    (root / 'share/oh-no-parent-control/confinement/generation').touch()
    (root / 'share/oh-no-parent-control/confinement/generation').chmod(0o644)

    def physical(path):
        path = Path(path)
        return tmp_path / path.relative_to('/') if path == Path('/usr') or Path('/usr') in path.parents else path

    def logical(path):
        path = Path(path)
        return Path('/usr') / path.relative_to(root) if path == root or root in path.parents else path

    def metadata(path):
        path = Path(path)
        name = logical(path)
        if ('metadata', name) in failures:
            raise failures['metadata', name]
        info = old_lstat(physical(path))
        if name in faults:
            values = list(info)
            mode, uid, gid = faults[name]
            values[0] = stat.S_IFMT(info.st_mode) | mode
            values[4:6] = [uid, gid]
            return os.stat_result(values)
        return info

    def entries(path):
        visited.append(logical(path))
        return iter(logical(child) for child in old_iterdir(physical(path)))

    def readlink(path, *args, **kwargs):
        name = logical(path)
        if ('readlink', name) in failures:
            raise failures['readlink', name]
        return old_readlink(physical(path), *args, **kwargs)

    def trusted(path, **kwargs):
        path = Path(path)
        # Payload snapshots use the attested fixture, while all layout and
        # alias checks use the real private tree and complete original checks.
        if path.parent == helper.PAYLOAD and path.name in ('config.json', 'onpc-kiosk.apparmor'):
            return old_trusted(path, **kwargs)
        if path == Path('/usr') or Path('/usr') in path.parents:
            return logical(scene.real_trusted(physical(path), **kwargs))
        return old_trusted(path, **kwargs)

    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    monkeypatch.setattr(helper.Path, 'stat', lambda path, **kwargs: old_stat(physical(path), **kwargs))
    monkeypatch.setattr(helper.Path, 'exists', lambda path, **kwargs: old_exists(physical(path), **kwargs))
    monkeypatch.setattr(helper.Path, 'iterdir', entries)
    monkeypatch.setattr(helper.os, 'readlink', readlink)
    monkeypatch.setattr(helper, 'trusted', trusted)
    monkeypatch.setattr(helper, 'directory_layout', scene.real_directory_layout)
    scene.faults, scene.failures, scene.visited = faults, failures, visited
    scene.physical = physical
    scene.config = json.loads((scene.payload / 'config.json').read_text())

    def configure():
        (scene.payload / 'config.json').write_text(json.dumps(scene.config))
    scene.configure = configure
    return scene


@pytest.mark.parametrize('fault', ['lexical-directory', 'lexical-link', 'intermediate-target'])
def test_classification_refuses_late_required_alias_ancestry(classification_preparation, fault):
    scene = classification_preparation
    root = scene.physical('/usr')
    (root / 'bin').mkdir(mode=0o755)
    (root / 'aliases').mkdir(mode=0o755)
    (root / 'links').mkdir(mode=0o755)
    (root / 'aliases/command').symlink_to('../links/forward')
    (root / 'links/forward').symlink_to('../lib/polkit-1/polkit-agent-helper-1')
    if fault == 'lexical-directory':
        changed = Path('/usr/aliases')
    elif fault == 'lexical-link':
        (root / 'bin/command').symlink_to('../aliases/command')
        changed = Path('/usr/aliases/command')
    else:
        changed = Path('/usr/links/forward')
    alias = '/usr/aliases/command' if fault == 'lexical-directory' else '/usr/bin/command'
    if fault == 'intermediate-target':
        (root / 'bin/command').symlink_to('../aliases/command')
    config = dict(scene.config, executables=[dict(role='service', paths=[alias])])
    # This models owner drift after a successful native inventory, before the
    # actual directory trust/layout boundary. Canonical bytes remain present.
    scene.faults[changed] = (0o755 if fault == 'lexical-directory' else 0o777, 1000, 1000)
    with pytest.raises(ValueError, match='untrusted-path|unsafe-directory-entry'):
        scene.helper.directory_layout(config, [scene.record])


@pytest.mark.parametrize('role', ['manager', 'gate'])
def test_classification_non_utf8_name_reaches_actual_publication(classification_preparation, role):
    scene = classification_preparation
    sibling = scene.physical('/usr/lib/polkit-1') / os.fsdecode(b'vendor-\xff')
    sibling.write_bytes(b'ambient bytes must never be read')
    sibling.chmod(0o644)
    scene.helper.prepare(role)
    bindings = scene.bindings.read_bytes()
    assert b'ONPC-KIOSK\t1\tapparmor\t' + role.encode() + b'\t' in bindings
    assert b'vendor-' not in bindings
    generation = next(path for path in scene.runtime.iterdir() if len(path.name) == 64)
    layout = json.loads((generation / 'records.json').read_text())['layout']
    assert all('vendor-' not in entry['path'] for entry in layout)
    assert not (generation / 'tree/lib/polkit-1' / sibling.name).exists()
    assert sibling.read_bytes() == b'ambient bytes must never be read'


CLASSIFICATION_CASES = [
    ('directory', 'owner', 'empty-directory'),
    ('directory', 'group-write', 'empty-directory'),
    ('directory', 'world-write', 'empty-directory'),
    ('file', 'owner', None), ('file', 'group-write', None), ('file', 'world-write', None),
    ('link', 'owner', None), ('fifo', 'safe', None),
    ('file', 'tab-name', None), ('file', 'newline-name', None),
    ('file', 'control-name', None), ('file', 'delete-name', None),
    ('file', 'non-utf8-name', None), ('directory', 'non-utf8-name', None),
    ('link', 'tab-target', None), ('link', 'newline-target', None),
    ('link', 'control-target', None), ('link', 'non-utf8-target', None),
    ('file', 'metadata-denied', None), ('directory', 'metadata-denied', None),
    ('file', 'disappeared', None), ('link', 'readlink-denied', None),
    ('link', 'readlink-disappeared', None),
]


@pytest.mark.parametrize('kind,fault,expected', CLASSIFICATION_CASES)
@pytest.mark.parametrize('required', [False, True], ids=['ambient', 'required'])
def test_classification_independent_required_and_ambient_inputs(
        classification_preparation, monkeypatch, capfd, kind, fault, expected, required):
    scene = classification_preparation
    helper = scene.helper
    names = {'tab-name': 'vendor\titem', 'newline-name': 'vendor\nitem',
             'control-name': 'vendor\ritem', 'delete-name': 'vendor\x7fitem',
             'non-utf8-name': os.fsdecode(b'vendor-\xff')}
    path = Path('/usr/lib/polkit-1') / names.get(fault, 'vendor-item')
    source = scene.physical(path)
    target = {'tab-target': 'vendor\titem', 'newline-target': 'vendor\nitem',
              'control-target': 'vendor\ritem',
              'non-utf8-target': os.fsdecode(b'vendor-\xff')}.get(
                  fault, 'polkit-agent-helper-1')
    if kind == 'directory':
        source.mkdir(mode=0o755)
        (source / 'private-content').write_bytes(b'never enumerate masked descendants')
    elif kind == 'link':
        source.symlink_to(target)
    elif kind == 'fifo':
        os.mkfifo(source, 0o644)
    else:
        source.write_bytes(b'never read ambient contents')
        source.chmod(0o644)
    if fault in ('owner', 'group-write', 'world-write'):
        mode = 0o755 if kind == 'directory' else 0o777 if kind == 'link' else 0o644
        mode |= 0o020 if fault == 'group-write' else 0o002 if fault == 'world-write' else 0
        scene.faults[path] = (mode, 1000 if fault == 'owner' else 0, 1000)
    if fault in ('metadata-denied', 'disappeared', 'readlink-denied', 'readlink-disappeared'):
        operation = 'readlink' if fault.startswith('readlink') else 'metadata'
        error = FileNotFoundError(2, 'private disappearing entry') if 'disappeared' in fault else PermissionError(13, 'private unavailable entry')
        scene.failures[operation, path] = error
    records = [scene.record]
    config = dict(scene.config)
    if required:
        if kind == 'directory':
            config['reserved_directories'] = [str(path)]
        elif kind == 'link':
            config['executables'] = [dict(role='service', paths=[str(path)])]
        else:
            records.append(dict(path=str(path)))
    original_open = Path.open

    def no_contents(path, *args, **kwargs):
        assert path != source, 'classification read an ambient or rejected input'
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(helper.Path, 'open', no_contents)
    if required:
        with pytest.raises((ValueError, OSError)):
            helper.directory_layout(config, records)
    else:
        layout = helper.directory_layout(config, records)
        entry = next((entry for entry in layout if entry['path'] == str(path)), None)
        assert entry == (dict(path=str(path), kind=expected) if expected else None)
        assert path not in scene.visited
        # Exercise actual manager and gate generation and protocol publication,
        # rather than accepting a layout that the binder cannot represent.
        for role in ('manager', 'gate'):
            helper.prepare(role)
            rows = [row.split('\t') for row in scene.bindings.read_text().splitlines()]
            assert all(row[3] != str(path) for row in rows if row[0] == 'bind')
            generation = scene.runtime / rows[0][4]
            private = generation / 'tree' / path.relative_to('/usr')
            if expected == 'empty-directory':
                assert private.is_dir() and list(private.iterdir()) == []
            else:
                assert not private.exists() and not private.is_symlink()
    assert 'vendor' not in capfd.readouterr().err


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('fault', ['missing', 'link', 'directory', 'masked', 'duplicate-file',
                                  'duplicate-link', 'disappeared-and-restored'])
def test_classification_requires_every_native_destination_before_publication(
        preserved_password_preparation, tmp_path, monkeypatch, role, fault):
    scene = preserved_password_preparation
    source = tmp_path / 'measured-native'
    source.write_bytes(b'\x7fELFmeasured substitute remains present')
    source.chmod(0o755)
    path = '/usr/bin/required-native'
    installed = tmp_path / path.lstrip('/')
    installed.parent.mkdir(mode=0o755)
    installed.write_bytes(source.read_bytes())
    installed.chmod(0o755)
    record = dict(role='service', path=path, source=str(source),
                  sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    scene.layout.append(dict(path='/usr/bin', kind='tree'))
    if fault not in ('missing', 'disappeared-and-restored'):
        kind = {'masked': 'empty-directory', 'directory': 'directory', 'link': 'link'}.get(fault, 'file')
        scene.layout.append(dict(path=path, kind=kind, **({'link': 'other'} if kind == 'link' else {})))
        if fault.startswith('duplicate'):
            scene.layout.append(dict(path=path, kind='file' if fault == 'duplicate-file' else 'link',
                                     **({'link': 'other'} if fault == 'duplicate-link' else {})))
    monkeypatch.setattr(scene.helper, 'inventory', lambda config: [record])

    def collect(config, records):
        assert records == [record, scene.record]
        if fault == 'disappeared-and-restored':
            # The layout missed a transient absent destination. Its return does
            # not prove completeness even when that pathname is restored.
            installed.unlink()
            assert not installed.exists()
            installed.write_bytes(source.read_bytes())
            installed.chmod(0o755)
        return scene.layout
    monkeypatch.setattr(scene.helper, 'directory_layout', collect)
    with pytest.raises(ValueError, match='layout|coverage|unsafe-directory-entry'):
        scene.helper.prepare(role)
    assert source.read_bytes() == installed.read_bytes() == b'\x7fELFmeasured substitute remains present'
    assert (scene.runtime / 'bindings').read_text() == 'previous bindings\n'
    assert not scene.bindings.exists()
    assert not any(len(item.name) == 64 for item in scene.runtime.iterdir())
    assert scene.manager_checks == scene.reclaims == []


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('required', [False, True], ids=['ambient', 'required'])
def test_classification_disappearance_reappearance_at_directory_snapshot(
        classification_preparation, monkeypatch, role, required):
    scene = classification_preparation
    path = Path(scene.path) if required else Path('/usr/lib/polkit-1/vendor-transient')
    source = scene.physical(path)
    if not required:
        source.write_bytes(b'private transient sibling')
        source.chmod(0o644)
    contents, mode = source.read_bytes(), stat.S_IMODE(source.stat().st_mode)
    original_entries, collect = Path.iterdir, scene.helper.directory_layout
    removed = []

    def entries(directory):
        children = list(original_entries(directory))
        if directory == path.parent and path in children:
            source.unlink()
            removed.append(path)
        return iter(children)

    def snapshot(config, records):
        try:
            return collect(config, records)
        finally:
            # Restore after classification, before binding publication: a
            # pathname reappearing cannot supply a missing layout assertion.
            source.write_bytes(contents)
            source.chmod(mode)
    monkeypatch.setattr(scene.helper.Path, 'iterdir', entries)
    monkeypatch.setattr(scene.helper, 'directory_layout', snapshot)
    if required:
        with pytest.raises((ValueError, OSError)):
            scene.helper.prepare(role)
        assert not scene.bindings.exists()
        assert (scene.runtime / 'bindings').read_text() == 'previous bindings\n'
    else:
        scene.helper.prepare(role)
        assert 'vendor-transient' not in scene.bindings.read_text()
    assert removed
    assert source.read_bytes() == contents


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('denied', [False, True], ids=['ambient-admitted', 'required-denied'])
def test_classification_logging_failure_preserves_actual_admission(
        classification_preparation, monkeypatch, role, denied):
    scene = classification_preparation
    path = Path(scene.path) if denied else Path('/usr/lib/polkit-1/vendor-masked')
    if not denied:
        scene.physical(path).mkdir(mode=0o755)
    if denied:
        requirements = scene.helper.layout_requirements
        def drift_after_proof(*args):
            result = requirements(*args)
            scene.faults[path] = (0o664, 0, 0)
            return result
        monkeypatch.setattr(scene.helper, 'layout_requirements', drift_after_proof)
    else:
        scene.faults[path] = (0o775, 0, 0)
    original_write = scene.helper.os.write
    attempts = []

    def closed_log(fd, data):
        if fd == 2:
            attempts.append(data)
            raise BrokenPipeError(32, 'private closed diagnostics')
        return original_write(fd, data)
    monkeypatch.setattr(scene.helper.os, 'write', closed_log)
    if denied:
        with pytest.raises(ValueError, match='untrusted-path|unsafe-directory-entry'):
            scene.helper.prepare(role)
        assert not scene.bindings.exists()
    else:
        scene.helper.prepare(role)
        assert b'vendor-masked' not in b'\n'.join(
            row for row in scene.bindings.read_bytes().splitlines() if row.startswith(b'bind\t'))
    assert attempts


@pytest.mark.parametrize('role', ['manager', 'gate'])
def test_classification_healthy_directory_alias_reaches_actual_publication(
        classification_preparation, native_mount_binding, monkeypatch, role):
    scene = classification_preparation
    root = scene.physical('/usr')
    (root / 'bin').mkdir(mode=0o755)
    source = root / 'bin/program'
    source.write_bytes(b'\x7fELFprivate alias program')
    source.chmod(0o755)
    (root / 'alias-bin').symlink_to('bin', target_is_directory=True)
    scene.config['executables'] = [dict(role='service', paths=['/usr/alias-bin/program'])]
    scene.configure()
    record = dict(role='service', path='/usr/bin/program', source=str(source),
                  sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    monkeypatch.setattr(scene.helper, 'inventory', lambda config: [record])
    scene.helper.prepare(role)
    rows = [row.split('\t') for row in scene.bindings.read_text().splitlines()]
    generation = scene.runtime / rows[0][4]
    assert ['node', 'link', 'alias-bin', 'bin'] in rows
    assert ['proof', 'link', '/usr/alias-bin', 'bin'] in rows
    assert ['proof', 'file', '/usr/alias-bin/program', '-'] in rows
    assert ['bind', 'required', 'file', str(generation / '0'), 'bin/program', '-'] in rows
    assert (generation / 'tree/alias-bin').is_symlink()
    consumed = NATIVE_RUN([str(native_mount_binding), str(scene.bindings), 'none',
                          str(scene.runtime.parent), role, '/usr/bin/program'],
                         capture_output=True, text=True, timeout=5)
    assert consumed.returncode == 0, consumed.stdout + consumed.stderr
    assert 'fd-balance:0' in consumed.stdout.splitlines()
    assert os.readlink(scene.runtime / 'native-view/tree/alias-bin') == 'bin'
    assert source.read_bytes() == b'\x7fELFprivate alias program'


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('selected', [False, True], ids=['never-installed', 'selected-then-removed'])
def test_classification_optional_alias_selected_by_real_inventory_stays_required(
        classification_preparation, monkeypatch, role, selected):
    scene = classification_preparation
    root = scene.physical('/usr')
    (root / 'bin').mkdir(mode=0o755)
    source = root / 'bin/program'
    source.write_bytes(b'\x7fELFprivate optional native')
    source.chmod(0o755)
    alias = root / 'optional-program'
    if selected:
        alias.symlink_to('bin/program')
    scene.config['executables'] = [dict(role='service', paths=['/usr/optional-program'], optional=True)]
    scene.configure()

    def measured(role, path):
        canonical = scene.real_trusted(scene.physical(path), symlinks=True)
        record = scene.real_source_record(role, canonical)
        record['path'] = '/usr/' + str(canonical.relative_to(root))
        return record
    monkeypatch.setattr(scene.helper, 'source_record', measured)
    records = scene.real_inventory(scene.config)
    if selected:
        assert len(records) == 1
        assert records[0]['path'] == '/usr/bin/program'
        assert records[0]['aliases'] == ['/usr/optional-program']
        alias.unlink()
    else:
        assert records == []
    monkeypatch.setattr(scene.helper, 'inventory', lambda config: records)
    if selected:
        with pytest.raises((ValueError, OSError)):
            scene.helper.prepare(role)
        assert not scene.bindings.exists()
        assert scene.manager_checks == scene.reclaims == []
    else:
        scene.helper.prepare(role)
        assert 'optional-program' not in scene.bindings.read_text()
    assert source.read_bytes() == b'\x7fELFprivate optional native'


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('retarget', [False, True], ids=['healthy', 'final-proof-retarget'])
def test_classification_reserved_directory_alias_and_final_proof_drift(
        classification_preparation, monkeypatch, role, retarget):
    scene = classification_preparation
    alias = scene.physical('/usr/alias-data')
    original = 'share/oh-no-parent-control'
    alias.symlink_to(original, target_is_directory=True)
    scene.config['reserved_directories'] = ['/usr/alias-data/confinement']
    scene.configure()
    proofs = scene.helper.required_proofs
    changed = []

    def final_proofs(paths):
        paths = list(paths)
        # Only the final publication proof includes the private generation
        # marker's replacement source. Keep every earlier layout proof healthy.
        if retarget and any(Path(path).name == 'generation' and
                            Path(path).parent.parent == scene.runtime for path in paths):
            alias.unlink()
            alias.symlink_to('share/./oh-no-parent-control', target_is_directory=True)
            changed.append(True)
        return proofs(paths)
    monkeypatch.setattr(scene.helper, 'required_proofs', final_proofs)
    try:
        if retarget:
            with pytest.raises(ValueError, match='binding-proof-changed'):
                scene.helper.prepare(role)
            assert changed
            assert not scene.bindings.exists()
        else:
            scene.helper.prepare(role)
            rows = [row.split('\t') for row in scene.bindings.read_text().splitlines()]
            assert ['root', 'reserved', '/usr/share/oh-no-parent-control/confinement', '-'] in rows
            assert ['proof', 'link', '/usr/alias-data', original] in rows
            assert ['proof', 'directory', '/usr/alias-data/confinement', '-'] in rows
            assert ['node', 'link', 'alias-data', original] in rows
    finally:
        alias.unlink()
        alias.symlink_to(original, target_is_directory=True)


@pytest.mark.parametrize('fault', ['config', 'policy', 'empty', 'extra', 'missing-newline', 'malformed'])
def test_preparation_refuses_snapshot_changed_after_verification_before_inventory(
        preserved_password_preparation, monkeypatch, fault):
    scene = preserved_password_preparation
    helper = scene.helper
    verify = helper.subprocess.run
    before = (scene.runtime / 'bindings').read_bytes()

    def interrupted(*args, **kwargs):
        result = verify(*args, **kwargs)
        if fault in ('config', 'policy'):
            path = scene.payload / ('config.json' if fault == 'config' else 'onpc-kiosk.apparmor')
            path.write_bytes(path.read_bytes() + b'\n')
        else:
            result.stdout = {'empty': '', 'extra': result.stdout + 'unexpected\n',
                             'missing-newline': result.stdout.rstrip('\n'),
                             'malformed': 'not an attestation\n'}[fault]
        return result

    monkeypatch.setattr(helper.subprocess, 'run', interrupted)
    monkeypatch.setattr(helper, 'inventory', lambda config: pytest.fail('unattested snapshot reached inventory'))
    with pytest.raises(ValueError, match='policy-snapshot-not-attested'):
        helper.prepare('manager')
    assert (scene.runtime / 'bindings').read_bytes() == before
    assert scene.manager_checks == scene.reclaims == []
    assert sorted(item.name for item in scene.runtime.iterdir()) == ['bindings']


def test_preparation_swaps_independent_bubblewrap_copies_only_in_private_tree(
        preserved_password_preparation, tmp_path, monkeypatch):
    model = preserved_password_preparation
    helper = model.helper
    records = []
    for name, role, target in (
            ('launcher', 'bwrap', '/usr/bin/bwrap'),
            ('native', 'bwrap-native', '/usr/libexec/oh-no-parent-control-kiosk-bwrap')):
        source = tmp_path / name
        source.write_bytes(b'\x7fELFprivate ' + name.encode())
        source.chmod(0o755)
        installed = tmp_path / target.lstrip('/')
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.parent.chmod(0o755)
        installed.write_bytes(source.read_bytes())
        installed.chmod(0o755)
        records.append(dict(role=role, path=target, source=str(source),
                            sha256=helper.hashlib.sha256(source.read_bytes()).hexdigest()))
    originals = {record['source']: Path(record['source']).read_bytes() for record in records}
    model.layout += [dict(path='/usr/bin', kind='tree'), dict(path='/usr/libexec', kind='tree')]
    model.layout += [dict(path=record['path'], kind='file') for record in records]
    monkeypatch.setattr(helper, 'inventory', lambda config: records)
    def layout(config, observed):
        assert observed == [*records, model.record]
        return model.layout
    monkeypatch.setattr(helper, 'directory_layout', layout)
    helper.prepare('manager')
    generation = next(path for path in model.runtime.iterdir() if len(path.name) == 64)
    bindings = model.bindings.read_text()
    for index, record in enumerate(records):
        copy = generation / str(index)
        assert copy.read_bytes() == originals[record['source']]
        assert copy.stat().st_ino != Path(record['source']).stat().st_ino
        target = record['path'].removeprefix('/usr/')
        assert f'bind\trequired\tfile\t{copy}\t{target}\t-\n' in bindings
    assert json.loads((generation / 'records.json').read_text())['records'] == records
    helper.prepare('gate')
    assert model.bindings.read_text().splitlines()[1:] == bindings.splitlines()[1:]
    assert {path: Path(path).read_bytes() for path in originals} == originals


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('fault', ['missing', 'link', 'directory', 'duplicate-file', 'duplicate-link'])
def test_preserved_password_helper_preparation_refuses_missing_or_ambiguous_signed_binding(
        preserved_password_preparation, role, fault):
    model = preserved_password_preparation
    if fault == 'missing':
        model.layout[:] = [entry for entry in model.layout if entry['path'] != model.path]
    elif fault in ('link', 'directory'):
        entry = next(entry for entry in model.layout if entry['path'] == model.path)
        entry['kind'] = fault
        if fault == 'link':
            entry['link'] = 'replacement-helper'
    else:
        model.layout.append(dict(path=model.path, kind='file' if fault == 'duplicate-file' else 'link',
                                 **({'link': 'replacement-helper'} if fault == 'duplicate-link' else {})))
    with pytest.raises(ValueError, match='preserved-executable-layout'):
        model.helper.prepare(role)
    assert (model.runtime / 'bindings').read_text() == 'previous bindings\n'
    assert {item.name for item in model.runtime.iterdir()} <= {'bindings', 'native-view'}
    assert model.manager_checks == model.reclaims == []


@pytest.mark.parametrize('role', ['manager', 'gate'])
def test_preserved_password_helper_preparation_publishes_exactly_one_inode_signed_binding(
        preserved_password_preparation, role):
    model = preserved_password_preparation
    model.helper.prepare(role)
    lines = model.bindings.read_text().splitlines()
    header = lines[0].split('\t')
    assert header[:4] == ['ONPC-KIOSK', '1', 'apparmor', role]
    signed = [line for line in lines if line.startswith('bind\trequired\tfile\t' + model.path + '\t')]
    assert len(signed) == 1
    _, _, _, source, destination, assertion = signed[0].split('\t')
    assert source == model.path
    assert assertion == ' '.join(map(str, model.identities[model.path]))
    generation = model.runtime / header[4]
    assert destination == 'lib/polkit-1/polkit-agent-helper-1'
    assert lines[-1] == 'attach\t/usr'
    assert json.loads((generation / 'records.json').read_text())['preserved'] == [model.record]
    assert len(model.manager_checks) == (1 if role == 'gate' else 0)
    assert model.reclaims == [True]
    # Reusing a stable generation must retain the same single signed binding.
    model.helper.prepare(role)
    assert model.bindings.read_text().splitlines() == lines
    assert {item.name for item in model.runtime.iterdir()} == {'bindings', 'native-view', generation.name}


@pytest.mark.parametrize('sibling_kind,mode,gid,uid,scope,expected', [
    ('directory', 0o755, 0, 0, 'sibling', 'directory'),
    ('directory', 0o775, 0, 0, 'sibling', 'empty-directory'),
    ('directory', 0o775, 12345, 0, 'sibling', 'empty-directory'),
    ('directory', 0o777, 0, 0, 'sibling', 'empty-directory'),
    ('directory', 0o755, 1000, 1000, 'sibling', 'empty-directory'),
    ('directory', 0o700, 12345, 12345, 'sibling', 'empty-directory'),
    ('directory', 0o555, 0, 12345, 'sibling', 'empty-directory'),
    ('directory', 0o775, 12345, 12345, 'sibling', 'empty-directory'),
    ('directory', 0o777, 12345, 12345, 'sibling', 'empty-directory'),
    ('directory', 0o775, 0, 0, 'reserved', None),
    ('directory', 0o775, 0, 0, 'executable-parent', None),
    ('directory', 0o755, 1000, 1000, 'reserved', None),
    ('directory', 0o755, 1000, 1000, 'executable-parent', None),
    ('file', 0o664, 0, 0, 'sibling', 'absent'),
    ('file', 0o644, 12345, 0, 'sibling', 'file'),
    ('file', 0o644, 1000, 1000, 'sibling', 'absent'),
    ('file', 0o644, 1000, 1000, 'required-file', None),
    ('file', 0o664, 0, 0, 'required-file', None),
    ('link', 0o777, 0, 0, 'sibling', 'link'),
    ('link', 0o777, 1000, 1000, 'sibling', 'absent'),
    ('link', 0o777, 1000, 1000, 'alias', None),
    ('fifo', 0o644, 0, 0, 'sibling', 'absent'),
    ('fifo', 0o644, 1000, 1000, 'sibling', 'absent'),
    ('directory-tab', 0o755, 0, 0, 'sibling', 'absent'),
    ('directory-newline', 0o755, 1000, 1000, 'sibling', 'absent'),
    ('directory-tab', 0o755, 0, 0, 'reserved', None),
])
@pytest.mark.parametrize('sibling_parent', ('/usr/lib/polkit-1', '/usr/share', '/usr/bin'))
def test_preserved_password_helper_parent_contributes_real_private_directory_layout(
        tmp_path, monkeypatch, request, capfd, sibling_kind, mode, gid, uid, scope, expected,
        sibling_parent):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    private_root = tmp_path / 'private-root'
    source = private_root / 'usr/lib/polkit-1/polkit-agent-helper-1'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'\x7fELFprivate preserved helper')
    executable = private_root / 'usr/bin/required-native'
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b'\x7fELFprivate native executable')
    sibling_root = private_root / sibling_parent.lstrip('/')
    sibling_root.mkdir(parents=True, exist_ok=True)
    name = {'directory-tab': 'vendor\tdata', 'directory-newline': 'vendor\ndata'}.get(
        sibling_kind, 'vendor-data' if sibling_kind == 'directory' else 'vendor-file')
    sibling = sibling_root / name
    if sibling_kind.startswith('directory'):
        sibling.mkdir()
        (sibling / 'uncovered').write_text('private sibling')
    elif sibling_kind == 'file':
        sibling.touch()
    elif sibling_kind == 'link':
        sibling.symlink_to('vendor-data')
    else:
        os.mkfifo(sibling)
    payload = private_root / 'usr/share/oh-no-parent-control/confinement'
    payload.mkdir(parents=True)
    (payload / 'generation').touch()
    for path in private_root.rglob('*'):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)
    if sibling_kind != 'link':
        sibling.chmod(mode)
        # Read-only ownership cases must not leave pytest's private scratch
        # undeletable after success or the intentional pre-fix failure.
        request.addfinalizer(lambda: sibling.chmod(0o755))
    original_iterdir, original_lstat, original_readlink = Path.iterdir, Path.lstat, os.readlink
    visited = []

    def physical(path):
        assert path == Path('/usr') or Path('/usr') in path.parents
        return private_root / path.relative_to('/')

    def entries(path):
        if path != Path('/usr') and Path('/usr') not in path.parents:
            return original_iterdir(path)
        target = physical(path)
        visited.append(target)
        return iter(Path('/') / child.relative_to(private_root) for child in original_iterdir(target))

    def metadata(path):
        if path != Path('/usr') and Path('/usr') not in path.parents:
            return original_lstat(path)
        values = list(original_lstat(physical(path)))
        values[4] = uid if physical(path) == sibling else 0
        values[5] = gid if physical(path) == sibling else 0
        return os.stat_result(values)

    def readlink(path, *args, **kwargs):
        path = Path(path)
        if path == Path('/usr') or Path('/usr') in path.parents:
            path = physical(path)
        return original_readlink(path, *args, **kwargs)

    def trusted(path, *, directory=False, **kwargs):
        path = Path(path)
        info = original_lstat(physical(path))
        assert stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        return path

    monkeypatch.setattr(helper.Path, 'iterdir', entries)
    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    monkeypatch.setattr(helper.os, 'readlink', readlink)
    monkeypatch.setattr(helper, 'trusted', trusted)
    sibling_path = sibling_parent + '/' + sibling.name
    config = {'reserved_directories': [sibling_path] if scope == 'reserved' else []}
    records = [{'path': '/usr/lib/polkit-1/polkit-agent-helper-1'},
               {'path': '/usr/bin/required-native'}]
    if scope == 'executable-parent':
        (sibling / 'another-executable').write_bytes(b'\x7fELFprivate required executable')
        (sibling / 'another-executable').chmod(0o755)
        records.append({'path': sibling_path + '/another-executable'})
    elif scope == 'required-file':
        records.append({'path': sibling_path})
    elif scope == 'alias':
        config['executables'] = [{'paths': [sibling_path]}]
    if expected is None:
        with pytest.raises(ValueError, match='untrusted-path|unsafe-directory-entry|binding-protocol-path'):
            helper.directory_layout(config, records)
        return
    layout = helper.directory_layout(config, records)
    kinds = {entry['path']: entry['kind'] for entry in layout}
    assert kinds['/usr/lib'] == kinds['/usr/lib/polkit-1'] == 'tree'
    assert kinds['/usr/lib/polkit-1/polkit-agent-helper-1'] == 'file'
    if expected == 'absent':
        assert sibling_path not in kinds
    else:
        assert kinds[sibling_path] == expected
    assert sibling_path + '/uncovered' not in kinds
    assert source.parent in visited
    assert sibling not in visited
    diagnostic = capfd.readouterr().err
    assert 'vendor' not in diagnostic and str(uid) not in diagnostic


@pytest.mark.parametrize('name', ['code', 'gnome-shell', 'wireplumber'])
@pytest.mark.parametrize('role', ['manager', 'gate'])
def test_writable_sibling_contents_never_enter_private_generation_or_bindings(
        preserved_password_preparation, tmp_path, name, role, capfd):
    model = preserved_password_preparation
    # Model an unrelated application's data tree and consumed script/plugin
    # roots alike. A read-only alias would still expose their later changes.
    source = tmp_path / 'global' / name
    source.mkdir(parents=True)
    source.chmod(0o775)
    script = source / 'module.py'
    script.write_text('original host contents')
    model.layout += [{'path': '/usr/share/' + name, 'kind': 'empty-directory'}]
    model.helper.prepare(role)
    diagnostic = capfd.readouterr().err
    assert diagnostic.strip() == ('onpc.kiosk confinement directory-view outcome=masked '
                                  'reason=writable-sibling-directory count=1')
    generation = next(path for path in model.runtime.iterdir() if len(path.name) == 64)
    private = generation / 'tree/share' / name
    assert private.is_dir() and list(private.iterdir()) == []
    assert private.stat().st_ino != source.stat().st_ino
    assert stat.S_IMODE(private.stat().st_mode) == 0o755
    bindings = model.bindings.read_text().splitlines()
    # The native caller receives only the preserved helper and the final
    # private /usr root. Neither the global directory nor its private target
    # is a bind source/destination, even if it holds runtime script inputs.
    assert len([line for line in bindings if line.startswith('bind\t')]) == 2
    assert bindings[-1] == 'attach\t/usr'
    assert all('/usr/share/' + name not in line and str(private) not in line
               for line in bindings if line.startswith('bind\t'))
    script.unlink()
    script.symlink_to(tmp_path / 'replacement-script')
    (source / 'new-plugin').write_text('later host contents')
    model.helper.prepare(role)
    assert list(private.iterdir()) == []
    assert model.bindings.read_text().splitlines() == bindings
    # Generation validation must also reject contamination of the placeholder.
    (private / 'unexpected-script').write_text('private contamination')
    with pytest.raises(ValueError, match='directory-generation-changed'):
        model.helper.prepare(role)


@pytest.fixture(scope='module')
def native_preserved_identity(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-preserved-identity')
    header = (ROOT / 'tools/kiosk_confinement.h').read_text()
    function = header.split('static int\npreserved_kiosk_identity', 1)[1].split(
        '\nstatic int\nbind_kiosk_executables', 1)[0]
    source = directory / 'identity.c'
    source.write_text('#define _GNU_SOURCE\n#include <sys/stat.h>\n#include <stdio.h>\n#include <string.h>\n'
        'static int\npreserved_kiosk_identity' + function + '\n'
        'int main(int argc, char **argv) {\n'
        '    struct stat info;\n'
        '    if (argc != 3 || stat(argv[1], &info) != 0) return 2;\n'
        '    return preserved_kiosk_identity(&info, argv[2]) == 0 ? 0 : 1;\n}\n')
    executable = directory / 'identity'
    built = NATIVE_RUN(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-o',
                       str(executable), str(source)], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    return executable


@pytest.mark.parametrize('field', range(8), ids=[
    'device', 'inode', 'size', 'mtime-ns', 'ctime-ns', 'mode', 'uid', 'gid',
])
def test_native_preserved_identity_checks_every_python_assertion_field(native_preserved_identity, tmp_path, field):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    source = tmp_path / 'helper'
    source.write_bytes(b'\x7fELFprivate vendor helper')
    source.chmod(0o755)
    assertion = list(helper.file_identity(source.stat()))
    def check(values):
        return subprocess.run([str(native_preserved_identity), str(source), ' '.join(map(str, values))],
                              capture_output=True, timeout=5).returncode
    assert check(assertion) == 0
    assertion[field] += 1
    assert check(assertion) == 1


@pytest.mark.parametrize('fault', ['replacement', 'mode', 'content', 'mtime'])
def test_native_preserved_identity_refuses_real_post_measurement_file_changes(
        native_preserved_identity, tmp_path, fault):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    source = tmp_path / 'helper'
    source.write_bytes(b'\x7fELFprivate vendor helper')
    source.chmod(0o755)
    measured = source.stat()
    assertion = ' '.join(map(str, helper.file_identity(measured)))
    if fault == 'replacement':
        replacement = source.with_name('replacement')
        replacement.write_bytes(source.read_bytes())
        replacement.chmod(0o755)
        replacement.replace(source)
    elif fault == 'mode':
        source.chmod(0o4755)
    elif fault == 'content':
        source.write_bytes(b'\x7fELFchanged vendor helper')
        # Same length and restored mtime still leave the changed ctime.
        assert source.stat().st_size == measured.st_size
        os.utime(source, ns=(measured.st_atime_ns, measured.st_mtime_ns))
    else:
        os.utime(source, ns=(measured.st_atime_ns, measured.st_mtime_ns + 1))
    result = subprocess.run([str(native_preserved_identity), str(source), assertion],
                            capture_output=True, timeout=5)
    assert result.returncode == 1


@pytest.mark.parametrize('fault', ['missing-field', 'extra-field', 'trailing-space', 'nonnumeric', 'plus-sign', 'negative-zero', 'tab',
    *['overflow-' + str(field) for field in range(8)]])
def test_native_preserved_identity_refuses_malformed_assertions(native_preserved_identity, tmp_path, fault):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    source = tmp_path / 'helper'
    source.write_bytes(b'\x7fELFprivate vendor helper')
    values = list(map(str, helper.file_identity(source.stat())))
    if fault == 'missing-field':
        values.pop()
    elif fault == 'extra-field':
        values.append('0')
    elif fault == 'nonnumeric':
        values[0] = 'untrusted'
    elif fault == 'plus-sign':
        values[0] = '+' + values[0]
    elif fault == 'negative-zero':
        values[-1] = '-0'
    elif fault.startswith('overflow-'):
        values[int(fault.removeprefix('overflow-'))] = str(2**64)
    assertion = ' '.join(values) + (' ' if fault == 'trailing-space' else '')
    if fault == 'tab':
        assertion = assertion.replace(' ', '\t', 1)
    result = subprocess.run([str(native_preserved_identity), str(source), assertion],
                            capture_output=True, timeout=5)
    assert result.returncode == 1


@pytest.fixture(scope='module')
def native_mount_binding(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-mount-binding')
    header = (ROOT / 'tools/kiosk_confinement.h').read_text()
    functions = header[header.index('/* The namespace, filesystem and every mount below it belong'):].split(
        '\nstatic int\napply_kiosk_mac', 1)[0]
    functions = functions.replace(
        'fstat(child, &info) != 0 || !kiosk_trusted_stat(&info, kiosk_kind(proof->v[1])))\n            goto done;',
        'fstat(child, &info) != 0 || !kiosk_trusted_stat(&info, kiosk_kind(proof->v[1]))) {\n'
        '            fprintf(stderr, "fixture-proof:%s present=%d fd=%d mode=%o uid=%u\\n", next_path, '
        'proof != NULL, child, (unsigned) info.st_mode, (unsigned) info.st_uid); goto done; }')
    functions = functions.replace('if (!valid)\n            return -1;',
        'if (!valid) { fprintf(stderr, "fixture-node:%s mode=%o uid=%u\\n", node->v[2], '
        '(unsigned) info.st_mode, (unsigned) info.st_uid); return -1; }')
    # Arm real mutations only when native consumption reaches source-state
    # checking, after independent required-proof/target validation has finished.
    functions = functions.replace('struct stat named;', 'struct stat named; fixture_source_boundary = 1;')
    functions = functions.replace('goto done;',
        '{ fprintf(stderr, "fixture-stop:%s:%d\\n", __func__, __LINE__); goto done; }')
    functions = functions.replace('return -1;', 'return fixture_refuse(__func__, __LINE__);')
    functions = ('#line ' + str(header[:header.index('/* The namespace, filesystem and every mount below it belong')].count('\n') + 1)
                 + ' "kiosk_confinement.h"\n' + functions)
    preparation = ('static int\nprepare_kiosk_confinement' + header.split(
        'static int\nprepare_kiosk_confinement', 1)[1].split(
        '/* The namespace, filesystem and every mount below it belong', 1)[0])
    source = directory / 'binding.c'
    source.write_text(r'''
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/xattr.h>
#include <stdint.h>
#include <dirent.h>
#include <dlfcn.h>
#include <time.h>
#include <signal.h>
#include <stdarg.h>
#include <syslog.h>
#include <sys/wait.h>
#include <unistd.h>
static const char *manifest, *fault, *fixture_root, *caller, *drift_source;
static const char *diagnostic_mode;
static unsigned diagnostic_attempts;
typedef void pam_handle_t;
static void pam_syslog(pam_handle_t *handle, int priority, const char *format, ...) {
    (void) handle; (void) priority;
    diagnostic_attempts++;
    if (strcmp(diagnostic_mode, "discard") != 0) {
        va_list arguments;
        va_start(arguments, format);
        printf("native-record:"); vprintf(format, arguments); putchar('\n');
        va_end(arguments);
    }
    /* A failed log transport can change errno even though pam_syslog has no
     * return value. Production must preserve both native result and errno. */
    errno = EPIPE;
}
static char runtime_path[PATH_MAX], view_path[PATH_MAX], helper_path[PATH_MAX];
static unsigned source_checks, source_opens;
static int fixture_source_boundary;
static int cloned, readonly, private_mount;
static int clone_source = -1;
static int namespace_changed;
static char mounted_paths[64][PATH_MAX];
static int mounted_sources[64], mounted_live[64], mounted_descriptors[4096];
static unsigned mount_queries[64];
static unsigned mount_count;
static int fixture_refuse(const char *function, int line) {
    fprintf(stderr, "fixture-refuse:%s:%d errno=%d\n", function, line, errno);
    return -1;
}
static unsigned descriptor_count(void) {
    DIR *directory = opendir("/proc/self/fd");
    if (!directory) exit(2);
    unsigned count = 0; struct dirent *entry;
    while ((entry = readdir(directory)) != NULL)
        if (strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) count++;
    closedir(directory); return count;
}
static int fixture_selinux(void) { return strncmp(fault, "setup-selinux", 13) == 0; }
static void *fixture_dlopen(const char *name, int flags) { (void) name; (void) flags; return (void *) 1; }
static void *fixture_dlsym(void *library, const char *name) { (void) library; (void) name; return (void *) fixture_selinux; }
static int fixture_dlclose(void *library) { (void) library; return 0; }
static ssize_t fixture_getxattr(const char *path, const char *name, void *buffer, size_t size) {
    (void) path; (void) name;
    const char context[] = "system_u:object_r:onpc_kiosk_runtime_t:s0";
    if (strcmp(fault, "setup-selinux-label") == 0 || size < sizeof(context)) { errno = EIO; return -1; }
    memcpy(buffer, context, sizeof(context)); return sizeof(context);
}
static FILE *fixture_fopen(const char *path, const char *mode) {
    if (strcmp(path, "/proc/self/mountinfo") != 0) return fopen(path, mode);
    static char contents[PATH_MAX + 512];
    const char *options = strcmp(fault, "setup-selinux-options") == 0 ? "rw" :
        strcmp(fault, "setup-selinux-override") == 0 ? "rw,context=system_u:object_r:onpc_kiosk_runtime_t:s0" :
        "rw,fscontext=system_u:object_r:tmpfs_t:s0,rootcontext=system_u:object_r:onpc_kiosk_runtime_t:s0";
    int size = snprintf(contents, sizeof(contents), "2 1 0:1 / %s rw - tmpfs tmpfs %s\n", view_path, options);
    if (size < 0 || size >= (int) sizeof(contents)) exit(2);
    return fmemopen(contents, (size_t) size, "r");
}
static int fixture_clock(clockid_t clock, struct timespec *value) {
    static unsigned calls;
    if (clock_gettime(clock, value) != 0) return -1;
    if (strcmp(fault, "helper-timeout") == 0 && calls++ > 0) value->tv_sec += 61;
    return 0;
}
static int fixture_kill(pid_t pid, int signal) {
    printf("killed:%ld\n", (long) pid); return kill(pid, signal);
}
static pid_t fixture_waitpid(pid_t pid, int *status, int flags) {
    pid_t result = waitpid(pid, status, flags);
    if (result == pid) printf("reaped:%ld\n", (long) pid);
    return result;
}
static char mapped[PATH_MAX];
static const char *physical(const char *path) {
    if (strncmp(path, "/usr", 4) == 0) {
        snprintf(mapped, sizeof(mapped), "%s%s", fixture_root, path);
        return mapped;
    }
    return path;
}
static const char *logical(const char *path) {
    return strncmp(path, fixture_root, strlen(fixture_root)) == 0 &&
        strncmp(path + strlen(fixture_root), "/usr", 4) == 0
        ? path + strlen(fixture_root) : path;
}
static void fd_name(int fd, char *path) {
    char name[64];
    snprintf(name, sizeof(name), "/proc/self/fd/%d", fd);
    ssize_t length = readlink(name, path, PATH_MAX - 1);
    if (length < 0) { path[0] = 0; return; }
    path[length] = 0;
}
static void mutate_source(const char *path) {
    if (strncmp(fault, "real-", 5) != 0) return;
    unsigned boundary = strstr(fault, "-post") ? 3U : strstr(fault, "-pre") ? 2U : 1U;
    if (source_checks != boundary) return;
    char replacement[PATH_MAX];
    if (strstr(fault, "mode")) { if (chmod(path, 0666) != 0) exit(2); }
    else if (strstr(fault, "owner")) { /* Root identity is a metadata double below. */ }
    else if (strstr(fault, "vanish")) {
        struct stat info;
        if (lstat(path, &info) != 0) exit(2);
        if (S_ISDIR(info.st_mode)) {
            if (snprintf(replacement, sizeof(replacement), "%s/unreviewed-data", path) >= PATH_MAX ||
                unlink(replacement) != 0 || rmdir(path) != 0) exit(2);
        } else if (unlink(path) != 0) exit(2);
    }
    else {
        if (snprintf(replacement, sizeof(replacement), "%s.retired", path) >= PATH_MAX) exit(2);
        if (rename(path, replacement) != 0) exit(2);
        if (strstr(fault, "type")) { if (symlink("replacement", path) != 0) exit(2); }
        else if (!strstr(fault, "vanish")) {
            int fd = open(path, O_CREAT | O_EXCL | O_WRONLY, 0644);
            if (fd < 0 || write(fd, "replacement", 11) != 11 || close(fd) != 0) exit(2);
        }
    }
    printf("mutation:%u\n", source_checks);
}
static int fixture_open(const char *path, int flags) {
    if (strcmp(path, "/usr") == 0 && cloned) return dup(clone_source);
    if (strcmp(path, manifest) == 0) path = manifest;
    return open(physical(path), flags);
}
static int fixture_openat(int fd, const char *path, int flags, ...) {
    char parent[PATH_MAX]; fd_name(fd, parent);
    if (strcmp(parent, "/") == 0 && strcmp(path, "usr") == 0)
        return open(physical("/usr"), flags);
    char full[PATH_MAX];
    if (path[0] == '/') snprintf(full, sizeof(full), "%s", path);
    else if (snprintf(full, sizeof(full), "%s/%s", logical(parent), path) >= PATH_MAX) exit(2);
    for (unsigned i = 0; i < mount_count; i++) if (mounted_live[i] && strcmp(full, mounted_paths[i]) == 0) {
        int result = dup(mounted_sources[i]);
        if (result >= 0 && result < 4096) mounted_descriptors[result] = 1;
        return result;
    }
    int result = openat(fd, path[0] == '/' ? physical(path) : path, flags);
    char name[PATH_MAX];
    fd_name(result, name);
    if (strcmp(logical(name), drift_source) == 0) source_opens++;
    return result;
}
static int metadata(const char *path, struct stat *info) {
    if (strcmp(fault, "metadata") == 0) errno = EACCES;
    info->st_uid = info->st_gid = 0;
    if (strncmp(path, "/usr", 4) != 0 && strncmp(path, fixture_root, strlen(fixture_root)) != 0)
        info->st_mode &= ~0022;
    if (strcmp(path, drift_source) == 0) {
        if (strcmp(fault, "source-missing") == 0 || strcmp(fault, "missing-target-unlink") == 0) {
            errno = ENOENT; return -1;
        }
        if (strncmp(fault, "error-", 6) == 0) {
            errno = atoi(fault + 6); return -1;
        }
        if (strcmp(fault, "source-owner") == 0) info->st_uid = 12345;
        if (strcmp(fault, "source-group") == 0) info->st_mode |= 0020;
        if (strcmp(fault, "source-world") == 0) info->st_mode |= 0002;
        if (strcmp(fault, "source-type") == 0) info->st_mode = S_IFLNK | 0777;
        if (strstr(fault, "real-owner") && source_checks >=
                (strstr(fault, "-post") ? 3U : strstr(fault, "-pre") ? 2U : 1U)) info->st_uid = 12345;
    }
    if (strcmp(path, "/usr/share/assets") == 0) {
        if (strcmp(fault, "root-group-directory") == 0 ||
            strcmp(fault, "other-group-directory") == 0)
            info->st_mode |= 0020;
        if (strcmp(fault, "other-group-directory") == 0) info->st_gid = 12345;
        if (strcmp(fault, "world-directory") == 0) info->st_mode |= 0002;
        if (strcmp(fault, "unowned-directory") == 0) info->st_uid = 12345;
    }
    if (strcmp(path, "/usr/bin/program") == 0 && strcmp(fault, "group-file") == 0)
        info->st_mode |= 0020;
    if (strstr(path, "/tree/share/assets") != NULL && strcmp(fault, "group-target") == 0)
        info->st_mode |= 0020;
    if (strstr(path, "/tree/bin/program") != NULL && strcmp(fault, "target-stat") == 0) {
        errno = EIO; return -1;
    }
    return 0;
}
static int fixture_fstat(int fd, struct stat *info) {
    char path[PATH_MAX]; fd_name(fd, path);
    if (fixture_source_boundary && fd < 4096 && !mounted_descriptors[fd] && strcmp(logical(path), drift_source) == 0) {
        source_checks++; mutate_source(path);
    }
    if (fstat(fd, info) != 0) return -1;
    if (strstr(path, "mnt:[")) {
        info->st_ino += namespace_changed;
        if (strcmp(fault, "cleanup-namespace") == 0 && readonly) {
            info->st_ino++;
            puts("namespace-witness:mismatch");
        }
    }
    return metadata(logical(path), info);
}
static int fixture_fstatat(int fd, const char *path, struct stat *info, int flags) {
    char parent[PATH_MAX], full[PATH_MAX];
    if (path[0] == '/') snprintf(full, sizeof(full), "%s", path);
    else {
        fd_name(fd, parent);
        if (snprintf(full, sizeof(full), "%s/%s", logical(parent), path) >= PATH_MAX) exit(2);
    }
    for (unsigned i = 0; i < mount_count; i++) if (mounted_live[i] && strcmp(full, mounted_paths[i]) == 0) {
        if (fstat(mounted_sources[i], info) != 0) return -1;
        return metadata(full, info);
    }
    if (fstatat(fd, path[0] == '/' ? physical(path) : path, info, flags) != 0) return -1;
    return metadata(full, info);
}
static int fixture_close(int fd) {
    if (fd >= 0 && fd < 4096) mounted_descriptors[fd] = 0;
    return close(fd);
}
static int fixture_unlinkat(int fd, const char *path, int flags) {
    if (strcmp(fault, "missing-target-unlink") == 0) { errno = EIO; return -1; }
    return unlinkat(fd, path, flags);
}
static int fixture_fstatfs(int fd, struct statfs *info) {
    if (fstatfs(fd, info) != 0) return -1;
    info->f_type = 0x01021994;
    info->f_bsize = 4096; info->f_blocks = 131072; info->f_files = 32776;
    if (strcmp(fault, "setup-storage") == 0) info->f_blocks++;
    if (strcmp(fault, "setup-inodes") == 0) info->f_files++;
    return 0;
}
static int fixture_unshare(int flags) {
    printf("namespace\n");
    if (strcmp(fault, "setup-namespace") == 0) { errno = EPERM; return -1; }
    namespace_changed = 1;
    return flags == CLONE_NEWNS ? 0 : -1;
}
static int fixture_mkdir(const char *path, mode_t mode) { return mkdir(physical(path), mode); }
static int fixture_statx(int fd, const char *path, int flags, unsigned mask, struct statx *info) {
    (void) fd; (void) flags; (void) mask;
    char buffer[PATH_MAX];
    int descriptor;
    if (sscanf(path, "/proc/self/fd/%d", &descriptor) == 1) { fd_name(descriptor, buffer); path = logical(buffer); }
    memset(info, 0, sizeof(*info)); info->stx_mask = STATX_MNT_ID; info->stx_mnt_id = 1;
    if (strstr(path, "/native-view") && private_mount) info->stx_mnt_id = 2;
    for (unsigned i = 0; i < mount_count; i++)
        if (mounted_live[i] && strcmp(path, mounted_paths[i]) == 0) {
            info->stx_mnt_id = 10 + i; mount_queries[i]++;
        }
    if (strcmp(path, "/usr") == 0 && cloned) info->stx_mnt_id = 100;
    if (strcmp(fault, "foreign-mount") == 0 && mount_count && mount_queries[0] > 1 && strcmp(path, mounted_paths[0]) == 0)
        info->stx_mnt_id = 999;
    return 0;
}
static int fixture_mount(const char *from, const char *to, const char *type,
                         unsigned long flags, const void *data) {
    if (from == NULL) {
        if (strcmp(fault, "setup-propagation") == 0) { errno = EACCES; return -1; }
        return flags == (MS_REC | MS_PRIVATE) ? 0 : -1;
    }
    if (type && strcmp(type, "tmpfs") == 0) {
        printf("tmpfs:%s\n", to); private_mount = 1;
        printf("tmpfs-options:%s\n", (const char *) data);
        if (strcmp(fault, "setup-tmpfs") == 0) { errno = ENOSPC; return -1; }
        return 0;
    }
    int fd; char target[PATH_MAX];
    if (!(flags & MS_BIND) || sscanf(to, "/proc/self/fd/%d", &fd) != 1) exit(2);
    fd_name(fd, target);
    const char *path = logical(target);
    printf("bind:%s\n", path);
    if (strcmp(fault, "bind") == 0) { errno = EIO; return -1; }
    if (strncmp(fault, "bind-errno-", 11) == 0) {
        if (strcmp(fault, "bind-errno-zero") == 0) errno = 0;
        else if (strcmp(fault, "bind-errno-negative") == 0) errno = -1;
        else if (strcmp(fault, "bind-errno-upper") == 0) errno = 4095;
        else if (strcmp(fault, "bind-errno-overflow") == 0) errno = 4096;
        else exit(2);
        return -1;
    }
    if (strcmp(path, "/usr") == 0) {
        if (strcmp(fault, "attach") == 0) { errno = EIO; return -1; }
        int source_fd;
        if (sscanf(from, "/proc/self/fd/%d", &source_fd) != 1 ||
            (clone_source = dup(source_fd)) < 0) exit(2);
        cloned = 1;
    } else {
        if (mount_count >= 64) exit(2);
        int source_fd;
        if (sscanf(from, "/proc/self/fd/%d", &source_fd) != 1) exit(2);
        mounted_sources[mount_count] = dup(source_fd);
        if (mounted_sources[mount_count] < 0) exit(2);
        mounted_live[mount_count] = 1;
        snprintf(mounted_paths[mount_count++], PATH_MAX, "%s", path);
    }
    return 0;
}
static int fixture_readonly(int fd, const char *path, unsigned flags,
                            struct mount_attr *attributes, size_t size) {
    if (fd != AT_FDCWD || flags != AT_RECURSIVE || size != sizeof(*attributes) ||
        attributes->attr_set != MOUNT_ATTR_RDONLY) exit(2);
    printf("readonly:%s\n", path);
    if (strcmp(path, "/usr") == 0) {
        if (strcmp(fault, "readonly") == 0) { errno = EROFS; return -1; }
        readonly = 1;
    }
    return 0;
}
static int fixture_detach(const char *path, int flags) {
    if (flags != MNT_DETACH) exit(2);
    printf("detach:%s\n", path);
    if (strcmp(fault, "detach") == 0) { errno = EBUSY; return -1; }
    if (strcmp(path, "/usr") == 0) {
        if (clone_source >= 0) close(clone_source);
        clone_source = -1; cloned = 0;
    }
    for (unsigned i = 0; i < mount_count; i++)
        if (strcmp(path, mounted_paths[i]) == 0 && mounted_live[i]) {
            mounted_live[i] = 0; close(mounted_sources[i]); mounted_sources[i] = -1;
        }
    return 0;
}
#define KIOSK_CONFINEMENT_RUNTIME runtime_path
#define KIOSK_CONFINEMENT_VIEW view_path
#define KIOSK_CONFINEMENT_BINDINGS manifest
#define KIOSK_CONFINEMENT_PREPARE helper_path
#define KIOSK_VIEW_ROWS 32768U
#define KIOSK_VIEW_BYTES (64U * 1024U * 1024U)
#define open fixture_open
#define openat fixture_openat
#define fstat fixture_fstat
#define fstatat fixture_fstatat
#define close fixture_close
#define unlinkat fixture_unlinkat
#define fstatfs fixture_fstatfs
#define mkdir fixture_mkdir
#define statx(...) fixture_statx(__VA_ARGS__)
#define unshare fixture_unshare
#define mount fixture_mount
#define mount_setattr fixture_readonly
#define umount2 fixture_detach
#define dlopen fixture_dlopen
#define dlsym fixture_dlsym
#define dlclose fixture_dlclose
#define getxattr fixture_getxattr
#define lgetxattr fixture_getxattr
#define fopen fixture_fopen
#define clock_gettime fixture_clock
#define kill fixture_kill
#define waitpid fixture_waitpid
''' + preparation + functions + r'''
int main(int argc, char **argv) {
    char backend[32];
    struct kiosk_view view;
    if (argc != 6 && argc != 7) return 2;
    manifest = argv[1]; fault = argv[2]; fixture_root = argv[3]; caller = argv[4]; drift_source = argv[5];
    diagnostic_mode = argc == 7 ? argv[6] : "capture";
    if (snprintf(runtime_path, sizeof(runtime_path), "%s/runtime", fixture_root) >= PATH_MAX ||
        snprintf(view_path, sizeof(view_path), "%s/native-view", runtime_path) >= PATH_MAX ||
        snprintf(helper_path, sizeof(helper_path), "%s/helper", runtime_path) >= PATH_MAX) return 2;
    unsigned before = descriptor_count();
    if (strncmp(fault, "helper-", 7) == 0) {
        int lock = open(manifest, O_RDONLY);
        if (strcmp(fault, "helper-failure") == 0) strcpy(helper_path, "/bin/false");
        if (strcmp(fault, "helper-success") == 0) strcpy(helper_path, "/bin/true");
        int result = prepare_kiosk_confinement(caller, lock, lock);
        close(lock); printf("fd-balance:%d\n", (int) descriptor_count() - (int) before);
        return result == 0 ? 0 : 1;
    }
    int setup_only = strncmp(fault, "setup-", 6) == 0;
    int result;
    if (setup_only) result = setup_kiosk_view(&view);
    else {
        memset(&view, 0, sizeof(view));
        view.root = fixture_open(KIOSK_CONFINEMENT_VIEW, O_RDONLY | O_DIRECTORY);
        view.mounted = private_mount = 1; view.root_id = 2;
        struct stat ns; int nsfd = fixture_open("/proc/self/ns/mnt", O_RDONLY);
        if (nsfd < 0 || fixture_fstat(nsfd, &ns) != 0) return 2;
        fixture_close(nsfd); view.namespace_device = ns.st_dev; view.namespace_inode = ns.st_ino;
        view.mounts = calloc(KIOSK_VIEW_ROWS, sizeof(*view.mounts));
        result = view.root < 0 || view.mounts == NULL ? -1 : 0;
        if (result == 0) result = bind_kiosk_executables(backend, sizeof(backend), caller, &view);
    }
    if (result == 0 && strcmp(fault, "post-attach") == 0) result = -1;
    if (cleanup_kiosk_view(&view, result == 0) != 0) result = -1;
    int saved_errno = errno;
    kiosk_native_diagnostic(NULL, &view, caller);
    printf("diagnostic-attempts:%u\n", diagnostic_attempts);
    printf("diagnostic-errno-preserved:%d\n", errno == saved_errno);
    /* Kernel references are represented by fixture-owned duplicates; close
     * that bookkeeping after native cleanup before auditing native fd balance. */
    if (clone_source >= 0) close(clone_source);
    for (unsigned i = 0; i < mount_count; i++) if (mounted_live[i]) close(mounted_sources[i]);
    printf("source-opens:%u\n", source_opens);
    printf("fd-balance:%d\n", (int) descriptor_count() - (int) before);
    return result == 0 ? 0 : 1;
}
''')
    executable = directory / 'binding'
    built = NATIVE_RUN(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-o',
                       str(executable), str(source)], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    return executable


def _native_binding_scene(executable, root, *, role='manager', required=False, kind='file'):
    """Extend the binding fixture with private real files and its closed stream."""
    runtime = root / 'runtime'
    view = runtime / 'native-view'
    tree = view / 'tree'
    generation = runtime / ('a' * 64)
    for directory in (runtime, view, tree, generation, root / 'usr/bin', root / 'usr/share'):
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700 if directory in (runtime, view, generation) else 0o755)
    (generation / 'generation').write_text(generation.name + '\n')
    (generation / 'generation').chmod(0o644)
    marker = '/usr/share/oh-no-parent-control/confinement/generation'
    marker_relative = marker.removeprefix('/usr/')
    (tree / marker_relative).parent.mkdir(parents=True)
    (tree / marker_relative).touch()
    source = '/usr/bin/program' if kind == 'file' else '/usr/share/assets'
    physical = root / source.lstrip('/')
    if kind == 'file':
        physical.write_text('reviewed source')
        physical.chmod(0o644)
    else:
        physical.mkdir(exist_ok=True)
        physical.chmod(0o755)
        (physical / 'unreviewed-data').write_text('must never be copied')
    relative = source.removeprefix('/usr/')
    target = tree / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == 'file':
        target.touch()
    else:
        target.mkdir(exist_ok=True)
    roots = [('covered', '/usr', '-'),
             ('marker', marker, str(generation / 'generation'))]
    if required:
        if kind == 'file':
            shutil.copyfile(physical, generation / '0')
            (generation / '0').chmod(0o644)
            roots.append(('native', source, str(generation / '0')))
        else:
            roots.append(('reserved', source, '-'))
    nodes = [('tree', 'bin', '-'), ('tree', 'share', '-'),
             ('tree', 'share/oh-no-parent-control', '-'),
             ('tree', 'share/oh-no-parent-control/confinement', '-'),
             (kind, relative, '-'), ('file', marker_relative, '-')]
    # Keep real skeleton nodes in exact agreement with its declared inventory.
    (tree / 'bin').mkdir(exist_ok=True)
    (tree / 'share').mkdir(exist_ok=True)
    proof_paths = {'/', '/usr', str(generation), str(generation / 'generation')}
    proof_paths.update(map(str, generation.parents))
    if required:
        proof_paths.update((source, str(Path(source).parent)))
        if kind == 'file': proof_paths.add(str(generation / '0'))
    proofs = [('file' if path in (source, str(generation / 'generation'), str(generation / '0')) and
               not (path == source and kind == 'directory') else 'directory', path, '-')
              for path in sorted(proof_paths)]
    rows = ['ONPC-KIOSK\t1\tapparmor\t' + role + '\t' + generation.name]
    rows += ['\t'.join(('root', *record)) for record in roots]
    rows += ['\t'.join(('node', *record)) for record in nodes]
    rows += ['\t'.join(('proof', *record)) for record in proofs]
    bind_source = str(generation / '0') if required and kind == 'file' else source
    rows += ['\t'.join(('bind', 'required', 'file', str(generation / 'generation'), marker_relative, '-')),
             '\t'.join(('bind', 'required' if required else 'ambient', kind, bind_source, relative, '-')),
             'attach\t/usr']
    manifest = view / 'bindings'

    def publish(values=None):
        manifest.write_text('\n'.join(rows if values is None else values) + '\n')
        manifest.chmod(0o600)

    def run(fault='none', *, caller=role, path=source, diagnostic='capture'):
        changed = root / path.lstrip('/') if path.startswith('/usr/') else Path(path)
        assert changed.is_relative_to(root)
        try:
            result = NATIVE_RUN([str(executable), str(manifest), fault, str(root), caller, path, diagnostic],
                                capture_output=True, text=True, timeout=5)
        finally:
            # Real mode drift can remove directory search permission. Restore
            # only these fixture-owned source names after the native child is
            # reaped, including timeout/assertion failures, so pytest and the
            # identity-owned scratch collector can traverse their children.
            for candidate in (changed, changed.with_name(changed.name + '.retired')):
                try:
                    info = candidate.lstat()
                except FileNotFoundError:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    candidate.chmod(0o755, follow_symlinks=False)
        assert result.returncode in (0, 1), result.stdout + result.stderr
        assert 'fd-balance:0' in result.stdout.splitlines(), result.stdout + result.stderr
        return result

    publish()
    for path in [root / 'usr', *(root / 'usr').rglob('*')]:
        if path.is_dir(): path.chmod(0o755)
    for path in tree.rglob('*'):
        if not path.is_symlink(): path.chmod(0o755 if path.is_dir() else 0o644)
    return SimpleNamespace(root=root, runtime=runtime, view=view, tree=tree, generation=generation,
        source=source, physical=physical, target=target, relative=relative, rows=rows,
        manifest=manifest, publish=publish, run=run, marker_relative=marker_relative, bind_source=bind_source)


@pytest.mark.parametrize('fault', ['none', 'attach', 'readonly', 'detach', 'input',
    'root-group-directory', 'other-group-directory', 'world-directory',
    'unowned-directory', 'group-file', 'group-target'])
def test_native_binding_detaches_only_its_staging_mounts_after_readonly_clone(
        native_mount_binding, tmp_path, fault):
    scene = _native_binding_scene(native_mount_binding, tmp_path, required=True, kind='directory')
    program = tmp_path / 'usr/bin/program'
    program.write_text('required executable')
    program.chmod(0o644)
    shutil.copyfile(program, scene.generation / '0')
    (scene.generation / '0').chmod(0o644)
    (scene.tree / 'bin/program').touch()
    (scene.tree / 'bin/program').chmod(0o644)
    rows = scene.rows[:-1] + [
        'root\tnative\t/usr/bin/program\t' + str(scene.generation / '0'),
        'node\tfile\tbin/program\t-',
        'proof\tdirectory\t/usr/bin\t-', 'proof\tfile\t/usr/bin/program\t-',
        'proof\tfile\t' + str(scene.generation / '0') + '\t-',
        'bind\trequired\tfile\t' + str(scene.generation / '0') + '\tbin/program\t-', scene.rows[-1]]
    if fault == 'input':
        rows[-2] = 'bind\trequired\tfile\t/tmp/untrusted\tbin/program\t-'
    rows.sort(key=lambda row: {'ONPC-KIOSK': 0, 'root': 1, 'node': 2,
                              'proof': 3, 'bind': 4, 'attach': 5}[row.split('\t')[0]])
    scene.publish(rows)
    result = scene.run(fault)
    assert result.returncode == (0 if fault == 'none' else 1), result.stderr
    operations = result.stdout.splitlines()
    detached = [value.removeprefix('detach:') for value in operations if value.startswith('detach:')]
    targets = [str(scene.tree / scene.marker_relative), str(scene.target), str(scene.tree / 'bin/program')]
    if fault == 'none':
        assert detached == targets + [str(scene.view)]
        assert [value for value in operations if value.startswith('readonly:')] == ['readonly:/usr']
        assert operations.index('readonly:/usr') < operations.index('detach:' + targets[0])
    elif fault == 'detach':
        assert targets[0] in detached
        assert str(scene.view) not in detached
    else:
        assert 'readonly:/usr' not in operations or fault == 'readonly'
    if fault == 'none':
        assert '/usr' not in detached


def _native_diagnostic_records(result):
    records = [line.removeprefix('native-record:') for line in result.stdout.splitlines()
               if line.startswith('native-record:')]
    for record in records:
        # Match the whole schema: fixture paths, numeric identities, backend
        # exceptions and arbitrary syscall text cannot become producer fields.
        prefix = 'onpc.pam kiosk native-view '
        assert record.startswith(prefix), record
        fields = dict(value.split('=', 1) for value in record.removeprefix(prefix).split())
        assert set(fields) == {'outcome', 'role', 'stage', 'reason', 'errno'}
        assert fields['outcome'] in ('denied', 'cleanup-failed')
        assert fields['role'] in ('manager', 'gate')
        assert fields['stage'] in ('namespace', 'staging', 'manifest', 'structure',
                                   'source', 'bind', 'attach', 'readonly', 'detach')
        assert fields['reason'] in ('manifest', 'metadata', 'identity', 'namespace',
                                    'mount', 'readonly', 'detach')
        assert fields['errno'] == '-1' or 1 <= int(fields['errno']) <= 4095
        assert len(record) < 180
    return records


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('fault,stage,reason,error', [
    ('manifest', 'manifest', 'manifest', -1),
    ('metadata', 'structure', 'metadata', -1),
    ('identity', 'source', 'identity', -1),
    ('setup-namespace', 'namespace', 'namespace', 1),
    ('setup-storage', 'staging', 'metadata', -1),
    ('setup-tmpfs', 'staging', 'mount', 28),
    ('bind', 'bind', 'mount', 5),
    ('attach', 'attach', 'mount', 5),
    ('readonly', 'readonly', 'readonly', 30),
    ('detach', 'detach', 'detach', 16),
])
def test_native_binding_reports_closed_failure_causes(
        native_mount_binding, tmp_path, role, fault, stage, reason, error):
    scene = _native_binding_scene(native_mount_binding, tmp_path, role=role)
    if fault == 'manifest':
        scene.publish([scene.rows[0].replace('ONPC-KIOSK', 'private-manifest-canary'), *scene.rows[1:]])
    elif fault == 'metadata':
        scene.target.chmod(0o666)
    elif fault == 'identity':
        # Preserve an independently measured real identity in the native
        # assertion, then change exactly its inode witness. Do not ask the
        # diagnostic producer whether the helper is the same file.
        measured = list(module(ROOT / 'tools/kiosk_confinement.py').file_identity(scene.physical.stat()))
        measured[-2:] = [0, 0]
        measured[1] += 1
        rows = [row for row in scene.rows if not row.startswith('bind\tambient')]
        rows.insert(1, 'root\tpreserved\t' + scene.source + '\t' + scene.source)
        proof_at = next(index for index, row in enumerate(rows) if row.startswith('bind\t'))
        rows[proof_at:proof_at] = ['proof\tdirectory\t/usr/bin\t-',
                                  'proof\tfile\t' + scene.source + '\t-']
        rows.insert(-1, '\t'.join(('bind', 'required', 'file', scene.source,
                                   scene.relative, ' '.join(map(str, measured)))))
        scene.publish(rows)
    elif fault.startswith('setup-'):
        shutil.rmtree(scene.tree)
        scene.manifest.unlink()
    result = scene.run(fault)
    assert result.returncode == 1, result.stdout + result.stderr
    expected = (f'onpc.pam kiosk native-view outcome=denied role={role} '
                f'stage={stage} reason={reason} errno={error}')
    records = _native_diagnostic_records(result)
    assert records[0] == expected, result.stdout + result.stderr
    assert all('private-manifest-canary' not in record and str(tmp_path) not in record
               for record in records)
    assert 'diagnostic-errno-preserved:1' in result.stdout.splitlines()
    operations = result.stdout.splitlines()
    if fault in ('manifest', 'metadata', 'identity') or fault.startswith('setup-'):
        assert 'bind:' + str(scene.target) not in operations
        assert 'readonly:/usr' not in operations
    if fault in ('attach', 'readonly', 'detach'):
        assert 'bind:' + str(scene.target) in operations
    if fault == 'readonly':
        assert 'readonly:/usr' in operations and 'detach:/usr' in operations
    if fault == 'detach':
        assert operations.index('readonly:/usr') < operations.index('detach:' + str(scene.target))
        assert 'detach:' + str(scene.view) not in operations


@pytest.mark.parametrize('fault,error', [
    ('bind-errno-zero', -1), ('bind-errno-negative', -1),
    ('bind-errno-upper', 4095), ('bind-errno-overflow', -1),
])
def test_native_binding_bounds_only_observed_syscall_errno(native_mount_binding, tmp_path, fault, error):
    scene = _native_binding_scene(native_mount_binding, tmp_path)
    result = scene.run(fault)
    assert result.returncode == 1
    assert _native_diagnostic_records(result)[0] == (
        'onpc.pam kiosk native-view outcome=denied role=manager '
        f'stage=bind reason=mount errno={error}')
    assert 'readonly:/usr' not in result.stdout.splitlines()


@pytest.mark.parametrize('fault', ['none', 'bind', 'readonly', 'detach'])
def test_native_binding_diagnostic_transport_failure_preserves_result(native_mount_binding, tmp_path, fault):
    scene = _native_binding_scene(native_mount_binding, tmp_path)
    observed = scene.run(fault)
    discarded = scene.run(fault, diagnostic='discard')
    assert observed.returncode == discarded.returncode == (0 if fault == 'none' else 1)
    records = _native_diagnostic_records(observed)
    assert len(records) == (0 if fault == 'none' else 2 if fault == 'detach' else 1)
    assert _native_diagnostic_records(discarded) == []
    assert f'diagnostic-attempts:{len(records)}' in discarded.stdout.splitlines()
    if fault == 'detach':
        assert records == [
            'onpc.pam kiosk native-view outcome=denied role=manager '
            'stage=detach reason=detach errno=16',
            'onpc.pam kiosk native-view outcome=cleanup-failed role=manager '
            'stage=detach reason=detach errno=16',
        ]
    assert 'diagnostic-errno-preserved:1' in discarded.stdout.splitlines()
    # Logger failure does not change the independently observed native mount
    # and detach sequence, including refusal to detach a root after failed
    # subordinate cleanup. Ignore only the logger's own output.
    def operations(result):
        return [line for line in result.stdout.splitlines()
                if not line.startswith(('native-record:', 'diagnostic-'))]
    assert operations(observed) == operations(discarded)


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('required', [False, True], ids=['ambient', 'required'])
@pytest.mark.parametrize('kind', ['file', 'directory'])
@pytest.mark.parametrize('drift', ['missing', 'owner', 'group', 'world', 'type'])
def test_post_layout_source_drift(native_mount_binding, tmp_path, role, required, kind, drift):
    scene = _native_binding_scene(native_mount_binding, tmp_path, role=role, required=required, kind=kind)
    healthy = scene.run()
    assert healthy.returncode == 0, healthy.stdout + healthy.stderr
    result = scene.run('source-' + drift)
    assert result.returncode == (1 if required else 0), result.stderr
    if not required:
        assert 'bind:' + str(scene.target) not in result.stdout.splitlines()
        assert 'readonly:/usr' in result.stdout.splitlines()
        assert (not scene.target.exists() if kind == 'file' else
                scene.target.is_dir() and list(scene.target.iterdir()) == [])


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('scope', ['ambient-file', 'ambient-directory', 'required-file',
                                  'required-directory', 'preserved-file'])
@pytest.mark.parametrize('boundary', ['open', 'pre', 'post'])
@pytest.mark.parametrize('drift', ['vanish', 'reappear', 'type', 'mode', 'owner'])
def test_post_layout_descriptor_drift(native_mount_binding, tmp_path, role, scope, boundary, drift):
    required = not scope.startswith('ambient')
    kind = scope.rsplit('-', 1)[1]
    scene = _native_binding_scene(native_mount_binding, tmp_path, role=role, required=required, kind=kind)
    if scope.startswith('preserved'):
        identity = list(module(ROOT / 'tools/kiosk_confinement.py').file_identity(scene.physical.stat()))
        identity[-2:] = [0, 0]
        rows = []
        for row in scene.rows:
            if row.startswith('root\tnative\t'):
                row = 'root\tpreserved\t' + scene.source + '\t' + scene.source
            elif row.startswith('bind\trequired\tfile\t' + scene.bind_source + '\t'):
                row = '\t'.join(('bind', 'required', 'file', scene.source, scene.relative,
                                  ' '.join(map(str, identity))))
            rows.append(row)
        scene.publish(rows)
    mutation_source = scene.source if scope.startswith('preserved') else scene.bind_source
    mutation_physical = (tmp_path / mutation_source.lstrip('/') if mutation_source.startswith('/usr/')
                         else Path(mutation_source))
    healthy = scene.run(path=mutation_source)
    assert healthy.returncode == 0, healthy.stdout + healthy.stderr
    result = scene.run('real-' + drift + '-' + boundary, path=mutation_source)
    assert result.returncode == (1 if required else 0), result.stderr + result.stdout
    operations = result.stdout.splitlines()
    if required and not any(value.startswith('mutation:') for value in operations):
        pytest.fail('required control did not reach its descriptor mutation')
    assert any(value.startswith('mutation:') for value in operations), operations
    # A removed or replaced name is never reopened to adopt its successor.
    opens = int(next(value.split(':')[1] for value in operations if value.startswith('source-opens:')))
    if not required:
        assert opens == 1
        if boundary == 'post':
            assert 'detach:' + str(scene.target) in operations
        assert (not scene.target.exists() if kind == 'file' else
                scene.target.is_dir() and list(scene.target.iterdir()) == [])
        assert 'readonly:/usr' in operations
    assert (mutation_physical.with_name(mutation_physical.name + '.retired').exists()
            if drift in ('reappear', 'type') else True)
    if drift == 'vanish': assert not mutation_physical.exists()


@pytest.mark.parametrize('fault', [
    'old', 'version', 'backend', 'missing-caller', 'unknown-caller', 'caller-mismatch',
    'source-role', 'root-role', 'node-kind', 'duplicate-root', 'duplicate-node',
    'duplicate-proof', 'duplicate-bind', 'contradictory-node', 'truncated', 'extra-field',
    'missing-attach', 'after-attach', 'nul', 'path-empty', 'path-dot', 'path-dotdot',
    'path-prefix', 'absolute-target', 'overlong-path', 'over-limit-rows', 'over-limit-bytes',
    'over-limit-roots', 'over-limit-proofs', 'over-limit-binds',
    'missing-root', 'missing-marker-root', 'missing-marker-bind', 'missing-copy-proof',
    'missing-proof', 'required-ambient', 'ambient-assertion',
    'target-link', 'target-ancestor-link', 'target-mode', 'ancestor-mode', 'target-missing',
    'target-stat', 'target-unlink',
    'source-ancestor-mode', 'reserved-drift', 'alias-missing-target-proof', 'alias-unsafe-parent',
    'marker-drift',
])
def test_post_layout_protocol_and_targets(native_mount_binding, tmp_path, fault):
    scene = _native_binding_scene(native_mount_binding, tmp_path)
    rows = scene.rows.copy()
    bind_index = next(index for index, row in enumerate(rows) if row.startswith('bind\tambient'))
    caller = 'manager'
    if fault in ('version', 'backend', 'missing-caller', 'unknown-caller'):
        fields = rows[0].split('\t')
        fields[{'version': 1, 'backend': 2, 'missing-caller': 3, 'unknown-caller': 3}[fault]] = {
            'version': '2', 'backend': 'unknown', 'missing-caller': '', 'unknown-caller': 'other'}[fault]
        rows[0] = '\t'.join(fields)
    elif fault == 'old':
        rows = ['apparmor', scene.source + '\t' + str(scene.target), str(scene.tree) + '\t/usr']
    elif fault == 'caller-mismatch':
        caller = 'gate'
    elif fault in ('source-role', 'ambient-assertion', 'required-ambient'):
        fields = rows[bind_index].split('\t')
        if fault == 'source-role': fields[1] = 'unknown'
        elif fault == 'ambient-assertion': fields[-1] = '0 0 0 0 0 0 0 0'
        else:
            marker = next(index for index, row in enumerate(rows) if row.startswith('bind\trequired'))
            rows[marker] = rows[marker].replace('\trequired\t', '\tambient\t')
        rows[bind_index] = '\t'.join(fields)
    elif fault in ('root-role', 'node-kind'):
        prefix = 'root\t' if fault == 'root-role' else 'node\t'
        index = next(index for index, row in enumerate(rows) if row.startswith(prefix))
        fields = rows[index].split('\t'); fields[1] = 'unknown'; rows[index] = '\t'.join(fields)
    elif fault.startswith('duplicate-') or fault == 'contradictory-node':
        tag = 'node' if fault == 'contradictory-node' else fault.removeprefix('duplicate-')
        index = next(index for index, row in enumerate(rows) if row.startswith(tag + '\t'))
        duplicate = rows[index]
        if fault == 'contradictory-node': duplicate = duplicate.replace('\ttree\t', '\tfile\t')
        rows.insert(index, duplicate)
    elif fault in ('missing-root', 'missing-proof', 'missing-marker-root', 'missing-marker-bind', 'missing-copy-proof'):
        if fault == 'missing-root': rows.remove('root\tcovered\t/usr\t-')
        elif fault == 'missing-proof': rows.remove('proof\tdirectory\t/usr\t-')
        else:
            prefix = {'missing-marker-root': 'root\tmarker\t', 'missing-marker-bind': 'bind\trequired\t',
                      'missing-copy-proof': 'proof\tfile\t' + str(scene.generation / 'generation')}[fault]
            rows.remove(next(row for row in rows if row.startswith(prefix)))
    elif fault in ('missing-attach', 'after-attach'):
        if fault == 'missing-attach': rows.pop()
        else: rows.append(rows[bind_index])
    elif fault in ('extra-field', 'nul'):
        rows[bind_index] += '\textra' if fault == 'extra-field' else '\x00'
    elif fault.startswith('path-') or fault in ('absolute-target', 'overlong-path'):
        fields = rows[bind_index].split('\t')
        fields[4] = {'path-empty': '', 'path-dot': 'bin/./program', 'path-dotdot': 'bin/../program',
                     'path-prefix': 'binary/program', 'absolute-target': '/bin/program',
                     'overlong-path': 'x' * 4096}[fault]
        rows[bind_index] = '\t'.join(fields)
    elif fault == 'over-limit-rows':
        index = next(index for index, row in enumerate(rows) if row.startswith('node\t'))
        rows[index:index] = ['node\tfile\toverflow-' + str(index) + '\t-' for index in range(32769)]
    elif fault in ('over-limit-roots', 'over-limit-proofs', 'over-limit-binds'):
        tag = {'over-limit-roots': 'root', 'over-limit-proofs': 'proof', 'over-limit-binds': 'bind'}[fault]
        index = next(index for index, row in enumerate(rows) if row.startswith(tag + '\t'))
        rows[index:index] = [
            'root\tcovered\t/usr/overflow-' + str(value) + '\t-' if tag == 'root' else
            'proof\tfile\t/usr/overflow-' + str(value) + '\t-' if tag == 'proof' else
            'bind\tambient\tfile\t/usr/overflow-' + str(value) + '\toverflow-' + str(value) + '\t-'
            for value in range(32769)]
    elif fault == 'target-link':
        scene.target.unlink(); scene.target.symlink_to('foreign')
    elif fault == 'target-ancestor-link':
        scene.target.unlink(); scene.target.parent.rmdir(); scene.target.parent.symlink_to(tmp_path / 'usr/bin')
    elif fault in ('target-mode', 'ancestor-mode', 'source-ancestor-mode'):
        path = scene.target if fault == 'target-mode' else scene.target.parent if fault == 'ancestor-mode' else scene.physical.parent
        path.chmod(0o777)
    elif fault == 'target-missing':
        scene.target.unlink()
    elif fault == 'reserved-drift':
        rows.insert(1, 'root\treserved\t/usr/bin\t-')
        rows.insert(next(index for index, row in enumerate(rows) if row.startswith('bind\t')),
                    'proof\tdirectory\t/usr/bin\t-')
        scene.physical.parent.chmod(0o777)
    elif fault.startswith('alias-'):
        alias = tmp_path / 'usr/alias'
        required = tmp_path / 'usr/bin/required'
        required.write_text('required canonical executable'); required.chmod(0o644)
        shutil.copyfile(required, scene.generation / '0'); (scene.generation / '0').chmod(0o644)
        (scene.tree / 'bin/required').touch(); (scene.tree / 'bin/required').chmod(0o644)
        alias.symlink_to('targetalias' if fault == 'alias-missing-target-proof' else 'unsafe/../bin/required')
        (scene.tree / 'alias').symlink_to(os.readlink(alias))
        rows.insert(1, 'root\talias\t/usr/alias\t-')
        rows.insert(1, 'root\tnative\t/usr/bin/required\t' + str(scene.generation / '0'))
        rows.insert(next(index for index, row in enumerate(rows) if row.startswith('proof\t')),
                    'node\tlink\talias\t' + os.readlink(alias))
        rows.insert(next(index for index, row in enumerate(rows) if row.startswith('proof\t')),
                    'node\tfile\tbin/required\t-')
        index = next(index for index, row in enumerate(rows) if row.startswith('bind\t'))
        rows[index:index] = ['proof\tlink\t/usr/alias\t' + os.readlink(alias),
                            'proof\tdirectory\t/usr/bin\t-', 'proof\tfile\t/usr/bin/required\t-',
                            'proof\tfile\t' + str(scene.generation / '0') + '\t-']
        rows.insert(-1, 'bind\trequired\tfile\t' + str(scene.generation / '0') + '\tbin/required\t-')
        if fault == 'alias-unsafe-parent':
            (tmp_path / 'usr/unsafe').mkdir(mode=0o755); (tmp_path / 'usr/unsafe').chmod(0o755)
            rows.insert(next(index for index, row in enumerate(rows) if row.startswith('bind\t')),
                        'proof\tdirectory\t/usr/unsafe\t-')
        else:
            (tmp_path / 'usr/targetalias').symlink_to('bin/required')
            (scene.tree / 'targetalias').symlink_to('bin/required')
            rows.insert(next(index for index, row in enumerate(rows) if row.startswith('proof\t')),
                        'node\tlink\ttargetalias\tbin/required')
            rows.insert(next(index for index, row in enumerate(rows) if row.startswith('bind\t')),
                        'proof\tlink\t/usr/targetalias\tbin/required')
        scene.publish(rows)
        healthy = scene.run()
        assert healthy.returncode == 0, healthy.stdout + healthy.stderr
        if fault == 'alias-unsafe-parent': (tmp_path / 'usr/unsafe').chmod(0o777)
        else: rows.remove('proof\tlink\t/usr/targetalias\tbin/required')
    elif fault == 'marker-drift':
        (scene.generation / 'generation').write_text('b' * 64 + '\n')
    scene.publish(rows)
    if fault == 'truncated': scene.manifest.write_bytes(scene.manifest.read_bytes()[:-1])
    if fault == 'over-limit-bytes':
        with scene.manifest.open('r+b') as stream: stream.truncate(64 * 1024 * 1024 + 1)
    # Missing ambient input must not conceal any structural or target error.
    if fault == 'target-stat': scene.physical.unlink()
    result = scene.run('target-stat' if fault == 'target-stat' else
                       'missing-target-unlink' if fault == 'target-unlink' else 'source-missing', caller=caller)
    assert result.returncode == 1, result.stdout + result.stderr
    if fault.startswith('over-limit-'):
        assert 'fixture-stop:kiosk_read_protocol:' in result.stderr
    assert 'readonly:/usr' not in result.stdout.splitlines()
    assert 'bind:' + str(scene.target) not in result.stdout.splitlines()


@pytest.mark.parametrize('error', [13, 1, 5, 116, 24, 9, 12, 22])
@pytest.mark.parametrize('required', [False, True], ids=['ambient', 'required'])
def test_post_layout_protocol_and_targets_source_errors(native_mount_binding, tmp_path, error, required):
    scene = _native_binding_scene(native_mount_binding, tmp_path, required=required)
    result = scene.run('error-' + str(error))
    allowed = not required and error in (13, 1, 5, 116)
    assert result.returncode == (0 if allowed else 1), result.stdout + result.stderr
    if allowed:
        assert not scene.target.exists()
        assert 'bind:' + str(scene.target) not in result.stdout


@pytest.mark.parametrize('fault', ['none', 'bind', 'attach', 'readonly', 'detach',
    'foreign-mount', 'cleanup-namespace', 'post-attach', 'setup-none', 'setup-namespace', 'setup-propagation',
    'setup-tmpfs', 'setup-storage', 'setup-inodes', 'setup-nonempty', 'setup-selinux-none',
    'setup-selinux-label', 'setup-selinux-options', 'setup-selinux-override',
    'helper-success', 'helper-failure', 'helper-timeout'])
def test_post_layout_owned_cleanup_and_bounds(native_mount_binding, tmp_path, fault):
    scene = _native_binding_scene(native_mount_binding, tmp_path)
    shared = {str(path.relative_to(scene.generation)): path.read_bytes()
              for path in scene.generation.rglob('*') if path.is_file()}
    foreign = tmp_path / 'foreign'
    foreign.write_text('foreign state survives')
    if fault.startswith('setup-'):
        shutil.rmtree(scene.tree)
        scene.manifest.unlink()
        if fault == 'setup-nonempty': (scene.view / 'foreign').write_text('do not adopt')
    if fault == 'helper-timeout':
        helper = scene.runtime / 'helper'
        helper.write_text('#!/bin/sh\nexec /bin/sleep 30\n')
        helper.chmod(0o755)
    result = scene.run(fault)
    assert result.returncode == (0 if fault in ('none', 'setup-none', 'setup-selinux-none', 'helper-success') else 1), result.stdout + result.stderr
    operations = result.stdout.splitlines()
    assert foreign.read_text() == 'foreign state survives'
    assert {str(path.relative_to(scene.generation)): path.read_bytes()
            for path in scene.generation.rglob('*') if path.is_file()} == shared
    if fault == 'none':
        assert operations.index('readonly:/usr') < operations.index('detach:' + str(scene.view))
        assert 'detach:/usr' not in operations
    if fault == 'post-attach': assert 'detach:/usr' in operations
    if fault == 'foreign-mount': assert 'detach:' + str(scene.target) not in operations
    if fault == 'cleanup-namespace':
        assert 'namespace-witness:mismatch' in operations
        assert 'readonly:/usr' in operations
        assert not any(line.startswith('detach:') for line in operations)
    assert all('foreign' not in line for line in operations if line.startswith('detach:'))
    assert 'fd-balance:0' in operations
    if fault.startswith('helper-'):
        reaped = [line.removeprefix('reaped:') for line in operations if line.startswith('reaped:')]
        assert len(reaped) == 1
        killed = [line.removeprefix('killed:') for line in operations if line.startswith('killed:')]
        assert killed == (reaped if fault == 'helper-timeout' else [])
    if fault in ('setup-none', 'setup-selinux-none'):
        options = next(line.removeprefix('tmpfs-options:') for line in operations if line.startswith('tmpfs-options:'))
        expected = 'mode=0700,size=536870912,nr_inodes=32776'
        if fault == 'setup-selinux-none':
            expected += ',fscontext=system_u:object_r:tmpfs_t:s0,rootcontext=system_u:object_r:onpc_kiosk_runtime_t:s0'
        assert options == expected
        assert 'detach:' + str(scene.view) in operations
    if fault == 'setup-nonempty':
        assert (scene.view / 'foreign').read_text() == 'do not adopt'
    records = _native_diagnostic_records(result)
    expected_primary = {
        'setup-propagation': ('namespace', 'mount', 13),
        'setup-tmpfs': ('staging', 'mount', 28),
        'setup-storage': ('staging', 'metadata', -1),
        'setup-inodes': ('staging', 'metadata', -1),
        'setup-selinux-label': ('staging', 'metadata', -1),
        'setup-selinux-options': ('staging', 'metadata', -1),
        'setup-selinux-override': ('staging', 'metadata', -1),
    }
    if fault in expected_primary:
        stage, reason, error = expected_primary[fault]
        assert records[0] == ('onpc.pam kiosk native-view outcome=denied role=manager '
                              f'stage={stage} reason={reason} errno={error}')
    if fault in ('foreign-mount', 'cleanup-namespace'):
        reason = 'identity' if fault == 'foreign-mount' else 'namespace'
        assert records[-1] == ('onpc.pam kiosk native-view outcome=cleanup-failed role=manager '
                               f'stage=detach reason={reason} errno=-1')
    assert len(records) <= 2
    if fault in ('none', 'setup-none', 'setup-selinux-none'):
        assert records == []


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('kind', ['file', 'directory'])
@pytest.mark.parametrize('drift', ['missing', 'owner', 'group', 'world', 'type'])
def test_post_layout_published_roles_and_reuse(
        preserved_password_preparation, native_mount_binding, tmp_path, monkeypatch, role, kind, drift):
    model = preserved_password_preparation
    helper = model.helper
    scene = _native_binding_scene(native_mount_binding, tmp_path, role=role, kind=kind)
    # Retain the real copied input as well as records, complete skeleton and
    # marker in the shared snapshot; native omissions affect only native-view.
    native = tmp_path / 'usr/bin/reviewed-native'
    native.write_bytes(b'\x7fELFmeasured copy')
    native.chmod(0o755)
    record = dict(role='bwrap', path='/usr/bin/reviewed-native', source=str(native),
                  sha256=hashlib.sha256(native.read_bytes()).hexdigest())
    if not any(entry['path'] == '/usr/bin' for entry in model.layout):
        model.layout.append(dict(path='/usr/bin', kind='tree'))
    model.layout += [dict(path=record['path'], kind='file'), dict(path=scene.source, kind=kind)]
    monkeypatch.setattr(helper, 'inventory', lambda config: [record])
    monkeypatch.setattr(helper, 'directory_layout', lambda config, records: model.layout)
    helper.prepare('manager')
    digest = model.bindings.read_text().splitlines()[0].split('\t')[4]
    generation = model.runtime / digest
    manager = tmp_path / 'proc/777'
    (manager / 'root' / str(helper.PAYLOAD).lstrip('/')).mkdir(parents=True)
    (manager / 'root' / str(helper.PAYLOAD / 'generation').lstrip('/')).write_text(digest + '\n')
    (manager / 'status').write_text('Uid:\t1002\t1002\t1002\t1002\n')
    (manager / 'attr/apparmor').mkdir(parents=True)
    (manager / 'attr/apparmor/current').write_text('onpc-kiosk-manager (enforce)\n')
    verify = helper.subprocess.run
    def command(args, **kwargs):
        if args[:2] == ['/usr/bin/systemctl', 'show']:
            return SimpleNamespace(stdout='777\n')
        return verify(args, **kwargs)
    monkeypatch.setattr(helper.subprocess, 'run', command)
    original_path = helper.Path
    monkeypatch.setattr(helper, 'Path', lambda path: tmp_path / 'proc' if str(path) == '/proc' else original_path(path))
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda pid: os.open(manager / 'status', os.O_RDONLY))
    monkeypatch.setattr(helper.select if hasattr(helper, 'select') else select, 'poll',
                        lambda: SimpleNamespace(register=lambda *args: None, poll=lambda *args: []))
    def manager_check(uid, value, backend):
        model.manager_checks.append((uid, value, backend))
        model.real_manager_generation(uid, value, backend)
    monkeypatch.setattr(helper, 'manager_generation', manager_check)
    helper.prepare(role)
    assert model.bindings.read_text().splitlines()[0].split('\t')[3:] == [role, digest]
    def snapshot():
        return {str(path.relative_to(generation)):
                ('link', os.readlink(path)) if path.is_symlink() else
                ('directory', stat.S_IMODE(path.stat().st_mode), path.stat().st_ino) if path.is_dir() else
                ('file', path.read_bytes(), stat.S_IMODE(path.stat().st_mode), path.stat().st_ino)
                for path in [generation, *generation.rglob('*')]}
    before = snapshot()
    result = scene.run('source-' + drift, caller=role)
    assert result.returncode == 0, result.stdout + result.stderr
    target = scene.tree / scene.relative
    assert not target.exists() if kind == 'file' else target.is_dir() and list(target.iterdir()) == []
    assert 'bind:' + str(target) not in result.stdout.splitlines()
    assert snapshot() == before
    assert (model.runtime / 'bindings').read_text() == 'previous bindings\n'
    helper.prepare('gate')
    assert snapshot() == before
    assert model.manager_checks[-1] == (1002, digest, 'apparmor')
    assert target.exists()
    with pytest.raises(ValueError, match='manager-generation-stale'):
        model.real_manager_generation(1002, 'b' * 64, 'apparmor')
    model.layout.append(dict(path='/usr/share/new-layout-node', kind='file'))
    with pytest.raises(ValueError, match='manager-generation-stale'):
        helper.prepare('gate')
    assert snapshot() == before


@pytest.mark.parametrize('fault', ['row-limit', 'manifest-limit', 'generation-limit', 'copy-limit',
                                  'label', 'publication', 'logging'])
def test_post_layout_owned_cleanup_and_bounds_preparation(
        preserved_password_preparation, monkeypatch, fault):
    model = preserved_password_preparation
    helper = model.helper
    before = (model.runtime / 'bindings').read_bytes()
    if fault == 'row-limit': monkeypatch.setattr(helper, 'MAX_ROWS', 2)
    elif fault == 'manifest-limit': monkeypatch.setattr(helper, 'MAX_MANIFEST', 128)
    elif fault == 'generation-limit':
        for value in range(4): (model.runtime / (str(value) * 64)).mkdir()
    elif fault == 'copy-limit':
        source = model.runtime.parent / 'large-source'
        source.write_bytes(b'\x7fELFbounded private input')
        source.chmod(0o755)
        installed = model.runtime.parent / 'usr/bin/large-source'
        installed.parent.mkdir(mode=0o755)
        installed.write_bytes(source.read_bytes())
        installed.chmod(0o755)
        record = dict(role='bwrap', path='/usr/bin/large-source', source=str(source),
                      sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        monkeypatch.setattr(helper, 'inventory', lambda config: [record])
        model.layout += [dict(path='/usr/bin', kind='tree'), dict(path=record['path'], kind='file')]
        monkeypatch.setattr(helper, 'directory_layout', lambda config, records: model.layout)
        original_stat = Path.stat
        def oversized(path, *args, **kwargs):
            info = original_stat(path, *args, **kwargs)
            return SimpleNamespace(st_size=512 * 1024 * 1024 + 1) if path == source else info
        monkeypatch.setattr(helper.Path, 'stat', oversized)
    elif fault == 'label':
        def denied(*args, **kwargs): raise OSError(5, 'private label failure')
        monkeypatch.setattr(helper, 'runtime_label', denied)
    elif fault == 'publication':
        replace = Path.replace
        def denied(path, target):
            if target == model.bindings:
                assert not model.bindings.exists()
                raise OSError(5, 'private publication failure')
            return replace(path, target)
        monkeypatch.setattr(helper.Path, 'replace', denied)
    else:
        model.layout.append(dict(path='/usr/share/masked', kind='empty-directory'))
        def broken_stderr(*args): raise BrokenPipeError(32, 'closed fixture log')
        monkeypatch.setattr(helper.os, 'write', broken_stderr)
    if fault == 'logging':
        helper.prepare('manager')
        assert model.bindings.exists()
    else:
        reason = {'row-limit': 'binding-protocol-limit', 'manifest-limit': 'binding-protocol-limit',
                  'generation-limit': 'generation-limit-reboot-required',
                  'copy-limit': 'executable-inventory-too-large', 'label': 'private label failure',
                  'publication': 'private publication failure'}[fault]
        with pytest.raises((ValueError, OSError), match=reason):
            helper.prepare('manager')
        assert not model.bindings.exists()
    assert (model.runtime / 'bindings').read_bytes() == before
    assert not any(path.name.startswith(('.bindings-', '.prepare-')) for path in model.runtime.rglob('*'))


def test_directory_skeleton_preserves_links_without_following_them(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    tree = tmp_path / 'tree'
    layout = [
        {'path': '/usr/bin', 'kind': 'tree'},
        {'path': '/usr/bin/program', 'kind': 'file'},
        {'path': '/usr/bin/alias', 'kind': 'link', 'link': 'program'},
        {'path': '/usr/share', 'kind': 'directory'},
    ]
    previous = os.umask(0o077)
    try:
        helper.make_tree(tree, layout)
    finally:
        os.umask(previous)
    assert stat.S_IMODE(tree.stat().st_mode) == 0o755
    assert stat.S_IMODE((tree / 'bin').stat().st_mode) == 0o755
    assert (tree / 'bin/program').read_bytes() == b''
    assert stat.S_IMODE((tree / 'bin/program').stat().st_mode) == 0o644
    assert (tree / 'share').is_dir()
    original = Path.lstat
    def owned(path):
        info = list(original(path))
        info[4] = 0
        return os.stat_result(info)
    monkeypatch.setattr(helper.Path, 'lstat', owned)
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: path)
    helper.verify_tree(tree, layout)
    (tree / 'bin/alias').unlink()
    (tree / 'bin/alias').symlink_to(tmp_path)
    with pytest.raises(ValueError, match='directory-generation-changed'):
        helper.verify_tree(tree, layout)


@pytest.mark.parametrize('fault', ['directory-write', 'file-write', 'unowned-directory',
    'unowned-file', 'directory-link', 'file-link', 'file-type', 'hardlink', 'content',
    'unexpected', 'missing'])
def test_private_tree_validation_rejects_changed_entries_and_ancestors(tmp_path, monkeypatch, fault):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    tree = tmp_path / 'tree'
    layout = [{'path': '/usr/bin', 'kind': 'tree'},
              {'path': '/usr/bin/program', 'kind': 'file'}]
    helper.make_tree(tree, layout)
    directory, program = tree / 'bin', tree / 'bin/program'
    original = Path.lstat

    def metadata(path):
        info = list(original(path))
        info[4] = 1001 if ((fault == 'unowned-directory' and path == directory) or
                          (fault == 'unowned-file' and path == program)) else 0
        return os.stat_result(info)

    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    monkeypatch.setattr(helper, 'trusted', lambda path, **_kw: path)
    if fault == 'directory-write':
        directory.chmod(0o777)
    elif fault == 'file-write':
        program.chmod(0o666)
    elif fault == 'directory-link':
        directory.rename(tmp_path / 'outside')
        directory.symlink_to(tmp_path / 'outside')
    elif fault == 'file-link':
        program.unlink()
        program.symlink_to(tmp_path / 'absent')
    elif fault == 'file-type':
        program.unlink()
        program.mkdir()
    elif fault == 'hardlink':
        os.link(program, tmp_path / 'linked')
    elif fault == 'content':
        program.write_bytes(b'changed')
    elif fault == 'unexpected':
        (directory / 'extra').touch()
    elif fault == 'missing':
        program.unlink()
    with pytest.raises(ValueError):
        helper.verify_tree(tree, layout)


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_generated_policy_has_no_direct_interpreter_or_scanner_service_entry(distribution):
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    entries = policy.executables(distribution)
    for domain in ('manager', 'service', 'gate'):
        assert not {'python', 'gjs', 'audio', 'scanner'} & policy.routes()[domain].keys()
    assert any(entry['role'] == 'blocked' and entry.get('optional') for entry in entries)
    assert policy.routes()['app-start'] == {'python': 'app'}


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_glycin_inventory_pins_only_finite_native_loader_paths(tmp_path, monkeypatch, distribution):
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    entry, = [entry for entry in policy.executables(distribution) if entry['role'] == 'glycin']
    assert entry['paths'] == [policy.GLYCIN_DIRECTORY + '/' + name for name in policy.GLYCIN_LOADERS]
    assert not entry.get('optional')
    # Exercise the real native-record checks using one installed codec. Extra
    # local loader files are never discovered, while missing all codecs refuses.
    paths = [tmp_path / Path(path).name for path in entry['paths']]
    config = {'executables': [{**entry, 'paths': list(map(str, paths))}]}
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: Path(path).resolve(strict=True))
    paths[0].write_bytes(b'\x7fELFprivate svg loader')
    paths[0].chmod(0o755)
    (tmp_path / 'user-selected-loader').write_bytes(b'\x7fELFunlisted')
    assert [record['path'] for record in helper.inventory(config)] == [str(paths[0])]
    paths[0].unlink()
    with pytest.raises(ValueError, match='missing-executable'):
        helper.inventory(config)


def test_glycin_sandbox_routes_have_no_general_service_or_unsandboxed_decoder_route():
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    routes = policy.routes()
    assert routes['polkit'] == {'polkit': 'polkit', 'bwrap': 'glycin-bwrap'}
    assert routes['glycin-bwrap'] == {'bwrap-native': 'glycin-bwrap', 'glycin': 'glycin'}
    assert routes['glycin'] == {}
    assert {source for source, targets in routes.items() if 'glycin' in targets} == {'bwrap', 'glycin-bwrap'}
    for distribution in ('ubuntu', 'fedora'):
        generated = (policy.apparmor if distribution == 'ubuntu' else policy.selinux)(
            policy.executables(distribution))
        assert 'GLYCIN_DISABLE_SANDBOX' not in generated
        assert '/usr/bin/snap' not in generated
    generated = policy.apparmor(policy.executables('ubuntu'))
    sandbox = generated.split('profile onpc-kiosk-glycin-bwrap ', 1)[1].split('\n}\n', 1)[0]
    decoder = generated.split('profile onpc-kiosk-glycin ', 1)[1].split('\n}\n', 1)[0]
    for name in policy.GLYCIN_LOADERS:
        assert f'{policy.GLYCIN_DIRECTORY}/{name} Px -> onpc-kiosk-glycin-bwrap//&onpc-kiosk-glycin,' in sandbox
    assert '-> onpc-kiosk-service' not in sandbox
    assert '-> onpc-kiosk-webkit' not in sandbox
    assert '  userns,' in sandbox and '  capability sys_admin,' in sandbox
    assert 'mount options=(rw, rbind) /oldroot/usr/ -> /newroot/usr/,' in sandbox
    assert 'mount fstype=tmpfs -> /newroot/{tmp,tmp-home,tmp-run,dev,dev/shm}/,' in sandbox
    assert 'mount options=(rw, rbind) /oldroot/etc/ld.so.cache -> /newroot/etc/ld.so.cache,' in sandbox
    assert 'mount options=(rw, rbind) /oldroot/etc/fonts/conf.d/ -> /newroot/etc/fonts/conf.d/,' in sandbox
    assert 'deny /{,tmp/}newroot/{usr,lib,lib64,bin,sbin}/**[^/] wkl,' in sandbox
    assert '  userns,' not in decoder and '  capability sys_admin,' not in decoder
    assert ' Px ' not in decoder and ' ix,' not in decoder
    generated = policy.selinux(policy.executables('fedora'))
    assert '(allow onpc_kiosk_glycin_bwrap_t self (user_namespace (create)))' in generated
    assert '(allow onpc_kiosk_glycin_t self (user_namespace (create)))' not in generated
    assert '(allow onpc_kiosk_glycin_t self (capability (sys_admin' not in generated


def test_native_bootstrap_permissions_do_not_expand_payload_or_initial_namespace():
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    generated = policy.apparmor(policy.executables('ubuntu'))
    for domain in policy.DOMAINS:
        profile = generated.split(f'profile onpc-kiosk-{domain} ', 1)[1].split('\n}\n', 1)[0]
        assert ('  capability net_admin,' in profile) == (domain in ('bwrap', 'glycin-bwrap'))
        assert ('  / r,' in profile) == (domain in ('polkit', 'bwrap', 'glycin-bwrap'))
    generated = policy.selinux(policy.executables('fedora'))
    network_admin = [line for line in generated.splitlines()
                     if 'net_admin' in line or 'nlmsg_write' in line]
    assert network_admin == [line for name in ('bwrap', 'glycin_bwrap') for line in (
        f'(allow onpc_kiosk_{name}_t self (cap_userns (net_admin)))',
        f'(allow onpc_kiosk_{name}_t self (netlink_route_socket (nlmsg_write)))')]
    assert 'sys_ptrace' not in '\n'.join(line for line in generated.splitlines()
                                      if line.startswith('(allow onpc_kiosk_glycin'))
    assert [line for line in generated.splitlines()
            if ' fs_t (filesystem ' in line] == [
        f'(allow onpc_kiosk_{name}_t fs_t (filesystem (remount unmount)))'
        for name in ('bwrap', 'glycin_bwrap')]
    assert [line for line in generated.splitlines()
            if ' tmpfs_t (file (mounton))' in line] == [
        f'(allow onpc_kiosk_{name}_t tmpfs_t (file (mounton)))'
        for name in ('bwrap', 'glycin_bwrap')]
    assert [line for line in generated.splitlines() if ' sysfs_t (filesystem ' in line] == [
        '(allow onpc_kiosk_bwrap_t sysfs_t (filesystem (remount)))']
    assert [line for line in generated.splitlines() if ' locale_t (file (mounton))' in line] == [
        '(allow onpc_kiosk_bwrap_t locale_t (file (mounton)))']
    assert [line for line in generated.splitlines() if 'onpc_kiosk_scanner_exec_t (file (mounton))' in line] == [
        '(allow onpc_kiosk_bwrap_t onpc_kiosk_scanner_exec_t (file (mounton)))']
    assert [line for line in generated.splitlines() if 'onpc_kiosk_service_exec_t (file (mounton))' in line] == [
        '(allow onpc_kiosk_bwrap_t onpc_kiosk_service_exec_t (file (mounton)))']
    assert [line for line in generated.splitlines() if ' bin_t (file (mounton))' in line] == [
        '(allow onpc_kiosk_bwrap_t bin_t (file (mounton)))']
    assert not any(' bin_t (file (' in line and 'execute' in line for line in generated.splitlines())
    assert {line for line in generated.splitlines() if line.startswith('(allow onpc_kiosk') and
            '(file (' in line and 'mounton' in line} == {
        '(allow onpc_kiosk_bwrap_t tmpfs_t (file (mounton)))',
        '(allow onpc_kiosk_glycin_bwrap_t tmpfs_t (file (mounton)))',
        '(allow onpc_kiosk_bwrap_t locale_t (file (mounton)))',
        '(allow onpc_kiosk_bwrap_t onpc_kiosk_scanner_exec_t (file (mounton)))',
        '(allow onpc_kiosk_bwrap_t onpc_kiosk_service_exec_t (file (mounton)))',
        '(allow onpc_kiosk_bwrap_t bin_t (file (mounton)))',
    }


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_native_bubblewrap_requires_the_pinned_launcher(distribution):
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    entries = policy.executables(distribution)
    assert [entry for entry in entries if entry['role'].startswith('bwrap')] == [
        dict(role='bwrap', paths=['/usr/bin/bwrap'], source=policy.PREFIX + 'bwrap'),
        dict(role='bwrap-native', paths=[policy.PREFIX + 'bwrap'], source='/usr/bin/bwrap')]
    assert {source: targets['bwrap-native'] for source, targets in policy.routes().items()
            if 'bwrap-native' in targets} == {'bwrap': 'bwrap', 'glycin-bwrap': 'glycin-bwrap'}
    generated = policy.apparmor(entries)
    for domain in policy.DOMAINS:
        profile = generated.split(f'profile onpc-kiosk-{domain} ', 1)[1].split('\n}\n', 1)[0]
        bootstrap = domain in ('bwrap', 'glycin-bwrap')
        assert (f'{policy.PREFIX}bwrap ix,' in profile) == bootstrap
        assert ('mount options=(rw, rbind) /oldroot/usr/bin/ -> /newroot/usr/bin/,' in profile) == bootstrap
        if bootstrap:
            assert [line.strip() for line in profile.splitlines() if 'audit deny ' in line] == [
                'audit deny /{,tmp/}newroot/{usr,lib,lib64,bin,sbin}/**[^/] wkl,',
                'audit deny /{usr,lib,lib64,bin,sbin}/**[^/] wkl,']
            assert '/newroot/usr/bin/xdg-dbus-proxy w' not in profile
        aliases = [line.strip() for line in profile.splitlines()
                   if 'mount options=(rw, rbind) /oldroot/usr/lib' in line and
                   ' -> /newroot/lib' in line]
        assert aliases == ([f'mount options=(rw, rbind) /oldroot/usr/{path}/ -> /newroot/{path}/,'
                            for path in ('lib', 'lib64')] if domain == 'bwrap' else [])
        webkit_directories = {str(Path(path).parent) for entry in entries if entry['role'] == 'webkit'
                              for path in entry['paths']}
        for directory in webkit_directories:
            for path in (directory, directory + '/injected-bundle'):
                assert (f'mount options=(rw, rbind) /oldroot{path}/ -> '
                        f'/newroot{path}/,' in profile) == (domain == 'bwrap')
        assert ('mount options=(rw, rbind) /oldroot/usr/share/zoneinfo/** -> '
                '/newroot/usr/share/zoneinfo/**,' in profile) == (domain == 'bwrap')
        assert ('mount options=(rw, rbind) /oldroot/dev/udmabuf -> '
                '/newroot/dev/udmabuf,' in profile) == (domain == 'bwrap')
        for entry in entries:
            if entry['role'] == 'scanner':
                for path in entry['paths']:
                    for file in (path, str(Path(path).with_name('gst-ptp-helper'))):
                        assert (f'mount options=(rw, rbind) /oldroot{file} -> '
                                f'/newroot{file},' in profile) == (domain == 'bwrap')


def test_native_bubblewrap_flags_match_apparmor_normalization_at_finite_paths():
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    generated = policy.apparmor(policy.executables('ubuntu'))
    for domain in ('bwrap', 'glycin-bwrap'):
        profile = generated.split(f'profile onpc-kiosk-{domain} ', 1)[1].split('\n}\n', 1)[0]
        assert 'mount options=(rw, silent, rslave) -> /,' in profile
        assert 'mount options=(rw, silent, rprivate) -> /oldroot/,' in profile
        assert 'mount options=(rw, rbind) /oldroot/dev/null -> /newroot/dev/null,' in profile
        assert 'mount options=(rw, rbind) /oldroot/etc/ld.so.cache -> /newroot/etc/ld.so.cache,' in profile
        assert 'mount options=(rw, rbind) /oldroot/usr/ -> /newroot/usr/,' in profile
        assert 'mount options=(rw, rbind) /bindfile?????? -> /newroot/.flatpak-info,' in profile
        assert '/memfd:flatpak-info' not in profile
        assert ('mount options=(rw, rbind) /oldroot/run/user/*/{,**} -> '
                '/newroot/run/user/*/{,**},' in profile)
        assert ('mount options=(rw, bind) /oldroot/home/oh-no-parent-control/{,**} -> '
                '/newroot/home/oh-no-parent-control/{,**},' in profile)
        assert 'mount options in (ro, silent, remount, bind, nosuid, nodev, noexec, relatime, noatime, nodiratime) -> /newroot/**,' in profile
        assert '  mount,' not in profile
        assert 'silent, rbind' not in profile and 'silent, bind)' not in profile
        assert 'silent' not in '\n'.join(line for line in profile.splitlines()
                                       if 'mount fstype=' in line)


def test_native_bubblewrap_launcher_preserves_arguments_environment_and_descriptors(tmp_path):
    capture = tmp_path / 'capture'
    capture.write_text('#!/usr/bin/python3 -I\nimport json, os, sys\n'
        'print(json.dumps([sys.argv[1:], os.environ["ONPC_PRIVATE_CAPTURE"], '
        'os.read(int(sys.argv[-1]), 256).decode()]))\n')
    capture.chmod(0o700)
    source = tmp_path / 'launcher.c'
    source.write_text((ROOT / 'tools/kiosk_bwrap.c').read_text().replace(
        '"/usr/libexec/oh-no-parent-control-kiosk-bwrap"', json.dumps(str(capture))))
    launcher = tmp_path / 'launcher'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-o', str(launcher), str(source)],
                   check=True, capture_output=True, timeout=30)
    with (tmp_path / 'sealed-arguments').open('w+b') as inherited:
        inherited.write(b'--unshare-pid\0--proc\0/proc\0')
        inherited.seek(0)
        arguments = ['--args', str(inherited.fileno()), '--', '/usr/bin/xdg-dbus-proxy',
                     '--fd=' + str(inherited.fileno()), str(inherited.fileno())]
        result = subprocess.run([str(launcher), *arguments], pass_fds=(inherited.fileno(),),
            env={**os.environ, 'ONPC_PRIVATE_CAPTURE': 'preserved'}, capture_output=True,
            text=True, check=True, timeout=5)
    assert json.loads(result.stdout) == [
        ['--ro-bind', '/usr/bin', '/usr/bin', *arguments], 'preserved',
        '--unshare-pid\0--proc\0/proc\0']
    # An installed launcher outside the admitted namespace must refuse its
    # unchanged source inode instead of recursively executing itself.
    capture.unlink()
    capture.hardlink_to(launcher)
    result = subprocess.run([str(launcher)], capture_output=True, timeout=5)
    assert result.returncode == 1 and result.stdout == b''
    assert result.stderr == b'onpc.kiosk sandbox startup outcome=failed\n'


def test_vendor_password_helper_permissions_remain_limited_to_measured_protocol():
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    generated = policy.selinux(policy.executables('fedora'))
    assert [line for line in generated.splitlines() if line.startswith('(allow policykit_auth_t ')] == [
        '(allow policykit_auth_t onpc_kiosk_polkit_t (fifo_file (read write)))',
        '(allow policykit_auth_t onpc_kiosk_runtime_t (dir (search getattr)))',
        '(allow policykit_auth_t onpc_kiosk_runtime_t (lnk_file (read)))',
    ]
    assert '(typetransition onpc_kiosk_polkit_t policykit_auth_exec_t process policykit_auth_t)' in generated
    assert not any('policykit_auth_t' in roles for roles in policy.routes().values())
    assert [line for line in generated.splitlines() if line.startswith('(allow chkpwd_t ')] == [
        '(allow chkpwd_t onpc_kiosk_runtime_t (dir (search getattr)))',
        '(allow chkpwd_t onpc_kiosk_runtime_t (lnk_file (read)))',
    ]
    assert not any('chkpwd' in roles for roles in policy.routes().values())
    generated = policy.apparmor(policy.executables('ubuntu'))
    helper_entries = [line.strip() for line in generated.splitlines() if 'polkit-agent-helper-1' in line]
    assert helper_entries == ['/usr/lib/polkit-1/polkit-agent-helper-1 Cx -> password,']


def test_selinux_scanner_pipe_protocol_is_limited_to_admitted_actual_parents():
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    generated = policy.selinux(policy.executables('fedora'))
    assert {source for source, targets in policy.routes().items()
            if targets.get('scanner') == 'scanner'} == {'app', 'webkit'}
    rules = [line for line in generated.splitlines()
             if line.startswith('(allow onpc_kiosk_scanner_t ') and ' (fifo_file ' in line]
    assert rules == [f'(allow onpc_kiosk_scanner_t onpc_kiosk_{parent}_t '
                     '(fifo_file (read write getattr ioctl)))' for parent in ('app', 'webkit')]
    assert '(typeattributeset onpc_kiosk_clients (onpc_kiosk_scanner_t))' not in generated
    assert not policy.routes()['scanner']
    assert '(allow onpc_kiosk_scanner_t onpc_kiosk_service_t (fifo_file ' not in generated


def test_selinux_gpu_mapping_is_limited_to_renderer_roles():
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    generated = policy.selinux(policy.executables('fedora'))
    # The compositor and both GTK renderers need mmap in addition to device I/O.
    # The notification provider paints in its own domain, not the request app's.
    # Keep character-device mapping out of the shared domain/client attributes,
    # scanners, launchers and unrelated device types.
    mappings = [line for line in generated.splitlines()
                if ' (chr_file (' in line and 'map' in line]
    assert mappings == [
        f'(allow onpc_kiosk_{role}_t dri_device_t (chr_file (map)))'
        for role in ('service', 'app', 'notifications')]


def test_selinux_entrypoint_mappings_preserve_fixed_execution_routes():
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    generated = policy.selinux(policy.executables('fedora'))
    assert '(typeattributeset can_change_object_identity (onpc_kiosk_manager_t))' in generated
    assert generated.count('(typeattributeset can_change_object_identity ') == 1
    assert '(allow onpc_kiosk_service_t security_t (security (compute_av)))' in generated
    assert '(allow onpc_kiosk_domains onpc_kiosk_service_t (dbus (acquire_svc)))' in generated
    assert '(allow onpc_kiosk_domains domain (dbus (acquire_svc)))' not in generated
    assert '(allow xdm_t systemd_unit_file_t (service (status)))' in generated
    assert '(allow xdm_t systemd_unit_file_t (service (start' not in generated
    assert '(allow onpc_kiosk_service_t xdm_unit_file_t (service (start status)))' in generated
    assert '(allow onpc_kiosk_service_t dbusd_unit_file_t (service (stop)))' in generated
    assert '(allow onpc_kiosk_service_t dri_device_t (chr_file (map)))' in generated
    assert '(allow onpc_kiosk_domains dri_device_t (chr_file (map)))' not in generated
    assert '(allow onpc_kiosk_service_t onpc_kiosk_manager_t (system (reload status start)))' in generated
    assert '(allow onpc_kiosk_scanner_t onpc_kiosk_runtime_t (lnk_file (read getattr)))' in generated
    assert '(allow onpc_kiosk_scanner_t onpc_kiosk_app_t (fifo_file (read write getattr ioctl)))' in generated
    assert '(allow onpc_kiosk_gate_t onpc_kiosk_manager_t (system (status)))' in generated
    assert '(allow onpc_kiosk_domains onpc_kiosk_manager_t (system ' not in generated
    assert '(allow onpc_kiosk_domains xdm_unit_file_t (service ' not in generated
    assert 'unconfined_t' not in generated
    assert '(allow xdm_t var_run_t (file (read' not in generated
    for parent in ('/run', '/var/run'):
        assert (f'(filecon "{parent}/oh-no-parent-control-kiosk-admission[.]lock" '
                'file (system_u object_r onpc_kiosk_runtime_t ((s0) (s0))))') in generated
    for caller in ('init_t', 'xdm_t'):
        assert (f'(typetransition {caller} var_run_t file '
                '"oh-no-parent-control-kiosk-admission.lock" onpc_kiosk_runtime_t)') in generated
    assert policy.routes()['manager-pam'] == {'manager': 'manager', 'executor': 'manager'}
    assert '(allow init_t onpc_kiosk_manager_pam_t (process (dyntransition)))' in generated
    assert generated.count('(dyntransition)') == 1
    assert '(allow onpc_kiosk_manager_pam_t kernel_t (unix_dgram_socket (write)))' in generated
    assert '(allow onpc_kiosk_manager_pam_t init_t (unix_dgram_socket (write)))' not in generated
    assert '(allow onpc_kiosk_domains domain (unix_dgram_socket (write)))' not in generated
    assert [line for line in generated.splitlines() if '(noatsecure)' in line] == [
        '(allow onpc_kiosk_manager_pam_t onpc_kiosk_manager_t (process (noatsecure)))']
    audit_rules = [line for line in generated.splitlines() if '(netlink_audit_socket ' in line]
    assert len(audit_rules) == 1 and audit_rules[0].startswith('(allow onpc_kiosk_manager_pam_t self ')
    assert 'nlmsg_relay' in audit_rules[0] and 'nlmsg_write' not in audit_rules[0]
    assert 'audit_control' not in generated
    for source, targets in policy.routes().items():
        for role, destination in targets.items():
            if destination == source:
                continue
            domain = 'onpc_kiosk_' + destination.replace('-', '_') + '_t'
            typ = 'onpc_kiosk_' + role.replace('-', '_') + '_exec_t'
            assert f'(allow {domain} {typ} (file (read open getattr map execute)))' in generated
            if role not in policy.routes()[destination]:
                assert f'(allow {domain} {typ} (file (execute_no_trans)))' not in generated


def test_selinux_policy_is_reproducible_across_python_hash_seeds(tmp_path):
    import sys

    policies = []
    for seed in ('1', '2'):
        destination = tmp_path / seed
        subprocess.run([sys.executable, str(ROOT / 'tools/kiosk_confinement_policy.py'),
                        '--distribution', 'fedora', '--output', str(destination)],
                       env={**os.environ, 'PYTHONHASHSEED': seed},
                       check=True, capture_output=True, timeout=10)
        policies.append((destination / 'onpc-kiosk.cil').read_bytes())
    assert policies[0] == policies[1]


def test_apparmor_policy_compiles_without_loading_kernel_policy(tmp_path):
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    policy.generate(tmp_path, 'ubuntu')
    result = subprocess.run(
        ['/usr/sbin/apparmor_parser', '-Q', '-T', str(tmp_path / 'onpc-kiosk.apparmor')],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_kiosk_overrides_preserve_transition_settings_and_local_compositor_io(tmp_path, distribution):
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    policy.generate(tmp_path, distribution)
    policy.generate(tmp_path, distribution)
    overrides = sorted(path.relative_to(tmp_path / 'user-units').as_posix()
                       for path in (tmp_path / 'user-units').glob('*/*.conf'))
    assert overrides == (['dbus-broker.service.d/90-kiosk-confinement.conf',
                         'org.gnome.Kiosk@wayland.service.d/90-kiosk-confinement.conf']
        if distribution == 'fedora' else [
        'dbus.service.d/90-kiosk-confinement.conf',
        'oh-no-parent-control-wellbeing.service.d/90-kiosk-confinement.conf',
        'org.gnome.Kiosk@wayland.service.d/90-kiosk-confinement.conf',
        'wireplumber.service.d/90-kiosk-confinement.conf'])
    assert (tmp_path / 'user-units/org.gnome.Kiosk@wayland.service.d/90-kiosk-confinement.conf').read_text().endswith(
        '[Service]\nEnvironment=GIO_USE_VFS=local\n')
    if distribution == 'fedora':
        assert not (tmp_path / 'session-data').exists()
        generated = (tmp_path / 'onpc-kiosk.cil').read_text()
        assert '(allow onpc_kiosk_service_t onpc_kiosk_service_t (process (noatsecure)))' not in generated
        assert (tmp_path / 'user-units' / overrides[0]).read_text().endswith(
            '[Service]\nExecStart=\nExecStart=/usr/libexec/oh-no-parent-control-kiosk-dbus\n')
    if distribution == 'ubuntu':
        assert (tmp_path / 'user-units/dbus.service.d/90-kiosk-confinement.conf').read_text().endswith(
            '[Service]\nEnvironment=XDG_DATA_DIRS='
            '/usr/share/oh-no-parent-control/confinement/session-data:/usr/local/share:/usr/share\n')
        services = tmp_path / 'session-data/dbus-1/services'
        assert sorted(path.name for path in services.iterdir()) == [
            'io.snapcraft.Launcher.service', 'io.snapcraft.Settings.service']
        for name in ('io.snapcraft.Settings', 'io.snapcraft.Launcher'):
            assert (services / (name + '.service')).read_text() == (
                '[D-BUS Service]\nName=' + name + '\nExec=/bin/false\n'
                'SystemdService=snapd.session-agent.service\n')
        masks = sorted(path.name for path in (tmp_path / 'user-units').iterdir()
                       if path.is_symlink())
        assert masks == sorted((
            'snapd.session-agent.service', 'snapd.session-agent.socket',
            'snap.snapd-desktop-integration.snapd-desktop-integration.service',
            'snap.prompting-client.daemon.service',
            'snap.firmware-updater.firmware-notifier.service',
            'snap.firmware-updater.firmware-notifier.timer'))
        for name in masks:
            assert (tmp_path / 'user-units' / name).is_symlink()
            assert (tmp_path / 'user-units' / name).readlink() == Path('/dev/null')
        generated = (tmp_path / 'onpc-kiosk.apparmor').read_text()
        assert '/usr/bin/pipewire Px -> onpc-kiosk-manager//&onpc-kiosk-pipewire,' in generated
        assert 'Px -> onpc-kiosk-bwrap//&onpc-kiosk-webkit,' in generated
        assert 'Px -> onpc-kiosk-bwrap//&onpc-kiosk-webkit//&onpc-kiosk-scanner,' in generated


@pytest.mark.parametrize('kiosk', [True, False], ids=['kiosk', 'ordinary'])
def test_kiosk_snap_dbus_overrides_precede_vendor_direct_execution(tmp_path, short_runtime, kiosk):
    import select
    import shlex
    from xml.sax.saxutils import escape
    policy = module(ROOT / 'tools/kiosk_confinement_policy.py')
    policy.generate(tmp_path / 'payload', 'ubuntu')
    vendor = tmp_path / 'vendor/dbus-1/services'
    vendor.mkdir(parents=True)
    probe = tmp_path / 'vendor-probe'
    # The canary does not acquire a bus name. Fail explicitly after recording
    # execution so activation returns promptly instead of waiting for a name.
    probe.write_text('#!/bin/sh\n/usr/bin/touch "$1"\nexit 7\n')
    probe.chmod(0o700)
    markers = {}
    for name in ('io.snapcraft.Settings', 'io.snapcraft.Launcher'):
        markers[name] = tmp_path / (name + '-vendor-was-executed')
        (vendor / (name + '.service')).write_text(
            '[D-BUS Service]\nName=' + name + '\nExec=' + shlex.quote(str(probe))
            + ' ' + shlex.quote(str(markers[name])) + '\n')
    configuration = tmp_path / 'private-session.conf'
    address = 'unix:path=' + str(short_runtime / 'kiosk-bus')
    configuration.write_text('<busconfig><type>session</type><listen>' + escape(address) +
        '</listen><auth>EXTERNAL</auth><standard_session_servicedirs/>'
        '<policy context="default"><allow send_destination="*" eavesdrop="true"/>'
        '<allow eavesdrop="true"/><allow own="*"/></policy></busconfig>')
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C',
        'XDG_DATA_DIRS': ((str(tmp_path / 'payload/session-data') + ':') if kiosk else '')
            + str(vendor.parents[1]),
        'XDG_DATA_HOME': str(tmp_path / 'empty-data'), 'XDG_RUNTIME_DIR': str(tmp_path)}
    # Deliberately omit systemd activation here. Even the required inert Exec
    # fallback must beat the vendor's direct command in standard service dirs.
    # An ordinary bus must still execute each untouched vendor definition.
    daemon = subprocess.Popen(['/usr/bin/dbus-daemon', '--nofork', '--nopidfile', '--nosyslog',
        '--config-file=' + str(configuration), '--print-address'], env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([daemon.stdout], [], [], 5)[0], 'private bus did not become ready'
        published = daemon.stdout.readline().strip()
        assert published.split(',guid=', 1)[0] == address
        address = published
        for name in ('io.snapcraft.Settings', 'io.snapcraft.Launcher'):
            result = subprocess.run(['/usr/bin/dbus-send', '--bus=' + address, '--print-reply',
                '--reply-timeout=5000', '--dest=org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus.StartServiceByName', 'string:' + name, 'uint32:0'],
                env=environment, capture_output=True, text=True, timeout=8)
            assert result.returncode != 0 and 'Spawn.ChildExited' in result.stderr, result.stderr
            assert ('status 1' if kiosk else 'status 7') in result.stderr, result.stderr
            assert markers[name].exists() is (not kiosk)
    finally:
        # Popen's direct child remains unreaped, so this identity cannot recycle.
        daemon.terminate()
        try:
            daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:
            daemon.kill()
            daemon.wait(timeout=5)
        daemon.stdout.close()
        daemon.stderr.close()


@pytest.fixture(scope='module')
def fixed_launchers(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-native-launchers')
    target = directory / 'capture'
    target.write_text('#!/usr/bin/python3 -I\nimport json, os, sys\n'
                      'print(json.dumps([sys.argv[1:], dict(os.environ)]))\n')
    target.chmod(0o700)
    source = directory / 'launcher.c'
    # Preserve all argument/environment code. Redirect only the final exec to
    # the private observer and use this fixture UID for the kiosk audio branch.
    source.write_text((ROOT / 'tools/kiosk_session.c').read_text()
                      .replace('execv(arguments[0], arguments)', f'execv("{target}", arguments)')
                      .replace('getpwnam("oh-no-parent-control")', 'getpwuid(getuid())'))
    paths = {}
    for role in ('app', 'notifications', 'notification-client', 'wellbeing', 'audio', 'packages', 'dbus'):
        executable = directory / role
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        f'-DKIOSK_LAUNCH_ROLE="{role}"', '-o', str(executable), str(source)],
                       check=True, capture_output=True, text=True, timeout=30)
        paths[role] = executable
    ordinary_source = directory / 'ordinary.c'
    ordinary_source.write_text(source.read_text().replace('getpwuid(getuid())',
        '&(struct passwd){.pw_uid = getuid() + 1}'))
    executable = directory / 'ordinary-audio'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-DKIOSK_LAUNCH_ROLE="audio"', '-o', str(executable), str(ordinary_source)],
                   check=True, capture_output=True, text=True, timeout=30)
    paths['ordinary-audio'] = executable
    return paths


@pytest.mark.parametrize('role', ['app', 'notifications', 'notification-client', 'wellbeing', 'audio', 'packages', 'dbus'])
def test_fixed_native_launchers_reject_arguments_and_ignore_code_configuration(fixed_launchers, role, tmp_path):
    entry = fixed_launchers[role]
    denied = subprocess.run([str(entry), '--eval=untrusted'], capture_output=True, timeout=5)
    assert denied.returncode == 1 and denied.stdout == b''
    environment = dict(os.environ, HOME=str(tmp_path), WAYLAND_SOCKET='13',
                       PYTHONPATH=str(tmp_path), GJS_PATH=str(tmp_path),
                       WIREPLUMBER_CONFIG_DIR=str(tmp_path), WIREPLUMBER_DATA_DIR=str(tmp_path),
                       WIREPLUMBER_MODULE_DIR=str(tmp_path), GST_PLUGIN_PATH=str(tmp_path),
                       RPM_CONFIGDIR=str(tmp_path), LUA_PATH=str(tmp_path), LUA_CPATH=str(tmp_path),
                       LUA_PATH_5_4=str(tmp_path), LUA_CPATH_5_4=str(tmp_path),
                       LUA_PATH_5_5=str(tmp_path), LUA_CPATH_5_5=str(tmp_path),
                       GIO_USE_VFS=str(tmp_path))
    result = subprocess.run([str(entry)], env=environment, capture_output=True,
                            text=True, check=True, timeout=5)
    arguments, observed = json.loads(result.stdout)
    assert observed['WAYLAND_SOCKET'] == '13'
    assert observed['GIO_USE_VFS'] == 'local'
    for name in ('PYTHONPATH', 'GJS_PATH', 'WIREPLUMBER_MODULE_DIR', 'GST_PLUGIN_PATH',
                 'RPM_CONFIGDIR', 'LUA_PATH_5_4', 'LUA_CPATH_5_4', 'LUA_PATH_5_5', 'LUA_CPATH_5_5'):
        assert name not in observed
    if role == 'audio':
        assert arguments == []
        assert observed['WIREPLUMBER_CONFIG_DIR'] == '/etc/wireplumber:/usr/share/wireplumber'
        assert observed['WIREPLUMBER_DATA_DIR'] == '/usr/share/wireplumber'
        assert observed['LUA_PATH'] == observed['LUA_CPATH'] == ''
    elif role == 'packages':
        from common.oh_no_parent_control_ui.system_info import RPM_DIAGNOSTIC_PACKAGES
        assert arguments[arguments.index('--') + 1:] == list(RPM_DIAGNOSTIC_PACKAGES)
        assert '~' not in arguments[arguments.index('--macros') + 1]
        assert observed['HOME'] == '/'
    elif role == 'wellbeing':
        assert arguments == ['-m', '/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/wellbeingService.js']
    elif role == 'dbus':
        assert arguments == ['--scope', 'user']
    else:
        assert arguments[0] == '-I'
        if role == 'notification-client':
            assert arguments[1:] == ['/usr/bin/gnome-service-client', '--tag=gnome-kiosk-notification',
                                     '/usr/libexec/oh-no-parent-control-kiosk-notifications']
    if role != 'audio':
        assert 'LUA_PATH' not in observed and 'LUA_CPATH' not in observed


def test_ordinary_audio_launcher_preserves_lua_and_configuration_environment(fixed_launchers, tmp_path):
    environment = dict(os.environ, HOME=str(tmp_path), LUA_PATH='./?.lua', LUA_CPATH='./?.so',
                       LUA_PATH_5_4='./versioned/?.lua', WIREPLUMBER_CONFIG_DIR=str(tmp_path))
    result = subprocess.run([str(fixed_launchers['ordinary-audio'])], env=environment,
                            capture_output=True, text=True, check=True, timeout=5)
    arguments, observed = json.loads(result.stdout)
    assert arguments == []
    assert observed == environment


def test_kiosk_audio_empty_lua_paths_block_actual_native_cwd_require(fixed_launchers, tmp_path):
    import ctypes.util
    library = ctypes.util.find_library('lua5.4') or ctypes.util.find_library('lua-5.4')
    if library is None:
        pytest.skip('installed Lua 5.4 runtime unavailable for native cwd-canary check')
    canary = tmp_path / 'onpc_private_lua_canary.lua'
    canary.write_text('return "private-cwd-canary"\n')
    captured = subprocess.run([str(fixed_launchers['audio'])], cwd=tmp_path,
                             env={'HOME': str(tmp_path)}, capture_output=True,
                             text=True, check=True, timeout=5)
    _, environment = json.loads(captured.stdout)
    probe = '''import ctypes, json, sys
lua = ctypes.CDLL(sys.argv[1])
lua.luaL_newstate.restype = ctypes.c_void_p
lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lua.luaL_loadstring.restype = ctypes.c_int
lua.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         ctypes.c_ssize_t, ctypes.c_void_p]
lua.lua_pcallk.restype = ctypes.c_int
lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
lua.lua_tolstring.restype = ctypes.c_char_p
lua.lua_close.argtypes = [ctypes.c_void_p]
state = lua.luaL_newstate()
assert state
try:
    lua.luaL_openlibs(state)
    assert lua.luaL_loadstring(state, b'return require("onpc_private_lua_canary")') == 0
    status = lua.lua_pcallk(state, 0, 1, 0, 0, None)
    result = lua.lua_tolstring(state, -1, None)
    print(json.dumps({'loaded': status == 0 and result == b'private-cwd-canary',
                      'missing': status != 0 and b'not found' in (result or b'')}))
finally:
    lua.lua_close(state)
'''
    for restricted in (False, True):
        child_environment = dict(environment)
        if not restricted:
            child_environment.pop('LUA_PATH')
            child_environment.pop('LUA_CPATH')
        result = subprocess.run([sys.executable, '-I', '-c', probe, library],
            cwd=tmp_path, env=child_environment, capture_output=True, text=True, check=True, timeout=5)
        assert json.loads(result.stdout) == {'loaded': not restricted, 'missing': restricted}


@pytest.fixture
def service_denial_evidence(census_model):
    helper = census_model
    account = SimpleNamespace(pw_uid=1234, pw_gid=1234)
    target = {'path': '/usr/bin/private-denied', 'device': 7, 'inode': 987,
              'audit_device': 'privatefs', 'audit_name': 'private-denied', 'sha256': 'target-digest'}
    unit, invocation, boot = 'private-denial.service', 'a' * 32, 'b' * 32

    def native(stage='EXEC'):
        return {'MESSAGE_ID': '641257651c1b4ec9a8624d7a40a9e1e7',
                'CODE_FILE': 'src/core/executor.c', 'USER_UNIT': unit,
                'USER_INVOCATION_ID': invocation, '_PID': '4321', '_UID': '1234',
                '_BOOT_ID': boot, 'EXECUTABLE': target['path'], 'ERRNO': '13',
                '__REALTIME_TIMESTAMP': '100000001',
                'MESSAGE': f'{unit}: Failed at step {stage} spawning {target["path"]}: Permission denied'}

    def audit(backend, profile=False):
        prefix = 'audit(100.001:71): pid=4321 '
        if backend == 'apparmor':
            return prefix + 'apparmor="DENIED" profile="onpc-kiosk-manager" ' + (
                'operation="change_onexec" name="unconfined" target="unconfined"' if profile else
                f'operation="exec" name="{target["path"]}" denied_mask="x" fsuid=1234 ouid=0')
        return prefix + 'avc:  denied ' + (
            '{ setexec } tclass=process ' if profile else
            '{ execute } tclass=file ino=987 name="private-denied" dev="privatefs" ') + (
            f'scontext={helper.MANAGER_SID} tcontext={helper.MANAGER_SID} permissive=0')

    return SimpleNamespace(account=account, target=target, unit=unit, invocation=invocation,
                           boot=boot, command=[target['path']], native=native, audit=audit)


@pytest.mark.parametrize('stage', ['EXEC', 'APPARMOR', 'SELINUX_CONTEXT'])
@pytest.mark.parametrize('fault', [None, 'pid', 'uid', 'unit', 'invocation', 'boot', 'target',
                                  'source', 'message-id', 'stale', 'missing-error',
                                  'wrong-error', 'wrong-stage', 'unrelated-setup', 'trusted-unit'])
def test_service_native_denial_requires_fresh_executor_failure(
        census_model, service_denial_evidence, stage, fault):
    evidence = service_denial_evidence
    row = evidence.native(stage)
    changes = {'pid': ('_PID', '14321'), 'uid': ('_UID', '0'),
               'unit': ('USER_UNIT', 'other.service'),
               'invocation': ('USER_INVOCATION_ID', 'c' * 32), 'boot': ('_BOOT_ID', 'd' * 32),
               'target': ('EXECUTABLE', '/usr/bin/other'),
               'source': ('CODE_FILE', 'src/core/service.c'), 'message-id': ('MESSAGE_ID', 'other'),
               'stale': ('__REALTIME_TIMESTAMP', '99999999'),
               'wrong-error': ('ERRNO', '2'), 'trusted-unit': ('_SYSTEMD_USER_UNIT', 'other.service')}
    if fault in changes:
        key, value = changes[fault]
        row[key] = value
    elif fault == 'missing-error':
        row.pop('ERRNO')
    elif fault == 'wrong-stage':
        row['MESSAGE'] = row['MESSAGE'].replace(f'step {stage}', 'step NAMESPACE')
    elif fault == 'unrelated-setup':
        row['MESSAGE'] = 'Failed to set up mount namespacing: Permission denied'
    assert census_model.service_native_denial(row, evidence.account, evidence.unit,
        evidence.invocation, '4321', evidence.command, stage, evidence.boot, 100) is (fault is None)


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('profile', [False, True], ids=['exec', 'profile'])
@pytest.mark.parametrize('fault', [None, 'pid', 'role', 'operation', 'target', 'unenforced'])
def test_service_audit_denial_requires_exact_enforcing_operation(
        census_model, service_denial_evidence, backend, profile, fault):
    evidence = service_denial_evidence
    line = evidence.audit(backend, profile)
    if fault == 'pid':
        line = line.replace('pid=4321', 'pid=14321')
    elif fault == 'role':
        line = line.replace('onpc-kiosk-manager', 'onpc-kiosk-app').replace(
            'onpc_kiosk_manager_t', 'onpc_kiosk_app_t')
    elif fault == 'operation':
        line = line.replace('change_onexec', 'change_profile').replace('operation="exec"',
            'operation="open"').replace('{ execute }', '{ read }').replace('{ setexec }', '{ transition }')
    elif fault == 'target':
        line = (line.replace('target="unconfined"', 'target="other"') if backend == 'apparmor' and profile
                else line.replace('name="/usr/bin/private-denied"', 'name="/usr/bin/other"')
                if backend == 'apparmor' else
                line.replace('tcontext=' + census_model.MANAGER_SID, 'tcontext=unconfined_u:unconfined_r:unconfined_t:s0')
                if profile else line.replace('ino=987', 'ino=988'))
    elif fault == 'unenforced':
        line = line.replace('apparmor="DENIED"', 'apparmor="ALLOWED"').replace('permissive=0', 'permissive=1')
    assert census_model.service_audit_denial(line, backend, '4321', evidence.target,
        evidence.account.pw_uid, profile=profile) is (fault is None)


@pytest.mark.parametrize('replacement', ['dev="otherfs"', ''])
def test_service_selinux_audit_refuses_wrong_or_missing_device(
        census_model, service_denial_evidence, replacement):
    evidence = service_denial_evidence
    line = evidence.audit('selinux').replace('dev="privatefs"', replacement)
    assert not census_model.service_audit_denial(line, 'selinux', '4321', evidence.target, 1234)


@pytest.mark.parametrize('case', ['private-name', 'canonical-path', 'wrong-name', 'conflicting-path'])
def test_service_selinux_audit_binds_private_copy_name_and_optional_canonical_path(
        census_model, service_denial_evidence, case):
    evidence = service_denial_evidence
    target = {**evidence.target, 'audit_name': '37'}
    line = evidence.audit('selinux').replace('name="private-denied"', 'name="37"')
    if case == 'canonical-path':
        line += ' path="' + target['path'] + '"'
    elif case == 'wrong-name':
        line = line.replace('name="37"', 'name="private-denied"')
    elif case == 'conflicting-path':
        line += ' path="/usr/bin/other"'
    assert census_model.service_audit_denial(line, 'selinux', '4321', target, 1234) is (
        case in ('private-name', 'canonical-path'))


@pytest.mark.parametrize('fault', [None, 'missing-loader', 'nonexecutable-loader', 'bad-elf',
                                  'truncated-loader', 'control-target', 'control-loader', 'garbage-loader'])
def test_service_target_measures_private_namespace_elf_and_loader(
        census_model, tmp_path, monkeypatch, fault):
    import hashlib
    import struct

    helper = census_model
    manager = tmp_path / 'manager'
    command, loader = tmp_path / 'program', tmp_path / 'loader'
    visible = manager / 'root' / command.relative_to('/')
    native = manager / 'root' / loader.relative_to('/')
    native.parent.mkdir(parents=True)
    interpreter = os.fsencode(loader) + b'\0'
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', header, 16, 3, 62, 1)
    struct.pack_into('<Q', header, 32, 64)
    struct.pack_into('<H', header, 52, 64)
    struct.pack_into('<HH', header, 54, 56, 1)
    program = bytearray(56)
    struct.pack_into('<I', program, 0, 3)
    struct.pack_into('<Q', program, 8, 120)
    struct.pack_into('<Q', program, 32, len(interpreter))
    payload = bytes(header + program) + interpreter
    loader_header = bytearray(header)
    struct.pack_into('<Q', loader_header, 32, 0)
    struct.pack_into('<H', loader_header, 56, 0)
    loader_payload = bytes(loader_header) + b'private native loader'
    command.write_bytes(payload + (b'control drift' if fault == 'control-target' else b''))
    command.chmod(0o755)
    loader.write_bytes(loader_payload + (b'control drift' if fault == 'control-loader' else b''))
    loader.chmod(0o755)
    visible.write_bytes(b'invalid' if fault == 'bad-elf' else
                        payload[:-1] if fault == 'truncated-loader' else payload)
    visible.chmod(0o755)
    if fault != 'missing-loader':
        native.write_bytes(b'garbage loader' if fault == 'garbage-loader' else loader_payload)
        native.chmod(0o644 if fault == 'nonexecutable-loader' else 0o755)
    info = visible.stat()
    mount = f'1 0 {os.major(info.st_dev)}:{os.minor(info.st_dev)} / / rw - tmpfs tmpfs rw'
    (manager / 'mountinfo').write_text(mount + '\n')
    if fault is not None:
        expected = FileNotFoundError if fault == 'missing-loader' else helper.guest.GuestError
        reasons = {'nonexecutable-loader': 'loader-not-executable', 'bad-elf': 'target-format',
                   'truncated-loader': 'elf-loader-missing', 'control-target': 'control-target-drift',
                   'control-loader': 'control-loader-drift', 'garbage-loader': 'loader-format'}
        with pytest.raises(expected, match=None if fault == 'missing-loader' else
                           'kiosk-service:' + reasons[fault]):
            helper.service_target(manager, str(command))
        return
    measured = helper.service_target(manager, str(command))
    entry = command.lstat()
    assert measured == {'path': str(command), 'device': info.st_dev, 'inode': info.st_ino,
        'sha256': hashlib.sha256(payload).hexdigest(), 'audit_device': 'tmpfs', 'mount': mount,
        'audit_name': command.name,
        'entry': {'device': entry.st_dev, 'inode': entry.st_ino, 'mode': entry.st_mode,
                  'uid': entry.st_uid, 'gid': entry.st_gid},
        'loader': {'path': str(loader), 'sha256': hashlib.sha256(loader_payload).hexdigest()}}


@pytest.mark.parametrize('bind_first', [False, True], ids=['root-first', 'bind-first'])
def test_service_target_file_bind_uses_backing_device_despite_anonymous_stat_device(
        census_model, tmp_path, monkeypatch, bind_first):
    import struct

    helper = census_model
    manager = tmp_path / 'manager'
    command = tmp_path / 'private program'
    visible = manager / 'root' / command.relative_to('/')
    visible.parent.mkdir(parents=True)
    # A static ELF-shaped target needs no interpreter or live executable reads.
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<Q', header, 32, 64)
    struct.pack_into('<HH', header, 54, 56, 1)
    payload = bytes(header) + bytes(56)
    for path in (command, visible):
        path.write_bytes(payload)
        path.chmod(0o755)
    backing = tmp_path / 'backing-block'
    backing.touch()
    sysfs = tmp_path / 'sysfs'
    (sysfs / '8:17').mkdir(parents=True)
    (sysfs / '8:17/uevent').write_text('MAJOR=8\nMINOR=17\nDEVNAME=private-disk1\n')
    monkeypatch.setattr(helper, 'Path', lambda value: sysfs if value == '/sys/dev/block' else
                        backing if value == '/dev/private-disk1' else Path(value))
    original_stat = Path.stat
    anonymous_device = os.makedev(0, 421)

    def metadata(path, *args, **kwargs):
        info = original_stat(path, *args, **kwargs)
        if path == backing:
            return SimpleNamespace(st_mode=stat.S_IFBLK | 0o600, st_rdev=os.makedev(8, 17))
        if path == visible:
            return SimpleNamespace(st_mode=info.st_mode, st_dev=anonymous_device, st_ino=info.st_ino)
        return info

    monkeypatch.setattr(Path, 'stat', metadata)
    root_mount = '1 0 0:7 / / rw - tmpfs tmpfs rw'
    escaped_target = str(command).replace(' ', r'\040')
    bind_mount = f'2 1 8:17 /subvolume/program {escaped_target} ro - btrfs /dev/private-disk1 ro'
    mounts = [bind_mount, root_mount] if bind_first else [root_mount, bind_mount]
    (manager / 'mountinfo').write_text('\n'.join(mounts) + '\n')
    measured = helper.service_target(manager, str(command))
    assert measured['device'] == anonymous_device
    assert measured['mount'] == bind_mount
    assert measured['audit_device'] == 'private-disk1'
    assert measured['audit_name'] == 'program'
    assert 'loader' not in measured


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('mode', ['transient', 'strict-profile', 'writable'])
@pytest.mark.parametrize('fault', [None, 'old-audit', 'replayed-audit', 'missing-time',
                                  'native-setup', 'executor-target', 'unit-replaced', 'target-replaced'])
def test_service_denial_composes_fresh_proofs_and_guards_owned_reset(
        census_model, service_denial_evidence, tmp_path, monkeypatch, backend, mode, fault):
    helper, evidence = census_model, service_denial_evidence
    strict = mode == 'strict-profile'
    stage = ('APPARMOR' if backend == 'apparmor' else 'SELINUX_CONTEXT') if strict else 'EXEC'
    status = (231 if backend == 'apparmor' else 229) if strict else 203
    setting = ('AppArmorProfile=unconfined' if backend == 'apparmor'
               else 'SELinuxContext=unconfined_u:unconfined_r:unconfined_t:s0') if strict else None
    row = evidence.native(stage)
    if fault == 'native-setup':
        row['MESSAGE'] = 'Failed to set up credentials: Permission denied'
    line = evidence.audit(backend, strict)
    if fault == 'old-audit':
        line = line.replace('100.001', '99.999')
    elif fault == 'missing-time':
        line = line.replace('audit(100.001:71): ', '')
    audit_reads = iter([line if fault == 'replayed-audit' else '', line])

    def wait_for(predicate, reason):
        helper.guest.require(predicate(), reason)

    monkeypatch.setitem(sys.modules, 'system_kiosk_platform', SimpleNamespace(
        settle_kernel_audit=lambda selected: None, kernel_audit=lambda selected: next(audit_reads),
        wait_for=wait_for))
    monkeypatch.setattr(helper, 'PROC', tmp_path / 'proc')
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: 500)
    monkeypatch.setattr(helper, 'process_identity', lambda process: ('start', 1, ('1234',) * 4))
    targets = iter([evidence.target, {**evidence.target, 'sha256': 'replacement'}
                    if fault == 'target-replaced' else evidence.target])
    monkeypatch.setattr(helper, 'service_target', lambda manager, command: next(targets))
    monkeypatch.setattr(helper.time, 'time', lambda: 100)
    boot_file = tmp_path / 'boot-id'
    boot_file.write_text(evidence.boot)
    monkeypatch.setattr(helper, 'Path', lambda value: boot_file
                        if value == '/proc/sys/kernel/random/boot_id' else Path(value))
    properties = {'InvocationID': evidence.invocation, 'ExecMainPID': '4321',
                  'ExecMainCode': '1', 'ExecMainStatus': str(status), 'Result': 'exit-code',
                  'ActiveState': 'failed',
                  'ExecStart': '{ path=' + evidence.command[0] + ' ; argv[]=private ; pid=4321 ; code=exited ; }'}
    if fault == 'executor-target':
        properties['ExecStart'] = properties['ExecStart'].replace(evidence.command[0], '/usr/bin/other')
    commands, records = [], {}

    def user_command(account, command, *, check=True):
        commands.append(command)
        if '--property=InvocationID,ActiveState' in command:
            return b'InvocationID=\nActiveState=inactive\n'
        if any(value.startswith('--property=InvocationID,ExecMainPID,') for value in command):
            return ''.join(f'{key}={value}\n' for key, value in properties.items()).encode()
        if '--property=InvocationID' in command:
            return (('c' * 32 if fault == 'unit-replaced' else evidence.invocation) + '\n').encode()
        helper.guest.commands.last_returncode = status
        return b''

    def run(command):
        if command[0] == 'systemctl':
            return 'manager-invocation'
        if '--show-cursor' in command:
            return '-- cursor: private-cursor'
        assert '--after-cursor=private-cursor' in command
        return json.dumps(row)

    monkeypatch.setattr(helper, 'user_command', user_command)
    monkeypatch.setattr(helper.guest, 'run', run)
    monkeypatch.setattr(helper.guest, 'commands', SimpleNamespace(last_returncode=status))
    reasons = {'old-audit': 'kernel-denial-not-observed', 'replayed-audit': 'kernel-denial-not-observed',
               'missing-time': 'kernel-denial-not-observed', 'native-setup': 'native-denial-not-observed',
               'executor-target': 'executor-target', 'unit-replaced': 'unit-replaced',
               'target-replaced': 'target-changed'}
    if fault is None:
        helper.require_service_denial(evidence.account, backend, evidence.unit, evidence.command,
            records.__setitem__, setting=setting, writable=mode == 'writable')
        assert records['onpc.kiosk.service-denial.' + evidence.unit + '.kernel-denial'] == line
    else:
        with pytest.raises(helper.guest.GuestError, match='kiosk-service:' + reasons[fault]):
            helper.require_service_denial(evidence.account, backend, evidence.unit, evidence.command,
                records.__setitem__, setting=setting, writable=mode == 'writable')
    resets = [command for command in commands if 'reset-failed' in command]
    assert resets == ([] if fault == 'unit-replaced' else
                      [['/usr/bin/systemctl', '--user', 'reset-failed', evidence.unit]])
    launch = commands[1]
    if mode == 'writable':
        assert launch == ['/usr/bin/systemctl', '--user', 'start', evidence.unit]
    else:
        assert launch[:5] == ['/usr/bin/systemd-run', '--user', '--wait', '--pipe', '--unit=' + evidence.unit]
        assert launch[5:] == (['--property=' + setting] if strict else []) + evidence.command


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'sibling-label', 'sibling-uid', 'sibling-namespace',
                                   'sibling-generation', 'host-namespace', 'invalid-generation',
                                   'manager-replaced', 'exited', 'thread-replaced'])
def test_manager_reexec_observation_requires_each_live_thread_boundary(
        census_model, tmp_path, monkeypatch, backend, fault):
    helper = census_model
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    manager = tmp_path / '42'
    namespace = 'mnt:[host]' if fault == 'host-namespace' else 'mnt:[private]'
    generation = 'unconfined\n' if fault == 'invalid-generation' else 'a' * 64 + '\n'
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    expected = 'onpc-kiosk-manager (enforce)' if backend == 'apparmor' else helper.MANAGER_SID
    marker = 'root/usr/share/oh-no-parent-control/confinement/generation'
    for target in (manager, manager / 'task/42', manager / 'task/43'):
        target.mkdir(parents=True, exist_ok=True)
        (target / 'stat').write_text('42 (fixture) S 1 ' + '0 ' * 17 + '100')
        (target / 'status').write_text('PPid:\t1\nUid:\t1002\t1002\t1002\t1002\n')
        (target / 'ns').mkdir()
        (target / 'ns/mnt').symlink_to('mnt:[other]' if target.name == '43' and
                                     fault == 'sibling-namespace' else namespace)
        (target / marker).parent.mkdir(parents=True)
        (target / marker).write_text('b' * 64 + '\n' if target.name == '43' and
                                   fault == 'sibling-generation' else generation)
        (target / attribute).parent.mkdir(parents=True)
        (target / attribute).write_text('unconfined' if target.name == '43' and
                                       fault == 'sibling-label' else expected)
    if fault == 'sibling-uid':
        (manager / 'task/43/status').write_text('PPid:\t1\nUid:\t1002\t0\t0\t0\n')
    (tmp_path / '1/ns').mkdir(parents=True)
    (tmp_path / '1/ns/mnt').symlink_to('mnt:[host]')
    calls, closed = [], []
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda pid: 900)
    monkeypatch.setattr(helper.os, 'close', closed.append)
    monkeypatch.setattr(helper, 'exited', lambda fd: fault == 'exited')
    def manager_pid(unit):
        calls.append(unit)
        return 99 if fault == 'manager-replaced' and len(calls) > 1 else 42
    monkeypatch.setattr(helper, 'manager_pid', manager_pid)
    original = helper.census_thread_identity
    seen = {}
    def thread_identity(thread):
        value = original(thread)
        seen[thread] = seen.get(thread, 0) + 1
        return ('replacement', *value[1:]) if (fault == 'thread-replaced' and
                thread.name == '43' and seen[thread] > 1) else value
    monkeypatch.setattr(helper, 'census_thread_identity', thread_identity)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-confinement:manager-'):
            helper.manager_boundary(SimpleNamespace(pw_uid=1002), 'user@1002.service', backend)
    else:
        result = helper.manager_boundary(SimpleNamespace(pw_uid=1002), 'user@1002.service', backend)
        assert result == {'pid': 42, 'identity': ('100', 1, ('1002',) * 4),
                          'label': expected, 'namespace': namespace, 'generation': generation}
    assert closed == [900]


@pytest.mark.parametrize('directory', [True, False])
@pytest.mark.parametrize('body_error', [False, True])
def test_sibling_replacement_restores_exact_original_inode_and_content(
        census_model, tmp_path, monkeypatch, directory, body_error):
    helper = census_model
    monkeypatch.setattr(helper, 'SIBLING_PARENT', tmp_path)
    monkeypatch.setattr(helper.os, 'chown', lambda *args, **kwargs: None)
    path = tmp_path / 'owned'
    original = helper.sibling_create(path, 0o777 if directory else 0o644,
                                    os.getuid(), os.getgid(), b'original', directory=directory)
    row = dict(name=path.name, snapshot=original, directory=directory)

    def exercise():
        with helper.sibling_replacement(row) as replacement:
            assert replacement['snapshot']['identity'][:2] != original['identity'][:2]
            assert helper.sibling_snapshot(path) == replacement['snapshot']
            if body_error:
                raise RuntimeError('body-error')

    if body_error:
        with pytest.raises(RuntimeError, match='body-error'):
            exercise()
    else:
        exercise()
    assert helper.sibling_snapshot(path) == original
    assert not path.with_name('owned-saved').exists()


@pytest.mark.parametrize('fault', ['extra', 'content', 'mode', 'inode', 'symlink', 'hardlink'])
def test_sibling_cleanup_preserves_unknown_or_changed_inputs(
        census_model, tmp_path, fault):
    helper = census_model
    path = tmp_path / 'owned'
    path.mkdir()
    (path / 'canary').write_bytes(b'original')
    expected = helper.sibling_snapshot(path)
    if fault == 'extra':
        (path / 'unknown').write_bytes(b'foreign')
    elif fault == 'content':
        (path / 'canary').write_bytes(b'changed')
    elif fault == 'mode':
        path.chmod(0o700)
    elif fault == 'inode':
        path.rename(tmp_path / 'saved')
        path.mkdir()
        (path / 'canary').write_bytes(b'original')
    elif fault == 'symlink':
        (path / 'canary').rename(tmp_path / 'foreign')
        (path / 'canary').symlink_to(tmp_path / 'foreign')
    elif fault == 'hardlink':
        os.link(path / 'canary', tmp_path / 'another')
    with pytest.raises(helper.guest.GuestError, match='kiosk-sibling:'):
        helper.sibling_remove(path, expected)
    assert path.exists() and (path / 'canary').exists()


@pytest.mark.parametrize('fault', [None, 'contents', 'omitted-file', 'omitted-link', 'same-inode',
                                  'process-replaced'])
def test_sibling_private_view_reads_live_roots_and_refuses_exposure(
        census_model, tmp_path, monkeypatch, fault):
    helper = census_model
    proc = tmp_path / 'proc'
    process = proc / '42'
    share = process / 'root/usr/share'
    share.mkdir(parents=True)
    masked = share / 'masked'
    masked.mkdir()
    omitted = share / 'omitted'
    if fault == 'contents':
        (masked / 'mutable').write_bytes(b'exposed')
    elif fault == 'omitted-file':
        omitted.write_bytes(b'exposed')
    elif fault == 'omitted-link':
        omitted.symlink_to('missing')
    rows = [dict(name='masked', directory=True, snapshot={
        'identity': [masked.stat().st_dev, masked.stat().st_ino] if fault == 'same-inode' else [-1, -1]}),
        dict(name='omitted', directory=False)]
    monkeypatch.setattr(helper, 'PROC', proc)
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1234))
    census = Mock(return_value={'backend': 'apparmor', 'confined_thread_roles': {'app': 1}})
    monkeypatch.setattr(helper, 'census', census)
    identities = iter([('start', 1, ('1234',) * 4),
                       ('changed' if fault == 'process-replaced' else 'start', 1, ('1234',) * 4)])
    monkeypatch.setattr(helper, 'process_identity', lambda _: next(identities))
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda _: os.open('/dev/null', os.O_RDONLY))
    monkeypatch.setattr(helper, 'exited', lambda _: False)
    records = {}
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-sibling:'):
            helper.sibling_private_views(rows, records.__setitem__, 'test')
    else:
        helper.sibling_private_views(rows, records.__setitem__, 'test')
        assert json.loads(records['onpc.kiosk.sibling.private.test'])['processes'] == 1
    census.assert_called_once_with()


@pytest.mark.parametrize('stage', ['configuration', 'policy'])
@pytest.mark.parametrize('fault', [None, 'native-admitted', 'load-accepted', 'wrong-load-refusal',
                                   'extended-load-refusal',
                                   'ownership-changed', 'attestation-changed',
                                   'policy-unenforced', 'recovery-failed', 'manager-active'])
@pytest.mark.parametrize('diagnostic_suffix', [b'', b' source=kiosk-confinement line=547'],
                         ids=['reason-only', 'source-location'])
def test_payload_drift_requires_native_and_boot_refusal_before_exact_recovery(
        census_model, tmp_path, monkeypatch, stage, fault, diagnostic_suffix):
    helper = census_model
    config, policy = tmp_path / 'config.json', tmp_path / 'onpc-kiosk.apparmor'
    originals = {config: b'{"backend":"apparmor"}\n', policy: b'original policy\n'}
    for path, data in originals.items():
        path.write_bytes(data)
    identities = {path: (path.stat().st_dev, path.stat().st_ino, path.stat().st_mtime_ns)
                  for path in originals}
    current = {'drift': None, 'loaded': None}
    events, records = [], {}
    def drift():
        changed = [name for name, path in (('configuration', config), ('policy', policy))
                   if path.read_bytes() != originals[path]]
        assert len(changed) <= 1
        return changed[0] if changed else None
    def first_exec(account, directory, command, *, service, armed=True):
        selected = drift()
        assert command == ['/usr/lib/systemd/systemd', '--version'] and service == 'systemd-user'
        events.append(('native', selected, armed))
        if not armed:
            assert selected is not None
            current['drift'] = selected
            return (0, b'') if fault == 'native-admitted' and selected == stage else (125, b'{"pam":14}')
        assert selected is None
        for path, identity in identities.items():
            actual = path.stat()
            assert (actual.st_dev, actual.st_ino, actual.st_mtime_ns) == identity
        return (125, b'{"pam":14}') if (fault == 'recovery-failed' and
                current['loaded'] == stage) else (0, b'')
    monkeypatch.setattr(helper, 'first_exec', first_exec)
    def manager_pid(unit):
        assert unit == 'user@1002.service'
        return 42 if fault == 'manager-active' and (stage == 'configuration' or
                current['loaded'] == 'configuration') else 0
    monkeypatch.setattr(helper, 'manager_pid', manager_pid)
    def ownership():
        return 'changed' if fault == 'ownership-changed' and current['loaded'] == stage else 'original'
    def attestation(path):
        assert str(path) == '/var/lib/oh-no-parent-control/kiosk-confinement.json'
        return 'changed' if fault == 'attestation-changed' and current['loaded'] == stage else 'original'
    monkeypatch.setitem(sys.modules, 'system_removal', SimpleNamespace(
        admission_removal_state=ownership, private_recovery_record=attestation))
    def enforcing(value):
        assert value == {'backend': 'apparmor'}
        events.append(('enforcing', drift()))
        if fault == 'policy-unenforced' and current['loaded'] == stage:
            raise ValueError('policy-unenforced')
    monkeypatch.setattr(helper.runpy, 'run_path', lambda path: {'enforcing': enforcing})
    def load(command, **options):
        assert command == ['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'load']
        assert options == {'timeout': 90, 'check': False, 'merge_stderr': True}
        selected = drift()
        assert selected == current['drift']
        events.append(('load', selected))
        current['loaded'] = selected
        helper.guest.commands.last_returncode = 0 if fault == 'load-accepted' and selected == stage else 1
        reason = (b'other' if fault == 'wrong-load-refusal' and selected == stage else
                  b'policy-load-incomplete-reconfigure-required-extra'
                  if fault == 'extended-load-refusal' and selected == stage else
                  b'policy-load-incomplete-reconfigure-required')
        return b'reason=' + reason + diagnostic_suffix + b';'
    monkeypatch.setattr(helper.guest, 'commands', SimpleNamespace(run=load, last_returncode=None))
    if fault:
        category = ('generation-admitted' if fault == 'native-admitted' else
                    'payload-drift-boot-reattested' if fault in (
                        'load-accepted', 'wrong-load-refusal', 'extended-load-refusal') else
                    'payload-drift-ownership-changed' if fault in ('ownership-changed', 'attestation-changed') else
                    'policy-unenforced' if fault == 'policy-unenforced' else
                    'payload-drift-manager-active' if fault == 'manager-active' else
                    'payload-attestation-recovery')
        with pytest.raises((helper.guest.GuestError, ValueError), match=category):
            helper.verify_payload_attestation_faults(SimpleNamespace(pw_uid=1002), tmp_path,
                                                     policy, records.__setitem__)
        assert 'onpc.kiosk.' + stage + '-attestation-recovered' not in records
    else:
        helper.verify_payload_attestation_faults(SimpleNamespace(pw_uid=1002), tmp_path,
                                                 policy, records.__setitem__)
        assert events == [('native', None, True), ('enforcing', None),
                          ('native', 'configuration', False), ('load', 'configuration'),
                          ('enforcing', 'configuration'), ('native', None, True), ('enforcing', None),
                          ('native', 'policy', False), ('load', 'policy'),
                          ('enforcing', 'policy'), ('native', None, True), ('enforcing', None)]
        assert records['onpc.kiosk.unloaded-configuration-generation-denied'] is True
        assert records['onpc.kiosk.unloaded-policy-generation-denied'] is True
        for name in ('configuration', 'policy'):
            assert records['onpc.kiosk.' + name + '-drift-loader-refused'] is True
            assert records['onpc.kiosk.' + name + '-attestation-recovered'] is True
    for path, identity in identities.items():
        actual = path.stat()
        assert (actual.st_dev, actual.st_ino, actual.st_mtime_ns) == identity
        assert path.read_bytes() == originals[path]


@pytest.mark.parametrize('fault', [None, 'accepted-load', 'wrong-refusal', 'holder-changed',
                                   'record-changed', 'pam-changed', 'policy-unenforced',
                                   'drained-load-failed'])
@pytest.mark.parametrize('defer_drain', [False, True])
def test_installed_loader_refusal_preserves_real_admission_and_policy(
        census_model, monkeypatch, fault, defer_drain):
    from contextlib import contextmanager
    helper = census_model
    events, records = [], {}
    native_identity = ('start', 1, ('0',) * 4)
    current = {'held': False, 'attempted': False, 'loads': 0}
    @contextmanager
    def held_account(record):
        events.append('hold')
        current['held'] = True
        try:
            yield 42
        finally:
            current['held'] = False
            events.append('pam-end')
    def owned_bytes(path, *, private):
        assert private and str(path) == '/var/lib/oh-no-parent-control/kiosk-confinement.json'
        return b'changed' if fault == 'record-changed' and current['attempted'] else b'original'
    monkeypatch.setitem(sys.modules, 'system_kiosk_admission', SimpleNamespace(held_account=held_account))
    monkeypatch.setitem(sys.modules, 'system_kiosk_accounts', SimpleNamespace(owned_bytes=owned_bytes))
    def enforcing(config):
        events.append('enforcing')
        if fault == 'policy-unenforced' and current['attempted']:
            raise ValueError('policy-unenforced')
    monkeypatch.setattr(helper.runpy, 'run_path', lambda path: {'enforcing': enforcing})
    def run(command, *, timeout):
        assert command[-1] == 'load' and not current['held'] and timeout == 90
        events.append('load')
        current['loads'] += 1
        if fault == 'drained-load-failed' and current['loads'] == (1 if defer_drain else 2):
            raise helper.guest.GuestError('drained-load-failed')
    monkeypatch.setattr(helper.guest, 'run', run)
    def refused(command, **options):
        assert current['held'] and command[-1] == 'load'
        assert options == {'timeout': 90, 'check': False, 'merge_stderr': True}
        events.append('refused-load')
        current['attempted'] = True
        helper.guest.commands.last_returncode = 0 if fault == 'accepted-load' else 1
        return b'other error' if fault == 'wrong-refusal' else b'kiosk-admissions-active'
    monkeypatch.setattr(helper.guest, 'commands', SimpleNamespace(run=refused, last_returncode=None))
    monkeypatch.setattr(helper.guest, 'pam_service_state', lambda:
        'changed' if fault == 'pam-changed' and current['attempted'] else 'original')
    monkeypatch.setattr(helper, 'process_identity', lambda process:
        ('replacement', *native_identity[1:]) if fault == 'holder-changed' and current['attempted']
        else native_identity)
    def verify():
        digest = helper.verify_loader_admission_refusal(
            {'backend': 'apparmor'}, records.__setitem__, defer_drain=defer_drain)
        assert digest == hashlib.sha256(b'original').hexdigest()
        if defer_drain:
            assert records['onpc.kiosk.loader.drain-deferred-to-retirement'] is True
            assert 'onpc.kiosk.loader.allowed-after-admission' not in records
            assert current['loads'] == 0
            helper.verify_loader_admission_drained(
                {'backend': 'apparmor'}, records.__setitem__, digest, 'original')
    if fault:
        category = ('policy-unenforced' if fault == 'policy-unenforced' else
                    'drained-load-failed' if fault == 'drained-load-failed' else
                    'held-admission-not-refused' if fault in ('accepted-load', 'wrong-refusal') else
                    'refusal-changed-admission-state')
        with pytest.raises((helper.guest.GuestError, ValueError), match=category):
            verify()
        assert 'onpc.kiosk.loader.allowed-after-admission' not in records
    else:
        verify()
        assert events == ([] if defer_drain else ['load']) + ['enforcing', 'hold', 'refused-load', 'enforcing',
                          'pam-end', 'load', 'enforcing']
        assert records.get('onpc.kiosk.loader.allowed-before-admission') is (None if defer_drain else True)
        assert records['onpc.kiosk.loader.allowed-after-admission'] is True
    assert not current['held']


@pytest.mark.parametrize('fault', [None, 'body-error', 'chown-error', 'inode', 'target',
                                   'mode', 'gid', 'mtime', 'foreign-owner'])
def test_native_alias_fault_restores_only_its_unchanged_owned_symlink(
        census_model, monkeypatch, fault):
    helper = census_model
    monkeypatch.setattr(helper, 'os', SimpleNamespace(**vars(os)))
    alias = Path('/usr/bin/python3')
    current = dict(st_dev=7, st_ino=42, st_mode=stat.S_IFLNK | 0o777,
                   st_uid=0, st_gid=0, st_nlink=1, st_atime_ns=90, st_mtime_ns=100)
    link = {'target': 'python3.14'}
    closed, owners, times = [], [], []
    monkeypatch.setattr(helper.guest, 'guard', lambda: None)
    monkeypatch.setattr(helper.os, 'open', lambda path, flags: 900)
    monkeypatch.setattr(helper.os, 'fstat', lambda fd:
                        SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o755))
    def metadata(name, *, dir_fd, follow_symlinks):
        assert (name, dir_fd, follow_symlinks) == ('python3', 900, False)
        return SimpleNamespace(**current)
    monkeypatch.setattr(helper.os, 'stat', metadata)
    def readlink(name, *, dir_fd):
        assert (name, dir_fd) == ('python3', 900)
        current['st_atime_ns'] = 999
        return link['target']
    monkeypatch.setattr(helper.os, 'readlink', readlink)
    def chown(name, uid, gid, *, dir_fd, follow_symlinks):
        assert (name, gid, dir_fd, follow_symlinks) == ('python3', 0, 900, False)
        owners.append(uid)
        if fault == 'chown-error' and uid == 1002:
            raise OSError('chown-error')
        current['st_uid'], current['st_gid'] = uid, gid
    monkeypatch.setattr(helper.os, 'chown', chown)
    def utime(name, *, ns, dir_fd, follow_symlinks):
        assert (name, dir_fd, follow_symlinks) == ('python3', 900, False)
        times.append(ns)
        current['st_atime_ns'], current['st_mtime_ns'] = ns
    monkeypatch.setattr(helper.os, 'utime', utime)
    monkeypatch.setattr(helper.os, 'close', closed.append)
    def exercise():
        with helper.untrusted_alias_owner(alias, 1002):
            assert current['st_uid'] == 1002
            if fault == 'body-error':
                raise RuntimeError('body-error')
            if fault == 'inode':
                current['st_ino'] += 1
            elif fault == 'target':
                link['target'] = 'foreign'
            elif fault == 'mode':
                current['st_mode'] = stat.S_IFREG | 0o755
            elif fault == 'gid':
                current['st_gid'] = 1003
            elif fault == 'mtime':
                current['st_mtime_ns'] += 1
            elif fault == 'foreign-owner':
                current['st_uid'] = 1003
    if fault in ('body-error', 'chown-error'):
        with pytest.raises((OSError, RuntimeError), match=fault):
            exercise()
    elif fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-alias:fixture-replaced'):
            exercise()
    else:
        exercise()
    if fault in (None, 'body-error', 'chown-error'):
        assert owners == [1002, 0] and current['st_uid'] == current['st_gid'] == 0
        assert times == [(90, 100)]
        assert current['st_atime_ns'] == 90 and current['st_mtime_ns'] == 100
    else:
        assert owners == [1002] and times == []
    assert closed == [900]
