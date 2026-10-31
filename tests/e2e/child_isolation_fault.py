"""One attempt-owned missing fixture home; no product policy substitution."""
import json
import ast
from io import BytesIO
import os
from pathlib import Path
import pwd
import secrets
import stat
import sys
from zipfile import ZipFile


def require(value, code):
    if not value:
        raise RuntimeError('child-isolation:' + code)


def guest_operation(action, token, receipt):
    sys.path.insert(0, '/var/tmp/onpc-system-input')
    import system_guest as guest
    from gi.repository import Gio, GLib
    marker = guest.guard()
    guest.enable_diagnostics()
    require(len(token) == 32 and all(c in '0123456789abcdef' for c in token), 'token')
    account = pwd.getpwnam('onpc-child-jordan')
    home = Path(account.pw_dir)
    require(account.pw_uid >= 1000 and home == Path('/home/onpc-child-jordan'), 'account')
    hidden = home.with_name('.onpc-u02-' + token)
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def call(method, signature=None, values=(), destination=guest.BUS,
             path='/com/puffyslippers/OhNoParentControl1', interface=guest.BUS):
        return bus.call_sync(destination, path, interface, method,
            GLib.Variant(signature, values) if signature else None,
            None, Gio.DBusCallFlags.NONE, 30000, None).unpack()

    def preferences():
        return json.loads(call('GetPreferences', '(u)', (account.pw_uid,))[0])

    def enforcement():
        path = '/org/freedesktop/Accounts/User' + str(account.pw_uid)
        values = {interface: call('GetAll', '(s)', (interface,),
            destination='org.freedesktop.Accounts', path=path,
            interface='org.freedesktop.DBus.Properties')[0]
            for interface in ('com.endlessm.ParentalControls.AppFilter',
                              'com.endlessm.ParentalControls.SessionLimits')}
        # D-Bus structs unpack as tuples; receipts cross the JSON transport.
        return json.loads(json.dumps(values))

    def diagnostics():
        # Use the product's bounded, validated export and canonical reader.
        sys.path.insert(0, '/usr/lib/oh-no-parent-control')
        from common.oh_no_parent_control_ui.diagnostic_bundle import validate_bundle
        from common.oh_no_parent_control_ui.diagnostic_report import read_report
        data = bytes(call('ExportDiagnosticLogs')[0])
        require(0 < len(data) <= 16 * 1024 * 1024, 'diagnostic-bound')
        with ZipFile(BytesIO(validate_bundle(data))) as archive:
            logs, _ = read_report(archive)
        return [record for name, records in logs.items() if name.startswith('broker/')
                for record in records]

    def inactive():
        sessions = call('ListSessions', destination='org.freedesktop.login1',
            path='/org/freedesktop/login1', interface='org.freedesktop.login1.Manager')[0]
        require(not any(row[1] == account.pw_uid for row in sessions), 'live-child-session')
        require(guest.run(['systemctl', 'show', '--property=ActiveState', '--value',
                          f'user@{account.pw_uid}.service']) in ('inactive', 'failed'),
                'live-child-manager')

    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    parent = home.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0
            and not parent.st_mode & 0o022 and not home.parent.is_symlink(), 'home-parent')
    if action == 'install':
        inactive()
        info = home.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == account.pw_uid
                and not home.is_symlink() and not os.path.lexists(hidden)
                and not os.path.ismount(home), 'home-identity')
        policy, live = preferences(), enforcement()
        previous_failures = [record for record in diagnostics() if record['event'] == 'core.001']
        require(policy['parent_control_enabled'] is True, 'child-not-enabled')
        guest.run(['systemctl', 'stop', guest.BROKER])
        inactive()
        current = home.lstat()
        require([current.st_dev, current.st_ino, current.st_uid, current.st_mode] ==
                [info.st_dev, info.st_ino, info.st_uid, info.st_mode]
                and not os.path.lexists(hidden), 'home-changed')
        home.rename(hidden)
        return {'run': marker['run'], 'boot': boot, 'uid': account.pw_uid,
                'home': [info.st_dev, info.st_ino],
                'parent': [parent.st_dev, parent.st_ino], 'policy': policy, 'live': live,
                'previous_failures': previous_failures}

    require(receipt['run'] == marker['run'] and receipt['boot'] == boot
            and receipt['uid'] == account.pw_uid
            and receipt['parent'] == [parent.st_dev, parent.st_ino], 'attempt-changed')
    info = hidden.lstat()
    require(not os.path.lexists(home) and stat.S_ISDIR(info.st_mode)
            and info.st_uid == account.pw_uid and not hidden.is_symlink()
            and receipt['home'] == [info.st_dev, info.st_ino], 'hidden-home-changed')
    if action == 'verify-refusal':
        # Submitting a request intentionally saves its duration/app choices;
        # those UI preferences are independent of authoritative parent policy.
        current = preferences()
        require({key: value for key, value in current.items() if key != 'request'} ==
                {key: value for key, value in receipt['policy'].items() if key != 'request'},
                'refusal-parent-policy-changed')
        require(enforcement() == receipt['live'], 'refusal-enforcement-or-grant-changed')
        return {'no_new_grant': True, 'authoritative_policy_preserved': True,
                'native_enforcement_preserved': True}
    if action == 'restore':
        inactive()
        hidden.rename(home)
        guest.run(['systemctl', 'restart', guest.BROKER])
        require(guest.run(['systemctl', 'is-active', guest.BROKER]) == 'active', 'restore-startup')
        def setting(key):
            return guest.run(['/usr/bin/setpriv', '--reuid', str(account.pw_uid),
                '--regid', str(account.pw_gid), '--clear-groups', '/usr/bin/env', '-i',
                'HOME=' + str(home), 'PATH=/usr/bin:/bin', 'LANG=C',
                '/usr/bin/dbus-run-session', '--', '/usr/bin/gsettings', 'get',
                'org.gnome.shell', key])
        uuid = 'oh-no-parent-control@tech.puffyslippers.com'
        enabled = ast.literal_eval(setting('enabled-extensions').removeprefix('@as '))
        disabled = ast.literal_eval(setting('disabled-extensions').removeprefix('@as '))
        require(type(enabled) is list and type(disabled) is list
                and uuid in enabled and uuid not in disabled
                and setting('disable-user-extensions') == 'false', 'restored-activation')
        return {'restored': True, 'same_home': True, 'supported_startup': True,
                'extension_activation_restored': True}

    require(action == 'startup', 'action')
    guest.run(['systemctl', 'start', guest.BROKER])
    require(guest.run(['systemctl', 'is-active', guest.BROKER]) == 'active', 'isolated-startup')
    require(account.pw_uid in {row[0] for row in call('ListManagedUsers')[0]}, 'hidden-child')
    require(preferences() == receipt['policy'] and enforcement() == receipt['live'], 'startup-policy-changed')
    records = diagnostics()
    failures = [record for record in records if record['event'] == 'core.001'
                and record not in receipt['previous_failures']]
    require(bool(failures) and any(record['event'] == 'runtime.failure-cause'
            and record['segment'] == failures[-1]['segment']
            and record['fields']['source'] == 'extension-manager'
            and record['fields']['error_type'] == 'RuntimeError' for record in records),
            'original-sanitized-diagnostic-missing')
    try:
        call('SetParentControl', '(ubu)', (account.pw_uid, False,
             receipt['policy']['daily_time_limit_minutes']))
    except GLib.Error as error:
        require(Gio.DBusError.get_remote_error(error) == guest.BUS + '.Error.BackendFailure',
                'unexpected-toggle-error')
    else:
        raise RuntimeError('child-isolation:integration-dependent-toggle-succeeded')
    require(preferences() == receipt['policy'] and enforcement() == receipt['live'], 'refusal-policy-changed')
    return {'broker_ready': True, 'unavailable_child_listed': True,
            'integration_toggle_refused': True, 'authoritative_policy_preserved': True,
            'native_enforcement_preserved': True, 'original_sanitized_cause_preserved': True}


