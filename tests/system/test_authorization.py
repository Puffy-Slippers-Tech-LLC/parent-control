"""Installed system-bus assertions; run only through the guarded VM runner."""

import json
from pathlib import Path
import pwd
import re
import time

import pytest

import system_guest as guest
from system_caller import FixturePassword, PersistentCaller, TextAgent
from system_assertions import batch, call, accepted, account_property, account_state
from system_accounts import create_disposable_identity, delete_disposable_identity

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
    parent = role in ('parent1', 'parent2', 'locked', 'root')
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
    before = {key: account_state(accounts[key]) for key in ('child1', 'child2')}
    replies = batch(accounts[role], [
        {'kind': kind, 'target': accounts[target]}
        for target in ('child1', 'child2') for kind in ('private-read', 'private-write')])
    guest.require(replies == [{'readable': False}, {'writable': False}] * 2,
                  'authorization:private-record')
    guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                  'authorization:private-probe-write')
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






@pytest.fixture
def disposable_identities(accounts, record_testsuite_property):
    # Create both before deleting either, so this slice cannot reuse a deleted UID.
    values = {role: create_disposable_identity(role, record_testsuite_property)
              for role in ('target', 'approver')}
    FixturePassword().install(values['approver'])
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               f"/org/freedesktop/Accounts/User{values['approver']}",
               'org.freedesktop.Accounts.User', 'SetLocked', 'b', 'false'])
    guest.require(account_property(values['approver'], 'org.freedesktop.Accounts.User',
                                   'Locked') is False,
                  'authorization:deletion-fixture-approver-locked')
    accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)',
                  (values['target'], False, 60)))
    return values




def test_deleted_target_and_approver_fail_closed(accounts, disposable_identities,
                                               record_testsuite_property):
    """Stale selections fail on existing bus connections and preserve survivors."""
    target, approver = (disposable_identities[key] for key in ('target', 'approver'))
    parent = accounts['parent1']
    original = accepted(call(parent, 'GetPreferences', '(u)', (accounts['child1'],)))[0]
    accepted(call(parent, 'SetParentControl', '(ubu)', (accounts['child1'], True, 0)))
    try:
        with PersistentCaller(parent) as manager, PersistentCaller(accounts['kiosk']) as kiosk:
            callers = (manager, kiosk)

            def discovery():
                return tuple((
                    {row[0] for row in accepted(caller.call('ListManagedUsers'))[0]},
                    {row[0] for row in accepted(caller.call('ListApprovers'))[0]},
                ) for caller in callers)

            initial = discovery()
            guest.require(all(target in children and approver in parents
                              for children, parents in initial),
                          'authorization:deletion-fixtures-not-discovered')
            # Seed a real remembered selection before its administrator disappears.
            accepted(call(parent, 'UpdateRequestPreferences', '(usdbu)',
                          (accounts['child1'], '300', 5.0, False, approver)))
            saved_target = accepted(manager.call('GetPreferences', '(u)', (target,)))[0]
            before = {key: account_state(accounts[key]) for key in ROLES}
            approver_before = account_state(approver)
            record = Path('/var/lib/oh-no-parent-control/preferences') / f'{target}.json'
            delete_disposable_identity(target, 'target')
            record_testsuite_property('onpc.account-deletion', 'target:visible-in-nss-and-accountsservice')
            # Account removal may itself clean product state. Requests must not
            # recreate or change whatever state remains after that operation.
            deleted_record = record.read_bytes() if record.exists() else None
            guest.require(discovery() == tuple((children - {target}, parents)
                                              for children, parents in initial),
                          'authorization:deleted-target-discovery')
            specs = (
                ('GetPreferences', '(u)', (target,)),
                ('ListApplications', '(u)', (target,)),
                ('GetTimeStatus', '(uu)', (target, 0)),
                ('CalculateRemainingTime', '(uuuu)', (target, 10, 0, 5)),
                ('UpdateRequestPreferences', '(usdbu)', (target, '300', 5.0, False, approver)),
                ('SetRequestMuted', '(usb)', (target, 'kiosk', True)),
                ('SetPreferences', '(us)', (target, saved_target)),
                ('SetParentControl', '(ubu)', (target, False, 60)),
                ('RevokeOneTimeGrant', '(u)', (target,)),
            )
            for method, signature, args in specs:
                reply = manager.call(method, signature, args)
                guest.require(reply.get('error') == guest.BUS + '.Error.InvalidRequest',
                              'authorization:deleted-target:' + method)
            reply = kiosk.call('RequestAccess', '(uuub)', (target, approver, 300, False))
            guest.require(reply.get('error') == guest.BUS + '.Error.InvalidRequest',
                          'authorization:deleted-target-request')
            guest.require(account_state(approver) == approver_before,
                          'authorization:deleted-target-approver-write')
            delete_disposable_identity(approver, 'approver')
            record_testsuite_property('onpc.account-deletion', 'approver:visible-in-nss-and-accountsservice')
            guest.require(discovery() == tuple((children - {target}, parents - {approver})
                                              for children, parents in initial),
                          'authorization:deleted-approver-discovery')
            for surface in ('child1', 'kiosk'):
                reply = (call(accounts['child1'], 'RequestOwnAccess', '(uub)',
                              (approver, 300, False)) if surface == 'child1' else
                         kiosk.call('RequestAccess', '(uuub)',
                                    (accounts['child1'], approver, 300, False)))
                guest.require(reply.get('error') == guest.BUS + '.Error.InvalidRequest',
                              'authorization:deleted-approver-request:' + surface)
            guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                          'authorization:deleted-identity-survivor-write')
            guest.require((record.read_bytes() if record.exists() else None) == deleted_record,
                          'authorization:deleted-target-record-write')
            record_testsuite_property('onpc.deleted-identity-requests', 'denied-state-preserved')
            print('onpc-system: stage=deleted-identity-requests outcome=denied-state-preserved',
                  flush=True)
    finally:
        accepted(call(parent, 'SetPreferences', '(us)', (accounts['child1'], original)))
        accepted(call(parent, 'SetParentControl', '(ubu)', (accounts['child1'], False, 60)))


