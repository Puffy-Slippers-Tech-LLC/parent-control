#!/usr/bin/python3
"""Engineering-only broker fault, bound to the guarded installed VM attempt.

The retained record owns one runtime mask. Recovery refuses another mask,
service invocation, boot or attempt rather than stopping a replacement service.
"""
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import sys

import system_guest as guest

MASK = Path('/run/systemd/system') / guest.BROKER
RECORD = guest.PAYLOAD / 'private/kiosk-feedback-fault.json'
BOOT = Path('/proc/sys/kernel/random/boot_id')
SCANNER = guest.PAYLOAD / 'private/kiosk-scanner-observer.json'
SCANNER_STOP = guest.PAYLOAD / 'private/kiosk-scanner-stop'
SCANNER_RESULT = guest.PAYLOAD / 'private/kiosk-scanner-result.json'


def observer_file(path, *, create=False, identity=None):
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC |
                 (os.O_CREAT | os.O_EXCL if create else 0), 0o600)
    try:
        info = os.fstat(fd)
        current = path.lstat()
        guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and
            stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1 and
            (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino) and
            (identity is None or [info.st_dev, info.st_ino] == identity),
            'kiosk-scanner:record-owner')
        return fd
    except BaseException:
        os.close(fd)
        raise


def observer_write(fd, value):
    data = (json.dumps(value, sort_keys=True) + '\n').encode()
    guest.require(len(data) <= 4096, 'kiosk-scanner:result-size')
    os.ftruncate(fd, 0)
    guest.require(os.pwrite(fd, data, 0) == len(data), 'kiosk-scanner:result-write')
    os.fsync(fd)


def scanner_start():
    """Spawn only a bounded read-only observer; retain its exact root identity."""
    from system_kiosk_confinement import observe_scanner, process_identity
    marker = guest.guard()
    directory = SCANNER.parent
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0 and
                  stat.S_IMODE(info.st_mode) == 0o700, 'kiosk-scanner:directory-owner')
    descriptors = []
    child = None
    pidfd = None
    committed = False
    try:
        record_fd = observer_file(SCANNER, create=True)
        descriptors.append(record_fd)
        stop_fd = observer_file(SCANNER_STOP, create=True)
        descriptors.append(stop_fd)
        result_fd = observer_file(SCANNER_RESULT, create=True)
        descriptors.append(result_fd)
        release_read, release_write = os.pipe2(os.O_CLOEXEC)
        descriptors.extend((release_read, release_write))
        ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
        descriptors.extend((ready_read, ready_write))
        child = os.fork()
        if child == 0:
            os.close(release_write)
            os.close(ready_read)
            os.close(record_fd)
            try:
                os.setsid()
                with open('/dev/null', 'r+b', buffering=0) as null:
                    for fd in (0, 1, 2):
                        os.dup2(null.fileno(), fd)
                guest.require(os.read(release_read, 1) == b'G', 'kiosk-scanner:observer-release')
                os.close(release_read)
                result = observe_scanner(stop_fd, lambda: os.write(ready_write, b'R'))
                observer_write(result_fd, result)
                os._exit(0)
            except BaseException as error:
                category = str(error) if isinstance(error, guest.GuestError) else 'internal'
                if not re.fullmatch(r'[a-z][a-z0-9:-]*', category):
                    category = 'internal'
                try:
                    observer_write(result_fd, {'scanner_observed': False, 'observation': 'rejected',
                                               'category': category})
                except BaseException:
                    pass
                os._exit(124)
        pidfd = os.pidfd_open(child)
        identity = process_identity(Path('/proc') / str(child))
        guest.require(identity[1:] == (os.getpid(), ('0',) * 4), 'kiosk-scanner:observer-identity')
        def inode(fd):
            value = os.fstat(fd)
            return [value.st_dev, value.st_ino]
        observer_write(record_fd, {'run': marker['run'], 'boot': BOOT.read_text(), 'pid': child,
                                  'starttime': identity[0], 'stop': inode(stop_fd), 'result': inode(result_fd)})
        os.close(release_read)
        descriptors.remove(release_read)
        os.close(ready_write)
        descriptors.remove(ready_write)
        os.write(release_write, b'G')
        poll = select.poll()
        poll.register(ready_read, select.POLLIN | select.POLLHUP)
        guest.require(bool(poll.poll(10000)) and os.read(ready_read, 1) == b'R',
                      'kiosk-scanner:observer-not-ready')
        committed = True
        return {'scanner_observer_started': True}
    finally:
        for fd in descriptors:
            os.close(fd)
        if child is not None and child > 0 and not committed:
            # This unreaped directly spawned identity cannot have recycled.
            try:
                if pidfd is None:
                    os.kill(child, signal.SIGKILL)
                else:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(child, 0)
        if pidfd is not None:
            os.close(pidfd)


