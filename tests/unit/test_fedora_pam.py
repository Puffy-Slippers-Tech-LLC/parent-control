"""Authselect ownership and restoration with private paths and command doubles."""
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
import stat
import sys
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT


@pytest.fixture
def pam_machine(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('onpc_fedora_pam', ROOT / 'packaging/fedora_pam.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    for key, relative in (
        ('PROFILE_DIR', 'etc/authselect/custom/oh-no-parent-control'),
        ('STATE', 'var/lib/oh-no-parent-control/fedora-authselect.json'),
        ('STACK', 'usr/share/oh-no-parent-control/pam/managed-stack'),
        ('PAM_DIR', 'etc/pam.d'),
    ):
        monkeypatch.setattr(helper, key, tmp_path / relative)
    helper.STATE.parent.mkdir(parents=True)
    helper.STACK.parent.mkdir(parents=True)
    helper.PAM_DIR.mkdir(parents=True)
    source = ROOT / 'packaging/stage_distribution.py'
    stage_spec = importlib.util.spec_from_file_location('fixture_pam_stage', source)
    stage = importlib.util.module_from_spec(stage_spec)
    exec(compile(source.read_bytes(), str(source), 'exec'), stage.__dict__)
    profiles = tmp_path / 'data/pam-configs'
    profiles.mkdir(parents=True)
    for name in ('oh-no-parent-control-kiosk-only', 'oh-no-parent-control-session-limits'):
        (profiles / name).write_bytes(
            (ROOT / 'data/pam-configs' / name).read_bytes())
    helper.STACK.write_text(stage.pam_stack(tmp_path))
    original = 'auth sufficient pam_unix.so nullok\naccount required pam_unix.so\n'
    for name in helper.PAM_FILES:
        (helper.PAM_DIR / name).write_text(original)
    current = ['local', 'with-fingerprint', 'with-faillock']
    commands = []

    def fixture_secure(path, *, directory=False):
        # Simulate root ownership in this unprivileged tree; retain the real
        # no-link/type checks. No global paths or authselect command is used.
        assert path.is_relative_to(tmp_path)
        if path.is_symlink() or not (path.is_dir() if directory else path.is_file()):
            raise ValueError('unsafe fixture ownership or substituted path')

    def run(*arguments, capture=False):
        commands.append(arguments)
        if arguments[0] == 'current':
            return SimpleNamespace(stdout=' '.join(current) + '\n')
        if arguments[0] == 'create-profile':
            helper.PROFILE_DIR.mkdir(parents=True)
            for name in helper.PAM_FILES:
                (helper.PROFILE_DIR / name).write_text(original)
            (helper.PROFILE_DIR / 'README').write_text('fixture')
        elif arguments[0] == 'select':
            current[:] = arguments[1:]
            for name in helper.PAM_FILES:
                contents = (helper.PROFILE_DIR / name).read_text() if current[0] == helper.PROFILE else original
                (helper.PAM_DIR / name).write_text(contents)
        return SimpleNamespace(stdout='')

    monkeypatch.setattr(helper, 'secure', fixture_secure)
    monkeypatch.setattr(helper, 'run', run)
    return helper, current, commands


def test_install_retry_and_remove_restore_original_profile_features(pam_machine):
    helper, current, commands = pam_machine
    original = current.copy()
    helper.configure('install')
    assert current == [helper.PROFILE, *original[1:]]
    before = helper.digests()
    helper.configure('install')
    assert helper.digests() == before
    assert [cmd[0] for cmd in commands].count('create-profile') == 1
    helper.configure('remove')
    assert current == original
    assert not helper.PROFILE_DIR.exists()
    helper.configure('remove')
    helper.configure('install')
    assert current == [helper.PROFILE, *original[1:]]
    assert all('--force' not in cmd for cmd in commands)


def test_upgrade_replaces_only_owned_managed_stack_and_keeps_original_profile(pam_machine):
    helper, current, commands = pam_machine
    helper.configure('install')
    original = {name: (helper.PROFILE_DIR / name).read_text().split(helper.END, 1)[1]
                for name in helper.PAM_FILES}
    helper.STACK.write_text(helper.STACK.read_text() + '# updated shipped policy\n')
    helper.configure('install')
    for name in helper.PAM_FILES:
        contents = (helper.PROFILE_DIR / name).read_text()
        assert '# updated shipped policy\n' in contents
        assert contents.split(helper.END, 1)[1] == original[name]
        assert contents.count(helper.BEGIN) == contents.count(helper.END) == 1
    assert [cmd[0] for cmd in commands].count('create-profile') == 1


def test_upgrade_removes_recorded_legacy_helper_and_preserves_vendor_profile(pam_machine):
    helper, current, _commands = pam_machine
    helper.configure('install')
    original = {}
    for name in helper.PAM_FILES:
        path = helper.PROFILE_DIR / name
        contents = path.read_text()
        original[name] = contents.split(helper.END, 1)[1]
        path.write_text(contents.replace(helper.BEGIN, helper.BEGIN +
                        'account required pam_exec.so quiet /usr/libexec/oh-no-parent-control-login-check\n'))
    record = json.loads(helper.STATE.read_text())
    record['files'] = helper.digests()
    helper.save(record)
    helper.run('select', *current)
    with pytest.raises(ValueError, match='integration does not match'):
        helper.verify_pam(installed=True)
    helper.configure('install')
    for name in helper.PAM_FILES:
        contents = (helper.PAM_DIR / name).read_text()
        assert 'oh-no-parent-control-login-check' not in contents
        assert contents.split(helper.END, 1)[1] == original[name]
    helper.configure('remove')
    assert current[0] == 'local'


@pytest.mark.parametrize('kind', ['account', 'session'])
def test_verification_requires_both_kiosk_admission_stages(pam_machine, kind):
    helper, _current, _commands = pam_machine
    helper.configure('install')
    path = helper.PAM_DIR / 'system-auth'
    path.write_text(path.read_text().replace(
        f'{kind} required pam_oh_no_parent_control.so kiosk\n', ''))
    with pytest.raises(ValueError, match='integration does not match'):
        helper.verify_pam(installed=True)


@pytest.mark.parametrize('action', ['install', 'remove'])
def test_modified_owned_profile_is_preserved_and_selection_unchanged(pam_machine, action):
    helper, current, commands = pam_machine
    helper.configure('install')
    modified = helper.PROFILE_DIR / 'system-auth'
    modified.write_text('administrator replacement\n')
    original = current.copy()
    commands.clear()
    with pytest.raises(ValueError, match='profile changed'):
        helper.configure(action)
    assert current == original
    assert modified.read_text() == 'administrator replacement\n'
    assert not any(cmd[0] == 'select' for cmd in commands)


@pytest.mark.parametrize('collision', ['directory', 'symlink'])
def test_unowned_custom_profile_collision_precedes_mutation(pam_machine, collision):
    helper, current, commands = pam_machine
    helper.PROFILE_DIR.parent.mkdir(parents=True)
    if collision == 'directory':
        helper.PROFILE_DIR.mkdir()
    else:
        helper.PROFILE_DIR.symlink_to(helper.PAM_DIR, target_is_directory=True)
    with pytest.raises(ValueError, match='reserved authselect profile'):
        helper.configure('install')
    assert current[0] == 'local'
    assert not helper.STATE.exists()
    assert not any(cmd[0] in ('select', 'create-profile') for cmd in commands)


def test_changed_selected_profile_is_not_overwritten(pam_machine):
    helper, current, commands = pam_machine
    helper.configure('install')
    current[:] = ['sssd']
    commands.clear()
    with pytest.raises(ValueError, match='selection changed'):
        helper.configure('remove')
    assert current == ['sssd']
    assert not any(cmd[0] == 'select' for cmd in commands)


def test_nullok_policy_is_not_weakened(pam_machine):
    helper, current, commands = pam_machine
    current.append('without-nullok')
    with pytest.raises(ValueError, match='disallows the passwordless kiosk'):
        helper.configure('install')
    assert not helper.STATE.exists()
    assert not any(cmd[0] in ('create-profile', 'select') for cmd in commands)


def test_dangling_ownership_record_is_rejected(pam_machine):
    helper, current, commands = pam_machine
    helper.STATE.symlink_to(helper.STATE.parent / 'missing')
    with pytest.raises(ValueError, match='substituted path'):
        helper.configure('install')
    assert not any(cmd[0] in ('create-profile', 'select') for cmd in commands)


@pytest.fixture
def prepared_fedora(pam_machine, monkeypatch):
    """Compose the prepared caller with authselect and the private policy store."""
    authselect, current, commands = pam_machine
    source = ROOT / 'packaging/distro_pam.py'
    spec = importlib.util.spec_from_file_location('prepared_fedora_distro', source)
    prepared = importlib.util.module_from_spec(spec)
    exec(compile(source.read_bytes(), str(source), 'exec'), prepared.__dict__)
    monkeypatch.setattr(prepared, 'PAM', authselect.PAM_DIR)
    monkeypatch.setattr(prepared, 'SSH_POLICY', authselect.STACK.with_name('onpc-ssh-accounts.cil'))
    monkeypatch.setattr(prepared, 'SSH_POLICY_RECEIPT', authselect.STATE.with_name('ssh-policy.json'))
    prepared.SSH_POLICY.write_bytes((ROOT / 'data/pam-configs/onpc-ssh-accounts.cil').read_bytes())
    policy = SimpleNamespace(active=True, installed=None, loaded=None, foreign=False,
                             fail_after_publish=False,
                             native_transaction=prepared.ssh_policy_transaction)

    def secure_policy_path(path, *, directory=False):
        path.lstat()  # Preserve FileNotFoundError for the first configuration.
        authselect.secure(path, directory=directory)

    monkeypatch.setattr(prepared, 'secure_ssh_policy_path', secure_policy_path)
    monkeypatch.setattr(prepared, 'ssh_policy_store_active', lambda: policy.active)

    @contextmanager
    def policy_transaction(*, writable, reload):
        draft = policy.installed

        def install(data):
            nonlocal draft
            assert writable
            commands.append(('policy-install',))
            draft = 'sha256:' + hashlib.sha256(data).hexdigest()

        def remove():
            nonlocal draft
            assert writable and draft is not None
            commands.append(('policy-remove',))
            draft = None

        def commit():
            assert writable
            policy.installed = draft
            if policy.fail_after_publish:
                policy.fail_after_publish = False
                raise OSError('test policy commit interrupted after store publication')
            if reload:
                policy.loaded = draft

        yield SimpleNamespace(inventory=lambda: (draft, policy.foreign), install=install,
                              remove=remove, commit=commit)

    monkeypatch.setattr(prepared, 'ssh_policy_transaction', policy_transaction)

    def run(arguments, *, input=None):
        assert input is None
        assert arguments[0] == str(prepared.FEDORA_HELPER)
        assert arguments[1] in ('install', 'remove')
        authselect.configure(arguments[1])

    monkeypatch.setattr(prepared, 'run', run)
    return prepared, authselect, current, commands, policy


def test_prepared_fedora_transaction_preserves_profile_features_and_rolls_back(prepared_fedora):
    prepared, authselect, current, commands, policy = prepared_fedora
    original = current.copy()
    prepared.configure('fedora', 'install')
    assert current == [authselect.PROFILE, *original[1:]]
    assert policy.loaded == policy.installed and policy.loaded is not None
    install = ('policy-install',)
    assert commands.index(install) < commands.index(('select', *current))
    prepared.configure('fedora', 'restore')
    assert commands.count(install) == 1
    prepared.configure('fedora', 'remove')
    assert current == original
    assert not authselect.PROFILE_DIR.exists()
    remove = ('policy-remove',)
    assert commands.index(('select', *original)) < commands.index(remove)
    assert policy.loaded is policy.installed is None
    prepared.configure('fedora', 'remove')
    assert commands.count(remove) == 1
    prepared.configure('fedora', 'install')
    assert current == [authselect.PROFILE, *original[1:]]


def test_prepared_fedora_respects_explicit_passwordless_denial(prepared_fedora):
    prepared, authselect, current, commands, _policy = prepared_fedora
    current.append('without-nullok')
    with pytest.raises(ValueError, match='disallows the passwordless kiosk'):
        prepared.configure('fedora', 'install')
    assert not authselect.STATE.exists()
    assert not any(command[0] in ('create-profile', 'select') for command in commands)


def test_prepared_fedora_owned_profile_edit_is_preserved_for_restore_and_remove(prepared_fedora):
    prepared, authselect, current, _commands, _policy = prepared_fedora
    prepared.configure('fedora', 'install')
    profile = authselect.PROFILE_DIR / 'system-auth'
    profile.write_text('administrator replacement\n')
    selected = current.copy()
    for action in ('restore', 'remove'):
        with pytest.raises(ValueError, match='profile changed'):
            prepared.configure('fedora', action)
        assert profile.read_text() == 'administrator replacement\n'
        assert current == selected


def test_prepared_fedora_preserves_replaced_selinux_module(prepared_fedora):
    prepared, _authselect, current, commands, policy = prepared_fedora
    prepared.configure('fedora', 'install')
    replacement = 'sha256:' + 'a' * 64
    policy.installed = replacement
    selected = current.copy()
    for action in ('restore', 'remove'):
        commands.clear()
        with pytest.raises(ValueError, match='unknown ownership'):
            prepared.configure('fedora', action)
        assert current == selected
        assert policy.installed == replacement
        assert not any(command[0] in ('select', 'policy-install', 'policy-remove')
                       for command in commands)


def test_prepared_fedora_does_not_shadow_an_existing_selinux_module(prepared_fedora):
    prepared, authselect, current, commands, policy = prepared_fedora
    policy.foreign = True
    with pytest.raises(ValueError, match='SSH SELinux policy'):
        prepared.configure('fedora', 'install')
    assert current[0] != authselect.PROFILE
    assert policy.installed is None and policy.foreign
    assert ('policy-install',) not in commands


def test_prepared_fedora_reloads_after_interrupted_policy_publication(prepared_fedora):
    prepared, authselect, current, _commands, policy = prepared_fedora
    original = current.copy()
    policy.fail_after_publish = True
    with pytest.raises(OSError, match='interrupted after store publication'):
        prepared.configure('fedora', 'install')
    assert policy.installed is not None and policy.loaded is None
    assert current == original
    prepared.configure('fedora', 'install')
    assert policy.loaded == policy.installed
    assert current[0] == authselect.PROFILE

    policy.fail_after_publish = True
    with pytest.raises(OSError, match='interrupted after store publication'):
        prepared.configure('fedora', 'remove')
    assert policy.installed is None and policy.loaded is not None
    assert current == original
    prepared.configure('fedora', 'remove')
    assert policy.loaded is None
    assert not prepared.SSH_POLICY_RECEIPT.exists()


def test_prepared_fedora_removes_policy_from_its_original_store(prepared_fedora):
    prepared, _authselect, current, _commands, policy = prepared_fedora
    original = current.copy()
    prepared.configure('fedora', 'install')
    # The now-active local store also has a module with the same digest.
    active_local_policy = policy.installed
    policy.active = False
    prepared.configure('fedora', 'remove')
    assert current == original
    assert policy.installed is None
    assert policy.loaded == active_local_policy
    assert not prepared.SSH_POLICY_RECEIPT.exists()


def test_prepared_fedora_never_opens_an_alternate_selinux_store_root(prepared_fedora, tmp_path, monkeypatch):
    prepared, _authselect, current, _commands, policy = prepared_fedora
    prepared.configure('fedora', 'install')
    selected = current.copy()
    original_policy = policy.installed

    source = ROOT / 'packaging/fedora_selinux.py'
    spec = importlib.util.spec_from_file_location('fedora_selinux', source)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    monkeypatch.setitem(sys.modules, 'fedora_selinux', adapter)
    config = tmp_path / 'semanage.conf'
    monkeypatch.setattr(adapter, 'SEMANAGE_CONFIG', config)
    monkeypatch.setattr(adapter, 'semanage', lambda: pytest.fail('opened an alternate policy store'))
    monkeypatch.setattr(prepared, 'ssh_policy_transaction', policy.native_transaction)
    for contents in ('store-root = "/alternate/selinux"\n',
                     'module-store = policy.example\n',
                     'module-store # administrator setting\n= policy.example\n',
                     'store-root = "/var/lib/selinux" \n',
                     'module-store = direct\nmodule-store = direct\n'):
        config.write_text(contents)
        assert adapter.configured_store() is None
        with pytest.raises(ValueError, match='store root and direct connection'):
            prepared.configure('fedora', 'remove')
    assert current == selected
    assert policy.installed == original_policy
    assert prepared.SSH_POLICY_RECEIPT.exists()

    config.write_text('# store-root = "/alternate/selinux"\nmodule-store = direct\n'
                      'ignoredirs = /srv/store-root\nstore-root = "/var/lib/selinux"\n')
    events = []
    lib = SimpleNamespace(
        semanage_handle_create=lambda: 1,
        semanage_set_store_root=lambda _handle, root: events.append(('root', root)),
        semanage_select_store=lambda _handle, name, _mode: events.append(('name', name)),
        semanage_connect=lambda _handle: events.append(('connect',)) or 0,
        semanage_disconnect=lambda _handle: 0,
        semanage_handle_destroy=lambda _handle: None,
    )
    monkeypatch.setattr(adapter, 'semanage', lambda: lib)
    with adapter.module_store('targeted', prepared.SSH_POLICY.stem, 200, writable=False, reload=False):
        pass
    assert set(events[:2]) == {('root', b'/var/lib/selinux'), ('name', b'targeted')}
    assert events[2:] == [('connect',)]


def test_prepared_fedora_ready_under_migration_state_lock(prepared_fedora, monkeypatch):
    prepared, _authselect, _current, _commands, _policy = prepared_fedora
    prepared.configure('fedora', 'install')
    payload = SimpleNamespace(stat=lambda: SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0))
    monkeypatch.setattr(prepared, 'MODULES', {'fedora': payload})
    monkeypatch.setattr(prepared, 'LOGIN_CHECK', payload)
    monkeypatch.setattr(prepared, 'TIME_CHECK', payload)
    # An accidental recursive lock must fail immediately instead of hanging pytest.
    monkeypatch.setattr(prepared, 'fcntl', SimpleNamespace(
        LOCK_EX=fcntl.LOCK_EX, flock=lambda fd, op: fcntl.flock(fd, op | fcntl.LOCK_NB)))
    descriptor = os.open(prepared.SSH_POLICY_RECEIPT.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            prepared.runtime_ready('fedora')
        prepared.runtime_ready('fedora', state_locked=True)
    finally:
        os.close(descriptor)
    prepared.runtime_ready('fedora')


def test_prepared_fedora_interrupted_select_keeps_original_for_exact_retry(prepared_fedora, monkeypatch):
    prepared, authselect, current, _commands, _policy = prepared_fedora
    import subprocess
    original, real_run = current.copy(), authselect.run

    def fail_select(*arguments, capture=False):
        if arguments[0] == 'select':
            raise subprocess.CalledProcessError(1, ['authselect', *arguments])
        return real_run(*arguments, capture=capture)

    monkeypatch.setattr(authselect, 'run', fail_select)
    with pytest.raises(subprocess.CalledProcessError):
        prepared.configure('fedora', 'install')
    assert current == original
    assert json.loads(authselect.STATE.read_text())['original'] == original
    assert json.loads(authselect.STATE.read_text())['phase'] == 'prepared'
    monkeypatch.setattr(authselect, 'run', real_run)
    prepared.configure('fedora', 'install')
    prepared.configure('fedora', 'remove')
    assert current == original
