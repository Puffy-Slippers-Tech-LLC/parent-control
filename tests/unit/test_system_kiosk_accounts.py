"""Account fixture writes and service operations preserve ownership."""

import json
import os
import stat
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_kiosk_accounts as accounts


@pytest.mark.parametrize('entry', ['exercise', 'verify_reboot'])
def test_guest_guard_precedes_account_and_service_actions(monkeypatch, entry):
    monkeypatch.setattr(accounts.guest, 'guard', Mock(side_effect=accounts.guest.GuestError('identity')))
    commands = Mock()
    monkeypatch.setattr(accounts.guest, 'commands', commands)
    native = Mock()
    monkeypatch.setattr(accounts.pwd, 'getpwnam', native)
    with pytest.raises(accounts.guest.GuestError, match='identity'):
        getattr(accounts, entry)(Mock())
    commands.run.assert_not_called()
    native.assert_not_called()


@pytest.mark.parametrize('collision', [None, 'file', 'dangling-symlink'])
def test_fixture_icon_is_greeter_readable_and_preserves_collisions(tmp_path, monkeypatch, collision):
    cache, icon, source = (tmp_path / name for name in ('cache', 'icon', 'packaged.png'))
    cache.write_bytes(b'original cache')
    source.write_bytes(b'packaged icon bytes')
    if collision == 'file':
        icon.write_bytes(b'foreign icon')
    elif collision == 'dangling-symlink':
        icon.symlink_to(tmp_path / 'missing')
    monkeypatch.setattr(accounts, 'CACHE', cache)
    monkeypatch.setattr(accounts, 'ICON', icon)
    for name in ('guard', 'verify_package_files', 'enable_diagnostics'):
        monkeypatch.setattr(accounts.guest, name, Mock())
    monkeypatch.setattr(accounts.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_shell='/usr/sbin/nologin'))
    monkeypatch.setattr(accounts, 'unit_property', lambda _: 'active')
    monkeypatch.setattr(accounts, 'owned_bytes', lambda _: cache.read_bytes())
    monkeypatch.setattr(accounts, 'ordinary_state', Mock(return_value={}))
    packaged = Mock(return_value=source)
    monkeypatch.setattr(accounts, 'Path', packaged)
    fingerprint = Mock(side_effect=RuntimeError('icon creation complete'))
    monkeypatch.setattr(accounts, 'fingerprint', fingerprint)
    if collision:
        with pytest.raises(accounts.guest.GuestError, match='icon-collision'):
            accounts.exercise(Mock())
        packaged.assert_not_called()
        fingerprint.assert_not_called()
        if collision == 'file':
            assert icon.read_bytes() == b'foreign icon'
        else:
            assert icon.is_symlink() and os.readlink(icon) == str(tmp_path / 'missing')
    else:
        with pytest.raises(RuntimeError, match='icon creation complete'):
            accounts.exercise(Mock())
        packaged.assert_called_once_with('/usr/share/oh-no-parent-control/kiosk_account_icon.png')
        fingerprint.assert_called_once_with(icon)
        assert icon.read_bytes() == source.read_bytes()
        mode = stat.S_IMODE(icon.stat().st_mode)
        assert mode & stat.S_IRGRP and mode & stat.S_IROTH
        assert not mode & (stat.S_IWGRP | stat.S_IWOTH | 0o111)
    assert cache.read_bytes() == b'original cache'


@pytest.mark.parametrize('stage', ['before', 'after', 'unrecognized'])
def test_interrupt_guard_precedes_fault_injection(monkeypatch, stage):
    monkeypatch.setattr(accounts.guest, 'guard', Mock(side_effect=accounts.guest.GuestError('identity')))
    production = Mock()
    monkeypatch.setattr(accounts.runpy, 'run_path', production)
    with pytest.raises(accounts.guest.GuestError, match='identity'):
        accounts.interrupt_repair(stage)
    production.assert_not_called()


def test_interrupt_refuses_a_live_daemon_before_loading_product(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts.guest, 'guard', Mock())
    mask = tmp_path / 'mask'
    mask.symlink_to('/dev/null')
    monkeypatch.setattr(accounts, 'MASK', mask)
    monkeypatch.setattr(accounts, 'unit_property', lambda _: 'active')
    production = Mock()
    monkeypatch.setattr(accounts.runpy, 'run_path', production)
    with pytest.raises(accounts.guest.GuestError, match='interruption-not-quiescent'):
        accounts.interrupt_repair('before')
    production.assert_not_called()


