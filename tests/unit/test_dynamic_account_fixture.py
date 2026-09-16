"""The E2E-003 fixture is fixed, guarded and collision-safe."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import account_fixture
import e2e_dynamic_account as guest_fixture
from private_artifacts import EvidenceError


def test_guest_guard_refuses_before_account_lookup_or_creation(monkeypatch):
    guard = Mock(side_effect=guest_fixture.guest.GuestError("guard-refused"))
    lookup, run = Mock(), Mock()
    monkeypatch.setattr(guest_fixture.guest, "guard", guard)
    monkeypatch.setattr(guest_fixture.pwd, "getpwnam", lookup)
    monkeypatch.setattr(guest_fixture.guest, "run", run)

    with pytest.raises(guest_fixture.guest.GuestError, match="guard-refused"):
        guest_fixture.create()

    lookup.assert_not_called()
    run.assert_not_called()


def test_guest_fixture_refuses_an_existing_identity(monkeypatch):
    monkeypatch.setattr(guest_fixture.guest, "guard", Mock())
    monkeypatch.setattr(guest_fixture.pwd, "getpwnam", Mock(return_value=SimpleNamespace()))
    run = Mock()
    monkeypatch.setattr(guest_fixture.guest, "run", run)

    with pytest.raises(guest_fixture.guest.GuestError, match="dynamic-account:collision"):
        guest_fixture.create()

    run.assert_not_called()


def test_controller_fixture_is_single_use_and_guarded(monkeypatch):
    run = "a" * 32
    transport = Mock()
    transport.call.return_value = b"onpc-e2e: stage=dynamic-account outcome=created\n"
    context = SimpleNamespace(lease=SimpleNamespace(state={"run": run}))
    journey = SimpleNamespace(context=context, transport=transport)
    guard = Mock()
    fixture = account_fixture.DynamicAccountFixture(context)

    assert fixture.create(journey, guard) == {"eligible_account_created": True}
    assert guard.call_count == 2
    argv = transport.call.call_args.args[0]
    assert argv[-2].endswith("/e2e_dynamic_account.py") and argv[-1] == "create"
    assert argv[1] == "ONPC_EXPECTED_RUN=" + run
    with pytest.raises(EvidenceError, match="controller-state"):
        fixture.create(journey, guard)
    transport.call.assert_called_once()


def test_guest_empty_fixture_changes_complete_finite_eligible_set(monkeypatch):
    names = (*guest_fixture.FIXED_CHILDREN, "onpc-baseline-admin",
             guest_fixture.KIOSK_USERNAME)
    identities = [SimpleNamespace(pw_name=name, pw_uid=index, pw_shell="/bin/bash")
                  for index, name in enumerate(names, 1001)]
    paths = {str(item.pw_uid): f"/org/freedesktop/Accounts/User{item.pw_uid}"
             for item in identities}
    roles = {path: "0" for path in paths.values()}
    roles[paths['1003']] = '1'

    def run(argv):
        if argv[-4:-2] == [guest_fixture.ACCOUNTS_INTERFACE, "FindUserById"]:
            return f'o "{paths[argv[-1]]}"'
        if "get-property" in argv:
            path, name = argv[-3], argv[-1]
            values = {"LocalAccount": "b true", "SystemAccount": "b false",
                      "AccountType": "i " + roles[path]}
            return values[name]
        assert argv[-4:] == [guest_fixture.USER_INTERFACE, "SetAccountType", "i", "1"]
        roles[argv[-5]] = "1"
        return ""

    guard = Mock()
    monkeypatch.setattr(guest_fixture.guest, "guard", guard)
    monkeypatch.setattr(guest_fixture.guest, "run", Mock(side_effect=run))
    monkeypatch.setattr(guest_fixture.pwd, "getpwall", Mock(return_value=identities))

    guest_fixture.prepare_empty()

    assert roles == {path: ("0" if uid == "1004" else "1")
                     for uid, path in paths.items()}
    assert guard.call_count == 4


@pytest.mark.parametrize('fault', ['missing-child', 'extra-account', 'substituted-account'])
def test_guest_empty_fixture_refuses_an_unexpected_eligible_set_before_mutation(monkeypatch, fault):
    names = (*guest_fixture.FIXED_CHILDREN, guest_fixture.KIOSK_USERNAME, 'unrelated-standard')
    identities = [SimpleNamespace(pw_name=name, pw_uid=index, pw_shell="/bin/bash")
                  for index, name in enumerate(names, 1001)]
    monkeypatch.setattr(guest_fixture.pwd, "getpwall", Mock(return_value=identities))
    monkeypatch.setattr(guest_fixture, "account_path", lambda uid: f"/org/freedesktop/Accounts/User{uid}")
    roles = {1001: '0', 1002: '0', 1003: '0', 1004: '1'}
    if fault in ('missing-child', 'substituted-account'): roles[1002] = '1'
    if fault in ('extra-account', 'substituted-account'): roles[1004] = '0'
    def property_value(path, name, signature):
        uid = int(path.rsplit('User', 1)[1])
        return {'LocalAccount': 'true', 'SystemAccount': 'false', 'AccountType': roles[uid]}[name]
    monkeypatch.setattr(guest_fixture, 'property_value', property_value)
    run = Mock()
    monkeypatch.setattr(guest_fixture.guest, "run", run)
    monkeypatch.setattr(guest_fixture.guest, "guard", Mock())

    counts = {'missing-child': (1, 1), 'extra-account': (3, 2), 'substituted-account': (2, 1)}
    eligible, fixed = counts[fault]
    with pytest.raises(guest_fixture.guest.GuestError,
                       match=f'^empty-account:baseline:eligible={eligible}:fixed={fixed}$'):
        guest_fixture.prepare_empty()

    run.assert_not_called()


def test_controller_empty_fixture_is_single_use_and_guarded():
    run = "b" * 32
    transport = Mock()
    transport.call.return_value = b"onpc-e2e: stage=empty-account outcome=prepared\n"
    context = SimpleNamespace(lease=SimpleNamespace(state={"run": run}))
    journey = SimpleNamespace(context=context, transport=transport)
    guard = Mock()
    fixture = account_fixture.EmptyAccountFixture(context)

    assert fixture.prepare(journey, guard) == {"eligible_accounts_removed": 2}
    assert guard.call_count == 2
    argv = transport.call.call_args.args[0]
    assert argv[-2].endswith("/e2e_dynamic_account.py") and argv[-1] == "prepare-empty"
    assert argv[1] == "ONPC_EXPECTED_RUN=" + run
    with pytest.raises(EvidenceError, match="controller-state"):
        fixture.prepare(journey, guard)
    transport.call.assert_called_once()