def scanner_finish():
    """Stop only the recorded observer, preserving unknown/replaced resources."""
    from system_kiosk_confinement import exited, process_identity
    marker = guest.guard()
    if not SCANNER.exists() and not SCANNER.is_symlink():
        guest.require(not SCANNER_STOP.exists() and not SCANNER_RESULT.exists(),
                      'kiosk-scanner:unrecorded-observer')
        return {'scanner_observed': False, 'observation': 'not-started'}
    with os.fdopen(observer_file(SCANNER), 'r') as stream:
        value = json.loads(stream.read(4097))
    guest.require(set(value) == {'run', 'boot', 'pid', 'starttime', 'stop', 'result'} and
        value['run'] == marker['run'] and value['boot'] == BOOT.read_text() and
        type(value['pid']) is int and value['pid'] > 1 and isinstance(value['starttime'], str) and
        value['starttime'].isdigit() and all(isinstance(value[key], list) and len(value[key]) == 2 and
        all(type(item) is int for item in value[key]) for key in ('stop', 'result')),
        'kiosk-scanner:observer-record')
    stop_fd = observer_file(SCANNER_STOP, identity=value['stop'])
    try:
        result_fd = observer_file(SCANNER_RESULT, identity=value['result'])
        try:
            process = Path('/proc') / str(value['pid'])
            pidfd = None
            try:
                pidfd = os.pidfd_open(value['pid'])
            except ProcessLookupError:
                pass
            if pidfd is not None:
                try:
                    try:
                        identity = process_identity(process)
                    except (FileNotFoundError, ProcessLookupError):
                        guest.require(exited(pidfd), 'kiosk-scanner:live-observer-unreadable')
                    else:
                        guest.require(identity[0] == value['starttime'] and identity[2] == ('0',) * 4,
                                      'kiosk-scanner:observer-replaced')
                        guest.require(os.pwrite(stop_fd, b'stop\n', 0) == 5, 'kiosk-scanner:stop-write')
                        os.fsync(stop_fd)
                    poll = select.poll()
                    poll.register(pidfd, select.POLLIN)
                    stopped = bool(poll.poll(10000))
                    if not stopped:
                        try:
                            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        guest.require(bool(poll.poll(10000)), 'kiosk-scanner:observer-kill-timeout')
                    try:
                        os.waitpid(value['pid'], 0)
                    except ChildProcessError:
                        pass  # The real start command already exited; init reaps.
                    guest.require(stopped, 'kiosk-scanner:observer-stop-timeout')
                finally:
                    os.close(pidfd)
            data = os.pread(result_fd, 4097, 0)
            guest.require(bool(data) and len(data) <= 4096, 'kiosk-scanner:result-missing')
            result = json.loads(data)
            guest.require(isinstance(result, dict) and type(result.get('scanner_observed')) is bool and
                result.get('observation') in ('observed', 'not-observed', 'rejected') and
                result['scanner_observed'] == (result['observation'] == 'observed'),
                'kiosk-scanner:result-content')
            return result
        finally:
            os.close(result_fd)
    finally:
        os.close(stop_fd)


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
    value = census(required_roles=('manager', 'app', 'service', 'wellbeing', 'pipewire', 'webkit'))
    # A configured profile is not evidence of a scanner which already exited.
    # All live threads retain strict checks; transient scanner proof is distinct.
    scanner = 'onpc-kiosk-scanner' if value['backend'] == 'apparmor' else 'onpc_kiosk_scanner_t'
    return {'census': value, 'scanner_observed': value['confined_thread_roles'].get(scanner, 0) > 0}


if __name__ == '__main__':
    actions = {'begin': begin, 'restore': restore, 'census': feedback_census,
               'scanner-start': scanner_start, 'scanner-finish': scanner_finish}
    guest.require(len(sys.argv) == 2 and sys.argv[1] in actions,
                  'kiosk-feedback:arguments')
    print(json.dumps(actions[sys.argv[1]](), sort_keys=True))
