"""Classification assertions use private files and OS/service doubles only."""

import copy
import json
import os
from pathlib import Path
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


def test_retained_record_oracle_keeps_unknown_keys_comments_and_groups(monkeypatch):
    monkeypatch.setattr(accounts, 'ICON', Path('/fixed-test-icon'))
    original = (b'[User]\nLanguage=fr_FR.UTF-8\nSystemAccount=false\n'
                b'Icon=/original\n# Existing comment\nUnknown=keep\\svalue\n\n'
                b'[org.example.Existing]\nData=keep extension\n')
    visible = accounts.fixture_record(original, hidden=False)
    hidden = accounts.fixture_record(original, hidden=True)
    assert hidden.replace(b'SystemAccount=true', b'SystemAccount=false') == visible
    for retained in (b'Language=fr_FR.UTF-8', b'# Existing comment',
                     b'Unknown=keep\\svalue', b'[org.example.Existing]\nData=keep extension'):
        assert retained in visible
    assert visible.count(b'SystemAccount=') == visible.count(b'Icon=') == 1
    assert b'Icon=/fixed-test-icon' in visible
    assert b'X-OnpcConfinementMetadata=' in visible
    assert b'[org.example.OnpcConfinementRetained]' in visible


@pytest.mark.parametrize('raw', [b'[User]\n', b'[User]\nSystemAccount=maybe\n',
                               b'[User]\nSystemAccount=true\nSystemAccount=false\n'])
def test_fixture_refuses_ambiguous_classification(raw):
    with pytest.raises(accounts.guest.GuestError, match='fixture-record-shape'):
        accounts.fixture_record(raw, hidden=True)


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


@pytest.mark.parametrize('changed', ['content', 'mode', 'xattr', 'icon'])
def test_metadata_assertion_detects_each_preserved_boundary(monkeypatch, changed):
    expected = {'sha256': 'a', 'uid': 0, 'gid': 0, 'mode': 0o600, 'xattrs': {'label': 'b'}}
    actual = dict(expected)
    key = {'content': 'sha256', 'mode': 'mode', 'xattr': 'xattrs', 'icon': 'sha256'}[changed]
    actual[key] = {'mode': 0o640, 'xattrs': {'label': 'changed'}}.get(key, 'changed')
    monkeypatch.setattr(accounts, 'fingerprint', lambda path:
                        actual if (path == accounts.ICON) == (changed == 'icon') else expected)
    with pytest.raises(accounts.guest.GuestError, match='retained-metadata-changed') as error:
        accounts.verify_preserved(expected, expected)
    detail = json.loads(str(error.value).split('retained-metadata-changed:', 1)[1])
    role = 'icon' if changed == 'icon' else 'cache'
    assert set(detail) == {role}
    assert detail[role]['fields'] == [key]
    if key == 'sha256':
        assert detail[role]['sha256'] == {'expected': 'a', 'actual': 'changed'}
    elif key == 'mode':
        assert detail[role]['mode'] == {'expected': '0o600', 'actual': '0o640'}
    else:
        assert detail[role]['xattrs'] == [{'name': 'label', 'expected_sha256': 'b',
                                          'actual_sha256': 'changed'}]


def test_metadata_diagnostics_bound_xattr_names_and_count():
    expected = {'sha256': 'a', 'uid': 0, 'gid': 0, 'mode': 0o600, 'xattrs': {}}
    actual = copy.deepcopy(expected)
    actual['xattrs'] = {f'user.fixture-{index:02d}-' + 'x' * 100: 'b' * 64
                       for index in range(20)}
    detail = accounts.fingerprint_difference(expected, actual)
    assert detail['fields'] == ['xattrs']
    assert len(detail['xattrs']) == 8 and detail['omitted_xattrs'] == 12
    assert all(len(attribute['name']) == 96 for attribute in detail['xattrs'])
    assert all(attribute['expected_sha256'] is None and
               attribute['actual_sha256'] == 'b' * 64 for attribute in detail['xattrs'])


def test_equal_fingerprints_pass_without_diagnostic_output(capsys):
    expected = {'sha256': 'a', 'uid': 0, 'gid': 0, 'mode': 0o600, 'xattrs': {}}
    accounts.require_fingerprints((('cache', expected, copy.deepcopy(expected)),), 'failure')
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('initial_mode', [0o600, 0o644])
def test_fresh_restart_accepts_only_source_owned_permission_normalization(initial_mode):
    before = {'sha256': 'a', 'uid': 0, 'gid': 0, 'mode': initial_mode,
              'xattrs': {'security.selinux': 'b'}}
    original = copy.deepcopy(before)
    accounts.verify_fresh_restart(before, dict(before, mode=0o600))
    assert before == original


@pytest.mark.parametrize('initial_mode', [0o400, 0o640, 0o666])
def test_fresh_restart_refuses_unexpected_initial_permissions(initial_mode):
    before = {'sha256': 'a', 'uid': 0, 'gid': 0, 'mode': initial_mode, 'xattrs': {}}
    with pytest.raises(accounts.guest.GuestError, match='fresh-initial-mode'):
        accounts.verify_fresh_restart(before, dict(before, mode=0o600))


