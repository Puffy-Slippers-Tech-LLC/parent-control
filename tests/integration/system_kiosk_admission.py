"""Installed account/routing admission, separate from final-exec and UI proof."""

import ctypes
import json
from pathlib import Path
import pwd
import stat
import sys

import system_guest as guest


SERVICES = ('gdm-password', 'login', 'sshd')
USERS = {'ordinary': 'onpc-parent-jamie', 'kiosk': 'oh-no-parent-control'}
INTERFACE = 'org.freedesktop.Accounts.User'
DEDICATED = ('oh-no-parent-control', 'wayland')
PAM_PERM_DENIED = 6


def pam_account(service, role):
    """Use libpam's installed configuration, with no authentication or session.

    The caller bounds this worker. No password, replacement PAM configuration,
    shell change or executable fixture can cause an inconclusive login failure
    to masquerade as the installed account gate's permission denial.
    """
    guest.guard()
    guest.require(service in SERVICES and role in USERS, 'kiosk-admission:arguments')
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
    finally:
        ended = pam.pam_end(handle, status)
    return {'account': status, 'end': ended}


def probe(service, role, expected, stage, record):
    raw = guest.commands.run([
        '/usr/bin/python3', '-B', str(Path(__file__).resolve()), 'pam-account', service, role],
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
    guest.require(len(sys.argv) == 4 and sys.argv[1] == 'pam-account',
                  'kiosk-admission:arguments')
    print(json.dumps(pam_account(sys.argv[2], sys.argv[3]), sort_keys=True))
