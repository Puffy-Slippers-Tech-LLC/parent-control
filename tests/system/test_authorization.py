"""Installed system-bus assertions; run only through the guarded VM runner."""

import json
from pathlib import Path
import pwd

import pytest

import system_guest as guest
from system_caller import FixturePassword, PersistentCaller, TextAgent

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]
DENIED = guest.BUS + '.Error.AccessDenied'
ROLES = ('child1', 'child2', 'parent1', 'parent2', 'kiosk', 'unrelated', 'locked')
METHODS = (
    'ListManagedUsers', 'ListApprovers', 'GetOwnAccount', 'GetPreferences',
    'ListApplications', 'GetTimeStatus', 'CalculateRemainingTime',
    'CalculateOwnRemainingTime', 'PrepareOwnSession', 'UpdateRequestPreferences',
    'SetRequestMuted', 'SetPreferences', 'SetParentControl', 'RevokeOneTimeGrant',
    'RequestOwnAccess', 'RequestAccess', 'LogEvent',
)


def batch(uid, operations):
    raw = guest.commands.run(
        ['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_caller.py')],
        input=json.dumps({'uid': uid, 'operations': operations}).encode(),
        timeout=180, merge_stderr=False)
    reply = json.loads(raw)
    guest.require(reply['uid'] == uid and len(reply['replies']) == len(operations), 'caller:reply')
    return reply['replies']


def call(uid, method, signature='()', args=()):
    return batch(uid, [{'kind': 'call', 'method': method, 'signature': signature, 'args': args}])[0]


def accepted(reply):
    # Avoid pytest printing account data from a reply on failure.
    guest.require('result' in reply, 'authorization:expected-success:' + reply.get('error', 'malformed'))
    return reply['result']


@pytest.fixture(scope='module')
def accounts():
    guest.guard()
    guest.enable_diagnostics()
    names = dict(child1='onpc-child-riley', child2='onpc-child-jordan',
                 parent1='onpc-parent-jamie', parent2='onpc-parent-casey')
    # Refuse collisions. The retained baseline is the account cleanup boundary.
    for role, options in (
        ('unrelated', ['--create-home', '--shell', '/bin/bash']),
        ('locked', ['--create-home', '--shell', '/bin/bash', '--groups', 'sudo']),
        ('noninteractive', ['--no-create-home', '--shell', '/usr/sbin/nologin']),
        ('system', ['--system', '--no-create-home', '--shell', '/usr/sbin/nologin']),
    ):
        name = 'onpc-auth-' + role
        try:
            pwd.getpwnam(name)
        except KeyError:
            pass
        else:
            raise guest.GuestError('authorization:fixture-collision')
        guest.run(['useradd', *options, name])
        names[role] = name
    values = {role: pwd.getpwnam(name).pw_uid for role, name in names.items()}
    values['kiosk'] = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())['kiosk_uid']
    # Preserve the public dependency's real caller boundary alongside product
    # results. Raw replies stay in the existing private/redacted diagnostics;
    # this probe never substitutes for a successful GetTimeStatus assertion.
    query = ['busctl', '--system', 'call', 'org.freedesktop.MalcontentTimer1',
             '/org/freedesktop/MalcontentTimer1',
             'org.freedesktop.MalcontentTimer1.Parent', 'QueryUsage', 'uss',
             str(values['child1']), 'login-session', '']
    for role in ('root', 'parent1', 'child1', 'kiosk'):
        prefix = [] if role == 'root' else [
            'runuser', '--user', pwd.getpwuid(values[role]).pw_name, '--']
        guest.commands.run(prefix + query, timeout=45, check=False, merge_stderr=False)
        print(f'onpc-system: stage=usage-boundary role={role} '
              f'exit={guest.commands.last_returncode}', flush=True)
    # Empty policies exercise authorization without selecting application processes.
    for role in ('child1', 'child2', 'unrelated'):
        accepted(call(values['parent1'], 'SetParentControl', '(ubu)', (values[role], False, 60)))
    print('onpc-system: stage=authorization-accounts outcome=ready')
    return values


