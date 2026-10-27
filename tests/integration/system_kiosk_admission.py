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


SERVICES = ('gdm-password', 'login', 'sshd', 'su-l')
USERS = {'ordinary': 'onpc-parent-jamie', 'other': 'onpc-child-jordan',
         'kiosk': 'oh-no-parent-control'}
INTERFACE = 'org.freedesktop.Accounts.User'
DEDICATED = ('oh-no-parent-control', 'wayland')
PAM_PERM_DENIED = 6
PAM_AUTH_ERR = 7
DURABLE_SERVICES = ('gdm-password', 'systemd-user')


def empty_token_conversation(user, *, token=b''):
    """A real libpam conversation; station probes retain the empty default.

    PAM takes ownership of calloc/strdup responses on success. Keep the callback
    alive until pam_end; reject unknown styles and bound the provider's batch.
    Ordinary-account collateral probes may supply their existing fixture token.
    """
    class Message(ctypes.Structure):
        _fields_ = [('style', ctypes.c_int), ('message', ctypes.c_char_p)]

    class Response(ctypes.Structure):
        _fields_ = [('response', ctypes.c_void_p), ('code', ctypes.c_int)]

    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.POINTER(Message)), ctypes.POINTER(ctypes.POINTER(Response)),
        ctypes.c_void_p)
    libc = ctypes.CDLL('libc.so.6')
    libc.calloc.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
    libc.calloc.restype = ctypes.c_void_p
    libc.strdup.argtypes = [ctypes.c_char_p]
    libc.strdup.restype = ctypes.c_void_p
    libc.free.argtypes = [ctypes.c_void_p]

    @callback_type
    def reply(count, messages, output, _data):
        if count < 1 or count > 16 or not messages or not output:
            return 19  # PAM_CONV_ERR
        styles = [messages[index].contents.style for index in range(count)]
        if any(style not in (1, 2, 3, 4) for style in styles):
            return 19
        allocation = libc.calloc(count, ctypes.sizeof(Response))
        if not allocation:
            return 5  # PAM_BUF_ERR
        responses = ctypes.cast(allocation, ctypes.POINTER(Response))
        for index, style in enumerate(styles):
            if style in (1, 2):
                value = libc.strdup(token if style == 1 else user.encode())
                if not value:
                    for previous in range(index):
                        libc.free(responses[previous].response)
                    libc.free(allocation)
                    return 5
                responses[index].response = value
        output[0] = responses
        return 0

    return reply


def pam_account(service, role, *, hold=None):
    """Use libpam's installed configuration, with no authentication or session.

    The caller bounds this worker. No password, replacement PAM configuration,
    shell change or executable fixture can cause an inconclusive login failure
    to masquerade as the installed account gate's permission denial.
    """
    result = pam_callback(service, role, 'account', hold=hold)
    return {'account': result['status'], 'end': result['end']}


