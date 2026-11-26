"""Installed extension recovery from one real Malcontent open-store conflict."""

from contextlib import contextmanager
import os
from pathlib import Path
import pwd
import socket
import struct
import tempfile
import threading
import time

from gi.repository import Gio, GLib

import system_guest as guest
from system_assertions import accepted, call
from system_caller import PersistentCaller
from system_extension_monitor import Shell, UUID
from system_graphical_expiry import TIMER, TIMER_UNIT, child_session, timer_identity, wait_for
from system_session_expiry import LIMITS, identities, installed_manager
from timer_trace_bus import monitor_timer

CHILD, PARENT = TIMER + '.Child', TIMER + '.Parent'
BUSY = CHILD + '.Error.Busy'
DROPIN = Path('/run/systemd/system') / (TIMER_UNIT + '.d') / 'onpc-checkpoint-test.conf'


@contextmanager
def instrument_timer():
    guest.guard()
    with tempfile.TemporaryDirectory(prefix='onpc-checkpoint-', dir='/run') as directory:
        root = Path(directory)
        root.chmod(0o755)
        address = root / 'control'
        library = guest.PAYLOAD / 'usage_checkpoint_gate.so'
        staged = root / 'gate.so'
        staged.write_bytes(library.read_bytes())
        staged.chmod(0o644)
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as listener:
            listener.bind(str(address))
            # The unit has a dedicated UID. The endpoint can only be accepted
            # once and must authenticate as the active timer service process.
            unit_user = guest.run(['systemctl', 'show', TIMER_UNIT, '-p', 'User', '--value'])
            account = pwd.getpwnam(unit_user)
            os.chown(address, 0, account.pw_gid)
            address.chmod(0o660)
            listener.listen(1)
            listener.settimeout(15)
            DROPIN.parent.mkdir(mode=0o755, exist_ok=True)
            with DROPIN.open('x') as stream:
                stream.write(f'[Service]\nEnvironment=LD_PRELOAD={staged}\n'
                             f'Environment=ONPC_CHECKPOINT_SOCKET={address}\n')
            try:
                guest.run(['systemctl', 'daemon-reload'])
                guest.run(['systemctl', 'restart', TIMER_UNIT], timeout=100)
                control, _ = listener.accept()
                with control:
                    control.settimeout(8)
                    daemon = timer_identity()
                    pid, uid, _ = struct.unpack('3i', control.getsockopt(socket.SOL_SOCKET,
                                                  socket.SO_PEERCRED, struct.calcsize('3i')))
                    guest.require(pid == daemon['pid'] and uid == account.pw_uid,
                                  'checkpoint:control-owner')
                    yield control, daemon
            finally:
                DROPIN.unlink()
                guest.run(['systemctl', 'daemon-reload'])
                guest.run(['systemctl', 'restart', TIMER_UNIT], timeout=100)


def bus_identity(connection, method, name=None):
    reply = connection.call_sync(
        'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', method,
        None if name is None else GLib.Variant('(s)', (name,)), None,
        Gio.DBusCallFlags.NONE, 3000, None)
    return reply.unpack()[0]


def shell_senders(shell, uid):
    owner = bus_identity(shell.bus, 'GetNameOwner', 'org.gnome.Shell')
    pid = bus_identity(shell.bus, 'GetConnectionUnixProcessID', owner)
    system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    senders = []
    for name in bus_identity(system, 'ListNames'):
        if not Gio.dbus_is_unique_name(name):
            continue
        try:
            if (bus_identity(system, 'GetConnectionUnixProcessID', name) == pid
                    and bus_identity(system, 'GetConnectionUnixUser', name) == uid):
                senders.append(name)
        except GLib.Error as error:
            if Gio.DBusError.get_remote_error(error) != 'org.freedesktop.DBus.Error.NameHasNoOwner':
                raise
    guest.require(senders and sum(len(name) + 1 for name in senders) < 510,
                  'checkpoint:child-shell-system-connections')
    return senders


