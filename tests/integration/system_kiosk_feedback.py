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
import time

import system_guest as guest

MASK = Path('/run/systemd/system') / guest.BROKER
RECORD = guest.PAYLOAD / 'private/kiosk-feedback-fault.json'
BOOT = Path('/proc/sys/kernel/random/boot_id')
READER = guest.PAYLOAD / 'product_failure_journal.py'
PREFERENCES = Path('/var/lib/oh-no-parent-control/preferences')
OUTAGE_SOURCES = {('parent', 'gtk'), ('child', 'gnome-shell'), ('kiosk', 'gtk')}
REBOOT_PROBE = 'onpc-product-fault-qualification.service'


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
    from product_failure_journal import action_time

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
    fault_time = action_time()
    identity = guest.runtime_service_mask(guest.BROKER, category='kiosk-feedback')
    value.update(mask=list(identity), state='masked')
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
    return {'broker_unavailable': True, 'runtime_mask_owned': True, 'fault_time': fault_time}


def restore():
    from product_failure_journal import action_time

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
        identity = tuple(value['mask'])
        guest.runtime_service_mask(guest.BROKER, category='kiosk-feedback', identity=identity)
        current = service()
        guest.require(current['LoadState'] == 'masked' and
                      (current['ActiveState'] == 'inactive' or
                       current['ActiveState'] == 'active' and current['InvocationID'] == value['invocation']),
                      'kiosk-feedback:broker-replaced')
        guest.remove_runtime_service_mask(guest.BROKER, identity, category='kiosk-feedback')
        value['state'] = 'unmasked'
        write_record(value)
    guest.require(not MASK.exists() and not MASK.is_symlink(), 'kiosk-feedback:mask-replaced')
    guest.run(['systemctl', 'start', guest.BROKER], timeout=45)
    current = service()
    guest.require(current['LoadState'] == 'loaded' and current['ActiveState'] == 'active' and
                  re.fullmatch(r'[0-9a-f]{32}', current['InvocationID']) and
                  current['InvocationID'] != '0' * 32,
                  'kiosk-feedback:recovery-not-active')
    fault_time = action_time()
    value['state'] = 'restored'
    write_record(value)
    return {'broker_restored': True, 'fault_time': fault_time}


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
    guest.runtime_service_mask(guest.BROKER, category='kiosk-feedback',
                               identity=tuple(value['mask']))
    guest.require(value['state'] == 'stopped' and
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


def qualification_uids(*, child_name='onpc-child-riley'):
    baseline = json.loads(guest.BASELINE.read_bytes())['accounts']
    parent = pwd.getpwnam('onpc-parent-jamie')
    child = pwd.getpwnam(child_name)
    kiosk = pwd.getpwnam('oh-no-parent-control')
    guest.require(all(baseline.get(account.pw_name, {}).get('uid') == account.pw_uid
                      for account in (parent, child)) and
                  kiosk.pw_dir == '/home/oh-no-parent-control' and
                  len({0, parent.pw_uid, child.pw_uid, kiosk.pw_uid}) == 4,
                  'kiosk-feedback:signal-account-identity')
    return parent.pw_uid, child.pw_uid, kiosk.pw_uid


def journal(*args):
    return guest.run(['/usr/bin/python3', '-B', str(READER), *args], timeout=30)


def failure_boundary():
    return journal('boundary')


def failure_observation(start, end, uids):
    observation = json.loads(journal('read', start, end, *map(str, uids)))
    guest.require(observation['complete'] is True,
                  'kiosk-feedback:failure-span-incomplete:' + observation['reason'])
    return observation


def failures(start, end, uids):
    return failure_observation(start, end, uids)['events']


def outage_failures(start):
    from system_assertions import call

    marker = guest.guard()
    uids = qualification_uids()
    record = read_record(marker)
    identity = tuple(record['mask'])
    guest.require(record['state'] == 'stopped', 'kiosk-feedback:outage-record')
    deadline = time.monotonic() + 80
    while True:
        observation = failure_observation(start, failure_boundary(), uids)
        events = observation['events']
        # The owned mask and public failure establish the outage. The OS can
        # classify the failed call differently while the emitter remains visible.
        sources = {(event['component'], event['source']) for event in events}
        if OUTAGE_SOURCES <= sources:
            break
        if time.monotonic() >= deadline:
            missing = sorted(component for component, _ in OUTAGE_SOURCES - sources)
            kinds = sorted({(event['component'], event['category'], event['source'])
                            for event in events})
            reply = call(uids[0], 'ListManagedUsers')
            error = reply.get('error', 'unexpected-success')
            if not isinstance(error, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', error):
                error = 'unknown'
            raise guest.GuestError(
                'kiosk-feedback:outage-signal-missing:' + ','.join(missing)
                + ':observed=' + ','.join('/'.join(kind) for kind in kinds)
                + ':unattributed=' + str(observation['unattributed'])
                + ':activation=' + error)
        time.sleep(1)
    guest.runtime_service_mask(guest.BROKER, category='kiosk-feedback', identity=identity)
    observed = service()
    guest.require(observed['ActiveState'] == 'inactive' and observed['LoadState'] == 'masked',
                  'kiosk-feedback:signal-broker-not-unavailable')
    return {'broker_unavailable': True, 'failure_roles': sorted(role for role, _ in OUTAGE_SOURCES)}


def broker_failures(probe='combined'):
    from product_failure_journal import action_time
    from system_assertions import accepted, account_property, call

    guest.guard()
    uids = qualification_uids()
    # Parent and the kiosk still use Riley during the graphical probe.
    # Corrupt Jordan's preferences so their background reads stay healthy.
    fault_uids = qualification_uids(child_name='onpc-child-jordan') if probe == 'combined' else uids
    parent, child, _ = fault_uids
    original_service = service()
    guest.require(original_service['ActiveState'] == 'active' and
                  original_service['LoadState'] == 'loaded', 'kiosk-feedback:signal-broker-inactive')
    policy = account_property(child, 'com.endlessm.ParentalControls.AppFilter', 'AppFilter')
    guest.require(policy[0] is False, 'kiosk-feedback:signal-account-not-denylist')
    if probe == 'combined':
        guest.require(child != uids[1], 'kiosk-feedback:signal-target-overlaps-journey')
        seed_preferences(fault_uids)

    def get_preferences():
        return call(parent, 'GetPreferences', '(u)', (child,))

    expected = accepted(get_preferences())
    for directory in (PREFERENCES.parent, PREFERENCES):
        info = directory.lstat()
        guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
                      'kiosk-feedback:signal-preference-directory')
    path = PREFERENCES / f'{child}.json'
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        original = os.fstat(fd)
        guest.require(stat.S_ISREG(original.st_mode) and original.st_uid == 0 and
                      not original.st_mode & 0o022 and original.st_nlink == 1 and
                      0 < original.st_size <= 65536 and os.path.samestat(original, path.lstat()),
                      'kiosk-feedback:signal-preference-file')
        contents = os.pread(fd, original.st_size + 1, 0)
        guest.require(len(contents) == original.st_size and isinstance(json.loads(contents), dict),
                      'kiosk-feedback:signal-preference-content')
        fault_start = start = failure_boundary()
        guest.require(os.pread(fd, len(contents) + 1, 0) == contents and
                      os.path.samestat(original, path.lstat()),
                      'kiosk-feedback:signal-preference-changed')
        # Append one byte to the pinned fixture inode. A partial write cannot
        # introduce a second byte, and cleanup never truncates a replacement.
        allowance_start = action_time()
        try:
            guest.require(os.pwrite(fd, b'[', len(contents)) == 1,
                          'kiosk-feedback:signal-preference-injection')
            stamps = set()
            for _ in range({'combined': 2, 'backend': 1, 'log-only': 0}[probe]):
                guest.require(get_preferences() == {'error': guest.BUS + '.Error.BackendFailure'},
                              'kiosk-feedback:broker-did-not-report-backend-failure')
                if probe == 'backend':
                    break  # Restore before waiting for the journal or a reconciliation tick.
                end = failure_boundary()
                stamps_in_span = {event['monotonic_usec'] for event in failures(start, end, uids)
                                  if (event['component'], event['category'], event['source']) ==
                                  ('broker', 'backend', 'broker')}
                guest.require(stamps_in_span and not stamps.intersection(stamps_in_span),
                              'kiosk-feedback:broker-repeat-missing')
                stamps.update(stamps_in_span)
                start = end

            # The periodic policy reconciliation rereads this file without a
            # caller. Its operation failure qualifies the log-only producer.
            if probe != 'backend':
                deadline = time.monotonic() + 70
                while not any((event['component'], event['category'], event['source']) ==
                              ('broker', 'operation', 'broker')
                              for event in failures(start, failure_boundary(), uids)):
                    guest.require(time.monotonic() < deadline, 'kiosk-feedback:broker-log-only-missing')
                    time.sleep(1)
        finally:
            current = os.fstat(fd)
            mutated = os.pread(fd, len(contents) + 2, 0)
            guest.require(os.path.samestat(original, current) and
                          os.path.samestat(original, path.lstat()) and current.st_nlink == 1 and
                          mutated in (contents, contents + b'['),
                          'kiosk-feedback:signal-preference-cleanup-ownership')
            os.ftruncate(fd, len(contents))
            allowance_end = action_time()
            os.utime(fd, ns=(original.st_atime_ns, original.st_mtime_ns))
            os.fsync(fd)
    finally:
        os.close(fd)
    guest.require(service() == original_service and accepted(get_preferences()) == expected,
                  'kiosk-feedback:broker-preference-not-recovered')
    end = failure_boundary()
    if probe == 'backend':
        stamps = {event['monotonic_usec'] for event in failures(start, end, uids)
                  if (event['component'], event['category'], event['source']) ==
                  ('broker', 'backend', 'broker')}
        guest.require(len(stamps) == 1, 'kiosk-feedback:broker-backend-signal-missing')
    return {'backend_occurrences': len(stamps), 'operation_observed': probe != 'backend',
            'restored': True, 'fault_start': json.loads(fault_start), 'fault_end': json.loads(end),
            'fault_allowance': [allowance_start, allowance_end]}


def seed_preferences(uids=None):
    from system_assertions import accepted, call

    guest.guard()
    parent, child, _ = qualification_uids() if uids is None else uids
    before = accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0]
    accepted(call(parent, 'SetPreferences', '(us)', (child, before)))
    guest.require(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0] == before,
                  'kiosk-feedback:preferences-seed-not-preserved')
    return {'preferences_verified': True}


