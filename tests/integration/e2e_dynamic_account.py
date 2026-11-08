#!/usr/bin/python3
"""Guarded account fixtures for the finite E2E-003 customer variants."""

import json
import pwd
import re
import shlex
import sys

import system_guest as guest
from system_assertions import account_properties
from system_accounts import (SPARE_CHILDREN, create_disposable_identity,
                             delete_disposable_identity, require_logged_out,
                             SPARE_APPROVER, change_spare_approver_role)
from system_caller import FixturePassword


USERNAME = "onpc-e2e-new-child"
DISPLAY_NAME = "Morgan (Child)"
ACCOUNTS_NAME = "org.freedesktop.Accounts"
ACCOUNTS_PATH = "/org/freedesktop/Accounts"
ACCOUNTS_INTERFACE = "org.freedesktop.Accounts"
USER_INTERFACE = "org.freedesktop.Accounts.User"
FIXED_CHILDREN = ("onpc-child-riley", "onpc-child-jordan")
FIXED_APPROVERS = ("onpc-parent-jamie", "onpc-parent-casey")
KIOSK_USERNAME = "oh-no-parent-control"
INELIGIBLE_USERNAME = 'onpc-e2e-locked-parent'
EXPECTED_ELIGIBLE_ACCOUNTS = len(FIXED_CHILDREN)
NONINTERACTIVE_SHELLS = ("", "/bin/false", "/usr/sbin/nologin")
APPROVER_NONINTERACTIVE_SHELLS = (*NONINTERACTIVE_SHELLS, '/usr/bin/false', '/sbin/nologin')
USER_PROPERTIES = {'Uid': 't', 'UserName': 's', 'LocalAccount': 'b',
                   'SystemAccount': 'b', 'AccountType': 'i', 'Locked': 'b', 'Shell': 's'}
ROLE_PROPERTIES = {key: USER_PROPERTIES[key]
                   for key in ('LocalAccount', 'SystemAccount', 'AccountType')}


def property_value(path, name, signature):
    fields = shlex.split(guest.run([
        "busctl", "--system", "get-property", ACCOUNTS_NAME, path,
        USER_INTERFACE, name,
    ]))
    guest.require(len(fields) == 2 and fields[0] == signature,
                  "dynamic-account:property")
    return fields[1]


def property_values(path, properties=USER_PROPERTIES):
    """Share typed batched reads with system tests; keep busctl's scalar spelling."""
    guest.require(re.fullmatch(r'/org/freedesktop/Accounts/User[0-9]+', path),
                  'dynamic-account:property-path')
    values = account_properties(int(path.rsplit('User', 1)[1]), USER_INTERFACE, properties)
    return {name: ('true' if value else 'false') if properties[name] == 'b' else str(value)
            for name, value in values.items()}


def account_path(uid):
    fields = shlex.split(guest.run([
        "busctl", "--system", "call", ACCOUNTS_NAME, ACCOUNTS_PATH,
        ACCOUNTS_INTERFACE, "FindUserById", "x", str(uid),
    ]))
    guest.require(len(fields) == 2 and fields[0] == "o"
                  and re.fullmatch(r"/org/freedesktop/Accounts/User[0-9]+", fields[1]),
                  "empty-account:lookup")
    return fields[1]


def account_identities(identities, noninteractive_shells=()):
    """Persistent NSS identities, including the station's nologin account."""
    return [entry for entry in identities
            if 1000 <= entry.pw_uid <= (1 << 32) - 1
            and not 60578 <= entry.pw_uid <= 60705
            and (entry.pw_name == KIOSK_USERNAME
                 or entry.pw_shell not in noninteractive_shells)]


def create():
    guest.guard()
    try:
        pwd.getpwnam(USERNAME)
    except KeyError:
        pass
    else:
        raise guest.GuestError("dynamic-account:collision")
    reply = shlex.split(guest.run([
        "busctl", "--system", "call", ACCOUNTS_NAME, ACCOUNTS_PATH,
        ACCOUNTS_INTERFACE, "CreateUser", "ssi", USERNAME, DISPLAY_NAME, "0",
    ]))
    guest.require(len(reply) == 2 and reply[0] == "o"
                  and reply[1].startswith("/org/freedesktop/Accounts/User"),
                  "dynamic-account:create-reply")
    account = pwd.getpwnam(USERNAME)
    guest.require(account.pw_uid >= 1000 and account.pw_shell == "/bin/bash",
                  "dynamic-account:identity")
    observed = property_values(reply[1], ROLE_PROPERTIES)
    guest.require(observed == {
        "LocalAccount": "true", "SystemAccount": "false", "AccountType": "0",
    }, "dynamic-account:eligibility")
    print("onpc-e2e: stage=dynamic-account outcome=created", flush=True)


