"""Bounded ordinary-account collateral checks for kiosk PAM and policy."""

from contextlib import contextmanager
import json
from pathlib import Path
import pwd
import runpy
import shlex

import system_guest as guest
from system_kiosk_accounts import ORDINARY_ACCOUNTS
from system_kiosk_confinement import process_identity, user_command
from system_wellbeing_qualification import manager, valid_invocation


PAYLOAD = Path('/usr/share/oh-no-parent-control/confinement')
PROC = Path('/proc')
SERVICES = ('wireplumber.service', 'pipewire.service',
            'oh-no-parent-control-wellbeing.service', 'dbus.service',
            'org.gnome.Kiosk@wayland.service')


def backend():
    suffix = guest.package_path().suffix
    guest.require(suffix in ('.deb', '.rpm'), 'kiosk-collateral:package-format')
    return 'selinux' if suffix == '.rpm' else 'apparmor'


def environment(process):
    return dict(entry.decode().split('=', 1) for entry in
                (process / 'environ').read_bytes().split(b'\0') if entry)


def ordinary_accounts():
    """Bind collateral controls to both unchanged prepared account roles."""
    baseline = json.loads(guest.BASELINE.read_bytes())
    result = {}
    for role, name in ORDINARY_ACCOUNTS.items():
        account = pwd.getpwnam(name)
        guest.require(baseline['accounts'].get(name) ==
                      {'uid': account.pw_uid, 'role': role} and
                      account.pw_uid > 0 and account.pw_shell == '/bin/bash',
                      'kiosk-collateral:baseline-role:' + role)
        result[role] = account
    return result


def verify_vendor_pam(record):
    """Verify finite owned distro blocks without auditing opaque vendor stacks.

    Vendor/admin denial authority needs its independent PAM-variant histories;
    this side-effect-free readiness read does not certify those policies.
    """
    integration = runpy.run_path('/usr/libexec/oh-no-parent-control-distro-pam')
    distribution = 'fedora' if backend() == 'selinux' else 'ubuntu'
    integration['runtime_ready'](distribution)
    record('onpc.kiosk.collateral.pam.owned-distro-blocks-ready', True)


@contextmanager
def owned_manager(account):
    """Stop only the invocation created here, including a failed startup."""
    unit = f'user@{account.pw_uid}.service'
    before = manager(unit)
    guest.require(before['ActiveState'] == 'inactive', 'kiosk-collateral:manager-already-active')
    identity = None
    try:
        try:
            guest.run(['systemctl', 'start', unit], timeout=75)
        finally:
            current = manager(unit)
            if (valid_invocation(current['InvocationID']) and
                    current['InvocationID'] != before['InvocationID']):
                identity = current
        guest.require(identity is not None and identity['ActiveState'] == 'active' and
                      identity['MainPID'].isdecimal() and int(identity['MainPID']) > 1,
                      'kiosk-collateral:manager-startup')
        yield PROC / identity['MainPID']
    finally:
        if identity is not None:
            guest.require(manager(unit)['InvocationID'] == identity['InvocationID'],
                          'kiosk-collateral:manager-replaced')
            guest.run(['systemctl', 'stop', unit], timeout=75)
            guest.require(manager(unit)['ActiveState'] == 'inactive',
                          'kiosk-collateral:manager-not-stopped')


def ordinary_process(process, account, backend, *, domain='unconfined_t'):
    guest.require(process_identity(process)[2] == (str(account.pw_uid),) * 4,
                  'kiosk-collateral:process-credentials')
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    label = (process / attribute).read_text().strip().rstrip('\0')
    parts = label.split(':')
    guest.require(label == 'unconfined' if backend == 'apparmor' else
                  len(parts) >= 4 and parts[2] == domain, 'kiosk-collateral:process-label')
    for executable in ('/usr/bin/python3', '/usr/bin/gjs', '/usr/bin/wireplumber'):
        original = Path(executable).stat()
        visible = (process / 'root' / executable.lstrip('/')).stat()
        guest.require((visible.st_dev, visible.st_ino) == (original.st_dev, original.st_ino),
                      'kiosk-collateral:private-executable')


def properties(account, service, names):
    raw = user_command(account, ['systemctl', '--user', 'show', service,
                                '--property=' + ','.join(names)]).decode()
    result = dict(line.split('=', 1) for line in raw.splitlines())
    guest.require(set(result) == set(names), 'kiosk-collateral:unit-properties')
    return result


