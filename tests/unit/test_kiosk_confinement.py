"""Private confinement lifecycle machines; no host PAM or kernel policy changes."""
import importlib.util
import json
import fcntl
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT


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


def test_removal_preflight_restores_recreated_lock_label_without_manufacturing_legacy_inodes(integration):
    helper, commands = integration
    helper.install()
    helper.ADMISSION_LOCK.unlink()
    commands.clear()
    helper.remove(check=True)
    assert commands == [['/usr/sbin/restorecon', str(helper.ADMISSION_LOCK)]]
    assert not helper.LEGACY_LOGIN_LOCK.exists()
    assert not helper.PREPARATION_LOCK.exists()


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


@pytest.fixture
def admission_model(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tests/integration'))
    return module(ROOT / 'tests/integration/system_kiosk_admission.py')


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
def test_installed_admission_uses_real_service_name_and_ends_denied_transactions(
        admission_model, monkeypatch, status):
    from unittest.mock import MagicMock
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    service = Mock()
    service.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
    directory = MagicMock()
    directory.__truediv__.return_value = service
    monkeypatch.setattr(helper, 'Path', Mock(return_value=directory))
    monkeypatch.setattr(helper.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(
        pw_uid=41001, pw_name='oh-no-parent-control')))
    pam = Mock()
    pam.pam_start.return_value = 0
    pam.pam_acct_mgmt.return_value = status
    pam.pam_end.return_value = 0
    monkeypatch.setattr(helper.ctypes, 'CDLL', Mock(return_value=pam))
    assert helper.pam_account('sshd', 'kiosk') == {'account': status, 'end': 0}
    assert pam.pam_start.call_args.args[:2] == (b'sshd', b'oh-no-parent-control')
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


@pytest.mark.parametrize('fault', [None, 'waiting-label', 'finished', 'credential-status', 'establish-status'])
def test_pam_lifecycle_observer_pins_and_reaps_owned_executor_and_orphan(
        census_model, tmp_path, monkeypatch, fault):
    helper = census_model
    observer = os.getpid()
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: observer)
    original_read = Path.read_text
    expected = 'onpc-kiosk-manager (enforce)'
    def read(path, *args, **kwargs):
        if path.name == 'current' and 'attr' in path.parts:
            return 'unconfined' if fault == 'waiting-label' else expected
        if path.name == 'generation':
            return 'private generation'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(helper.shutil, 'copyfile', lambda source, target: target.write_bytes(b'private executor'))
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
        with pytest.raises(helper.guest.GuestError, match='kiosk-lifecycle:'):
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
@pytest.mark.parametrize('fault', [None, 'label', 'namespace', 'generation', 'parent-role',
                                  'pinned-inode', 'credentials', 'lifecycle', 'exited',
                                  'exited-readable', 'exec-change', 'label-change'])
