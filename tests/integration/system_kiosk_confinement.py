"""Installed kernel-boundary probes, separate from customer UI acceptance."""
import ctypes
import errno
import json
import os
from pathlib import Path
import pwd
import select
import signal
import sys
import time
import tempfile
import shutil
import hashlib
import runpy
import shlex
import re
import stat
from contextlib import ExitStack, contextmanager

import system_guest as guest


ENV = ['PATH=/usr/bin:/bin', 'LANG=C', 'LC_ALL=C']
PROC = Path('/proc')
MANAGER_SID = 'system_u:system_r:onpc_kiosk_manager_t:s0'


def wait_kiosk_inactive(account, *,
                        identity_category='kiosk-confinement:kiosk-identity-changed',
                        active_category='kiosk-confinement:manager-already-active'):
    """Let a completed GDM logout settle without adopting or stopping its manager."""
    deadline = time.monotonic() + 75
    unit = f'user@{account.pw_uid}.service'
    while True:
        guest.guard()
        guest.require(pwd.getpwnam('oh-no-parent-control').pw_uid == account.pw_uid,
                      identity_category)
        state = guest.run(['systemctl', 'show', '--value', '--property=ActiveState', unit])
        if state in ('inactive', 'failed'):
            return
        guest.require(state in ('active', 'activating', 'deactivating') and
                      time.monotonic() < deadline, active_category)
        time.sleep(0.25)


def exited(pidfd):
    poll = select.poll()
    poll.register(pidfd, select.POLLIN)
    return bool(poll.poll(0))


def process_identity(process):
    # The comm field can contain spaces and parentheses; fields after its last
    # ')' begin at stat field 3. Keep starttime to detect reuse as well as exit.
    fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
    status = dict(line.split(':', 1) for line in (process / 'status').read_text().splitlines()
                  if ':' in line)
    return (fields[19], int(status['PPid']), tuple(status['Uid'].split()))


def confined_thread_roles(thread, config, backend, generation, host_namespace):
    guest.require(os.readlink(thread / 'ns/mnt') != host_namespace,
                  'kiosk-census:unconfined-namespace')
    marker = 'usr/share/oh-no-parent-control/confinement/generation'
    guest.require((thread / 'root' / marker).read_text() == generation,
                  'kiosk-census:unconfined-generation')
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    label = (thread / attribute).read_text().strip().rstrip('\0')
    if backend == 'apparmor':
        guest.require(label.endswith(' (enforce)'), 'kiosk-census:unenforced-thread')
        roles = label.removesuffix(' (enforce)').split('//&')
        guest.require(all(role in config['apparmor_profiles'] for role in roles),
                      'kiosk-census:unconfined-thread')
        return roles
    roles = label.split(':')
    guest.require(len(roles) == 4 and roles[:2] == ['system_u', 'system_r'] and
        roles[3] == 's0' and roles[2] in {
            'onpc_kiosk_' + name.replace('-', '_') + '_t' for name in config['domains']},
        'kiosk-census:unconfined-thread')
    return [roles[2]]


def census(*, required_roles=('manager', 'app', 'service', 'wellbeing', 'pipewire')):
    """Read-only engineering check after the real GDM request form appears.

    Include every process with any kiosk UID and every surviving thread. This
    catches daemons forked by earlier PAM callbacks, not just the final app.
    Only role counts leave the guest; command lines and account data do not.
    """
    guest.guard()
    account = pwd.getpwnam('oh-no-parent-control')
    payload = Path('/usr/share/oh-no-parent-control/confinement')
    config = json.loads((payload / 'config.json').read_text())
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    preparation['enforcing'](config)
    backend = config['backend']
    unit = f'user@{account.pw_uid}.service'
    manager = PROC / str(manager_pid(unit))
    manager_fd = os.pidfd_open(int(manager.name))
    try:
        deadline = time.monotonic() + 5
        first_race = None
        while True:
            try:
                return census_processes(account, config, backend, manager, manager_fd, unit,
                                        required_roles=required_roles)
            except guest.GuestError as error:
                # A changing task set is not a security-policy refusal. Discard
                # the whole observation and keep the original manager pinned.
                if str(error) != 'kiosk-census:process-lifecycle-changed':
                    raise
                if first_race is None:
                    first_race = error
                if time.monotonic() >= deadline:
                    raise first_race
                time.sleep(0.05)
                guest.guard()
                preparation['enforcing'](config)
                guest.require(not exited(manager_fd) and
                              manager_pid(unit) == int(manager.name),
                              'kiosk-census:manager-lifecycle-changed')
                if time.monotonic() >= deadline:
                    raise first_race
    finally:
        os.close(manager_fd)


def census_processes(account, config, backend, manager, manager_fd, unit, *,
                     required_roles=('manager', 'app', 'service', 'wellbeing', 'pipewire')):
    payload = Path('/usr/share/oh-no-parent-control/confinement')
    manager_identity = process_identity(manager)
    guest.require(manager_identity[2] == (str(account.pw_uid),) * 4,
                  'kiosk-census:manager-uid')
    marker = str(payload / 'generation').lstrip('/')
    generation = (manager / 'root' / marker).read_text()
    guest.require(generation.strip() != 'unconfined', 'kiosk-census:manager-generation')
    host_namespace = os.readlink(PROC / '1/ns/mnt')
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    expected = 'onpc-kiosk-manager (enforce)' if backend == 'apparmor' else MANAGER_SID
    guest.require((manager / attribute).read_text().strip().rstrip('\0') == expected,
                  'kiosk-census:manager-label')
    counts = {}
    for process in PROC.iterdir():
        if not process.name.isdecimal():
            continue
        pidfd = None
        try:
            pidfd = os.pidfd_open(int(process.name))
            identity = process_identity(process)
            threads = {thread: process_identity(thread) for thread in (process / 'task').iterdir()}
            # Linux credentials belong to individual threads. A root leader
            # must not hide a sibling which adopted any kiosk credential.
            relevant = any(str(account.pw_uid) in value[2] for value in threads.values())
            if (relevant and backend == 'selinux' and
                    (process / 'attr/current').read_text().strip().rstrip('\0') ==
                    'system_u:system_r:policykit_auth_t:s0'):
                password_helper_process(process, account, config, manager, generation,
                                        host_namespace, identity, threads)
                counts['policykit_auth_t'] = counts.get('policykit_auth_t', 0) + len(threads)
                relevant = False
            for thread in threads if relevant else ():
                for role in confined_thread_roles(thread, config, backend, generation, host_namespace):
                    counts[role] = counts.get(role, 0) + 1
            guest.require(set((process / 'task').iterdir()) == set(threads) and
                          all(process_identity(thread) == value for thread, value in threads.items()) and
                          process_identity(process) == identity and not exited(pidfd),
                          'kiosk-census:process-lifecycle-changed')
        except (FileNotFoundError, ProcessLookupError):
            if pidfd is not None:
                guest.require(exited(pidfd), 'kiosk-census:live-process-unreadable')
        finally:
            if pidfd is not None:
                os.close(pidfd)
    guest.require(not exited(manager_fd) and process_identity(manager) == manager_identity and
                  manager_pid(unit) == int(manager.name), 'kiosk-census:manager-lifecycle-changed')
    guest.require(all(role in config['domains'] for role in required_roles),
                  'kiosk-census:unknown-required-role')
    for role in required_roles:
        name = ('onpc-kiosk-' + role if backend == 'apparmor'
                else 'onpc_kiosk_' + role.replace('-', '_') + '_t')
        guest.require(counts.get(name, 0) > 0, 'kiosk-census:required-service-missing:' + role)
    return {'backend': backend, 'confined_thread_roles': counts}


