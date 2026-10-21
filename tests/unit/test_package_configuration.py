"""Run postinst with fake commands and all system paths in a temporary tree.

No host service, account, process, or policy is changed.
"""

import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


from tests.support.paths import ROOT
BROKER = "oh-no-parent-control-broker.service"
REBOOT_NOTICE = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"


from tests.support.package_scripts import (
    mapped_pam_worker, package_machine, prepared_lifecycle_machine, rpm_script_source,
    use_real_kiosk_confinement, use_real_state_migration,
)
from tests.support.shell import relocate_system_paths


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('installed', [False, True])
def test_prepared_lifecycle_composes_fresh_and_owned_upgrade(tmp_path, monkeypatch, backend, installed):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend, installed=installed)
    migration = machine.migration
    saved = migration.state()
    preferences = migration.STATE_DIRECTORY / 'preferences'
    preferences.mkdir()
    retained = preferences / '1001.json'
    retained.write_text('{"language":"fr","daily_time_limit_minutes":75}\n')
    unrelated = tmp_path / 'ordinary-user-metadata'
    unrelated.write_text('retain ordinary policy\n')
    runtime = tmp_path / 'run/oh-no-parent-control-confinement/generation-foreign'
    runtime.mkdir(parents=True)
    inode = runtime.stat().st_ino
    migration.prepare()
    assert machine.expires == 1
    if saved:
        assert not machine.loaded
        assert all((migration.PAM / name).read_text() == migration.DENIAL + migration.original(record)
                   for name, record in saved['pam'].items())
    migration.restore_original_pam()

    def replacement_ready():
        assert machine.expires == 1
        # A concrete side-effect-free fixture readiness readback; C02 must
        # supply the actual native/distro verifier before selecting this source.
        assert (migration.PAM / 'gdm-password').read_text() == 'session required pam_unix.so\n'
        assert not (migration.PAM / 'systemd-user').exists()

    migration.commit_migration(replacement_ready)
    migration.release_account()
    migration.release_account()
    assert machine.expires is None
    assert not any(path.exists() for path in (migration.STATE, migration.DISABLED, migration.EXPIRY))
    assert migration.OWNERSHIP.read_text() == '1006\n'
    assert retained.read_text() == '{"language":"fr","daily_time_limit_minutes":75}\n'
    assert unrelated.read_text() == 'retain ordinary policy\n'
    assert runtime.stat().st_ino == inode


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('boundary', ['denial', 'unload', 'restore', 'commit', 'expiry'])
def test_prepared_lifecycle_interrupted_steps_retry_without_losing_originals(
        tmp_path, monkeypatch, backend, boundary):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    saved = migration.state()
    machine.expires = 19000
    function = {'denial': 'write', 'unload': 'policy', 'restore': 'erase',
                'commit': 'erase', 'expiry': 'erase'}[boundary]
    original = getattr(migration, function)
    failed = False

    def interrupt(*args, **kwargs):
        nonlocal failed
        selected = ((boundary == 'denial' and args[0] == migration.PAM / 'systemd-user') or
                    (boundary == 'unload' and kwargs.get('load') is False) or
                    (boundary == 'restore' and args[0] == migration.PAM / 'systemd-user') or
                    (boundary == 'commit' and args[0] == migration.STATE) or
                    (boundary == 'expiry' and args[0] == migration.EXPIRY))
        if selected and not failed:
            failed = True
            raise OSError('owned interruption')
        return original(*args, **kwargs)

    def verify():
        assert machine.expires == 1
        migration.verify_pam(saved, originals=True)

    monkeypatch.setattr(migration, function, interrupt)
    with pytest.raises(OSError, match='owned interruption'):
        migration.prepare()
        migration.restore_original_pam()
        migration.commit_migration(verify)
        migration.release_account()
    assert failed
    # The release interruption has already restored the original native policy;
    # its releasing record permits a retry without another quarantine cycle.
    if boundary == 'expiry':
        assert machine.expires == 19000
        assert migration.expiry_record(1006)['phase'] == 'releasing'
        migration.release_account()
    else:
        assert machine.expires == 1
        migration.prepare()
        migration.restore_original_pam()
        migration.commit_migration(verify)
        migration.release_account()
    assert machine.expires == 19000
    assert not migration.STATE.exists() and not migration.EXPIRY.exists()
    migration.verify_pam(saved, originals=True)


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('partial', [False, True])
def test_prepared_lifecycle_abort_restores_policy_before_account_release(tmp_path, monkeypatch, backend, partial):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    saved = migration.state()
    migration.prepare()
    if partial:
        migration.restore_original_pam()
    machine.commands.clear()
    migration.rollback()
    assert machine.loaded and machine.expires is None
    assert not migration.DISABLED.exists() and not migration.EXPIRY.exists()
    assert not migration.state().get('removing')
    for name, record in saved['pam'].items():
        assert (migration.PAM / name).read_text() == record['after']
    load_index = next(i for i, command in enumerate(machine.commands) if command[0].endswith(('semodule', 'apparmor_parser')))
    release_index = next(i for i, command in enumerate(machine.commands) if command[:2] == ['usermod', '--expiredate'])
    assert load_index < release_index


@pytest.mark.parametrize('failure', [None, 'admission-label', 'pam-labels'])
def test_prepared_lifecycle_selinux_rollback_restores_labels_under_quarantine(
        tmp_path, monkeypatch, failure):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, 'selinux')
    migration = machine.migration
    saved = migration.state()
    machine.expires = 19000
    migration.prepare()
    migration.restore_original_pam()
    run = migration.run
    write = migration.write
    erase = migration.erase
    events = []
    failed = False
    lock_command = ['/usr/sbin/restorecon', str(migration.LOCKS[0])]
    pam_command = ['/usr/sbin/restorecon', str(migration.PAM / 'gdm-password'),
                   str(migration.PAM / 'systemd-user')]

    def observed_run(arguments):
        nonlocal failed
        events.append(('run', arguments))
        if arguments[0] == '/usr/sbin/restorecon':
            if arguments == lock_command and not machine.loaded:
                # The common barrier reasserts the current (now stock) label
                # before rollback loads the old policy and restores its type.
                assert machine.expires == 1
                return run(arguments)
            assert machine.loaded and machine.expires == 1
            assert migration.state()['removing'] and migration.DISABLED.exists()
            if arguments == lock_command:
                migration.verify_pam(saved)
                point = 'admission-label'
            else:
                assert arguments == pam_command
                assert all((migration.PAM / name).read_text() == record['after']
                           for name, record in saved['pam'].items())
                point = 'pam-labels'
            if point == failure and not failed:
                failed = True
                raise OSError('owned SELinux label interruption')
        return run(arguments)

    def observed_write(path, contents, mode=0o600):
        if path.parent == migration.PAM:
            events.append(('pam', path))
        return write(path, contents, mode)

    def observed_erase(path):
        if path == migration.DISABLED:
            events.append(('release-marker', path))
        return erase(path)

    monkeypatch.setattr(migration, 'run', observed_run)
    monkeypatch.setattr(migration, 'write', observed_write)
    monkeypatch.setattr(migration, 'erase', observed_erase)
    if failure:
        with pytest.raises(OSError, match='SELinux label interruption'):
            migration.rollback()
        assert machine.expires == 1 and migration.expiry_record(1006)['phase'] == 'quarantined'
        assert migration.state()['removing'] and migration.DISABLED.exists()
        # At the PAM-label failure the gates have already been republished;
        # the retry must accept that exact owned generation and relabel again.
        events.clear()
    migration.rollback()
    load = next(i for i, event in enumerate(events) if event[0] == 'run' and event[1][:2] == ['/usr/sbin/semodule', '-i'])
    lock_label = next(i for i, event in enumerate(events) if i > load and event == ('run', lock_command))
    pam_writes = [i for i, event in enumerate(events) if event[0] == 'pam']
    pam_labels = events.index(('run', pam_command))
    marker_release = next(i for i, event in enumerate(events) if event[0] == 'release-marker')
    expiry_release = next(i for i, event in enumerate(events) if event[0] == 'run' and event[1][:2] == ['usermod', '--expiredate'])
    assert load < lock_label < min(pam_writes) <= max(pam_writes) < pam_labels < marker_release < expiry_release
    assert machine.expires == 19000 and not migration.EXPIRY.exists()
    assert not migration.DISABLED.exists() and not migration.state().get('removing')


@pytest.mark.parametrize('entrypoint,refusal', [
    ('prepare', 'pam'), ('prepare', 'policy'), ('prepare', 'idle'),
    ('rollback', 'pam'), ('rollback', 'idle'),
])
def test_prepared_lifecycle_selinux_absent_lease_label_survives_preflight_refusal(
        tmp_path, monkeypatch, entrypoint, refusal):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, 'selinux')
    migration = machine.migration
    migration.LOCKS[0].unlink()
    original_pam = {name: (migration.PAM / name).read_bytes() for name in migration.SERVICES}
    config = migration.PAYLOAD / 'config.json'
    original_config = config.read_bytes()
    if refusal == 'pam':
        (migration.PAM / 'gdm-password').write_text('administrator policy\n')
    elif refusal == 'policy':
        config.write_text('{"backend":"selinux","changed":true}\n')
    else:
        thread = migration.PROCESSES / '42/task/42'
        (thread / 'attr').mkdir(parents=True)
        (thread / 'status').write_text('Uid:\t1006\t1006\t1006\t1006\n')
        (thread / 'loginuid').write_text('1001\n')
        (thread / 'maps').write_text('')
        for attribute in ('current', 'exec'):
            (thread / 'attr' / attribute).write_text('unconfined\n')
    before_state = migration.STATE.read_bytes()
    before_pam = {name: (migration.PAM / name).read_bytes() for name in migration.SERVICES}
    before_config = config.read_bytes()
    events = []
    identities = []
    native_run = migration.run
    label_command = ['/usr/sbin/restorecon', str(migration.LOCKS[0])]

    def observed_run(arguments):
        if arguments == label_command:
            assert machine.loaded and machine.expires is None
            info = migration.LOCKS[0].stat()
            identities.append((info.st_dev, info.st_ino))
            events.append('label')
        return native_run(arguments)

    def observe(name):
        function = getattr(migration, name)
        def checked(*args, **kwargs):
            events.append(name)
            return function(*args, **kwargs)
        monkeypatch.setattr(migration, name, checked)

    monkeypatch.setattr(migration, 'run', observed_run)
    for function in ('verify_pam', 'policy_material', 'idle'):
        observe(function)
    with pytest.raises(ValueError, match={'pam': 'modified-legacy-pam',
                                         'policy': 'changed-legacy-policy-payload',
                                         'idle': 'kiosk-processes-active'}[refusal]):
        getattr(migration, entrypoint)()
    failed_at = {'pam': 'verify_pam', 'policy': 'policy_material', 'idle': 'idle'}[refusal]
    assert events.index('label') < events.index(failed_at)
    retained = migration.LOCKS[0].stat()
    assert identities == [(retained.st_dev, retained.st_ino)]
    assert machine.loaded and machine.expires is None
    assert migration.STATE.read_bytes() == before_state
    assert {name: (migration.PAM / name).read_bytes() for name in migration.SERVICES} == before_pam
    assert config.read_bytes() == before_config
    assert not migration.EXPIRY.exists() and not migration.DISABLED.exists()
    for name, contents in original_pam.items():
        (migration.PAM / name).write_bytes(contents)
    config.write_bytes(original_config)
    if refusal == 'idle':
        (thread / 'status').write_text('Uid:\t1001\t1001\t1001\t1001\n')
    migration.prepare()
    assert identities == [(retained.st_dev, retained.st_ino)] * 2
    assert not machine.loaded and machine.expires == 1
    assert ['/usr/sbin/restorecon', '-F', str(migration.LOCKS[0])] in machine.commands
    monkeypatch.setattr(migration, 'run', native_run)
    machine.user = None
    for path in migration.PAYLOAD.iterdir():
        path.unlink()
    migration.finish_remove()
    final = migration.LOCKS[0].stat()
    assert (final.st_dev, final.st_ino) == (retained.st_dev, retained.st_ino)
    assert not migration.STATE.exists() and not migration.EXPIRY.exists()


def test_prepared_lifecycle_selinux_failed_initial_lease_label_retries_same_inode(tmp_path, monkeypatch):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, 'selinux')
    migration = machine.migration
    migration.LOCKS[0].unlink()
    before_state = migration.STATE.read_bytes()
    before_pam = {name: (migration.PAM / name).read_bytes() for name in migration.SERVICES}
    identities = []
    native_run = migration.run
    label_command = ['/usr/sbin/restorecon', str(migration.LOCKS[0])]
    def interrupted_label(arguments):
        if arguments == label_command:
            info = migration.LOCKS[0].stat()
            identities.append((info.st_dev, info.st_ino))
            if len(identities) == 1:
                raise OSError('initial lease label unavailable')
        return native_run(arguments)
    monkeypatch.setattr(migration, 'run', interrupted_label)
    with pytest.raises(OSError, match='initial lease label unavailable'):
        migration.prepare()
    assert machine.loaded and machine.expires is None
    assert migration.STATE.read_bytes() == before_state
    assert {name: (migration.PAM / name).read_bytes() for name in migration.SERVICES} == before_pam
    assert not migration.EXPIRY.exists() and not migration.DISABLED.exists()
    migration.prepare()
    assert len(identities) == 2 and identities[0] == identities[1]
    assert not machine.loaded and machine.expires == 1
    machine.user = None
    for path in migration.PAYLOAD.iterdir():
        path.unlink()
    migration.finish_remove()
    assert identities[-1] == identities[0]
    assert not migration.STATE.exists() and not migration.DISABLED.exists()


