"""Offline credential fixtures with mocked guest APIs and private canaries."""
from contextlib import contextmanager
from unittest.mock import Mock
import pytest
import fixture_credentials as credentials

CANARY = 'fixture-only-secret-0123456789'
HASH = '$6$fixturesalt$' + 'a' * 86

@pytest.fixture
def attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(credentials, 'read_password', lambda: CANARY)
    fixture = credentials.FixtureCredentials()
    lease = Mock(fd=42, state={'phase': 'isolated', 'domain_id': None})
    accounts = {account.username: {'uid': 1000 + n}
                for n, account in enumerate(credentials.ACCOUNTS.values())}
    lease.capture.state = {'source': {'layout': {'disk': '/recorded-offline.qcow2'}},
                           'guest': {'accounts': accounts}}
    verified = Mock(lease=lease)
    guest = Mock()
    guest.realpath.side_effect = lambda path: path
    guest.lstatns.return_value = {'st_uid': 0, 'st_nlink': 1, 'st_mode': 0o100640}
    files = {
        '/etc/passwd': b'root:x:0:0:root:/root:/bin/bash\n' + ''.join(
            f'{name}:x:{record["uid"]}:1000:Fixture:/home/{name}:/bin/bash\n'
            for name, record in accounts.items()).encode(),
        '/etc/shadow': b'root:!:20000:0:99999:7:::\n' + ''.join(
            f'{name}:{HASH}:20000:0:99999:7:::\n' for name in accounts).encode(),
    }
    original = dict(files)
    guest.filesize.side_effect = lambda path: len(files[path])
    guest.read_file.side_effect = lambda path: files[path]
    @contextmanager
    def mounted(api, selected, **kwargs):
        assert selected is lease and kwargs == {'readonly': True}
        try:
            yield guest
        finally:
            guest.close()
    monkeypatch.setattr(credentials, 'mounted_guest', mounted)
    verifier = Mock(side_effect=lambda password, encoded: password == CANARY and encoded == HASH)
    monkeypatch.setattr(credentials, 'matches', verifier)
    commands = Mock()
    run = lambda: fixture.provision(lease, verified, tmp_path, Mock(), commands)
    return Mock(fixture=fixture, lease=lease, verified=verified, guest=guest,
                files=files, original=original, commands=commands, verifier=verifier,
                run=run, directory=tmp_path)
