"""One real gdm-autologin attempt in the caller's installed VM envelope.

The guest half is streamed on stdin. Its receipt stays under the existing
attempt payload; it never allocates host storage or changes a product gate.
Refusal qualifies only the invoked route, never selected app execution.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import stat
import sys
import time


ACCOUNT = 'oh-no-parent-control'
INTERFACE = 'org.freedesktop.Accounts.User'
DEDICATED = ['oh-no-parent-control', 'wayland']
PAM = Path('/etc/pam.d/gdm-autologin')
WORKER = '/usr/libexec/gdm-session-worker'
WARNING = b'# onpc service-variation observation only\naccount optional pam_warn.so\n'


def require(value, code):
    if not value:
        raise RuntimeError('gdm-variation:' + code)


def identity(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid,
            info.st_gid, info.st_nlink]


def snapshot(path):
    """Pin ordinary root-owned files and retain their exact bytes/metadata."""
    for parent in path.parents:
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
                and (not info.st_mode & 0o022 or info.st_mode & stat.S_ISVTX),
                'unsafe-parent')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 0
                and before.st_nlink == 1 and not before.st_mode & 0o022
                and before.st_size <= 65536, 'unsafe-file')
        contents = stream.read(65537)
        require(len(contents) <= 65536 and identity(before) == identity(path.lstat())
                == identity(os.fstat(stream.fileno()))
                and before.st_mtime_ns == os.fstat(stream.fileno()).st_mtime_ns,
                'file-changed')
    return {'identity': identity(before), 'bytes': base64.b64encode(contents).decode()}


def replace_owned(path, expected, contents):
    """Never overwrite a foreign/replaced/edited configuration during cleanup."""
    require(snapshot(path) == expected, 'configuration-changed')
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'r+b') as stream:
        require(identity(os.fstat(stream.fileno())) == expected['identity']
                and stream.read() == base64.b64decode(expected['bytes'])
                and identity(path.lstat()) == expected['identity'], 'configuration-changed')
        stream.seek(0)
        stream.write(contents)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    current = snapshot(path)
    require(current['identity'] == expected['identity']
            and base64.b64decode(current['bytes']) == contents, 'configuration-readback')
    return current


def debug_config(contents):
    """Enable only GDM's existing debug section, keeping other text opaque."""
    text = contents.decode('utf-8')
    sections = list(re.finditer(r'^\[([^\]\n]+)\][ \t]*$', text, re.MULTILINE))
    debug = [index for index, section in enumerate(sections) if section[1] == 'debug']
    require(len(debug) == 1, 'debug-section')
    index = debug[0]
    start = sections[index].end()
    end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
    section = text[start:end]
    keys = list(re.finditer(r'^[ \t]*Enable[ \t]*=.*$', section, re.MULTILINE))
    require(len(keys) <= 1, 'debug-key')
    if keys:
        key = keys[0]
        section = section[:key.start()] + 'Enable=true' + section[key.end():]
    else:
        section = '\nEnable=true\n' + section.lstrip('\n')
    return (text[:start] + section + text[end:]).encode()


def accounts():
    from gi.repository import Gio, GLib
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def call(path, interface, method, signature, values, reply):
        return connection.call_sync('org.freedesktop.Accounts', path, interface,
            method, GLib.Variant(signature, values), GLib.VariantType.new(reply),
            Gio.DBusCallFlags.NONE, 15000, None).unpack()

    class Accounts:
        def automatic(self):
            users = call('/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
                         'ListCachedUsers', '()', (), '(ao)')[0]
            require(isinstance(users, list) and len(users) <= 64 and all(
                re.fullmatch(r'/org/freedesktop/Accounts/User[0-9]+', item)
                for item in users), 'cached-users')
            value = [user for user in users if call(user, 'org.freedesktop.DBus.Properties',
                'Get', '(ss)', (INTERFACE, 'AutomaticLogin'), '(v)')[0] is True]
            require(len(value) <= 1, 'automatic-users')
            return value

        def routing(self, path):
            values = call(path, 'org.freedesktop.DBus.Properties', 'GetAll',
                          '(s)', (INTERFACE,), '(a{sv})')[0]
            require(all(type(values.get(key)) is str for key in ('Session', 'SessionType')),
                    'routing-properties')
            return [values['Session'], values['SessionType']]

        def set_routing(self, path, values):
            for method, value in zip(('SetSession', 'SetSessionType'), values):
                call(path, INTERFACE, method, '(s)', (value,), '()')
            require(self.routing(path) == values, 'routing-readback')

        def set_automatic(self, path, enabled):
            call(path, INTERFACE, 'SetAutomaticLogin', '(b)', (enabled,), '()')
            deadline = time.monotonic() + 10
            while self.automatic() != ([path] if enabled else []):
                require(time.monotonic() < deadline, 'automatic-readback-timeout')
                time.sleep(.1)

    return Accounts()


