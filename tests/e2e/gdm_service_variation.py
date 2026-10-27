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
ROUTING_VARIATIONS = ('normal', 'alternate-session', 'empty-fields', 'alternate-transport')

# GDM resolves this caller through the greeter user's service manager, as in
# session_control.submit. SelectSession is explicit and does not save defaults.
# No prompt is answered; a challenge is an unsupported passwordless route.
PEER_SELECTION = r'''
import json
import re
import gi
gi.require_version('Gdm', '1.0')
from gi.repository import Gdm, GLib
client = Gdm.Client.new()
greeter = client.get_greeter_sync(None)
verifier = client.get_user_verifier_sync(None)
loop = GLib.MainLoop()
result = {'selected_session': 'oh-no-parent-control', 'selection_acknowledged': False}
def finish(outcome):
    result['result'] = outcome
    loop.quit()
def opened(_greeter, service, session_id):
    if service != 'gdm-password' or not isinstance(session_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', session_id):
        finish('unexpected-service')
        return
    result['opened_session'] = session_id
    greeter.call_start_session_when_ready_sync(service, True, None)
    finish('session-start-requested')
verifier.connect('info-query', lambda *_: finish('unexpected-prompt'))
verifier.connect('secret-info-query', lambda *_: finish('unexpected-prompt'))
verifier.connect('verification-failed', lambda *_: finish('verification-failed'))
greeter.connect('session-opened', opened)
greeter.call_select_session_sync('oh-no-parent-control', None)
result['selection_acknowledged'] = True
verifier.call_begin_verification_for_user_sync('gdm-password', 'oh-no-parent-control', None)
GLib.timeout_add_seconds(90, lambda: finish('timeout'))
if 'result' not in result:
    loop.run()
print(json.dumps(result, sort_keys=True))
'''


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


