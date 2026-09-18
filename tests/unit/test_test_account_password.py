import os
from unittest.mock import Mock

import pytest
import test_account_password as config
import prepare_vm


@pytest.mark.parametrize('assignment,value', [
    ("export TEST_ACCOUNT_PASSWORD='same $password `literal`'", 'same $password `literal`'),
    ('TEST_ACCOUNT_PASSWORD="fixture password" # note', 'fixture password'),
    ('TEST_ACCOUNT_PASSWORD=fixture-password', 'fixture-password'),
])
def test_reads_only_literal_assignment(tmp_path, assignment, value):
    path = tmp_path / '.envrc'
    path.write_text('unrelated_command_that_must_not_run\n' + assignment + '\n')
    path.chmod(0o600)
    assert config.read_password(tmp_path) == value


@pytest.mark.parametrize('value', ['', "''", "'REPLACE_WITH_TEST_PASSWORD'", '"$OTHER"',
    '$(touch /tmp/forbidden)', "'one'; touch /tmp/forbidden", "'one'\nTEST_ACCOUNT_PASSWORD='two'",
    "'not:accepted'", "'one'\"$OTHER\""])
def test_missing_or_unsafe_values_refuse_without_revealing_contents(tmp_path, value, monkeypatch):
    monkeypatch.setenv('TEST_ACCOUNT_PASSWORD', 'environment-is-not-a-fallback')
    path = tmp_path / '.envrc'
    path.write_text('TEST_ACCOUNT_PASSWORD=' + value + '\n')
    path.chmod(0o600)
    with pytest.raises(ValueError, match='TEST_ACCOUNT_PASSWORD') as caught:
        config.read_password(tmp_path)
    assert 'forbidden' not in str(caught.value)


@pytest.mark.parametrize('fault', ['missing', 'public', 'symlink', 'hardlink'])
def test_private_file_is_required(tmp_path, fault):
    path = tmp_path / '.envrc'
    if fault != 'missing':
        path.write_text("TEST_ACCOUNT_PASSWORD='fixture-password'\n")
        path.chmod(0o600)
    if fault == 'public': path.chmod(0o644)
    if fault == 'symlink':
        path.rename(tmp_path / 'target')
        path.symlink_to(tmp_path / 'target')
    if fault == 'hardlink': os.link(path, tmp_path / 'alias')
    with pytest.raises(ValueError):
        config.read_password(tmp_path)


def test_native_hash_verification():
    # Published crypt(3) example, no real account or local secret involved.
    assert config.matches('Hello world!', '$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1')
    assert not config.matches('incorrect', '$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1')
    assert not config.matches('anything', '!')


def test_keyrings_are_backed_up_and_repeat_without_new_keyring_is_noop(tmp_path):
    account = prepare_vm.IDENTITIES[0]
    keyrings = tmp_path / account.username / '.local/share/keyrings'
    keyrings.mkdir(parents=True)
    for path in (keyrings, keyrings.parent, keyrings.parent.parent, keyrings.parent.parent.parent):
        path.chmod(0o700)
    (keyrings / 'login.keyring').write_bytes(b'encrypted-private-canary')
    lookup = lambda _: Mock(pw_uid=os.getuid(), pw_gid=os.getgid())
    prepare_vm.preserve_keyrings(account, lookup_user=lookup, homes=tmp_path)
    assert not keyrings.exists()
    backups = list(keyrings.parent.glob('onpc-keyring-backup-*'))
    assert len(backups) == 1
    assert (backups[0] / 'keyrings/login.keyring').read_bytes() == b'encrypted-private-canary'
    prepare_vm.preserve_keyrings(account, lookup_user=lookup, homes=tmp_path)
    assert list(keyrings.parent.glob('onpc-keyring-backup-*')) == backups


def test_keyring_symlink_cannot_change_another_directory(tmp_path):
    account = prepare_vm.IDENTITIES[0]
    home = tmp_path / account.username
    home.mkdir()
    elsewhere = tmp_path / 'unrelated'
    elsewhere.mkdir()
    (home / '.local').symlink_to(elsewhere)
    with pytest.raises(prepare_vm.PreparationError, match='keyring-path'):
        prepare_vm.preserve_keyrings(account, lookup_user=lambda _: Mock(pw_uid=os.getuid()), homes=tmp_path)
    assert elsewhere.is_dir()