def invocation(method, role, accounts):
    child = role in ('child1', 'child2', 'unrelated')
    target = accounts[role] if child else accounts['child1']
    parent = role in ('parent1', 'parent2', 'locked')
    manager = parent or role == 'kiosk'
    component = 'parent' if parent else 'kiosk' if role == 'kiosk' else 'child'
    specs = {
        'ListManagedUsers': ('()', (), manager),
        'ListApprovers': ('()', (), True),
        'GetOwnAccount': ('()', (), child),
        'GetPreferences': ('(u)', (target,), True),
        'ListApplications': ('(u)', (target,), parent),
        'GetTimeStatus': ('(uu)', (target, 0), True),
        'CalculateRemainingTime': ('(uuuu)', (target, 10, 0, 5), True),
        'CalculateOwnRemainingTime': ('(u)', (10,), child),
        'PrepareOwnSession': ('()', (), child),
        'UpdateRequestPreferences': ('(usdbu)', (target, '300', 5.0, False, accounts['parent1']), True),
        'SetRequestMuted': ('(usb)', (target, 'child' if child else 'kiosk', True), True),
        'SetParentControl': ('(ubu)', (target, False, 60), parent),
        'RevokeOneTimeGrant': ('(u)', (target,), parent),
        # Disabled children must be denied before authentication. Enabled and
        # in-flight cases are separate tests, not acceptance inferred from this cell.
        'RequestOwnAccess': ('(uub)', (accounts['parent1'], 300, False), False),
        'RequestAccess': ('(uuub)', (target, accounts['parent1'], 300, False), role == 'kiosk'),
        'LogEvent': ('(sss)', (component, 'INFO', 'authorization matrix [Test user]'), True),
    }
    if method == 'SetPreferences':
        current = accepted(call(accounts['parent1'], 'GetPreferences', '(u)', (target,)))[0]
        return '(us)', (target, current), parent
    return specs[method]


@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('method', METHODS)
def test_method_role_matrix(accounts, role, method):
    signature, args, allowed = invocation(method, role, accounts)
    reply = call(accounts[role], method, signature, args)
    if allowed:
        result = accepted(reply)
        if method == 'GetOwnAccount':
            guest.require(result[0] == accounts[role], 'authorization:own-target')
        elif method == 'RequestAccess':
            guest.require(result[1] in ('denied', 'cancelled'), 'authorization:agentless-grant')
    else:
        guest.require(reply.get('error') == DENIED, 'authorization:expected-denial')


@pytest.mark.parametrize('role', ('child1', 'child2', 'unrelated'))
@pytest.mark.parametrize('method', ('GetPreferences', 'GetTimeStatus', 'CalculateRemainingTime',
                                  'UpdateRequestPreferences', 'SetRequestMuted'))
def test_cross_child_targets_fail_closed(accounts, role, method):
    signature, args, _ = invocation(method, role, accounts)
    other = accounts['child2'] if role == 'child1' else accounts['child1']
    before = accepted(call(accounts['parent1'], 'GetPreferences', '(u)', (other,)))
    reply = call(accounts[role], method, signature, (other, *args[1:]))
    guest.require(reply.get('error') == DENIED, 'authorization:cross-child-denial')
    after = accepted(call(accounts['parent1'], 'GetPreferences', '(u)', (other,)))
    guest.require(before == after, 'authorization:cross-child-write')


@pytest.mark.parametrize('role', ROLES)
def test_private_records_and_log_components(accounts, role):
    replies = batch(accounts[role], [
        {'kind': 'private-read', 'target': accounts[target]} for target in ('child1', 'child2')])
    guest.require(all(reply == {'readable': False} for reply in replies), 'authorization:private-record')
    own = 'parent' if role in ('parent1', 'parent2', 'locked') else 'kiosk' if role == 'kiosk' else 'child'
    for component in {'parent', 'child', 'kiosk', 'broker'} - {own}:
        reply = call(accounts[role], 'LogEvent', '(sss)', (component, 'INFO', 'forbidden component test'))
        guest.require(reply.get('error') == DENIED, 'authorization:log-impersonation')


def test_account_discovery_after_installation(accounts):
    for role in ('parent1', 'kiosk'):
        children = accepted(call(accounts[role], 'ListManagedUsers'))[0]
        approvers = accepted(call(accounts[role], 'ListApprovers'))[0]
        child_uids, approver_uids = {row[0] for row in children}, {row[0] for row in approvers}
        guest.require({accounts[key] for key in ('child1', 'child2', 'unrelated')} <= child_uids,
                      'authorization:discovery-missing-child')
        guest.require(not child_uids & {accounts[key] for key in (
            'parent1', 'parent2', 'locked', 'kiosk', 'noninteractive', 'system')},
            'authorization:discovery-ineligible-child')
        guest.require({accounts['parent1'], accounts['parent2']} <= approver_uids and
                      not approver_uids & {accounts[key] for key in (
                          'locked', 'kiosk', 'noninteractive', 'system', 'child1', 'child2', 'unrelated')},
                      'authorization:discovery-ineligible-approver')
        for rows in (children, approvers):
            guest.require(rows == sorted(rows, key=lambda row: (row[1].casefold(), row[0])),
                          'authorization:discovery-sort')
            guest.require(all(isinstance(row[2], str) and (not row[2] or row[2].startswith('/'))
                              for row in rows), 'authorization:icon-path')


