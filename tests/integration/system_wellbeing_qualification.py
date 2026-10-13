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
    guest.require(manager(unit)['ActiveState'] == 'inactive', 'wellbeing-installed:manager-already-active')
    guest.run(['systemctl', 'start', unit], timeout=60)
    identity = manager(unit)
    guest.require(identity['ActiveState'] == 'active' and identity['MainPID'].isdecimal() and
                  int(identity['MainPID']) > 1 and re.fullmatch(r'[0-9a-f]{32}', identity['InvocationID']) and
                  identity['InvocationID'] != '0' * 32, 'wellbeing-installed:manager-identity')
    environment = {'HOME': account.pw_dir, 'USER': account.pw_name, 'LANG': 'C.UTF-8',
        'PATH': '/usr/bin:/bin', 'XDG_RUNTIME_DIR': f'/run/user/{account.pw_uid}',
        'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{account.pw_uid}/bus'}

    def user_command(arguments, **options):
        return guest.commands.run(['/usr/bin/setpriv', '--reuid', str(account.pw_uid),
            '--regid', str(account.pw_gid), '--init-groups', '/usr/bin/env', '-i',
            *[key + '=' + value for key, value in environment.items()], *arguments],
            timeout=30, merge_stderr=False, **options).decode().strip()

    try:
        raw = user_command(['systemctl', '--user', 'show-environment'])
        for line in raw.splitlines():
            if line.split('=', 1)[0] in SETTINGS_ENV:
                values = shlex.split(line)
                guest.require(len(values) == 1 and '=' in values[0], 'wellbeing-installed:settings-environment')
                key, value = values[0].split('=', 1)
                environment[key] = value
        guest.require(environment.get('GSETTINGS_BACKEND') != 'memory', 'wellbeing-installed:volatile-settings')
        # This is the installed session service, activated through its public
        # bus API. The client is exactly the operation used by component tests.
        source = (guest.PAYLOAD / 'wellbeing_probe.py').read_bytes()
        result = json.loads(user_command(['/usr/bin/python3', '-I', '-'], input=source))
        guest.require(set(result) == {'original', 'backup_recorded', 'suppressed', 'restored'} and
                      result['original'] in ('default', 'true', 'false') and
                      all(result[key] is True for key in ('backup_recorded', 'suppressed', 'restored')),
                      'wellbeing-installed:client-response')
        def service_identity():
            return dict(line.split('=', 1) for line in user_command(['systemctl', '--user', 'show',
                '--property=ActiveState,InvocationID,MainPID', SERVICE]).splitlines())
        service = service_identity()
        service_pid = service.get('MainPID', '')
        guest.require(set(service) == {'ActiveState', 'InvocationID', 'MainPID'} and
                      service['ActiveState'] == 'active' and service_pid.isdecimal() and
                      int(service_pid) > 1 and re.fullmatch(r'[0-9a-f]{32}', service['InvocationID']) and
                      service['InvocationID'] != '0' * 32 and
                      (Path('/proc') / service_pid).stat().st_uid == account.pw_uid,
                      'wellbeing-installed:service-identity')
        fields = (Path('/proc') / service_pid / 'environ').read_bytes().split(b'\0')
        actual = dict(field.decode().split('=', 1) for field in fields if b'=' in field)
        guest.require(all(actual.get(key) == environment.get(key) for key in SETTINGS_ENV),
                      'wellbeing-installed:settings-target-mismatch')
        guest.require(service_identity() == service, 'wellbeing-installed:service-replaced')
        result['ordinary_settings_environment_retained'] = True
    finally:
        guest.require(manager(unit) == identity, 'wellbeing-installed:manager-replaced')
        guest.run(['systemctl', 'stop', unit], timeout=60)
        guest.require(manager(unit)['ActiveState'] == 'inactive', 'wellbeing-installed:manager-not-stopped')
    result['owned_manager_stopped'] = True
    return result


if __name__ == '__main__':
    guest.require(sys.argv[1:] == ['ordinary'], 'wellbeing-installed:arguments')
    print(json.dumps(qualify(), sort_keys=True))