def password_helper_process(process, account, config, manager, generation,
                            host_namespace, identity, threads):
    """Qualify one measured Fedora native helper, never a domain-wide exception."""
    path = '/usr/lib/polkit-1/polkit-agent-helper-1'
    expected = dict(path=path, mode=0o4755,
                    label='system_u:object_r:policykit_auth_exec_t:s0')
    guest.require(config.get('preserved_executables') == [expected] and
                  re.fullmatch(r'[0-9a-f]{64}\n', generation) is not None,
                  'kiosk-password:unmeasured-inventory')
    # The global enforcing bit alone does not exclude a permissive helper
    # domain. Reuse the installed preparation check, including its vendor SID.
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    preparation['enforcing'](config)
    parent = PROC / str(identity[1])
    parent_fd = os.pidfd_open(identity[1])
    try:
        parent_identity = process_identity(parent)
        parent_threads = {thread: process_identity(thread) for thread in (parent / 'task').iterdir()}
        namespace = os.readlink(manager / 'ns/mnt')
        guest.require(namespace != host_namespace and bool(threads) and bool(parent_threads),
                      'kiosk-password:empty-or-host-namespace')
        marker = 'usr/share/oh-no-parent-control/confinement/generation'
        for thread, value in threads.items():
            guest.require(value[2] == (str(account.pw_uid), '0', '0', '0') and
                          value[1] == int(parent.name), 'kiosk-password:credentials')
            guest.require((thread / 'attr/current').read_text().strip().rstrip('\0') ==
                          'system_u:system_r:policykit_auth_t:s0', 'kiosk-password:thread-label')
            guest.require(os.readlink(thread / 'ns/mnt') == namespace and
                          (thread / 'root' / marker).read_text() == generation,
                          'kiosk-password:namespace-generation')
        for thread, value in parent_threads.items():
            guest.require(value[2] == (str(account.pw_uid),) * 4 and
                          os.readlink(thread / 'ns/mnt') == namespace and
                          confined_thread_roles(thread, config, 'selinux', generation, host_namespace) ==
                          ['onpc_kiosk_polkit_t'], 'kiosk-password:parent-role')
        parent_exe = (parent / 'exe').stat()
        guest.require(any((parent_exe.st_dev, parent_exe.st_ino) ==
                          (pinned.st_dev, pinned.st_ino)
                          for entry in config['executables'] if entry['role'] == 'polkit'
                          for name in entry['paths']
                          for pinned in [(manager / 'root' / name.lstrip('/')).stat()]),
                      'kiosk-password:parent-executable')
        pinned = manager / 'root' / path.lstrip('/')
        with pinned.open('rb') as stream:
            before = os.fstat(stream.fileno())
            guest.require(stat.S_ISREG(before.st_mode) and before.st_nlink in (0, 1) and
                          before.st_uid == before.st_gid == 0 and
                          stat.S_IMODE(before.st_mode) == expected['mode'] and
                          stream.read(4) == b'\x7fELF' and
                          'security.capability' not in os.listxattr(stream.fileno()) and
                          os.getxattr(stream.fileno(), 'security.selinux').rstrip(b'\0').decode('ascii') ==
                          expected['label'], 'kiosk-password:executable-metadata')
            stream.seek(0)
            record = dict(expected, uid=0, gid=0,
                          sha256=hashlib.file_digest(stream, 'sha256').hexdigest())
            after = os.fstat(stream.fileno())
            guest.require(all(getattr(before, field) == getattr(after, field) for field in
                          ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_uid', 'st_gid',
                           'st_mtime_ns', 'st_ctime_ns')), 'kiosk-password:executable-changed')
        manifest = json.loads((Path('/run/oh-no-parent-control-confinement') /
                               generation.strip() / 'records.json').read_text())
        guest.require(manifest.get('preserved') == [record], 'kiosk-password:generation-inventory')
        for target in (*threads, manager):
            visible = (target / 'root' / path.lstrip('/')).stat()
            mounts = [line.split() for line in (target / 'mountinfo').read_text().splitlines()
                      if line.split()[4] == path]
            guest.require((visible.st_dev, visible.st_ino) == (before.st_dev, before.st_ino) and
                          len(mounts) == 1 and 'ro' in mounts[0][5].split(','),
                          'kiosk-password:unpinned-executable')
        for thread in threads:
            actual = (thread / 'exe').stat()
            guest.require((actual.st_dev, actual.st_ino) == (before.st_dev, before.st_ino) and
                          (thread / 'attr/current').read_text().strip().rstrip('\0') ==
                          'system_u:system_r:policykit_auth_t:s0' and
                          os.readlink(thread / 'ns/mnt') == namespace and
                          (thread / 'root' / marker).read_text() == generation,
                          'kiosk-password:helper-lifecycle-changed')
        guest.require(set((parent / 'task').iterdir()) == set(parent_threads) and
                      all(process_identity(thread) == value for thread, value in parent_threads.items()) and
                      process_identity(parent) == parent_identity and not exited(parent_fd) and
                      all(os.readlink(thread / 'ns/mnt') == namespace and
                          confined_thread_roles(thread, config, 'selinux', generation, host_namespace) ==
                          ['onpc_kiosk_polkit_t'] for thread in parent_threads) and
                      ((parent / 'exe').stat().st_dev, (parent / 'exe').stat().st_ino) ==
                      (parent_exe.st_dev, parent_exe.st_ino),
                      'kiosk-password:parent-lifecycle-changed')
    finally:
        os.close(parent_fd)


def scanner_process(process, account, config, manager, generation, host_namespace):
    """Observe a real scanner and its live admitted parent, without signalling."""
    descriptors = []
    try:
        scanner_fd = os.pidfd_open(int(process.name))
        descriptors.append(scanner_fd)
        identity = process_identity(process)
        threads = {thread: process_identity(thread) for thread in (process / 'task').iterdir()}
        if not any(str(account.pw_uid) in value[2] for value in threads.values()):
            return None
        parent = PROC / str(identity[1])
        parent_fd = os.pidfd_open(identity[1])
        descriptors.append(parent_fd)
        parent_identity = process_identity(parent)
        parent_exe = (parent / 'exe').stat()
        parent_threads = {thread: process_identity(thread) for thread in (parent / 'task').iterdir()}
        backend = config['backend']
        role_name = lambda name: ('onpc-kiosk-' + name if backend == 'apparmor'
                                  else 'onpc_kiosk_' + name + '_t')
        counts = []
        namespaces = set()
        thread_roles = {}
        for snapshot, expected in ((threads, {role_name('scanner')}),
                                   (parent_threads, {role_name('app'), role_name('webkit')})):
            roles_seen = {}
            for thread, status in snapshot.items():
                guest.require(status[2] == (str(account.pw_uid),) * 4, 'kiosk-scanner:mixed-credentials')
                roles = confined_thread_roles(thread, config, backend, generation, host_namespace)
                guest.require(bool(set(roles) & expected), 'kiosk-scanner:unexpected-role')
                thread_roles[thread] = roles
                namespaces.add(os.readlink(thread / 'ns/mnt'))
                for role in roles:
                    roles_seen[role] = roles_seen.get(role, 0) + 1
            guest.require(bool(roles_seen), 'kiosk-scanner:empty-threads')
            counts.append(roles_seen)
        guest.require(len(namespaces) == 1, 'kiosk-scanner:parent-namespace')
        actual = (process / 'exe').stat()
        pinned = [(manager / 'root' / path.lstrip('/')).stat() for entry in config['executables']
                  if entry['role'] == 'scanner' for path in entry['paths']]
        guest.require(any((actual.st_dev, actual.st_ino) == (value.st_dev, value.st_ino)
                          for value in pinned), 'kiosk-scanner:unpinned-executable')
        if any(exited(fd) for fd in descriptors):
            return None
        for target, expected_identity, snapshot, executable in (
                (process, identity, threads, actual),
                (parent, parent_identity, parent_threads, parent_exe)):
            guest.require(set((target / 'task').iterdir()) == set(snapshot) and
                all(process_identity(thread) == value for thread, value in snapshot.items()) and
                process_identity(target) == expected_identity,
                'kiosk-scanner:process-lifecycle-changed')
            current = (target / 'exe').stat()
            guest.require((current.st_dev, current.st_ino) == (executable.st_dev, executable.st_ino) and
                all(os.readlink(thread / 'ns/mnt') in namespaces and
                    set(confined_thread_roles(thread, config, backend, generation, host_namespace)) ==
                    set(thread_roles[thread]) for thread in snapshot), 'kiosk-scanner:boundary-changed')
        if any(exited(fd) for fd in descriptors):
            return None
        return {'scanner_observed': True, 'observation': 'observed', 'backend': backend,
                'scanner_thread_roles': counts[0], 'parent_thread_roles': counts[1],
                'pinned_executable': True, 'private_namespace_and_generation': True}
    except (FileNotFoundError, ProcessLookupError):
        # A naturally exited scanner is inconclusive, never positive evidence.
        if descriptors:
            guest.require(any(exited(fd) for fd in descriptors), 'kiosk-scanner:live-process-unreadable')
        return None
    finally:
        for fd in descriptors:
            os.close(fd)


def scanner_manager_pid(unit):
    state = dict(line.split('=', 1) for line in guest.run([
        'systemctl', 'show', '--property=ActiveState,MainPID', unit]).splitlines())
    guest.require(set(state) == {'ActiveState', 'MainPID'} and state['MainPID'].isdigit(),
                  'kiosk-scanner:manager-state')
    # MainPID can name the executor while PAM is still entering confinement.
    # Bind the final manager only once its native startup is complete.
    return int(state['MainPID']) if state['ActiveState'] == 'active' else 0