def pam_callback(service, role, callback, *, durable=False, hold=None, token=b''):
    """Call exactly one installed PAM boundary and retire its real handle."""
    guest.guard()
    services = DURABLE_SERVICES if durable else SERVICES
    guest.require(service in services and role in USERS and
                  callback in ('account', 'session', 'authentication-account') and
                  (durable or callback == 'account') and
                  (callback != 'authentication-account' or
                   (service == 'gdm-password' and hold is None and
                    (role == 'kiosk' and token == b'' or
                     role in ('ordinary', 'other') and isinstance(token, bytes) and
                     1 <= len(token) <= 256 and b'\0' not in token))),
                  'kiosk-admission:arguments')
    if service == 'gdm-password' and role == 'kiosk' and guest.package_path().suffix == '.rpm':
        from system_kiosk_confinement import caller_identity
        guest.require(Path('/proc/self/attr/current').read_text().strip().rstrip('\0') ==
                      caller_identity(service)[0], 'kiosk-admission:caller-context')
    # pam_start otherwise falls back to "other" for a missing service.
    configurations = [Path(root) / service for root in ('/etc/pam.d', '/usr/lib/pam.d')]
    path = next((path for path in configurations if path.exists() or path.is_symlink()), None)
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
    for name in ('pam_acct_mgmt', 'pam_open_session', 'pam_close_session', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
        getattr(pam, name).restype = ctypes.c_int
    pam.pam_start.restype = ctypes.c_int
    reply = empty_token_conversation(account.pw_name, token=token) if callback == 'authentication-account' else None
    handle = ctypes.c_void_p()
    conversation = Conversation(ctypes.cast(reply, ctypes.c_void_p).value if reply else None, None)
    guest.require(pam.pam_start(service.encode(), account.pw_name.encode(),
                               ctypes.byref(conversation), ctypes.byref(handle)) == 0,
                  'kiosk-admission:pam-start')
    status = 4  # PAM_SYSTEM_ERR if the account call fails before returning.
    closed = None
    authenticated = accounted = None
    try:
        if callback == 'authentication-account':
            pam.pam_authenticate.argtypes = [ctypes.c_void_p, ctypes.c_int]
            pam.pam_authenticate.restype = ctypes.c_int
            authenticated = status = pam.pam_authenticate(handle, 0)
            if authenticated == 0:
                accounted = status = pam.pam_acct_mgmt(handle, 0)
        else:
            operation = pam.pam_acct_mgmt if callback == 'account' else pam.pam_open_session
            status = operation(handle, 0)
        if hold is not None:
            hold(status)
    finally:
        try:
            if callback == 'session' and status == 0:
                closed = pam.pam_close_session(handle, 0)
        finally:
            ended = pam.pam_end(handle, status)
    if callback == 'authentication-account':
        return {'authenticate': authenticated, 'account': accounted, 'end': ended}
    return {'callback': callback, 'status': status, 'close': closed, 'end': ended}


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
    guest.guard()
    guest.require(service in SERVICES and role in USERS and type(expected) is int,
                  'kiosk-admission:arguments')
    with ExitStack() as resources:
        caller = ['/usr/bin/python3', '-B']
        if service == 'gdm-password' and role == 'kiosk' and guest.package_path().suffix == '.rpm':
            from system_kiosk_confinement import pam_caller_command
            # Match the distribution caller for the shared admission lock;
            # this is engineering setup, not a private-runtime MAC assertion.
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


def durable_probe(service, role, callback, expected, stage, record):
    """Observe the lifecycle's distribution-only barriers after payload erasure.

    Session probes deliberately call only open_session: they test the durable
    refusal, not successful GDM account/session composition or public entry.
    """
    guest.guard()
    guest.require(service in DURABLE_SERVICES and role in USERS and
                  callback in ('account', 'session') and type(expected) is int,
                  'kiosk-admission:arguments')
    with ExitStack() as resources:
        caller = ['/usr/bin/python3', '-B']
        if service == 'gdm-password' and role == 'kiosk' and guest.package_path().suffix == '.rpm':
            from system_kiosk_confinement import pam_caller_command
            # This baseline native caller route uses no erased product config.
            caller = resources.enter_context(pam_caller_command(guest.PAYLOAD, service))
        raw = guest.commands.run([
            *caller, str(Path(__file__).resolve()), 'pam-durable', service, role, callback],
            timeout=45, merge_stderr=False)
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise guest.GuestError('kiosk-admission:worker-result') from None
    guest.require(type(result) is dict and
                  set(result) == {'callback', 'status', 'close', 'end'} and
                  type(result['callback']) is str and
                  type(result['status']) is int and type(result['end']) is int and
                  (result['close'] is None or type(result['close']) is int),
                  'kiosk-admission:worker-result')
    record('onpc.kiosk.admission.' + stage, json.dumps(result, sort_keys=True))
    guest.require(result == {'callback': callback, 'status': expected,
                            'close': 0 if callback == 'session' and expected == 0 else None,
                            'end': 0}, 'kiosk-admission:unexpected-status:' + stage)


def empty_authentication_probe(expected_account, stage, record, *, expected_authenticate=0):
    """Observe empty-token authentication and its subsequent account authority."""
    guest.guard()
    guest.require(type(expected_authenticate) is int and expected_authenticate >= 0 and
                  ((expected_authenticate == 0 and type(expected_account) is int and
                    expected_account >= 0) or
                   (expected_authenticate != 0 and expected_account is None)),
                  'kiosk-admission:arguments')
    with ExitStack() as resources:
        caller = ['/usr/bin/python3', '-B']
        if guest.package_path().suffix == '.rpm':
            from system_kiosk_confinement import pam_caller_command
            caller = resources.enter_context(pam_caller_command(guest.PAYLOAD, 'gdm-password'))
        raw = guest.commands.run([
            *caller, str(Path(__file__).resolve()), 'pam-authentication-account'],
            timeout=45, merge_stderr=False)
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise guest.GuestError('kiosk-admission:worker-result') from None
    guest.require(type(result) is dict and set(result) == {'authenticate', 'account', 'end'} and
                  type(result['authenticate']) is int and type(result['end']) is int and
                  (result['account'] is None or type(result['account']) is int),
                  'kiosk-admission:worker-result')
    record('onpc.kiosk.admission.' + stage, json.dumps(result, sort_keys=True))
    guest.require(result == {'authenticate': expected_authenticate,
                            'account': expected_account, 'end': 0},
                  'kiosk-admission:unexpected-status:' + stage)


def routing(uid):
    from system_assertions import account_properties
    values = account_properties(uid, INTERFACE, {'Session': 's', 'SessionType': 's'})
    return values['Session'], values['SessionType']


def set_routing(uid, values):
    for method, value in zip(('SetSession', 'SetSessionType'), values):
        guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                   f'/org/freedesktop/Accounts/User{uid}', INTERFACE, method, 's', value])
    guest.require(routing(uid) == values, 'kiosk-admission:routing-write')