def guest_context(token):
    # The installed setup owns these verified guest helpers and the payload.
    sys.path.insert(0, '/var/tmp/onpc-system-input')
    import system_guest as guest
    marker = guest.guard()
    require(re.fullmatch(r'[0-9a-f]{32}', token) is not None, 'token')
    guest.enable_diagnostics()
    private = guest.PAYLOAD / 'private'
    info = private.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0
            and stat.S_IMODE(info.st_mode) == 0o700, 'private-directory')
    return guest, marker, private / 'gdm-service-variation.json'


def save(path, state, *, create=False):
    flags = os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    flags |= os.O_CREAT | os.O_EXCL if create else 0
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
                and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600,
                'receipt-identity')
        stream.write(json.dumps(state, sort_keys=True).encode())
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())


def load(path, marker, token):
    state = json.loads(base64.b64decode(snapshot(path)['bytes']))
    require(state['run'] == marker['run'] and state['token'] == token
            and state['boot'] == Path('/proc/sys/kernel/random/boot_id').read_text(),
            'receipt-binding')
    return state


def journal(guest, state):
    raw = guest.run(['journalctl', '--no-pager', '--boot=' + state['boot'].strip().replace('-', ''),
                     '--after-cursor=' + state['cursor'], '--output=json', '--lines=3000'],
                    timeout=15)
    require(len(raw) <= 4 * 1024 * 1024, 'journal-bound')
    rows = [json.loads(line) for line in raw.splitlines()]
    require(len(rows) < 3000 and all(row.get('_BOOT_ID') ==
            state['boot'].strip().replace('-', '') for row in rows), 'journal-window')
    return rows


def station_sessions(guest, uid):
    result = []
    for line in guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines():
        fields = line.split()
        require(len(fields) >= 2 and re.fullmatch(r'[A-Za-z0-9_-]+', fields[0]), 'session-row')
        if fields[1] != str(uid):
            continue
        raw = guest.run(['loginctl', 'show-session', fields[0], '--no-pager',
            '-p', 'User', '-p', 'Service', '-p', 'Type', '-p', 'Class', '-p', 'State',
            '-p', 'Seat', '-p', 'Active'])
        props = dict(row.split('=', 1) for row in raw.splitlines())
        if props['Class'] in ('manager', 'manager-early') and props['Service'] == 'systemd-user':
            continue
        result.append((fields[0], props))
    require(len(result) <= 1, 'ambiguous-station-session')
    return result