def observe_scanner(stop_fd, ready, *, timeout=300):
    """Observe real station/editor startup, including its transient scanner.

    Readiness precedes login: the manager need not exist yet. A missing
    manager/scanner remains missing proof, while any observed wrong boundary
    refuses. No cache removal or synthetic scanner launch supplies evidence.
    """
    account = pwd.getpwnam('oh-no-parent-control')
    config = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())
    unit = f'user@{account.pw_uid}.service'
    manager_fd = None
    try:
        host_namespace = os.readlink(PROC / '1/ns/mnt')
        deadline = time.monotonic() + timeout
        ready()
        while time.monotonic() < deadline:
            stop = os.pread(stop_fd, 6, 0)
            guest.require(stop in (b'', b'stop\n'), 'kiosk-scanner:stop-content')
            if stop:
                break
            if manager_fd is None:
                pid = scanner_manager_pid(unit)
                if pid == 0:
                    time.sleep(0.02)
                    continue
                manager = PROC / str(pid)
                manager_fd = os.pidfd_open(pid)
                manager_identity = process_identity(manager)
                generation = (manager / 'root/usr/share/oh-no-parent-control/confinement/generation').read_text()
                guest.require(manager_identity[2] == (str(account.pw_uid),) * 4 and
                              generation.strip() != 'unconfined', 'kiosk-scanner:manager-identity')
                expected = ('onpc-kiosk-manager' if config['backend'] == 'apparmor'
                            else 'onpc_kiosk_manager_t')
                guest.require(confined_thread_roles(manager, config, config['backend'], generation,
                              host_namespace) == [expected], 'kiosk-scanner:manager-role')
            for process in PROC.iterdir():
                if not process.name.isdecimal():
                    continue
                try:
                    executable = os.readlink(process / 'exe')
                except (FileNotFoundError, ProcessLookupError):
                    continue
                if Path(executable.removesuffix(' (deleted)')).name != 'gst-plugin-scanner':
                    continue
                observed = scanner_process(process, account, config, manager, generation, host_namespace)
                if observed is not None:
                    guest.require(not exited(manager_fd) and process_identity(manager) == manager_identity and
                                  manager_pid(unit) == int(manager.name), 'kiosk-scanner:manager-changed')
                    return observed
            time.sleep(0.005)
        if manager_fd is not None:
            guest.require(not exited(manager_fd) and process_identity(manager) == manager_identity and
                          manager_pid(unit) == int(manager.name), 'kiosk-scanner:manager-changed')
        return {'scanner_observed': False, 'observation': 'not-observed', 'backend': config['backend']}
    finally:
        if manager_fd is not None:
            os.close(manager_fd)


