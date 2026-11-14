#!/usr/bin/python3
"""One real station agent loss; the restored VM owns all fault state."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys

import system_guest as guest
from system_assertions import account_state, account_states
from system_kiosk_confinement import (ACCOUNT, SERVICES, graphical_session,
                                      process_identity, user_command, user_unit)

RECORD = guest.PAYLOAD / 'private/kiosk-agent-fault.json'
UNIT = SERVICES['polkit']


def digest(value):
    return hashlib.sha256(repr(value).encode()).hexdigest()


def manager(account):
    return guest.run(['systemctl', 'show', '--value', '--property=InvocationID',
                      f'user@{account.pw_uid}.service'])


def save(value, *, create=False):
    RECORD.parent.mkdir(mode=0o700, exist_ok=True)
    info = RECORD.parent.lstat()
    guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0
                  and stat.S_IMODE(info.st_mode) == 0o700, 'kiosk-agent:private-owner')
    flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_EXCL | os.O_CREAT if create else os.O_TRUNC)
    with os.fdopen(os.open(RECORD, flags, 0o600), 'w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


def read():
    marker = guest.guard()
    info = RECORD.lstat()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                  info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o600,
                  'kiosk-agent:record-owner')
    value = json.loads(RECORD.read_text())
    guest.require(value['run'] == marker['run'] and value['boot'] ==
                  Path('/proc/sys/kernel/random/boot_id').read_text(), 'kiosk-agent:record-identity')
    return value


def bound_account(value):
    account = pwd.getpwnam(ACCOUNT)
    guest.require(account.pw_uid == value['uid'] and manager(account) == value['manager']
                  and graphical_session(account)[0] == value['session'], 'kiosk-agent:session-replaced')
    return account


def stop_agent(account, original):
    """Never stop a replacement service or a process owned by another user."""
    guest.guard()
    guest.require(user_unit(account, UNIT) == original and original['ActiveState'] == 'active'
                  and re.fullmatch(r'[0-9a-f]{32}', original['InvocationID'])
                  and original['InvocationID'] != '0' * 32 and int(original['MainPID']) > 1,
                  'kiosk-agent:agent-replaced')
    process = Path('/proc') / original['MainPID']
    guest.require(process_identity(process)[2] == (str(account.pw_uid),) * 4 and
                  ('0::' + original['ControlGroup']) in (process / 'cgroup').read_text().splitlines(),
                  'kiosk-agent:process-owner')
    # Explicit stop suppresses Restart=on-failure; no PID signal or broker fault.
    user_command(account, ['systemctl', '--user', 'stop', UNIT], timeout=120)
    current = user_unit(account, UNIT)
    guest.require(current['ActiveState'] == 'inactive' and current['MainPID'] == '0',
                  'kiosk-agent:not-stopped')


def peers(value):
    identities = {name: pwd.getpwnam(name).pw_uid for name in value['peers']}
    states = account_states(identities.values())
    return {name: digest(states[uid]) for name, uid in identities.items()}


def begin():
    marker = guest.guard()
    guest.enable_diagnostics()
    account = pwd.getpwnam(ACCOUNT)
    configured = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())['kiosk_uid']
    guest.require(account.pw_uid == configured, 'kiosk-agent:account-identity')
    child = pwd.getpwnam('onpc-child-riley').pw_uid
    state = account_state(child)
    guest.require(state[3][1] == 0, 'kiosk-agent:initial-grant')
    value = {'run': marker['run'], 'boot': Path('/proc/sys/kernel/random/boot_id').read_text(),
             'uid': account.pw_uid, 'manager': manager(account),
             'session': graphical_session(account)[0], 'agent': user_unit(account, UNIT),
             'child': child, 'controls': digest(state[1:]),
             'peers': dict.fromkeys(('onpc-child-jordan', 'onpc-parent-jamie', 'onpc-parent-casey')),
             'state': 'prepared'}
    value['peers'] = peers(value)
    save(value, create=True)
    bound_account(value)
    stop_agent(account, value['agent'])
    value['state'] = 'stopped'
    save(value)
    return {'actual_agent_stopped': True}


def no_grant():
    value = read()
    account = bound_account(value)
    guest.require(value['state'] == 'stopped' and
                  user_unit(account, UNIT)['ActiveState'] == 'inactive', 'kiosk-agent:fault-not-held')
    guest.require(digest(account_state(value['child'])[1:]) == value['controls'] and
                  peers(value) == value['peers'], 'kiosk-agent:failure-changed-accounts')
    value['no_grant'] = True
    save(value)
    return {'no_grant': True, 'other_accounts_unchanged': True}


def restore():
    guest.guard()
    if not RECORD.exists():
        return {'agent_restored': True}  # Failure before fault creation.
    value = read()
    if value['state'] in ('restored', 'complete'):
        return {'agent_restored': True}
    account = bound_account(value)
    current = user_unit(account, UNIT)
    guest.require(current['ActiveState'] == 'inactive' or current == value['agent'],
                  'kiosk-agent:replacement-before-recovery')
    user_command(account, ['systemctl', '--user', 'start', UNIT], timeout=120)
    current = user_unit(account, UNIT)
    guest.require(current['ActiveState'] == 'active' and int(current['MainPID']) > 1
                  and (value['state'] == 'prepared' or
                       current['InvocationID'] != value['agent']['InvocationID']),
                  'kiosk-agent:recovery-not-active')
    value.update(state='restored', recovered_agent=current['InvocationID'])
    save(value)
    return {'agent_restored': True}


def complete():
    value = read()
    state = account_state(value['child'])
    guest.require(value['state'] == 'restored' and value.get('no_grant') is True
                  and state[3][1] > 0 and peers(value) == value['peers'],
                  'kiosk-agent:recovery-or-isolation-not-verified')
    value['state'] = 'complete'
    save(value)
    return {'fresh_approval': True, 'other_accounts_unchanged': True}


def verify():
    value = read()
    guest.require(value['state'] == 'complete' and value.get('no_grant') is True,
                  'kiosk-agent:host-history-not-complete')
    return {'actual_agent_failure_and_recovery': True}


if __name__ == '__main__':
    actions = {'begin': begin, 'no-grant': no_grant, 'restore': restore, 'complete': complete}
    guest.require(len(sys.argv) == 2 and sys.argv[1] in actions, 'kiosk-agent:arguments')
    print(json.dumps(actions[sys.argv[1]](), sort_keys=True))
