"""Host-safe validation of remote-directory provisioning refusal and NSS edits."""

from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import system_remote_accounts as remote
sys.path.pop(0)


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