def user_command(account, command, *, check=True):
    return guest.commands.run(
        ['/usr/bin/setpriv', '--reuid', str(account.pw_uid), '--regid', str(account.pw_gid),
         '--clear-groups', '/usr/bin/env', '-i', *ENV,
         f'XDG_RUNTIME_DIR=/run/user/{account.pw_uid}',
         f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{account.pw_uid}/bus', *command],
        check=check, timeout=45, merge_stderr=False)


def caller_identity(service):
    guest.require(service in ('gdm-password', 'systemd-user'),
                  'kiosk-confinement:unsupported-pam-caller')
    role = 'xdm' if service == 'gdm-password' else 'init'
    return f'system_u:system_r:{role}_t:s0', role + '_exec_t'


@contextmanager
def pam_caller_command(directory, service, *, expected_selinux='Enforcing'):
    """Run an engineering PAM worker in its real Fedora caller domain."""
    guest.guard(expected_selinux=expected_selinux)
    context, executable_type = caller_identity(service)
    with tempfile.TemporaryDirectory(prefix='pam-caller-', dir=directory) as temporary:
        caller = Path(temporary) / 'caller'
        shutil.copyfile(Path('/usr/bin/python3').resolve(), caller)
        caller.chmod(0o700)
        guest.run(['/usr/bin/chcon', '-t', executable_type, str(caller)])
        yield ['/usr/bin/runcon', context, str(caller), '-B']


def first_exec(account, directory, command, *, fd_mode=None, service='gdm-password', armed=True,
               expected_selinux='Enforcing'):
    """A real PAM final-session call followed by the caller's actual exec.

    Root Python is only the engineering harness: it is already running before
    the tested boundary. No interpreter entry is added to production policy.
    """
    backend = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())['backend']
    module = next(path for path in (
        Path('/usr/lib/x86_64-linux-gnu/security/pam_oh_no_parent_control.so'),
        Path('/usr/lib64/security/pam_oh_no_parent_control.so')) if path.is_file())
    fixture = directory / service
    contents = f'session required {module} kiosk-confinement\n'
    if backend == 'selinux':
        context, _ = caller_identity(service)
        if Path('/proc/self/attr/current').read_text().strip().rstrip('\0') != context:
            # init_t may read the prepared PAM input, but cannot create a
            # user_tmp_t file. Prepare scenario data before entering the real
            # caller domain; never add a production permission for the fixture.
            fixture.write_text(contents)
            # Enter the vendor's real PAM caller domain before opening PAM.
            # In particular, unconfined_t lacks nosuid_transition on the private
            # /usr view. Adding that permission would test a different boundary.
            # The root-private interpreter copy is only a scenario fixture with
            # a vendor entrypoint label; production policy remains unchanged.
            with pam_caller_command(directory, service,
                                    expected_selinux=expected_selinux) as caller:
                # init_t cannot write the harness's user_tmp_t capture files.
                # An inherited pipe carries the bounded result without a
                # production permission or a differently labelled fixture file.
                result_read, result_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
                try:
                    request = json.dumps({'command': command, 'directory': str(directory),
                        'fd_mode': fd_mode, 'service': service, 'armed': armed,
                        'result_fd': result_write, 'expected_selinux': expected_selinux})
                    guest.commands.run([*caller,
                        str(Path(__file__).resolve()), 'first-exec', request], timeout=90,
                        merge_stderr=False, pass_fds=(result_write,))
                    try:
                        last = os.read(result_read, 4097)
                    except BlockingIOError:
                        last = b''
                finally:
                    os.close(result_read)
                    os.close(result_write)
                guest.require(last.startswith(b'onpc-first-exec:'),
                              'kiosk-confinement:caller-result-missing')
                guest.require(len(last) <= 4096, 'kiosk-confinement:caller-result-size')
                result = json.loads(last.removeprefix(b'onpc-first-exec:'))
                guest.require(set(result) == {'status', 'data'} and type(result['status']) is int
                              and isinstance(result['data'], str),
                              'kiosk-confinement:caller-result-invalid')
                return result['status'], bytes.fromhex(result['data'])
        guest.require(fixture.read_text() == contents, 'kiosk-confinement:caller-pam-fixture')
    else:
        fixture.write_text(contents)
    pam = ctypes.CDLL('libpam.so.0')
    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]
    pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
        ctypes.POINTER(Conversation), ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
    pam.pam_open_session.argtypes = [ctypes.c_void_p, ctypes.c_int]
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    try:
        child = os.fork()
    except BaseException:
        os.close(read_fd)
        os.close(write_fd)
        raise
    if child == 0:
        os.close(read_fd)
        try:
            target = command[0]
            descriptor = None
            if fd_mode == 'file':
                descriptor = os.open(target, os.O_RDONLY)
            elif fd_mode == 'memfd':
                descriptor = os.memfd_create('onpc-confinement-probe', os.MFD_CLOEXEC)
                os.write(descriptor, Path(target).read_bytes())
            handle = ctypes.c_void_p()
            conv = Conversation()
            status = pam.pam_start_confdir(service.encode(), account.pw_name.encode(),
                ctypes.byref(conv), os.fsencode(directory), ctypes.byref(handle))
            if status == 0:
                status = pam.pam_open_session(handle, 0)
            if status:
                os.write(write_fd, json.dumps({'pam': status}).encode())
                os._exit(125)
            os.setgroups([])
            os.setgid(account.pw_gid)
            os.setuid(account.pw_uid)
            os.write(write_fd, b'armed\n')
            try:
                os.execve(descriptor if descriptor is not None else target, command,
                          {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            except OSError as error:
                os.write(write_fd, json.dumps({'exec_errno': error.errno}).encode())
                os._exit(126)
        except BaseException:
            os._exit(124)
    os.close(write_fd)
    return wait_first_exec(child, read_fd, armed=armed)


def wait_first_exec(child, read_fd, *, armed):
    """Own the unreaped fork child even if pidfd acquisition fails."""
    pidfd = None
    reaped = False
    try:
        pidfd = os.pidfd_open(child)
        poll = select.poll()
        poll.register(pidfd, select.POLLIN)
        if not poll.poll(75000):
            raise AssertionError('confinement probe timed out')
        _, status = os.waitpid(child, 0)
        reaped = True
        data = os.read(read_fd, 4096)
        guest.require(data.startswith(b'armed\n') == armed, 'kiosk-confinement:unexpected-pam-admission')
        return os.waitstatus_to_exitcode(status), data.removeprefix(b'armed\n')
    finally:
        if not reaped:
            try:
                if pidfd is None:
                    # This direct child is still unreaped, so its PID cannot
                    # be recycled. No process discovery establishes ownership.
                    os.kill(child, signal.SIGKILL)
                else:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(child, 0)
        if pidfd is not None:
            os.close(pidfd)
        os.close(read_fd)


def manager_pid(unit):
    return int(guest.run(['systemctl', 'show', '--value', '--property=MainPID', unit]))


def lifecycle_label(backend):
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    return Path('/proc/self', attribute).read_text().strip().rstrip('\0')


def lifecycle_denials():
    """Fork only owned denial probes from the surviving PAM lifecycle domain."""
    for command in (['/bin/sh', '-c', 'exit 0'], ['/usr/bin/python3', '-c', 'pass']):
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
        try:
            child = os.fork()
        except BaseException:
            os.close(read_fd)
            os.close(write_fd)
            raise
        if child == 0:
            os.close(read_fd)
            try:
                os.execve(command[0], command, {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            except OSError as error:
                os.write(write_fd, json.dumps({'exec_errno': error.errno}).encode())
                os._exit(126)
            os._exit(124)
        os.close(write_fd)
        status, data = wait_first_exec(child, read_fd, armed=False)
        guest.require(status == 126 and json.loads(data).get('exec_errno') in (errno.EACCES, errno.EPERM),
                      'kiosk-lifecycle:exec-not-denied')


def lifecycle_teardown(pam, handle, backend, expected):
    """The real close/delete/end callbacks retain the non-exec child's label."""
    stages = []
    for stage, callback, flags in (
        ('parent-exited', None, 0),
        ('close-session', pam.pam_close_session, 0),
        ('delete-credentials', pam.pam_setcred, 4),
        # systemd marks child pam_end cleanup with PAM_DATA_SILENT.
        ('end', pam.pam_end, 0x40000000),
    ):
        status = None if callback is None else callback(handle, flags)
        # systemd continues teardown even when a provider reports failure.
        # Retain every status and prove the boundary after each callback;
        # the observer separately refuses incomplete teardown acceptance.
        guest.require(lifecycle_label(backend) == expected, 'kiosk-lifecycle:label-' + stage)
        lifecycle_denials()
        stages.append({'stage': stage, 'pam_status': status})
    return stages


def lifecycle_executor(request):
    """Trusted engineering executor; never an admitted production entrypoint.

    Follow systemd's setup_pam ordering using the installed systemd-user stack,
    including its actual vendor teardown callbacks. Only this initial executor
    enters init_t; its non-exec lifecycle child must inherit manager-pam.
    """
    backend = request['backend']
    for name in ('executor_release', 'helper_release', 'events'):
        os.set_inheritable(request[name], False)
    expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_manager_pam_t:s0')
    account = pwd.getpwnam('oh-no-parent-control')
    pam = ctypes.CDLL('libpam.so.0')
    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]
    pam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.POINTER(Conversation), ctypes.POINTER(ctypes.c_void_p)]
    for name in ('pam_acct_mgmt', 'pam_setcred', 'pam_open_session', 'pam_close_session', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    handle = ctypes.c_void_p()
    conversation = Conversation()
    guest.require(pam.pam_start(b'systemd-user', account.pw_name.encode(),
        ctypes.byref(conversation), ctypes.byref(handle)) == 0, 'kiosk-lifecycle:pam-start')
    guest.require(pam.pam_acct_mgmt(handle, 0) == 0, 'kiosk-lifecycle:pam-account')
    # Retain even failed establishment so the observer can prove all subsequent
    # boundaries before refusing qualification. The owned kiosk credential route
    # must succeed rather than consume the global "other" fallback.
    establish_status = pam.pam_setcred(handle, 2)
    guest.require(pam.pam_open_session(handle, 0) == 0, 'kiosk-lifecycle:pam-open')
    guest.require(lifecycle_label(backend) == expected, 'kiosk-lifecycle:executor-label')
    child = os.fork()
    if child == 0:
        os.close(request['executor_release'])
        try:
            os.setgroups([])
            os.setgid(account.pw_gid)
            os.setuid(account.pw_uid)
            parent = os.getppid()
            os.write(request['events'], (json.dumps({'phase': 'ready', 'pid': os.getpid(),
                'parent': parent}) + '\n').encode())
            guest.require(os.read(request['helper_release'], 1) == b'T', 'kiosk-lifecycle:helper-release')
            guest.require(os.getppid() != parent, 'kiosk-lifecycle:parent-still-alive')
            stages = lifecycle_teardown(pam, handle, backend, expected)
            os.write(request['events'], (json.dumps({'phase': 'finished', 'stages': stages,
                'establish_status': establish_status}) + '\n').encode())
            os._exit(0)
        except BaseException:
            os._exit(124)
    os.close(request['helper_release'])
    try:
        guest.require(os.read(request['executor_release'], 1) == b'E', 'kiosk-lifecycle:executor-release')
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
        os.execve('/usr/lib/systemd/systemd', ['/usr/lib/systemd/systemd', '--version'],
                  {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    except BaseException:
        # The direct unreaped child cannot have a recycled PID. EOF on the
        # observer's helper channel also lets it exit if this executor fails.
        os.kill(child, signal.SIGKILL)
        os.waitpid(child, 0)
        raise


def lifecycle_event(fd):
    """Read one bounded atomic event without allowing a lost worker to hang."""
    poll = select.poll()
    poll.register(fd, select.POLLIN | select.POLLHUP)
    deadline = time.monotonic() + 75
    data = bytearray()
    while not data.endswith(b'\n'):
        remaining = max(0, int((deadline - time.monotonic()) * 1000))
        guest.require(remaining > 0 and poll.poll(remaining), 'kiosk-lifecycle:event-timeout')
        part = os.read(fd, 1)
        guest.require(bool(part), 'kiosk-lifecycle:event-missing')
        data.extend(part)
        guest.require(len(data) <= 4096, 'kiosk-lifecycle:event-size')
    return json.loads(data)


def lifecycle_wait(pid, pidfd):
    poll = select.poll()
    poll.register(pidfd, select.POLLIN)
    guest.require(bool(poll.poll(75000)), 'kiosk-lifecycle:worker-timeout')
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


def lifecycle_generation_diagnostic(manager, helper, record):
    """Explain a failed equality check without changing its failure or state."""
    try:
        from system_kiosk_accounts import owned_bytes

        guest.require(all(isinstance(value, str) and
                          re.fullmatch(r'[a-f0-9]{64}\n', value) for value in (manager, helper)),
                      'kiosk-lifecycle:diagnostic-marker')
        record('onpc.kiosk.pam-lifecycle.manager-generation', manager.strip())
        record('onpc.kiosk.pam-lifecycle.helper-generation', helper.strip())
        preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
        trusted = preparation['trusted']
        runtime = trusted(Path('/run/oh-no-parent-control-confinement'), directory=True)
        guest.require(stat.S_IMODE(runtime.stat().st_mode) == 0o700,
                      'kiosk-lifecycle:diagnostic-runtime')
        manifests = []
        for generation in (manager.strip(), helper.strip()):
            manifest = json.loads(owned_bytes(trusted(runtime / generation / 'records.json'),
                                              private=True))
            guest.require(type(manifest) is dict, 'kiosk-lifecycle:diagnostic-manifest')
            manifests.append(manifest)
        differences = {}
        for section in ('records', 'preserved', 'layout'):
            states = []
            for manifest in manifests:
                rows = manifest[section]
                guest.require(type(rows) is list and len(rows) <= 32768,
                              'kiosk-lifecycle:diagnostic-section')
                paths = {}
                for row in rows:
                    path = row.get('path') if type(row) is dict else None
                    guest.require(isinstance(path, str) and path.startswith('/usr/') and
                                  str(Path(path)) == path and '..' not in Path(path).parts and
                                  len(path) <= 4096 and not any(ord(char) < 32 for char in path) and
                                  path not in paths, 'kiosk-lifecycle:diagnostic-path')
                    paths[path] = row
                states.append(paths)
            before, after = states
            added, removed = sorted(after.keys() - before.keys()), sorted(before.keys() - after.keys())
            changed = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
            differences[section] = {
                name: {'count': len(paths), 'paths': paths[:8]}
                for name, paths in (('added', added), ('removed', removed), ('changed', changed))}
        record('onpc.kiosk.pam-lifecycle.generation-diagnostic',
               json.dumps({'status': 'compared', **differences}, sort_keys=True))
    except Exception:
        # Diagnostics and their recorder must never replace the equality
        # failure, including unsafe or unavailable runtime records.
        try:
            record('onpc.kiosk.pam-lifecycle.generation-diagnostic', '{"status":"unavailable"}')
        except Exception:
            pass


def verify_pam_lifecycle(account, unit, backend, directory, record):
    """Hold a real PAM child past executor exit; retain the saved user manager."""
    saved_pid = manager_pid(unit)
    saved_identity = process_identity(PROC / str(saved_pid))
    expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_manager_pam_t:s0')
    caller = directory / 'lifecycle-caller'
    shutil.copyfile(Path('/usr/bin/python3').resolve(), caller)
    caller.chmod(0o700)
    command = [str(caller), '-B', str(Path(__file__).resolve()), 'pam-lifecycle']
    if backend == 'selinux':
        context, executable_type = caller_identity('systemd-user')
        guest.run(['/usr/bin/chcon', '-t', executable_type, str(caller)])
        command = ['/usr/bin/runcon', context, *command]
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    guest.require(libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0, 'kiosk-lifecycle:get-subreaper')
    guest.require(libc.prctl(36, 1, 0, 0, 0) == 0, 'kiosk-lifecycle:set-subreaper')
    descriptors = set()
    workers = {}
    try:
        def pipe():
            pair = os.pipe2(os.O_CLOEXEC)
            descriptors.update(pair)
            return pair
        executor_read, executor_write = pipe()
        helper_read, helper_write = pipe()
        event_read, event_write = pipe()
        executor = os.fork()
        if executor == 0:
            try:
                for fd in (executor_write, helper_write, event_read):
                    os.close(fd)
                for fd in (executor_read, helper_read, event_write):
                    os.set_inheritable(fd, True)
                request = json.dumps({'backend': backend, 'executor_release': executor_read,
                                      'helper_release': helper_read, 'events': event_write})
                os.execve(command[0], [*command, request], dict(os.environ))
            except BaseException:
                os._exit(124)
        workers[executor] = None
        workers[executor] = os.pidfd_open(executor)
        for fd in (executor_read, helper_read, event_write):
            os.close(fd)
            descriptors.remove(fd)
        ready = lifecycle_event(event_read)
        guest.require(set(ready) == {'phase', 'pid', 'parent'} and ready['phase'] == 'ready' and
                      type(ready['pid']) is int and ready['pid'] > 1 and ready['parent'] == executor,
                      'kiosk-lifecycle:spawn-identity')
        helper = ready['pid']
        workers[helper] = None
        workers[helper] = os.pidfd_open(helper)
        identity = process_identity(PROC / str(helper))
        guest.require(identity[1:] == (executor, (str(account.pw_uid),) * 4), 'kiosk-lifecycle:helper-identity')
        attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
        guest.require((PROC / str(helper) / attribute).read_text().strip().rstrip('\0') == expected,
                      'kiosk-lifecycle:waiting-label')
        marker = 'usr/share/oh-no-parent-control/confinement/generation'
        helper_generation = (PROC / str(helper) / 'root' / marker).read_text()
        manager_generation = (PROC / str(saved_pid) / 'root' / marker).read_text()
        if helper_generation != manager_generation:
            lifecycle_generation_diagnostic(manager_generation, helper_generation, record)
        guest.require(helper_generation == manager_generation, 'kiosk-lifecycle:waiting-generation')
        os.write(executor_write, b'E')
        status = lifecycle_wait(executor, workers[executor])
        os.close(workers.pop(executor))
        guest.require(status == 0, 'kiosk-lifecycle:executor-exec')
        after = process_identity(PROC / str(helper))
        guest.require(after[0] == identity[0] and after[1:] == (os.getpid(), identity[2]) and
                      not exited(workers[helper]), 'kiosk-lifecycle:post-parent-identity')
        guest.require((PROC / str(helper) / attribute).read_text().strip().rstrip('\0') == expected,
                      'kiosk-lifecycle:post-parent-label')
        os.write(helper_write, b'T')
        finished = lifecycle_event(event_read)
        guest.require(set(finished) == {'phase', 'stages', 'establish_status'} and
                      finished['phase'] == 'finished' and type(finished['establish_status']) is int and
                      isinstance(finished['stages'], list) and
                      [item.get('stage') for item in finished['stages']] == ['parent-exited',
                      'close-session', 'delete-credentials', 'end'], 'kiosk-lifecycle:teardown-result')
        status = lifecycle_wait(helper, workers[helper])
        os.close(workers.pop(helper))
        guest.require(status == 0, 'kiosk-lifecycle:teardown-exit')
        guest.require(manager_pid(unit) == saved_pid and process_identity(PROC / str(saved_pid)) == saved_identity,
                      'kiosk-lifecycle:saved-manager-changed')
        record('onpc.kiosk.pam-lifecycle.establish-credentials-status', finished['establish_status'])
        for item in finished['stages'][1:]:
            guest.require(set(item) == {'stage', 'pam_status'} and type(item['pam_status']) is int,
                          'kiosk-lifecycle:callback-result')
            record('onpc.kiosk.pam-lifecycle.' + item['stage'] + '-status', item['pam_status'])
        record('onpc.kiosk.pam-lifecycle.post-parent-close-setcred-end-denials', True)
        guest.require(finished['establish_status'] == 0 and
                      all(item['pam_status'] == 0 for item in finished['stages'][1:]),
                      'kiosk-lifecycle:credential-teardown-incomplete')
    finally:
        try:
            for fd in descriptors:
                os.close(fd)
            # Only explicit spawn identities from this root-owned protocol may
            # be signalled. Reap the executor first so its child is adopted here.
            errors = []
            for pid, pidfd in workers.items():
                try:
                    try:
                        if pidfd is None:
                            os.kill(pid, signal.SIGKILL)
                        else:
                            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.waitpid(pid, 0)
                except BaseException as error:
                    errors.append(error)
                finally:
                    if pidfd is not None:
                        os.close(pidfd)
            if errors:
                raise errors[0]
        finally:
            guest.require(libc.prctl(36, previous.value, 0, 0, 0) == 0, 'kiosk-lifecycle:restore-subreaper')


def bwrap_probe_child(request):
    """Root-owned engineering entry into the app boundary, never a product route.

    AppArmor can restrict the already-running harness immediately. SELinux
    enters through an independent root-private interpreter fixture carrying the
    existing Python entrypoint type, as the PAM caller probes do. No production
    interpreter or dynamic-transition permission is added for this fixture.
    """
    backend = request['backend']
    expected = ('onpc-kiosk-app (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_app_t:s0')
    if backend == 'apparmor':
        library = ctypes.CDLL('libapparmor.so.1', use_errno=True)
        library.aa_change_profile.argtypes = [ctypes.c_char_p]
        guest.require(library.aa_change_profile(b'onpc-kiosk-app') == 0,
                      'kiosk-bwrap:app-profile-entry')
    guest.require(lifecycle_label(backend) == expected, 'kiosk-bwrap:app-label')
    os.setgroups([])
    os.setgid(request['gid'])
    os.setuid(request['uid'])
    guest.require(process_identity(PROC / 'self')[2] == (str(request['uid']),) * 4 and
                  os.stat('/proc/self/ns/mnt').st_ino == request['namespace'] and
                  Path('/usr/share/oh-no-parent-control/confinement/generation').read_text() ==
                  request['generation'], 'kiosk-bwrap:app-boundary')
    proof = {name: request[name] for name in ('uid', 'namespace', 'generation')}
    proof['role'] = expected
    os.set_inheritable(request['proof_fd'], False)
    data = json.dumps(proof).encode()
    guest.require(os.write(request['proof_fd'], data) == len(data), 'kiosk-bwrap:proof-write')
    try:
        os.execve('/usr/bin/bwrap', request['arguments'], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    except OSError:
        os._exit(126)


def verify_bwrap_inputs(account, directory, record):
    """User bytes cannot acquire a pinned executable's authority through a bind."""
    config = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())
    backend = config['backend']
    guest.require(backend in ('apparmor', 'selinux'), 'kiosk-bwrap:backend')
    manager = PROC / str(manager_pid(f'user@{account.pw_uid}.service'))
    identity = process_identity(manager)
    marker = 'usr/share/oh-no-parent-control/confinement/generation'
    generation = (manager / 'root' / marker).read_text()
    copied = directory / 'bwrap-canary'
    shutil.copyfile('/usr/bin/xdg-dbus-proxy', copied)
    copied.chmod(0o755)
    os.chown(copied, account.pw_uid, account.pw_gid)
    with ExitStack() as resources:
        def descriptor(path, flags):
            fd = os.open(path, flags | os.O_CLOEXEC)
            resources.callback(os.close, fd)
            return fd
        manager_fd = os.pidfd_open(int(manager.name))
        resources.callback(os.close, manager_fd)
        namespace = descriptor(manager / 'ns/mnt', os.O_RDONLY)
        root = descriptor(manager / 'root', os.O_RDONLY | os.O_DIRECTORY)
        namespace_inode = os.fstat(namespace).st_ino
        guest.require(not exited(manager_fd) and process_identity(manager) == identity and
                      namespace_inode != os.stat('/proc/self/ns/mnt').st_ino,
                      'kiosk-bwrap:manager-boundary')
        temporary = resources.enter_context(tempfile.TemporaryDirectory(
            prefix='bwrap-caller-', dir=guest.PAYLOAD))
        caller = Path(temporary) / 'caller'
        if backend == 'selinux':
            shutil.copyfile(Path('/usr/bin/python3').resolve(), caller)
            caller.chmod(0o700)
            guest.run(['/usr/bin/chcon', '-t', 'onpc_kiosk_python_exec_t', str(caller)])

        def probe(arguments, *, input_fd=None, control=False):
            output_read, output_write = os.pipe2(os.O_CLOEXEC)
            try:
                proof_read, proof_write = os.pipe2(os.O_CLOEXEC)
            except BaseException:
                os.close(output_read)
                os.close(output_write)
                raise
            try:
                child = os.fork()
            except BaseException:
                for fd in (output_read, output_write, proof_read, proof_write):
                    os.close(fd)
                raise
            if child == 0:
                os.close(output_read)
                os.close(proof_read)
                try:
                    os.dup2(output_write, 1)
                    os.close(output_write)
                    os.setns(namespace, os.CLONE_NEWNS)
                    os.fchdir(root)
                    os.chroot('.')
                    os.chdir('/')
                    for fd in (namespace, root, manager_fd):
                        os.close(fd)
                    if control:
                        os.setgroups([])
                        os.setgid(account.pw_gid)
                        os.setuid(account.pw_uid)
                        os.execve(str(copied), arguments, {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
                    request = dict(backend=backend, uid=account.pw_uid, gid=account.pw_gid,
                        namespace=namespace_inode, generation=generation, arguments=arguments,
                        proof_fd=proof_write)
                    if input_fd is not None:
                        os.set_inheritable(input_fd, True)
                    if backend == 'selinux':
                        library = ctypes.CDLL('libselinux.so.1', use_errno=True)
                        library.setexeccon.argtypes = [ctypes.c_char_p]
                        guest.require(library.setexeccon(b'system_u:system_r:onpc_kiosk_app_t:s0') == 0,
                                      'kiosk-bwrap:app-exec-context')
                        os.set_inheritable(proof_write, True)
                        os.execve(str(caller), [str(caller), '-B', str(Path(__file__).resolve()),
                            'bwrap-exec', json.dumps(request)], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
                    bwrap_probe_child(request)
                    os._exit(124)
                except BaseException as error:
                    try:
                        category = str(error) if isinstance(error, guest.GuestError) else type(error).__name__
                        diagnostic = json.dumps({'bwrap_setup': category, 'errno': getattr(error, 'errno', None)})
                        os.write(2, (diagnostic + '\n').encode())
                    finally:
                        os._exit(124)
            os.close(output_write)
            os.close(proof_write)
            try:
                status, output = wait_first_exec(child, output_read, armed=False)
                proof = os.read(proof_read, 4097)
                if not control:
                    expected = dict(uid=account.pw_uid, namespace=namespace_inode, generation=generation,
                        role='onpc-kiosk-app (enforce)' if backend == 'apparmor'
                             else 'system_u:system_r:onpc_kiosk_app_t:s0')
                    guest.require(len(proof) <= 4096 and proof and json.loads(proof) == expected,
                                  'kiosk-bwrap:app-proof-missing')
                return status, output
            finally:
                os.close(proof_read)

        base = ['/usr/bin/bwrap', '--die-with-parent', '--unshare-pid',
                '--ro-bind', '/usr', '/usr', '--ro-bind', '/etc', '/etc',
                '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
                '--ro-bind', str(directory), str(directory)]
        status, output = probe([*base, '--', '/usr/bin/xdg-dbus-proxy', '--version'])
        guest.require(status == 0 and output.startswith(b'xdg-dbus-proxy '),
                      'kiosk-bwrap:native-sandbox-positive')
        token = output
        record('onpc.kiosk.bwrap.native-sandbox-positive', True)
        scanner = next(entry['paths'][0] for entry in config['executables'] if entry['role'] == 'scanner')
        for role, target in (('proxy', '/usr/bin/xdg-dbus-proxy'), ('scanner', scanner)):
            arguments = [target, '--version']
            status, output = probe(arguments, control=True)
            guest.require(status == 0 and output == token, 'kiosk-bwrap:canary-positive')
            for mode in ('bind', 'data', 'tmpfs-file'):
                with copied.open('rb') as stream:
                    fd = stream.fileno()
                    mutation = (['--ro-bind', str(copied), target] if mode == 'bind' else
                        ['--perms', '0755', '--ro-bind-data', str(fd), target] if mode == 'data' else
                        ['--tmpfs', str(Path(target).parent), '--perms', '0755', '--file', str(fd), target])
                    status, output = probe([*base, *mutation, '--', *arguments], input_fd=fd)
                guest.require(status != 0 and token not in output, 'kiosk-bwrap:user-bytes-executed')
                record('onpc.kiosk.bwrap.' + role + '.' + mode + '-denied', status)
        guest.require(not exited(manager_fd) and process_identity(manager) == identity and
                      (manager / 'root' / marker).read_text() == generation,
                      'kiosk-bwrap:manager-changed')


def verify_user_inputs(account, record):
    runtime = Path(f'/run/user/{account.pw_uid}')
    with tempfile.TemporaryDirectory(prefix='onpc-confinement-input-', dir=runtime) as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        os.chown(directory, account.pw_uid, account.pw_gid)
        copied = directory / 'copied-systemctl'
        shutil.copy2('/usr/bin/systemctl', copied)
        os.chown(copied, account.pw_uid, account.pw_gid)
        alias = directory / 'interpreter-alias'
        alias.symlink_to('/usr/bin/python3')
        os.lchown(alias, account.pw_uid, account.pw_gid)
        for index, command in enumerate(([str(copied), '--version'], [str(alias), '-c', 'pass'])):
            user_command(account, ['/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
                '--unit=onpc-confinement-writable-' + str(index), *command], check=False)
            guest.require(guest.commands.last_returncode == 203,
                          'kiosk-confinement:writable-command-not-denied')
        verify_bwrap_inputs(account, directory, record)
    unit_directory = runtime / 'systemd/user'
    created = []
    for path in (unit_directory.parent, unit_directory):
        if not path.exists():
            path.mkdir(mode=0o700)
            os.chown(path, account.pw_uid, account.pw_gid)
            created.append(path)
    unit = unit_directory / 'onpc-confinement-prefix.service'
    with unit.open('x') as stream:
        stream.write('[Service]\nType=oneshot\nExecStart=+/bin/sh -c "exit 0"\n')
    os.chown(unit, account.pw_uid, account.pw_gid)
    identity = (unit.stat().st_dev, unit.stat().st_ino)
    try:
        user_command(account, ['/usr/bin/systemctl', '--user', 'daemon-reload'])
        user_command(account, ['/usr/bin/systemctl', '--user', 'start', unit.name], check=False)
        status = user_command(account, ['/usr/bin/systemctl', '--user', 'show',
                                       '--value', '--property=ExecMainStatus', unit.name])
        guest.require(status.strip() == b'203', 'kiosk-confinement:plus-unit-not-denied')
        record('onpc.kiosk.copied-alias-and-plus-unit-denied', True)
    finally:
        guest.require((unit.stat().st_dev, unit.stat().st_ino) == identity,
                      'kiosk-confinement:unit-identity-changed')
        unit.unlink()
        user_command(account, ['/usr/bin/systemctl', '--user', 'reset-failed', unit.name], check=False)
        user_command(account, ['/usr/bin/systemctl', '--user', 'daemon-reload'])
        for path in reversed(created):
            path.rmdir()


def verify_updates(account, unit, backend, record):
    """Model the unlink/replacement operations performed by distro packages.

    Root scenario mutations are restored byte-for-byte with original labels;
    the user manager must keep its independent executable/library dentries.
    """
    @contextmanager
    def replacement(program):
        original = program.read_bytes()
        with tempfile.TemporaryDirectory(prefix='.onpc-confinement-update-', dir=program.parent) as temporary:
            backup = Path(temporary) / 'original'
            candidate = Path(temporary) / 'replacement'
            shutil.copy2(program, candidate)
            with candidate.open('ab') as stream:
                stream.write(b'\0onpc-owned-package-update-probe\0')
            program.rename(backup)
            try:
                candidate.rename(program)
                yield hashlib.sha256(original).digest()
            finally:
                if program.exists():
                    program.unlink()
                backup.rename(program)

    library_directory = Path('/usr/lib64/systemd' if backend == 'selinux'
                             else '/usr/lib/x86_64-linux-gnu/systemd')
    libraries = sorted(library_directory.glob('libsystemd-*.so'))
    guest.require(bool(libraries), 'kiosk-confinement:systemd-libraries-missing')
    with ExitStack() as mutations:
        expected = {program: mutations.enter_context(replacement(program))
                    for program in [Path('/usr/bin/systemctl'), *libraries]}
        def pinned_bytes():
            root = Path(f'/proc/{manager_pid(unit)}/root')
            for program, digest in expected.items():
                guest.require(hashlib.sha256((root / str(program).lstrip('/')).read_bytes()).digest() == digest,
                              'kiosk-confinement:package-replacement-detached-mount')
                guest.require(hashlib.sha256(program.read_bytes()).digest() != digest,
                              'kiosk-confinement:update-not-applied')
        pinned_bytes()
        # Both supported systemd packages expose the user manager's reexec as
        # a synchronous notify-reload transaction (SIGRTMIN+25 = 59).
        guest.require(guest.run(['systemctl', 'show', '--value', '--property=Type', unit]) == 'notify-reload' and
                      guest.run(['systemctl', 'show', '--value', '--property=ReloadSignal', unit]) == '59',
                      'kiosk-confinement:unsupported-manager-reexec-protocol')
        guest.run(['systemctl', 'reload', unit], timeout=75)
        pinned_bytes()
        guest.require(b'systemd ' in user_command(account, ['/usr/bin/systemd-run', '--user', '--wait',
            '--collect', '--pipe', '--unit=onpc-confinement-after-reexec', '/usr/bin/systemctl', '--version']),
            'kiosk-confinement:service-after-reexec')
        record('onpc.kiosk.executable-library-replacement-and-reexec', True)
    plugin_directory = Path('/usr/lib64/gstreamer-1.0' if backend == 'selinux'
                            else '/usr/lib/x86_64-linux-gnu/gstreamer-1.0')
    before = plugin_directory / 'libgstpython.so'
    existed = before.exists()
    previous = before.read_bytes() if existed else None
    with tempfile.TemporaryDirectory(prefix='.onpc-confinement-plugin-', dir=plugin_directory.parent) as temporary:
        backup = Path(temporary) / 'original'
        plugin_directory.rename(backup)
        plugin_directory.mkdir(mode=0o755)
        try:
            (plugin_directory / 'libgstpython.so').write_bytes(b'owned-update-probe')
            in_manager = Path(f'/proc/{manager_pid(unit)}/root') / str(before).lstrip('/')
            guest.require(in_manager.exists() == existed and
                          (not existed or in_manager.read_bytes() == previous),
                          'kiosk-confinement:plugin-parent-replacement-exposed-library')
            record('onpc.kiosk.plugin-parent-replacement', True)
        finally:
            (plugin_directory / 'libgstpython.so').unlink()
            plugin_directory.rmdir()
            backup.rename(plugin_directory)


@contextmanager
def appended_probe(path, suffix):
    """Restore the opened fixture inode, including package-verified timestamps."""
    with os.fdopen(os.open(path, os.O_RDWR | os.O_NOFOLLOW), 'r+b') as stream:
        before = os.fstat(stream.fileno())
        original = stream.read()
        try:
            stream.write(suffix)
            stream.flush()
            yield
        finally:
            stream.seek(0)
            stream.write(original)
            stream.truncate()
            stream.flush()
            os.utime(stream.fileno(), ns=(before.st_atime_ns, before.st_mtime_ns))


def verify_admission_faults(account, directory, backend, record):
    command = ['/usr/lib/systemd/systemd', '--version']
    status, data = first_exec(account, directory, command, service='systemd-user')
    guest.require(status == 0 and not data, 'kiosk-confinement:manager-first-exec-positive')
    for name in ('/etc/pam.d/gdm-password', '/usr/lib/pam.d/systemd-user'):
        with appended_probe(Path(name), b'\n# owned integration-drift probe\n'):
            status, data = first_exec(account, directory, command, service='systemd-user', armed=False)
            guest.require(status == 125 and json.loads(data)['pam'] != 0,
                          'kiosk-confinement:drift-admitted')
    record('onpc.kiosk.pam-vendor-drift-denied', True)
    policy = Path('/usr/share/oh-no-parent-control/confinement') / (
        'onpc-kiosk.apparmor' if backend == 'apparmor' else 'onpc-kiosk.cil')
    with appended_probe(policy, b'\n'):
        status, data = first_exec(account, directory, command, service='systemd-user', armed=False)
        guest.require(status == 125 and json.loads(data)['pam'] != 0,
                      'kiosk-confinement:unloaded-policy-generation-admitted')
    record('onpc.kiosk.unloaded-policy-generation-denied', True)
    if backend == 'apparmor':
        restore = ['/usr/sbin/apparmor_parser', '-r', str(policy)]
        mutations = [(['/usr/sbin/apparmor_parser', '-C', '-r', str(policy)], restore),
                     (['/usr/sbin/apparmor_parser', '-R', str(policy)], restore)]
    else:
        mutations = [(['/usr/sbin/setenforce', '0'], ['/usr/sbin/setenforce', '1']),
            (['/usr/sbin/semanage', 'permissive', '-a', 'onpc_kiosk_app_t'],
             ['/usr/sbin/semanage', 'permissive', '-d', 'onpc_kiosk_app_t']),
            (['/usr/sbin/semodule', '-r', 'onpc-kiosk'],
             ['/usr/sbin/semodule', '-i', str(policy)])]
    for index, (mutation, restore) in enumerate(mutations):
        try:
            guest.run(mutation, timeout=60)
            expected = 'Permissive' if mutation == ['/usr/sbin/setenforce', '0'] else 'Enforcing'
            status, data = first_exec(account, directory, command, service='systemd-user',
                                      armed=False, expected_selinux=expected)
            guest.require(status == 125 and json.loads(data)['pam'] != 0,
                          'kiosk-confinement:unenforced-policy-admitted')
        finally:
            guest.run(restore, timeout=60)
        status, data = first_exec(account, directory, command, service='systemd-user')
        guest.require(status == 0 and not data, 'kiosk-confinement:policy-recovery')
        record('onpc.kiosk.unenforced-policy-denied.' + str(index), True)


def verify_namespace_guard(record):
    """Exercise real namespace open/init/close callbacks, outside UI acceptance."""
    from system_kiosk_scope import ordinary_accounts
    guest.guard()
    guest.enable_diagnostics()
    accounts = {'ordinary': pwd.getpwnam('root'), **ordinary_accounts(),
                'kiosk': pwd.getpwnam('oh-no-parent-control')}
    installed = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement-integration')
    namespace_directory = Path('/etc/security/namespace.d')
    guest.require(namespace_directory.is_dir(), 'kiosk-namespace:configuration-directory-missing')
    parent_namespace = os.readlink('/proc/self/ns/mnt')
    with tempfile.TemporaryDirectory(prefix='kiosk-namespace-', dir=guest.PAYLOAD) as temporary:
        directory = Path(temporary)
        poly = directory / 'poly'
        poly.mkdir(mode=0o700)
        original_poly = poly.stat()
        instances = directory / 'instances'
        instances.mkdir(mode=0)
        initialized = directory / 'initialized'
        script = directory / 'init'
        script.write_text('#!/bin/sh\nset -eu\nprintf namespace-init > ' + shlex.quote(str(initialized)) + '\n')
        script.chmod(0o700)
        service = directory / 'onpc-namespace-probe'
        # This synthetic service never changes its SELinux exec context.
        # pam_namespace documents use_current_context for exactly that case;
        # no production policy or caller transition is needed for the fixture.
        service.write_text('auth required pam_permit.so\n' + installed['guarded_sessions'](
            'session required pam_namespace.so unmount_on_close use_current_context\n') +
            'session required pam_permit.so\n')
        configuration = namespace_directory / (directory.name + '.conf')
        contents = (f'{poly} {instances}/ tmpdir:iscript={script} ~' +
                    ','.join(account.pw_name for account in accounts.values()) + '\n')
        with configuration.open('x') as stream:
            stream.write(contents)
        configuration.chmod(0o600)
        identity = configuration.stat()
        try:
            for role, account in accounts.items():
                kiosk = role == 'kiosk'
                read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
                try:
                    child = os.fork()
                except BaseException:
                    os.close(read_fd)
                    os.close(write_fd)
                    raise
                if child == 0:
                    os.close(read_fd)
                    stage = 'start'
                    pam_status = None
                    try:
                        pam = ctypes.CDLL('libpam.so.0')
                        class Conversation(ctypes.Structure):
                            _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]
                        pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                            ctypes.POINTER(Conversation), ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
                        for callback in ('pam_open_session', 'pam_close_session', 'pam_setcred', 'pam_end'):
                            getattr(pam, callback).argtypes = [ctypes.c_void_p, ctypes.c_int]
                        handle = ctypes.c_void_p()
                        conversation = Conversation()
                        user = account.pw_name.encode()
                        guest.require(pam.pam_start_confdir(service.name.encode(), user,
                            ctypes.byref(conversation), os.fsencode(directory), ctypes.byref(handle)) == 0,
                            'kiosk-namespace:pam-start')
                        stage = 'establish-credentials'
                        guest.require(pam.pam_setcred(handle, 2) == 0, 'kiosk-namespace:pam-setcred')
                        stage = 'open'
                        pam_status = pam.pam_open_session(handle, 0)
                        guest.require(pam_status == 0, 'kiosk-namespace:pam-open')
                        stage = 'namespace'
                        guest.require((os.readlink('/proc/self/ns/mnt') != parent_namespace) == (not kiosk),
                                      'kiosk-namespace:open-namespace')
                        stage = 'init'
                        guest.require(initialized.exists() == (not kiosk), 'kiosk-namespace:init-callback')
                        stage = 'instance'
                        guest.require(bool(list(instances.iterdir())) == (not kiosk),
                                      'kiosk-namespace:instance-created')
                        stage = 'close'
                        guest.require(pam.pam_close_session(handle, 0) == 0, 'kiosk-namespace:pam-close')
                        guest.require(not list(instances.iterdir()), 'kiosk-namespace:instance-not-cleaned')
                        current_poly = poly.stat()
                        guest.require((current_poly.st_dev, current_poly.st_ino) ==
                            (original_poly.st_dev, original_poly.st_ino), 'kiosk-namespace:close-mount')
                        stage = 'delete-credentials'
                        guest.require(pam.pam_setcred(handle, 4) == 0, 'kiosk-namespace:pam-delete-credentials')
                        guest.require(pam.pam_end(handle, 0) == 0, 'kiosk-namespace:pam-end')
                        os._exit(0)
                    except BaseException as error:
                        category = str(error) if isinstance(error, guest.GuestError) else 'internal'
                        os.write(write_fd, json.dumps({'stage': stage, 'category': category,
                            'pam_status': pam_status}).encode())
                        os._exit(1)
                os.close(write_fd)
                status, data = wait_first_exec(child, read_fd, armed=False)
                if data:
                    diagnostic = json.loads(data)
                    for key in ('stage', 'category', 'pam_status'):
                        record('onpc.kiosk.namespace.' + role + '.failed-' + key, diagnostic[key])
                if status != 0:
                    guest.commands.run(['journalctl', '-b', '--no-pager', '-n', '100',
                        '--grep=pam_namespace|onpc-namespace|avc:'], timeout=15,
                        check=False, merge_stderr=False)
                guest.require(status == 0, 'kiosk-namespace:callbacks:' + role)
                guest.require(os.readlink('/proc/self/ns/mnt') == parent_namespace and
                              not list(instances.iterdir()), 'kiosk-namespace:parent-isolation')
                record('onpc.kiosk.namespace.' + role + '.open-init-close-setcred', True)
                if initialized.exists():
                    initialized.unlink()
        finally:
            current = configuration.stat()
            guest.require((current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino)
                          and configuration.read_text() == contents,
                          'kiosk-namespace:configuration-replaced')
            configuration.unlink()


def verify(record):
    guest.guard()
    guest.enable_diagnostics()
    account = pwd.getpwnam('oh-no-parent-control')
    unit = f'user@{account.pw_uid}.service'
    guest.require(account.pw_shell == '/usr/sbin/nologin' and guest.run([
        'busctl', '--system', 'get-property', 'org.freedesktop.Accounts',
        f'/org/freedesktop/Accounts/User{account.pw_uid}', 'org.freedesktop.Accounts.User',
        'SystemAccount']) == 'b false', 'kiosk-confinement:greeter-classification')
    record('onpc.kiosk.nologin-account-visible-after-reboot', True)
    wait_kiosk_inactive(account)
    guest.run(['systemctl', 'start', unit], timeout=75)
    invocation = guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit])
    try:
        pid = manager_pid(unit)
        backend = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())['backend']
        attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
        label = (Path('/proc') / str(pid) / attribute).read_text().strip().rstrip('\0')
        expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor'
                    else 'system_u:system_r:onpc_kiosk_manager_t:s0')
        guest.require(label == expected, 'kiosk-confinement:manager-label')
        record('onpc.kiosk.boundary.backend', backend)
        # First prove that the manager can successfully run a required native
        # service, so an unavailable bus/manager cannot count as denial.
        positive = ['/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
                    '--unit=onpc-confinement-positive', '/usr/bin/systemctl', '--version']
        guest.require(b'systemd ' in user_command(account, positive), 'kiosk-confinement:positive-service')
        integration = '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration'
        refusal = guest.commands.run([integration, 'check-remove'], check=False,
                                     timeout=30, merge_stderr=True)
        guest.require(guest.commands.last_returncode != 0 and any(reason in refusal for reason in
                      (b'kiosk-processes-active', b'kiosk-admissions-active')),
                      'kiosk-confinement:active-removal-not-refused')
        record('onpc.kiosk.active-removal-refused', True)
        if backend == 'apparmor':
            for service, properties in (
                ('oh-no-parent-control-wellbeing.service', {'NoNewPrivileges': 'no'}),
                ('wireplumber.service', {'NoNewPrivileges': 'no', 'LockPersonality': 'no',
                                         'MemoryDenyWriteExecute': 'no', 'SystemCallFilter': '~',
                                         'SystemCallArchitectures': ''}),
                ('pipewire.service', {'NoNewPrivileges': 'yes', 'LockPersonality': 'yes',
                                      'MemoryDenyWriteExecute': 'yes', 'DropInPaths': ''}),
            ):
                for property_name, value in properties.items():
                    observed = user_command(account, ['/usr/bin/systemctl', '--user', 'show',
                        '--value', '--property=' + property_name, service]).decode().strip()
                    guest.require(observed == value,
                                  'kiosk-confinement:effective-unit-setting:' + property_name)
            record('onpc.kiosk.effective-unit-overrides', True)
        denied = (
            ['/bin/sh', '-c', 'exit 0'],
            ['/usr/bin/python3', '-c', 'pass'],
            ['/usr/bin/gjs', '-c', 'void 0'],
            ['/usr/bin/gnome-shell', '--version'],
            ['/usr/bin/gnome-session', '--version'],
            ['/usr/bin/wireplumber', '--version'],
        )
        for index, command in enumerate(denied):
            name = f'onpc-confinement-deny-{index}'
            user_command(account, ['/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
                                  '--unit=' + name, *command], check=False)
            guest.require(guest.commands.last_returncode == 203, 'kiosk-confinement:manager-exec-not-denied')
            record('onpc.kiosk.manager-denied.' + str(index), True)
        verify_user_inputs(account, record)
        verify_updates(account, unit, backend, record)
        # GDM's saved-session metadata is deliberately irrelevant here: test
        # the executable selected after final PAM admission, including FDs.
        with tempfile.TemporaryDirectory(prefix='kiosk-confinement-', dir=guest.PAYLOAD) as temporary:
            directory = Path(temporary)
            verify_pam_lifecycle(account, unit, backend, directory, record)
            config = Path('/usr/share/oh-no-parent-control/confinement/config.json')
            with appended_probe(config, b'\n'):
                status, data = first_exec(account, directory,
                    ['/usr/libexec/gdm-wayland-session', '--help'], armed=False)
                guest.require(status == 125 and json.loads(data)['pam'] != 0,
                              'kiosk-confinement:stale-manager-admitted')
            guest.require(manager_pid(unit) == pid, 'kiosk-confinement:stale-manager-restarted')
            record('onpc.kiosk.stale-manager-denied-without-restart', True)
            status, data = first_exec(account, directory, ['/usr/libexec/gdm-wayland-session', '--help'])
            record('onpc.kiosk.positive-final-exec.status', status)
            if data:
                detail = json.loads(data)
                for key in ('pam', 'exec_errno'):
                    if type(detail.get(key)) is int:
                        record('onpc.kiosk.positive-final-exec.' + key, detail[key])
            guest.require(status == 0 and data == b'', 'kiosk-confinement:positive-final-exec')
            loader = '/usr/lib64/ld-linux-x86-64.so.2' if backend == 'selinux' else '/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'
            cases = [(command, None) for command in denied]
            cases += [([loader, '/usr/bin/true'], None),
                      (['/usr/bin/true'], 'file'), (['/usr/bin/true'], 'memfd')]
            for index, (command, fd_mode) in enumerate(cases):
                status, data = first_exec(account, directory, command, fd_mode=fd_mode)
                guest.require(status == 126 and json.loads(data)['exec_errno'] in (errno.EACCES, errno.EPERM),
                              'kiosk-confinement:final-exec-not-denied')
                record('onpc.kiosk.final-exec-denied.' + str(index), True)
    finally:
        # Stop only the instance started here, never a replacement invocation.
        guest.require(guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit]) == invocation,
                      'kiosk-confinement:manager-identity-changed')
        guest.run(['systemctl', 'stop', unit], timeout=75)
    guest.run([integration, 'check-remove'], timeout=30)
    record('onpc.kiosk.inactive-removal-admitted', True)
    # Removing AppArmor policy detaches profiles from live processes. Faults
    # therefore run only after the explicitly owned manager has stopped.
    with tempfile.TemporaryDirectory(prefix='kiosk-admission-', dir=guest.PAYLOAD) as temporary:
        verify_admission_faults(account, Path(temporary), backend, record)


if __name__ == '__main__':
    if sys.argv[1:] == ['census']:
        print(json.dumps(census(), sort_keys=True))
    elif len(sys.argv) == 3 and sys.argv[1] == 'bwrap-exec':
        request = json.loads(sys.argv[2])
        guest.require(set(request) == {'backend', 'uid', 'gid', 'namespace', 'generation',
            'arguments', 'proof_fd'} and request['backend'] == 'selinux' and
            all(type(request[name]) is int and request[name] > 2 for name in
                ('uid', 'gid', 'namespace', 'proof_fd')) and
            re.fullmatch(r'[a-f0-9]{64}\n', request['generation']) is not None and
            isinstance(request['arguments'], list) and request['arguments'] and
            request['arguments'][0] == '/usr/bin/bwrap' and
            all(isinstance(value, str) for value in request['arguments']),
            'kiosk-bwrap:caller-request')
        bwrap_probe_child(request)
    elif len(sys.argv) == 3 and sys.argv[1] == 'pam-lifecycle':
        request = json.loads(sys.argv[2])
        guest.require(set(request) == {'backend', 'executor_release', 'helper_release', 'events'} and
                      request['backend'] in ('apparmor', 'selinux') and
                      all(type(request[name]) is int and request[name] > 2 for name in
                          ('executor_release', 'helper_release', 'events')),
                      'kiosk-lifecycle:arguments')
        guest.guard()
        if request['backend'] == 'selinux':
            guest.require(lifecycle_label('selinux') == caller_identity('systemd-user')[0],
                          'kiosk-lifecycle:caller-context')
        lifecycle_executor(request)
    else:
        guest.require(len(sys.argv) == 3 and sys.argv[1] == 'first-exec',
                      'kiosk-confinement:arguments')
        request = json.loads(sys.argv[2])
        guest.require(set(request) == {'command', 'directory', 'fd_mode', 'service', 'armed',
                                      'result_fd', 'expected_selinux'},
                      'kiosk-confinement:caller-request')
        guest.guard(expected_selinux=request.pop('expected_selinux'))
        result_fd = request.pop('result_fd')
        guest.require(type(result_fd) is int and result_fd > 2,
                      'kiosk-confinement:caller-result-descriptor')
        # The fork child must not retain this reporting channel after exec.
        os.set_inheritable(result_fd, False)
        context, _ = caller_identity(request['service'])
        guest.require(Path('/proc/self/attr/current').read_text().strip().rstrip('\0') == context,
                      'kiosk-confinement:caller-context')
        status, data = first_exec(pwd.getpwnam('oh-no-parent-control'),
            Path(request.pop('directory')), request.pop('command'), **request)
        result = ('onpc-first-exec:' + json.dumps({'status': status, 'data': data.hex()})).encode()
        guest.require(len(result) <= 4096, 'kiosk-confinement:caller-result-size')
        guest.require(os.write(result_fd, result) == len(result),
                      'kiosk-confinement:caller-result-write')
        os.close(result_fd)