def test_root_method_permissions_and_approver_exclusion(accounts):
    """All root cells share one guarded case; every call verifies bus UID 0."""
    target = accounts['child1']
    original = accepted(call(accounts['parent1'], 'GetPreferences', '(u)', (target,)))[0]
    others = {key: account_state(accounts[key]) for key in ROLES if key != 'child1'}
    try:
        for method in METHODS:
            signature, args, allowed = invocation(method, 'root', accounts)
            if method == 'SetPreferences':
                desired = json.loads(args[1])
                desired['request']['child_muted'] = not desired['request']['child_muted']
                args = (target, json.dumps(desired))
            elif method == 'SetParentControl':
                args = (target, True, 37)
            before = account_state(target)
            reply = call(0, method, signature, args, allow_root=True)
            if allowed:
                result = accepted(reply)
                if method in ('ListManagedUsers', 'ListApprovers'):
                    uids = {row[0] for row in result[0]}
                    expected = ('child1', 'child2') if method == 'ListManagedUsers' else (
                        'parent1', 'parent2')
                    guest.require(0 not in uids and {accounts[key] for key in expected} <= uids,
                                  'authorization:root-discovery')
                elif method == 'SetPreferences':
                    saved = json.loads(accepted(call(accounts['parent1'], 'GetPreferences',
                                                    '(u)', (target,)))[0])
                    guest.require(saved == desired, 'authorization:root-preferences-not-applied')
                elif method == 'SetParentControl':
                    saved = json.loads(accepted(call(accounts['parent1'], 'GetPreferences',
                                                    '(u)', (target,)))[0])
                    guest.require(saved['parent_control_enabled'] and account_state(target) != before,
                                  'authorization:root-control-not-applied')
            else:
                guest.require(reply.get('error') == DENIED, 'authorization:root-request-only-denial')
                guest.require(account_state(target) == before, 'authorization:root-denial-write')
            guest.require(all(account_state(accounts[key]) == state for key, state in others.items()),
                          'authorization:root-cross-account-write')
            print(f'onpc-system: stage=root-method method={method} '
                  f'outcome={"allowed" if allowed else "denied"}', flush=True)

        # Root's management bypass cannot turn it into a selected approver.
        for surface in ('child1', 'kiosk'):
            before = account_state(target)
            method = 'RequestOwnAccess' if surface == 'child1' else 'RequestAccess'
            signature = '(uub)' if surface == 'child1' else '(uuub)'
            args = (0, 300, False) if surface == 'child1' else (target, 0, 300, False)
            reply = call(accounts[surface], method, signature, args)
            guest.require(reply.get('error') == DENIED, 'authorization:root-selected-approver')
            guest.require(account_state(target) == before and all(
                account_state(accounts[key]) == state for key, state in others.items()),
                'authorization:root-approver-denial-write')
        for component in ('child', 'kiosk', 'broker'):
            reply = call(0, 'LogEvent', '(sss)', (component, 'INFO', 'root component test'),
                         allow_root=True)
            guest.require(reply.get('error') == DENIED, 'authorization:root-log-impersonation')
    finally:
        accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, False, 60)))
        accepted(call(accounts['parent1'], 'SetPreferences', '(us)', (target, original)))


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