def test_prepared_lifecycle_invalid_state_does_not_create_admission_inode(tmp_path, monkeypatch):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, 'selinux')
    migration = machine.migration
    migration.LOCKS[0].unlink()
    record = migration.state()
    record['schema'] = 2
    migration.save(migration.STATE, record)
    with pytest.raises(ValueError, match='invalid-legacy-confinement-record'):
        migration.prepare()
    assert not migration.LOCKS[0].exists()
    assert machine.loaded and machine.expires is None


def test_prepared_lifecycle_failed_readiness_and_misuse_retain_recovery(tmp_path, monkeypatch):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch)
    migration = machine.migration
    migration.prepare()
    migration.restore_original_pam()
    before = migration.STATE.read_bytes()
    with pytest.raises(TypeError, match='verifier-required'):
        migration.commit_migration(True)
    with pytest.raises(ValueError, match='return-none'):
        migration.commit_migration(lambda: True)
    def failed_verifier():
        raise OSError('native PAM readiness unavailable')
    with pytest.raises(OSError, match='readiness unavailable'):
        migration.commit_migration(failed_verifier)
    assert machine.expires == 1 and migration.STATE.read_bytes() == before
    migration.rollback()
    assert machine.loaded and machine.expires is None


@pytest.mark.parametrize('change', ['pam', 'expiry', 'state'])
def test_prepared_lifecycle_readiness_cannot_retire_changed_inputs(tmp_path, monkeypatch, change):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch)
    migration = machine.migration
    migration.prepare()
    migration.restore_original_pam()
    def changed_verifier():
        if change == 'pam':
            (migration.PAM / 'gdm-password').write_text('administrator edit\n')
        elif change == 'expiry':
            machine.expires = 20000
        else:
            record = migration.state()
            record['kiosk_uid'] = 1007
            migration.save(migration.STATE, record)
    with pytest.raises(ValueError):
        migration.commit_migration(changed_verifier)
    assert migration.STATE.exists() and migration.DISABLED.exists()


@pytest.mark.parametrize('condition', ['lease', 'kiosk-process', 'foreign-state', 'prelease'])
def test_prepared_lifecycle_preserves_live_and_foreign_state(tmp_path, monkeypatch, condition):
    import fcntl
    import os
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch)
    migration = machine.migration
    original = {name: (migration.PAM / name).read_bytes() for name in migration.SERVICES}
    held = None
    if condition == 'lease':
        held = os.open(migration.LOCKS[0], os.O_RDWR)
        fcntl.flock(held, fcntl.LOCK_SH)
    elif condition == 'kiosk-process':
        thread = migration.PROCESSES / '123/task/123'
        thread.mkdir(parents=True)
        (thread / 'status').write_text('Uid:\t1006\t1006\t1006\t1006\n')
    elif condition == 'foreign-state':
        (migration.PAM / 'gdm-password').write_text('administrator policy\n')
        original['gdm-password'] = b'administrator policy\n'
    else:
        saved = migration.state()
        saved.pop('admission_protocol')
        migration.save(migration.STATE, saved)
    try:
        with pytest.raises((ValueError, BlockingIOError)):
            migration.prepare()
        assert machine.expires is None and machine.loaded
        assert {name: (migration.PAM / name).read_bytes() for name in migration.SERVICES} == original
    finally:
        if held is not None:
            os.close(held)
    if condition == 'prelease':
        migration.BOOT.write_text('22222222-2222-2222-2222-222222222222\n')
        migration.prepare()
        assert machine.expires == 1


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
def test_prepared_lifecycle_partial_pam_publication_and_removing_retry(tmp_path, monkeypatch, backend):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    saved = migration.state()
    previous = dict(saved['pam']['gdm-password'])
    previous['after'] = '# older owned generation\n' + previous['after']
    saved['previous_pam'] = {'gdm-password': previous}
    (migration.PAM / 'gdm-password').write_text(previous['after'])
    (migration.PAM / 'systemd-user').unlink()
    migration.save(migration.STATE, saved)
    migration.prepare()
    migration.prepare()
    migration.restore_original_pam()
    migration.rollback()
    assert machine.loaded and machine.expires is None
    assert migration.state().get('previous_pam') is None


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
def test_prepared_lifecycle_post_erase_retries_without_any_payload(tmp_path, monkeypatch, backend):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    saved = migration.state()
    migration.prepare()
    for path in migration.PAYLOAD.iterdir():
        path.unlink()
    machine.user = None
    original_erase = migration.erase
    failed = False
    def interrupt(path):
        nonlocal failed
        if path == migration.PAM / 'systemd-user' and not failed:
            failed = True
            raise OSError('post-erase interruption')
        original_erase(path)
    monkeypatch.setattr(migration, 'erase', interrupt)
    with pytest.raises(OSError, match='post-erase interruption'):
        migration.finish_remove()
    assert migration.STATE.exists() and migration.DISABLED.exists()
    migration.finish_remove()
    migration.finish_remove()
    migration.verify_pam(saved, originals=True)
    assert not migration.STATE.exists() and not migration.EXPIRY.exists()
    assert migration.OWNERSHIP.exists()


def test_prepared_lifecycle_post_erase_preserves_reassigned_uid(tmp_path, monkeypatch):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch)
    migration = machine.migration
    migration.prepare()
    machine.user = None
    monkeypatch.setattr(migration.pwd, 'getpwuid', lambda identity: object())
    with pytest.raises(ValueError, match='reassigned-kiosk-uid'):
        migration.finish_remove()
    assert migration.STATE.exists() and migration.DISABLED.exists()


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
def test_prepared_lifecycle_post_erase_preserves_real_ordinary_mapped_worker(tmp_path, monkeypatch, backend):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    saved = migration.state()
    migration.prepare()
    thread = migration.PROCESSES / '42/task/42'
    (thread / 'attr').mkdir(parents=True)
    # Root credentials and ordinary audit/MAC identity are explicit fixture
    # inputs. The retained mapping itself comes from a real owned Linux child.
    (thread / 'status').write_text('Uid:\t0\t0\t0\t0\n')
    (thread / 'loginuid').write_text('1001\n')
    for attribute in ('current', 'exec'):
        (thread / 'attr' / attribute).write_text('unconfined\n')
    with mapped_pam_worker(tmp_path) as worker:
        (thread / 'maps').symlink_to(worker.proc / 'maps')
        assert str(worker.library) in (worker.proc / 'maps').read_text()
        worker.library.unlink()
        assert str(worker.library) + ' (deleted)' in (worker.proc / 'maps').read_text()
        for path in migration.PAYLOAD.iterdir():
            path.unlink()
        machine.user = None
        migration.finish_remove()
        assert worker.child.poll() is None
        assert str(worker.library) + ' (deleted)' in (worker.proc / 'maps').read_text()
    assert worker.child.returncode == 0
    migration.verify_pam(saved, originals=True)
    assert not migration.STATE.exists() and not migration.DISABLED.exists() and not migration.EXPIRY.exists()


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('active', ['uid', 'audit', 'mac-current', 'mac-exec', 'lease'])
def test_prepared_lifecycle_post_erase_still_preserves_kiosk_executors(tmp_path, monkeypatch, backend, active):
    import fcntl
    import os
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    migration.prepare()
    for path in migration.PAYLOAD.iterdir():
        path.unlink()
    machine.user = None
    before = migration.STATE.read_bytes()
    thread = migration.PROCESSES / '42/task/42'
    (thread / 'attr').mkdir(parents=True)
    (thread / 'status').write_text('Uid:\t0\t0\t0\t0\n')
    (thread / 'loginuid').write_text('1001\n')
    (thread / 'maps').write_text('')
    for attribute in ('current', 'exec'):
        (thread / 'attr' / attribute).write_text('unconfined\n')
    held = None
    if active == 'uid':
        (thread / 'status').write_text('Uid:\t0\t1006\t0\t0\n')
    elif active == 'audit':
        (thread / 'loginuid').write_text('1006\n')
    elif active.startswith('mac-'):
        label = ('onpc-kiosk-manager (enforce)\n' if backend == 'apparmor' else
                 'system_u:system_r:onpc_kiosk_manager_t:s0\n')
        (thread / 'attr' / active.removeprefix('mac-')).write_text(label)
    else:
        held = os.open(migration.LOCKS[0], os.O_RDWR)
        fcntl.flock(held, fcntl.LOCK_SH)
    try:
        with pytest.raises(BlockingIOError if active == 'lease' else ValueError,
                           match=None if active == 'lease' else 'kiosk-(?:processes|executors)-active'):
            migration.finish_remove()
        assert migration.STATE.read_bytes() == before
        assert migration.DISABLED.exists() and migration.EXPIRY.exists()
    finally:
        if held is not None:
            os.close(held)
    (thread / 'status').write_text('Uid:\t0\t0\t0\t0\n')
    (thread / 'loginuid').write_text('1001\n')
    for attribute in ('current', 'exec'):
        (thread / 'attr' / attribute).write_text('unconfined\n')
    migration.finish_remove()
    assert not migration.STATE.exists() and not migration.DISABLED.exists()


@pytest.mark.parametrize('changed', ['home', 'admin', 'orphan-marker', 'policy'])
def test_prepared_lifecycle_preserves_changed_owned_inputs(tmp_path, monkeypatch, changed):
    from types import SimpleNamespace
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch)
    migration = machine.migration
    if changed == 'home':
        machine.home_uid = 1007
    elif changed == 'admin':
        monkeypatch.setattr(migration.grp, 'getgrall', lambda: [
            SimpleNamespace(gr_name='wheel', gr_gid=10, gr_mem=[migration.USER])])
    elif changed == 'orphan-marker':
        migration.STATE.unlink()
        migration.write(migration.DISABLED, b'removing\n')
    else:
        migration.prepare()
        (migration.PAYLOAD / 'config.json').write_text('{"backend":"apparmor","changed":true}\n')
    with pytest.raises(ValueError):
        if changed in ('orphan-marker', 'policy'):
            migration.rollback()
        else:
            migration.prepare()
    assert machine.expires == (1 if changed == 'policy' else None)
    if changed == 'policy':
        assert migration.STATE.exists() and migration.DISABLED.exists() and not machine.loaded


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
def test_prepared_lifecycle_requires_retained_rollback_bytes_before_mutation(tmp_path, monkeypatch, backend):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    (migration.PAYLOAD / 'config.json').write_text('{"backend":"' + backend + '","changed":true}\n')
    before = migration.STATE.read_bytes()
    with pytest.raises(ValueError, match='changed-legacy-policy-payload'):
        migration.prepare()
    assert machine.loaded and machine.expires is None
    assert migration.STATE.read_bytes() == before and not migration.DISABLED.exists()
    assert not migration.EXPIRY.exists()


@pytest.mark.parametrize('variant', ['hidden', 'missing-key', 'visible'])
def test_prepared_lifecycle_visibility_preserves_metadata_without_version_vote(tmp_path, monkeypatch, variant):
    import os
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, installed=False)
    migration = machine.migration
    source = (b'# retained comments\n[User]\nIcon=/custom/icon.png\n'
              b'X-Unknown=value\n' +
              (b'SystemAccount=true\n' if variant == 'hidden' else
               b'SystemAccount=false\n' if variant == 'visible' else b'') +
              b'[Other]\nPreserve=true\n')
    cached = migration.CACHE / migration.USER
    cached.write_bytes(source)
    cached.chmod(0o600)
    os.setxattr(cached, 'user.retained', b'preserved')
    ordinary = migration.CACHE / 'ordinary-user'
    ordinary.write_bytes(b'[User]\nSystemAccount=true\n')
    migration.visibility()
    migration.visibility()
    expected = (source.replace(b'SystemAccount=true', b'SystemAccount=false') if variant == 'hidden' else
                source.replace(b'[Other]', b'SystemAccount=false\n[Other]') if variant == 'missing-key' else source)
    assert cached.read_bytes() == expected
    assert os.getxattr(cached, 'user.retained') == b'preserved'
    assert migration.ATTRIBUTE not in os.listxattr(cached)
    assert ordinary.read_bytes() == b'[User]\nSystemAccount=true\n'
    assert not (migration.CACHE / migration.SLOT).exists()
    assert not any('--version' in command or command[0] == 'rpm' for command in machine.commands)