def receive(control, event, *, sender=None):
    try:
        packet = control.recv(96).decode('ascii').split()
    except TimeoutError as error:
        raise guest.GuestError(f'checkpoint:gate-timeout-{event}') from error
    guest.require(len(packet) == 3 and packet[0] == event and packet[1].isdecimal(),
                  f'checkpoint:gate-expected-{event}:{packet[:1]}')
    serial, source = int(packet[1]), packet[2]
    guest.require((serial == 0 and source == '-') if sender is None else
                  (serial > 0 and source in sender), f'checkpoint:gate-source-{event}')
    return serial, source


class Trace:
    def __init__(self):
        self.condition = threading.Condition()
        self.rows = []
        self.overflow = False
        self.bus = monitor_timer(self.emit)

    def emit(self, _, **row):
        with self.condition:
            if len(self.rows) < 2048:
                self.rows.append(row)
            else:
                self.overflow = True
            self.condition.notify_all()

    def until(self, match, timeout=8):
        def check():
            return self.overflow or next((row for row in self.rows if match(row)), None)

        with self.condition:
            result = self.condition.wait_for(check, timeout)
            guest.require(not self.overflow and not self.bus.is_closed(), 'checkpoint:trace-lost')
            return result

    def reply(self, invocation, daemon, *, timeout=8):
        return self.until(lambda row: is_reply(row, invocation, daemon), timeout)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.bus.close_sync(None)


def is_call(row, sender, interface, member, *, serial=None, destination=TIMER):
    return (row['kind'] == 1 and row['sender'] == sender and row['destination'] == destination
            and row['interface'] == interface and row['member'] == member
            and (serial is None or row['serial'] == serial))


def is_reply(row, invocation, daemon):
    return (row['kind'] in (2, 3) and row['sender'] == daemon
            and row['destination'] == invocation['sender'] and row['reply_serial'] == invocation['serial'])


def values(row, signature):
    return GLib.Variant.parse(GLib.VariantType.new(signature), row['body'], None, None).unpack()


def merge(records):
    result = []
    for start, end in sorted(records):
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


def session_active(uid, expected_session):
    session = child_session(uid)
    if session is None or session[0] != expected_session:
        return False
    state = guest.parse_properties(guest.run(['loginctl', 'show-session', expected_session,
        '-p', 'Active', '-p', 'LockedHint', '-p', 'IdleHint']), ('Active', 'LockedHint', 'IdleHint'),
        category='checkpoint:session-state')
    return state == {'Active': 'yes', 'LockedHint': 'no', 'IdleHint': 'no'}


