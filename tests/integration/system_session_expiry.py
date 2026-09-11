"""Installed expiry diagnostics inside the exclusively leased test guest.

PAM probes use the installed stack and real pam_systemd from a transient service,
outside the SSH session. They do not claim to be a graphical GDM login. Only the
outer VM lease restores the guest; no process or session is discovered for killing.
"""

import ctypes
import json
import os
from pathlib import Path
import pwd
import re
import sys
import tempfile
import time

import system_guest as guest
from system_assertions import accepted, account_property, account_state, call

LIMITS = 'com.endlessm.ParentalControls.SessionLimits'
SERVICES = ('gdm-password', 'gdm-autologin', 'login', 'sshd')


def identities():
    guest.guard()
    guest.enable_diagnostics()
    names = {'child': 'onpc-child-riley', 'other': 'onpc-child-jordan',
             'parent': 'onpc-parent-jamie'}
    result = {role: pwd.getpwnam(name).pw_uid for role, name in names.items()}
    guest.require(len(set(result.values())) == 3, 'expiry:fixture-identities')
    return result


def grant(uid, seconds):
    guest.guard()
    # Fixture setup uses the same public property that the product writes. It
    # is not recorded as an approved request or a customer interaction.
    issued = int(time.time())
    guest.run(['busctl', '--system', 'set-property', 'org.freedesktop.Accounts',
               f'/org/freedesktop/Accounts/User{uid}', LIMITS, 'ActiveExtension',
               '(tu)', str(issued), str(seconds)])
    guest.require(account_property(uid, LIMITS, 'ActiveExtension') == [issued, seconds],
                  'expiry:fixture-grant-readback')
    return issued + seconds


def pam_probe(service):
    guest.require(service in SERVICES, 'expiry:pam-service')
    accounts = identities()
    uid = accounts['child']
    pam = ctypes.CDLL('libpam.so.0')

    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('appdata_ptr', ctypes.c_void_p)]

    pam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.POINTER(Conversation), ctypes.POINTER(ctypes.c_void_p)]
    pam.pam_putenv.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    pam.pam_getenv.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    pam.pam_getenv.restype = ctypes.c_char_p
    for name in ('pam_acct_mgmt', 'pam_open_session', 'pam_close_session', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    handle, conversation = ctypes.c_void_p(), Conversation()
    guest.require(pam.pam_start(service.encode(), pwd.getpwuid(uid).pw_name.encode(),
                               ctypes.byref(conversation), ctypes.byref(handle)) == 0,
                  'expiry:pam-start')
    opened = False
    try:
        # No desktop is launched. An unspecified session deliberately excludes
        # the broker's graphical-only fallback from making this check pass.
        guest.require(pam.pam_putenv(handle, b'XDG_SESSION_TYPE=unspecified') == 0,
                      'expiry:pam-environment')
        # Start near the beginning of a wall-clock second, leaving enough time
        # for the real account stack while retaining a <=1-second grant.
        time.sleep(max(0, int(time.time()) + 1.01 - time.time()))
        deadline = grant(uid, 1 if service.startswith('gdm-') else 3)
        account = pam.pam_acct_mgmt(handle, 0)
        print(json.dumps({'stage': 'account', 'status': account,
                          'remaining_seconds': round(deadline - time.time(), 3)}), flush=True)
        guest.require(account == 0, 'expiry:pam-account-denied')
        session = pam.pam_open_session(handle, 0)
        guest.require(session == 0, 'expiry:pam-open-session')
        opened = True
        session_id = pam.pam_getenv(handle, b'XDG_SESSION_ID')
        guest.require(session_id is not None, 'expiry:pam-session-identity')
        scope = guest.run(['loginctl', 'show-session', session_id.decode(),
                           '--property=Scope', '--value'])
        runtime = guest.run(['systemctl', 'show', scope,
                             '--property=RuntimeMaxUSec', '--value'])
        print(json.dumps({'stage': 'scope-created', 'runtime_max': runtime, 'scope': scope}), flush=True)
        if service.startswith('gdm-'):
            guest.require(runtime == 'infinity', 'expiry:finite-gdm-scope')
            time.sleep(3)
            guest.require(guest.run(['systemctl', 'is-active', scope]) == 'active',
                          'expiry:scope-ended-at-old-deadline')
            print(json.dumps({'stage': 'past-deadline', 'scope_active': True}), flush=True)
        else:
            guest.require(runtime != 'infinity', 'expiry:non-gdm-cap-removed')
            # The real scope timer should terminate this probe. Do not kill it
            # from the observer or treat its ordinary exit as timer enforcement.
            time.sleep(6)
            raise guest.GuestError('expiry:non-gdm-timer-did-not-terminate')
    finally:
        if opened:
            guest.require(pam.pam_close_session(handle, 0) == 0, 'expiry:pam-close')
        pam.pam_end(handle, 0)


def verify_pam_scope(service, record):
    accounts = identities()
    child, parent = accounts['child'], accounts['parent']
    before = account_state(accounts['other'])
    accepted(call(parent, 'SetParentControl', '(ubu)', (child, True, 0)))
    try:
        marker = guest.guard()
        unit = 'onpc-expiry-' + marker['run'] + '-' + service
        raw = guest.commands.run([
            'systemd-run', '--quiet', '--wait', '--pipe', '--collect',
            '--unit=' + unit, '--property=Type=exec', '--property=RuntimeMaxSec=45',
            '--setenv=ONPC_EXPECTED_RUN=' + marker['run'],
            '--setenv=PYTHONDONTWRITEBYTECODE=1',
            '/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_session_expiry.py'),
            '--pam', service], timeout=60, check=False, merge_stderr=False)
        status = guest.commands.last_returncode
        observations = [json.loads(line) for line in raw.decode().splitlines()
                        if line.startswith('{')]
        record('onpc.expiry.pam.' + service, json.dumps([
            {key: value for key, value in observation.items() if key != 'scope'}
            for observation in observations], sort_keys=True))
        guest.require(len(observations) >= 2 and observations[0]['stage'] == 'account'
                      and observations[0]['status'] == 0
                      and observations[1]['stage'] == 'scope-created', 'expiry:pam-witnesses')
        if service.startswith('gdm-'):
            guest.require(status == 0 and observations[0]['remaining_seconds'] <= 1
                          and observations[1]['runtime_max'] == 'infinity'
                          and observations[-1] == {'stage': 'past-deadline', 'scope_active': True},
                          'expiry:gdm-runtime-witness')
        else:
            scope = observations[1].get('scope', '')
            guest.require(re.fullmatch(r'session-[a-zA-Z0-9_-]+\.scope', scope),
                          'expiry:scope-witness-identity')
            journal = guest.run(['journalctl', '--no-pager', '-b', '-u', scope])
            # pam_systemd moves the worker out of its launcher service. That
            # service can exit successfully even when the scope kills its
            # member. Require the owned scope's actual timer-expiry event.
            guest.require(observations[1]['runtime_max'] != 'infinity'
                          and 'Scope reached runtime time limit. Stopping.' in journal,
                          'expiry:non-gdm-runtime-witness')
        guest.require(account_state(accounts['other']) == before, 'expiry:other-account-changed')
    finally:
        accepted(call(parent, 'SetParentControl', '(ubu)', (child, False, 60)))