def account_property(uid, interface, prop):
    return json.loads(guest.run([
        'busctl', '--system', '--json=short', 'get-property',
        'org.freedesktop.Accounts', f'/org/freedesktop/Accounts/User{uid}',
        interface, prop]))['data']


def account_state(uid):
    # Snapshot authoritative enforcement and private preferences without exposing
    # their contents to pytest assertions or diagnostics.
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
               'FindUserById', 'x', str(uid)])
    record = Path('/var/lib/oh-no-parent-control/preferences') / f'{uid}.json'
    return (
        record.read_bytes() if record.exists() else None,
        *(account_property(uid, 'com.endlessm.ParentalControls.SessionLimits', prop)
          for prop in ('LimitType', 'DailyLimit', 'ActiveExtension')),
        account_property(uid, 'com.endlessm.ParentalControls.AppFilter', 'AppFilter'),
    )


@pytest.mark.parametrize('role', ('noninteractive', 'system'))
@pytest.mark.parametrize('method', METHODS)
def test_ineligible_callers_cannot_use_broker(accounts, role, method):
    signature, args, _ = invocation(method, role, accounts)
    reply = call(accounts[role], method, signature, args)
    guest.require(reply.get('error') == DENIED, 'authorization:ineligible-caller')


@pytest.mark.parametrize('role', ('parent1', 'locked', 'kiosk', 'noninteractive', 'system'))
@pytest.mark.parametrize('method', ('GetPreferences', 'SetParentControl', 'RequestAccess'))
def test_ineligible_targets_fail_closed(accounts, role, method):
    caller = 'kiosk' if method == 'RequestAccess' else 'parent1'
    signature, args, _ = invocation(method, caller, accounts)
    before = account_state(accounts[role])
    reply = call(accounts[caller], method, signature, (accounts[role], *args[1:]))
    guest.require(reply.get('error') == DENIED, 'authorization:ineligible-target')
    guest.require(account_state(accounts[role]) == before, 'authorization:ineligible-target-write')


@pytest.mark.parametrize('role', ('child1', 'child2'))
def test_enabled_child_request_reaches_authentication_without_grant(accounts, role):
    target = accounts[role]
    accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, True, 60)))
    try:
        before = {key: account_state(accounts[key]) for key in ROLES}
        result = accepted(call(target, 'RequestOwnAccess', '(uub)',
                               (accounts['parent1'], 300, False)))
        guest.require(result[1] in ('denied', 'cancelled') and result[2] == 0,
                      'authorization:enabled-agentless-request')
        guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                      'authorization:denied-request-write')
    finally:
        accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, False, 60)))


@pytest.mark.parametrize('target_role', ('child1', 'parent1', 'parent2'))
def test_icons_match_authoritative_account_properties(accounts, target_role):
    target = accounts[target_role]
    method = 'ListManagedUsers' if target_role == 'child1' else 'ListApprovers'
    path = f'/org/freedesktop/Accounts/User{target}'
    for icon in ('/usr/share/oh-no-parent-control/app_logo.png', ''):
        guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts', path,
                   'org.freedesktop.Accounts.User', 'SetIconFile', 's', icon])
        expected = account_property(target, 'org.freedesktop.Accounts.User', 'IconFile')
        guest.require(bool(expected) == bool(icon), 'authorization:icon-fixture')
        for role in ('parent1', 'kiosk'):
            rows = accepted(call(accounts[role], method))[0]
            matches = [row for row in rows if row[0] == target]
            guest.require(len(matches) == 1 and matches[0][2] == expected,
                          'authorization:authoritative-list-icon')
        if target_role == 'child1':
            own = accepted(call(target, 'GetOwnAccount'))
            guest.require(own[2] == expected, 'authorization:authoritative-own-icon')


@pytest.mark.parametrize('surface', ('child1', 'kiosk'))
@pytest.mark.parametrize('approver', (
    'child1', 'child2', 'unrelated', 'locked', 'kiosk', 'noninteractive', 'system'))