def guest_context(token, *, routing=False):
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
    name = 'gdm-routing-' + token + '.json' if routing else 'gdm-service-variation.json'
    return guest, marker, private / name


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
    service = state.get('service', 'gdm-autologin')
    deadline = time.monotonic() + 90
    while True:
        rows = [row for row in journal(guest, state) if type(row.get('MESSAGE')) is str]
        workers = [row for row in rows if row.get('_EXE') == WORKER]
        initialized = {row['_PID'] for row in workers if
            'initializing PAM; service=' + service + ' username=' + ACCOUNT + ' seat=seat0'
            in row.get('MESSAGE', '')}
        warned = {row['_PID'] for row in workers if
            'pam_warn(' + service + ':account)' in row.get('MESSAGE', '')
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
        selected = (state.get('independent_selection', {}).get('selection_acknowledged') is True
            and any(row.get('_EXE') in ('/usr/sbin/gdm3', '/usr/bin/gdm')
                    and "GdmSession: selecting session '" + DEDICATED[0] + "'"
                        in row.get('MESSAGE', '') for row in rows))
        # Account refusal precedes resolution of the selected command. The
        # acknowledged peer choice and daemon selection witness identify that
        # route; only a created session can proceed to actual execution proof.
        selection_reached = (bool(refused) and selected) or DEDICATED[0] in resolved
        if invoked and selection_reached and (refused or sessions):
            require(not (refused and sessions), 'conflicting-result')
            return {'route': service, 'worker_executable': WORKER,
                'worker_pid': int(next(iter(invoked))), 'pam_account_observed': True,
                'journal_boot_bound': True, 'journal_cursor_bound': True,
                'result': 'account-refused' if refused else 'session-created',
                'saved_routing_setup_only': state.get('routing_input', DEDICATED),
                'independent_selection_observed': selected,
                'gdm_command_resolution': (DEDICATED[0] + '.desktop'
                                           if DEDICATED[0] in resolved else None),
                'gdm_resolved_desktops': resolved, 'app_execution_qualified': False}
        require(time.monotonic() < deadline, 'invocation-or-result-timeout')
        time.sleep(.5)


def peer_selection(guest):
    """Use the sole active local greeter, outside the remote SSH session."""
    from system_kiosk_confinement import user_command
    deadline = time.monotonic() + 75
    while True:
        found = []
        for line in guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines():
            fields = line.split()
            require(len(fields) >= 4 and re.fullmatch(r'[A-Za-z0-9_-]+', fields[0]), 'session-row')
            # Remote command sessions may retire between list and show. They
            # cannot own this seat and are irrelevant to the greeter binding.
            if fields[3] != 'seat0':
                continue
            raw = guest.run(['loginctl', 'show-session', fields[0], '--no-pager',
                '-p', 'User', '-p', 'Class', '-p', 'Type', '-p', 'Seat', '-p', 'Remote', '-p', 'Active'])
            props = dict(row.split('=', 1) for row in raw.splitlines())
            if props.get('Active') == 'yes' and props.get('Seat') == 'seat0':
                require(props.get('Class') == 'greeter' and props.get('Remote') == 'no'
                        and props.get('Type') == 'wayland' and props.get('User', '').isdecimal(),
                        'greeter-owner')
                found.append((fields[0], pwd.getpwuid(int(props['User']))))
        require(len(found) <= 1, 'greeter-identity')
        if found:
            break
        require(time.monotonic() < deadline, 'greeter-timeout')
        time.sleep(.2)
    require(found[0][1].pw_uid > 0, 'greeter-identity')
    account = found[0][1]
    # Validate the public user-manager connection before submitting one action.
    # GDM can register the greeter before its runtime directory and bus exist.
    runtime = Path('/run/user') / str(account.pw_uid)
    while True:
        try:
            runtime_info = runtime.lstat()
            require(stat.S_ISDIR(runtime_info.st_mode)
                    and runtime_info.st_uid == account.pw_uid, 'greeter-bus')
            bus_info = (runtime / 'bus').lstat()
        except FileNotFoundError:
            require(time.monotonic() < deadline, 'greeter-bus-timeout')
            time.sleep(.2)
            continue
        require(stat.S_ISSOCK(bus_info.st_mode)
                and bus_info.st_uid == account.pw_uid, 'greeter-bus')
        break
    guest.guard()
    raw = user_command(account, ['/usr/bin/systemd-run', '--user', '--quiet', '--collect',
        '--wait', '--pipe', '--service-type=exec', '/usr/bin/python3', '-I', '-'],
        input=PEER_SELECTION.encode(), timeout=110)
    require(len(raw) <= 4096, 'peer-response-bound')
    result = json.loads(raw)
    outcome = result.get('result')
    require(outcome in ('verification-failed', 'session-start-requested',
            'unexpected-service', 'unexpected-prompt', 'timeout'), 'peer-result')
    require(result.get('selected_session') == DEDICATED[0]
            and result.get('selection_acknowledged') is True
            and outcome in ('verification-failed', 'session-start-requested'),
            'peer-selection-or-passwordless-route:' + outcome)
    return result


def attempt(token, *, routing_variation=None):
    require(routing_variation is None or routing_variation in ROUTING_VARIATIONS, 'routing-variation')
    guest, marker, receipt = guest_context(token, routing=routing_variation is not None)
    account = pwd.getpwnam(ACCOUNT)
    require(account.pw_uid > 0 and account.pw_shell == '/usr/sbin/nologin', 'station-account')
    require(not station_sessions(guest, account.pw_uid), 'station-already-active')
    api = accounts()
    user = '/org/freedesktop/Accounts/User' + str(account.pw_uid)
    config = Path('/etc/gdm/custom.conf' if guest.package_path().suffix == '.rpm'
                  else '/etc/gdm3/custom.conf')
    pam = Path('/etc/pam.d/gdm-password') if routing_variation is not None else PAM
    original_config, original_pam = snapshot(config), snapshot(pam)
    require(WARNING not in base64.b64decode(original_pam['bytes']), 'observation-collision')
    require(Path(WORKER).is_file() and Path(WORKER).stat().st_uid == 0, 'worker-executable')
    state = {'run': marker['run'], 'token': token, 'uid': account.pw_uid, 'user': user,
        'boot': Path('/proc/sys/kernel/random/boot_id').read_text(), 'config': str(config),
        'config_original': original_config, 'config_expected': original_config,
        'pam_original': original_pam, 'pam_expected': original_pam,
        'automatic_original': api.automatic(), 'automatic_expected': api.automatic(),
        'routing_original': api.routing(user), 'routing_expected': api.routing(user),
        'restored': False, 'restart_attempted': False, 'pam': str(pam),
        'service': 'gdm-password' if routing_variation is not None else 'gdm-autologin'}
    if routing_variation is not None:
        from system_kiosk_admission import routing_variations
        require(state['routing_original'] == DEDICATED and not state['automatic_original'],
                'routing-baseline')
        state['routing_input'] = list(routing_variations()[routing_variation])
        ordinary = pwd.getpwnam('onpc-parent-jamie')
        require(ordinary.pw_uid > 0 and ordinary.pw_uid != account.pw_uid, 'ordinary-identity')
        state['ordinary'] = ordinary.pw_uid
        state['ordinary_routing'] = api.routing('/org/freedesktop/Accounts/User' + str(ordinary.pw_uid))
    save(receipt, state, create=True)  # Collision refuses before the first mutation.
    try:
        # AccountsService serializes the keyfile and can replace its inode. Its
        # post-call readback becomes the exact owned configuration for cleanup.
        if routing_variation is None:
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
        state['pam_expected'] = replace_owned(pam, state['pam_expected'],
            WARNING + base64.b64decode(original_pam['bytes']))
        save(receipt, state)
        if routing_variation is not None:
            state['restart_attempted'] = True
            save(receipt, state)
            guest.guard()
            guest.run(['systemctl', 'restart', 'display-manager.service'], timeout=60)
            # Vary one input only, after startup and before explicit selection.
            require(api.routing(user) == DEDICATED, 'routing-baseline-changed')
            try:
                api.set_routing(user, state['routing_input'])
            finally:
                state['routing_expected'] = api.routing(user)
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
        if routing_variation is None:
            guest.run(['systemctl', 'restart', 'display-manager.service'], timeout=60)
            return observe_attempt(guest, state)
        require(api.routing(user) == state['routing_input'], 'routing-input-changed')
        selected = peer_selection(guest)
        state['independent_selection'] = selected
        save(receipt, state)
        result = observe_attempt(guest, state)
        messages = [row['MESSAGE'] for row in journal(guest, state)
                    if type(row.get('MESSAGE')) is str
                    and row['MESSAGE'].startswith('onpc.pam kiosk routing stage=account ')]
        expected = 'onpc.pam kiosk routing stage=account outcome=denied recovery=restored reason=routing'
        allowed = 'onpc.pam kiosk routing stage=account outcome=allowed recovery=none reason=none'
        require(messages == [expected] if result['result'] == 'account-refused' else
                messages in ([], [allowed]), 'routing-admission-witness')
        # Only this witnessed product repair may change the expected cleanup
        # value; an unexplained or foreign routing change is never adopted.
        current = api.routing(user)
        require(current == DEDICATED if result['result'] == 'account-refused' else
                current in (state['routing_input'], DEDICATED), 'routing-product-recovery')
        state['routing_expected'] = current
        save(receipt, state)
        result.update(variation=routing_variation, independent_selection=selected,
            routing_input=state['routing_input'], admission_witness=messages,
            routing_repaired=result['result'] == 'account-refused')
        return result
    except BaseException:
        # The host always runs guarded restore, including on a failed attempt.
        # Preserve the receipt and original error; never repeat uncertain input.
        raise


def execution(token, *, routing=False):
    """Actual logind and running selected-process evidence after the public form."""
    guest, marker, receipt = guest_context(token, routing=routing)
    state = load(receipt, marker, token)
    account = pwd.getpwnam(ACCOUNT)
    require(account.pw_uid == state['uid'], 'station-replaced')
    sessions = station_sessions(guest, account.pw_uid)
    if routing:
        require(len(sessions) == 1 and sessions[0][0] ==
                state['independent_selection'].get('opened_session'), 'selected-session-identity')
    require(len(sessions) == 1 and sessions[0][1] == {
        'User': str(account.pw_uid), 'Service': state.get('service', 'gdm-autologin'), 'Type': 'wayland',
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


def restore(token, *, routing=False):
    guest, marker, receipt = guest_context(token, routing=routing)
    if not receipt.exists() and not receipt.is_symlink():
        return {'restored': True, 'attempt_started': False}
    state = load(receipt, marker, token)
    require(not state['restored'], 'already-restored')
    config = Path(state['config'])
    pam = Path(state.get('pam', str(PAM)))
    require(pam == (Path('/etc/pam.d/gdm-password') if routing else PAM), 'receipt-pam')
    api = accounts()
    if routing and api.routing(state['user']) != state['routing_expected']:
        # A failed controller observation can still follow a completed product
        # repair. Adopt only this attempt's exact denied/restored witness.
        messages = [row.get('MESSAGE') for row in journal(guest, state)
                    if type(row.get('MESSAGE')) is str and
                    row['MESSAGE'].startswith('onpc.pam kiosk routing stage=account ')]
        repaired = messages == ['onpc.pam kiosk routing stage=account outcome=denied '
                                'recovery=restored reason=routing']
        selected = (state.get('independent_selection', {}).get('selection_acknowledged') is True
                    and messages in ([], ['onpc.pam kiosk routing stage=account outcome=allowed '
                                         'recovery=none reason=none']))
        require(state['routing_input'] != DEDICATED and api.routing(state['user']) == DEDICATED
                and (repaired or selected), 'restore-unwitnessed-routing')
        state['routing_expected'] = DEDICATED
        save(receipt, state)
    # Audit all resources before any restoration mutation; preserve a foreign
    # replacement rather than partially hiding a changed attempt boundary.
    require(snapshot(config) == state['config_expected']
            and snapshot(pam) == state['pam_expected']
            and api.automatic() == state['automatic_expected']
            and api.routing(state['user']) == state['routing_expected'], 'restore-state-changed')
    require(pwd.getpwnam(ACCOUNT).pw_uid == state['uid'], 'station-replaced')
    if routing:
        require(pwd.getpwnam('onpc-parent-jamie').pw_uid == state['ordinary']
                and api.routing('/org/freedesktop/Accounts/User' + str(state['ordinary']))
                    == state['ordinary_routing'], 'ordinary-routing-changed')
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
    replace_owned(pam, state['pam_expected'], base64.b64decode(state['pam_original']['bytes']))
    current = replace_owned(config, state['config_expected'],
                            base64.b64decode(state['config_original']['bytes']))
    # AccountsService may have replaced the inode, but original bytes and all
    # ownership/mode metadata must be identical after restoration.
    require(current['bytes'] == state['config_original']['bytes']
            and current['identity'][2:] == state['config_original']['identity'][2:]
            and snapshot(pam) == state['pam_original']
            and api.routing(state['user']) == state['routing_original']
            and api.automatic() == state['automatic_original'], 'restore-readback')
    guest.guard()
    guest.run(['systemctl', 'restart', 'display-manager.service'], timeout=60)
    require(snapshot(config) == current and snapshot(pam) == state['pam_original']
            and api.routing(state['user']) == state['routing_original']
            and api.automatic() == state['automatic_original'], 'restore-restart-readback')
    if routing:
        require(api.routing('/org/freedesktop/Accounts/User' + str(state['ordinary']))
                == state['ordinary_routing'], 'ordinary-routing-changed')
    state['restored'] = True
    save(receipt, state)
    return {'restored': True, 'attempt_started': True, 'configuration_exact': True,
            'pam_exact': True, 'automatic_account_exact': True, 'routing_exact': True}


def outage(token, *, restore_only=False, positive=False):
    """One actual AccountsService loss; only its owned runtime mask is removed."""
    guest, marker, receipt = guest_context(token, routing=True)
    from system_kiosk_admission import routing, routing_outage_probe
    mask = Path('/run/systemd/system/accounts-daemon.service')

    def unit():
        raw = guest.run(['systemctl', 'show', 'accounts-daemon.service', '--no-pager',
            '-p', 'LoadState', '-p', 'ActiveState', '-p', 'SubState',
            '-p', 'FragmentPath', '-p', 'DropInPaths', '-p', 'UnitFileState'])
        return dict(line.split('=', 1) for line in raw.splitlines())

    def mask_identity():
        info = mask.lstat()
        require(stat.S_ISLNK(info.st_mode) and info.st_uid == info.st_gid == 0
                and info.st_nlink == 1 and os.readlink(mask) == '/dev/null', 'outage-mask')
        return identity(info)

    if restore_only:
        if not receipt.exists() and not receipt.is_symlink():
            return {'restored': True, 'attempt_started': False}
        state = load(receipt, marker, token)
        require(not state['restored'], 'already-restored')
        require(pwd.getpwnam(ACCOUNT).pw_uid == state['uid']
                and pwd.getpwnam('onpc-parent-jamie').pw_uid == state['ordinary'],
                'outage-account-changed')
        if state['mask'] is not None:
            require(mask_identity() == state['mask']
                    and unit() == state['unit_expected']
                    and snapshot(Path(state['unit_original']['FragmentPath'])) == state['fragment']
                    and all(snapshot(Path(path)) == saved for path, saved in state['dropins'].items()),
                    'outage-restore-changed')
            mask.unlink()
            state['mask'] = None
            state['mask_removed'] = True
            save(receipt, state)
        if state['mask_removed']:
            require(not mask.exists() and not mask.is_symlink()
                    and unit() == state['unit_expected']
                    and snapshot(Path(state['unit_original']['FragmentPath'])) == state['fragment']
                    and all(snapshot(Path(path)) == saved for path, saved in state['dropins'].items()),
                    'outage-restore-changed')
            guest.run(['systemctl', 'daemon-reload'], timeout=30)
            state['unit_expected'] = unit()
            save(receipt, state)
            try:
                guest.run(['systemctl', 'start', 'accounts-daemon.service'], timeout=30)
            finally:
                state['unit_expected'] = unit()
                save(receipt, state)
        require(not mask.exists() and not mask.is_symlink()
                and unit() == state['unit_original']
                and list(routing(state['uid'])) == state['routing_original']
                and list(routing(state['ordinary'])) == state['ordinary_routing'],
                'outage-restoration-readback')
        state['restored'] = True
        save(receipt, state)
        return {'restored': True, 'service_state_exact': True, 'runtime_mask_removed': True,
                'routing_exact': True, 'ordinary_routing_exact': True}
    original = unit()
    require(original.get('LoadState') == 'loaded' and original.get('ActiveState') == 'active'
            and original.get('SubState') == 'running'
            and original.get('UnitFileState') not in ('masked', 'masked-runtime')
            and original.get('FragmentPath', '') in (
                '/usr/lib/systemd/system/accounts-daemon.service',
                '/lib/systemd/system/accounts-daemon.service')
            and not mask.exists() and not mask.is_symlink(), 'outage-service-baseline')
    parent = mask.parent.lstat()
    require(mask.parent.resolve() == mask.parent and stat.S_ISDIR(parent.st_mode)
            and parent.st_uid == parent.st_gid == 0 and not parent.st_mode & 0o022,
            'outage-mask-parent')
    kiosk, ordinary = pwd.getpwnam(ACCOUNT), pwd.getpwnam('onpc-parent-jamie')
    require(kiosk.pw_uid > 0 and ordinary.pw_uid > 0 and kiosk.pw_uid != ordinary.pw_uid
            and list(routing(kiosk.pw_uid)) == DEDICATED, 'outage-account-baseline')
    latest = json.loads(guest.run(['journalctl', '--no-pager', '--lines=1', '--output=json']))
    state = {'run': marker['run'], 'token': token,
        'boot': Path('/proc/sys/kernel/random/boot_id').read_text(), 'cursor': latest['__CURSOR'],
        'uid': kiosk.pw_uid, 'ordinary': ordinary.pw_uid, 'routing_original': DEDICATED,
        'ordinary_routing': list(routing(ordinary.pw_uid)), 'unit_original': original,
        'unit_expected': original, 'fragment': snapshot(Path(original['FragmentPath'])),
        'dropins': {path: snapshot(Path(path)) for path in original['DropInPaths'].split()},
        'mask': None, 'mask_removed': False, 'restored': False}
    save(receipt, state, create=True)
    # Exclusive creation cannot overwrite a pre-existing or foreign mask.
    os.symlink('/dev/null', mask)
    state['mask'] = mask_identity()
    save(receipt, state)
    try:
        guest.run(['systemctl', 'daemon-reload'], timeout=30)
        guest.run(['systemctl', 'stop', 'accounts-daemon.service'], timeout=30)
    finally:
        state['unit_expected'] = unit()
        save(receipt, state)
    require(state['unit_expected']['LoadState'] == 'masked'
            and state['unit_expected']['ActiveState'] == 'inactive', 'outage-not-established')
    records = []
    routing_outage_probe(lambda stage, result: records.append({'stage': stage, 'result': result}),
                         expected=0 if positive else 4)
    messages = [row.get('MESSAGE') for row in journal(guest, state)
                if type(row.get('MESSAGE')) is str and
                row['MESSAGE'].startswith('onpc.pam kiosk routing stage=account ')]
    require(messages == [] if positive else messages == [
            'onpc.pam kiosk routing stage=account outcome=unavailable '
            'recovery=none reason=account-service'], 'outage-helper-outcome')
    require(mask_identity() == state['mask'] and unit() == state['unit_expected'],
            'outage-state-changed')
    return {'result': 'routing-discovery-independent' if positive else 'routing-discovery-unavailable',
            'installed_pam': records, 'helper_unavailable_observed': not positive,
            'app_execution_qualified': False}


def qualify_routing(transport, lease, *, expectation='refusal'):
    """Finite D00a3q binding; D00a3 reuses it with expectation='execution'."""
    import watch_activity
    from ui_observations import UiObservations
    require(expectation in ('refusal', 'execution'), 'routing-expectation')
    program = Path(__file__).read_bytes()

    def remote(operation, token):
        lease.guard()
        raw = transport.call(['env', 'ONPC_EXPECTED_RUN=' + lease.state['run'],
            '/usr/bin/python3', '-I', '-', operation, token], input=program, timeout=360)
        require(type(raw) is bytes and 0 < len(raw) <= 65536, 'response-bound')
        return json.loads(raw)

    results = []
    for variation in ROUTING_VARIATIONS:
        # Restoration starts a fresh greeter. Let its public account list
        # become usable before the next debug-enabled restart, rather than
        # interrupting startup with consecutive display-manager restarts.
        ui = UiObservations(transport)
        ui.boot_guard = hashlib.sha256(transport.call(
            ['cat', '/proc/sys/kernel/random/boot_id'], timeout=15)).hexdigest()
        baseline = ui.observe('gdm-station-list')
        token = secrets.token_hex(16)
        result = None
        try:
            with watch_activity.operation('Qualifying dedicated GDM selection: ' + variation):
                result = remote('routing-' + variation, token)
            if result['result'] == 'session-created':
                ui = UiObservations(transport)
                ui.boot_guard = hashlib.sha256(transport.call(
                    ['cat', '/proc/sys/kernel/random/boot_id'], timeout=15)).hexdigest()
                result['public_observations'] = [ui.observe(operation) for operation in
                    ('station-default-entry', 'kiosk-request-form')]
                result['execution'] = remote('routing-execution', token)
                result['app_execution_qualified'] = True
        finally:
            with watch_activity.operation('Restoring the owned saved-routing variation'):
                restored = remote('routing-restore', token)
            require(restored.get('restored') is True, 'restoration-failed')
        result['restoration'] = restored
        result['public_baseline'] = baseline
        results.append(result)
        if variation == 'normal' and result['result'] != 'session-created':
            return {'qualified': False, 'result': 'normal-execution-not-reached',
                    'expectation': expectation, 'normal_execution': result,
                    'controls': [], 'discovery_outage': None}
    token = secrets.token_hex(16)
    # The preceding restoration restarts GDM. Establish a usable public
    # greeter before taking discovery away; otherwise this also interrupts
    # greeter startup rather than varying one service in a valid baseline.
    ui = UiObservations(transport)
    ui.boot_guard = hashlib.sha256(transport.call(
        ['cat', '/proc/sys/kernel/random/boot_id'], timeout=15)).hexdigest()
    baseline = ui.observe('gdm-station-list')
    try:
        with watch_activity.operation('Qualifying actual installed routing-discovery loss'):
            discovery = remote('routing-outage-positive' if expectation == 'execution' else
                               'routing-outage', token)
    finally:
        with watch_activity.operation('Restoring the owned AccountsService routing discovery'):
            restored = remote('routing-outage-restore', token)
        require(restored.get('restored') is True, 'restoration-failed')
    discovery['restoration'] = restored
    discovery['public_baseline'] = baseline
    normal, *variations = results
    expected = 'account-refused' if expectation == 'refusal' else 'session-created'
    qualified = (normal['result'] == 'session-created'
                 and normal['app_execution_qualified'] is True
                 and all(item['result'] == expected and
                         item['app_execution_qualified'] is (expectation == 'execution')
                         for item in variations))
    return {'qualified': qualified, 'result': 'routing-qualified' if qualified else
            'routing-outcome-mismatch', 'expectation': expectation,
            'normal_execution': normal, 'controls': variations, 'discovery_outage': discovery}


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
        operations = {'attempt': attempt, 'execution': execution, 'restore': restore,
            'routing-execution': lambda token: execution(token, routing=True),
            'routing-restore': lambda token: restore(token, routing=True),
            'routing-outage': outage,
            'routing-outage-positive': lambda token: outage(token, positive=True),
            'routing-outage-restore': lambda token: outage(token, restore_only=True)}
        operations.update({'routing-' + variation:
            lambda token, variation=variation: attempt(token, routing_variation=variation)
            for variation in ROUTING_VARIATIONS})
        require(len(sys.argv) == 3 and sys.argv[1] in operations, 'arguments')
        print(json.dumps(operations[sys.argv[1]](sys.argv[2]), sort_keys=True))
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