def installed_manager():
    guest.guard()
    sys.path.insert(0, '/usr/lib/oh-no-parent-control/broker')
    try:
        from oh_no_parent_control.extension_manager import ExtensionManager
    finally:
        sys.path.pop(0)
    return ExtensionManager()


def pam_password_status(uid, password, *, account_only=False):
    """Bound each installed PAM transaction in its own recorded process.

    Credentials travel only through stdin, never command arguments, artifacts,
    or exception text. Native PAM modules must not be able to stall the entire
    runtime suite inside its long-lived Python observer.
    """
    from system_caller import FixturePassword
    guest.guard()
    guest.require(isinstance(password, FixturePassword)
                  and uid == identities()['child'], 'expiry:pam-password-fixture')
    phase = 'account' if account_only else 'authenticate'
    print('onpc-system: stage=pam-password-' + phase + ' outcome=started', flush=True)
    raw = guest.commands.run([
        '/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_session_expiry.py'),
        '--pam-password', phase],
        input=json.dumps({'uid': uid, 'password': password._value.decode('ascii')}).encode(),
        timeout=30, merge_stderr=False)
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise guest.GuestError('expiry:pam-password-result') from None
    guest.require(type(result) is int and 0 <= result <= 31, 'expiry:pam-password-status')
    return result