@pytest.mark.parametrize('boundary', ['slot', 'committed'])
def test_prepared_lifecycle_visibility_recovers_exact_old_transaction(tmp_path, monkeypatch, boundary):
    import os
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, installed=False)
    migration = machine.migration
    cached = migration.CACHE / migration.USER
    cached.write_bytes(b'# retained\n[User]\nSystemAccount=true\nIcon=/custom\n')
    cached.chmod(0o600)
    original_replace = migration.os.replace
    original_remove = migration.os.removexattr
    failed = False
    def replace(*args, **kwargs):
        nonlocal failed
        if args[0] == migration.SLOT and boundary == 'slot' and not failed:
            failed = True
            raise OSError('visibility interruption')
        return original_replace(*args, **kwargs)
    def remove(*args, **kwargs):
        nonlocal failed
        if args[1] == migration.ATTRIBUTE and boundary == 'committed' and not failed:
            failed = True
            raise OSError('visibility interruption')
        return original_remove(*args, **kwargs)
    monkeypatch.setattr(migration.os, 'replace', replace)
    monkeypatch.setattr(migration.os, 'removexattr', remove)
    with pytest.raises(OSError, match='visibility interruption'):
        migration.visibility()
    assert failed
    assert ((migration.CACHE / migration.SLOT).exists() if boundary == 'slot' else
            migration.ATTRIBUTE in os.listxattr(cached))
    migration.visibility()
    migration.visibility()
    assert cached.read_bytes() == b'# retained\n[User]\nSystemAccount=false\nIcon=/custom\n'
    assert not (migration.CACHE / migration.SLOT).exists()
    assert migration.ATTRIBUTE not in os.listxattr(cached)


@pytest.mark.parametrize('foreign', ['slot', 'committed', 'live-daemon'])
def test_prepared_lifecycle_visibility_preserves_foreign_or_live_cache(tmp_path, monkeypatch, foreign):
    import os
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, installed=False)
    migration = machine.migration
    cached = migration.CACHE / migration.USER
    cached.write_bytes(b'[User]\nSystemAccount=true\n')
    cached.chmod(0o600)
    if foreign == 'slot':
        (migration.CACHE / migration.SLOT).write_bytes(b'foreign slot\n')
    elif foreign == 'committed':
        os.setxattr(cached, migration.ATTRIBUTE, b'{"foreign":true}')
    else:
        run = migration.run
        def live(arguments):
            if arguments[0] == 'systemctl':
                return type('Result', (), {'stdout': 'ActiveState=active\nSubState=running\nMainPID=123\n'})()
            return run(arguments)
        monkeypatch.setattr(migration, 'run', live)
    with pytest.raises(ValueError):
        migration.visibility()
    assert cached.read_bytes() == b'[User]\nSystemAccount=true\n'
    if foreign == 'slot':
        assert (migration.CACHE / migration.SLOT).read_bytes() == b'foreign slot\n'


def test_prepared_lifecycle_embedded_finalizer_is_unselected_and_payload_independent():
    renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
    source = renderer['embedded_prepared_confinement_finish_remove'](ROOT)
    assert 'def finish_remove():' in source and 'legacy cleanup failed' in source
    for distribution in ('ubuntu', 'fedora'):
        selected = renderer['render'](ROOT, distribution, 'postrm')
        assert 'ONPC_PREPARED_CONFINEMENT_FINISH_REMOVE' not in selected
    result = subprocess.run(['make', '--no-print-directory', 'package-source-files'],
                            cwd=ROOT, capture_output=True, text=True, timeout=30, check=True)
    assert 'data/kiosk-runtime-unselected/lifecycle_migration.py' not in result.stdout.splitlines()


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
def test_prepared_lifecycle_embedded_post_erase_executes_and_retries(tmp_path, monkeypatch, backend):
    import os
    import shlex
    from tools.test_storage import scratch_descriptors
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    # The distribution's fixed relabel tool survives product payload erasure.
    # Its private double accepts only the one source-defined admission pathname.
    relabel = tmp_path / 'usr/sbin/restorecon'
    relabel.parent.mkdir(parents=True)
    relabel.write_text('#!/bin/sh\nset -eu\n[ "$#" -eq 1 ]\n[ "$1" = ' +
                       shlex.quote(str(migration.LOCKS[0])) + ' ]\n')
    relabel.chmod(0o755)
    saved = migration.state()
    migration.prepare()
    for payload in migration.PAYLOAD.iterdir():
        payload.unlink()
    # Model verified account removal in the child without querying host NSS.
    renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
    header, body = renderer['embedded_prepared_confinement_finish_remove'](ROOT).split('\n', 1)
    body = relocate_system_paths(body, tmp_path, prefixes=('/etc/', '/var/', '/run/', '/home/', '/usr/', '/sys/', '/proc/'))
    body = body.replace("ROOT = Path('/')", 'ROOT = Path(' + repr(str(tmp_path)) + ')')
    body = body.replace("Path('/run')", 'Path(' + repr(str(tmp_path / 'run')) + ')')
    body = body.replace("Path('/proc')", 'Path(' + repr(str(tmp_path / 'proc')) + ')')
    body = body.replace('OWNER = 0', 'OWNER = ' + str(os.getuid()))
    body = body.replace('GROUP = 0', 'GROUP = ' + str(os.getgid()))
    body = body.replace('pwd.getpwnam(USER)', '(_ for _ in ()).throw(KeyError(USER))')
    body = body.replace('pwd.getpwuid(identity)', '(_ for _ in ()).throw(KeyError(identity))')
    failure = tmp_path / 'owned-post-erase-interruption'
    failure.touch()
    fault = ('\n_original_erase = erase\n'
             'def erase(path):\n'
             f'    failure = Path({str(failure)!r})\n'
             "    if path == PAM / 'systemd-user' and failure.exists():\n"
             '        failure.unlink()\n'
             "        raise OSError('owned post-erase interruption')\n"
             '    return _original_erase(path)\n')
    assert body.count('\nimport sys\ntry:\n') == 1
    body = body.replace('\nimport sys\ntry:\n', fault + '\nimport sys\ntry:\n')
    script = header + '\n' + body
    def run_finalizer():
        return subprocess.run(['/bin/sh'], input=script, capture_output=True, text=True,
                              timeout=30, pass_fds=scratch_descriptors())
    first = run_finalizer()
    assert first.returncode == 1 and 'preserving recovery state' in first.stderr
    assert migration.STATE.exists() and migration.DISABLED.exists()
    second = run_finalizer()
    assert second.returncode == 0, second.stderr
    assert run_finalizer().returncode == 0
    migration.verify_pam(saved, originals=True)
    assert not migration.STATE.exists() and not migration.EXPIRY.exists()


def test_prepared_lifecycle_removed_manifest_members_keep_existing_activation(tmp_path):
    module = runpy.run_path(str(ROOT / 'packaging/package_activation.py'))
    paths = ['usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
             'usr/share/oh-no-parent-control/confinement/config.json',
             'usr/lib/systemd/system/oh-no-parent-control-kiosk-confinement.service',
             'usr/lib/systemd/system/accounts-daemon.service.d/oh-no-parent-control.conf']
    old = tmp_path / 'previous.json'
    new = tmp_path / 'candidate.json'
    old.write_text(json.dumps({'version': 1, 'files': [dict(path=path, sha256='a' * 64,
                   activation=module['activation_for'](path)) for path in paths]}))
    new.write_text('{"version":1,"files":[]}')
    assert module['changed_impacts'](old, new) == ['reboot']


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('older_partial', [False, True])
def test_first_install_activation_origin_survives_interrupted_reinstall(tmp_path, distribution, older_partial):
    from tests.support.package_scripts import Machine
    machine = Machine(tmp_path, distribution)
    state = tmp_path / 'var/lib/oh-no-parent-control'
    first = state / 'first-install-in-progress'
    pending = state / 'package-activation-pending'
    previous = state / 'previous-package-activation.json'
    result = machine.run('preinst', 'install')
    assert result.returncode == 0, result.stderr
    assert first.is_file() and pending.is_file() and not previous.exists()
    manifest = machine.write('usr/share/oh-no-parent-control/package-activation.json',
        json.dumps({'version': 1, 'files': []}))
    if older_partial:
        # Earlier preinst generations replaced the absent origin with the
        # already-unpacked candidate. The retained first-install marker still
        # proves that no initial configuration has consumed its activation.
        previous.write_bytes(manifest.read_bytes())
    changed_impacts = runpy.run_path(str(ROOT / 'packaging/package_activation.py'))['changed_impacts']
    for _ in range(2):
        # Retain all bookkeeping just as failed configuration does, then use
        # the shared preinst entered by same-version APT/RPM reinstall.
        result = machine.run('preinst', 'upgrade')
        assert result.returncode == 0, result.stderr
        assert first.is_file() and pending.is_file() and not previous.exists()
        assert changed_impacts(previous, manifest) == ['reboot']


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('prior_manifest', [False, True])
def test_upgrade_activation_origin_is_retained_until_successful_configuration(tmp_path, distribution, prior_manifest):
    from tests.support.package_scripts import Machine
    machine = Machine(tmp_path, distribution)
    machine.baseline()
    state = tmp_path / 'var/lib/oh-no-parent-control'
    previous = state / 'previous-package-activation.json'
    pending = state / 'package-activation-pending'
    manifest_path = 'usr/share/oh-no-parent-control/package-activation.json'
    before = json.dumps({'version': 1, 'files': [{'path': 'etc/pam.d/product',
        'sha256': 'a' * 64, 'activation': 'reboot'}]})
    if prior_manifest:
        machine.write(manifest_path, before)
    result = machine.run('preinst', 'upgrade')
    assert result.returncode == 0, result.stderr
    assert pending.is_file() and previous.exists() == prior_manifest
    manifest = machine.write(manifest_path, json.dumps({'version': 1, 'files': [{
        'path': 'etc/pam.d/product', 'sha256': 'b' * 64, 'activation': 'reboot'}]}))
    changed_impacts = runpy.run_path(str(ROOT / 'packaging/package_activation.py'))['changed_impacts']
    for _ in range(2):
        result = machine.run('preinst', 'upgrade')
        assert result.returncode == 0, result.stderr
        assert pending.is_file() and previous.exists() == prior_manifest
        if prior_manifest:
            assert previous.read_text() == before
        assert changed_impacts(previous, manifest) == ['reboot']
    # Successful postinst consumes these exact records. A subsequent unchanged
    # reinstall must establish a new origin and avoid inventing another reboot.
    previous.unlink(missing_ok=True)
    pending.unlink()
    result = machine.run('preinst', 'upgrade')
    assert result.returncode == 0, result.stderr
    assert previous.read_bytes() == manifest.read_bytes()
    assert changed_impacts(previous, manifest) == []


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('name', ['package-activation-pending', 'previous-package-activation.json',
                                 'first-install-in-progress'])
@pytest.mark.parametrize('substitution', ['symlink', 'directory'])
def test_preinst_preserves_substituted_activation_bookkeeping(tmp_path, distribution, name, substitution):
    from tests.support.package_scripts import Machine
    machine = Machine(tmp_path, distribution)
    state = tmp_path / 'var/lib/oh-no-parent-control'
    record = state / name
    if substitution == 'symlink':
        foreign = machine.write('unrelated-state', 'preserve me\n')
        record.symlink_to(foreign)
    else:
        record.mkdir()
    result = machine.run('preinst', 'install')
    assert result.returncode != 0
    assert 'refusing substituted activation bookkeeping' in result.stderr
    if substitution == 'symlink':
        assert record.is_symlink() and foreign.read_text() == 'preserve me\n'
    else:
        assert record.is_dir()
    assert not (state / 'migration-in-progress').exists()


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('failure', ['provision', 'setup', 'pam', 'confinement', 'release'])
def test_owned_passwordless_configuration_stays_expired_until_both_guards_pass(package_machine, failure):
    root, state, run = package_machine
    stub = root / 'bin/stub'
    source = stub.read_text()
    boundary = 'case "$name" in\n'
    lifecycle = r'''case "$name:$*" in
    oh-no-parent-control-provision:*--quarantine-account*)
        printf '1\n' > "$AUDIT_ROOT/account-expiry"
        ;;
    usermod:*|passwd:*)
        test "$(cat "$AUDIT_ROOT/account-expiry")" = 1 || exit 91
        ;;
    oh-no-parent-control-provision:*--release-account)
        test -f "$AUDIT_ROOT/shared-pam-verified" || exit 92
        test -f "$AUDIT_ROOT/final-confinement-verified" || exit 93
        test "${CONFIGURE_FAILURE:-}" != release || exit 71
        printf '\n' > "$AUDIT_ROOT/account-expiry"
        ;;
    oh-no-parent-control-provision:*)
        test "$(cat "$AUDIT_ROOT/account-expiry")" = 1 || exit 91
        test "${CONFIGURE_FAILURE:-}" != provision || exit 71
        ;;
    setpriv:*)
        test "$(cat "$AUDIT_ROOT/account-expiry")" = 1 || exit 91
        test "${CONFIGURE_FAILURE:-}" != setup || exit 71
        ;;
    pam-auth-update:*|oh-no-parent-control-fedora-pam:install)
        test "$(cat "$AUDIT_ROOT/account-expiry")" = 1 || exit 91
        test "${CONFIGURE_FAILURE:-}" != pam || exit 71
        touch "$AUDIT_ROOT/shared-pam-verified"
        ;;
    oh-no-parent-control-kiosk-confinement-integration:install)
        test "$(cat "$AUDIT_ROOT/account-expiry")" = 1 || exit 91
        test "${CONFIGURE_FAILURE:-}" != confinement || exit 71
        touch "$AUDIT_ROOT/final-confinement-verified"
        ;;
esac
'''
    assert source.count(boundary) == 1
    stub.write_text(source.replace(boundary, lifecycle + boundary, 1))
    result = run(CONFIGURE_FAILURE=failure)
    assert result.returncode == 71, result.stderr
    assert (root / 'account-expiry').read_text() == '1\n'
    assert (state / 'package-created-kiosk-uid').read_text() == '1006\n'
    assert run().returncode == 0
    assert (root / 'account-expiry').read_text() == '\n'
    commands = (root / 'commands').read_text()
    assert 'setpriv --reuid 1006 --regid 1006 --init-groups -- ' in commands
    assert not any(line.startswith('runuser ') for line in commands.splitlines())