def test_ineligible_selected_approvers_fail_closed(accounts, surface, approver):
    target = accounts['child1']
    accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, True, 60)))
    try:
        before = {key: account_state(accounts[key]) for key in ROLES}
        if surface == 'child1':
            reply = call(target, 'RequestOwnAccess', '(uub)',
                         (accounts[approver], 300, False))
        else:
            reply = call(accounts['kiosk'], 'RequestAccess', '(uuub)',
                         (target, accounts[approver], 300, False))
        guest.require(reply.get('error') == DENIED, 'authorization:ineligible-approver')
        guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                      'authorization:ineligible-approver-write')
    finally:
        accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, False, 60)))


def test_management_changes_preserve_other_accounts(accounts):
    before = {key: account_state(accounts[key]) for key in ROLES if key != 'child1'}
    target = accounts['child1']
    accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, True, 37)))
    accepted(call(target, 'UpdateRequestPreferences', '(usdbu)',
                  (target, 'custom', 10.0, True, accounts['parent2'])))
    accepted(call(accounts['parent1'], 'RevokeOneTimeGrant', '(u)', (target,)))
    accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, False, 60)))
    guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                  'authorization:management-cross-account-write')


@pytest.mark.parametrize('role,method,original,changed', (
    ('parent2', 'ListManagedUsers', 1, 0),
    ('child2', 'GetOwnAccount', 0, 1),
))
def test_persistent_caller_revalidates_changed_role(accounts, role, method, original, changed):
    target = accounts[role]
    interface = 'org.freedesktop.Accounts.User'
    path = f'/org/freedesktop/Accounts/User{target}'
    guest.require(account_property(target, interface, 'AccountType') == original,
                  'authorization:role-fixture')
    before = {key: account_state(accounts[key]) for key in ROLES}
    with PersistentCaller(target) as caller:
        accepted(caller.call(method))
        try:
            guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts', path,
                       interface, 'SetAccountType', 'i', str(changed)])
            guest.require(account_property(target, interface, 'AccountType') == changed,
                          'authorization:role-change-not-visible')
            reply = caller.call(method)
            guest.require(reply.get('error') == DENIED, 'authorization:stale-caller-role')
            guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                          'authorization:stale-role-write')
        finally:
            guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts', path,
                       interface, 'SetAccountType', 'i', str(original)])
        accepted(caller.call(method))


@pytest.fixture(scope='module')
def passwords(accounts):
    values = {role: FixturePassword() for role in ('parent1', 'parent2')}
    for role, password in values.items():
        password.install(accounts[role])
    return values


@pytest.fixture
def authentication_diagnostics(request, record_testsuite_property):
    """Retain safe per-attempt evidence even when an authentication assertion fails."""
    attempt = 0

    def record(*, expected, outcome, helper_category):
        nonlocal attempt
        attempt += 1
        # This public fixture supports xunit2. Suite properties include the
        # registered case ID because multiple tests can authenticate in a phase.
        record_testsuite_property('onpc.authentication', json.dumps({
            'case_id': request.node.name, 'attempt': attempt,
            'expected': expected, 'outcome': outcome, 'helper_category': helper_category,
        }, sort_keys=True))

    return record


