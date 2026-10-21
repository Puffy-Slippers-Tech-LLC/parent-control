"""Installed session identity and owned PAM workers, not confinement proof.

The retired private-runtime, material-generation and all-role MAC probes have
no selected production implementation. Their surviving route/authorization and
normal-use obligations remain pending installed qualification in the C-series
plan. These supporting observations do not qualify a public UI operation.
"""

from configparser import ConfigParser
from contextlib import contextmanager
import json
import os
from pathlib import Path
import pwd
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time

import system_guest as guest
from owned_commands import CommandError


ENV = ['PATH=/usr/bin:/bin', 'LANG=C', 'LC_ALL=C']
PROC = Path('/proc')
ACCOUNT = 'oh-no-parent-control'
SERVICES = {
    'compositor': 'org.gnome.Kiosk@wayland.service',
    'app': 'oh-no-parent-control-app.service',
    'polkit': 'oh-no-parent-control-polkit-agent.service',
    'notifications': 'oh-no-parent-control-notifications.service',
}
SESSION_TARGET = 'gnome-session@oh-no-parent-control.target'


def wait_kiosk_inactive(account, *,
                        identity_category='kiosk-confinement:kiosk-identity-changed',
                        active_category='kiosk-confinement:manager-already-active'):
    """Wait for public logout without adopting or stopping a manager."""
    deadline = time.monotonic() + 75
    unit = f'user@{account.pw_uid}.service'
    while True:
        guest.guard()
        guest.require(pwd.getpwnam(ACCOUNT).pw_uid == account.pw_uid, identity_category)
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
    # comm may contain spaces and parentheses. Fields after its last ')' start
    # at stat field 3; starttime and all four credentials detect substitution.
    fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
    status = dict(line.split(':', 1) for line in (process / 'status').read_text().splitlines()
                  if ':' in line)
    return (fields[19], int(status['PPid']), tuple(status['Uid'].split()))