def test_administrator_eligibility_predicates(accounts, record_testsuite_property):
    """Isolate shell/name exclusions from role, locality, system and lock state."""
    guest.guard()
    interface = 'org.freedesktop.Accounts.User'
    target = accounts['child1']
    accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, True, 60)))
    try:
        for predicate in ('noninteractive', 'unsafe-name'):
            name = 'onpc-auth-check-' + predicate
            if predicate == 'unsafe-name':
                name = '1' + name
            guest.require(len(name.encode()) <= 32, 'authorization:eligibility-name-length')
            try:
                pwd.getpwnam(name)
            except KeyError:
                pass
            else:
                raise guest.GuestError('authorization:eligibility-fixture-collision')
            if predicate == 'unsafe-name':
                # Ubuntu useradd supports this name. Avoid renaming a cached
                # account: AccountsService can leave a duplicate exported object.
                guest.run(['useradd', '--create-home', '--shell', '/bin/bash',
                           '--groups', 'sudo', name])
            else:
                guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                           '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
                           'CreateUser', 'ssi', name, '', '1'])
            uid = pwd.getpwnam(name).pw_uid
            path = f'/org/freedesktop/Accounts/User{uid}'
            FixturePassword().install(uid)
            guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                       '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
                       'FindUserById', 'x', str(uid)])

            def observe(stage):
                # Exercise the same public resolution route as the broker, not
                # only a possibly stale previously exported object path.
                resolved = json.loads(guest.run([
                    'busctl', '--system', '--json=short', 'call', 'org.freedesktop.Accounts',
                    '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
                    'FindUserById', 'x', str(uid)]))['data']
                guest.require(resolved == [path], 'authorization:eligibility-resolution')
                observed = {prop: account_property(uid, interface, prop) for prop in (
                    'AccountType', 'LocalAccount', 'SystemAccount', 'Locked')}
                # Record predicates, never usernames, UIDs or credentials.
                shell = account_property(uid, interface, 'Shell')
                username = account_property(uid, interface, 'UserName')
                observed['interactive'] = shell == '/bin/bash'
                observed['safe_name'] = bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*[$]?', username))
                observed['nss_matches'] = (pwd.getpwuid(uid).pw_shell == shell and
                                           pwd.getpwuid(uid).pw_name == username)
                return observed

            def require_ready(stage):
                # useradd updates NSS synchronously, whereas AccountsService
                # reloads local accounts asynchronously. Re-resolve publicly
                # until locality is visible; never relax another predicate.
                started = time.monotonic()
                previous = None
                while True:
                    observed = observe(stage)
                    elapsed = time.monotonic() - started
                    finished = observed['LocalAccount'] or elapsed >= 10
                    if observed != previous or finished:
                        record_testsuite_property('onpc.eligibility-fixture', json.dumps({
                            'predicate': predicate, 'stage': stage,
                            'elapsed_seconds': round(elapsed, 3), **observed,
                        }, sort_keys=True))
                    if finished:
                        break
                    previous = observed
                    time.sleep(0.1)
                guest.require(uid >= 1000 and uid != accounts['kiosk'] and observed == {
                    'AccountType': 1, 'LocalAccount': True, 'SystemAccount': False,
                    'Locked': False, 'interactive': stage != 'excluded' or predicate != 'noninteractive',
                    'safe_name': stage != 'excluded' or predicate != 'unsafe-name',
                    'nss_matches': True,
                }, 'authorization:independent-eligibility:' + predicate + ':' + stage)

            guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts', path,
                       interface, 'SetShell', 's', '/bin/bash'])
            guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts', path,
                       interface, 'SetLocked', 'b', 'false'])
            if predicate == 'noninteractive':
                require_ready('eligible')
                for caller in ('parent1', 'child1', 'kiosk'):
                    guest.require(uid in {row[0] for row in accepted(call(
                        accounts[caller], 'ListApprovers'))[0]}, 'authorization:eligible-control')
                guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts', path,
                           interface, 'SetShell', 's', '/usr/sbin/nologin'])
            require_ready('excluded')
            before = {key: account_state(accounts[key]) for key in ROLES}
            for caller in ('parent1', 'child1', 'kiosk'):
                offered = {row[0] for row in accepted(call(accounts[caller], 'ListApprovers'))[0]}
                guest.require(uid not in offered and accounts['parent1'] in offered,
                              'authorization:predicate-discovery')
            for surface in ('child1', 'kiosk'):
                if surface == 'child1':
                    reply = call(target, 'RequestOwnAccess', '(uub)', (uid, 300, False))
                else:
                    reply = call(accounts['kiosk'], 'RequestAccess', '(uuub)',
                                 (target, uid, 300, False))
                record_testsuite_property('onpc.eligibility-denial', json.dumps({
                    'predicate': predicate, 'surface': surface,
                    'access_denied': reply.get('error') == DENIED,
                    'invalid_request': reply.get('error') == guest.BUS + '.Error.InvalidRequest',
                }, sort_keys=True))
                guest.require(reply.get('error') == DENIED,
                              'authorization:predicate-direct-selection:' + predicate + ':' + surface)
                guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                              'authorization:predicate-state-write')
                print(f'onpc-system: stage=eligibility predicate={predicate} '
                      f'surface={surface} outcome=denied', flush=True)
    finally:
        accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, False, 60)))