@pytest.mark.parametrize('surface', ('child1', 'kiosk'))
@pytest.mark.parametrize('mutation', ('child-role', 'approver-role', 'preferences'))
def test_authenticated_request_revalidates_live_state(accounts, passwords, surface, mutation,
                                                     authentication_diagnostics):
    """Authenticate successfully after a real, observable mid-prompt change."""
    target = accounts['child1']
    selected, other = accounts['parent1'], accounts['parent2']
    accepted(call(other, 'SetParentControl', '(ubu)', (target, True, 0)))
    original_preferences = accepted(call(other, 'GetPreferences', '(u)', (target,)))[0]
    changed_uid = target if mutation == 'child-role' else selected
    original_role = 0 if mutation == 'child-role' else 1
    interface = 'org.freedesktop.Accounts.User'
    path = f'/org/freedesktop/Accounts/User{changed_uid}'
    role_changed = False
    try:
        with PersistentCaller(accounts[surface]) as caller, TextAgent(
                caller, record_diagnostic=authentication_diagnostics) as agent:
            caller.send({
                'kind': 'call',
                'method': 'RequestOwnAccess' if surface == 'child1' else 'RequestAccess',
                'signature': '(uub)' if surface == 'child1' else '(uuub)',
                'args': (selected, 300, False) if surface == 'child1' else
                        (target, selected, 300, False),
            })
            agent.prompt(selected, other)
            if mutation == 'preferences':
                saved = json.loads(original_preferences)
                accepted(call(other, 'SetRequestMuted', '(usb)',
                              (target, 'child', not saved['request']['child_muted'])))
                current = accepted(call(other, 'GetPreferences', '(u)', (target,)))[0]
                guest.require(current != original_preferences,
                              'authorization:inflight-preferences-not-visible')
            else:
                # Changing the role leaves the password valid. A completed PAM
                # challenge must therefore be rejected by broker revalidation,
                # not merely fail because the selected account was locked.
                guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                           path, interface, 'SetAccountType', 'i', str(1 - original_role)])
                role_changed = True
                guest.require(account_property(changed_uid, interface, 'AccountType') ==
                              1 - original_role, 'authorization:inflight-role-not-visible')
            print(f'onpc-system: stage=inflight-mutation kind={mutation} outcome=visible',
                  flush=True)
            # Snapshot after the intentional mutation, before releasing the
            # password prompt. No grant, filter or other-account write is allowed.
            before = {key: account_state(accounts[key]) for key in ROLES}
            agent.authenticate(passwords['parent1'])
            reply = caller.receive()
            guest.require(reply.get('error') == DENIED,
                          'authorization:authenticated-stale-request')
            guest.require(all(account_state(accounts[key]) == state
                              for key, state in before.items()),
                          'authorization:authenticated-stale-request-write')
            print('onpc-system: stage=inflight-revalidation outcome=denied-state-preserved',
                  flush=True)
    finally:
        if role_changed:
            guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                       path, interface, 'SetAccountType', 'i', str(original_role)])
        accepted(call(other, 'SetPreferences', '(us)', (target, original_preferences)))
        accepted(call(other, 'SetParentControl', '(ubu)', (target, False, 60)))


@pytest.mark.parametrize('surface', ('child1', 'kiosk'))
def test_real_selected_parent_authentication(accounts, passwords, surface,
                                            authentication_diagnostics):
    target = accounts['child1']
    selected, other = accounts['parent1'], accounts['parent2']
    accepted(call(selected, 'SetParentControl', '(ubu)', (target, True, 0)))
    try:
        before = {key: account_state(accounts[key]) for key in ROLES}
        with PersistentCaller(accounts[surface]) as caller, TextAgent(
                caller, record_diagnostic=authentication_diagnostics) as agent:
            operation = {
                'kind': 'call',
                'method': 'RequestOwnAccess' if surface == 'child1' else 'RequestAccess',
                'signature': '(uub)' if surface == 'child1' else '(uuub)',
                'args': (selected, 300, False) if surface == 'child1' else
                        (target, selected, 300, False),
            }
            caller.send(operation)
            agent.prompt(selected, other)
            agent.authenticate(passwords['parent2'], succeeds=False)
            result = accepted(caller.receive())
            guest.require(result[1] in ('denied', 'cancelled') and
                          (surface == 'kiosk' or result[2] == 0),
                          'authorization:wrong-parent-password')
            guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                          'authorization:wrong-password-write')
            caller.send(operation)
            agent.prompt(selected, other)
            agent.authenticate(passwords['parent1'])
            result = accepted(caller.receive())
            guest.require(result[1] == 'approved' and
                          (surface == 'kiosk' or result[2] > 0),
                          'authorization:real-authentication-grant')
            grant = account_property(target, 'com.endlessm.ParentalControls.SessionLimits',
                                     'ActiveExtension')
            guest.require(grant[0] > 0 and grant[1] >= 300,
                          'authorization:real-authentication-live-grant')
            agent.close()
            caller.send({'kind': 'account-type-write', 'target': accounts['child2']})
            reply = caller.receive()
            guest.require(reply.get('error') == 'org.freedesktop.Accounts.Error.PermissionDenied',
                          'authorization:approval-accounts-authority')
            guest.require(account_property(accounts['child2'], 'org.freedesktop.Accounts.User',
                                           'AccountType') == 0,
                          'authorization:approval-accounts-role-write')
            for method in ('SetPreferences', 'SetParentControl', 'RevokeOneTimeGrant'):
                signature, args, _ = invocation(method, surface, accounts)
                reply = caller.call(method, signature, args)
                guest.require(reply.get('error') == DENIED,
                              'authorization:approval-management-authority')
            guest.require(all(account_state(accounts[key]) == state
                              for key, state in before.items() if key != 'child1'),
                          'authorization:approved-cross-account-write')
    finally:
        accepted(call(selected, 'SetParentControl', '(ubu)', (target, False, 60)))