def user_command(account, command, *, check=True, timeout=45):
    return guest.commands.run(
        ['/usr/bin/setpriv', '--reuid', str(account.pw_uid), '--regid', str(account.pw_gid),
         '--clear-groups', '/usr/bin/env', '-i', *ENV,
         f'XDG_RUNTIME_DIR=/run/user/{account.pw_uid}',
         f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{account.pw_uid}/bus', *command],
        check=check, timeout=timeout, merge_stderr=False)


def manager_pid(unit):
    return int(guest.run(['systemctl', 'show', '--value', '--property=MainPID', unit]))


def caller_identity(service):
    guest.require(service in ('gdm-password', 'systemd-user'),
                  'kiosk-confinement:unsupported-pam-caller')
    role = 'xdm' if service == 'gdm-password' else 'init'
    return f'system_u:system_r:{role}_t:s0', role + '_exec_t'


@contextmanager
def pam_caller_command(directory, service, *, expected_selinux='Enforcing'):
    """Give an engineering PAM worker the real Fedora caller's object labels.

    The native module's owned admission lease is created by the vendor caller.
    This fixture changes no policy and adds no arbitrary-code product route.
    """
    guest.guard(expected_selinux=expected_selinux)
    context, executable_type = caller_identity(service)
    with tempfile.TemporaryDirectory(prefix='pam-caller-', dir=directory) as temporary:
        caller = Path(temporary) / 'caller'
        shutil.copyfile(Path('/usr/bin/python3').resolve(), caller)
        caller.chmod(0o700)
        guest.run(['/usr/bin/chcon', '-t', executable_type, str(caller)])
        yield ['/usr/bin/runcon', context, str(caller), '-B']


def lifecycle_event(fd):
    """Read one bounded atomic event from an explicitly owned PAM worker."""
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


def properties(output, names):
    rows = output.splitlines()
    guest.require(all('=' in row for row in rows), 'kiosk-session:invalid-properties')
    values = dict(row.split('=', 1) for row in rows)
    guest.require(len(rows) == len(values) and set(values) == set(names),
                  'kiosk-session:invalid-properties')
    return values


def graphical_session(account):
    """Bind the one live station session through public logind properties."""
    sessions = []
    for row in guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines():
        fields = row.split()
        if len(fields) >= 2 and fields[1] == str(account.pw_uid):
            guest.require(re.fullmatch(r'[A-Za-z0-9_-]+', fields[0]) is not None,
                          'kiosk-session:invalid-session')
            sessions.append(fields[0])
    guest.require(len(sessions) == 1, 'kiosk-session:ambiguous-or-missing-session')
    names = ('User', 'Type', 'Class', 'Service', 'State')
    value = properties(guest.run(['loginctl', 'show-session', sessions[0],
        '--property=' + ','.join(names)], timeout=15), names)
    guest.require(value == {'User': str(account.pw_uid), 'Type': 'wayland',
                  'Class': 'user', 'Service': 'gdm-password', 'State': 'active'},
                  'kiosk-session:unexpected-session')
    return sessions[0], value


def user_unit(account, unit):
    names = ('ActiveState', 'InvocationID', 'MainPID', 'ControlGroup')
    return properties(user_command(account, ['/usr/bin/systemctl', '--user', 'show',
        '--property=' + ','.join(names), unit], check=False).decode(), names)


def session_target_state(account):
    # Targets have no MainPID or service ControlGroup properties.
    return user_command(account, ['/usr/bin/systemctl', '--user', 'show', '--value',
        '--property=ActiveState', SESSION_TARGET]).decode().strip()


def optional_service_state(account, unit):
    """Best-effort telemetry; feature restart/absence cannot veto the form."""
    try:
        value = user_command(account, ['/usr/bin/systemctl', '--user', 'show', '--value',
            '--property=ActiveState', unit], check=False, timeout=3).decode().strip()
        return value if value in ('active', 'inactive', 'failed', 'activating',
                                   'deactivating', 'reloading') else 'unavailable'
    except (CommandError, OSError, UnicodeError, subprocess.TimeoutExpired):
        return 'unavailable'


def census():
    """Observe live session/service identity after an independent public form read.

    This neither scans all kiosk processes nor asserts a private namespace,
    generation, executable allowlist or MAC role. Optional feature services can
    be unavailable without vetoing the core request form. Genuine approval and
    actual escape-route defenses require their separate installed results.
    """
    guest.guard()
    account = pwd.getpwnam(ACCOUNT)
    guest.require(account.pw_uid > 0 and account.pw_shell == '/usr/sbin/nologin',
                  'kiosk-session:account')
    session = graphical_session(account)
    unit = f'user@{account.pw_uid}.service'
    manager = PROC / str(manager_pid(unit))
    descriptor = os.pidfd_open(int(manager.name))
    descriptors = []
    try:
        identity = process_identity(manager)
        guest.require(identity[2] == (str(account.pw_uid),) * 4, 'kiosk-session:manager-uid')
        target = session_target_state(account)
        guest.require(target == 'active', 'kiosk-session:target-inactive')
        observed = {}
        optional = {}
        for role, name in SERVICES.items():
            if role not in ('compositor', 'app'):
                optional[role] = {'active_state': optional_service_state(account, name),
                                  'identity_observed': False}
                continue
            value = user_unit(account, name)
            guest.require(value['ActiveState'] == 'active', 'kiosk-session:service-inactive:' + role)
            pid = value['MainPID']
            guest.require(pid.isdecimal() and int(pid) > 1 and
                          re.fullmatch(r'[a-f0-9]{32}', value['InvocationID']) is not None and
                          value['InvocationID'] != '0' * 32 and
                          value['ControlGroup'].startswith('/'), 'kiosk-session:service-identity:' + role)
            process = PROC / pid
            pidfd = os.pidfd_open(int(pid))
            descriptors.append(pidfd)
            before = process_identity(process)
            guest.require(before[2] == (str(account.pw_uid),) * 4 and
                          (process / 'cgroup').read_text().strip() == '0::' + value['ControlGroup'],
                          'kiosk-session:service-owner:' + role)
            observed[role] = (name, value, process, pidfd, before)
        guest.guard()
        guest.require(pwd.getpwnam(ACCOUNT).pw_uid == account.pw_uid and
                      graphical_session(account) == session and
                      session_target_state(account) == target and
                      not exited(descriptor) and process_identity(manager) == identity and
                      manager_pid(unit) == int(manager.name), 'kiosk-session:lifecycle-changed')
        for name, value, process, pidfd, before in observed.values():
            guest.require(user_unit(account, name) == value and
                          (process is None or not exited(pidfd) and process_identity(process) == before),
                          'kiosk-session:lifecycle-changed')
        return {'scope': 'session-identity-only', 'confinement_qualified': False,
                'session': {key.lower(): value for key, value in session[1].items() if key != 'User'},
                'services': {**{role: {'active_state': value[1]['ActiveState'],
                                      'identity_observed': True}
                                for role, value in observed.items()}, **optional}}
    finally:
        for pidfd in descriptors:
            os.close(pidfd)
        os.close(descriptor)


def installed_configuration(path, section):
    parser = ConfigParser(interpolation=None, strict=False)
    with path.open() as stream:
        parser.read_file(stream)
    guest.require(parser.has_section(section), 'kiosk-session:missing-configuration')
    return parser[section]


def verify_session_composition(record):
    """Verify installed composition, never an execution fence.

    Installation/PAM histories call this at the greeter. Do not create a manager
    or manufacture a graphical-login result on their behalf.
    """
    guest.guard()
    account = pwd.getpwnam(ACCOUNT)
    suffix = guest.package_path().suffix
    guest.require(suffix in ('.deb', '.rpm'), 'kiosk-session:unsupported-package')
    distribution, backend = ('fedora', 'selinux') if suffix == '.rpm' else ('ubuntu', 'apparmor')
    guest.require(account.pw_uid > 0 and account.pw_shell == '/usr/sbin/nologin',
                  'kiosk-session:account')
    from system_kiosk_admission import DEDICATED, routing
    guest.require(routing(account.pw_uid) == DEDICATED, 'kiosk-session:dedicated-routing')
    guest.run(['/usr/libexec/oh-no-parent-control-distro-pam',
               '--distribution', distribution, 'verify'], timeout=45)
    desktop = installed_configuration(Path('/usr/share/wayland-sessions/oh-no-parent-control.desktop'),
                                      'Desktop Entry')
    session = installed_configuration(Path('/usr/share/gnome-session/sessions/oh-no-parent-control.session'),
                                      'GNOME Session')
    app = installed_configuration(Path('/usr/lib/systemd/user/oh-no-parent-control-app.service'), 'Service')
    guest.require(desktop.get('Exec') == 'gnome-session --session oh-no-parent-control' and
                  desktop.get('TryExec') == 'gnome-session' and session.getboolean('Kiosk') and
                  app.get('ExecStart') == '/usr/bin/oh-no-parent-control',
                  'kiosk-session:installed-composition')
    record('onpc.kiosk.session.composition', json.dumps({
        'distribution': distribution, 'session': 'GNOME-Kiosk',
        'dedicated_routing': True, 'distro_pam': 'verified',
        'confinement_qualified': False}, sort_keys=True))
    return account, backend


if __name__ == '__main__':
    guest.require(sys.argv[1:] == ['census'], 'kiosk-session:arguments')
    print(json.dumps(census(), sort_keys=True))