def test_remote_accounts_are_excluded(accounts, record_testsuite_property):
    """Real LDAP identities must be rejected solely for their nonlocal status."""
    from system_remote_accounts import PACKAGES, provision

    remote = provision()
    record_testsuite_property('onpc.remote-packages', guest.run([
        'dpkg-query', '-W', '-f=${Package}=${Version}\n',
        *[package.split('=')[0] for package in PACKAGES]]))
    interface = 'org.freedesktop.Accounts.User'
    for role, uid in remote.items():
        observed = {prop: account_property(uid, interface, prop) for prop in (
            'AccountType', 'LocalAccount', 'SystemAccount', 'Locked')}
        shell = account_property(uid, interface, 'Shell')
        name = account_property(uid, interface, 'UserName')
        observed.update(interactive=shell == '/bin/bash',
                        safe_name=bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*[$]?', name)),
                        nss_matches=pwd.getpwuid(uid).pw_name == name and
                        pwd.getpwuid(uid).pw_shell == shell)
        record_testsuite_property('onpc.remote-fixture', json.dumps({
            'role': role, **observed}, sort_keys=True))
        guest.require(uid >= 1000 and uid != accounts['kiosk'] and observed == {
            'AccountType': int(role == 'administrator'), 'LocalAccount': False,
            'SystemAccount': False, 'Locked': False, 'interactive': True,
            'safe_name': True, 'nss_matches': True,
        }, 'authorization:independent-remote-predicate:' + role)
    for caller in ('parent1', 'kiosk'):
        managed = {row[0] for row in accepted(call(accounts[caller], 'ListManagedUsers'))[0]}
        guest.require(not managed.intersection(remote.values()) and accounts['child1'] in managed,
                      'authorization:remote-child-discovery')
    for caller in ('parent1', 'child1', 'kiosk'):
        approvers = {row[0] for row in accepted(call(accounts[caller], 'ListApprovers'))[0]}
        guest.require(not approvers.intersection(remote.values()) and accounts['parent1'] in approvers,
                      'authorization:remote-approver-discovery')
    target = accounts['child1']
    accepted(call(accounts['parent1'], 'SetParentControl', '(ubu)', (target, True, 60)))
    try:
        before = {key: account_state(accounts[key]) for key in ROLES}
        attempts = (
            ('child-selected-parent', target, 'RequestOwnAccess', '(uub)',
             (remote['administrator'], 300, False)),
            ('kiosk-selected-parent', accounts['kiosk'], 'RequestAccess', '(uuub)',
             (target, remote['administrator'], 300, False)),
            ('kiosk-selected-child', accounts['kiosk'], 'RequestAccess', '(uuub)',
             (remote['child'], accounts['parent1'], 300, False)),
            ('parent-selected-child', accounts['parent1'], 'GetPreferences', '(u)',
             (remote['child'],)),
            ('remote-child-caller', remote['child'], 'GetOwnAccount', '()', ()),
            ('remote-admin-caller', remote['administrator'], 'ListManagedUsers', '()', ()),
        )
        for boundary, caller, method, signature, args in attempts:
            reply = call(caller, method, signature, args)
            record_testsuite_property('onpc.remote-denial', json.dumps({
                'boundary': boundary, 'access_denied': reply.get('error') == DENIED,
            }, sort_keys=True))
            guest.require(reply.get('error') == DENIED, 'authorization:remote-denial:' + boundary)
            guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                          'authorization:remote-state-write')
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


