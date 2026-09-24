"""The E2E-003 fixture is fixed, guarded and collision-safe."""

import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import account_fixture
from accessible_ui import CHILD_ACCOUNTS, NEW_CHILD
import e2e_dynamic_account as guest_fixture
from private_artifacts import EvidenceError


def test_dynamic_child_ui_lookup_uses_the_created_account():
    assert CHILD_ACCOUNTS[NEW_CHILD] == guest_fixture.USERNAME


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


def no_approver_guest(monkeypatch, fault=None):
    names = [*guest_fixture.FIXED_CHILDREN, *guest_fixture.FIXED_APPROVERS,
             guest_fixture.KIOSK_USERNAME]
    if fault == 'missing-parent':
        names.remove(guest_fixture.FIXED_APPROVERS[1])
    if fault == 'extra-parent':
        names.append('unrelated-admin')
    identities = [SimpleNamespace(pw_name=name, pw_uid=index, pw_shell='/bin/bash')
                  for index, name in enumerate(names, 1001)]
    if fault == 'duplicate-uid':
        identities[-1].pw_uid = identities[0].pw_uid
    records = {f'/org/freedesktop/Accounts/User{entry.pw_uid}': {
        'Uid': str(entry.pw_uid), 'UserName': entry.pw_name,
        'LocalAccount': 'true', 'SystemAccount': 'false',
        'AccountType': '1' if entry.pw_name in (*guest_fixture.FIXED_APPROVERS,
                                              'unrelated-admin') else '0',
        'Locked': 'false', 'Shell': '/bin/bash',
    } for entry in identities}
    parent = next(value for value in records.values()
                  if value['UserName'] == guest_fixture.FIXED_APPROVERS[0])
    mutations = {
        'locked-parent': ('Locked', 'true'), 'standard-parent': ('AccountType', '0'),
        'remote-parent': ('LocalAccount', 'false'), 'system-parent': ('SystemAccount', 'true'),
        'noninteractive-parent': ('Shell', '/usr/sbin/nologin'),
        'wrong-uid': ('Uid', '9999'), 'wrong-name': ('UserName', 'unrelated'),
    }
    if fault in mutations:
        key, value = mutations[fault]
        parent[key] = value
    if fault == 'wrong-child':
        records['/org/freedesktop/Accounts/User1001']['AccountType'] = '1'
    if fault == 'system-child':
        records['/org/freedesktop/Accounts/User1001']['SystemAccount'] = 'true'
    if fault == 'station-admin':
        records['/org/freedesktop/Accounts/User1005']['AccountType'] = '1'
        records['/org/freedesktop/Accounts/User1005']['Locked'] = 'true'
    monkeypatch.setattr(guest_fixture.pwd, 'getpwall', Mock(return_value=identities))
    monkeypatch.setattr(guest_fixture, 'account_path',
                        lambda uid: f'/org/freedesktop/Accounts/User{uid}')
    monkeypatch.setattr(guest_fixture, 'property_value', lambda path, key, _: records[path][key])
    guard = Mock()
    monkeypatch.setattr(guest_fixture.guest, 'guard', guard)

    def run(argv):
        assert argv[:5] == ['busctl', '--system', 'call', guest_fixture.ACCOUNTS_NAME, argv[4]]
        assert argv[5:] == [guest_fixture.USER_INTERFACE, 'SetLocked', 'b', 'true']
        assert records[argv[4]]['AccountType'] == '1'
        if fault != 'failed-readback':
            records[argv[4]]['Locked'] = 'true'
        if fault == 'changed-child':
            records['/org/freedesktop/Accounts/User1001']['AccountType'] = '1'
        return ''
    mutation = Mock(side_effect=run)
    monkeypatch.setattr(guest_fixture.guest, 'run', mutation)
    return records, guard, mutation


