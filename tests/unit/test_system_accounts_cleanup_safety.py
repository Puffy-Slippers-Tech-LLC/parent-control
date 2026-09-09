"""Shared account fixtures must refuse before any unguarded guest mutation."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import system_accounts as accounts


@pytest.mark.parametrize('operation', ['create', 'delete'])
def test_guest_guard_precedes_account_reads_and_mutations(monkeypatch, operation):
    guard = Mock(side_effect=accounts.guest.GuestError('guard refused'))
    lookup, run = Mock(), Mock()
    monkeypatch.setattr(accounts.guest, 'guard', guard)
    monkeypatch.setattr(accounts.guest, 'run', run)
    monkeypatch.setattr(accounts.pwd, 'getpwnam', lookup)
    with pytest.raises(accounts.guest.GuestError, match='guard refused'):
        if operation == 'create':
            accounts.create_disposable_identity('target', Mock())
        else:
            accounts.delete_disposable_identity(1234, 'target')
    lookup.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize('role,surface', [('unrelated', None), ('target', 'other')])
def test_account_fixture_names_have_no_unreviewed_scope(monkeypatch, role, surface):
    monkeypatch.setattr(accounts.guest, 'guard', Mock())
    lookup, run = Mock(), Mock()
    monkeypatch.setattr(accounts.pwd, 'getpwnam', lookup)
    monkeypatch.setattr(accounts.guest, 'run', run)
    with pytest.raises(accounts.guest.GuestError, match='deletion-fixture-scope'):
        accounts.create_disposable_identity(role, Mock(), surface=surface)
    lookup.assert_not_called()
    run.assert_not_called()


def test_account_creation_preserves_existing_identity(monkeypatch):
    monkeypatch.setattr(accounts.guest, 'guard', Mock())
    monkeypatch.setattr(accounts.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(pw_uid=1234)))
    run = Mock()
    monkeypatch.setattr(accounts.guest, 'run', run)
    with pytest.raises(accounts.guest.GuestError, match='fixture-collision'):
        accounts.create_disposable_identity('target', Mock())
    run.assert_not_called()


def test_account_deletion_preserves_replaced_identity(monkeypatch):
    monkeypatch.setattr(accounts.guest, 'guard', Mock())
    monkeypatch.setattr(accounts.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(pw_uid=9999)))
    run, retain = Mock(), Mock()
    monkeypatch.setattr(accounts.guest, 'run', run)
    monkeypatch.setattr(accounts.guest, 'retain_identity_for_redaction', retain)
    with pytest.raises(accounts.guest.GuestError, match='identity-mismatch'):
        accounts.delete_disposable_identity(1234, 'target')
    retain.assert_not_called()
    run.assert_not_called()
