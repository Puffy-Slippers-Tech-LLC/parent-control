"""Bounded engineering capture alongside the unchanged retained-unlock check.

The foreground controller retains the lease. A separate command owner reads the
child bus while GDM input continues; no capture result supplies acceptance.
Timestamps mark callback delivery. Separate bus queues do not establish causal
ordering or precise transition intervals between ScreenSaver, logind and AT-SPI.
"""

import hashlib
import json
import os
from pathlib import Path
import pwd
import threading
import time


def role_category(role, atspi):
    return {int(atspi.Role.DIALOG): 'dialog', int(atspi.Role.ALERT): 'alert',
            int(atspi.Role.PASSWORD_TEXT): 'password'}.get(role, 'other')


def shell_baseline(api, owner, atspi):
    """Read only structure, roles and states before the old objects disappear."""
    from public_atspi import ROOT, LIMIT
    pending, roles, interesting = [ROOT], {}, []
    deadline = time.monotonic() + 10
    while pending:
        if len(roles) >= LIMIT or time.monotonic() >= deadline:
            raise RuntimeError('capture:baseline-bound')
        path = pending.pop()
        if path in roles:
            raise RuntimeError('capture:baseline-duplicate')
        role = role_category(api.call(owner, path, 'org.a11y.atspi.Accessible', 'GetRole'), atspi)
        roles[path] = role
        words = api.call(owner, path, 'org.a11y.atspi.Accessible', 'GetState')
        if len(words) != 2 or any(type(word) is not int for word in words):
            raise RuntimeError('capture:baseline-state')
        bits = words[0] | words[1] << 32
        state = {name: bool(bits & 1 << int(value)) for name, value in (
            ('modal', atspi.StateType.MODAL), ('showing', atspi.StateType.SHOWING),
            ('visible', atspi.StateType.VISIBLE))}
        if state['modal'] or role != 'other':
            interesting.append({'source_sha256': hashlib.sha256((owner + path).encode()).hexdigest(),
                                'role': role, **state})
        children = api.call(owner, path, 'org.a11y.atspi.Accessible', 'GetChildren')
        if len(children) + len(pending) + len(roles) > LIMIT or any(bus != owner for bus, _path in children):
            raise RuntimeError('capture:baseline-scope')
        pending.extend(path for _bus, path in children)
    return roles, interesting