def test_no_approver_changes_only_observed_parent_lock_state(monkeypatch, capsys):
    records, guard, mutation = no_approver_guest(monkeypatch)
    before = {path: dict(record) for path, record in records.items()}
    monkeypatch.setattr(guest_fixture.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(b'[1003,1004]')))
    guest_fixture.main(['prepare-no-approver'])
    assert mutation.call_count == 2
    assert guard.call_count >= 4
    for path, record in records.items():
        expected = dict(before[path])
        if record['UserName'] in guest_fixture.FIXED_APPROVERS:
            expected['Locked'] = 'true'
        assert record == expected
    assert capsys.readouterr().out == 'onpc-e2e: stage=no-approver outcome=prepared locked=2\n'


@pytest.mark.parametrize('fault', [
    'missing-parent', 'duplicate-uid', 'locked-parent', 'standard-parent',
    'remote-parent', 'system-parent', 'noninteractive-parent', 'wrong-uid', 'wrong-name',
    'wrong-child', 'system-child', 'station-admin',
])
def test_no_approver_refuses_unexpected_identity_before_mutation(monkeypatch, fault):
    _, _, mutation = no_approver_guest(monkeypatch, fault)
    with pytest.raises(guest_fixture.guest.GuestError, match='no-approver:'):
        guest_fixture.prepare_no_approver([1003, 1004])
    mutation.assert_not_called()


@pytest.mark.parametrize('fault, uids', [
    ('missing-parent', [1003]), ('extra-parent', [1003, 1004, 1006]),
    ('extra-parent', [1006]), ('locked-parent', [1004]),
    ('standard-parent', [1004]), ('remote-parent', [1004]),
    ('system-parent', [1004]), ('noninteractive-parent', [1004]),
])
def test_no_approver_accepts_any_nonempty_observed_set_and_preserves_others(
        monkeypatch, capsys, fault, uids):
    records, _, mutation = no_approver_guest(monkeypatch, fault)
    before = {path: dict(record) for path, record in records.items()}
    targets = {int(record['Uid']) for record in before.values()
               if record['LocalAccount'] == 'true' and record['SystemAccount'] == 'false'
               and record['AccountType'] == '1' and record['Locked'] == 'false'
               and record['Shell'] == '/bin/bash'}
    guest_fixture.prepare_no_approver(uids)
    assert mutation.call_count == len(targets)
    for path, record in records.items():
        expected = dict(before[path])
        if int(record['Uid']) in targets:
            expected['Locked'] = 'true'
        assert record == expected
    assert capsys.readouterr().out == (
        f'onpc-e2e: stage=no-approver outcome=prepared locked={len(targets)}\n')


@pytest.mark.parametrize('uids', [[], [1003, 1003], [True], ['1003'], [0],
                                [999], [2 ** 32], [9999], [1001], [1005], None])
def test_no_approver_refuses_invalid_missing_or_protected_public_targets(monkeypatch, uids):
    _, _, mutation = no_approver_guest(monkeypatch)
    with pytest.raises(guest_fixture.guest.GuestError, match='no-approver:'):
        guest_fixture.prepare_no_approver(uids)
    mutation.assert_not_called()


def test_no_approver_discovers_parents_without_canonical_names(monkeypatch):
    records, _, mutation = no_approver_guest(monkeypatch, 'extra-parent')
    for entry in guest_fixture.pwd.getpwall.return_value:
        if entry.pw_name in guest_fixture.FIXED_APPROVERS:
            entry.pw_name = 'some-parent-' + str(entry.pw_uid)
            records[f'/org/freedesktop/Accounts/User{entry.pw_uid}']['UserName'] = entry.pw_name
    guest_fixture.prepare_no_approver([1006])
    assert mutation.call_count == 3
    assert all(record['Locked'] == 'true' for record in records.values()
               if record['AccountType'] == '1')


@pytest.mark.parametrize('field,value', [('Shell', '/usr/bin/false'), ('Shell', '/sbin/nologin'),
                                       ('Locked', 'true'), ('LocalAccount', 'false'),
                                       ('SystemAccount', 'true'), ('AccountType', '0')])
def test_no_approver_discovery_preserves_ineligible_accounts(monkeypatch, field, value):
    records, _, mutation = no_approver_guest(monkeypatch, 'extra-parent')
    record = records['/org/freedesktop/Accounts/User1006']
    record[field] = value
    before = dict(record)
    guest_fixture.prepare_no_approver([1003])
    assert mutation.call_count == 2
    assert record == before


