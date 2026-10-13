#!/usr/bin/python3
"""Installed engineering check on one idle ordinary fixture user manager."""
import json
from pathlib import Path
import pwd
import re
import shlex
import sys

import system_guest as guest

ACCOUNT = 'onpc-child-jordan'
SERVICE = 'oh-no-parent-control-wellbeing.service'
SETTINGS_ENV = ('DCONF_PROFILE', 'XDG_CONFIG_HOME', 'GSETTINGS_BACKEND')


def valid_invocation(value):
    return bool(re.fullmatch(r'[0-9a-f]{32}', value)) and value != '0' * 32


def manager(unit):
    value = dict(line.split('=', 1) for line in guest.run(['systemctl', 'show',
        '--property=ActiveState,InvocationID,MainPID', unit], timeout=15).splitlines())
    guest.require(set(value) == {'ActiveState', 'InvocationID', 'MainPID'}, 'wellbeing-installed:manager-state')
    return value


def qualify():
    guest.guard()
    account = pwd.getpwnam(ACCOUNT)
    guest.require(account.pw_uid >= 1000 and account.pw_uid != pwd.getpwnam('oh-no-parent-control').pw_uid,
                  'wellbeing-installed:fixture-account')
    unit = f'user@{account.pw_uid}.service'
    before = manager(unit)
    guest.require(before['ActiveState'] == 'inactive', 'wellbeing-installed:manager-already-active')
    identity = None
    environment = {'HOME': account.pw_dir, 'USER': account.pw_name, 'LANG': 'C.UTF-8',
        'PATH': '/usr/bin:/bin', 'XDG_RUNTIME_DIR': f'/run/user/{account.pw_uid}',
        'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{account.pw_uid}/bus'}

    def user_command(arguments, **options):
        return guest.commands.run(['/usr/bin/setpriv', '--reuid', str(account.pw_uid),
            '--regid', str(account.pw_gid), '--init-groups', '/usr/bin/env', '-i',
            *[key + '=' + value for key, value in environment.items()], *arguments],
            timeout=30, merge_stderr=False, **options).decode().strip()

    try:
        try:
            guest.run(['systemctl', 'start', unit], timeout=60)
        finally:
            current = manager(unit)
            # A failed start can still have created a live invocation. Record
            # that identity before validating readiness so cleanup owns it too.
            if (valid_invocation(current['InvocationID']) and
                    current['InvocationID'] != before['InvocationID']):
                identity = current
        guest.require(identity is not None and identity['ActiveState'] == 'active' and
                      identity['MainPID'].isdecimal() and int(identity['MainPID']) > 1,
                      'wellbeing-installed:manager-identity')
        raw = user_command(['systemctl', '--user', 'show-environment'])
        for line in raw.splitlines():
            if line.split('=', 1)[0] in SETTINGS_ENV:
                values = shlex.split(line)
                guest.require(len(values) == 1 and '=' in values[0], 'wellbeing-installed:settings-environment')
                key, value = values[0].split('=', 1)
                environment[key] = value
        # Exercise populated values even when the ordinary baseline has no
        # explicit overrides. These defaults address the same settings store;
        # leave an absent DConf profile absent rather than inventing a profile.
        environment.setdefault('XDG_CONFIG_HOME', str(Path(account.pw_dir) / '.config'))
        environment.setdefault('GSETTINGS_BACKEND', 'dconf')
        guest.require(environment.get('GSETTINGS_BACKEND') != 'memory', 'wellbeing-installed:volatile-settings')

        def service_identity():
            value = dict(line.split('=', 1) for line in user_command(['systemctl', '--user', 'show',
                '--property=ActiveState,InvocationID,MainPID', SERVICE]).splitlines())
            guest.require(set(value) == {'ActiveState', 'InvocationID', 'MainPID'},
                          'wellbeing-installed:service-state')
            return value

        def active_service():
            value = service_identity()
            pid = value['MainPID']
            guest.require(value['ActiveState'] == 'active' and pid.isdecimal() and int(pid) > 1 and
                          valid_invocation(value['InvocationID']) and
                          (Path('/proc') / pid).stat().st_uid == account.pw_uid,
                          'wellbeing-installed:service-identity')
            return value

        # The default-target helper may already be running. Stop that owned
        # invocation before changing only this attempt's manager environment.
        user_command(['systemctl', '--user', 'start', SERVICE])
        original_service = active_service()
        guest.require(service_identity() == original_service, 'wellbeing-installed:service-replaced')
        user_command(['systemctl', '--user', 'stop', SERVICE])
        guest.require(service_identity()['ActiveState'] == 'inactive', 'wellbeing-installed:service-not-stopped')
        user_command(['systemctl', '--user', 'set-environment',
                      *[key + '=' + environment[key] for key in SETTINGS_ENV if key in environment]])
        user_command(['systemctl', '--user', 'start', SERVICE])
        # Exercise the installed session service through its public bus API.
        # The client is exactly the operation used by component tests.
        source = (guest.PAYLOAD / 'wellbeing_probe.py').read_bytes()
        result = json.loads(user_command(['/usr/bin/python3', '-I', '-'], input=source))
        guest.require(set(result) == {'original', 'backup_recorded', 'suppressed', 'restored'} and
                      result['original'] in ('default', 'true', 'false') and
                      all(result[key] is True for key in ('backup_recorded', 'suppressed', 'restored')),
                      'wellbeing-installed:client-response')
        service = active_service()
        service_pid = service['MainPID']
        fields = (Path('/proc') / service_pid / 'environ').read_bytes().split(b'\0')
        actual = dict(field.decode().split('=', 1) for field in fields if b'=' in field)
        guest.require(all(actual.get(key) == environment.get(key) for key in SETTINGS_ENV),
                      'wellbeing-installed:settings-target-mismatch')
        guest.require(service_identity() == service, 'wellbeing-installed:service-replaced')
        result['ordinary_settings_environment_retained'] = True
    finally:
        if identity is not None:
            # Readiness/state can change on a failed invocation. Ownership
            # follows its immutable systemd identity, never a replacement.
            guest.require(manager(unit)['InvocationID'] == identity['InvocationID'],
                          'wellbeing-installed:manager-replaced')
            guest.run(['systemctl', 'stop', unit], timeout=60)
            guest.require(manager(unit)['ActiveState'] == 'inactive', 'wellbeing-installed:manager-not-stopped')
    result['owned_manager_stopped'] = True
    return result


if __name__ == '__main__':
    guest.require(sys.argv[1:] == ['ordinary'], 'wellbeing-installed:arguments')
    print(json.dumps(qualify(), sort_keys=True))