def verify_units(account, backend):
    unit_path = user_command(account, ['systemctl', '--user', 'show',
                                     '--value', '--property=UnitPath']).decode().strip()
    guest.require(unit_path and str(PAYLOAD) not in unit_path, 'kiosk-collateral:private-unit-path')
    for service in SERVICES:
        names = ('LoadState', 'FragmentPath', 'DropInPaths',
                 'Environment', 'ExecStart', 'NoNewPrivileges')
        if service == 'wireplumber.service':
            names += ('LockPersonality', 'MemoryDenyWriteExecute',
                      'SystemCallFilter', 'SystemCallArchitectures')
        values = properties(account, service, names)
        guest.require(values['LoadState'] == 'loaded' and values['FragmentPath'] and
                      all(str(PAYLOAD) not in values[key] for key in
                          ('FragmentPath', 'DropInPaths', 'Environment', 'ExecStart')),
                      'kiosk-collateral:private-unit-override')
        if service in SERVICES[:3]:
            guest.require(values['NoNewPrivileges'] == 'yes', 'kiosk-collateral:vendor-nnp')
        if service == 'org.gnome.Kiosk@wayland.service':
            guest.require('GIO_USE_VFS=local' not in shlex.split(values['Environment']),
                          'kiosk-collateral:compositor-environment')
        if service == 'wireplumber.service':
            guest.require(values['LockPersonality'] == values['MemoryDenyWriteExecute'] == 'yes'
                          and values['SystemCallArchitectures'] == 'native' and
                          values['SystemCallFilter'] not in ('', '~'),
                          'kiosk-collateral:vendor-audio-hardening')
        if service == 'dbus.service':
            executable = '/usr/bin/dbus-daemon' if backend == 'apparmor' else '/usr/bin/dbus-broker-launch'
            guest.require('path=' + executable + ' ;' in values['ExecStart'] and
                          (backend != 'selinux' or '--scope user ;' in values['ExecStart']),
                          'kiosk-collateral:vendor-bus-executable')


def verify_services(account, backend):
    raw = user_command(account, ['systemctl', '--user', 'show-environment']).decode()
    inherited = dict(shlex.split(line)[0].split('=', 1) for line in raw.splitlines())
    guest.require(str(PAYLOAD) not in inherited.get('XDG_DATA_DIRS', '') and
                  'SYSTEMD_UNIT_PATH' not in inherited, 'kiosk-collateral:private-manager-environment')
    for service, names in (
        ('wireplumber.service', ('LUA_PATH', 'LUA_CPATH', 'WIREPLUMBER_CONFIG_DIR', 'WIREPLUMBER_DATA_DIR')),
        ('oh-no-parent-control-wellbeing.service', ('DCONF_PROFILE', 'GSETTINGS_BACKEND', 'XDG_CONFIG_HOME')),
        ('dbus.service', ('XDG_DATA_DIRS',)),
    ):
        user_command(account, ['systemctl', '--user', 'start', service])
        values = properties(account, service, ('MainPID', 'ActiveState'))
        guest.require(values['ActiveState'] == 'active' and values['MainPID'].isdecimal() and
                      int(values['MainPID']) > 1, 'kiosk-collateral:service-startup')
        process = PROC / values['MainPID']
        identity = process_identity(process)
        # Fedora's vendor user-bus entrypoint has its own ordinary domain.
        # Keep that measured distinction rather than accepting arbitrary labels.
        ordinary_process(process, account, backend, domain=(
            'unconfined_dbusd_t' if service == 'dbus.service' else 'unconfined_t'))
        actual = environment(process)
        guest.require(all(actual.get(name) == inherited.get(name) for name in names),
                      'kiosk-collateral:ordinary-service-environment')
        guest.require(process_identity(process) == identity and
                      properties(account, service, ('MainPID',))['MainPID'] == process.name,
                      'kiosk-collateral:service-replaced')


def verify(record):
    guest.guard()
    guest.enable_diagnostics()
    accounts = ordinary_accounts()
    selected_backend = backend()
    verify_vendor_pam(record)
    for role, account in accounts.items():
        with owned_manager(account) as process:
            identity = process_identity(process)
            ordinary_process(process, account, selected_backend)
            verify_units(account, selected_backend)
            verify_services(account, selected_backend)
            # These commands share the same ordinary transient-service boundary.
            # One fail-fast unit still executes each interpreter and witnesses
            # each result, without repeating systemd admission/collection.
            result = user_command(account, ['systemd-run', '--user', '--wait', '--collect',
                '--pipe', '--unit=onpc-collateral-execution', '/bin/sh', '-ec',
                "printf '%s\\n' onpc-ordinary-shell\n"
                "/usr/bin/python3 -I -c 'print(\"onpc-ordinary-python\")'\n"
                "/usr/bin/gjs -c 'print(\"onpc-ordinary-gjs\")'"])
            guest.require(result.splitlines() == [b'onpc-ordinary-shell', b'onpc-ordinary-python',
                                                  b'onpc-ordinary-gjs'],
                          'kiosk-collateral:ordinary-execution')
            guest.require(process_identity(process) == identity,
                          'kiosk-collateral:manager-process-replaced')
            record('onpc.kiosk.collateral.' + role + '.pam-manager-and-policy-preserved', True)
        record('onpc.kiosk.collateral.' + role + '.owned-manager-stopped', True)
