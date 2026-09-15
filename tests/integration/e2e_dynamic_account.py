#!/usr/bin/python3
"""Guarded account fixtures for the finite E2E-003 customer variants."""

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
KIOSK_USERNAME = "oh-no-parent-control"
EXPECTED_ELIGIBLE_ACCOUNTS = 3
NONINTERACTIVE_SHELLS = ("", "/bin/false", "/usr/sbin/nologin")


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
    guest.require(len(accounts) == EXPECTED_ELIGIBLE_ACCOUNTS,
                  "empty-account:baseline")
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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    guest.require(argv in (["create"], ["prepare-empty"]),
                  "dynamic-account:operation")
    if argv == ["create"]:
        create()
    else:
        prepare_empty()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
