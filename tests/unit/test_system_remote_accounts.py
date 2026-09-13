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