def prepare_startup_probe():
    """Place a single real broker fault before the next boot's SSH readiness."""
    marker = guest.guard()
    guest.require(re.fullmatch(r'[a-f0-9]{32}', marker['run']),
                  'kiosk-feedback:reboot-probe-selection')
    path = Path('/etc/systemd/system') / REBOOT_PROBE
    program = f'{sys.executable} -B {__file__} observe-reboot-startup'
    # Exclusive creation within the already owned guest. The attempt's
    # baseline restoration removes both this unit and its enablement.
    with path.open('x', encoding='ascii') as unit:
        unit.write(f'[Unit]\nRequires={guest.BROKER}\nWants=accounts-daemon.service\n'
                   f'After={guest.BROKER} accounts-daemon.service dbus.service\n'
                   'Before=ssh.service sshd.service\n'
                   f'[Service]\nType=oneshot\nTimeoutSec=50\n'
                   f'Environment=ONPC_EXPECTED_RUN={marker["run"]}\nExecStart={program}\n'
                   '[Install]\nWantedBy=multi-user.target\n')
    guest.run(['systemctl', 'enable', REBOOT_PROBE], timeout=20)
    return {'armed': 'startup', 'boot': BOOT.read_text().strip().replace('-', '')}


def observe_startup_probe():
    guest.guard()
    ssh = guest.run(['systemctl', 'show', 'ssh.service', '--property=ActiveState',
                     '--value'], timeout=10).strip()
    guest.require(ssh == 'inactive', 'kiosk-feedback:reboot-ssh-already-started')
    result = broker_failures('backend')
    RECORD.parent.mkdir(mode=0o700, exist_ok=True)
    with (RECORD.parent / 'fault-startup.json').open('x', encoding='ascii') as report:
        json.dump(result, report)
    return result