def pam_password_in_process(uid, secret, *, account_only=False):
    """The installed GDM authentication/account stacks, with a real PAM secret.

    No desktop is opened. PAM owns and frees the malloc-backed responses, as
    required by pam_conv; prompt text and credentials never enter evidence.
    """
    guest.guard()
    guest.require(uid == identities()['child'] and isinstance(secret, bytes)
                  and 1 <= len(secret) <= 256 and b'\0' not in secret,
                  'expiry:pam-password-fixture')
    pam, libc = ctypes.CDLL('libpam.so.0'), ctypes.CDLL(None)
    libc.calloc.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
    libc.calloc.restype = ctypes.c_void_p
    libc.strdup.argtypes = [ctypes.c_char_p]
    libc.strdup.restype = ctypes.c_void_p
    libc.free.argtypes = [ctypes.c_void_p]

    class Message(ctypes.Structure):
        _fields_ = [('style', ctypes.c_int), ('text', ctypes.c_char_p)]

    class Response(ctypes.Structure):
        _fields_ = [('text', ctypes.c_void_p), ('code', ctypes.c_int)]

    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.POINTER(Message)), ctypes.POINTER(ctypes.POINTER(Response)),
        ctypes.c_void_p)
    username = pwd.getpwuid(uid).pw_name.encode()

    @callback_type
    def converse(count, messages, output, _data):
        if not 1 <= count <= 32:
            return 19  # PAM_CONV_ERR
        memory = libc.calloc(count, ctypes.sizeof(Response))
        if not memory:
            return 5  # PAM_BUF_ERR
        responses = ctypes.cast(memory, ctypes.POINTER(Response))
        try:
            for index in range(count):
                style = messages[index].contents.style
                if style in (1, 2):
                    responses[index].text = libc.strdup(secret if style == 1 else username)
                    if not responses[index].text:
                        raise MemoryError
                elif style not in (3, 4):
                    raise ValueError
            output[0] = responses
            return 0
        except Exception:
            for index in range(count):
                libc.free(responses[index].text)
            libc.free(memory)
            return 19

    class Conversation(ctypes.Structure):
        _fields_ = [('callback', callback_type), ('data', ctypes.c_void_p)]

    pam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.POINTER(Conversation), ctypes.POINTER(ctypes.c_void_p)]
    for name in ('pam_authenticate', 'pam_acct_mgmt', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    handle, conversation = ctypes.c_void_p(), Conversation(converse, None)
    guest.require(pam.pam_start(b'gdm-password', username, ctypes.byref(conversation),
                               ctypes.byref(handle)) == 0, 'expiry:pam-password-start')
    try:
        operation = pam.pam_acct_mgmt if account_only else pam.pam_authenticate
        return operation(handle, 0)
    finally:
        pam.pam_end(handle, 0)


def verify_zero_time_pam(record):
    from system_caller import FixturePassword
    accounts = identities()
    child, parent = accounts['child'], accounts['parent']
    password = FixturePassword()
    password.install(child)
    accepted(call(parent, 'RevokeOneTimeGrant', '(u)', (child,)))
    denied = (pam_password_status(child, password),
              pam_password_status(child, password, account_only=True))
    record('onpc.expiry.pam-denied-status', json.dumps({
        'authentication': denied[0], 'account': denied[1]}, sort_keys=True))
    # Our authentication hook returns PAM_ACCT_EXPIRED (13). The stock
    # pam_malcontent account hook returns PAM_AUTH_ERR (7) for exhausted time;
    # preserve that authoritative denial rather than demanding another code.
    guest.require(denied == (13, 7), 'expiry:zero-time-pam-not-expired')
    grant(child, 45)
    try:
        allowed = (pam_password_status(child, password),
                   pam_password_status(child, password, account_only=True))
        guest.require(allowed == (0, 0), 'expiry:positive-time-pam-denied')
        record('onpc.expiry.pam-admission', json.dumps({
            'zero_time_authentication': denied[0], 'zero_time_account': denied[1],
            'positive_time_authentication': allowed[0], 'positive_time_account': allowed[1],
        }, sort_keys=True))
    finally:
        accepted(call(parent, 'RevokeOneTimeGrant', '(u)', (child,)))


def verify_request_extension(record):
    """Authenticated real broker calls for child and kiosk, in the retained session.

    This observes the installed API and Polkit path; it is not UI click evidence.
    """
    from system_caller import FixturePassword, PersistentCaller, TextAgent
    accounts = identities()
    child, parent = accounts['child'], accounts['parent']
    other_parent = pwd.getpwnam('onpc-parent-casey').pw_uid
    kiosk = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())['kiosk_uid']
    password = FixturePassword()
    password.install(parent)
    before_other = account_state(accounts['other'])
    deadline = None
    for surface, uid, seconds in (('child', child, 15), ('kiosk', kiosk, 60)):
        with PersistentCaller(uid) as caller, TextAgent(caller) as agent:
            caller.send({
                'kind': 'call', 'method': 'RequestOwnAccess' if surface == 'child' else 'RequestAccess',
                'signature': '(uub)' if surface == 'child' else '(uuub)',
                'args': (parent, seconds, False) if surface == 'child'
                        else (child, parent, seconds, False),
            })
            agent.prompt(parent, other_parent)
            agent.authenticate(password)
            result = accepted(caller.receive())
            guest.require(result[1] == 'approved', 'expiry:request-not-approved:' + surface)
        extension = account_property(child, LIMITS, 'ActiveExtension')
        guest.require(extension[0] > 0 and extension[1] >= seconds,
                      'expiry:request-grant-missing:' + surface)
        if deadline is None:
            guest.require(extension[1] == seconds, 'expiry:unexpected-initial-approved-duration')
            deadline = sum(extension)
        else:
            guest.require(time.time() < deadline and sum(extension) > deadline,
                          'expiry:extension-not-before-original-deadline')
        record('onpc.expiry.request.' + surface, 'polkit-authenticated; approved; grant-readback')
    guest.require(account_state(accounts['other']) == before_other, 'expiry:request-other-account-changed')
    return deadline