def test_requester_disconnect_during_approval(accounts, passwords,
                                            authentication_diagnostics,
                                            record_testsuite_property):
    """Requester exit cancels approval while its real authentication agent lives."""
    target = accounts['child1']
    selected, other = accounts['parent1'], accounts['parent2']

    def request_log_lines():
        # Read only guest product logs. Raw lines remain private; public evidence
        # contains fixed stages and the product's random request correlation ID.
        return {line for path in Path('/var/log/oh-no-parent-control/broker').glob('*.log')
                for line in path.read_text().splitlines() if 'request=' in line}

    for surface in ('child', 'kiosk'):
        accepted(call(other, 'SetParentControl', '(ubu)', (target, True, 0)))
        granted_at = None
        try:
            before = {key: account_state(accounts[key]) for key in ROLES}
            caller_uid = target if surface == 'child' else accounts['kiosk']
            with PersistentCaller(accounts['kiosk']) as observer, \
                    PersistentCaller(caller_uid) as caller, TextAgent(
                        caller, record_diagnostic=authentication_diagnostics) as agent:
                # Invalid duration is checked after acquiring the transaction
                # lock and before authentication or writes. This public method
                # is therefore a side-effect-free Busy -> InvalidRequest probe.
                def transaction_probe():
                    return observer.call('RequestAccess', '(uuub)',
                                         (target, selected, 1, False)).get('error')

                previous_lines = request_log_lines()
                operation = {
                    'kind': 'call',
                    'method': 'RequestOwnAccess' if surface == 'child' else 'RequestAccess',
                    'signature': '(uub)' if surface == 'child' else '(uuub)',
                    'args': (selected, 300, False) if surface == 'child' else
                            (target, selected, 300, False),
                }
                caller.send(operation)
                agent.prompt(selected, other)
                started = [match.group(1) for line in request_log_lines() - previous_lines
                           if (match := re.search(r'request=([0-9a-f-]{36}) .*kind=' +
                                                  surface + r' stage=authorize$', line))]
                guest.require(len(started) == 1, 'authorization:disconnect-request-correlation')
                correlation = started[0]
                guest.require(transaction_probe() == guest.BUS + '.Error.Busy',
                              'authorization:disconnect-prompt-transaction-not-active')

                caller.close()
                deadline = time.monotonic() + 10
                while True:
                    owner = json.loads(guest.run([
                        'busctl', '--system', '--json=short', 'call',
                        'org.freedesktop.DBus', '/org/freedesktop/DBus',
                        'org.freedesktop.DBus', 'NameHasOwner', 's', caller.name]))['data']
                    if owner == [False]:
                        break
                    guest.require(owner == [True] and time.monotonic() < deadline,
                                  'authorization:disconnect-bus-name-still-owned')
                    time.sleep(0.05)
                record_testsuite_property('onpc.requester-disconnect',
                                          surface + ':bus-name-gone-before-authentication')
                # Keep the registered agent alive and never enter a password.
                # The broker must cancel Polkit itself and release its lock.
                deadline = time.monotonic() + 10
                while True:
                    result = transaction_probe()
                    if result == guest.BUS + '.Error.InvalidRequest':
                        break
                    guest.require(result == guest.BUS + '.Error.Busy' and
                                  time.monotonic() < deadline,
                                  'authorization:disconnect-transaction-not-finished')
                    time.sleep(0.05)
                finished = request_log_lines() - previous_lines
                guest.require(any(line.endswith('request=' + correlation + ' outcome=cancelled')
                                  for line in finished),
                              'authorization:disconnect-terminal-outcome-missing')
                guest.require(any('request=' + correlation +
                                  ' authorization cancel-check outcome=accepted' in line
                                  for line in finished),
                              'authorization:disconnect-remote-cancellation-missing')
                guest.require(agent.child.poll() is None,
                              'authorization:disconnect-agent-did-not-survive')
                record_testsuite_property('onpc.requester-disconnect-agent',
                                          surface + ':alive-after-broker-cancellation')
                guest.require(not any('request=' + correlation + ' stage=' + stage in line
                                      for line in finished for stage in (
                                          'usage-query', 'limit-initialize', 'filter-write',
                                          'blocked-app-termination', 'extension-write')),
                              'authorization:disconnect-reached-write-pipeline')
                guest.require(all(account_state(accounts[key]) == state
                                  for key, state in before.items()),
                              'authorization:disconnect-account-state-write')
                record_testsuite_property('onpc.requester-disconnect-result', json.dumps({
                    'surface': surface, 'request': correlation,
                    'outcome': 'disconnected-cancelled-state-preserved',
                    'transaction': 'busy-then-released',
                }, sort_keys=True))
                print(f'onpc-system: stage=requester-disconnect surface={surface} '
                      'outcome=disconnected-cancelled-state-preserved', flush=True)

            # Use the same UID, selected parent, password, and displayed request
            # on a new bus connection. A real grant proves cancellation did not
            # consume the repeat interval or leave the broker blocked.
            with PersistentCaller(caller_uid) as fresh, TextAgent(
                    fresh, record_diagnostic=authentication_diagnostics) as agent:
                fresh.send(operation)
                agent.prompt(selected, other)
                agent.authenticate(passwords['parent1'])
                result = accepted(fresh.receive())
                guest.require(result[1] == 'approved', 'authorization:disconnect-retry-not-approved')
                granted_at = time.monotonic()
                extension = account_property(target,
                    'com.endlessm.ParentalControls.SessionLimits', 'ActiveExtension')
                guest.require(extension[0] > 0 and extension[1] >= 300,
                              'authorization:disconnect-retry-no-grant')
                guest.require(all(account_state(accounts[key]) == state
                                  for key, state in before.items() if key != 'child1'),
                              'authorization:disconnect-retry-other-account-write')
                record_testsuite_property('onpc.requester-disconnect-recovery',
                                          surface + ':fresh-connection-authenticated-and-granted')
                print(f'onpc-system: stage=requester-disconnect-recovery surface={surface} '
                      'outcome=approved', flush=True)
        finally:
            accepted(call(other, 'RevokeOneTimeGrant', '(u)', (target,)))
            accepted(call(other, 'SetParentControl', '(ubu)', (target, False, 60)))
            if granted_at is not None:
                # The successful control must not rate-limit a later registered
                # case using the same child/kiosk UID. Let the real interval
                # elapse; never reset broker state or alter product configuration.
                interval = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())[
                    'minimum_request_interval_seconds']
                time.sleep(max(0, granted_at + interval - time.monotonic()))