def signal_start():
    guest.guard()
    journal('exercise')
    return {'boundary': json.loads(failure_boundary()), 'settlement_exercised': True}


def healthy_failures(start):
    guest.guard()
    end = failure_boundary()
    guest.require(not failures(start, end, qualification_uids()),
                  'kiosk-feedback:healthy-actions-signalled-failure')
    return {'failure_events': 0, 'boundary': json.loads(end)}


if __name__ == '__main__':
    actions = {'begin': begin, 'restore': restore, 'census': feedback_census,
               'no-grant': no_grant, 'signal-start': signal_start, 'broker-signals': broker_failures,
               'seed-preferences': seed_preferences,
               'broker-backend': lambda: broker_failures('backend'),
               'broker-log-only': lambda: broker_failures('log-only'),
               'arm-reboot-startup': prepare_startup_probe,
               'observe-reboot-startup': observe_startup_probe}
    spans = {'healthy-signals': healthy_failures, 'outage-signals': outage_failures}
    if len(sys.argv) == 3 and sys.argv[1] in spans:
        value = spans[sys.argv[1]](sys.argv[2])
    else:
        guest.require(len(sys.argv) == 2 and sys.argv[1] in actions, 'kiosk-feedback:arguments')
        value = actions[sys.argv[1]]()
    print(json.dumps(value, sort_keys=True))
