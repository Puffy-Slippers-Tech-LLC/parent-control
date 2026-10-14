"""Bounded ordinary-account collateral checks for kiosk PAM and policy."""

from contextlib import contextmanager
import json
from pathlib import Path
import pwd
import runpy
import shlex

import system_guest as guest
from system_kiosk_accounts import ORDINARY_ACCOUNTS
from system_kiosk_confinement import process_identity, user_command, verify_namespace_guard
from system_kiosk_platform import environment
from system_wellbeing_qualification import manager, valid_invocation


PAYLOAD = Path('/usr/share/oh-no-parent-control/confinement')
PROC = Path('/proc')
SERVICES = ('wireplumber.service', 'pipewire.service',
            'oh-no-parent-control-wellbeing.service', 'dbus.service',
            'org.gnome.Kiosk@wayland.service')
MASKS = ('snapd.session-agent.service', 'snapd.session-agent.socket',
         'snap.snapd-desktop-integration.snapd-desktop-integration.service',
         'snap.prompting-client.daemon.service',
         'snap.firmware-updater.firmware-notifier.service',
         'snap.firmware-updater.firmware-notifier.timer')


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
    integration = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement-integration')
    saved = integration['state']()
    guest.require(saved is not None, 'kiosk-collateral:pam-record-missing')
    integration['verify_pam'](saved)
    for service, state in saved['pam'].items():
        source = state['before'] if state['before'] is not None else state['vendor']
        actual = (integration['PAM_LOCAL'] / service).read_text()
        if service == 'systemd-user':
            guest.require(actual.startswith(integration['MANAGER_CREDENTIALS']),
                          'kiosk-collateral:manager-fallback')
            actual = actual.removeprefix(integration['MANAGER_CREDENTIALS'])
        guest.require(actual.startswith(integration['PREFIX']) and
                      actual.endswith(integration['BLOCK']), 'kiosk-collateral:pam-boundaries')
        original = actual.removeprefix(integration['PREFIX']).removesuffix(integration['BLOCK'])
        original = original.replace(integration['KEYRING_GUARD'], '')
        guest.require(original == source.rstrip('\n') + '\n',
                      'kiosk-collateral:vendor-callbacks-changed')
        record('onpc.kiosk.collateral.pam.' + service + '.vendor-callbacks-preserved', True)


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
    guest.require((process / 'root' / PAYLOAD.relative_to('/') / 'generation').read_text()
                  == 'unconfined\n', 'kiosk-collateral:private-generation')
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
        values = properties(account, service, ('LoadState', 'FragmentPath', 'DropInPaths',
                                              'Environment', 'ExecStart', 'NoNewPrivileges'))
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
            hardening = properties(account, service, ('LockPersonality', 'MemoryDenyWriteExecute',
                                                       'SystemCallFilter', 'SystemCallArchitectures'))
            guest.require(hardening['LockPersonality'] == hardening['MemoryDenyWriteExecute'] == 'yes'
                          and hardening['SystemCallArchitectures'] == 'native' and
                          hardening['SystemCallFilter'] not in ('', '~'),
                          'kiosk-collateral:vendor-audio-hardening')
        if service == 'dbus.service':
            executable = '/usr/bin/dbus-daemon' if backend == 'apparmor' else '/usr/bin/dbus-broker-launch'
            guest.require('path=' + executable + ' ;' in values['ExecStart'] and
                          (backend != 'selinux' or '--scope user ;' in values['ExecStart']),
                          'kiosk-collateral:vendor-bus-executable')
    if backend == 'apparmor':
        for name in MASKS:
            mask = PAYLOAD / 'user-units' / name
            guest.require(mask.is_symlink() and mask.readlink() == Path('/dev/null'),
                          'kiosk-collateral:private-mask-missing')
            values = properties(account, name, ('LoadState', 'FragmentPath'))
            guest.require(values['LoadState'] == 'loaded' and
                          values['FragmentPath'] not in ('', '/dev/null') and
                          str(PAYLOAD) not in values['FragmentPath'],
                          'kiosk-collateral:ordinary-service-masked')


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
    backend = json.loads((PAYLOAD / 'config.json').read_text())['backend']
    verify_vendor_pam(record)
    verify_namespace_guard(record)
    for role, account in accounts.items():
        with owned_manager(account) as process:
            identity = process_identity(process)
            ordinary_process(process, account, backend)
            verify_units(account, backend)
            verify_services(account, backend)
            for index, command in enumerate((
                ['/bin/sh', '-c', 'printf onpc-ordinary-shell'],
                ['/usr/bin/python3', '-I', '-c', 'print("onpc-ordinary-python")'],
                ['/usr/bin/gjs', '-c', 'print("onpc-ordinary-gjs")'],
            )):
                result = user_command(account, ['systemd-run', '--user', '--wait', '--collect',
                    '--pipe', '--unit=onpc-collateral-' + str(index), *command])
                guest.require(result.strip() == b'onpc-ordinary-' + (b'shell', b'python', b'gjs')[index],
                              'kiosk-collateral:ordinary-execution')
            guest.require(process_identity(process) == identity,
                          'kiosk-collateral:manager-process-replaced')
            record('onpc.kiosk.collateral.' + role + '.pam-manager-and-policy-preserved', True)
        record('onpc.kiosk.collateral.' + role + '.owned-manager-stopped', True)