def prepare_empty():
    """Make the guarded baseline's finite eligible set ineligible for this boot."""
    guest.guard()
    accounts = []
    eligible_names = set()
    identities = account_identities(pwd.getpwall(), NONINTERACTIVE_SHELLS)
    guest.require(len(identities) == len({entry.pw_uid for entry in identities})
                  and set((*FIXED_CHILDREN, KIOSK_USERNAME))
                  <= {entry.pw_name for entry in identities},
                  "empty-account:identity")
    for entry in identities:
        if entry.pw_name == KIOSK_USERNAME:
            continue
        path = account_path(entry.pw_uid)
        observed = property_values(path, ROLE_PROPERTIES)
        if observed == {
            "LocalAccount": "true", "SystemAccount": "false",
            "AccountType": "0",
        }:
            accounts.append(path)
            eligible_names.add(entry.pw_name)
    # Only the canonical child fixtures are authorized mutation targets.
    # A count alone could substitute an unrelated standard account for one.
    fixed_eligible = len(eligible_names.intersection(FIXED_CHILDREN))
    guest.require(len(accounts) == EXPECTED_ELIGIBLE_ACCOUNTS
                  and eligible_names == set(FIXED_CHILDREN),
                  f"empty-account:baseline:eligible={len(accounts)}:fixed={fixed_eligible}")
    guest.require(len(accounts) == len(set(accounts)), "empty-account:identity")
    for path in accounts:
        guest.guard()
        fields = shlex.split(guest.run([
            "busctl", "--system", "call", ACCOUNTS_NAME, path,
            USER_INTERFACE, "SetAccountType", "i", "1",
        ]))
        guest.require(fields == [], "empty-account:set-role")
        guest.require(property_value(path, "AccountType", "i") == "1",
                      "empty-account:role")
    guest.guard()
    print("onpc-e2e: stage=empty-account outcome=prepared", flush=True)