def observe_attempt(guest, state):
    deadline = time.monotonic() + 90
    while True:
        rows = [row for row in journal(guest, state) if type(row.get('MESSAGE')) is str]
        workers = [row for row in rows if row.get('_EXE') == WORKER]
        initialized = {row['_PID'] for row in workers if
            'initializing PAM; service=gdm-autologin username=' + ACCOUNT + ' seat=seat0'
            in row.get('MESSAGE', '')}
        warned = {row['_PID'] for row in workers if
            'pam_warn(gdm-autologin:account)' in row.get('MESSAGE', '')
            and 'user=[' + ACCOUNT + ']' in row.get('MESSAGE', '')}
        require(len(initialized) <= 1 and len(warned) <= 1, 'multiple-invocations')
        invoked = initialized & warned
        refused = {row['_PID'] for row in workers if
            'GdmSessionWorker: user is not authorized to log in: Permission denied'
            in row.get('MESSAGE', '')} & invoked
        sessions = station_sessions(guest, state['uid'])
        # Resolution logs are useful but are deliberately not called execution.
        resolved = sorted({match[1] for row in rows for match in [re.search(
            r"getting session command for file '([A-Za-z0-9_-]+)\.desktop'",
            row.get('MESSAGE', ''))] if match and row.get('_EXE') in
            ('/usr/sbin/gdm3', '/usr/bin/gdm', WORKER)})
        if invoked and DEDICATED[0] in resolved and (refused or sessions):
            require(not (refused and sessions), 'conflicting-result')
            return {'route': 'gdm-autologin', 'worker_executable': WORKER,
                'worker_pid': int(next(iter(invoked))), 'pam_account_observed': True,
                'journal_boot_bound': True, 'journal_cursor_bound': True,
                'result': 'account-refused' if refused else 'session-created',
                'saved_routing_setup_only': DEDICATED,
                'gdm_command_resolution': DEDICATED[0] + '.desktop',
                'gdm_resolved_desktops': resolved, 'app_execution_qualified': False}
        require(time.monotonic() < deadline, 'invocation-or-result-timeout')
        time.sleep(.5)


def attempt(token):
    guest, marker, receipt = guest_context(token)
    account = pwd.getpwnam(ACCOUNT)
    require(account.pw_uid > 0 and account.pw_shell == '/usr/sbin/nologin', 'station-account')
    require(not station_sessions(guest, account.pw_uid), 'station-already-active')
    api = accounts()
    user = '/org/freedesktop/Accounts/User' + str(account.pw_uid)
    config = Path('/etc/gdm/custom.conf' if guest.package_path().suffix == '.rpm'
                  else '/etc/gdm3/custom.conf')
    original_config, original_pam = snapshot(config), snapshot(PAM)
    require(WARNING not in base64.b64decode(original_pam['bytes']), 'observation-collision')
    require(Path(WORKER).is_file() and Path(WORKER).stat().st_uid == 0, 'worker-executable')
    state = {'run': marker['run'], 'token': token, 'uid': account.pw_uid, 'user': user,
        'boot': Path('/proc/sys/kernel/random/boot_id').read_text(), 'config': str(config),
        'config_original': original_config, 'config_expected': original_config,
        'pam_original': original_pam, 'pam_expected': original_pam,
        'automatic_original': api.automatic(), 'automatic_expected': api.automatic(),
        'routing_original': api.routing(user), 'routing_expected': api.routing(user),
        'restored': False, 'restart_attempted': False}
    save(receipt, state, create=True)  # Collision refuses before the first mutation.
    try:
        # AccountsService serializes the keyfile and can replace its inode. Its
        # post-call readback becomes the exact owned configuration for cleanup.
        require(snapshot(config) == state['config_expected'], 'configuration-changed')
        try:
            api.set_automatic(user, True)
        finally:
            state['config_expected'] = snapshot(config)
            state['automatic_expected'] = api.automatic()
            save(receipt, state)
        require(state['automatic_expected'] == [user], 'automatic-readback')
        try:
            api.set_routing(user, DEDICATED)
        finally:
            state['routing_expected'] = api.routing(user)
            save(receipt, state)
        state['config_expected'] = replace_owned(config, state['config_expected'],
            debug_config(base64.b64decode(state['config_expected']['bytes'])))
        save(receipt, state)
        state['pam_expected'] = replace_owned(PAM, state['pam_expected'],
            WARNING + base64.b64decode(original_pam['bytes']))
        save(receipt, state)
        latest = json.loads(guest.run(['journalctl', '--no-pager', '--lines=1', '--output=json',
            '--boot=' + state['boot'].strip().replace('-', '')]))
        cursor = latest.get('__CURSOR')
        require(type(cursor) is str and 0 < len(cursor) <= 1024 and '\n' not in cursor,
                'journal-cursor')
        state['cursor'] = cursor
        state['restart_attempted'] = True
        save(receipt, state)
        guest.guard()
        guest.run(['systemctl', 'restart', 'display-manager.service'], timeout=60)
        return observe_attempt(guest, state)
    except BaseException:
        # The host always runs guarded restore, including on a failed attempt.
        # Preserve the receipt and original error; never repeat uncertain input.
        raise


