"""Host-safe validation of remote-directory provisioning refusal and NSS edits."""

from pathlib import Path
from unittest.mock import Mock
from types import SimpleNamespace

import pytest

import system_remote_accounts as remote


def test_remote_provisioning_refuses_host_before_any_access(monkeypatch):
    def refuse():
        raise remote.guest.GuestError('guest-refused')

    monkeypatch.setattr(remote.guest, 'guard', refuse)
    paths, commands = Mock(), Mock()
    monkeypatch.setattr(remote, 'Path', paths)
    monkeypatch.setattr(remote.guest, 'commands', commands)
    with pytest.raises(remote.guest.GuestError, match='guest-refused'):
        remote.provision()
    paths.assert_not_called()
    assert not commands.mock_calls


def test_nss_preserves_sources_actions_comments_and_other_databases():
    original = ('# directory test\npasswd: files systemd # identities\n'
                'group: files [SUCCESS=merge] systemd sss\n'
                'shadow: files\nhosts: files resolve [!UNAVAIL=return] dns\n')
    changed = remote.nss_configuration(original)
    assert changed == original.replace('systemd # identities', 'systemd sss # identities')
    assert remote.nss_configuration(changed) == changed


@pytest.mark.parametrize('original', ('passwd: files\n',
                                     'passwd: files\npasswd: sss\ngroup: files\n'))
def test_nss_refuses_ambiguous_configuration(original):
    with pytest.raises(remote.guest.GuestError, match='remote:nss-'):
        remote.nss_configuration(original)


@pytest.mark.parametrize('prepared', [True, False])
def test_remote_fixture_uses_installed_packages_without_apt_and_keeps_identities_fresh(tmp_path, monkeypatch, prepared):
    from guest_test_dependencies import VERSIONS
    files = {
        '/var/lib/dpkg/status': '\n\n'.join(
            f'Package: {name}\nVersion: {version}\nStatus: install ok installed\n'
            for name, version in VERSIONS.items()) if prepared else '',
        '/etc/default/slapd': 'SLAPD_SERVICES="ldap:/// ldapi:///"\n',
        '/etc/nsswitch.conf': 'passwd: files systemd\ngroup: files systemd\nshadow: files\n',
    }
    for path, content in files.items():
        target = tmp_path / path.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    (tmp_path / 'etc/sssd').mkdir()
    monkeypatch.setattr(remote, 'Path', lambda path: tmp_path / path.lstrip('/'))
    monkeypatch.setattr(remote.guest, 'guard', Mock())
    monkeypatch.setattr(remote.guest, 'enable_diagnostics', Mock())
    commands = []
    ready = False
    identities = [SimpleNamespace(pw_name=name, pw_uid=uid) for name, uid in remote.IDENTITIES.values()]
    def lookup(value):
        if ready:
            for identity in identities:
                if value in (identity.pw_name, identity.pw_uid):
                    return identity
        raise KeyError(value)
    monkeypatch.setattr(remote, 'pwd', SimpleNamespace(getpwnam=lookup, getpwuid=lookup,
                                                     getpwall=lambda: identities if ready else []))
    monkeypatch.setattr(remote, 'grp', SimpleNamespace(getgrgid=lookup))
    adapter = Mock(last_returncode=2)
    adapter.run.return_value = b''
    monkeypatch.setattr(remote.guest, 'commands', adapter)
    def run(command, **kwargs):
        nonlocal ready
        commands.append(command)
        if command[0] == 'dpkg-reconfigure':
            assert 'ldap://127.0.0.1/ ldapi:///' in (tmp_path / 'etc/default/slapd').read_text()
            (tmp_path / 'etc/ldap/slapd.d').mkdir(parents=True)
        if command[0] == 'ldapsearch':
            return 'dn: olcDatabase={1}mdb,cn=config'
        if command == ['systemctl', 'start', 'sssd.service']:
            ready = True
        return ''
    monkeypatch.setattr(remote.guest, 'run', run)
    if not prepared:
        with pytest.raises(ValueError, match='guest-tools:'):
            remote.provision()
        assert not commands
        adapter.run.assert_not_called()
        return
    assert remote.provision() == {role: uid for role, (_, uid) in remote.IDENTITIES.items()}
    assert ['dpkg-reconfigure', '--frontend=noninteractive', 'slapd'] in commands
    assert not any('apt-get' in command or 'apt-cache' in command for command in commands)
    assert (tmp_path / 'etc/sssd/sssd.conf').stat().st_mode & 0o777 == 0o600
    assert 'shadow: files\n' in (tmp_path / 'etc/nsswitch.conf').read_text()
    assert sum(call.args[0][0] == 'ldapadd' for call in adapter.run.call_args_list) == 1


