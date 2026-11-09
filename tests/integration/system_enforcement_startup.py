"""Owned Ubuntu enforcement-readiness failure and explicit GDM recovery.

The existing package mount fixture pins and restores the readiness executable.
This is engineering fault injection, not customer UI acceptance.
"""

import json
from pathlib import Path
import pwd
import shlex
import shutil
import tempfile
import time

import system_guest as guest
from system_assertions import account_state
from system_removal_faults import Fault, WITNESS, identity, mounted_fault


POLICY = 'fapolicyd.service'
DISPLAY = 'display-manager.service'
READY = Path('/usr/libexec/oh-no-parent-control-execution-policy-ready')


def require(condition, reason):
    guest.require(condition, 'enforcement-startup:' + reason)


def properties(unit, *names):
    raw = guest.run(['systemctl', 'show', unit, '--no-pager',
                     '--property=' + ','.join(names)])
    rows = [line.split('=', 1) for line in raw.splitlines()]
    result = {}
    for name, value in rows:
        require(name in names and (name not in result or name == 'ExecStartPost'),
                'unit-observation')
        # systemctl emits one ExecStartPost row per configured command.
        result[name] = result[name] + '\n' + value if name in result else value
    require(set(result) == set(names), 'unit-observation')
    return result


def graphical_sessions():
    result = []
    for line in guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines():
        session = line.split()[0]
        raw = guest.run(['loginctl', 'show-session', session, '--property=Class',
                         '--property=Type', '--property=Active', '--property=Remote'])
        values = dict(row.split('=', 1) for row in raw.splitlines())
        require(set(values) == {'Class', 'Type', 'Active', 'Remote'}, 'session-observation')
        if values['Type'] in ('wayland', 'x11'):
            require(values['Class'] == 'greeter', 'personal-session-active')
            result.append(values)
    return result


def exercise(record):
    guest.guard()
    require(guest.package_path().suffix == '.deb', 'ubuntu-binding-required')
    boot = guest.sha(Path('/proc/sys/kernel/random/boot_id'))
    accounts = [pwd.getpwnam(name).pw_uid for name in
                ('onpc-child-riley', 'onpc-child-jordan', 'onpc-parent-jamie')]
    before = {uid: account_state(uid) for uid in accounts}
    graphical_sessions()  # Refuse to stop any personal graphical session.
    require(properties(POLICY, 'ActiveState')['ActiveState'] == 'active', 'initial-policy')
    require(properties(DISPLAY, 'ActiveState')['ActiveState'] == 'active', 'initial-display')
    expected = identity(READY)
    private = guest.PAYLOAD / 'private'
    fixture = Path(tempfile.mkdtemp(prefix='enforcement-startup-', dir=private))
    wrapper, witness = fixture / 'readiness', fixture / 'triggered.txt'
    # Retries must also refuse, without replacing the original fault witness.
    wrapper.write_text('#!/bin/sh\nset -eu\n[ "$#" -eq 0 ] || exit 80\n'
                       f'if [ ! -f {shlex.quote(str(witness))} ]; then\n'
                       '  (set -C; umask 077; '
                       f'printf %s {shlex.quote(WITNESS.decode())} > '
                       f'{shlex.quote(str(witness))})\nfi\nexit 79\n')
    shutil.copystat(READY, wrapper, follow_symlinks=False)
    replacement = identity(wrapper)
    fault = Fault('enforcement-startup', READY, expected, witness=witness,
                  wrapper=replacement, artifacts=((wrapper, replacement),))
    refused_us = None
    try:
        guest.run(['systemctl', 'stop', DISPLAY, POLICY], timeout=180)
        require(not graphical_sessions(), 'greeter-not-stopped')
        stopped = properties(DISPLAY, 'MainPID', 'ExecMainStartTimestampMonotonic')
        require(stopped['MainPID'] == '0', 'display-not-stopped')
        with mounted_fault(fault, wrapper, record):
            guest.commands.run(['systemctl', 'start', DISPLAY], timeout=240,
                               check=False, merge_stderr=False)
            require(guest.commands.last_returncode != 0, 'fault-start-not-refused')
            fault.verify_triggered()
            policy = properties(POLICY, 'ActiveState', 'ExecStartPost')
            readiness = [row for row in policy['ExecStartPost'].splitlines()
                         if row.startswith('{ path=' + str(READY) + ' ;')]
            require(policy['ActiveState'] != 'active' and
                    len(readiness) == 1 and 'status=79 }' in readiness[0],
                    'readiness-failure-not-observed')
            display = properties(DISPLAY, 'ActiveState', 'MainPID',
                                 'ExecMainStartTimestampMonotonic')
            require(display['ActiveState'] in ('inactive', 'failed') and
                    display['MainPID'] == '0' and
                    int(display['ExecMainStartTimestampMonotonic']) <=
                    int(stopped['ExecMainStartTimestampMonotonic']) and
                    not graphical_sessions(), 'display-started-without-readiness')
            require(all(account_state(uid) == state for uid, state in before.items()),
                    'fault-account-writes')
            refused_us = time.monotonic_ns() // 1000
            record('onpc.enforcement-startup.refused',
                   'readiness-exit-79; display-never-started; accounts-unchanged')
            print('onpc-system: enforcement-startup=sign-in-withheld', flush=True)
            # Cancel native retries while our fault is still mounted.
            guest.run(['systemctl', 'stop', POLICY], timeout=180)
    finally:
        # mounted_fault restores only its exact owned mount before this start.
        # Never start through an unverified replacement after cleanup refusal.
        require(identity(READY) == expected, 'readiness-not-restored')
        guest.run(['systemctl', 'stop', POLICY], timeout=180)
        guest.run(['systemctl', 'reset-failed', POLICY, DISPLAY], timeout=30)
        guest.run(['systemctl', 'start', DISPLAY], timeout=300)

    deadline = time.monotonic() + 180
    while True:
        sessions = graphical_sessions()
        if any(row['Active'] == 'yes' and row['Remote'] == 'no' for row in sessions):
            break
        require(time.monotonic() < deadline, 'recovered-greeter-unavailable')
        time.sleep(1)
    require(all(account_state(uid) == state for uid, state in before.items()),
            'recovery-account-writes')
    require(guest.sha(Path('/proc/sys/kernel/random/boot_id')) == boot, 'boot-changed')
    result = {'boot_sha256': boot, 'refused_us': refused_us,
              'recovery_action': 'stop; reset-failed; start display-manager.service',
              'local_greeter_active': True, 'accounts_unchanged': True,
              'owned_fault_removed': True}
    output = guest.PAYLOAD / 'results'
    output.mkdir(mode=0o700, exist_ok=True)
    (output / 'enforcement-startup.json').write_text(json.dumps(result))
    record('onpc.enforcement-startup.recovered', json.dumps(result, sort_keys=True))
    print('onpc-system: enforcement-startup=sign-in-recovered', flush=True)