def execution(token):
    """Actual logind and running selected-process evidence after the public form."""
    guest, marker, receipt = guest_context(token)
    state = load(receipt, marker, token)
    account = pwd.getpwnam(ACCOUNT)
    require(account.pw_uid == state['uid'], 'station-replaced')
    sessions = station_sessions(guest, account.pw_uid)
    require(len(sessions) == 1 and sessions[0][1] == {
        'User': str(account.pw_uid), 'Service': 'gdm-autologin', 'Type': 'wayland',
        'Class': 'user', 'State': 'active', 'Seat': 'seat0', 'Active': 'yes'}, 'execution-session')
    from system_kiosk_confinement import process_identity, user_unit, session_target_state
    require(session_target_state(account) == 'active', 'dedicated-target')
    unit = 'oh-no-parent-control-app.service'
    service = user_unit(account, unit)
    require(service['ActiveState'] == 'active' and service['MainPID'].isdecimal()
            and int(service['MainPID']) > 1, 'app-service')
    app = Path('/proc') / service['MainPID']
    before = process_identity(app)
    executable = os.readlink(app / 'exe')
    arguments = (app / 'cmdline').read_bytes().split(b'\0')
    require(before[2] == (str(account.pw_uid),) * 4
            and b'/usr/bin/oh-no-parent-control' in arguments
            and (app / 'cgroup').read_text().strip() == '0::' + service['ControlGroup']
            and Path(executable).stat().st_uid == 0, 'app-process')
    # GNOME 50 runs its selected session in this user-manager service. GDM's
    # wrapper also carries --session in its child argv; a process-name scan
    # mistakes that wrapper for an unexpected session executable.
    manager_unit = 'gnome-session-manager@oh-no-parent-control.service'
    manager = user_unit(account, manager_unit)
    require(manager['ActiveState'] == 'active' and manager['MainPID'].isdecimal()
            and int(manager['MainPID']) > 1, 'selected-session-service')
    process = Path('/proc') / manager['MainPID']
    manager_before = process_identity(process)
    exe = os.readlink(process / 'exe')
    args = (process / 'cmdline').read_bytes().split(b'\0')
    require(Path(exe).name == 'gnome-session-service' and Path(exe).stat().st_uid == 0
            and manager_before[2] == (str(account.pw_uid),) * 4
            and b'--session=oh-no-parent-control' in args
            and (process / 'cgroup').read_text().strip() == '0::' + manager['ControlGroup'],
            'selected-session-process')
    selected = [{'pid': int(manager['MainPID']), 'executable': exe,
                 'session': 'oh-no-parent-control'}]
    require(user_unit(account, manager_unit) == manager
            and process_identity(process) == manager_before
            and user_unit(account, unit) == service
            and process_identity(app) == before
            and station_sessions(guest, account.pw_uid) == sessions, 'execution-changed')
    return {'session': {key.lower(): value for key, value in sessions[0][1].items()
                        if key != 'User'}, 'selected_processes': selected,
            'app': {'executable': executable, 'launcher': '/usr/bin/oh-no-parent-control',
                    'pid': int(service['MainPID']), 'unit': unit},
            'app_execution_qualified': True}


