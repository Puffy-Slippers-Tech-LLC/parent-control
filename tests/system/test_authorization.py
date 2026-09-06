"""Installed system-bus assertions; run only through the guarded VM runner."""

import json
from pathlib import Path
import pwd

import pytest

import system_guest as guest

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