@pytest.mark.parametrize('package_machine,backend', [('ubuntu', 'apparmor'), ('fedora', 'selinux')],
                         indirect=['package_machine'])
@pytest.mark.parametrize('profile', ['minimal', 'lxc-sssd', 'continued-include', 'vendor-symlink',
                                   'local-manager'])
def test_configuration_composes_real_confinement_with_supported_machine_profiles(
        package_machine, backend, profile):
    from oh_no_parent_control.preferences import default_preferences

    root, state, run = package_machine
    payload, pam, vendor = use_real_kiosk_confinement(root, backend)
    use_real_state_migration(root)
    (payload.parent / 'app.json').write_text('{"version": "1.4"}\n')
    preferences = default_preferences()
    preferences.update(parent_control_enabled=True, daily_time_limit_minutes=75)
    preferences['personal']['language'] = 'fr'
    preferences['apps'] = {'game.desktop': {'state': 'conditional', 'targets': ['/opt/game'],
                                          'patterns': [], 'user_saved_match_rule': True}}
    directory = state / 'preferences'
    directory.mkdir(mode=0o700)
    record = directory / '1001.json'
    record.write_text(json.dumps(preferences))
    record.chmod(0o600)
    retained = record.read_bytes()
    # Preserve real shared-stack inputs through the package's native-PAM audit;
    # only pam-auth-update itself remains an explicit distribution-tool double.
    sources = {
        'common-auth': 'auth required pam_oh_no_parent_control.so\n',
        'common-account': 'account required pam_oh_no_parent_control.so kiosk\n',
        'common-session': 'session required pam_oh_no_parent_control.so kiosk\n',
        'common-session-noninteractive': 'session required pam_unix.so\n',
    }
    directive = '@include\\\n\t' if profile == 'continued-include' else '@include '
    if profile != 'minimal':
        rule = 'session optional pam_cgfs.so -c freezer,memory,name=systemd\n'
        sources['common-session'] += 'session optional pam_sss.so\n' + rule
        sources['common-session-noninteractive'] += rule
    for name, contents in sources.items():
        (pam / name).write_text(contents)
        (pam / name).chmod(0o644)
    (pam / 'gdm-password').write_text(directive + 'common-session\n')
    (vendor / 'systemd-user').write_text('@include common-account\n' +
                                       directive + 'common-session-noninteractive\n')
    if profile == 'vendor-symlink':
        target = vendor / 'common-session'
        target.write_text(sources['common-session'])
        target.chmod(0o644)
        (pam / 'common-session').unlink()
        (pam / 'common-session').symlink_to(target)
    if profile == 'local-manager':
        (pam / 'systemd-user').write_bytes((vendor / 'systemd-user').read_bytes())
        (pam / 'systemd-user').chmod(0o644)
    original = {name: (pam / name).read_bytes() for name in sources}
    for _ in range(2):
        result = run(PAM_LOCAL_CHANGES='1')
        assert result.returncode == 0, result.stderr
        saved = json.loads((state / 'kiosk-confinement.json').read_text())
        assert saved['loaded_config_sha256'] == hashlib.sha256(
            (payload / 'config.json').read_bytes()).hexdigest()
        assert saved['loaded_policy_sha256'] == hashlib.sha256(
            (payload / ('onpc-kiosk.apparmor' if backend == 'apparmor' else 'onpc-kiosk.cil'))
            .read_bytes()).hexdigest()
        for name in ('gdm-password', 'systemd-user'):
            assert (pam / name).read_text() == saved['pam'][name]['after']
            assert (pam / name).read_text().endswith(
                'session required pam_oh_no_parent_control.so kiosk-confinement\n'
                '# END Oh No Parent Control execution confinement\n')
        assert {name: (pam / name).read_bytes() for name in sources} == original
        assert record.read_bytes() == retained
        assert not (state / 'migration-in-progress').exists()
        assert not (state / 'package-activation-pending').exists()
        assert 'PASS: Oh No! Parent Control package configuration completed successfully.' in result.stdout
    commands = (root / 'commands').read_text().splitlines()
    loaded = next(index for index, line in enumerate(commands)
                  if line.startswith('policy-tool -r ' if backend == 'apparmor' else 'policy-tool -i '))
    released = next(index for index, line in enumerate(commands)
                    if line.startswith('oh-no-parent-control-provision ') and '--release-account' in line)
    activated = commands.index(f'systemctl --system restart {BROKER}')
    assert loaded < released < activated


@pytest.mark.parametrize('package_machine,backend', [('ubuntu', 'apparmor'), ('fedora', 'selinux')],
                         indirect=['package_machine'])
@pytest.mark.parametrize('failure,reason', [
    ('unknown-module', 'unsupported-pam-session-module'),
    ('short-circuit', 'pam-can-skip-confinement'),
    ('pending-vendor', 'pending-distribution-pam-update'),
    ('compiler', 'command-failed'), ('missing-tool', 'os-error'),
])
def test_real_confinement_failure_preserves_exclusion_and_configuration_recovers(
        package_machine, backend, failure, reason):
    root, state, run = package_machine
    payload, pam, _vendor = use_real_kiosk_confinement(root, backend)
    use_real_state_migration(root)
    (payload.parent / 'app.json').write_text('{"version": "1.4"}\n')
    recovery = None
    if failure in ('unknown-module', 'short-circuit'):
        original = (pam / 'gdm-password').read_text()
        (pam / 'gdm-password').write_text(
            'session optional pam_exec.so /private/program\n' if failure == 'unknown-module'
            else 'session sufficient pam_cgfs.so\n')
        recovery = lambda: (pam / 'gdm-password').write_text(original)
    elif failure == 'pending-vendor':
        pending = pam / 'gdm-password.dpkg-dist'
        pending.write_text('session required pam_limits.so\n')
        pending.chmod(0o644)
        recovery = pending.unlink
    elif failure == 'compiler':
        status = root / 'policy-load-status'
        status.write_text('7\n')
        recovery = status.unlink
    elif failure == 'missing-tool':
        tool = root / 'usr/sbin' / ('apparmor_parser' if backend == 'apparmor' else 'semodule')
        before = tool.read_bytes()
        tool.unlink()

        def restore():
            tool.write_bytes(before)
            tool.chmod(0o755)
        recovery = restore
    pam_before = {name: (pam / name).read_bytes() if (pam / name).exists() else None
                  for name in ('gdm-password', 'systemd-user')}
    result = run()
    assert result.returncode != 0
    assert 'reason=' + reason in result.stderr
    assert '/private/program' not in result.stderr
    assert (state / 'migration-in-progress').exists()
    assert (state / 'package-activation-pending').exists()
    assert not (root / 'run/oh-no-parent-control-package-configuration-complete').exists()
    assert {name: (pam / name).read_bytes() if (pam / name).exists() else None
            for name in pam_before} == pam_before
    commands = (root / 'commands').read_text()
    assert '--release-account' not in commands
    assert f'systemctl --system restart {BROKER}' not in commands
    assert f'systemctl --system start {BROKER}' not in commands
    recovery()
    result = run()
    assert result.returncode == 0, result.stderr
    assert not (state / 'migration-in-progress').exists()
    assert not (state / 'package-activation-pending').exists()
    assert 'PASS: Oh No! Parent Control package configuration completed successfully.' in result.stdout
    assert f'systemctl --system restart {BROKER}' in (root / 'commands').read_text()