def restore(token):
    guest, marker, receipt = guest_context(token)
    if not receipt.exists() and not receipt.is_symlink():
        return {'restored': True, 'attempt_started': False}
    state = load(receipt, marker, token)
    require(not state['restored'], 'already-restored')
    config = Path(state['config'])
    api = accounts()
    # Audit all resources before any restoration mutation; preserve a foreign
    # replacement rather than partially hiding a changed attempt boundary.
    require(snapshot(config) == state['config_expected']
            and snapshot(PAM) == state['pam_expected']
            and api.automatic() == state['automatic_expected']
            and api.routing(state['user']) == state['routing_expected'], 'restore-state-changed')
    require(pwd.getpwnam(ACCOUNT).pw_uid == state['uid'], 'station-replaced')
    try:
        if api.automatic() != state['automatic_original']:
            if state['automatic_original']:
                api.set_automatic(state['automatic_original'][0], True)
            else:
                api.set_automatic(state['user'], False)
    finally:
        # This call legitimately serializes/replaces the same config again.
        state['config_expected'] = snapshot(config)
        state['automatic_expected'] = api.automatic()
        save(receipt, state)
    require(state['automatic_expected'] == state['automatic_original'], 'restore-automatic')
    api.set_routing(state['user'], state['routing_original'])
    replace_owned(PAM, state['pam_expected'], base64.b64decode(state['pam_original']['bytes']))
    current = replace_owned(config, state['config_expected'],
                            base64.b64decode(state['config_original']['bytes']))
    # AccountsService may have replaced the inode, but original bytes and all
    # ownership/mode metadata must be identical after restoration.
    require(current['bytes'] == state['config_original']['bytes']
            and current['identity'][2:] == state['config_original']['identity'][2:]
            and snapshot(PAM) == state['pam_original']
            and api.routing(state['user']) == state['routing_original']
            and api.automatic() == state['automatic_original'], 'restore-readback')
    guest.guard()
    guest.run(['systemctl', 'restart', 'display-manager.service'], timeout=60)
    require(snapshot(config) == current and snapshot(PAM) == state['pam_original']
            and api.routing(state['user']) == state['routing_original']
            and api.automatic() == state['automatic_original'], 'restore-restart-readback')
    state['restored'] = True
    save(receipt, state)
    return {'restored': True, 'attempt_started': True, 'configuration_exact': True,
            'pam_exact': True, 'automatic_account_exact': True, 'routing_exact': True}


def qualify(transport, lease):
    """Finite controller binding; caller subsequently verifies normal entry."""
    import watch_activity
    from ui_observations import UiObservations
    token = secrets.token_hex(16)
    program = Path(__file__).read_bytes()

    def remote(operation):
        lease.guard()
        raw = transport.call(['env', 'ONPC_EXPECTED_RUN=' + lease.state['run'],
            '/usr/bin/python3', '-I', '-', operation, token], input=program, timeout=210)
        require(type(raw) is bytes and 0 < len(raw) <= 65536, 'response-bound')
        return json.loads(raw)

    result = None
    try:
        with watch_activity.operation('Invoking one real GDM automatic station entry'):
            result = remote('attempt')
        require(result['route'] == 'gdm-autologin' and result['pam_account_observed'] is True
                and result['result'] in ('account-refused', 'session-created'), 'attempt-response')
        result['boot_sha256'] = hashlib.sha256(
            transport.call(['cat', '/proc/sys/kernel/random/boot_id'], timeout=15)).hexdigest()
        result['public_observations'] = []
        if result['result'] == 'session-created':
            ui = UiObservations(transport)
            ui.boot_guard = result['boot_sha256']
            for operation in ('station-default-entry', 'kiosk-request-form'):
                lease.guard()
                result['public_observations'].append(ui.observe(operation))
            with watch_activity.operation('Reading the actual selected GDM station execution'):
                result['execution'] = remote('execution')
            result['app_execution_qualified'] = True
    finally:
        with watch_activity.operation('Restoring the exact GDM service-variation attempt state'):
            restored = remote('restore')
        require(restored.get('restored') is True, 'restoration-failed')
    result['restoration'] = restored
    return result


if __name__ == '__main__':
    try:
        require(len(sys.argv) == 3 and sys.argv[1] in ('attempt', 'execution', 'restore'), 'arguments')
        print(json.dumps({'attempt': attempt, 'execution': execution, 'restore': restore}
                         [sys.argv[1]](sys.argv[2]), sort_keys=True))
    except Exception as error:
        # Fixed categories only. Raw PAM/journal/account/config data is private.
        code = str(error) if type(error) is RuntimeError and str(error).startswith(
            'gdm-variation:') else 'gdm-variation:operation-failed'
        if code == 'gdm-variation:operation-failed':
            import traceback
            location = traceback.extract_tb(error.__traceback__)[-1]
            code += ':' + type(error).__name__ + ':' + location.name + ':' + str(location.lineno)
            if type(error).__name__ in ('CommandError', 'GuestError') and re.fullmatch(
                    r'[a-zA-Z0-9:_-]{1,200}', str(error)):
                code += ':' + str(error)
        print(code, file=sys.stderr)
        sys.exit(1)
