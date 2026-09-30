"""Authselect ownership and restoration with private paths and command doubles."""
import importlib.util
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
    helper.STACK.write_text('account required pam_exec.so /usr/libexec/oh-no-parent-control-login-check\n'
                            'auth required pam_oh_no_parent_control.so\n')
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