class ChildIsolationFault:
    def __init__(self, journey, lease):
        self.journey, self.lease = journey, lease
        self.token, self.receipt, self.restored = secrets.token_hex(16), None, False
        self.source = Path(__file__).read_bytes()

    def call(self, action):
        import watch_activity
        self.lease.guard()
        with watch_activity.operation({
                'install': 'Making the inactive fixture child home unavailable',
                'startup': 'Checking isolated broker startup and unchanged child policy',
                'verify-refusal': 'Checking refused approval preserved child policy and native enforcement',
                'restore': 'Restoring the exact fixture home and retrying broker startup'}[action]):
            raw = self.journey.transport.call([
                'env', 'ONPC_EXPECTED_RUN=' + self.lease.state['run'],
                '/usr/bin/python3', '-I', '-', action, self.token, json.dumps(self.receipt)],
                input=self.source, timeout=180)
        self.lease.guard()
        require(type(raw) is bytes and 0 < len(raw) <= 1048576, 'response-bound')
        return json.loads(raw)

    def install(self):
        self.receipt = self.call('install')
        return self.call('startup')

    def restore(self):
        if self.receipt is not None and not self.restored:
            value = self.call('restore')
            require(value.get('restored') is True, 'restoration')
            self.restored = True
            return value


if __name__ == '__main__':
    require(len(sys.argv) == 4 and sys.argv[1] in ('install', 'startup', 'verify-refusal', 'restore'), 'arguments')
    print(json.dumps(guest_operation(sys.argv[1], sys.argv[2], json.loads(sys.argv[3])), sort_keys=True))
