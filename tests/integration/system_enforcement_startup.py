"""Owned Ubuntu enforcement-readiness failure and explicit GDM recovery.

The existing package mount fixture pins and restores the readiness executable.
This is engineering fault injection, not customer UI acceptance.
"""

import json
from pathlib import Path
import pwd
import re
import shlex
import shutil
import tempfile
import time

import system_guest as guest
from product_logs import read_component
from system_assertions import accepted, account_state, call
from system_removal_faults import Fault, WITNESS, identity, mounted_fault


POLICY = 'fapolicyd.service'
DISPLAY = 'display-manager.service'
READY = Path('/usr/libexec/oh-no-parent-control-execution-policy-ready')


def require(condition, reason):
    guest.require(condition, 'enforcement-startup:' + reason)


def properties(unit, *names):
    raw = guest.run(['systemctl', 'show', unit, '--no-pager',
                     '--property=' + ','.join(names)])
    # systemctl emits one ExecStartPost row per configured command.
    return guest.parse_properties(raw, names, category='enforcement-startup:unit-observation',
                                  repeated=('ExecStartPost',))


def graphical_sessions():
    result = []
    for line in guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines():
        session = line.split()[0]
        raw = guest.run(['loginctl', 'show-session', session, '--property=Class',
                         '--property=Type', '--property=Active', '--property=Remote'])
        values = guest.parse_properties(raw, ('Class', 'Type', 'Active', 'Remote'),
                                        category='enforcement-startup:session-observation')
        if values['Type'] in ('wayland', 'x11'):
            require(values['Class'] == 'greeter', 'personal-session-active')
            result.append(values)
    return result


def verify_broker_reconciliation(record):
    """Obligation 141: policy write failure gates management, not GDM.

    Mount the original generated rules file read-only. Its pinned mount also
    refuses atomic replacement. The healthy daemon, canary and greeter keep
    their original invocation; existing mount receipts own fault removal.
    """
    guest.guard()
    require(guest.package_path().suffix == '.deb', 'broker-ubuntu-binding-required')
    accounts = [pwd.getpwnam(name).pw_uid for name in
                ('onpc-child-riley', 'onpc-child-jordan', 'onpc-parent-jamie')]
    parent = accounts[-1]
    require(bool(accepted(call(parent, 'ListManagedUsers'))), 'broker-initial-parent-query')
    before = {uid: account_state(uid) for uid in accounts}
    rules = guest.execution_rule_state()
    policy = Path('/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
    original = identity(policy)
    fault = Fault('broker-reconciliation', policy, original)
    evidence = {}
    output = guest.PAYLOAD / 'results' / 'broker-startup.json'
    output.parent.mkdir(mode=0o700, exist_ok=True)

    def gate(stage):
        # Generated directly from startup_observations.ENFORCEMENT and frozen
        # in this attempt's input manifest. Its canonical output is validated
        # again by that shared parser in the controller.
        raw = guest.commands.run(['/usr/bin/python3', '-B',
                                  str(guest.PAYLOAD / 'startup-enforcement.py')], timeout=45)
        require(raw.startswith(b'{'), 'broker-' + stage + '-healthy-gate')
        require(any(row['Active'] == 'yes' and row['Remote'] == 'no'
                    for row in graphical_sessions()), 'broker-' + stage + '-greeter')
        evidence[stage] = raw.decode('utf-8')
        output.write_text(json.dumps(evidence, sort_keys=True))
        return raw

    guest.run(['systemctl', 'stop', guest.BROKER])
    healthy = gate('before')

    def broker_events():
        return [json.loads(line) for line in read_component('broker').splitlines()
                if line.startswith('{')]

    previous_segments = {row['segment'] for row in broker_events()}
    try:
        with mounted_fault(fault, policy, record, readonly=True):
            try:
                # This is the real Parent startup operation under its own UID.
                reply = call(parent, 'ListManagedUsers')
                require('error' in reply and 'result' not in reply,
                        'broker-parent-available-during-fault')
                failed = properties(guest.BROKER, 'ActiveState', 'MainPID', 'Result', 'InvocationID')
                invocation = failed.pop('InvocationID')
                require(failed == {'ActiveState': 'failed', 'MainPID': '0', 'Result': 'exit-code'}
                        and re.fullmatch(r'[0-9a-f]{32}', invocation), 'broker-startup-not-failed')
                # The broker writes structured files, not journal messages.
                # One fresh process segment after the owned stop binds these
                # failures to this activation; old incidents cannot satisfy it.
                expected = {
                    'execution-policy.005': {'error_type': 'ExecutionPolicyError'},
                    'execution-policy.006': {'error_type': 'ExecutionPolicyError'},
                    'service.025': {},
                }
                deadline = time.monotonic() + 30
                while True:
                    events = [row for row in broker_events()
                              if row['component'] == 'broker' and row['segment'] not in previous_segments]
                    if len({row['segment'] for row in events}) == 1 and all(
                            any(row['event'] == event and row['fields'] == fields
                                and row['level'] == 'ERROR' for row in events)
                            for event, fields in expected.items()):
                        break
                    require(time.monotonic() < deadline, 'broker-policy-write-failure-not-observed')
                    time.sleep(0.2)
                require(any(row['event'] == 'service.023' for row in events) and
                        not any(row['event'] == 'service.ready' for row in events) and
                        properties(guest.BROKER, 'InvocationID') == {'InvocationID': invocation},
                        'broker-failure-activation-not-correlated')
                owner = guest.run(['busctl', '--system', 'call', 'org.freedesktop.DBus',
                                  '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                                  'NameHasOwner', 's', guest.BUS])
                require(owner == 'b false', 'broker-failed-startup-published')
                require(gate('during') == healthy, 'broker-fault-changed-login-gate')
                require(guest.execution_rule_state() == rules and
                        all(account_state(uid) == state for uid, state in before.items()),
                        'broker-fault-changed-policy-or-accounts')
                evidence['refused_ns'] = time.monotonic_ns()
                evidence['parent_error'] = reply['error']
                output.write_text(json.dumps(evidence, sort_keys=True))
                record('onpc.broker-startup.refused',
                       'policy-write-failure-observed; object-unpublished; parent-unavailable; '
                       'original-canary-and-greeter-healthy; accounts-unchanged')
                print('onpc-system: broker-startup=management-refused-login-healthy', flush=True)
            finally:
                # Drain activation before removing the owned policy mount.
                guest.run(['systemctl', 'stop', guest.BROKER])
    finally:
        require(identity(policy) == original, 'broker-policy-file-not-restored')
        guest.run(['systemctl', 'reset-failed', guest.BROKER])
        guest.activate_broker(restart=False)

    require(bool(accepted(call(parent, 'ListManagedUsers'))), 'broker-parent-recovery-query')
    require(gate('after') == healthy, 'broker-recovery-changed-login-gate')
    require(guest.execution_rule_state() == rules and
            all(account_state(uid) == state for uid, state in before.items()),
            'broker-recovery-changed-policy-or-accounts')
    evidence.update(owned_fault_removed=True, accounts_unchanged=True,
                    parent_query_recovered=True)
    output.write_text(json.dumps(evidence, sort_keys=True))
    record('onpc.broker-startup.recovered',
           'policy-mount-removed; real-parent-query-succeeded; login-gate-unchanged; accounts-unchanged')
    print('onpc-system: broker-startup=parent-management-recovered', flush=True)


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