@pytest.mark.parametrize('fault', [None, 'missing-package', 'configuration-collision', 'active-directory'])
def test_fedora_remote_fixture_uses_native_ldap_and_wheel_without_debian_commands(
        tmp_path, monkeypatch, fault):
    monkeypatch.setattr(remote.guest, 'guard', Mock())
    monkeypatch.setattr(remote.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(remote.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(remote, 'Path', lambda value: tmp_path / str(value).lstrip('/'))
    for path in ('etc/openldap', 'var/lib/ldap', 'etc/sssd', 'etc/systemd/system'):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)
    if fault == 'configuration-collision':
        (tmp_path / 'var/lib/ldap/onpc-system-fixture-config').mkdir()
    identities = [SimpleNamespace(pw_name=name, pw_uid=uid, pw_gid=uid)
                  for name, uid in remote.IDENTITIES.values()]
    ready = False

    def lookup(value):
        if value == 'ldap':
            return SimpleNamespace(pw_uid=55, pw_gid=55)
        if ready:
            for identity in identities:
                if value in (identity.pw_uid, identity.pw_name):
                    return identity
        raise KeyError(value)

    monkeypatch.setattr(remote, 'pwd', SimpleNamespace(getpwnam=lookup, getpwuid=lookup,
                                                     getpwall=lambda: identities if ready else []))
    monkeypatch.setattr(remote, 'grp', SimpleNamespace(getgrgid=lookup))
    monkeypatch.setattr(remote.os, 'chown', Mock())
    nss = Mock()
    monkeypatch.setattr(remote, 'configure_fedora_nss', nss)
    adapter = Mock(last_returncode=2)
    adapter.run.return_value = b''
    monkeypatch.setattr(remote.guest, 'commands', adapter)
    commands = []

    def run(command, **kwargs):
        nonlocal ready
        commands.append(command)
        if command[0] == 'rpm':
            versions = dict(remote.FEDORA_REMOTE_VERSIONS)
            if fault == 'missing-package':
                versions.pop('sssd-client')
            return ''.join(f'{name}={version}\n' for name, version in versions.items())
        if command[:2] == ['systemctl', 'show']:
            return 'active' if fault == 'active-directory' else 'inactive'
        if command[0] == 'ldapsearch':
            return 'dn: olcDatabase={1}mdb,cn=config'
        if command == ['systemctl', 'start', 'sssd.service']:
            ready = True
        return ''

    monkeypatch.setattr(remote.guest, 'run', run)
    restoration = {}
    if fault:
        with pytest.raises(remote.guest.GuestError, match='remote:'):
            remote.provision(restoration=restoration)
        nss.assert_not_called()
        assert not any(command == ['systemctl', 'start', 'sssd.service'] for command in commands)
        assert not adapter.run.mock_calls
        return
    assert remote.provision(restoration=restoration) == {
        role: uid for role, (_, uid) in remote.IDENTITIES.items()}
    nss.assert_called_once_with(restoration)
    assert ['gpasswd', '--add', 'onpc-remote-admin', 'wheel'] in commands
    assert not any(command[0] in ('apt-get', 'dpkg-query', 'dpkg-reconfigure') for command in commands)
    ldif = next(call.kwargs['input'].decode() for call in adapter.run.call_args_list
                if call.args[0][0] == 'runuser')
    assert 'olcSuffix: dc=onpc,dc=invalid' in ldif and 'olcRootPW' not in ldif
    for schema in ('core', 'cosine', 'nis', 'inetorgperson'):
        assert f'include: file:///etc/openldap/schema/{schema}.ldif' in ldif
    dropin = (tmp_path / 'etc/systemd/system/slapd.service.d/onpc-system-fixture.conf').read_text()
    assert 'ldap://127.0.0.1/ ldapi:///' in dropin and '-F ' in dropin
    config = tmp_path / 'var/lib/ldap/onpc-system-fixture-config'
    assert f'-F {config}' in dropin
    assert ['restorecon', '-RF', str(config)] in commands
    assert str(config) in next(call.args[0] for call in adapter.run.call_args_list
                              if call.args[0][0] == 'runuser')
    assert not (tmp_path / 'etc/openldap/onpc-system-fixture.d').exists()
    entries = next(call.kwargs['input'].decode() for call in adapter.run.call_args_list
                   if call.args[0][0] == 'ldapadd')
    assert 'dn: dc=onpc,dc=invalid\n' in entries
    assert (tmp_path / 'etc/sssd/sssd.conf').stat().st_mode & 0o777 == 0o600


def test_fedora_nss_clones_live_profile_and_restores_exact_features(tmp_path, monkeypatch):
    profile = tmp_path / 'profile'
    profile.mkdir()
    nss = profile / 'nsswitch.conf'
    monkeypatch.setattr(remote, 'Path', lambda value: nss)
    original_lstat = type(nss).lstat

    def metadata(path):
        value = original_lstat(path)
        return SimpleNamespace(st_mode=value.st_mode, st_uid=0)

    monkeypatch.setattr(type(nss), 'lstat', metadata)
    monkeypatch.setattr(remote.guest, 'guard', Mock())
    monkeypatch.setattr(remote.guest, 'sha', lambda path: path.read_text())
    original = ['custom/oh-no-parent-control', 'with-silent-lastlog']
    selected = original[:]
    commands = []

    def run(command, **kwargs):
        nonlocal selected
        commands.append(command)
        if command == ['authselect', 'current', '--raw']:
            return ' '.join(selected)
        if command[:2] == ['authselect', 'create-profile']:
            nss.write_text('passwd: files systemd\ngroup: files systemd\nshadow: files\n')
            nss.chmod(0o644)
        if command[:2] == ['authselect', 'select']:
            selected = command[2:]
        return ''

    monkeypatch.setattr(remote.guest, 'run', run)
    restoration = {}
    remote.configure_fedora_nss(restoration)
    assert selected == ['custom/onpc-remote-fixture', 'with-silent-lastlog']
    assert 'passwd: files systemd sss \n' in nss.read_text()
    assert 'shadow: files\n' in nss.read_text()
    assert ['authselect', 'create-profile', 'onpc-remote-fixture', '-b', original[0]] in commands
    remote.restore_nss(restoration)
    assert selected == original
    assert ['systemctl', 'stop', 'sssd.service'] in commands
    assert not any('--force' in command for command in commands)


@pytest.mark.parametrize('fault', ['foreign-profile', 'changed-template'])
def test_fedora_nss_restore_refuses_foreign_state(monkeypatch, fault):
    run = Mock(return_value='custom/foreign' if fault == 'foreign-profile' else
               'custom/onpc-remote-fixture with-silent-lastlog')
    monkeypatch.setattr(remote.guest, 'guard', Mock())
    monkeypatch.setattr(remote.guest, 'run', run)
    monkeypatch.setattr(remote.guest, 'sha', Mock(return_value='changed'))
    with pytest.raises(remote.guest.GuestError, match='remote:authselect-'):
        remote.restore_nss({'original': ['custom/oh-no-parent-control', 'with-silent-lastlog'],
                            'profile_sha256': 'expected'})
    assert not any(call.args[0][:2] == ['authselect', 'select'] for call in run.call_args_list)