@pytest.mark.parametrize('fault', ['failed-readback', 'changed-child'])
def test_no_approver_refuses_failed_or_unrelated_changes(monkeypatch, capsys, fault):
    _, _, mutation = no_approver_guest(monkeypatch, fault)
    with pytest.raises(guest_fixture.guest.GuestError, match='no-approver:'):
        guest_fixture.prepare_no_approver([1003, 1004])
    assert mutation.call_count == (1 if fault == 'failed-readback' else 2)
    assert not capsys.readouterr().out


@pytest.mark.parametrize('boundary', [0, 1, 2])
def test_no_approver_guard_loss_stops_mutation(monkeypatch, boundary):
    _, guard, mutation = no_approver_guest(monkeypatch)
    guard.side_effect = [*[None] * boundary, guest_fixture.guest.GuestError('guard-refused')]
    with pytest.raises(guest_fixture.guest.GuestError, match='guard-refused'):
        guest_fixture.prepare_no_approver([1003, 1004])
    assert mutation.call_count == max(0, boundary - 1)


def test_no_approver_revalidates_target_identity_before_locking(monkeypatch):
    records, guard, mutation = no_approver_guest(monkeypatch)
    def change_target():
        if guard.call_count == 2:
            # Discovery locks all parents; Casey is the first mutation target.
            records['/org/freedesktop/Accounts/User1004']['UserName'] = 'replacement'
    guard.side_effect = change_target
    with pytest.raises(guest_fixture.guest.GuestError, match='target-changed'):
        guest_fixture.prepare_no_approver([1003])
    mutation.assert_not_called()


@pytest.mark.parametrize('raw', [b'', b'not json', b'[]', b'{}', b'1' * 65537])
def test_no_approver_cli_requires_valid_public_baseline(monkeypatch, raw):
    _, _, mutation = no_approver_guest(monkeypatch)
    monkeypatch.setattr(guest_fixture.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(raw)))
    with pytest.raises(guest_fixture.guest.GuestError):
        guest_fixture.main(['prepare-no-approver'])
    mutation.assert_not_called()


@pytest.mark.parametrize('uids', [(), (1003, 1003), (True,), ('1003',), None])
def test_no_approver_controller_requires_unconsumed_valid_baseline(uids):
    context = SimpleNamespace(lease=SimpleNamespace(state={'run': 'a' * 32}))
    journey = SimpleNamespace(context=context, transport=Mock(),
                              ui=SimpleNamespace(last_operation='kiosk-approver-baseline',
                                                 approver_uids=uids))
    with pytest.raises(EvidenceError, match='public-baseline'):
        account_fixture.NoApproverFixture(context).prepare(journey, Mock())
    journey.transport.call.assert_not_called()


@pytest.mark.parametrize('fault', ['context', 'transport', 'run', 'guard', 'reply', 'uncertain'])
def test_no_approver_controller_failure_never_replays(fault):
    transport = Mock()
    transport.call.return_value = b'onpc-e2e: stage=no-approver outcome=prepared locked=2\n'
    context = SimpleNamespace(lease=SimpleNamespace(state={'run': 'a' * 32}))
    journey = SimpleNamespace(context=context, transport=transport,
                              ui=SimpleNamespace(last_operation='kiosk-approver-baseline',
                                                 approver_uids=(1003, 1004)))
    guard = Mock()
    fixture = account_fixture.NoApproverFixture(context)
    if fault == 'context': journey.context = object()
    if fault == 'transport': journey.transport = None
    if fault == 'run': context.lease.state['run'] = 'invalid'
    if fault == 'guard': guard.side_effect = EvidenceError('guard')
    if fault == 'reply': transport.call.return_value = b'unexpected'
    if fault == 'uncertain': transport.call.side_effect = TimeoutError('uncertain')
    with pytest.raises((EvidenceError, TimeoutError)):
        fixture.prepare(journey, guard)
    with pytest.raises(EvidenceError):
        fixture.prepare(journey, guard)
    assert transport.call.call_count == (1 if fault in ('reply', 'uncertain') else 0)