def verify_runtime_rollback(record):
    """Inject bounded response/readback/activation failures over real dconf.

    Only the selected installed manager instance is instrumented. Each fault is
    one-shot, allowing its actual rollback operations and readback to run.
    """
    accounts = identities()
    manager = installed_manager()
    account, _ = manager._account(accounts['child'])
    live = manager._shell_is_available(account)

    class FaultManager(type(manager)):
        def __init__(self, fault):
            super().__init__()
            self.fault, self.armed, self.fired = fault, False, False

        def _set_boolean(self, account, key, value):
            if key == 'disable-user-extensions' and value is False and not self.fired:
                self.armed = True
            super()._set_boolean(account, key, value)
            if self.fault == 'write-response' and self.armed and not self.fired:
                self.fired = True
                raise RuntimeError('injected extension write response failure')

        def _boolean(self, account, key):
            value = super()._boolean(account, key)
            if self.fault == 'readback' and self.armed and not self.fired and value is False:
                self.fired = True
                return True
            return value

        def _set_live(self, *args):
            super()._set_live(*args)
            self.fail_activation()

        def _set_offline(self, *args):
            super()._set_offline(*args)
            self.fail_activation()

        def fail_activation(self):
            if self.fault == 'activation' and not self.fired:
                self.fired = True
                raise RuntimeError('injected extension activation failure')

    for fault in ('write-response', 'readback', 'activation'):
        manager._set_boolean(account, 'disable-user-extensions', True)
        if live:
            deadline = time.monotonic() + 10
            while manager._runtime_state(account)[1]:
                guest.require(time.monotonic() < deadline, 'expiry:rollback-disable-not-observed')
                time.sleep(0.1)
        previous = (manager._list(account, 'enabled-extensions'),
                    manager._list(account, 'disabled-extensions'))
        runtime = manager._runtime_state(account) if live else None
        faulty = FaultManager(fault)
        failed = False
        try:
            faulty.set_enabled(accounts['child'], True, recover_global_switch=True)
        except RuntimeError:
            failed = True
        guest.require(failed and faulty.fired, 'expiry:injected-failure-not-exercised')
        guest.require(manager._boolean(account, 'disable-user-extensions') is True
                      and manager._list(account, 'enabled-extensions') == previous[0]
                      and manager._list(account, 'disabled-extensions') == previous[1]
                      and (not live or manager._runtime_state(account) == runtime),
                      'expiry:injected-failure-rollback-unverified')
        manager.set_enabled(accounts['child'], True, recover_global_switch=True)
        mode = 'live' if live else 'offline'
        record('onpc.expiry.rollback.' + mode + '.' + fault,
               'injected; real-settings-and-runtime-rollback-verified')