def test_real_scanner_snapshot_checks_live_parent_every_thread_and_pinned_inode(
        census_model, tmp_path, monkeypatch, backend, fault):
    helper = census_model
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    roles = ['manager', 'app', 'webkit', 'scanner', 'manager-pam']
    config = {'backend': backend, 'domains': roles,
              'apparmor_profiles': ['onpc-kiosk-' + role for role in roles],
              'executables': [{'role': 'scanner', 'paths': ['/usr/libexec/gst-plugin-scanner']}]}
    marker = 'usr/share/oh-no-parent-control/confinement/generation'
    for pid, role, ppid in ((42, 'manager', 1), (43, 'webkit', 42), (44, 'scanner', 43)):
        process = tmp_path / str(pid)
        for tid in (pid, pid + 1000):
            thread = process / 'task' / str(tid)
            thread.mkdir(parents=True)
            fields = ['S', str(ppid)] + ['0'] * 17 + [str(tid * 100)]
            (thread / 'stat').write_text(f'{tid} (native fixture) ' + ' '.join(fields))
            uid = '0' if fault == 'credentials' and pid == 44 and tid != pid else '1002'
            (thread / 'status').write_text('PPid:\t' + str(ppid) + '\nUid:\t' + '\t'.join([uid] * 4) + '\n')
            (thread / 'ns').mkdir()
            (thread / 'ns/mnt').symlink_to('mnt:[host]' if fault == 'namespace' and pid == 44 else 'mnt:[private]')
            generation = thread / 'root' / marker
            generation.parent.mkdir(parents=True)
            generation.write_text('changed' if fault == 'generation' and pid == 44 else 'private generation')
            label_role = 'manager-pam' if fault == 'parent-role' and pid == 43 else role
            name = ('onpc-kiosk-' + label_role if backend == 'apparmor'
                    else 'onpc_kiosk_' + label_role.replace('-', '_') + '_t')
            label = name + ' (enforce)' if backend == 'apparmor' else 'system_u:system_r:' + name + ':s0'
            if fault == 'label' and pid == 44 and tid != pid:
                label = 'unconfined'
            attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
            (thread / attribute).parent.mkdir(parents=True)
            (thread / attribute).write_text(label)
        for name in ('stat', 'status', 'root', 'ns', 'attr'):
            (process / name).symlink_to(process / 'task' / str(pid) / name)
    pinned = tmp_path / '42/root/usr/libexec/gst-plugin-scanner'
    pinned.parent.mkdir(parents=True)
    pinned.write_bytes(b'private native scanner')
    other = tmp_path / 'other-scanner'
    other.write_bytes(b'private native scanner')
    scanner = tmp_path / '44'
    (scanner / 'exe').symlink_to(other if fault == 'pinned-inode' else pinned)
    (tmp_path / '43/exe').symlink_to(other)
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda pid: pid)
    monkeypatch.setattr(helper.os, 'close', lambda fd: None)
    monkeypatch.setattr(helper, 'exited', lambda fd: fault in ('exited', 'exited-readable') and fd == 44)
    if fault == 'exited':
        (scanner / 'task/1044/stat').unlink()
    real_identity = helper.process_identity
    reads = {}
    def identity(path):
        result = real_identity(path)
        reads[path] = reads.get(path, 0) + 1
        if fault == 'lifecycle' and path == scanner and reads[path] > 1:
            return ('replaced', *result[1:])
        if path == scanner and reads[path] > 1:
            if fault == 'exec-change':
                (scanner / 'exe').unlink()
                (scanner / 'exe').symlink_to(other)
            if fault == 'label-change':
                attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
                (scanner / attribute).write_text('unconfined')
        return result
    monkeypatch.setattr(helper, 'process_identity', identity)
    def observe():
        return helper.scanner_process(scanner, SimpleNamespace(pw_uid=1002), config,
                                      tmp_path / '42', 'private generation', 'mnt:[host]')
    if fault in ('exited', 'exited-readable'):
        assert observe() is None
    elif fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-(scanner|census):'):
            observe()
    else:
        result = observe()
        assert result['scanner_observed'] and result['pinned_executable']
        assert result['private_namespace_and_generation']
        assert sum(result['scanner_thread_roles'].values()) == 2
        assert sum(result['parent_thread_roles'].values()) == 2


@pytest.mark.parametrize('stop', [b'', b'stop\n', b'foreign'])
def test_scanner_observer_missing_transient_is_explicit_and_unknown_stop_refuses(
        census_model, tmp_path, monkeypatch, stop):
    helper = census_model
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    manager = tmp_path / '42'
    generation = manager / 'root/usr/share/oh-no-parent-control/confinement/generation'
    generation.parent.mkdir(parents=True)
    generation.write_text('private generation')
    host_namespace = tmp_path / '1/ns/mnt'
    host_namespace.parent.mkdir(parents=True)
    host_namespace.symlink_to('mnt:[host]')
    config = {'backend': 'apparmor'}
    original_read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *args, **kw:
        json.dumps(config) if str(path) == '/usr/share/oh-no-parent-control/confinement/config.json'
        else original_read(path, *args, **kw))
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1002))
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: 42)
    monkeypatch.setattr(helper, 'scanner_manager_pid', lambda unit: 42)
    monkeypatch.setattr(helper, 'process_identity', lambda process: ('private', 1, ('1002',) * 4))
    monkeypatch.setattr(helper, 'confined_thread_roles', lambda *args: ['onpc-kiosk-manager'])
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda pid: 42)
    monkeypatch.setattr(helper.os, 'close', lambda fd: None)
    monkeypatch.setattr(helper, 'exited', lambda fd: False)
    ready = []
    with (tmp_path / 'stop').open('w+b') as stream:
        stream.write(stop)
        stream.flush()
        if stop == b'foreign':
            with pytest.raises(helper.guest.GuestError, match='stop-content'):
                helper.observe_scanner(stream.fileno(), lambda: ready.append(True), timeout=1)
        else:
            value = helper.observe_scanner(stream.fileno(), lambda: ready.append(True),
                                           timeout=0 if not stop else 1)
            assert value == {'scanner_observed': False, 'observation': 'not-observed', 'backend': 'apparmor'}
    assert ready == [True]


