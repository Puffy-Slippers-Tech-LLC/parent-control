"""Installed account/routing admission, separate from final-exec and UI proof."""

import ctypes
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import pwd
import select
import signal
import stat
import subprocess
import sys

import system_guest as guest


SERVICES = ('gdm-password', 'login', 'sshd')
USERS = {'ordinary': 'onpc-parent-jamie', 'kiosk': 'oh-no-parent-control'}
INTERFACE = 'org.freedesktop.Accounts.User'
DEDICATED = ('oh-no-parent-control', 'wayland')
PAM_PERM_DENIED = 6


def pam_account(service, role, *, hold=None):
    """Use libpam's installed configuration, with no authentication or session.

    The caller bounds this worker. No password, replacement PAM configuration,
    shell change or executable fixture can cause an inconclusive login failure
    to masquerade as the installed account gate's permission denial.
    """
    guest.guard()
    guest.require(service in SERVICES and role in USERS, 'kiosk-admission:arguments')
    if service == 'gdm-password' and role == 'kiosk' and guest.package_path().suffix == '.rpm':
        from system_kiosk_confinement import caller_identity
        guest.require(Path('/proc/self/attr/current').read_text().strip().rstrip('\0') ==
                      caller_identity(service)[0], 'kiosk-admission:caller-context')
    # pam_start otherwise falls back to "other" for a missing service.
    configurations = [Path(root) / service for root in ('/etc/pam.d', '/usr/lib/pam.d')]
    path = next((path for path in configurations if path.exists()), None)
    guest.require(path is not None, 'kiosk-admission:missing-service')
    info = path.lstat()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                  not info.st_mode & 0o022, 'kiosk-admission:unsafe-service')
    account = pwd.getpwnam(USERS[role])
    guest.require(account.pw_uid > 0, 'kiosk-admission:identity')
    pam = ctypes.CDLL('libpam.so.0')

    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('appdata_ptr', ctypes.c_void_p)]

    pam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.POINTER(Conversation), ctypes.POINTER(ctypes.c_void_p)]
    for name in ('pam_acct_mgmt', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    handle, conversation = ctypes.c_void_p(), Conversation()
    guest.require(pam.pam_start(service.encode(), account.pw_name.encode(),
                               ctypes.byref(conversation), ctypes.byref(handle)) == 0,
                  'kiosk-admission:pam-start')
    status = 4  # PAM_SYSTEM_ERR if the account call fails before returning.
    try:
        status = pam.pam_acct_mgmt(handle, 0)
        if hold is not None:
            hold(status)
    finally:
        ended = pam.pam_end(handle, status)
    return {'account': status, 'end': ended}


def root_uids(pid):
    """Check real, effective, saved and filesystem IDs independently of PAM."""
    rows = (Path('/proc') / str(pid) / 'status').read_text().splitlines()
    values = next((line.split()[1:] for line in rows if line.startswith('Uid:')), [])
    guest.require(values == ['0'] * 4, 'kiosk-admission:held-root-credentials')
    return [int(value) for value in values]


def held_worker():
    """Keep the actual installed PAM handle until controller EOF, at most 240s."""
    guest.guard()
    root_uids(os.getpid())

    def hold(status):
        guest.require(status == 0, 'kiosk-admission:held-account-status')
        ready = {'pid': os.getpid(), 'uids': root_uids(os.getpid()), 'account': status}
        print(json.dumps(ready, sort_keys=True), flush=True)
        poll = select.poll()
        poll.register(0, select.POLLIN | select.POLLHUP)
        guest.require(bool(poll.poll(240000)), 'kiosk-admission:held-expired')
        guest.require(os.read(0, 1) == b'', 'kiosk-admission:held-release-protocol')
        root_uids(os.getpid())

    result = pam_account('gdm-password', 'kiosk', hold=hold)
    print(json.dumps(result, sort_keys=True), flush=True)
    guest.require(result == {'account': 0, 'end': 0}, 'kiosk-admission:held-end-status')


@contextmanager
def held_account(record):
    """Yield only a live, root, directly owned worker holding a real PAM handle.

    Normal release is controller EOF followed by pam_end and a normal exit.
    Exceptional cleanup signals only the pidfd of this directly spawned child
    (or its still-unreaped child PID if acquiring that pidfd itself failed).
    """
    from system_kiosk_confinement import exited, lifecycle_event, lifecycle_wait, pam_caller_command

    guest.guard()
    with ExitStack() as resources:
        caller = ['/usr/bin/python3', '-B']
        if guest.package_path().suffix == '.rpm':
            caller = resources.enter_context(pam_caller_command(guest.PAYLOAD, 'gdm-password'))
        child = subprocess.Popen(
            [*caller, str(Path(__file__).resolve()), 'held-account'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)
        pidfd = None
        try:
            pidfd = os.pidfd_open(child.pid)
            ready = lifecycle_event(child.stdout.fileno())
            guest.require(type(ready) is dict and ready == {
                'pid': child.pid, 'uids': [0, 0, 0, 0], 'account': 0},
                'kiosk-admission:held-ready')
            root_uids(child.pid)
            guest.require(not exited(pidfd), 'kiosk-admission:held-premature-exit')
            record('onpc.kiosk.admission.held-ready', json.dumps(ready, sort_keys=True))
            yield child.pid
            guest.require(not exited(pidfd), 'kiosk-admission:held-premature-exit')
            root_uids(child.pid)
            child.stdin.close()
            finished = lifecycle_event(child.stdout.fileno())
            record('onpc.kiosk.admission.held-ended', json.dumps(finished, sort_keys=True))
            guest.require(type(finished) is dict and finished == {'account': 0, 'end': 0},
                          'kiosk-admission:held-end-status')
            child.returncode = lifecycle_wait(child.pid, pidfd)
            guest.require(child.returncode == 0, 'kiosk-admission:held-exit-status')
        finally:
            failure = sys.exc_info()[1]
            cleanup_errors = []
            try:
                child.stdin.close()
            except BaseException as error:
                cleanup_errors.append(error)
            try:
                if child.poll() is None:
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        if pidfd is None:
                            child.kill()  # Direct unreaped child; no reusable PID lookup.
                        else:
                            try:
                                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                        child.wait(timeout=10)
            except BaseException as error:
                cleanup_errors.append(error)
            try:
                child.stdout.close()
            except BaseException as error:
                cleanup_errors.append(error)
            if pidfd is not None:
                try:
                    os.close(pidfd)
                except BaseException as error:
                    cleanup_errors.append(error)
            if cleanup_errors:
                if failure is None:
                    raise cleanup_errors[0]
                failure.add_note('kiosk-admission:held-cleanup-failed')


def probe(service, role, expected, stage, record):
    with ExitStack() as resources:
        caller = ['/usr/bin/python3', '-B']
        if service == 'gdm-password' and role == 'kiosk' and guest.package_path().suffix == '.rpm':
            from system_kiosk_confinement import pam_caller_command
            # The native GDM callback creates its leased runtime inode in
            # xdm_t. An unconfined engineering caller would create the wrong
            # SELinux object type before a later real session could use it.
            caller = resources.enter_context(pam_caller_command(guest.PAYLOAD, service))
        raw = guest.commands.run([
            *caller, str(Path(__file__).resolve()), 'pam-account', service, role],
            timeout=45, merge_stderr=False)
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise guest.GuestError('kiosk-admission:worker-result') from None
    guest.require(type(result) is dict and set(result) == {'account', 'end'} and
                  all(type(value) is int for value in result.values()),
                  'kiosk-admission:worker-result')
    # Retain the actual native statuses even when the assertion fails.
    record('onpc.kiosk.admission.' + stage, json.dumps(result, sort_keys=True))
    guest.require(result == {'account': expected, 'end': 0},
                  'kiosk-admission:unexpected-status:' + stage)


def routing(uid):
    from system_assertions import account_property
    return tuple(account_property(uid, INTERFACE, prop) for prop in ('Session', 'SessionType'))


def set_routing(uid, values):
    for method, value in zip(('SetSession', 'SetSessionType'), values):
        guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                   f'/org/freedesktop/Accounts/User{uid}', INTERFACE, method, 's', value])
    guest.require(routing(uid) == values, 'kiosk-admission:routing-write')


