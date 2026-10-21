"""Collateral evidence refuses wrong roles, private scope and lost ownership."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest

import system_kiosk_scope as scope


@pytest.mark.parametrize('fault', [None, 'uid', 'role', 'shell'])
def test_both_ordinary_controls_require_prepared_identity(tmp_path, monkeypatch, fault):
    baseline = tmp_path / 'baseline.json'
    accounts = {name: SimpleNamespace(pw_name=name, pw_uid=1001 + index, pw_shell='/bin/bash')
                for index, name in enumerate(scope.ORDINARY_ACCOUNTS.values())}
    declared = {name: {'uid': accounts[name].pw_uid, 'role': role}
                for role, name in scope.ORDINARY_ACCOUNTS.items()}
    standard = scope.ORDINARY_ACCOUNTS['standard']
    if fault in ('uid', 'role'):
        declared[standard][fault] = 999 if fault == 'uid' else 'administrator'
    if fault == 'shell':
        accounts[standard].pw_shell = '/usr/sbin/nologin'
    baseline.write_text(json.dumps({'accounts': declared}))
    monkeypatch.setattr(scope.guest, 'BASELINE', baseline)
    monkeypatch.setattr(scope.pwd, 'getpwnam', accounts.__getitem__)
    if fault:
        with pytest.raises(scope.guest.GuestError, match='baseline-role:standard'):
            scope.ordinary_accounts()
    else:
        assert list(scope.ordinary_accounts()) == ['administrator', 'standard']


@pytest.mark.parametrize('fault', [None, 'failed-start', 'replaced', 'preexisting'])
def test_manager_cleanup_requires_its_new_invocation(monkeypatch, tmp_path, fault):
    old = dict(ActiveState='inactive', InvocationID='', MainPID='0')
    owned = dict(ActiveState='active', InvocationID='a' * 32, MainPID='4321')
    if fault == 'preexisting':
        old = owned
    current = dict(owned, InvocationID='b' * 32) if fault == 'replaced' else owned
    state = Mock(side_effect=[old, owned, current, old])
    monkeypatch.setattr(scope, 'manager', state)
    run = Mock()
    if fault == 'failed-start':
        run.side_effect = [RuntimeError('startup'), '']
    monkeypatch.setattr(scope.guest, 'run', run)
    monkeypatch.setattr(scope, 'PROC', tmp_path)
    if fault:
        expected = RuntimeError if fault == 'failed-start' else scope.guest.GuestError
        with pytest.raises(expected):
            with scope.owned_manager(SimpleNamespace(pw_uid=1001)):
                pass
    else:
        with scope.owned_manager(SimpleNamespace(pw_uid=1001)) as process:
            assert process == tmp_path / '4321'
    stopped = [call.args[0] for call in run.call_args_list if call.args[0][1] == 'stop']
    assert stopped == ([] if fault in ('preexisting', 'replaced') else
                       [['systemctl', 'stop', 'user@1001.service']])


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'unit-path', 'drop-in', 'nnp', 'filter', 'compositor',
                                 'bus'])
def test_effective_unit_scope_rejects_collateral_changes(tmp_path, monkeypatch, backend, fault):
    monkeypatch.setattr(scope, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(scope, 'user_command', lambda *args: (
        str(tmp_path) if fault == 'unit-path' else '/usr/lib/systemd/user').encode())

    def properties(account, service, names):
        executable = '/usr/bin/dbus-daemon' if backend == 'apparmor' else '/usr/bin/dbus-broker-launch'
        values = dict(LoadState='loaded', FragmentPath='/usr/lib/systemd/user/' + service,
            DropInPaths='/usr/lib/systemd/user/service.d/vendor.conf', Environment='',
            ExecStart='{ path=' + executable + ' ; argv[]=' + executable + ' --scope user ; }',
            NoNewPrivileges='yes', LockPersonality='yes', MemoryDenyWriteExecute='yes',
            SystemCallFilter='read write', SystemCallArchitectures='native')
        if fault == 'drop-in':
            values['DropInPaths'] = str(tmp_path / 'user-units/override.conf')
        if fault == 'nnp':
            values['NoNewPrivileges'] = 'no'
        if fault == 'filter':
            values['SystemCallFilter'] = '~'
        if fault == 'compositor' and service == scope.SERVICES[-1]:
            values['Environment'] = 'GIO_USE_VFS=local'
        if fault == 'bus' and service == 'dbus.service':
            values['ExecStart'] = '{ path=/usr/libexec/oh-no-parent-control-kiosk-dbus ; }'
        return {name: values[name] for name in names}

    monkeypatch.setattr(scope, 'properties', properties)
    if fault:
        with pytest.raises(scope.guest.GuestError, match='kiosk-collateral:'):
            scope.verify_units(None, backend)
    else:
        scope.verify_units(None, backend)


@pytest.mark.parametrize('suffix,distribution', [('.deb', 'ubuntu'), ('.rpm', 'fedora')])
@pytest.mark.parametrize('failure', [False, True])
def test_vendor_readiness_uses_selected_distro_owner(monkeypatch, suffix, distribution, failure):
    monkeypatch.setattr(scope.guest, 'package_path', lambda: Path('package' + suffix))
    ready = Mock(side_effect=ValueError('owned-policy-changed') if failure else None)
    load = Mock(return_value={'runtime_ready': ready})
    monkeypatch.setattr(scope.runpy, 'run_path', load)
    record = Mock()
    if failure:
        with pytest.raises(ValueError, match='owned-policy-changed'):
            scope.verify_vendor_pam(record)
        record.assert_not_called()
    else:
        scope.verify_vendor_pam(record)
        record.assert_called_once_with('onpc.kiosk.collateral.pam.owned-distro-blocks-ready', True)
    load.assert_called_once_with('/usr/libexec/oh-no-parent-control-distro-pam')
    ready.assert_called_once_with(distribution)


def test_guard_refuses_before_any_guest_action(monkeypatch):
    monkeypatch.setattr(scope.guest, 'guard', Mock(side_effect=scope.guest.GuestError('identity')))
    diagnostics, accounts, pam = Mock(), Mock(), Mock()
    monkeypatch.setattr(scope.guest, 'enable_diagnostics', diagnostics)
    monkeypatch.setattr(scope, 'ordinary_accounts', accounts)
    monkeypatch.setattr(scope, 'verify_vendor_pam', pam)
    with pytest.raises(scope.guest.GuestError, match='identity'):
        scope.verify(Mock())
    for action in (diagnostics, accounts, pam):
        action.assert_not_called()


def test_pam_readiness_refusal_prevents_ordinary_manager_actions(monkeypatch):
    monkeypatch.setattr(scope, 'backend', lambda: 'apparmor')
    monkeypatch.setattr(scope.guest, 'guard', Mock())
    monkeypatch.setattr(scope.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(scope, 'ordinary_accounts', lambda: {'standard': object()})
    monkeypatch.setattr(scope, 'verify_vendor_pam', Mock(
        side_effect=scope.guest.GuestError('owned-policy-changed')))
    owned = Mock()
    monkeypatch.setattr(scope, 'owned_manager', owned)
    with pytest.raises(scope.guest.GuestError, match='owned-policy-changed'):
        scope.verify(Mock())
    owned.assert_not_called()


@pytest.mark.parametrize('backend,domain', [('apparmor', 'unconfined_t'),
    ('selinux', 'unconfined_t'), ('selinux', 'unconfined_dbusd_t')])
@pytest.mark.parametrize('fault', [None, 'uid', 'label', 'malformed-label', 'inode'])
def test_ordinary_process_requires_measured_domain_and_global_executables(
        tmp_path, monkeypatch, backend, domain, fault):
    process = tmp_path / 'process'
    attribute = process / ('attr/apparmor/current' if backend == 'apparmor' else 'attr/current')
    attribute.parent.mkdir(parents=True)
    label = 'unconfined' if backend == 'apparmor' else 'unconfined_u:unconfined_r:' + domain + ':s0'
    if fault == 'label':
        label = 'onpc-kiosk-manager (enforce)' if backend == 'apparmor' else 'system_u:system_r:onpc_kiosk_manager_t:s0'
    if fault == 'malformed-label':
        label = 'unexpected'
    attribute.write_text(label)
    monkeypatch.setattr(scope, 'PAYLOAD', Path('/confinement'))
    uid = '1002' if fault == 'uid' else '1001'
    monkeypatch.setattr(scope, 'process_identity', lambda path: ('start', 1, (uid,) * 4))
    originals = {}
    for name in ('python3', 'gjs', 'wireplumber'):
        visible = process / 'root/usr/bin' / name
        visible.parent.mkdir(parents=True, exist_ok=True)
        visible.write_text(name)
        info = visible.stat()
        originals['/usr/bin/' + name] = SimpleNamespace(stat=lambda info=info:
            SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino + (fault == 'inode')))
    monkeypatch.setattr(scope, 'Path', originals.__getitem__)
    if fault:
        with pytest.raises(scope.guest.GuestError, match='kiosk-collateral:'):
            scope.ordinary_process(process, SimpleNamespace(pw_uid=1001), backend, domain=domain)
    else:
        scope.ordinary_process(process, SimpleNamespace(pw_uid=1001), backend, domain=domain)