def test_scanner_observer_is_ready_before_login_and_never_opens_pid_zero(
        census_model, tmp_path, monkeypatch):
    helper = census_model
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    host = tmp_path / '1/ns/mnt'
    host.parent.mkdir(parents=True)
    host.symlink_to('mnt:[host]')
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1002))
    monkeypatch.setattr(Path, 'read_text', lambda path: json.dumps({'backend': 'apparmor'}))
    ready = []
    def manager(unit):
        assert ready == [True]  # Login may proceed before the manager exists.
        return 0
    monkeypatch.setattr(helper, 'scanner_manager_pid', manager)
    opened = Mock(side_effect=AssertionError('no live manager'))
    monkeypatch.setattr(helper.os, 'pidfd_open', opened)
    with (tmp_path / 'stop').open('w+b') as stream:
        monkeypatch.setattr(helper.time, 'sleep', lambda seconds:
                            os.pwrite(stream.fileno(), b'stop\n', 0))
        assert helper.observe_scanner(stream.fileno(), lambda: ready.append(True)) == {
            'scanner_observed': False, 'observation': 'not-observed', 'backend': 'apparmor'}
    opened.assert_not_called()


@pytest.mark.parametrize('state,pid', [('activating', 0), ('inactive', 0), ('active', 42)])
def test_scanner_binds_only_the_started_manager(census_model, monkeypatch, state, pid):
    helper = census_model
    monkeypatch.setattr(helper.guest, 'run', lambda argv:
                        'ActiveState=' + state + '\nMainPID=42\n')
    assert helper.scanner_manager_pid('user@1002.service') == pid


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'label', 'credentials', 'namespace', 'generation',
                                  'profile-entry', 'proof-write'])
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
    def write(fd, data):
        assert fd == 53
        proofs.append(json.loads(data))
        return len(data) - int(fault == 'proof-write')
    monkeypatch.setattr(helper.os, 'write', write)
    executed = []
    def execute(path, arguments, environment):
        executed.append((path, arguments, environment))
        raise RuntimeError('exec captured')
    monkeypatch.setattr(helper.os, 'execve', execute)
    failed = fault is not None and not (fault == 'profile-entry' and backend == 'selinux')
    if failed:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            helper.bwrap_probe_child(request)
        assert not executed
    else:
        with pytest.raises(RuntimeError, match='exec captured'):
            helper.bwrap_probe_child(request)
        assert credentials == [('groups', []), ('gid', 1002), ('uid', 1002)]
        assert proofs == [dict(uid=1002, namespace=42, generation=generation, role=expected)]
        assert inherited == [(53, False)]
        assert executed == [('/usr/bin/bwrap', request['arguments'], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})]
    assert change.call_count == int(backend == 'apparmor')


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
    payload, runtime = tmp_path / 'payload', tmp_path / 'runtime'
    payload.mkdir()
    runtime.mkdir(mode=0o700)
    marker = tmp_path / 'kiosk-uid'
    marker.write_text('1002\n')
    marker.chmod(0o600)
    vendor = tmp_path / 'vendor-helper'
    vendor.write_bytes(b'\x7fELFprivate vendor password helper')
    vendor.chmod(0o755)
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
              {'path': path, 'kind': 'file'}]
    manager_checks, reclaims = [], []
    monkeypatch.setattr(helper, 'PAYLOAD', payload)
    monkeypatch.setattr(helper, 'RUNTIME', runtime)
    monkeypatch.setattr(helper.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(helper.os, 'umask', lambda mode: 0o022)
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1002))
    # These unit cases inject a post-measurement layout, keeping actual private
    # generation/tree/bindings writes. Inventory trust has independent coverage.
    monkeypatch.setattr(helper, 'trusted', lambda source, **kwargs:
                        marker if str(source) == '/var/lib/oh-no-parent-control/package-created-kiosk-uid'
                        else Path(source))
    def verify(arguments, **kwargs):
        assert arguments == ['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'verify']
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(helper.subprocess, 'run', verify)
    monkeypatch.setattr(helper, 'enforcing', lambda value: None)
    monkeypatch.setattr(helper, 'inventory', lambda value: [])
    monkeypatch.setattr(helper, 'preserved_inventory', lambda value: ([record], identities))
    def collect(value, records):
        assert records == [record]
        return layout
    monkeypatch.setattr(helper, 'directory_layout', collect)
    monkeypatch.setattr(helper, 'manager_generation', lambda *args: manager_checks.append(args))
    monkeypatch.setattr(helper, 'reclaim_interrupted', lambda: reclaims.append(True))
    return SimpleNamespace(helper=helper, runtime=runtime, layout=layout, path=path, record=record,
        identities=identities, manager_checks=manager_checks, reclaims=reclaims)


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
    generation = next(path for path in model.runtime.iterdir() if path.is_dir())
    bindings = (model.runtime / 'bindings').read_text()
    for index, record in enumerate(records):
        copy = generation / str(index)
        assert copy.read_bytes() == originals[record['source']]
        assert copy.stat().st_ino != Path(record['source']).stat().st_ino
        target = generation / 'tree' / record['path'].removeprefix('/usr/')
        assert f'{copy}\t{target}\n' in bindings
    assert json.loads((generation / 'records.json').read_text())['records'] == records
    helper.prepare('gate')
    assert (model.runtime / 'bindings').read_text() == bindings
    assert {path: Path(path).read_bytes() for path in originals} == originals


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('fault', ['missing', 'link', 'directory', 'duplicate-file', 'duplicate-link'])
def test_preserved_password_helper_preparation_refuses_missing_or_ambiguous_signed_binding(
        preserved_password_preparation, role, fault):
    model = preserved_password_preparation
    if fault == 'missing':
        model.layout.pop()
    elif fault in ('link', 'directory'):
        model.layout[-1]['kind'] = fault
        if fault == 'link':
            model.layout[-1]['link'] = 'replacement-helper'
    else:
        model.layout.append(dict(path=model.path, kind='file' if fault == 'duplicate-file' else 'link',
                                 **({'link': 'replacement-helper'} if fault == 'duplicate-link' else {})))
    with pytest.raises(ValueError, match='preserved-executable-layout'):
        model.helper.prepare(role)
    assert (model.runtime / 'bindings').read_text() == 'previous bindings\n'
    assert {item.name for item in model.runtime.iterdir()} == {'bindings'}
    assert model.manager_checks == model.reclaims == []


@pytest.mark.parametrize('role', ['manager', 'gate'])
def test_preserved_password_helper_preparation_publishes_exactly_one_inode_signed_binding(
        preserved_password_preparation, role):
    model = preserved_password_preparation
    model.helper.prepare(role)
    lines = (model.runtime / 'bindings').read_text().splitlines()
    assert lines[0] == 'apparmor'
    source, destination, assertion = lines[1].split('\t')
    assert source == model.path
    assert assertion == ' '.join(map(str, model.identities[model.path]))
    generation = Path(destination).parents[3]
    assert Path(destination) == generation / 'tree/lib/polkit-1/polkit-agent-helper-1'
    assert lines[2:] == [str(generation / 'tree') + '\t/usr']
    assert json.loads((generation / 'records.json').read_text())['preserved'] == [model.record]
    assert len(model.manager_checks) == (1 if role == 'gate' else 0)
    assert model.reclaims == [True]
    # Reusing a stable generation must retain the same single signed binding.
    model.helper.prepare(role)
    assert (model.runtime / 'bindings').read_text().splitlines() == lines
    assert {item.name for item in model.runtime.iterdir()} == {'bindings', generation.name}


def test_preserved_password_helper_parent_contributes_real_private_directory_layout(tmp_path, monkeypatch):
    helper = module(ROOT / 'tools/kiosk_confinement.py')
    private_root = tmp_path / 'private-root'
    source = private_root / 'usr/lib/polkit-1/polkit-agent-helper-1'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'\x7fELFprivate preserved helper')
    (source.parent / 'vendor-data').mkdir()
    (source.parent / 'vendor-data/uncovered').write_text('private sibling')
    payload = private_root / 'usr/share/oh-no-parent-control/confinement'
    payload.mkdir(parents=True)
    (payload / 'generation').touch()
    original_iterdir, original_lstat = Path.iterdir, Path.lstat
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
        values[4] = 0
        return os.stat_result(values)

    def trusted(path, *, directory=False, **kwargs):
        info = original_lstat(physical(path))
        assert stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        return path

    monkeypatch.setattr(helper.Path, 'iterdir', entries)
    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    monkeypatch.setattr(helper, 'trusted', trusted)
    layout = helper.directory_layout({'reserved_directories': []},
        [{'path': '/usr/lib/polkit-1/polkit-agent-helper-1'}])
    kinds = {entry['path']: entry['kind'] for entry in layout}
    assert kinds['/usr/lib'] == kinds['/usr/lib/polkit-1'] == 'tree'
    assert kinds['/usr/lib/polkit-1/polkit-agent-helper-1'] == 'file'
    assert kinds['/usr/lib/polkit-1/vendor-data'] == 'directory'
    assert '/usr/lib/polkit-1/vendor-data/uncovered' not in kinds
    assert source.parent in visited
    assert source.parent / 'vendor-data' not in visited


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
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-o',
                    str(executable), str(source)], check=True, capture_output=True, text=True, timeout=30)
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


@pytest.mark.parametrize('fault', ['missing-field', 'extra-field', 'trailing-space', 'nonnumeric', 'plus-sign', 'negative-zero', 'tab'])
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
    assertion = ' '.join(values) + (' ' if fault == 'trailing-space' else '')
    if fault == 'tab':
        assertion = assertion.replace(' ', '\t', 1)
    result = subprocess.run([str(native_preserved_identity), str(source), assertion],
                            capture_output=True, timeout=5)
    assert result.returncode == 1


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
            assert 'deny /{,tmp/}newroot/{usr,lib,lib64,bin,sbin}/**[^/] wkl,' in profile
            assert 'deny /{usr,lib,lib64,bin,sbin}/**[^/] wkl,' in profile
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