def verify_gates(record):
    """Observe installed account gates without changing retained routing state."""
    guest.guard()
    guest.enable_diagnostics()
    kiosk, ordinary = (pwd.getpwnam(USERS[role]) for role in ('kiosk', 'ordinary'))
    guest.require(kiosk.pw_uid != ordinary.pw_uid and kiosk.pw_shell == '/usr/sbin/nologin',
                  'kiosk-admission:identities')
    for service in SERVICES:
        probe(service, 'ordinary', 0, service + '.ordinary-before', record)
    probe('gdm-password', 'kiosk', 0, 'dedicated-before', record)
    for service in ('login', 'sshd'):
        probe(service, 'kiosk', PAM_PERM_DENIED, service + '.denied', record)
        probe(service, 'ordinary', 0, service + '.ordinary-after', record)


def verify(record):
    guest.guard()
    guest.enable_diagnostics()
    kiosk, ordinary = (pwd.getpwnam(USERS[role]) for role in ('kiosk', 'ordinary'))
    guest.require(kiosk.pw_uid != ordinary.pw_uid and kiosk.pw_shell == '/usr/sbin/nologin',
                  'kiosk-admission:identities')
    original = routing(kiosk.pw_uid)
    ordinary_routing = routing(ordinary.pw_uid)
    guest.require(original == DEDICATED, 'kiosk-admission:initial-routing')
    # Establish that the installed daemon actually uses the tested PAM service,
    # including effective per-user Match configuration, without starting SSH.
    ssh = guest.run(['/usr/sbin/sshd', '-T', '-C',
                     'user=' + kiosk.pw_name + ',host=localhost,addr=127.0.0.1'])
    settings = dict(line.split(' ', 1) for line in ssh.splitlines() if ' ' in line)
    guest.require(settings.get('usepam') == 'yes' and
                  settings.get('pamservicename', 'sshd') == 'sshd',
                  'kiosk-admission:ssh-pam-routing')
    record('onpc.kiosk.admission.ssh-installed-pam', True)
    alternate = 'gnome' if guest.package_path().suffix == '.rpm' else 'ubuntu'
    guest.require((Path('/usr/share/wayland-sessions') / (alternate + '.desktop')).is_file(),
                  'kiosk-admission:alternate-session-missing')
    try:
        for service in SERVICES:
            probe(service, 'ordinary', 0, service + '.ordinary-before', record)
        probe('gdm-password', 'kiosk', 0, 'dedicated-before', record)
        # A real alternate Wayland session and invalid saved transport must
        # both refuse this attempt, repair the default, and permit a fresh one.
        for stage, values in (('alternate-session', (alternate, 'wayland')),
                              ('alternate-transport', (DEDICATED[0], 'x11'))):
            set_routing(kiosk.pw_uid, values)
            probe('gdm-password', 'kiosk', PAM_PERM_DENIED, stage + '.denied', record)
            guest.require(routing(kiosk.pw_uid) == DEDICATED,
                          'kiosk-admission:routing-not-repaired:' + stage)
            record('onpc.kiosk.admission.' + stage + '.repaired', True)
            probe('gdm-password', 'kiosk', 0, stage + '.retry', record)
        for service in ('login', 'sshd'):
            probe(service, 'kiosk', PAM_PERM_DENIED, service + '.denied', record)
            probe(service, 'ordinary', 0, service + '.ordinary-after', record)
        probe('gdm-password', 'kiosk', 0, 'dedicated-after', record)
        guest.require(routing(kiosk.pw_uid) == DEDICATED and
                      routing(ordinary.pw_uid) == ordinary_routing,
                      'kiosk-admission:routing-changed')
    finally:
        # Public setters restore only this attempt's deliberate kiosk mutation.
        if routing(kiosk.pw_uid) != original:
            set_routing(kiosk.pw_uid, original)


if __name__ == '__main__':
    if sys.argv[1:] == ['held-account']:
        held_worker()
    else:
        guest.require(len(sys.argv) == 4 and sys.argv[1] == 'pam-account',
                      'kiosk-admission:arguments')
        print(json.dumps(pam_account(sys.argv[2], sys.argv[3]), sort_keys=True))
