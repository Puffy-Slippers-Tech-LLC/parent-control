"""Guarded disposable identities with observed creation/deletion boundaries.

The retained guest baseline owns account cleanup. These helpers do not infer
process ownership or terminate account sessions.
"""

import json
import pwd
import time

import system_guest as guest
from system_assertions import account_property


def disposable_identity_name(role, surface=None):
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
               'CreateUser', 'ssi', name, '', '1' if role == 'approver' else '0'])
    uid = pwd.getpwnam(name).pw_uid
    observed = {prop: account_property(uid, 'org.freedesktop.Accounts.User', prop)
                for prop in ('AccountType', 'LocalAccount', 'SystemAccount')}
    record_testsuite_property('onpc.deletion-fixture', json.dumps(
        {'role': role, 'surface': surface, **observed}, sort_keys=True))
    guest.require(observed == {'AccountType': int(role == 'approver'),
                               'LocalAccount': True, 'SystemAccount': False},
                  'authorization:deletion-fixture-eligibility:' + role)
    return uid


def delete_disposable_identity(uid, role, *, surface=None):
    """Observe deletion in both identity authorities before testing the broker."""
    guest.guard()
    name = disposable_identity_name(role, surface)
    guest.require(pwd.getpwnam(name).pw_uid == uid,
                  'authorization:deletion-identity-mismatch')
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
