#!/usr/bin/python3
"""Engineering-only broker fault, bound to the guarded installed VM attempt.

The retained record owns one runtime mask. Recovery refuses another mask,
service invocation, boot or attempt rather than stopping a replacement service.
"""
import json
import os
import pwd
from pathlib import Path
import re
import stat
import sys

import system_guest as guest

MASK = Path('/run/systemd/system') / guest.BROKER
RECORD = guest.PAYLOAD / 'private/kiosk-feedback-fault.json'
BOOT = Path('/proc/sys/kernel/random/boot_id')


def service():
    value = dict(line.split('=', 1) for line in guest.run([
        'systemctl', 'show', '--property=ActiveState,LoadState,InvocationID',
        guest.BROKER], timeout=15).splitlines())
    guest.require(set(value) == {'ActiveState', 'LoadState', 'InvocationID'},
                  'kiosk-feedback:service-state')
    return value


def write_record(value, *, create=False):
    flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if create else os.O_TRUNC)
    fd = os.open(RECORD, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', closefd=False) as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def read_record(marker):
    info = RECORD.lstat()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and
                  stat.S_IMODE(info.st_mode) == 0o600, 'kiosk-feedback:record-owner')
    value = json.loads(RECORD.read_text())
    guest.require(set(value) == {'run', 'boot', 'invocation', 'mask', 'state'} and
                  value['run'] == marker['run'] and value['boot'] == BOOT.read_text() and
                  re.fullmatch(r'[0-9a-f]{32}', value['invocation']) and
                  value['invocation'] != '0' * 32 and
                  value['state'] in ('prepared', 'masked', 'stopped', 'unmasked', 'restored'),
                  'kiosk-feedback:record-identity')
    return value


def begin():
    marker = guest.guard()
    guest.require(not MASK.exists() and not MASK.is_symlink(), 'kiosk-feedback:mask-exists')
    original = service()
    guest.require(original['ActiveState'] == 'active' and original['LoadState'] == 'loaded' and
                  re.fullmatch(r'[0-9a-f]{32}', original['InvocationID']) and
                  original['InvocationID'] != '0' * 32, 'kiosk-feedback:broker-not-active')
    directory = RECORD.parent
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0 and
                  stat.S_IMODE(info.st_mode) == 0o700, 'kiosk-feedback:directory-owner')
    value = {'run': marker['run'], 'boot': BOOT.read_text(),
             'invocation': original['InvocationID'], 'mask': None, 'state': 'prepared'}
    write_record(value, create=True)
    guest.run(['systemctl', 'mask', '--runtime', guest.BROKER], timeout=30)
    info = MASK.lstat()
    guest.require(stat.S_ISLNK(info.st_mode) and info.st_uid == info.st_gid == 0 and
                  os.readlink(MASK) == '/dev/null', 'kiosk-feedback:mask-owner')
    value.update(mask=[info.st_dev, info.st_ino], state='masked')
    write_record(value)
    # Do not stop an independently restarted replacement invocation.
    guest.require(service()['InvocationID'] == value['invocation'],
                  'kiosk-feedback:broker-replaced')
    guest.run(['systemctl', 'stop', guest.BROKER], timeout=45)
    stopped = service()
    guest.require(stopped['ActiveState'] == 'inactive' and stopped['LoadState'] == 'masked',
                  'kiosk-feedback:broker-not-stopped')
    value['state'] = 'stopped'
    write_record(value)
    return {'broker_unavailable': True, 'runtime_mask_owned': True}


def restore():
    marker = guest.guard()
    if not RECORD.exists() and not RECORD.is_symlink():
        guest.require(not MASK.exists() and not MASK.is_symlink() and
                      service()['ActiveState'] == 'active', 'kiosk-feedback:unrecorded-fault')
        return {'broker_restored': True}
    value = read_record(marker)
    if value['state'] == 'restored':
        guest.require(service()['ActiveState'] == 'active', 'kiosk-feedback:recovery-not-active')
        return {'broker_restored': True}
    if value['state'] == 'prepared':
        # No recorded mask identity means an interrupted mutation is uncertain.
        guest.require(not MASK.exists() and not MASK.is_symlink() and
                      service()['InvocationID'] == value['invocation'],
                      'kiosk-feedback:unrecorded-mask-recovery-required')
        value['state'] = 'restored'
        write_record(value)
        return {'broker_restored': True}
    if value['state'] != 'unmasked':
        info = MASK.lstat()
        guest.require(stat.S_ISLNK(info.st_mode) and info.st_uid == info.st_gid == 0 and
                      [info.st_dev, info.st_ino] == value['mask'] and
                      os.readlink(MASK) == '/dev/null', 'kiosk-feedback:mask-replaced')
        current = service()
        guest.require(current['LoadState'] == 'masked' and
                      (current['ActiveState'] == 'inactive' or
                       current['ActiveState'] == 'active' and current['InvocationID'] == value['invocation']),
                      'kiosk-feedback:broker-replaced')
        guest.run(['systemctl', 'unmask', '--runtime', guest.BROKER], timeout=30)
        value['state'] = 'unmasked'
        write_record(value)
    guest.require(not MASK.exists() and not MASK.is_symlink(), 'kiosk-feedback:mask-replaced')
    guest.run(['systemctl', 'start', guest.BROKER], timeout=45)
    current = service()
    guest.require(current['LoadState'] == 'loaded' and current['ActiveState'] == 'active' and
                  re.fullmatch(r'[0-9a-f]{32}', current['InvocationID']) and
                  current['InvocationID'] != '0' * 32,
                  'kiosk-feedback:recovery-not-active')
    value['state'] = 'restored'
    write_record(value)
    return {'broker_restored': True}


def feedback_census():
    from system_kiosk_confinement import census
    # Supplement the public editor observation with session identity only.
    # Optional providers and a private MAC role census have no admission vote.
    value = census()
    return {'census': value}


def no_grant():
    """Engineering observation while this attempt still owns the stopped broker."""
    from system_assertions import session_limits
    marker = guest.guard()
    value = read_record(marker)
    info = MASK.lstat()
    guest.require(value['state'] == 'stopped' and stat.S_ISLNK(info.st_mode) and
                  [info.st_dev, info.st_ino] == value['mask'] and
                  info.st_uid == info.st_gid == 0 and os.readlink(MASK) == '/dev/null' and
                  service()['ActiveState'] == 'inactive', 'kiosk-feedback:fault-not-owned')
    account = pwd.getpwnam('onpc-child-riley')
    baseline = json.loads(guest.BASELINE.read_bytes())
    guest.require(baseline['accounts'].get(account.pw_name) ==
                  {'uid': account.pw_uid, 'role': 'standard'},
                  'kiosk-feedback:child-identity')
    _, _, extension = session_limits(account.pw_uid)
    guest.require(type(extension) is list and len(extension) == 2 and extension[1] == 0,
                  'kiosk-feedback:unexpected-grant')
    return {'broker_unavailable': True, 'no_grant': True}


if __name__ == '__main__':
    actions = {'begin': begin, 'restore': restore, 'census': feedback_census,
               'no-grant': no_grant}
    guest.require(len(sys.argv) == 2 and sys.argv[1] in actions,
                  'kiosk-feedback:arguments')
    print(json.dumps(actions[sys.argv[1]](), sort_keys=True))