@pytest.mark.parametrize('destination,expected', [
    (accounts.NAME, 'injected'), ('foreign-account', 'refused'),
])
def test_precommit_injection_has_one_identity_pinned_target(tmp_path, monkeypatch, destination, expected):
    monkeypatch.setattr(accounts.guest, 'guard', Mock())
    mask = tmp_path / 'mask'
    mask.symlink_to('/dev/null')
    monkeypatch.setattr(accounts, 'MASK', mask)
    monkeypatch.setattr(accounts, 'CACHE', tmp_path / accounts.NAME)
    monkeypatch.setattr(accounts, 'unit_property', lambda name:
                        'inactive' if name == 'ActiveState' else '0')
    native_run, native_replace = Mock(), Mock()
    product = {'os': SimpleNamespace(replace=native_replace),
               'subprocess': SimpleNamespace(run=native_run)}
    descriptor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)

    def repair():
        product['os'].replace(accounts.SLOT, destination,
                              src_dir_fd=descriptor, dst_dir_fd=descriptor)

    product['visibility'] = repair
    monkeypatch.setattr(accounts.runpy, 'run_path', lambda _: product)
    try:
        if expected == 'injected':
            assert accounts.interrupt_repair('failure') == 74
        else:
            with pytest.raises(accounts.guest.GuestError, match='interruption-commit-target'):
                accounts.interrupt_repair('failure')
    finally:
        os.close(descriptor)
    native_replace.assert_not_called()
    assert product['os'].replace is native_replace
    assert product['subprocess'].run is native_run


@pytest.mark.parametrize('replacement', [False, True])
def test_fixture_mask_cleanup_preserves_foreign_replacement(tmp_path, monkeypatch, replacement):
    mask = tmp_path / 'accounts-daemon.service'
    monkeypatch.setattr(accounts, 'MASK', mask)
    monkeypatch.setattr(accounts, 'unit_property', lambda _: 'inactive' if mask.is_symlink() else 'active')
    actions = []

    def run(command, **_):
        actions.append(command[1])
        if command[1] == 'mask':
            mask.symlink_to('/dev/null')
        elif command[1] == 'unmask':
            mask.unlink()

    monkeypatch.setattr(accounts.guest, 'run', run)

    def operation():
        with accounts.stopped_fixture_daemon():
            if replacement:
                mask.unlink()
                mask.write_text('foreign unit')

    if replacement:
        with pytest.raises(accounts.guest.GuestError, match='fixture-mask-replaced'):
            operation()
        assert mask.read_text() == 'foreign unit'
        assert actions == ['reset-failed', 'mask', 'stop']
    else:
        operation()
        assert not mask.exists()
        assert actions == ['reset-failed', 'mask', 'stop', 'unmask', 'start']


def test_fixture_resets_healthy_restart_budget_before_masking(tmp_path, monkeypatch):
    mask = tmp_path / 'mask'
    monkeypatch.setattr(accounts, 'MASK', mask)
    actions = []

    def property_value(name):
        assert name == 'ActiveState'
        state = 'inactive' if mask.is_symlink() else 'active'
        actions.append(('observe', state))
        return state

    def run(command, **_):
        assert command[-1] == accounts.DAEMON
        actions.append(('run', command[1]))
        if command[1] == 'mask':
            mask.symlink_to('/dev/null')
        elif command[1] == 'unmask':
            mask.unlink()

    monkeypatch.setattr(accounts, 'unit_property', property_value)
    monkeypatch.setattr(accounts.guest, 'run', run)
    with accounts.stopped_fixture_daemon():
        assert actions == [('observe', 'active'), ('run', 'reset-failed'),
                           ('run', 'mask'), ('run', 'stop'), ('observe', 'inactive')]
    assert actions[-3:] == [('run', 'unmask'), ('run', 'start'), ('observe', 'active')]


@pytest.mark.parametrize('state', ['failed', 'inactive', 'activating'])
def test_fixture_never_resets_or_masks_an_unhealthy_daemon(tmp_path, monkeypatch, state):
    mask = tmp_path / 'mask'
    monkeypatch.setattr(accounts, 'MASK', mask)
    monkeypatch.setattr(accounts, 'unit_property', lambda _: state)
    command = Mock()
    monkeypatch.setattr(accounts.guest, 'run', command)
    with pytest.raises(accounts.guest.GuestError, match='fixture-daemon-not-healthy'):
        with accounts.stopped_fixture_daemon():
            pytest.fail('unhealthy daemon admitted')
    command.assert_not_called()
    assert not mask.exists()


def test_fixture_refuses_preexisting_runtime_mask_without_service_action(tmp_path, monkeypatch):
    mask = tmp_path / 'mask'
    mask.symlink_to('/dev/null')
    monkeypatch.setattr(accounts, 'MASK', mask)
    command = Mock()
    monkeypatch.setattr(accounts.guest, 'run', command)
    with pytest.raises(accounts.guest.GuestError, match='foreign-runtime-mask'):
        with accounts.stopped_fixture_daemon():
            pytest.fail('foreign mask admitted')
    command.assert_not_called()
    assert mask.is_symlink()