@pytest.mark.parametrize('package_machine,entrypoint', [
    ('ubuntu', 'configure'), ('fedora', 'configure'), ('fedora', 'rpm-posttrans'),
], indirect=['package_machine'])
@pytest.mark.parametrize('failure', [None, 'startup', 'trust', 'readiness', 'restore'])
def test_reinstall_restores_snapshot_only_after_enforcement_is_ready(
    package_machine, entrypoint, failure,
):
    root, state, run = package_machine
    canary = root / 'usr/share/oh-no-parent-control/00-oh-no-parent-control-canary.rules'
    distribution = 'fedora' if canary.exists() else 'ubuntu'
    if entrypoint == 'rpm-posttrans':
        renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
        scripts = root / 'rpm-lifecycle'
        renderer['rpm_scripts'](ROOT, scripts)
        (root / 'postinst').write_text(relocate_system_paths(
            rpm_script_source(scripts / 'rpm-posttrans'), root))

    # Interrupted post-erase retained the exact policy snapshot and durable
    # admission barrier, but restored the baseline with fapolicyd stopped.
    snapshot = state / 'uninstall-enforcement.json'
    snapshot.write_text('{"retained": "derived policy before removal"}\n')
    before = snapshot.read_bytes()
    barrier = state / 'kiosk-admission-barrier'
    barrier.write_text('owned removal barrier\n')
    stub = root / 'bin/stub'
    source = stub.read_text()
    boundary = 'case "$name" in\n'
    stateful_commands = r'''case "$name:$*" in
    systemctl:'start fapolicyd.service '*|deb-systemd-invoke:'start fapolicyd.service '*)
        test "${REINSTALL_FAILURE:-}" != startup || exit 7
        touch "$AUDIT_ROOT/fapolicyd-active"
        # Ubuntu's ordinary service start includes its readiness drop-in.
        if [ "$REINSTALL_DISTRIBUTION" = ubuntu ]; then
            test "${REINSTALL_FAILURE:-}" != readiness || exit 9
            touch "$AUDIT_ROOT/enforcement-ready"
        fi
        ;;
    oh-no-parent-control-package-activation:'wait-child-trust --refresh')
        test -f "$AUDIT_ROOT/fapolicyd-active" || exit 96
        test "${REINSTALL_FAILURE:-}" != trust || exit 8
        touch "$AUDIT_ROOT/trust-refreshed"
        ;;
    systemctl:'start oh-no-parent-control-execution-policy-ready.service')
        test -f "$AUDIT_ROOT/fapolicyd-active" || exit 96
        test -f "$AUDIT_ROOT/trust-refreshed" || exit 97
        test -f "$AUDIT_ROOT/canary-loaded" || exit 92
        test "${REINSTALL_FAILURE:-}" != readiness || exit 9
        touch "$AUDIT_ROOT/enforcement-ready"
        ;;
    oh-no-parent-control-uninstall:--restore)
        test -f "$AUDIT_ROOT/fapolicyd-active" || exit 6
        test -f "$AUDIT_ROOT/trust-refreshed" || exit 97
        test -f "$AUDIT_ROOT/enforcement-ready" || exit 98
        test -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/migration-in-progress" || exit 99
        test -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/kiosk-admission-barrier" || exit 99
        test "${REINSTALL_FAILURE:-}" != restore || exit 10
        rm "$AUDIT_ROOT/var/lib/oh-no-parent-control/uninstall-enforcement.json"
        touch "$AUDIT_ROOT/snapshot-restored"
        exit 0
        ;;
    oh-no-parent-control-kiosk-confinement-integration:install)
        test -f "$AUDIT_ROOT/snapshot-restored" || exit 99
        test -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/migration-in-progress" || exit 99
        test ! -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/uninstall-enforcement.json" || exit 99
        rm "$AUDIT_ROOT/var/lib/oh-no-parent-control/kiosk-admission-barrier"
        touch "$AUDIT_ROOT/confinement-armed"
        ;;
    systemctl:'--system restart oh-no-parent-control-broker.service')
        test -f "$AUDIT_ROOT/confinement-armed" || exit 99
        test ! -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/kiosk-admission-barrier" || exit 99
        ;;
esac
'''
    assert source.count(boundary) == 1
    stub.write_text(source.replace(boundary, stateful_commands + boundary, 1))
    (root / 'usr/libexec/oh-no-parent-control-uninstall').symlink_to(stub)
    environment = {'REINSTALL_DISTRIBUTION': distribution,
                   'FAPOLICYD_ACTIVE_STATUS': '1'}
    result = run(**environment, REINSTALL_FAILURE=failure or '')
    if failure:
        assert result.returncode == {
            'startup': 7, 'trust': 8, 'readiness': 9, 'restore': 10,
        }[failure], result.stderr
        assert snapshot.read_bytes() == before
        assert barrier.read_text() == 'owned removal barrier\n'
        for name in ('migration-in-progress', 'package-activation-pending',
                     'previous-package-activation.json'):
            assert (state / name).exists(), name
        assert not (root / 'confinement-armed').exists()
        commands = (root / 'commands').read_text()
        assert 'oh-no-parent-control-kiosk-confinement-integration install' not in commands
        assert f'systemctl --system restart {BROKER}' not in commands
        assert ('oh-no-parent-control-uninstall --restore' in commands) == (failure == 'restore')
        # Retry the same owned state through the same native entry point.
        (root / 'commands').write_text('')
        result = run(**environment)

    assert result.returncode == 0, result.stderr
    assert not snapshot.exists() and not barrier.exists()
    assert (root / 'snapshot-restored').exists()
    assert (root / 'confinement-armed').exists()
    for name in ('migration-in-progress', 'package-activation-pending',
                 'previous-package-activation.json'):
        assert not (state / name).exists(), name
    commands = (root / 'commands').read_text().splitlines()
    restore = commands.index('oh-no-parent-control-uninstall --restore')
    confinement = commands.index('oh-no-parent-control-kiosk-confinement-integration install')
    startup = ('systemctl' if distribution == 'fedora' else 'deb-systemd-invoke') + (
        ' start fapolicyd.service malcontent-timerd.service malcontent-timer-extension-agent.service')
    assert commands.index(startup) < commands.index(
        'oh-no-parent-control-package-activation wait-child-trust --refresh') < restore
    if distribution == 'fedora':
        assert commands.index('systemctl start oh-no-parent-control-execution-policy-ready.service') < restore
    assert restore < confinement < commands.index(f'systemctl --system restart {BROKER}')
    assert commands.count('oh-no-parent-control-uninstall --restore') == 1
    assert commands.count('oh-no-parent-control-kiosk-confinement-integration install') == 1


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('schema', [1, 2, 3, 4])
def test_v1_4_configuration_upgrades_legacy_policy_without_losing_choices(package_machine, schema):
    from oh_no_parent_control.preferences import PreferenceStore

    root, state, run = package_machine
    use_real_state_migration(root)
    product = root / 'usr/share/oh-no-parent-control/app.json'
    product.write_text('{"version": "1.4"}')
    (state / 'previous-product.json').write_text('{"version": "1.3"}')
    (state / 'previous-product.json').chmod(0o600)
    entry = {'state': 'conditional', 'targets': ['/opt/game/game']}
    if schema >= 2:
        entry['patterns'] = ['/opt/game/*']
    if schema >= 3:
        entry['user_saved_match_rule'] = True
    legacy = {
        'version': schema, 'parent_control_enabled': True,
        'daily_time_limit_minutes': 75, 'apps': {'game.desktop': entry},
        'request': {'last_selected_duration': 'custom', 'last_custom_minutes': 12.5,
                    'allow_soft_blocked_apps': True, 'last_selected_approver_uid': 1003,
                    'child_muted': False, 'kiosk_muted': False},
    }
    if schema == 4:
        legacy['personal'] = {'language': 'fr'}
    directory = state / 'preferences'
    directory.mkdir(mode=0o700)
    record = directory / '1001.json'
    record.write_text(json.dumps(legacy))
    record.chmod(0o600)
    before = record.read_bytes()
    # Reconfiguration must establish its own exclusion and stop a running broker.
    (state / 'migration-in-progress').unlink()
    (root / 'broker-active').touch()

    result = run()
    assert result.returncode == 0, result.stderr
    saved = PreferenceStore(directory).load(1001)
    assert saved['version'] == 4
    assert saved['parent_control_enabled'] is True
    assert saved['daily_time_limit_minutes'] == 75
    # The current reader supplies the compatible unit default for legacy records.
    # Compare every saved choice as well as that documented normalized field.
    assert saved['request'] == {**legacy['request'], 'last_custom_unit': 'minutes'}
    assert saved['apps'] == {'game.desktop': {
        **entry, 'patterns': ['/opt/game/*'] if schema >= 2 else [],
        'user_saved_match_rule': schema >= 2,
    }}
    assert saved['personal'] == {
        'language': 'fr' if schema == 4 else '',
        'time_grant_presets': [300, 900, 1800, 3600, 7200, 14400],
        'notifications': {'show_in_fullscreen': True, 'reminders': [
            {'id': name, 'value': value, 'unit': unit, 'text': ''}
            for name, value, unit in [('ten-minutes', 10, 'minute'), ('five-minutes', 5, 'minute'),
                                     ('one-minute', 1, 'minute'), ('fifteen-seconds', 15, 'second')]]
        },
    }
    if schema == 4:
        assert record.read_bytes() == before, 'compatible additions need no on-disk rewrite'
    assert record.stat().st_mode & 0o777 == 0o600
    assert json.loads((state / 'whats-new-installation.json').read_text()) == {
        'version': 1, 'first_version': '1.3', 'current_version': '1.4',
    }
    assert not (state / 'previous-product.json').exists()
    commands = (root / 'commands').read_text().splitlines()
    assert commands.index('oh-no-parent-control-migrate-state ') < commands.index(
        f'systemctl --system restart {BROKER}')
    after = record.read_bytes()
    result = run()
    assert result.returncode == 0, result.stderr
    assert record.read_bytes() == after


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('personal_only', [False, True])
@pytest.mark.parametrize('fields', ['reminders', 'presets', 'both', 'empty'])
def test_v1_4_configuration_retains_personal_customizations(package_machine, personal_only, fields):
    from oh_no_parent_control.preferences import PreferenceStore, default_preferences

    root, state, run = package_machine
    use_real_state_migration(root)
    (root / 'usr/share/oh-no-parent-control/app.json').write_text('{"version": "1.4"}')
    personal = {'language': 'fr', 'whats_new_seen': ['1.3:Child']}
    if fields in ('reminders', 'both', 'empty'):
        personal['notifications'] = {'show_in_fullscreen': False, 'reminders': [] if fields == 'empty' else [
            {'id': 'save-game', 'value': 42, 'unit': 'second', 'text': '  Save <game>!  '}]}
    if fields in ('presets', 'both', 'empty'):
        personal['time_grant_presets'] = [] if fields == 'empty' else [123, 6, 86400]
    value = {'version': 4, 'personal': personal}
    if not personal_only:
        value = {**default_preferences(), **value}
        # A remembered duration remains valid even when deleted from presets.
        value['request']['last_selected_duration'] = '900'
    directory = state / 'preferences'
    directory.mkdir(mode=0o700)
    record = directory / '0.json'
    record.write_text(json.dumps(value))
    record.chmod(0o600)
    before = record.read_bytes()

    for _ in range(2):
        result = run()
        assert result.returncode == 0, result.stderr
        assert record.read_bytes() == before
        saved = PreferenceStore(directory).load(0)
        assert saved['personal']['language'] == 'fr'
        assert saved['personal']['whats_new_seen'] == ['1.3:Child']
        if 'notifications' in personal:
            assert saved['personal']['notifications'] == personal['notifications']
        if 'time_grant_presets' in personal:
            assert saved['personal']['time_grant_presets'] == sorted(personal['time_grant_presets'])
        if not personal_only:
            assert saved['request'] == value['request']


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('invalid', [
    {'version': 5, 'personal': {'language': ''}},
    {'version': 4, 'personal': {'language': '', 'time_grant_presets': [0]}},
    {'version': 4, 'personal': {'language': '', 'notifications': {}}},
], ids=['future-schema', 'invalid-presets', 'invalid-reminders'])
def test_v1_4_configuration_validation_failure_blocks_activation_and_allows_retry(package_machine, invalid):
    root, state, run = package_machine
    use_real_state_migration(root)
    (root / 'usr/share/oh-no-parent-control/app.json').write_text('{"version": "1.4"}')
    directory = state / 'preferences'
    directory.mkdir(mode=0o700)
    record = directory / '1001.json'
    record.write_text(json.dumps(invalid))
    record.chmod(0o600)
    before = record.read_bytes()

    result = run()
    assert result.returncode != 0
    assert (state / 'migration-in-progress').exists()
    assert record.read_bytes() == before
    assert f'--system restart {BROKER}' not in (root / 'commands').read_text()
    assert f'--system start {BROKER}' not in (root / 'commands').read_text()
    assert not (state / 'whats-new-installation.json').exists()

    # Model correcting the rejected input, then retry normal configuration.
    record.write_text('{"version": 4, "personal": {"language": "fr"}}')
    corrected = record.read_bytes()
    result = run()
    assert result.returncode == 0, result.stderr
    assert not (state / 'migration-in-progress').exists()
    assert record.read_bytes() == corrected


@pytest.mark.parametrize('package_machine', ['fedora'], indirect=True)
def test_native_policy_directory_permissions_and_restore_order_survive_retry(package_machine):
    root, state, run = package_machine
    for relative in ('etc/fapolicyd/rules.d', 'etc/fapolicyd/trust.d'):
        directory = root / relative
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o750)
    (state / 'uninstall-enforcement.json').write_text('{}')
    helper = root / 'usr/libexec/oh-no-parent-control-uninstall'
    helper.write_text('''#!/bin/sh
test "$1" = --restore || exit 96
test -f "$AUDIT_ROOT/etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules" || exit 97
test -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/migration-in-progress" || exit 98
printf '%s\\n' 'restored original-policy snapshot' >> "$AUDIT_ROOT/commands"
''')
    helper.chmod(0o755)
    result = run(ORIGINAL_POLICY_ELIGIBLE='yes', ORIGINAL_POLICY_COMMIT_STATUS='7')
    assert result.returncode == 7
    assert 'restored original-policy snapshot' not in (root / 'commands').read_text()
    result = run(ORIGINAL_POLICY_ELIGIBLE='yes')
    assert result.returncode == 0, result.stderr
    commands = (root / 'commands').read_text().splitlines()
    assert commands.index('oh-no-parent-control-fedora-execution-policy commit') < commands.index(
        'restored original-policy snapshot')
    for relative in ('etc/fapolicyd/rules.d', 'etc/fapolicyd/trust.d'):
        assert (root / relative).stat().st_mode & 0o777 == 0o750


@pytest.mark.parametrize("boot_order_changed", [False, True])
@pytest.mark.parametrize("native_pam_changed", [False, True])
def test_v1_1_upgrade_uses_real_activation_manifest(package_machine, boot_order_changed, native_pam_changed):
    root, state, run = package_machine
    activation = runpy.run_path(str(ROOT / "debian/package_activation.py"))
    # Old manifests marked the fresh diagnostic commands as reboot-required.
    # Current native PAM changes separately require renewal of the persistent
    # user manager; keep unchanged PAM distinct from those command updates.
    old_levels = {
        "usr/libexec/oh-no-parent-control-session-limit-check": "reboot",
        "usr/libexec/oh-no-parent-control-execution-policy-ready": "reboot",
        "usr/lib/x86_64-linux-gnu/security/pam_oh_no_parent_control.so": "reboot",
        "usr/libexec/oh-no-parent-control-broker": "process-restart",
        "usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/extension.js": "session-renewal",
        "usr/lib/systemd/system/display-manager.service.d/oh-no-parent-control.conf": "reboot",
    }
    old_files = []
    for path, level in old_levels.items():
        old_files.append({
            "path": path,
            "sha256": hashlib.sha256(b"old payload").hexdigest(),
            "activation": level,
        })
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        changed = (native_pam_changed if path.endswith('/security/pam_oh_no_parent_control.so') else
                   boot_order_changed if "display-manager.service.d/" in path else True)
        target.write_text("updated payload" if changed else "old payload")
    (state / "previous-package-activation.json").write_text(json.dumps({
        "version": 1, "files": old_files,
    }))
    activation["generate"](
        root, root / "usr/share/oh-no-parent-control/package-activation.json",
        [Path(path) for path in old_levels],
    )
    # Replace only this fixture's comparison stub with the shipped helper.
    helper = root / "usr/libexec/oh-no-parent-control-package-activation"
    helper.unlink()
    source = (ROOT / "packaging/package_activation.py").read_text()
    # Only comparison runs for real in this relocated machine. Keep the
    # daemon-readiness double: the host has neither this fixture's installed
    # trust file nor a fixture fapolicyd database. Exact live-record matching
    # has separate helper tests, and lifecycle tests cover its failure status.
    source = source.replace('    args = parser.parse_args()',
        '    args = parser.parse_args()\n'
        '    if args.command == "prepare-child-trust-backend":\n'
        '        print("none")\n'
        '        raise SystemExit(0)\n'
        '    if args.command == "complete-child-trust-backend":\n'
        '        raise SystemExit(0)\n'
        '    if args.command == "wait-child-trust":\n'
        '        import os\n'
        '        raise SystemExit(int(os.environ.get("TRUST_READY_STATUS", "0")))')
    helper.write_text(f"#!{sys.executable}\n" + source.split("\n", 1)[1])
    helper.chmod(0o755)

    result = run()
    assert result.returncode == 0, result.stderr
    commands = (root / "commands").read_text().splitlines()
    assert f"systemctl --system restart {BROKER}" in commands
    reboot = boot_order_changed or native_pam_changed
    assert ("notify-reboot-required " in commands) == reboot
    assert (root / "run/reboot-required").exists() == reboot
    assert (REBOOT_NOTICE in result.stderr) == reboot