@pytest.mark.parametrize('final_mode', [0o644, 0o640, 0o400])
def test_fresh_restart_requires_daemon_canonical_permissions(final_mode):
    before = {'sha256': 'a', 'uid': 0, 'gid': 0, 'mode': 0o644, 'xattrs': {}}
    with pytest.raises(accounts.guest.GuestError, match='fresh-restart-changed-record'):
        accounts.verify_fresh_restart(before, dict(before, mode=final_mode))


@pytest.mark.parametrize('field,value', [('sha256', 'changed'), ('uid', 1), ('gid', 1),
                                       ('xattrs', {'security.selinux': 'changed'})])
def test_fresh_restart_permission_normalization_keeps_every_other_field_exact(field, value):
    before = {'sha256': 'a', 'uid': 0, 'gid': 0, 'mode': 0o644,
              'xattrs': {'security.selinux': 'b'}}
    after = dict(before, mode=0o600)
    after[field] = value
    with pytest.raises(accounts.guest.GuestError, match='fresh-restart-changed-record') as error:
        accounts.verify_fresh_restart(before, after)
    detail = json.loads(str(error.value).split('fresh-restart-changed-record:', 1)[1])
    assert detail['cache']['fields'] == [field]


@pytest.mark.parametrize('role', ['administrator', 'standard'])
@pytest.mark.parametrize('field', ['uid', 'icon_path', 'cache', 'icon'])
def test_ordinary_witness_detects_each_role_without_disclosing_identifiers(monkeypatch, role, field):
    metadata = {'sha256': 'a', 'uid': 0, 'gid': 0, 'mode': 0o600, 'xattrs': {}}
    state = {'uid': 1000, 'icon_path': '/private/expected', 'cache': metadata, 'icon': metadata}
    expected = {name: copy.deepcopy(state) for name in accounts.ORDINARY_ACCOUNTS}
    actual = copy.deepcopy(expected)
    if field in ('cache', 'icon'):
        actual[role][field] = dict(metadata, sha256='changed')
    else:
        actual[role][field] = 2000 if field == 'uid' else '/private/actual'
    monkeypatch.setattr(accounts, 'ordinary_state', lambda: actual)
    with pytest.raises(accounts.guest.GuestError, match='ordinary-metadata-changed') as error:
        accounts.verify_ordinary(expected)
    detail = json.loads(str(error.value).split('ordinary-metadata-changed:', 1)[1])
    changed = {'fields': [field]}
    if field in ('cache', 'icon'):
        changed[field] = {'fields': ['sha256'], 'sha256': {'expected': 'a', 'actual': 'changed'}}
    assert detail == {role: changed}


@pytest.mark.parametrize('missing', ['administrator', 'standard'])
def test_ordinary_witness_requires_both_roles(monkeypatch, missing):
    actual = {role: {} for role in accounts.ORDINARY_ACCOUNTS}
    expected = {role: value for role, value in actual.items() if role != missing}
    monkeypatch.setattr(accounts, 'ordinary_state', lambda: actual)
    with pytest.raises(accounts.guest.GuestError, match='ordinary-witness-roles'):
        accounts.verify_ordinary(expected)


@pytest.mark.parametrize('fault', [None, 'missing-marker', 'content', 'extra-xattr',
                                 'marker-uid', 'marker-before', 'marker-inode'])
def test_pending_transaction_keeps_exact_independent_metadata_oracle(monkeypatch, fault):
    expected = {'sha256': 'visible-hash', 'uid': 0, 'gid': 0, 'mode': 0o600,
                'xattrs': {'user.original': 'original-hash'}}
    actual = copy.deepcopy(expected)
    actual['xattrs'][accounts.TRANSACTION] = 'transaction-hash'
    marker = {'version': 1, 'uid': 1002, 'device': 11, 'inode': 22,
              'before': 'hidden-hash', 'after': 'visible-hash'}
    if fault == 'missing-marker':
        del actual['xattrs'][accounts.TRANSACTION]
    elif fault == 'content':
        actual['sha256'] = 'foreign-content'
    elif fault == 'extra-xattr':
        actual['xattrs']['user.foreign'] = 'foreign-hash'
    elif fault == 'marker-uid':
        marker['uid'] = 2002
    elif fault == 'marker-before':
        marker['before'] = 'foreign-original'
    elif fault == 'marker-inode':
        marker['inode'] = 23
    monkeypatch.setattr(accounts, 'fingerprint', lambda _: copy.deepcopy(actual))
    monkeypatch.setattr(accounts.os, 'getxattr', lambda *_: json.dumps(marker).encode())
    arguments = (Path('/fixture/slot'), expected, {'sha256': 'hidden-hash'},
                 SimpleNamespace(pw_uid=1002), SimpleNamespace(st_dev=11, st_ino=22))
    if fault:
        with pytest.raises(accounts.guest.GuestError, match='transaction-'):
            accounts.verify_pending(*arguments)
    else:
        accounts.verify_pending(*arguments)
        assert expected['xattrs'] == {'user.original': 'original-hash'}


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