def capture_guest(control, boot):
    """Read lock/modal transitions as the pinned, initially inactive child."""
    def require(value):
        if not value:
            raise RuntimeError('capture:identity-or-bound')

    boot_digest = lambda: hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
    require(os.geteuid() == 0 and boot_digest() == boot)
    account = pwd.getpwnam(control.ACCOUNTS['child'])
    source, target = control.locked_entry_source(control.sessions(), account.pw_uid)
    identity = hashlib.sha256(json.dumps([source, target]).encode()).hexdigest()
    environment = control.environment(account)
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ.clear()
    os.environ.update(environment)

    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, Gio, GLib
    from public_atspi import PublicAtspi, ROOT
    Atspi.set_timeout(1000, 2000)
    session = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def call(bus, destination, path, interface, method, signature='', arguments=()):
        return bus.call_sync(destination, path, interface, method,
            GLib.Variant('(' + signature + ')', arguments) if signature else None,
            None, Gio.DBusCallFlags.NO_AUTO_START, 1000, None).unpack()

    def dbus(bus, method, name):
        return call(bus, 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                    'org.freedesktop.DBus', method, 's', (name,))[0]

    shell_owner = dbus(session, 'GetNameOwner', 'org.gnome.Shell')
    shell_pid = dbus(session, 'GetConnectionUnixProcessID', shell_owner)
    process = Path('/proc') / str(shell_pid)
    birth = (process / 'stat').read_text().rpartition(') ')[2].split()[19]

    def guard():
        require(boot_digest() == boot and process.stat().st_uid == account.pw_uid
            and (process / 'stat').read_text().rpartition(') ')[2].split()[19] == birth
            and dbus(session, 'GetNameOwner', 'org.gnome.Shell') == shell_owner)

    session_path = call(system, 'org.freedesktop.login1', '/org/freedesktop/login1',
        'org.freedesktop.login1.Manager', 'GetSession', 's', (source,))[0]
    started = time.monotonic_ns()
    count = 0
    failed = []

    def emit(event, **fields):
        nonlocal count
        require(count < 512)
        count += 1
        print(json.dumps({'event': event, 'monotonic_ns': time.monotonic_ns(),
                          **fields}, sort_keys=True), flush=True)

    def callback(function):
        def receive(*args):
            try:
                function(*args)
            except Exception:
                failed.append(True)
        return receive

    @callback
    def lock_changed(_bus, _sender, _path, _interface, _signal, parameters, *_unused):
        active, = parameters.unpack()
        require(type(active) is bool)
        emit('screensaver', active=active)

    @callback
    def session_changed(_bus, _sender, _path, _interface, _signal, parameters, *_unused):
        interface, changed, invalidated = parameters.unpack()
        if interface == 'org.freedesktop.login1.Session':
            for name in ('Active', 'LockedHint'):
                if name in changed:
                    require(type(changed[name]) is bool)
                    emit('session', property=name, value=changed[name])
                elif name in invalidated:
                    emit('session-invalidated', property=name)

    # Subscribe only to state events. Never read names, Text, password values,
    # arbitrary event payloads, or keystrokes, even for diagnostic output.
    api = PublicAtspi(Atspi)
    children = api.call('org.a11y.atspi.Registry', ROOT,
                        'org.a11y.atspi.Accessible', 'GetChildren')
    owners = [bus for bus, _path in children if api.call('org.freedesktop.DBus',
        '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'GetConnectionUnixProcessID',
        's', (bus,)) == shell_pid]
    require(len(owners) == 1)
    shell_a11y = owners[0]
    baseline_roles = {}

    @callback
    def state_changed(path, detail, value, error):
        require(error is None)
        resolution, role_error = 'live', None
        try:
            role = api.call(shell_a11y, path, 'org.a11y.atspi.Accessible', 'GetRole')
            category = role_category(role, Atspi)
        except GLib.Error as exception:
            name = Gio.DBusError.get_remote_error(exception)
            role_error = { 'org.freedesktop.DBus.Error.UnknownObject': 'retired',
                'org.freedesktop.DBus.Error.UnknownMethod': 'unsupported-method',
                'org.freedesktop.DBus.Error.UnknownInterface': 'unsupported-interface',
                'org.freedesktop.DBus.Error.AccessDenied': 'denied'}.get(name, 'other')
            # Historical roles annotate evidence only. They never authorize
            # input or make a disappeared object count as a current dialog.
            category = baseline_roles.get(path, 'unavailable') if role_error == 'retired' else 'unavailable'
            resolution = 'baseline' if category != 'unavailable' else 'unavailable'
        if detail == 'modal' or category != 'other':
            emit('shell-state', state=detail, value=value, role=category,
                 role_resolution=resolution, role_error=role_error,
                 source_sha256=hashlib.sha256((shell_a11y + path).encode()).hexdigest())

    subscriptions = [
        (session, session.signal_subscribe(shell_owner, 'org.gnome.ScreenSaver', 'ActiveChanged',
            '/org/gnome/ScreenSaver', None, Gio.DBusSignalFlags.NONE, lock_changed)),
        (system, system.signal_subscribe('org.freedesktop.login1',
            'org.freedesktop.DBus.Properties', 'PropertiesChanged', session_path,
            'org.freedesktop.login1.Session', Gio.DBusSignalFlags.NONE, session_changed)),
    ]
    try:
        with api.application_state_events(shell_a11y, state_changed,
                states=('modal', 'showing', 'visible')) as context:
            baseline_roles, baseline = shell_baseline(api, shell_a11y, Atspi)
            emit('shell-baseline', nodes=len(baseline_roles), objects=baseline)
            guard()
            active, = call(session, shell_owner, '/org/gnome/ScreenSaver',
                           'org.gnome.ScreenSaver', 'GetActive')
            require(active is True)
            props, = call(system, 'org.freedesktop.login1', session_path,
                'org.freedesktop.DBus.Properties', 'GetAll', 's', ('org.freedesktop.login1.Session',))
            require(props['Active'] is False and props['LockedHint'] is True
                    and props['User'][0] == account.pw_uid)
            emit('ready', boot_sha256=boot, session_sha256=identity,
                 screensaver_active=active, session_active=False, locked_hint=True)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and not failed:
                for current in (context, GLib.MainContext.default()):
                    # Finite dispatch: an event storm cannot extend the bound.
                    for _ in range(32):
                        if not current.pending():
                            break
                        current.iteration(False)
                time.sleep(.01)
            guard()
            require(not failed)
            props, = call(system, 'org.freedesktop.login1', session_path,
                'org.freedesktop.DBus.Properties', 'GetAll', 's', ('org.freedesktop.login1.Session',))
            require(props['User'][0] == account.pw_uid and props['Seat'][0] == 'seat0'
                    and props['Type'] == target['Type'] and props['Class'] == target['Class'])
            emit('finished', duration_ms=(time.monotonic_ns() - started) // 1000000)
    finally:
        for bus, subscription in subscriptions:
            bus.signal_unsubscribe(subscription)
        api.reset()


class Capture:
    def __init__(self, lease, transport, directory):
        self.lease, self.transport, self.directory = lease, transport, directory
        self.thread = None
        self.ready = threading.Event()
        self.done = threading.Event()
        self.error = None
        self.rows = []

    def start(self, boot):
        from owned_commands import Commands
        from vm_transport import Transport
        import system_runner as system

        system.require(self.thread is None and isinstance(boot, str)
            and len(boot) == 64 and all(c in '0123456789abcdef' for c in boot), 'capture:start')
        self.lease.guard()
        private = self.directory / 'unlock-capture'
        private.mkdir(mode=0o700)
        commands = Commands()
        commands.directory = private
        commands.lock_fd = self.transport.commands.lock_fd
        # The capture owns its command files and return status. Its sole lease
        # check runs before readiness, while the foreground waits; it never
        # races the journey's mutable Commands state or lease checks.
        transport = Transport(dict(self.transport.config), commands, guard=self.transport.guard)
        program = 'import types\ncontrol = types.ModuleType("session_control")\n'
        program += 'exec(' + repr((system.ROOT / 'tests/e2e/session_control.py').read_text()) + ', control.__dict__)\n'
        program += 'public = types.ModuleType("public_atspi")\nsys = __import__("sys")\nsys.modules["public_atspi"] = public\n'
        program += 'exec(' + repr((system.ROOT / 'tests/e2e/public_atspi.py').read_text()) + ', public.__dict__)\n'
        program += Path(__file__).read_text() + '\ncapture_guest(control, ' + repr(boot) + ')\n'
        buffer = bytearray()

        def receive(data, stream):
            if stream != 'stdout':
                return
            buffer.extend(data)
            system.require(len(buffer) <= 262144, 'capture:output-bound')
            while b'\n' in buffer:
                system.require(len(self.rows) < 512, 'capture:output-bound')
                line, _, rest = buffer.partition(b'\n')
                buffer[:] = rest
                row = json.loads(line)
                system.require(type(row) is dict and row.get('event') in (
                    'ready', 'shell-baseline', 'screensaver', 'session', 'session-invalidated', 'shell-state', 'finished')
                    and type(row.get('monotonic_ns')) is int, 'capture:record')
                self.rows.append(row)
                if row['event'] == 'ready':
                    system.require(not self.ready.is_set() and row == {
                        'event': 'ready', 'monotonic_ns': row['monotonic_ns'],
                        'boot_sha256': boot, 'session_sha256': row.get('session_sha256'),
                        'screensaver_active': True, 'session_active': False, 'locked_hint': True}
                        and isinstance(row.get('session_sha256'), str)
                        and len(row['session_sha256']) == 64, 'capture:readiness')
                    self.ready.set()

        def run():
            try:
                transport.call(['/usr/bin/python3', '-I', '-'], input=program.encode(),
                               timeout=75, on_stream=receive)
                system.require(not buffer and self.rows and self.rows[-1]['event'] == 'finished',
                               'capture:incomplete')
            except BaseException as error:
                self.error = type(error).__name__
            finally:
                self.done.set()

        self.thread = threading.Thread(target=run, name='retained-unlock-capture')
        self.thread.start()
        deadline = time.monotonic() + 20
        while not self.ready.is_set() and not self.done.wait(.05):
            system.require(time.monotonic() < deadline, 'capture:ready-timeout')
        system.require(self.ready.is_set() and self.error is None, 'capture:not-ready')
        self.lease.guard()

    def require_active(self):
        import system_runner as system
        system.require(self.ready.is_set() and not self.done.is_set() and self.error is None
            and self.rows[-1]['event'] != 'finished', 'capture:window-ended')

    def close(self):
        if self.thread is None:
            return
        # Commands owns SSH timeout and pidfd cleanup. Never signal a discovered
        # guest/host PID, abandon a thread, or clear the original journey failure.
        self.thread.join()
        (self.directory / 'unlock-transitions.json').write_text(json.dumps(self.rows))
        (self.directory / 'unlock-capture-result.json').write_text(json.dumps({
            'outcome': 'failed' if self.error else 'captured', 'error_type': self.error,
            'ready': self.ready.is_set(), 'records': len(self.rows),
            'timestamp_scope': 'guest-observer-dispatch', 'cross_bus_ordering': 'unproven'}))
        if self.error:
            raise RuntimeError('capture:failed:' + self.error)