@pytest.mark.parametrize("reboot", [False, True])
def test_configuration_output_ends_with_success_then_reboot_notice(package_machine, reboot):
    _, _, run = package_machine
    result = run(combine_output=True, IMPACTS="reboot" if reboot else "")
    assert result.returncode == 0, result.stdout
    success = (
        "\033[1;32mPASS: Oh No! Parent Control package configuration "
        "completed successfully.\033[0m"
    )
    expected = [success, REBOOT_NOTICE] if reboot else [success]
    assert result.stdout.splitlines()[-len(expected):] == expected
    assert result.stdout.count(success) == 1
    assert result.stdout.count(REBOOT_NOTICE) == int(reboot)


def test_apt_configuration_queues_notice_until_dpkg_finishes(package_machine):
    root, _, run = package_machine
    result = run(DPKG_FRONTEND_LOCKED="true", IMPACTS="reboot")
    assert result.returncode == 0, result.stderr
    assert "PASS:" not in result.stdout
    assert REBOOT_NOTICE not in result.stderr
    pending = root / "run/oh-no-parent-control-package-configuration-complete"
    assert pending.is_file()
    assert pending.stat().st_mode & 0o777 == 0o600
    result = run(DPKG_FRONTEND_LOCKED="true", BROKER_STATUS="1")
    assert result.returncode != 0
    assert not pending.exists(), "failed retries must discard earlier completion"


@pytest.mark.parametrize("impacts,action", [
    ("process-restart", "restart"), ("session-renewal", "restart"),
    ("reboot", "start"), ("", "start"),
    ("process-restart\nreboot", "restart"),
])
def test_configure_activates_static_broker_after_migration(package_machine, impacts, action):
    root, state, run = package_machine
    result = run(IMPACTS=impacts)
    assert result.returncode == 0, result.stderr
    commands = (root / "commands").read_text().splitlines()
    activation = f"systemctl --system {action} {BROKER}"
    assert commands.count(activation) == 1
    assert commands.index("oh-no-parent-control-migrate-state ") < commands.index(activation)
    assert commands.index(f"policy-rc.d {BROKER} {action}") < commands.index(activation)
    assert "inactive static unit skipped" not in result.stderr
    assert not (state / "package-activation-pending").exists()
    assert (root / "run/reboot-required").exists() == ("reboot" in impacts)
    assert ("notify-reboot-required " in commands) == ("reboot" in impacts)
    assert (REBOOT_NOTICE in result.stderr) == ("reboot" in impacts)
    assert "PASS: Oh No! Parent Control package configuration completed successfully." in result.stdout


def test_ubuntu_does_not_start_fedora_readiness_unit(package_machine):
    root, _, run = package_machine
    result = run(READINESS_STATUS='9')
    assert result.returncode == 0, result.stderr
    assert 'oh-no-parent-control-execution-policy-ready.service' not in (root / 'commands').read_text()
    assert 'fagenrules' not in (root / 'commands').read_text()
    assert 'fapolicyd-cli --reload-rules' not in (root / 'commands').read_text()


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('manager_state', ['inactive', 'active', 'failed'])
def test_configuration_retires_only_the_owned_failed_kiosk_manager(package_machine, manager_state):
    root, _, run = package_machine
    failure = root / 'kiosk-manager-failed'
    failed = manager_state == 'failed'
    if failed:
        failure.touch()
    result = run(IMPACTS='reboot', KIOSK_MANAGER_STATE=manager_state)
    assert result.returncode == 0, result.stderr
    commands = (root / 'commands').read_text().splitlines()
    reset = 'systemctl reset-failed user@1006.service'
    assert commands.count(reset) == int(failed)
    assert not failure.exists()
    assert not any(command.startswith(('systemctl start user@', 'systemctl stop user@',
                                       'systemctl restart user@')) for command in commands)
    assert not any('reset-failed' in command and command != reset for command in commands)
    if failed:
        assert commands.index('oh-no-parent-control-kiosk-confinement-integration install') < commands.index(reset)
        assert commands.index('systemctl --system start ' + BROKER) < commands.index(reset)
    assert REBOOT_NOTICE in result.stderr


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('failure', ['confinement', 'broker', 'query', 'reset'])
def test_kiosk_failed_state_recovery_preserves_configuration_retry(package_machine, failure):
    root, state, run = package_machine
    failed = root / 'kiosk-manager-failed'
    failed.touch()
    first_install = state / 'first-install-in-progress'
    first_install.touch()
    previous = state / 'previous-package-activation.json'
    previous.write_text('original activation comparison\n')
    result = run(**{
        'confinement': {'CONFINEMENT_STATUS': '7'},
        'broker': {'BROKER_STATUS': '8'},
        'query': {'KIOSK_QUERY_STATUS': '10'},
        'reset': {'KIOSK_RESET_STATUS': '9'},
    }[failure])
    assert result.returncode == {'confinement': 7, 'broker': 1, 'query': 10, 'reset': 9}[failure]
    assert failed.exists()
    assert (state / 'package-activation-pending').exists()
    assert previous.read_text() == 'original activation comparison\n'
    assert first_install.exists()
    commands = (root / 'commands').read_text().splitlines()
    reset = 'systemctl reset-failed user@1006.service'
    assert (reset in commands) == (failure == 'reset')
    retry = run()
    assert retry.returncode == 0, retry.stderr
    assert not failed.exists()
    assert not (state / 'package-activation-pending').exists()
    assert not previous.exists()
    assert not first_install.exists()


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('ownership', ['missing', 'changed-uid', 'symlink', 'unsafe-mode', 'foreign-owner'])
def test_failed_manager_recovery_refuses_unowned_kiosk(package_machine, ownership):
    root, state, run = package_machine
    failed = root / 'kiosk-manager-failed'
    failed.touch()
    marker = state / 'package-created-kiosk-uid'
    env = {}
    if ownership == 'missing':
        marker.unlink()
    elif ownership == 'changed-uid':
        marker.write_text('1007\n')
    elif ownership == 'symlink':
        foreign = root / 'foreign-uid'
        foreign.write_bytes(marker.read_bytes())
        marker.unlink()
        marker.symlink_to(foreign)
    else:
        env['KIOSK_MARKER_METADATA'] = '0:644' if ownership == 'unsafe-mode' else '1000:600'
    result = run(**env)
    assert result.returncode != 0
    assert 'refusing to modify an unowned or changed kiosk account' in result.stderr
    assert failed.exists()
    assert (state / 'package-activation-pending').exists()
    assert not any('user@' in line for line in (root / 'commands').read_text().splitlines())
    if ownership == 'symlink':
        assert marker.is_symlink() and foreign.read_text() == '1006\n'


@pytest.mark.parametrize("impacts", ["", "process-restart", "session-renewal", None],
                         ids=["reinstall", "broker-update", "session-update", "reconfigure"])
def test_reboot_marker_repeats_package_notice_until_reboot(package_machine, impacts):
    root, state, run = package_machine
    result = run(IMPACTS="reboot")
    assert result.returncode == 0, result.stderr
    assert result.stderr.count(REBOOT_NOTICE) == 1
    packages = root / "run/reboot-required.pkgs"
    original_packages = packages.read_text()

    for rebooted in (False, True):
        if rebooted:
            # A reboot clears these files from /run; only the fixture is changed.
            (root / "run/reboot-required").unlink()
            packages.unlink()
        if impacts is not None:
            # preinst records a new comparison for each reinstall or upgrade.
            (state / "package-activation-pending").touch()
            (state / "previous-package-activation.json").touch()
        result = run(IMPACTS=impacts or "")
        assert result.returncode == 0, result.stderr
        assert (REBOOT_NOTICE in result.stderr) == (not rebooted)
        assert not (state / "package-activation-pending").exists()
        if rebooted:
            assert not (root / "run/reboot-required").exists()
            assert not packages.exists()
        else:
            assert (root / "run/reboot-required").is_file()
            assert packages.read_text() == original_packages
    commands = (root / "commands").read_text().splitlines()
    assert commands.count("notify-reboot-required ") == 1


@pytest.mark.parametrize("packages", ["linux-base\ndbus\n", "oh-no-parent-control-extra\n"])
def test_other_packages_do_not_trigger_kiosk_reboot_notice(package_machine, packages):
    root, _, run = package_machine
    (root / "run/reboot-required").write_text("*** System restart required ***\n")
    package_marker = root / "run/reboot-required.pkgs"
    package_marker.write_text(packages)
    result = run(IMPACTS="")
    assert result.returncode == 0, result.stderr
    assert REBOOT_NOTICE not in result.stderr
    assert (root / "run/reboot-required").is_file()
    assert package_marker.read_text() == packages
    assert "notify-reboot-required " not in (root / "commands").read_text().splitlines()


@pytest.mark.parametrize("policy_status,success,activated", [
    ("0", True, True), ("104", True, True), ("101", True, False),
    ("102", False, False), ("106", False, False),
])
def test_configuration_respects_service_policy(package_machine, policy_status, success, activated):
    root, state, run = package_machine
    result = run(POLICY_STATUS=policy_status)
    assert (result.returncode == 0) == success, result.stderr
    commands = (root / "commands").read_text()
    assert (f"systemctl --system restart {BROKER}" in commands) == activated
    assert (state / "package-activation-pending").exists() != success
    if policy_status == "101":
        assert "deferred by policy-rc.d" in result.stderr


def test_configuration_without_policy_helper_starts_broker(package_machine):
    root, _, run = package_machine
    (root / "usr/sbin/policy-rc.d").unlink()
    result = run()
    assert result.returncode == 0, result.stderr
    assert f"systemctl --system restart {BROKER}" in (root / "commands").read_text()


def test_startup_failure_preserves_activation_for_retry(package_machine):
    root, state, run = package_machine
    result = run(BROKER_STATUS="1", IMPACTS="session-renewal\nreboot")
    assert result.returncode != 0
    assert "broker activation failed" in result.stderr
    assert (state / "package-activation-pending").exists()
    assert (state / "previous-package-activation.json").exists()
    result = run(IMPACTS="session-renewal\nreboot")
    assert result.returncode == 0, result.stderr
    assert not (state / "package-activation-pending").exists()
    assert (root / "commands").read_text().count(f"systemctl --system restart {BROKER}") == 2
    assert (root / "run/reboot-required.pkgs").read_text().splitlines() == ["oh-no-parent-control"]
    assert (root / "commands").read_text().splitlines().count("notify-reboot-required ") == 1


@pytest.mark.parametrize("defer", ["0", "1"])
def test_reboot_notification_preserves_other_package_requests(package_machine, defer):
    root, _, run = package_machine
    (root / "run/reboot-required").write_text("*** System restart required ***\n")
    packages = root / "run/reboot-required.pkgs"
    packages.write_text("linux-base\ndbus\n")
    result = run(IMPACTS="reboot", NOTIFIER_DEFER=defer)
    assert result.returncode == 0, result.stderr
    assert packages.read_text().splitlines() == ["linux-base", "dbus", "oh-no-parent-control"]
    assert (root / "run/reboot-required").is_file()


def test_notification_failure_retains_comparison_for_retry(package_machine):
    root, state, run = package_machine
    result = run(IMPACTS="reboot", NOTIFIER_STATUS="1")
    assert result.returncode != 0
    assert (state / "package-activation-pending").exists()
    assert (state / "previous-package-activation.json").exists()
    result = run(IMPACTS="reboot")
    assert result.returncode == 0, result.stderr
    assert (root / "run/reboot-required.pkgs").read_text().splitlines() == ["oh-no-parent-control"]


def test_migration_failure_prevents_broker_activation(package_machine):
    root, state, run = package_machine
    result = run(MIGRATION_STATUS="1")
    assert result.returncode != 0
    assert (state / "migration-in-progress").exists()
    assert (state / "package-activation-pending").exists()
    assert f"systemctl --system start {BROKER}" not in (root / "commands").read_text()
    assert f"systemctl --system restart {BROKER}" not in (root / "commands").read_text()


def test_configure_without_pending_comparison_starts_broker(package_machine):
    root, state, run = package_machine
    (state / "package-activation-pending").unlink()
    result = run()
    assert result.returncode == 0, result.stderr
    assert f"systemctl --system start {BROKER}" in (root / "commands").read_text()
    assert not (root / "run/reboot-required").exists()