def routing_variations():
    """Finite one-input controls, each interpreted from dedicated Wayland."""
    alternate = 'gnome' if guest.package_path().suffix == '.rpm' else 'ubuntu'
    guest.require((Path('/usr/share/wayland-sessions') / (alternate + '.desktop')).is_file(),
                  'kiosk-admission:alternate-session-missing')
    return {'normal': DEDICATED, 'alternate-session': (alternate, DEDICATED[1]),
            'empty-fields': ('', ''), 'alternate-transport': (DEDICATED[0], 'x11')}


def routing_outage_probe(record, *, expected=4):
    """Real installed account callbacks while the caller owns discovery loss.

    The caller must additionally witness the installed helper's unavailable
    diagnostic and restore its exact service state before public recovery.
    """
    guest.require(type(expected) is int and expected in (0, 4), 'kiosk-admission:outage-expectation')
    probe('gdm-password', 'ordinary', 0, 'routing-outage.ordinary', record)
    probe('gdm-password', 'kiosk', expected, 'routing-outage.station', record)


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
    # The actual child-invoked su-l route is qualified separately. These
    # callbacks protect its native predicate, not terminal/SSH execution.
    probe('su-l', 'kiosk', PAM_PERM_DENIED, 'su-l.denied', record)
    probe('su-l', 'ordinary', 0, 'su-l.ordinary-after', record)


def verify(record):
    guest.guard()
    guest.enable_diagnostics()
    kiosk, ordinary = (pwd.getpwnam(USERS[role]) for role in ('kiosk', 'ordinary'))
    guest.require(kiosk.pw_uid != ordinary.pw_uid and kiosk.pw_shell == '/usr/sbin/nologin',
                  'kiosk-admission:identities')
    original = routing(kiosk.pw_uid)
    ordinary_routing = routing(ordinary.pw_uid)
    guest.require(original == DEDICATED, 'kiosk-admission:initial-routing')
    # Observe effective per-user SSH configuration only; this invokes no child
    # SSH operation and supplies no qualification of that login route.
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
        probe('su-l', 'kiosk', PAM_PERM_DENIED, 'su-l.denied', record)
        probe('su-l', 'ordinary', 0, 'su-l.ordinary-after', record)
        probe('gdm-password', 'kiosk', 0, 'dedicated-after', record)
        guest.require(routing(kiosk.pw_uid) == DEDICATED and
                      routing(ordinary.pw_uid) == ordinary_routing,
                      'kiosk-admission:routing-changed')
    finally:
        # Public setters restore only this attempt's deliberate kiosk mutation.
        if routing(kiosk.pw_uid) != original:
            set_routing(kiosk.pw_uid, original)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'ordinary-authentication':
        token = sys.stdin.buffer.read(257)
        print(json.dumps(pam_callback('gdm-password', sys.argv[2], 'authentication-account',
                                      durable=True, token=token), sort_keys=True))
    elif sys.argv[1:] == ['held-account']:
        held_worker()
    elif sys.argv[1:] == ['pam-authentication-account']:
        print(json.dumps(pam_callback('gdm-password', 'kiosk', 'authentication-account', durable=True),
                         sort_keys=True))
    elif len(sys.argv) == 5 and sys.argv[1] == 'pam-durable':
        print(json.dumps(pam_callback(sys.argv[2], sys.argv[3], sys.argv[4], durable=True),
                         sort_keys=True))
    else:
        guest.require(len(sys.argv) == 4 and sys.argv[1] == 'pam-account',
                      'kiosk-admission:arguments')
        original_uids = os.getresuid()
        try:
            if sys.argv[2] == 'su-l':
                guest.guard()
                caller = pwd.getpwnam(USERS['other'])
                guest.require(caller.pw_uid > 0, 'kiosk-admission:caller-identity')
                # Match setuid su's child real UID, retaining effective/saved root.
                # Fedora's vendor stack otherwise short-circuits account checks
                # for a root real UID before reaching the product module.
                os.setresuid(caller.pw_uid, 0, 0)
                guest.require(os.getresuid() == (caller.pw_uid, 0, 0),
                              'kiosk-admission:caller-credentials')
            result = pam_account(sys.argv[2], sys.argv[3])
        finally:
            os.setresuid(*original_uids)
        print(json.dumps(result, sort_keys=True))