def verify_unavailable_enforcement(record):
    """A real startup activation failure must prevent a new grant.

    Temporarily withhold the verified extension metadata in the leased guest.
    Keep its exact inode in a new private fixture and restore it before broker
    recovery. No other file, process, or desktop is discovered for cleanup.
    """
    accounts = identities()
    manager = installed_manager()
    child, parent = accounts['child'], accounts['parent']
    account, _ = manager._account(child)
    manager._verify_installation()
    metadata = manager.installation / 'metadata.json'
    # Both enforcement and graphical preparation run this probe in one attempt.
    # Retain each private directory for outer VM cleanup without reusing it.
    fixture = Path(tempfile.mkdtemp(prefix='onpc-test-extension-failure-', dir='/var/lib'))
    saved = fixture / 'metadata.json'
    original = metadata.stat()
    digest = guest.sha(metadata)
    accepted(call(parent, 'RevokeOneTimeGrant', '(u)', (child,)))
    before = account_state(child)
    manager._set_boolean(account, 'disable-user-extensions', True)
    guest.run(['systemctl', 'stop', guest.BROKER])
    metadata.rename(saved)
    try:
        reply = call(child, 'RequestOwnAccess', '(uub)', (parent, 60, False))
        guest.require('error' in reply and 'result' not in reply,
                      'expiry:approval-without-enforcement')
        guest.require(account_state(child) == before,
                      'expiry:grant-written-without-enforcement')
        owner = guest.run(['busctl', '--system', 'call', 'org.freedesktop.DBus',
                          '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                          'NameHasOwner', 's', guest.BUS])
        guest.require(owner == 'b false', 'expiry:failed-startup-owned-bus')
        guest.require(manager._boolean(account, 'disable-user-extensions'),
                      'expiry:failed-startup-changed-global-switch')
        record('onpc.expiry.unavailable-enforcement',
               'startup-refused; request-failed; grant-unchanged; bus-name-unowned')
    finally:
        current = saved.lstat()
        guest.require(not metadata.exists() and not metadata.is_symlink()
                      and (current.st_dev, current.st_ino) == (original.st_dev, original.st_ino)
                      and guest.sha(saved) == digest, 'expiry:activation-failure-restore-identity')
        saved.rename(metadata)
        guest.activate_broker()
        guest.require(not manager._boolean(account, 'disable-user-extensions'),
                      'expiry:activation-failure-recovery')


def verify_offline_recovery(record):
    accounts = identities()
    child, parent = accounts['child'], accounts['parent']
    manager = installed_manager()
    account, _ = manager._account(child)
    guest.require(not manager._shell_is_available(account), 'expiry:expected-offline-shell')
    accepted(call(parent, 'SetParentControl', '(ubu)', (child, True, 0)))
    enabled = manager._list(account, 'enabled-extensions')
    disabled = manager._list(account, 'disabled-extensions')
    before_other = account_state(accounts['other'])
    try:
        # Individually selected canaries need not ship extension code. These
        # assert exact preservation of the settings lists during recovery.
        product = 'oh-no-parent-control@tech.puffyslippers.com'
        selected = ['onpc-preserve-enabled@example.invalid',
                    *(value for value in enabled if value != product), product]
        excluded = [*disabled, 'onpc-preserve-disabled@example.invalid']
        manager._set_list(account, 'enabled-extensions', selected)
        manager._set_list(account, 'disabled-extensions', excluded)
        manager._set_boolean(account, 'disable-user-extensions', True)
        guest.activate_broker()
        guest.require(not manager._boolean(account, 'disable-user-extensions')
                      and manager._list(account, 'enabled-extensions') == selected
                      and manager._list(account, 'disabled-extensions') == excluded,
                      'expiry:offline-recovery-readback')
        guest.require(account_state(accounts['other']) == before_other,
                      'expiry:offline-recovery-other-account')
        record('onpc.expiry.offline-recovery', 'broker-active; switch-restored; selections-preserved')
        verify_runtime_rollback(record)
        verify_unavailable_enforcement(record)
    finally:
        manager._set_boolean(account, 'disable-user-extensions', False)
        manager._set_list(account, 'enabled-extensions', enabled)
        manager._set_list(account, 'disabled-extensions', disabled)
        accepted(call(parent, 'SetParentControl', '(ubu)', (child, False, 60)))


if __name__ == '__main__':
    try:
        guest.guard()
        guest.require(len(sys.argv) == 3, 'expiry:arguments')
        if sys.argv[1] == '--pam-password':
            guest.require(sys.argv[2] in ('account', 'authenticate'), 'expiry:pam-password-phase')
            payload = json.loads(sys.stdin.buffer.read(1024))
            guest.require(isinstance(payload, dict) and set(payload) == {'uid', 'password'}
                          and type(payload['uid']) is int and isinstance(payload['password'], str),
                          'expiry:pam-password-input')
            print(json.dumps(pam_password_in_process(payload['uid'], payload['password'].encode('ascii'),
                             account_only=sys.argv[2] == 'account')), flush=True)
        else:
            guest.require(sys.argv[1] == '--pam', 'expiry:arguments')
            pam_probe(sys.argv[2])
    except Exception as error:
        category = str(error) if isinstance(error, guest.GuestError) else type(error).__name__
        print('onpc-system: stage=expiry-probe outcome=failed category=' + category,
              file=sys.stderr, flush=True)
        raise SystemExit(1) from None