def test_debhelper_automatic_activation_is_disabled():
    result = subprocess.run(
        ["make", "-n", "-f", "debian/rules", "override_dh_installsystemd"],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "dh_installsystemd --no-start --no-stop-on-upgrade" in result.stdout


@pytest.mark.parametrize("profiles,expected", [("0 unix, malcontent", "enabled"), ("0 unix, systemd", "disabled")])
def test_original_pam_selection_is_saved_once(package_machine, profiles, expected):
    _, state, run = package_machine
    result = run(PAM_PROFILES=profiles)
    assert result.returncode == 0, result.stderr
    baseline = state / "malcontent-pam-before-install"
    assert baseline.read_text() == expected + "\n"
    result = run(PAM_PROFILES="0 unix")
    assert result.returncode == 0, result.stderr
    assert baseline.read_text() == expected + "\n"


def test_unowned_kiosk_is_rejected_before_any_configuration(package_machine):
    root, state, run = package_machine
    (state / "package-created-kiosk-uid").unlink()
    result = run()
    assert result.returncode != 0
    commands = (root / "commands").read_text()
    assert "usermod" not in commands
    assert not any(line.startswith("passwd ") for line in commands.splitlines())
    assert "migrate-state" not in commands


def test_local_pam_configuration_cannot_silently_skip_enforcement(package_machine):
    root, _, run = package_machine
    (root / "etc/pam.d/common-auth").write_text("auth required pam_unix.so\n")
    result = run(PAM_LOCAL_CHANGES="1")
    assert result.returncode != 0
    assert "PAM integration was not activated" in result.stderr
    assert f"systemctl --system restart {BROKER}" not in (root / "commands").read_text()


@pytest.mark.parametrize('fault', ['account-missing', 'account-optional', 'account-commented',
                                 'session-missing', 'session-optional', 'legacy-helper'])
def test_ubuntu_activation_requires_native_kiosk_stages_and_no_generic_python_gate(package_machine, fault):
    root, state, run = package_machine
    pam = root / 'etc/pam.d'
    sources = {
        'common-auth': 'auth required pam_oh_no_parent_control.so\n',
        'common-account': 'account required pam_oh_no_parent_control.so kiosk\n',
        'common-session': 'session required pam_oh_no_parent_control.so kiosk\n',
    }
    if fault == 'legacy-helper':
        sources['common-account'] += (
            f'account required pam_exec.so quiet {root}/usr/libexec/oh-no-parent-control-login-check\n')
    else:
        stage, variation = fault.split('-')
        name = 'common-' + stage
        sources[name] = ('' if variation == 'missing' else
                         sources[name].replace('required', 'optional') if variation == 'optional' else
                         '# ' + sources[name])
    for name, contents in sources.items():
        (pam / name).write_text(contents)
    result = run(PAM_LOCAL_CHANGES='1')
    assert result.returncode != 0
    assert 'PAM integration was not activated' in result.stderr
    assert (state / 'migration-in-progress').exists()
    assert {name: (pam / name).read_text() for name in sources} == sources
    assert f'systemctl --system start {BROKER}' not in (root / 'commands').read_text()
    assert f'systemctl --system restart {BROKER}' not in (root / 'commands').read_text()


def test_missing_generated_integrations_are_recreated_on_reinstall(package_machine):
    root, state, run = package_machine
    result = run()
    assert result.returncode == 0, result.stderr
    for target in ("etc/gdm3/PreSession/Default", "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules"):
        (root / target).unlink()
    result = run()
    assert result.returncode == 0, result.stderr
    assert (root / "etc/gdm3/PreSession/Default").read_bytes() == (state / "installed-gdm-presession").read_bytes()
    assert (root / "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules").read_bytes() == (state / "installed-fapolicyd-fallback").read_bytes()


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
def test_child_module_trust_install_upgrade_and_reinstall(package_machine):
    root, state, run = package_machine
    template = root / 'usr/share/oh-no-parent-control/child-extension.trust'
    target = root / 'etc/fapolicyd/trust.d/oh-no-parent-control.trust'
    record = state / 'installed-child-extension-trust'
    # Existing administrator trust and the distribution filter are never edited.
    admin = target.parent / 'administrator.trust'
    admin.parent.mkdir(parents=True)
    admin.write_text('administrator trust\n')
    filter_path = root / 'etc/fapolicyd/fapolicyd-filter.conf'
    filter_path.write_text('+ /\n - usr/share/\n  + *.js\n')
    for payload in ('first packaged hashes\n', 'replacement packaged hashes\n'):
        template.write_text(payload)
        result = run()
        assert result.returncode == 0, result.stderr
        assert target.read_text() == record.read_text() == payload
        assert target.stat().st_mode & 0o777 == 0o644
        assert record.stat().st_mode & 0o777 == 0o600
    target.unlink()
    assert run().returncode == 0
    assert target.read_bytes() == template.read_bytes()
    assert admin.read_text() == 'administrator trust\n'
    assert filter_path.read_text() == '+ /\n - usr/share/\n  + *.js\n'
    commands = (root / 'commands').read_text().splitlines()
    refresh = commands.index('fapolicyd-cli --update')
    ready = commands.index('oh-no-parent-control-package-activation wait-child-trust --refresh')
    assert ready < refresh < commands.index(f'systemctl --system restart {BROKER}')


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('failure', ['TRUST_UPDATE_STATUS', 'TRUST_READY_STATUS'])
def test_child_trust_refresh_failure_blocks_activation_and_is_retryable(package_machine, failure):
    root, state, run = package_machine
    result = run(**{failure: '7'})
    assert result.returncode == 7
    assert (state / 'package-activation-pending').exists()
    assert (state / 'migration-in-progress').exists()
    assert f'systemctl --system restart {BROKER}' not in (root / 'commands').read_text()
    assert run().returncode == 0
    assert not (state / 'package-activation-pending').exists()
    assert not (state / 'migration-in-progress').exists()


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('state', ['inactive', 'failed', 'active', 'activating', 'deactivating'])
def test_canceled_stop_requires_confirmed_broker_exit_before_migration(package_machine, state):
    root, saved, run = package_machine
    (root / 'broker-active').touch()
    result = run(BROKER_STOP_STATUS='1', BROKER_STOP_STATE=state)
    stopped = state in ('inactive', 'failed')
    assert (result.returncode == 0) == stopped, result.stderr
    commands = (root / 'commands').read_text()
    assert ('oh-no-parent-control-migrate-state ' in commands) == stopped
    assert (saved / 'migration-in-progress').exists() != stopped
    assert (f'systemctl --system restart {BROKER}' in commands) == stopped


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('stop_refused', [False, True])
def test_reconfigure_guards_and_stops_an_existing_broker(package_machine, stop_refused):
    root, state, run = package_machine
    (state / 'migration-in-progress').unlink()
    (root / 'broker-active').touch()
    result = run(BROKER_STOP_REFUSED=str(int(stop_refused)))
    commands = (root / 'commands').read_text()
    if stop_refused:
        assert result.returncode != 0
        assert (state / 'migration-in-progress').exists()
        assert 'oh-no-parent-control-migrate-state ' not in commands
        assert 'wait-child-trust' not in commands
    else:
        assert result.returncode == 0, result.stderr
        assert not (state / 'migration-in-progress').exists()
        assert commands.index(f'stop {BROKER}') < commands.index('oh-no-parent-control-migrate-state ')


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
def test_dbus_startup_exclusion_survives_until_trust_is_ready(package_machine):
    root, state, run = package_machine
    # Model a concurrent activation at the actual readiness boundary using the
    # two shipped startup checks, without a host bus or installed service.
    launcher = root / 'broker-launcher'
    source = (ROOT / 'broker/oh-no-parent-control-broker').read_text()
    source = source.replace('/var/lib/oh-no-parent-control', str(state))
    source = source.replace('/run/oh-no-parent-control-child-trust-reboot',
                            str(root / 'run/oh-no-parent-control-child-trust-reboot'))
    launcher.write_text(source.split('# Check trust', 1)[0] + 'raise SystemExit(0)\n')
    unit = (ROOT / 'data/systemd/oh-no-parent-control-broker.service').read_text()
    assert 'ConditionPathExists=!/var/lib/oh-no-parent-control/migration-in-progress' in unit
    helper = root / 'usr/libexec/oh-no-parent-control-package-activation'
    helper.unlink()
    helper.write_text(f'''#!{sys.executable}
import pathlib, subprocess, sys
if sys.argv[1] == 'wait-child-trust':
    assert pathlib.Path({str(state / 'migration-in-progress')!r}).is_file()
    result = subprocess.run([{sys.executable!r}, {str(launcher)!r}], capture_output=True)
    assert result.returncode != 0
    assert b'saved-data migration is incomplete' in result.stderr
elif sys.argv[1] == 'prepare-child-trust-backend':
    print('none')
else:
    print('process-restart')
''')
    helper.chmod(0o755)
    result = run()
    assert result.returncode == 0, result.stderr
    assert subprocess.run([sys.executable, str(launcher)], capture_output=True).returncode == 0


@pytest.mark.parametrize('active', [False, True])
def test_backend_change_preserves_active_desktops_and_configuration_guard(package_machine, active):
    root, state, run = package_machine
    result = run(TRUST_BACKEND_ACTION='changed', FAPOLICYD_ACTIVE_STATUS='0' if active else '3')
    commands = (root / 'commands').read_text()
    assert 'restart fapolicyd.service' not in commands
    assert result.returncode == 0, result.stderr
    assert not (state / 'migration-in-progress').exists()
    assert not (state / 'package-activation-pending').exists()
    if active:
        assert 'activation deferred until reboot' in result.stderr
        guard = root / 'run/oh-no-parent-control-child-trust-reboot'
        assert guard.is_file()
        assert guard.stat().st_mode & 0o777 == 0o600
        assert (root / 'run/reboot-required').exists()
        assert (root / 'run/reboot-required.pkgs').read_text().splitlines() == ['oh-no-parent-control']
        assert REBOOT_NOTICE in result.stderr
        assert 'wait-child-trust' not in commands
        assert f'systemctl --system restart {BROKER}' not in commands
        assert f'systemctl --system start {BROKER}' not in commands
        # An unchanged same-boot reconfigure must retain the activation guard.
        assert run().returncode == 0
        assert guard.exists()
        assert (root / 'run/reboot-required.pkgs').read_text().splitlines() == ['oh-no-parent-control']
    else:
        # This double keeps the daemon stopped after the package-service call.
        assert 'deb-systemd-invoke start fapolicyd.service' in commands
        assert not (root / 'run/oh-no-parent-control-child-trust-reboot').exists()


def test_backend_acknowledgement_failure_blocks_activation(package_machine):
    root, state, run = package_machine
    result = run(TRUST_COMPLETE_STATUS='7')
    assert result.returncode == 7
    assert (state / 'migration-in-progress').exists()
    assert (state / 'package-activation-pending').exists()
    assert f'systemctl --system restart {BROKER}' not in (root / 'commands').read_text()
    assert run().returncode == 0


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('active', [False, True])
def test_real_backend_upgrade_completes_and_broker_guard_expires_on_reboot(package_machine, legacy, active):
    root, state, run = package_machine
    # The real helper also compares manifests. Give it valid equal manifests
    # so only the backend transition can require a reboot in this scenario.
    manifest = json.dumps({'version': 1, 'files': []})
    (state / 'previous-package-activation.json').write_text(manifest)
    (root / 'usr/share/oh-no-parent-control/package-activation.json').write_text(manifest)
    config = root / 'etc/fapolicyd/fapolicyd.conf'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('trust = debdb\n')
    receipt = state / 'child-trust-backend'
    if legacy:
        receipt.mkdir()
        (receipt / 'before').write_bytes(config.read_bytes())
        config.write_text('trust = debdb,file\n')
        (receipt / 'after').write_bytes(config.read_bytes())
    boot = root / 'boot-id'
    boot.write_text('11111111-1111-1111-1111-111111111111\n')
    helper = root / 'usr/libexec/oh-no-parent-control-package-activation'
    helper.unlink()
    source = (ROOT / 'packaging/package_activation.py').read_text()
    source = source.replace('/etc/fapolicyd/fapolicyd.conf', str(config))
    source = source.replace('/var/lib/oh-no-parent-control/child-trust-backend', str(receipt))
    source = source.replace('/proc/sys/kernel/random/boot_id', str(boot))
    # Only the live database is doubled; configuration and receipts run for real.
    source = source.replace('    args = parser.parse_args()',
        '    args = parser.parse_args()\n'
        '    if args.command == "wait-child-trust":\n'
        '        import os\n'
        '        if args.refresh:\n'
        '            subprocess.run([os.environ["AUDIT_ROOT"] + "/usr/sbin/fapolicyd-cli", "--update"], check=True)\n'
        '        raise SystemExit(int(os.environ.get("TRUST_READY_STATUS", "0")))')
    helper.write_text(f'#!{sys.executable}\n' + source.split('\n', 1)[1])
    helper.chmod(0o755)
    launcher = root / 'broker-launcher'
    source = (ROOT / 'broker/oh-no-parent-control-broker').read_text()
    source = source.replace('/var/lib/oh-no-parent-control', str(state))
    guard = root / 'run/oh-no-parent-control-child-trust-reboot'
    source = source.replace('/run/', str(root / 'run') + '/')
    source = source.replace('/usr/libexec/oh-no-parent-control-package-activation', str(helper))
    launcher.write_text(source.split('sys.path.insert', 1)[0] +
                        'print("diagnostics-only" if diagnostics_only else "policy-ready")\n')
    for _ in range(2):
        result = run(IMPACTS='', FAPOLICYD_ACTIVE_STATUS='0' if active else '3',
                     FAPOLICYD_STARTS='1')
        assert result.returncode == 0, result.stderr
        assert 'PASS:' in result.stdout
        assert guard.exists() == active
        blocked = subprocess.run([sys.executable, str(launcher)], capture_output=True)
        if active:
            assert blocked.returncode == 0, blocked.stderr
            assert blocked.stdout.strip() == b'diagnostics-only'
        else:
            assert blocked.returncode == 0, blocked.stderr
            assert blocked.stdout.strip() == b'policy-ready'
            assert (receipt / 'activation').read_text() == 'ready\n'
            commands = (root / 'commands').read_text()
            assert f'systemctl --system start {BROKER}' in commands
            assert 'fapolicyd-cli --update' in commands
            assert not (root / 'run/reboot-required').exists()
    # Reboot clears volatile state; successful postinst already released migration.
    assert not (state / 'migration-in-progress').exists()
    if active:
        guard.unlink()
    boot.write_text('22222222-2222-2222-2222-222222222222\n')
    assert subprocess.run([sys.executable, str(launcher)], capture_output=True).returncode == 0
    # Expiring the guard is insufficient if live exact trust is still missing.
    import os
    blocked = subprocess.run([sys.executable, str(launcher)], capture_output=True,
                             env={**os.environ, 'TRUST_READY_STATUS': '7'})
    assert blocked.returncode != 0
    assert b'child trust database is not ready' in blocked.stderr
    result = run(IMPACTS='')
    assert result.returncode == 0, result.stderr
    assert (receipt / 'activation').read_text() == 'ready\n'
    assert not guard.exists()
    # An unrelated OS update must not put this broker into diagnostics-only mode.
    (root / 'run/reboot-required').write_text('System restart required\n')
    (root / 'run/reboot-required.pkgs').write_text('linux-image-generic\nlibc6\n')
    allowed = subprocess.run([sys.executable, str(launcher)], capture_output=True)
    assert allowed.returncode == 0, allowed.stderr
    assert allowed.stdout.strip() == b'policy-ready'


def test_deferred_backend_notifier_failure_remains_retryable(package_machine):
    root, state, run = package_machine
    result = run(TRUST_BACKEND_ACTION='changed', NOTIFIER_STATUS='7')
    assert result.returncode == 7
    assert (state / 'migration-in-progress').exists()
    assert (state / 'package-activation-pending').exists()
    assert (root / 'run/oh-no-parent-control-child-trust-reboot').exists()
    assert run().returncode == 0


def test_substituted_deferred_backend_guard_is_preserved(package_machine):
    root, state, run = package_machine
    sentinel = root / 'sentinel'
    sentinel.write_text('preserve\n')
    (root / 'run/oh-no-parent-control-child-trust-reboot').symlink_to(sentinel)
    result = run(TRUST_BACKEND_ACTION='changed')
    assert result.returncode != 0
    assert sentinel.read_text() == 'preserve\n'
    assert (state / 'migration-in-progress').exists()


def test_deferred_daemon_start_does_not_request_trust_refresh(package_machine):
    root, _, run = package_machine
    assert run(FAPOLICYD_ACTIVE_STATUS='3', POLICY_STATUS='101').returncode == 0
    assert 'fapolicyd-cli --update' not in (root / 'commands').read_text()
    assert (root / 'etc/fapolicyd/trust.d/oh-no-parent-control.trust').is_file()


@pytest.mark.parametrize('substitution', ['modified', 'target-link', 'directory-link', 'record-link'])
def test_child_trust_configuration_preserves_modified_or_substituted_paths(package_machine, substitution):
    root, state, run = package_machine
    assert run().returncode == 0
    target = root / 'etc/fapolicyd/trust.d/oh-no-parent-control.trust'
    record = state / 'installed-child-extension-trust'
    sentinel = root / 'sentinel'
    sentinel.write_text('keep administrator content\n')
    if substitution == 'modified':
        target.write_bytes(sentinel.read_bytes())
    elif substitution == 'target-link':
        target.unlink()
        target.symlink_to(sentinel)
    elif substitution == 'record-link':
        record.unlink()
        record.symlink_to(sentinel)
    else:
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(sentinel.parent)
    assert run().returncode != 0
    assert sentinel.read_text() == 'keep administrator content\n'


def _prepared_pam_migration_runtime(root, monkeypatch, distribution, migration, *, formatting=None):
    """Real prepared verifier over private native payload/shared PAM output."""
    import importlib.util
    from types import SimpleNamespace
    from tools.test_storage import scratch_descriptors

    prepared = ROOT / 'data/kiosk-runtime-unselected'
    source = prepared / 'distro_pam.py'
    spec = importlib.util.spec_from_file_location('prepared_pam_migration_distro', source)
    helper = importlib.util.module_from_spec(spec)
    exec(compile(source.read_bytes(), str(source), 'exec'), helper.__dict__)
    monkeypatch.setattr(helper, 'PAM', migration.PAM)
    payload = root / 'prepared-runtime'
    payload.mkdir()
    module = payload / 'pam_oh_no_parent_control.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                    '-o', str(module), str(prepared / 'pam_oh_no_parent_control.c'), '-lpam'],
                   check=True, capture_output=True, text=True, timeout=30, pass_fds=scratch_descriptors())
    module.chmod(0o644)
    login = payload / 'login-check'
    login.write_bytes((prepared / 'login_check.py').read_bytes())
    login.chmod(0o755)
    time_check = payload / 'time-check'
    time_check.write_bytes((ROOT / 'tools/session_limit_check.py').read_bytes())
    time_check.chmod(0o755)
    monkeypatch.setattr(helper, 'MODULES', {distribution: module})
    monkeypatch.setattr(helper, 'LOGIN_CHECK', login)
    monkeypatch.setattr(helper, 'TIME_CHECK', time_check)
    original_stat = Path.stat

    def payload_stat(path, **options):
        info = original_stat(path, **options)
        # Only root ownership is doubled, only for these three installed files.
        if path in (module, login, time_check):
            return SimpleNamespace(st_mode=info.st_mode, st_uid=0)
        return info

    monkeypatch.setattr(helper.Path, 'stat', payload_stat)
    profile_root = root / 'prepared-profile-source'
    profiles = profile_root / 'data/pam-configs'
    profiles.mkdir(parents=True)
    for name in ('oh-no-parent-control-kiosk-only', 'oh-no-parent-control-session-limits'):
        (profiles / name).write_bytes((prepared / 'pam-configs' / name).read_bytes())
    stage_source = ROOT / 'packaging/stage_distribution.py'
    stage = {'__name__': 'prepared_migration_pam_stage'}
    exec(compile(stage_source.read_bytes(), str(stage_source), 'exec'), stage)
    stack = stage['pam_stack'](profile_root)
    vendor = '# native vendor callbacks remain\naccount required pam_unix.so\n'
    for name in helper.FILES[distribution]:
        if distribution == 'fedora':
            entries = stack
        else:
            kind = {'common-auth': 'auth', 'common-account': 'account',
                    'common-session': 'session', 'common-session-noninteractive': 'session'}.get(name)
            entries = ''.join(line.replace('ingroup wheel', 'ingroup sudo') + '\n'
                              for line in stack.splitlines() if kind and line.startswith(kind + ' '))
        contents = entries + vendor
        if formatting:
            formatted = []
            for row in contents.splitlines():
                if row and not row.startswith('#'):
                    if formatting in ('continuation', 'both'):
                        kind, _separator, rest = row.partition(' ')
                        row = kind + ' \\\n\t' + rest.replace(' pam_', ' \\\n  pam_', 1)
                    if formatting in ('inline-comment', 'both'):
                        row += ' # local formatting'
                formatted.append(row)
            contents = '\n'.join(formatted) + '\n'
        (migration.PAM / name).write_text(contents)
    return helper