def test_witness_is_private_and_never_overwrites_an_existing_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts.guest, 'PAYLOAD', tmp_path)
    boot = tmp_path / 'boot'
    boot.write_text('old-boot\n')
    monkeypatch.setattr(accounts, 'BOOT', boot)
    monkeypatch.setattr(accounts, 'fingerprint', lambda _: {'sha256': 'a'})
    account = SimpleNamespace(pw_uid=1002, pw_gid=1002)
    accounts.save_witness(account, {'ordinary': 'witness'})
    path = accounts.state_path()
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_bytes())['boot'] == 'old-boot'
    with pytest.raises(accounts.guest.GuestError, match='witness-collision'):
        accounts.save_witness(account, {'ordinary': 'witness'})


def test_reboot_readback_requires_a_new_boot_before_any_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts.guest, 'guard', Mock())
    monkeypatch.setattr(accounts.guest, 'verify_package_files', Mock())
    monkeypatch.setattr(accounts.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(accounts.guest, 'PAYLOAD', tmp_path)
    boot = tmp_path / 'boot'
    boot.write_text('same-boot')
    monkeypatch.setattr(accounts, 'BOOT', boot)
    monkeypatch.setattr(accounts, 'owned_bytes', lambda _, **__: json.dumps(
        {'boot': 'same-boot', 'uid': 1002, 'gid': 1002}).encode())
    monkeypatch.setattr(accounts.pwd, 'getpwnam', lambda _: SimpleNamespace(
        pw_uid=1002, pw_gid=1002, pw_shell='/usr/sbin/nologin'))
    production = Mock()
    monkeypatch.setattr(accounts, 'production_provision', production)
    with pytest.raises(accounts.guest.GuestError, match='reboot-identity'):
        accounts.verify_reboot(Mock())
    production.assert_not_called()


@pytest.mark.parametrize('role', ['administrator', 'standard'])
@pytest.mark.parametrize('fault', [None, 'role', 'icon'])
def test_ordinary_witness_uses_only_declared_baseline_roles_and_icons(tmp_path, monkeypatch, role, fault):
    baseline = tmp_path / 'baseline.json'
    users = {name: SimpleNamespace(pw_uid=1000 + index, pw_shell='/bin/bash')
             for index, name in enumerate(accounts.ORDINARY_ACCOUNTS.values())}
    declared = {name: {'uid': users[name].pw_uid,
                      'role': 'foreign' if fault == 'role' and label == role else label}
                for label, name in accounts.ORDINARY_ACCOUNTS.items()}
    baseline.write_text(json.dumps({'accounts': declared}))
    monkeypatch.setattr(accounts.guest, 'BASELINE', baseline)
    monkeypatch.setattr(accounts.pwd, 'getpwnam', users.__getitem__)
    resolve = Mock(side_effect=lambda user: f'/org/freedesktop/Accounts/User{user.pw_uid}')
    monkeypatch.setattr(accounts, 'resolve', resolve)
    icons = {f'/org/freedesktop/Accounts/User{users[name].pw_uid}':
             '/unrelated/private-file' if fault == 'icon' and label == role else
             str(accounts.ICON.parent / name)
             for label, name in accounts.ORDINARY_ACCOUNTS.items()}
    monkeypatch.setattr(accounts.guest, 'run', lambda command: 's ' + json.dumps(icons[command[4]]))
    fingerprint = Mock(return_value={'sha256': 'preserved'})
    monkeypatch.setattr(accounts, 'fingerprint', fingerprint)
    if fault:
        with pytest.raises(accounts.guest.GuestError, match='ordinary-.*:' + role):
            accounts.ordinary_state()
        name = accounts.ORDINARY_ACCOUNTS[role]
        assert all(call.args[0] not in (accounts.CACHE.parent / name,
                                       accounts.ICON.parent / name)
                   for call in fingerprint.call_args_list)
        if fault == 'role':
            assert all(call.args[0] != users[name] for call in resolve.call_args_list)
    else:
        result = accounts.ordinary_state()
        assert result == {label: {'uid': users[name].pw_uid, 'cache': {'sha256': 'preserved'},
                                  'icon_path': str(accounts.ICON.parent / name),
                                  'icon': {'sha256': 'preserved'}}
                          for label, name in accounts.ORDINARY_ACCOUNTS.items()}
        assert [call.args[0] for call in fingerprint.call_args_list] == [
            path for name in accounts.ORDINARY_ACCOUNTS.values()
            for path in (accounts.CACHE.parent / name, accounts.ICON.parent / name)]