def exercise(shell, child, session, active_witness, control, daemon, record):
    senders = shell_senders(shell, child)
    with PersistentCaller(child) as reader, Trace() as trace, control:
        def ask():
            reader.send({'kind': 'timer-self-usage'})

        control.sendall(f'arm {reader.name} ,{",".join(senders)},'.encode('ascii'))
        receive(control, 'armed')
        guest.require(session_active(child, session), 'checkpoint:child-not-active-at-arm')
        # Increasing the real allowance guarantees the estimate can advance
        # even if the initial desktop setup refreshed it shortly before arm.
        # The gate parks GNOME's native policy-change checkpoint.
        guest.run(['busctl', '--system', 'set-property', 'org.freedesktop.Accounts',
                   f'/org/freedesktop/Accounts/User{child}', LIMITS, 'DailyLimit', 'u', '9000'])
        serial, sender = receive(control, 'gated', sender=senders)
        write = trace.until(lambda row: is_call(row, sender, CHILD, 'RecordUsage', serial=serial))
        guest.require(write is not None, 'checkpoint:extension-write-missing')
        calls = trace.rows[:trace.rows.index(write)]
        preparatory = [row for row in calls if is_call(row, sender, PARENT, 'QueryUsage')
                       and values(row, '(uss)') == (child, 'login-session', '')]
        guest.require(preparatory and any(is_reply(row, preparatory[-1], daemon['owner'])
                      and row['kind'] == 2 for row in calls), 'checkpoint:preparatory-query-incomplete')
        payload, = values(write, '(a(ttss))')
        guest.require(len(payload) == 1, 'checkpoint:expected-one-active-record')
        start, end, usage_type, identifier = payload[0]
        guest.require(end - max(start, active_witness) >= 2
                      and usage_type == 'login-session' and identifier == '',
                      'checkpoint:expected-positive-active-record')

        ask()
        held_serial, _ = receive(control, 'held', sender=(reader.name,))
        held = trace.until(lambda row: is_call(row, reader.name, PARENT, 'QueryUsage', serial=held_serial))
        guest.require(held is not None and values(held, '(uss)') == (child, 'login-session', ''),
                      'checkpoint:held-query-identity')
        try:
            control.sendall(b'write')
            busy = trace.reply(write, daemon['owner'], timeout=4)
            guest.require(busy is not None and busy['error_name'] == BUSY,
                          'checkpoint:targeted-child-busy-missing')
        finally:
            control.sendall(b'release')
        receive(control, 'released')
        before = accepted(reader.receive(timeout=10), category='checkpoint:held-query-failed')
        expected = merge([*before, [start, end]])
        guest.require(merge(before) != expected, 'checkpoint:no-unsaved-activity')
        record('onpc.checkpoint.busy', f'call={write["serial"]} reply={busy["serial"]} '
               f'interval={start}..{end} held-read={held_serial}')
        print(f'checkpoint: matched Child.Error.Busy call={write["serial"]} reply={busy["serial"]}',
              flush=True)

        def successful_retry(row):
            return (row['kind'] == 2 and row['sender'] == daemon['owner'] and row['destination'] == sender
                    and any(is_call(candidate, sender, CHILD, 'RecordUsage', serial=row['reply_serial'])
                            and candidate['serial'] != serial and candidate['body'] == write['body']
                            for candidate in trace.rows))

        retry = trace.until(successful_retry, timeout=8)
        ask()
        after = accepted(reader.receive(timeout=12), category='checkpoint:fresh-query-failed')
        record('onpc.checkpoint.recovery', f'expected={expected} actual={after} '
               f'retry={None if retry is None else (retry["reply_serial"], retry["serial"])}')
        guest.require(retry is not None and after == expected,
                      f'checkpoint:recovery expected={expected} actual={after} '
                      f'exact-success={retry is not None}')
        between = trace.rows[trace.rows.index(write) + 1:trace.rows.index(retry)]
        guest.require(not any(is_call(row, sender, PARENT, 'QueryUsage') for row in between),
                      'checkpoint:retry-used-a-new-query')
        # The child Shell also originates GNOME's proxy writes. Only the
        # failed direct call and its exact retry may have returned by now.
        guest.require(not any(row['kind'] == 2 and row['reply_serial'] != retry['reply_serial']
            and any(is_reply(row, request, daemon['owner']) for request in trace.rows
                    if request['interface'] == CHILD and request['member'] == 'RecordUsage'
                    and request['sender'] == sender) for row in trace.rows),
            'checkpoint:other-shell-write-masked-recovery')
        guest.require(session_active(child, session) and timer_identity() == daemon,
                      'checkpoint:active-session-or-timer-changed')
        control.sendall(b'finish')
        receive(control, 'finished')


def verify(record):
    guest.guard()
    accounts = identities()
    child = accounts['child']
    manager = installed_manager()
    account, _ = manager._account(child)
    session, _ = wait_for(lambda: child_session(child), 'checkpoint:autologin')
    address = wait_for(lambda: manager._live_session_address(account), 'checkpoint:child-bus')
    shell = Shell(account, address)
    try:
        with instrument_timer() as (control, daemon):
            accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 120)))
            wait_for(lambda: shell.info().get('state') == 1, 'checkpoint:extension-inactive')

            def native_deadline():
                try:
                    deadline = shell.call('com.puffyslippers.OhNoParentControl.ChildUI',
                        '/com/puffyslippers/OhNoParentControl/NativeTime',
                        'com.puffyslippers.OhNoParentControl.NativeTime1', 'GetDeadline', '()', (), '(t)')
                    return deadline > time.monotonic_ns() // 1000 + 60_000_000
                except GLib.Error:
                    return False

            wait_for(native_deadline, 'checkpoint:native-deadline-unavailable')
            began = time.monotonic()
            active_witness = int(time.time())
            wait_for(lambda: time.monotonic() - began >= 4 and native_deadline()
                     and session_active(child, session), 'checkpoint:no-active-span')
            exercise(shell, child, session, active_witness, control, daemon, record)
    finally:
        shell.close()