@pytest.mark.parametrize('distribution,backend', [('ubuntu', 'apparmor'), ('fedora', 'selinux')])
@pytest.mark.parametrize('fault', [None, 'shared-pam', 'required-helper', 'missing-malcontent',
                                   'missing-cap', 'missing-bridge', 'missing-auth-admin-skip',
                                   'missing-account-kiosk-skip', 'reordered-account-skips', 'reordered-cap'])
def test_prepared_pam_migration_real_readiness_composes_and_retries(
        tmp_path, monkeypatch, distribution, backend, fault):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    saved = migration.state()
    migration.prepare()
    migration.restore_original_pam()
    originals = {name: (migration.PAM / name).read_bytes() if (migration.PAM / name).exists() else None
                 for name in migration.SERVICES}
    helper = _prepared_pam_migration_runtime(tmp_path, monkeypatch, distribution, migration)
    runtime_ready = lambda: helper.runtime_ready(distribution)
    if fault:
        kind = 'auth' if fault == 'missing-auth-admin-skip' else 'account'
        path = helper.LOGIN_CHECK if fault == 'required-helper' else migration.PAM / (
            f'common-{kind}' if distribution == 'ubuntu' else 'password-auth')
        before = path.read_bytes()
        if fault in ('shared-pam', 'required-helper'):
            path.unlink()
        else:
            rows = before.decode().splitlines()
            expected = helper.time_policy(distribution)[kind]
            if fault.startswith('missing-'):
                index = {'missing-malcontent': 4, 'missing-cap': 5, 'missing-bridge': 3,
                         'missing-auth-admin-skip': 1, 'missing-account-kiosk-skip': 1}[fault]
                rows.remove(expected[index])
            else:
                left, right = (0, 1) if fault == 'reordered-account-skips' else (4, 5)
                first, second = rows.index(expected[left]), rows.index(expected[right])
                rows[first], rows[second] = rows[second], rows[first]
            path.write_text('\n'.join(rows) + '\n')
        state = migration.STATE.read_bytes()
        with pytest.raises((OSError, ValueError)):
            migration.commit_migration(runtime_ready)
        assert migration.STATE.read_bytes() == state and migration.DISABLED.exists()
        assert machine.expires == 1 and migration.expiry_record(1006)['phase'] == 'quarantined'
        path.write_bytes(before)
        path.chmod(0o755 if fault == 'required-helper' else 0o644)
    migration.commit_migration(runtime_ready)
    migration.release_account()
    assert machine.expires is None
    assert not migration.STATE.exists() and not migration.DISABLED.exists() and not migration.EXPIRY.exists()
    assert migration.OWNERSHIP.read_text() == '1006\n'
    migration.verify_pam(saved, originals=True)
    assert originals == {name: (migration.PAM / name).read_bytes() if (migration.PAM / name).exists() else None
                         for name in migration.SERVICES}


@pytest.mark.parametrize('distribution,backend', [('ubuntu', 'apparmor'), ('fedora', 'selinux')])
@pytest.mark.parametrize('fault', ['required-helper', 'missing-malcontent', 'reordered-cap'])
def test_prepared_pam_migration_failed_real_readiness_preserves_legacy_rollback(
        tmp_path, monkeypatch, distribution, backend, fault):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    saved = migration.state()
    migration.prepare()
    migration.restore_original_pam()
    helper = _prepared_pam_migration_runtime(tmp_path, monkeypatch, distribution, migration)
    if fault == 'required-helper':
        helper.LOGIN_CHECK.unlink()
    else:
        path = migration.PAM / ('common-account' if distribution == 'ubuntu' else 'system-auth')
        rows = path.read_text().splitlines()
        expected = helper.time_policy(distribution)['account']
        if fault == 'missing-malcontent':
            rows.remove(expected[4])
        else:
            first, second = rows.index(expected[4]), rows.index(expected[5])
            rows[first], rows[second] = rows[second], rows[first]
        path.write_text('\n'.join(rows) + '\n')
    with pytest.raises((OSError, ValueError)):
        migration.commit_migration(lambda: helper.runtime_ready(distribution))
    migration.rollback()
    assert machine.loaded and machine.expires is None
    assert migration.state() == saved
    assert not migration.DISABLED.exists() and not migration.EXPIRY.exists()
    assert all((migration.PAM / name).read_text() == record['after'] for name, record in saved['pam'].items())


@pytest.mark.parametrize('distribution,backend', [('ubuntu', 'apparmor'), ('fedora', 'selinux')])
@pytest.mark.parametrize('formatting', ['continuation', 'inline-comment', 'both'])
def test_prepared_pam_migration_accepts_equivalent_logical_lines(
        tmp_path, monkeypatch, distribution, backend, formatting):
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch, backend)
    migration = machine.migration
    migration.prepare()
    migration.restore_original_pam()
    helper = _prepared_pam_migration_runtime(tmp_path, monkeypatch, distribution, migration, formatting=formatting)
    originals = {name: (migration.PAM / name).read_bytes() if (migration.PAM / name).exists() else None
                 for name in migration.SERVICES}
    shared = {name: (migration.PAM / name).read_bytes() for name in helper.FILES[distribution]}
    migration.commit_migration(lambda: helper.runtime_ready(distribution))
    migration.release_account()
    assert machine.expires is None
    assert not migration.STATE.exists() and not migration.DISABLED.exists() and not migration.EXPIRY.exists()
    assert originals == {name: (migration.PAM / name).read_bytes() if (migration.PAM / name).exists() else None
                         for name in migration.SERVICES}
    assert shared == {name: (migration.PAM / name).read_bytes() for name in helper.FILES[distribution]}
