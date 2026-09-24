#!/usr/bin/python3
"""Guarded account fixtures for the finite E2E-003 customer variants."""

import json
import pwd
import re
import shlex
import sys

import system_guest as guest


USERNAME = "onpc-e2e-new-child"
DISPLAY_NAME = "Morgan (Child)"
ACCOUNTS_NAME = "org.freedesktop.Accounts"
ACCOUNTS_PATH = "/org/freedesktop/Accounts"
ACCOUNTS_INTERFACE = "org.freedesktop.Accounts"
USER_INTERFACE = "org.freedesktop.Accounts.User"
FIXED_CHILDREN = ("onpc-child-riley", "onpc-child-jordan")
FIXED_APPROVERS = ("onpc-parent-jamie", "onpc-parent-casey")
KIOSK_USERNAME = "oh-no-parent-control"
EXPECTED_ELIGIBLE_ACCOUNTS = len(FIXED_CHILDREN)
NONINTERACTIVE_SHELLS = ("", "/bin/false", "/usr/sbin/nologin")
APPROVER_NONINTERACTIVE_SHELLS = (*NONINTERACTIVE_SHELLS, '/usr/bin/false', '/sbin/nologin')


def property_value(path, name, signature):
    fields = shlex.split(guest.run([
        "busctl", "--system", "get-property", ACCOUNTS_NAME, path,
        USER_INTERFACE, name,
    ]))
    guest.require(len(fields) == 2 and fields[0] == signature,
                  "dynamic-account:property")
    return fields[1]


def account_path(uid):
    fields = shlex.split(guest.run([
        "busctl", "--system", "call", ACCOUNTS_NAME, ACCOUNTS_PATH,
        ACCOUNTS_INTERFACE, "FindUserById", "x", str(uid),
    ]))
    guest.require(len(fields) == 2 and fields[0] == "o"
                  and re.fullmatch(r"/org/freedesktop/Accounts/User[0-9]+", fields[1]),
                  "empty-account:lookup")
    return fields[1]


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
    observed = {
        "LocalAccount": property_value(reply[1], "LocalAccount", "b"),
        "SystemAccount": property_value(reply[1], "SystemAccount", "b"),
        "AccountType": property_value(reply[1], "AccountType", "i"),
    }
    guest.require(observed == {
        "LocalAccount": "true", "SystemAccount": "false", "AccountType": "0",
    }, "dynamic-account:eligibility")
    print("onpc-e2e: stage=dynamic-account outcome=created", flush=True)


def prepare_empty():
    """Make the guarded baseline's finite eligible set ineligible for this boot."""
    guest.guard()
    accounts = []
    eligible_names = set()
    identities = [entry for entry in pwd.getpwall()
                  if 1000 <= entry.pw_uid <= (1 << 32) - 1
                  and entry.pw_shell not in NONINTERACTIVE_SHELLS]
    guest.require(len(identities) == len({entry.pw_uid for entry in identities})
                  and set((*FIXED_CHILDREN, KIOSK_USERNAME))
                  <= {entry.pw_name for entry in identities},
                  "empty-account:identity")
    for entry in identities:
        if entry.pw_name == KIOSK_USERNAME:
            continue
        path = account_path(entry.pw_uid)
        observed = {
            "LocalAccount": property_value(path, "LocalAccount", "b"),
            "SystemAccount": property_value(path, "SystemAccount", "b"),
            "AccountType": property_value(path, "AccountType", "i"),
        }
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
    identities = [entry for entry in pwd.getpwall()
                  if 1000 <= entry.pw_uid <= (1 << 32) - 1
                  and entry.pw_shell not in APPROVER_NONINTERACTIVE_SHELLS]
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
        observed[entry.pw_name] = {
            name: property_value(path, name, signature)
            for name, signature in (
                ('Uid', 't'), ('UserName', 's'), ('LocalAccount', 'b'),
                ('SystemAccount', 'b'), ('AccountType', 'i'), ('Locked', 'b'), ('Shell', 's'))
        }
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
        guest.require(all(property_value(paths[name], key, signature) == observed[name][key]
                          for key, signature in (
                              ('Uid', 't'), ('UserName', 's'), ('LocalAccount', 'b'),
                              ('SystemAccount', 'b'), ('AccountType', 'i'),
                              ('Locked', 'b'), ('Shell', 's'))),
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
        after = {key: property_value(paths[name], key, signature)
                 for key, signature in (
                     ('Uid', 't'), ('UserName', 's'), ('LocalAccount', 'b'),
                     ('SystemAccount', 'b'), ('AccountType', 'i'), ('Locked', 'b'), ('Shell', 's'))}
        guest.require(after == expected, 'no-approver:retained-identity')
    guest.guard()
    print(f'onpc-e2e: stage=no-approver outcome=prepared locked={len(targets)}', flush=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    guest.require(argv in (["create"], ["prepare-empty"], ['prepare-no-approver']),
                  "dynamic-account:operation")
    if argv == ["create"]:
        create()
    elif argv == ['prepare-empty']:
        prepare_empty()
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
