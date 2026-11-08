"""Guarded disposable identities with observed creation/deletion boundaries.

The retained guest baseline owns account cleanup. These helpers do not infer
process ownership or terminate account sessions.
"""

import json
import pwd
import time

import system_guest as guest
from system_assertions import account_properties
from account_registry import SPARE_CHILDREN, SPARE_APPROVER


def require_logged_out(uids, *, read_category, active_category):
    """Refuse mutation while any target has a session, including inactive ones."""
    sessions = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager'])
    for line in sessions.splitlines():
        fields = line.split()
        guest.require(len(fields) >= 3 and fields[1].isdigit(), read_category)
        guest.require(int(fields[1]) not in uids, active_category)


def disposable_identity_name(role, surface=None):
    if surface == 'spare-approver':
        guest.require(role == 'approver', 'authorization:deletion-fixture-scope')
        return SPARE_APPROVER[0]
    if surface == 'spare-child':
        guest.require(role in SPARE_CHILDREN, 'authorization:deletion-fixture-scope')
        return SPARE_CHILDREN[role][0]
    guest.require(role in ('target', 'approver') and surface in (None, 'child', 'kiosk'),
                  'authorization:deletion-fixture-scope')
    return 'onpc-auth-delete-' + (surface + '-' if surface else '') + role


def create_disposable_identity(role, record_testsuite_property, *, surface=None):
    """Only the guarded guest creates these; baseline restoration owns cleanup."""
    guest.guard()
    name = disposable_identity_name(role, surface)
    try:
        pwd.getpwnam(name)
    except KeyError:
        pass
    else:
        raise guest.GuestError('authorization:deletion-fixture-collision')
    # Establish eligibility through the authority the broker consults, without
    # racing the asynchronous local-user reload following a direct useradd.
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
               'CreateUser', 'ssi', name,
               SPARE_CHILDREN[role][1] if surface == 'spare-child' else
               SPARE_APPROVER[1] if surface == 'spare-approver' else '',
               '1' if role == 'approver' else '0'])
    uid = pwd.getpwnam(name).pw_uid
    observed = account_properties(uid, 'org.freedesktop.Accounts.User', {
        'AccountType': 'i', 'LocalAccount': 'b', 'SystemAccount': 'b',
    })
    record_testsuite_property('onpc.deletion-fixture', json.dumps(
        {'role': role, 'surface': surface, **observed}, sort_keys=True))
    guest.require(observed == {'AccountType': int(role == 'approver'),
                               'LocalAccount': True, 'SystemAccount': False},
                  'authorization:deletion-fixture-eligibility:' + role)
    return uid


def change_spare_approver_role(uid):
    """Demote only this attempt's logged-out Sam while retaining eligible Jamie."""
    guest.guard()
    name = disposable_identity_name('approver', 'spare-approver')
    entries = pwd.getpwall()
    guest.require(type(uid) is int and 1000 <= uid <= (1 << 32) - 1
                  and len({entry.pw_name for entry in entries}) == len(entries)
                  and len({entry.pw_uid for entry in entries}) == len(entries)
                  and [(entry.pw_name, entry.pw_uid) for entry in entries
                       if entry.pw_name == name or entry.pw_uid == uid] == [(name, uid)],
                  'spare-approver:identity')
    properties = {'Uid': 't', 'UserName': 's', 'AccountType': 'i',
                  'LocalAccount': 'b', 'SystemAccount': 'b', 'Locked': 'b', 'Shell': 's'}
    expected = {'Uid': uid, 'UserName': name, 'AccountType': 1,
                'LocalAccount': True, 'SystemAccount': False, 'Locked': False, 'Shell': '/bin/bash'}
    guest.require(account_properties(uid, 'org.freedesktop.Accounts.User', properties) == expected,
                  'spare-approver:eligibility')
    jamie = pwd.getpwnam('onpc-parent-jamie')
    guest.require(jamie.pw_uid >= 1000 and jamie.pw_uid != uid
                  and account_properties(jamie.pw_uid, 'org.freedesktop.Accounts.User', properties)
                  == {**expected, 'Uid': jamie.pw_uid, 'UserName': jamie.pw_name},
                  'spare-approver:retained-administrator')
    require_logged_out({uid}, read_category='spare-approver:session-read',
                       active_category='spare-approver:active-account')
    guest.guard()
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               f'/org/freedesktop/Accounts/User{uid}', 'org.freedesktop.Accounts.User',
               'SetAccountType', 'i', '0'])
    guest.require(account_properties(uid, 'org.freedesktop.Accounts.User', properties)
                  == {**expected, 'AccountType': 0}, 'spare-approver:role-readback')


def delete_disposable_identity(uid, role, *, surface=None):
    """Observe deletion in both identity authorities before testing the broker."""
    guest.guard()
    # Sam's fixture owns only creation and demotion; snapshot restoration is
    # its cleanup. Do not expose an unguarded administrator-deletion route.
    guest.require(surface != 'spare-approver', 'authorization:deletion-fixture-scope')
    name = disposable_identity_name(role, surface)
    guest.require(pwd.getpwnam(name).pw_uid == uid,
                  'authorization:deletion-identity-mismatch')
    if surface == 'spare-child':
        # These customer fixtures must stay logged out. Never let a stale
        # controller receipt remove an active user or a changed administrator.
        guest.require(type(uid) is int and uid >= 1000
                      and pwd.getpwuid(uid).pw_name == name,
                      'authorization:deletion-identity-mismatch')
        properties = account_properties(uid, 'org.freedesktop.Accounts.User', {
            'Uid': 't', 'UserName': 's', 'AccountType': 'i',
            'LocalAccount': 'b', 'SystemAccount': 'b',
        })
        guest.require(properties == {'Uid': uid, 'UserName': name, 'AccountType': 0,
                                      'LocalAccount': True, 'SystemAccount': False},
                      'authorization:deletion-fixture-eligibility')
        require_logged_out({uid}, read_category='authorization:deletion-session-read',
                           active_category='authorization:deletion-active-account')
    guest.retain_identity_for_redaction(uid)
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
               'DeleteUser', 'xb', str(uid), 'false'])
    deadline = time.monotonic() + 10
    while True:
        try:
            pwd.getpwuid(uid)
        except KeyError:
            absent = True
        else:
            absent = False
        # A missing UID must not resolve even if AccountsService cached it earlier.
        guest.commands.run([
            'busctl', '--system', 'call', 'org.freedesktop.Accounts',
            '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
            'FindUserById', 'x', str(uid)], check=False, merge_stderr=False)
        if absent and guest.commands.last_returncode != 0:
            break
        guest.require(time.monotonic() < deadline, 'authorization:deletion-not-visible')
        time.sleep(0.1)
    # Distinguish disappearance from an unavailable AccountsService daemon.
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
               'FindUserById', 'x', '0'])
    print(f'onpc-system: stage=account-deletion role={role} outcome=visible', flush=True)