def prepare_no_approver(approver_uids):
    """Detect all eligible parents after nonempty UI proof, then lock that set."""
    guest.guard()
    guest.require(type(approver_uids) is list and bool(approver_uids)
                  and all(type(uid) is int and 1000 <= uid <= (1 << 32) - 1
                          for uid in approver_uids)
                  and len(approver_uids) == len(set(approver_uids)),
                  'no-approver:public-baseline')
    identities = account_identities(pwd.getpwall(), APPROVER_NONINTERACTIVE_SHELLS)
    names = [entry.pw_name for entry in identities]
    guest.require(len(identities) == len({entry.pw_uid for entry in identities})
                  and len(names) == len(set(names))
                  and set((*FIXED_CHILDREN, KIOSK_USERNAME)) <= set(names)
                  and set(approver_uids) <= {entry.pw_uid for entry in identities},
                  'no-approver:identity')
    observed = {}
    paths = {}
    for entry in identities:
        path = account_path(entry.pw_uid)
        guest.require(path == f'/org/freedesktop/Accounts/User{entry.pw_uid}',
                      'no-approver:identity')
        paths[entry.pw_name] = path
        observed[entry.pw_name] = property_values(path)
        guest.require(observed[entry.pw_name]['Uid'] == str(entry.pw_uid)
                      and observed[entry.pw_name]['UserName'] == entry.pw_name,
                      'no-approver:identity')
    # Supporting OS fixture discovery, not a substitute for the public starting
    # observation or the later empty-form assertion. Freeze the complete target
    # set before mutation; a role/name/count is never assumed from fixture labels.
    targets = {name for name, values in observed.items()
               if values['LocalAccount'] == 'true' and values['SystemAccount'] == 'false'
               and values['AccountType'] == '1' and values['Locked'] == 'false'
               and values['Shell'] not in APPROVER_NONINTERACTIVE_SHELLS
               and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*[$]?', name)}
    guest.require(set(approver_uids) <= {int(observed[name]['Uid']) for name in targets},
                  'no-approver:target-eligibility')
    guest.require(not targets.intersection((*FIXED_CHILDREN, KIOSK_USERNAME)),
                  'no-approver:protected-account')
    guest.require(observed[KIOSK_USERNAME]['AccountType'] == '0',
                  'no-approver:station-role')
    for name in FIXED_CHILDREN:
        values = observed[name]
        guest.require(values['LocalAccount'] == 'true' and values['SystemAccount'] == 'false'
                      and values['AccountType'] == '0'
                      and values['Locked'] == 'false'
                      and values['Shell'] not in NONINTERACTIVE_SHELLS,
                      'no-approver:retained-account')
    for name in sorted(targets):
        guest.guard()
        guest.require(property_values(paths[name]) == observed[name],
                      'no-approver:target-changed')
        fields = shlex.split(guest.run([
            'busctl', '--system', 'call', ACCOUNTS_NAME, paths[name],
            USER_INTERFACE, 'SetLocked', 'b', 'true',
        ]))
        guest.require(fields == [], 'no-approver:set-locked')
        guest.require(property_value(paths[name], 'Locked', 'b') == 'true',
                      'no-approver:locked')
    for name, before in observed.items():
        guest.guard()
        expected = {**before, 'Locked': 'true'} if name in targets else before
        after = property_values(paths[name])
        guest.require(after == expected, 'no-approver:retained-identity')
    guest.guard()
    print(f'onpc-e2e: stage=no-approver outcome=prepared locked={len(targets)}', flush=True)


def prepare_ineligible_approver():
    """Create one locked administrator; never modify a pre-existing account."""
    guest.guard()
    identities = pwd.getpwall()
    names = [entry.pw_name for entry in identities]
    guest.require(INELIGIBLE_USERNAME not in names, 'ineligible-approver:collision')
    guest.require(len(names) == len(set(names))
                  and len(identities) == len({entry.pw_uid for entry in identities})
                  and set((*FIXED_CHILDREN, *FIXED_APPROVERS, KIOSK_USERNAME)) <= set(names),
                  'ineligible-approver:identity')
    def read(entry):
        path = account_path(entry.pw_uid)
        guest.require(path == f'/org/freedesktop/Accounts/User{entry.pw_uid}',
                      'ineligible-approver:identity')
        values = property_values(path)
        guest.require(values['Uid'] == str(entry.pw_uid) and values['UserName'] == entry.pw_name,
                      'ineligible-approver:identity')
        return path, values

    before = {entry.pw_name: read(entry) for entry in account_identities(identities)}
    for name in (*FIXED_CHILDREN, *FIXED_APPROVERS):
        values = before[name][1]
        guest.require(values['LocalAccount'] == 'true' and values['SystemAccount'] == 'false'
                      and values['Locked'] == 'false'
                      and values['Shell'] not in APPROVER_NONINTERACTIVE_SHELLS
                      and values['AccountType'] == ('1' if name in FIXED_APPROVERS else '0'),
                      'ineligible-approver:baseline')
    guest.require(before[KIOSK_USERNAME][1]['AccountType'] == '0',
                  'ineligible-approver:station-role')
    guest.guard()
    reply = shlex.split(guest.run([
        'busctl', '--system', 'call', ACCOUNTS_NAME, ACCOUNTS_PATH,
        ACCOUNTS_INTERFACE, 'CreateUser', 'ssi', INELIGIBLE_USERNAME, 'Locked Parent', '1',
    ]))
    account = pwd.getpwnam(INELIGIBLE_USERNAME)
    guest.require(account.pw_uid >= 1000 and account.pw_uid not in {e.pw_uid for e in identities},
                  'ineligible-approver:new-identity')
    path, values = read(account)
    guest.require(reply == ['o', path] and values == {
        'Uid': str(account.pw_uid), 'UserName': INELIGIBLE_USERNAME,
        'LocalAccount': 'true', 'SystemAccount': 'false', 'AccountType': '1',
        'Locked': 'true', 'Shell': '/bin/bash',
    }, 'ineligible-approver:locked-administrator')
    # CreateUser produces a locked account until credentials are assigned. No
    # password or authentication bypass is needed to construct this profile.
    after = pwd.getpwall()
    guest.require({(e.pw_name, e.pw_uid, e.pw_shell) for e in after}
                  == {(e.pw_name, e.pw_uid, e.pw_shell) for e in identities}
                  | {(account.pw_name, account.pw_uid, account.pw_shell)},
                  'ineligible-approver:retained-identity')
    for entry in identities:
        if entry.pw_name in before:
            guest.require(read(entry) == before[entry.pw_name],
                          'ineligible-approver:retained-account')
    guest.guard()
    print('onpc-e2e: stage=ineligible-approver outcome=prepared', flush=True)


def eligible_children():
    """Read the complete OS child set, never infer eligibility from a count."""
    children = {}
    for entry in account_identities(pwd.getpwall(), APPROVER_NONINTERACTIVE_SHELLS):
        if entry.pw_name == KIOSK_USERNAME:
            continue
        values = property_values(account_path(entry.pw_uid))
        guest.require(values['Uid'] == str(entry.pw_uid)
                      and values['UserName'] == entry.pw_name, 'spare-child:identity')
        if (values['LocalAccount'], values['SystemAccount'], values['AccountType']) == (
                'true', 'false', '0'):
            children[entry.pw_name] = entry.pw_uid
    return children


def prepare_spare_children(profile):
    """One finite spare-only profile; restoration retains every baseline identity."""
    guest.guard()
    guest.require(profile in ('one', 'two'), 'spare-child:profile')
    roles = ('jordan', 'riley') if profile == 'two' else ('jordan',)
    before = pwd.getpwall()
    names = {entry.pw_name for entry in before}
    guest.require(len(names) == len(before)
                  and len({entry.pw_uid for entry in before}) == len(before)
                  and set((*FIXED_CHILDREN, *FIXED_APPROVERS, KIOSK_USERNAME)) <= names
                  and not names.intersection(value[0] for value in SPARE_CHILDREN.values()),
                  'spare-child:baseline-identity')
    guest.require(set(eligible_children()) == set(FIXED_CHILDREN),
                  'spare-child:baseline-eligible-set')
    baseline_uids = {pwd.getpwnam(name).pw_uid for name in FIXED_CHILDREN}
    require_logged_out(baseline_uids, read_category='spare-child:session-read',
                       active_category='spare-child:baseline-active')
    # This profile explicitly changes only the two baseline children's roles,
    # preserving their identities. It never borrows/removes them as spares.
    for name in FIXED_APPROVERS:
        guest.require(property_values(account_path(pwd.getpwnam(name).pw_uid))['AccountType'] == '1',
                      'spare-child:retained-administrator')
    for name in FIXED_CHILDREN:
        guest.guard()
        path = account_path(pwd.getpwnam(name).pw_uid)
        guest.run(['busctl', '--system', 'call', ACCOUNTS_NAME, path,
                   USER_INTERFACE, 'SetAccountType', 'i', '1'])
        guest.require(property_value(path, 'AccountType', 'i') == '1', 'spare-child:baseline-role')
    created = {}
    for role in roles:
        uid = create_disposable_identity(role, lambda *_: None, surface='spare-child')
        guest.require(uid not in {entry.pw_uid for entry in before}, 'spare-child:new-identity')
        guest.retain_identity_for_redaction(uid)
        created[role] = uid
    guest.require(eligible_children() == {SPARE_CHILDREN[role][0]: uid
                                        for role, uid in created.items()},
                  'spare-child:prepared-eligible-set')
    guest.require({(entry.pw_name, entry.pw_uid, entry.pw_shell) for entry in pwd.getpwall()}
                  == {(entry.pw_name, entry.pw_uid, entry.pw_shell) for entry in before}
                  | {(SPARE_CHILDREN[role][0], uid, '/bin/bash') for role, uid in created.items()},
                  'spare-child:retained-identities')
    guest.guard()
    print(json.dumps(created, sort_keys=True), flush=True)


def remove_spare_child(uid):
    guest.guard()
    delete_disposable_identity(uid, 'jordan', surface='spare-child')
    guest.guard()
    print('onpc-e2e: stage=spare-child outcome=removed', flush=True)


def prepare_spare_approver():
    """Create fresh Sam without borrowing or changing any baseline identity."""
    guest.guard()
    before = pwd.getpwall()
    guest.require(len({entry.pw_name for entry in before}) == len(before)
                  and len({entry.pw_uid for entry in before}) == len(before)
                  and SPARE_APPROVER[0] not in {entry.pw_name for entry in before},
                  'spare-approver:baseline-identity')
    jamie = pwd.getpwnam(FIXED_APPROVERS[0])
    jamie_before = property_values(account_path(jamie.pw_uid))
    guest.require(jamie_before == {'Uid': str(jamie.pw_uid), 'UserName': jamie.pw_name,
                  'LocalAccount': 'true', 'SystemAccount': 'false', 'AccountType': '1',
                  'Locked': 'false', 'Shell': '/bin/bash'},
                  'spare-approver:retained-administrator')
    uid = create_disposable_identity('approver', lambda *_: None, surface='spare-approver')
    guest.require(uid >= 1000 and uid not in {entry.pw_uid for entry in before},
                  'spare-approver:new-identity')
    guest.retain_identity_for_redaction(uid)
    path = account_path(uid)
    guest.require(property_values(path) == {'Uid': str(uid), 'UserName': SPARE_APPROVER[0],
                  'LocalAccount': 'true', 'SystemAccount': 'false', 'AccountType': '1',
                  'Locked': 'true', 'Shell': '/bin/bash'}, 'spare-approver:created-account')
    guest.guard()
    # Unlocking a password-disabled account can report success without changing
    # its shadow lock. Reuse the system fixture's private, random credential so
    # AccountsService's next OS reload retains Sam's eligibility.
    FixturePassword().install(uid)
    guest.run(['busctl', '--system', 'call', ACCOUNTS_NAME, path,
               USER_INTERFACE, 'SetLocked', 'b', 'false'])
    guest.require(property_values(path) == {'Uid': str(uid), 'UserName': SPARE_APPROVER[0],
                  'LocalAccount': 'true', 'SystemAccount': 'false', 'AccountType': '1',
                  'Locked': 'false', 'Shell': '/bin/bash'}, 'spare-approver:prepared-account')
    guest.require({(entry.pw_name, entry.pw_uid, entry.pw_shell) for entry in pwd.getpwall()}
                  == {(entry.pw_name, entry.pw_uid, entry.pw_shell) for entry in before}
                  | {(SPARE_APPROVER[0], uid, '/bin/bash')}
                  and property_values(account_path(jamie.pw_uid)) == jamie_before,
                  'spare-approver:retained-identities')
    guest.guard()
    print(json.dumps({'sam': uid}), flush=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    guest.require(argv in (["create"], ["prepare-empty"], ['prepare-no-approver'],
                          ['prepare-ineligible-approver'], ['prepare-one-spare-child'],
                          ['prepare-two-spare-children'], ['remove-spare-child'],
                          ['prepare-spare-approver'], ['demote-spare-approver']),
                  "dynamic-account:operation")
    if argv == ["create"]:
        create()
    elif argv == ['prepare-empty']:
        prepare_empty()
    elif argv == ['prepare-ineligible-approver']:
        prepare_ineligible_approver()
    elif argv == ['prepare-spare-approver']:
        prepare_spare_approver()
    elif argv == ['demote-spare-approver']:
        raw = sys.stdin.buffer.read(65)
        guest.require(re.fullmatch(rb'[1-9][0-9]{3,9}', raw) is not None,
                      'spare-approver:role-input')
        change_spare_approver_role(int(raw))
        guest.guard()
        print('onpc-e2e: stage=spare-approver outcome=standard', flush=True)
    elif argv in (['prepare-one-spare-child'], ['prepare-two-spare-children']):
        prepare_spare_children('one' if argv == ['prepare-one-spare-child'] else 'two')
    elif argv == ['remove-spare-child']:
        raw = sys.stdin.buffer.read(65)
        guest.require(re.fullmatch(rb'[1-9][0-9]{3,9}', raw) is not None,
                      'spare-child:removal-input')
        remove_spare_child(int(raw))
    else:
        # The controller carries the public selection over guarded private stdin,
        # never as account labels or command-line arguments.
        raw = sys.stdin.buffer.read(65537)
        guest.require(0 < len(raw) <= 65536, 'no-approver:input')
        try:
            uids = json.loads(raw)
        except (ValueError, UnicodeError):
            raise guest.GuestError('no-approver:input') from None
        prepare_no_approver(uids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