def test_authenticated_request_rejects_deleted_target(accounts, passwords,
                                                      authentication_diagnostics,
                                                      record_testsuite_property):
    """Both real request surfaces reject deletion after successful authentication."""
    # Allocate before either deletion, keeping each target's UID distinct even
    # when the OS would otherwise reuse the most recently deleted account.
    targets = {surface: create_disposable_identity(
        'target', record_testsuite_property, surface=surface) for surface in ('child', 'kiosk')}
    guest.require(len(set(targets.values())) == 2, 'authorization:deletion-target-isolation')
    selected, other = accounts['parent1'], accounts['parent2']
    for target in targets.values():
        accepted(call(other, 'SetParentControl', '(ubu)', (target, True, 0)))

    surviving_targets = set(targets.values())
    for surface, target in targets.items():
        caller_uid = target if surface == 'child' else accounts['kiosk']
        with PersistentCaller(caller_uid) as caller, TextAgent(
                caller, record_diagnostic=authentication_diagnostics) as agent:
            caller.send({
                'kind': 'call',
                'method': 'RequestOwnAccess' if surface == 'child' else 'RequestAccess',
                'signature': '(uub)' if surface == 'child' else '(uuub)',
                'args': (selected, 300, False) if surface == 'child' else
                        (target, selected, 300, False),
            })
            agent.prompt(selected, other)
            delete_disposable_identity(target, 'target', surface=surface)
            surviving_targets.remove(target)
            record_testsuite_property('onpc.inflight-target-deletion',
                                      surface + ':visible-before-authentication')
            # Keep requester disconnect separate from deletion revalidation.
            # The real bus still owns the same name and kernel caller UID.
            def require_connected():
                observed = json.loads(guest.run([
                    'busctl', '--system', '--json=short', 'call',
                    'org.freedesktop.DBus', '/org/freedesktop/DBus',
                    'org.freedesktop.DBus', 'GetConnectionUnixUser', 's', caller.name]))['data']
                guest.require(observed == [caller_uid], 'authorization:deleted-target-caller-lost')

            require_connected()
            survivor_uids = {accounts[role] for role in ROLES} | surviving_targets
            before = {uid: account_state(uid) for uid in survivor_uids}
            record = Path('/var/lib/oh-no-parent-control/preferences') / f'{target}.json'
            deleted_record = record.read_bytes() if record.exists() else None
            agent.authenticate(passwords['parent1'])
            reply = caller.receive()
            guest.require(reply.get('error') == guest.BUS + '.Error.InvalidRequest',
                          'authorization:authenticated-deleted-target:' + surface)
            require_connected()
            guest.require(all(account_state(uid) == state for uid, state in before.items()),
                          'authorization:authenticated-deleted-target-survivor-write:' + surface)
            guest.require((record.read_bytes() if record.exists() else None) == deleted_record,
                          'authorization:authenticated-deleted-target-record-write:' + surface)
            guest.require(target not in {row[0] for row in accepted(
                call(other, 'ListManagedUsers'))[0]},
                'authorization:authenticated-deleted-target-reappeared:' + surface)
            record_testsuite_property('onpc.inflight-target-result',
                                      surface + ':authenticated-invalid-request-state-preserved')
            print(f'onpc-system: stage=inflight-target-deletion surface={surface} '
                  'outcome=authenticated-denied-state-preserved', flush=True)


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
def test_request_rejects_locked_approver_during_authentication(
        accounts, passwords, surface, authentication_diagnostics):
    """A parent locked after selection cannot approve through an active prompt."""
    target, selected, other = (accounts[key] for key in ('child1', 'parent1', 'parent2'))
    interface = 'org.freedesktop.Accounts.User'
    path = f'/org/freedesktop/Accounts/User{selected}'
    guest.require(account_property(selected, interface, 'Locked') is False,
                  'authorization:lock-fixture')
    original = accepted(call(other, 'GetPreferences', '(u)', (target,)))[0]
    accepted(call(other, 'SetParentControl', '(ubu)', (target, True, 0)))
    try:
        with PersistentCaller(accounts[surface]) as caller, TextAgent(
                caller, record_diagnostic=authentication_diagnostics) as agent:
            rows = accepted(caller.call('ListApprovers'))[0]
            guest.require(selected in {row[0] for row in rows},
                          'authorization:lock-initial-discovery')
            caller.send({
                'kind': 'call',
                'method': 'RequestOwnAccess' if surface == 'child1' else 'RequestAccess',
                'signature': '(uub)' if surface == 'child1' else '(uuub)',
                'args': (selected, 300, False) if surface == 'child1' else
                        (target, selected, 300, False),
            })
            agent.prompt(selected, other)
            guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                       path, interface, 'SetLocked', 'b', 'true'])
            guest.require(account_property(selected, interface, 'Locked') is True,
                          'authorization:inflight-lock-not-visible')
            rows = accepted(call(other, 'ListApprovers'))[0]
            guest.require(selected not in {row[0] for row in rows},
                          'authorization:locked-approver-discovery')
            before = {key: account_state(accounts[key]) for key in ROLES}
            # Unlike a role change, locking invalidates password authentication.
            # This case proves the installed denial boundary, not a successful
            # PAM challenge followed by the broker's post-authentication check.
            agent.authenticate(passwords['parent1'], succeeds=False)
            result = accepted(caller.receive())
            guest.require(result[1] in ('denied', 'cancelled') and
                          (surface == 'kiosk' or result[2] == 0),
                          'authorization:inflight-locked-approver-grant')
            guest.require(all(account_state(accounts[key]) == state for key, state in before.items()),
                          'authorization:inflight-locked-approver-write')
            print(f'onpc-system: stage=inflight-approver-lock surface={surface} '
                  'outcome=denied-state-preserved', flush=True)
    finally:
        guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                   path, interface, 'SetLocked', 'b', 'false'])
        guest.require(account_property(selected, interface, 'Locked') is False,
                      'authorization:approver-unlock-not-visible')
        accepted(call(other, 'SetParentControl', '(ubu)', (target, False, 60)))
        accepted(call(other, 'SetPreferences', '(us)', (target, original)))


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
