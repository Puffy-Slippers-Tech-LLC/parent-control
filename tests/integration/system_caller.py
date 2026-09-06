#!/usr/bin/python3
"""Guarded guest caller: drop credentials before opening a fresh system bus.

The controller sends one JSON batch over stdin. Replies stay in the controller's
private diagnostics until its normal redaction pass. No product module is loaded.
"""

import json
import fcntl
import os
from pathlib import Path
import pwd
import select
import signal
import secrets
import subprocess
import sys
import time
import termios

import system_guest as guest


class FixturePassword:
    """An in-memory fixture secret with safe diagnostic representation."""

    def __init__(self):
        self._value = secrets.token_urlsafe(32).encode()

    def __repr__(self):
        return '<fixture password redacted>'

    def install(self, uid):
        guest.guard()
        # A separate command controller has no diagnostic directory. Neither
        # stdin nor password-setting output is exported to artifacts.
        from owned_commands import Commands
        Commands().run(['/usr/sbin/chpasswd'],
                       input=pwd.getpwuid(uid).pw_name.encode() + b':' + self._value + b'\n',
                       timeout=30, merge_stderr=False)


class TextAgent:
    """Real pkttyagent on a private PTY; never export terminal contents."""

    def __init__(self, caller):
        guest.guard()
        guest.require(isinstance(caller.name, str) and caller.name.startswith(':'), 'agent:subject')
        subject = caller.agent_subject()
        self.child = None
        self.pidfd = None
        self.master = None
        self.pending = b''
        slave = notify_read = notify_write = None
        try:
            self.master, slave = os.openpty()
            notify_read, notify_write = os.pipe()
            self.child = subprocess.Popen(
                ['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_caller.py'),
                 '--agent', subject, str(notify_write)],
                stdin=slave, stdout=slave, stderr=slave, pass_fds=(notify_write,))
            self.pidfd = os.pidfd_open(self.child.pid)
            os.close(slave)
            slave = None
            os.close(notify_write)
            notify_write = None
            ready, _, _ = select.select([notify_read], [], [], 20)
            notified = bool(ready) and os.read(notify_read, 1) == b''
            status = self.child.poll()
            if not notified or status is not None:
                category = self._startup_category()
                print('onpc-system: stage=authentication-agent outcome=failed '
                      f'exit={status} category={category}', flush=True)
                exit_status = 'running' if status is None else str(status)
                raise guest.GuestError(f'agent:registration:{category}:exit-{exit_status}')
            print('onpc-system: stage=authentication-agent outcome=registered', flush=True)
        except BaseException:
            self.close()
            raise
        finally:
            for fd in (slave, notify_read, notify_write):
                if fd is not None:
                    os.close(fd)

    def _startup_category(self):
        # Startup bytes can contain account names or bus identities. Reduce
        # them to fixed categories in memory; never export the terminal.
        terminal = b''
        while len(terminal) < 65536:
            ready, _, _ = select.select([self.master], [], [], 0)
            if not ready:
                break
            try:
                chunk = os.read(self.master, min(4096, 65536 - len(terminal)))
            except OSError:
                break
            if not chunk:
                break
            terminal += chunk
        for marker, category in (
            (b'agent-wrapper:guard', 'wrapper-guard'),
            (b'agent-wrapper:session', 'wrapper-session'),
            (b'agent-wrapper:terminal', 'wrapper-terminal'),
            (b'agent-wrapper:executable-missing', 'executable-missing'),
            (b'agent-wrapper:exec', 'wrapper-exec'),
            (b'Authorization not available', 'authority-unavailable'),
            (b'Error creating textual authentication agent', 'terminal-agent'),
            (b'Only unix-process and unix-session subjects', 'unsupported-subject'),
            (b'Error registering authentication agent', 'polkit-registration'),
            (b'Error closing notify-fd', 'notification-fd'),
        ):
            if marker in terminal:
                return category
        return 'startup-unknown'

    def _until(self, marker, timeout=30, *, alternatives=()):
        deadline = time.monotonic() + timeout
        markers = (marker, *alternatives)
        while not any(value in self.pending for value in markers):
            remaining = deadline - time.monotonic()
            guest.require(remaining > 0, 'agent:terminal-timeout')
            ready, _, _ = select.select([self.master], [], [], remaining)
            guest.require(bool(ready), 'agent:terminal-timeout')
            try:
                chunk = os.read(self.master, 4096)
            except OSError:
                raise guest.GuestError('agent:terminal-disconnected') from None
            guest.require(bool(chunk), 'agent:terminal-disconnected')
            self.pending += chunk
            guest.require(len(self.pending) <= 65536, 'agent:terminal-size')
        found = min((value for value in markers if value in self.pending),
                    key=self.pending.index)
        end = self.pending.index(found) + len(found)
        result, self.pending = self.pending[:end], self.pending[end:]
        return result

    def prompt(self, selected_uid, other_uid):
        terminal = self._until(b'Password:')
        selected = pwd.getpwuid(selected_uid).pw_name.encode()
        other = pwd.getpwuid(other_uid).pw_name.encode()
        guest.require(b'Authenticating as:' in terminal and selected in terminal and
                      other not in terminal, 'agent:selected-identity')
        # pkttyagent prints the prompt before disabling echo. Wait for its
        # terminal transition so input cannot race its TCSAFLUSH operation.
        deadline = time.monotonic() + 5
        while termios.tcgetattr(self.master)[3] & termios.ECHO:
            guest.require(time.monotonic() < deadline, 'agent:echo-enabled')
            time.sleep(0.01)
        print('onpc-system: stage=authentication-prompt outcome=selected-identity', flush=True)

    def authenticate(self, password, *, succeeds=True):
        guest.require(isinstance(password, FixturePassword), 'agent:password-type')
        guest.require(not termios.tcgetattr(self.master)[3] & termios.ECHO, 'agent:echo-enabled')
        payload = password._value + b'\n'
        guest.require(os.write(self.master, payload) == len(payload), 'agent:password-write')
        expected = b'AUTHENTICATION COMPLETE' if succeeds else b'AUTHENTICATION FAILED'
        opposite = b'AUTHENTICATION FAILED' if succeeds else b'AUTHENTICATION COMPLETE'
        terminal = self._until(expected, alternatives=(opposite, b'AUTHENTICATION CANCELED'))
        outcome = ('accepted' if terminal.endswith(b'AUTHENTICATION COMPLETE') else
                   'denied' if terminal.endswith(b'AUTHENTICATION FAILED') else 'cancelled')
        print('onpc-system: stage=authentication outcome=' +
              outcome, flush=True)
        guest.require(terminal.endswith(expected), 'agent:unexpected-' + outcome)

    def close(self):
        try:
            if self.pidfd is not None:
                try:
                    signal.pidfd_send_signal(self.pidfd, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self.child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        signal.pidfd_send_signal(self.pidfd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    self.child.wait(timeout=5)
        finally:
            if self.pidfd is not None:
                os.close(self.pidfd)
                self.pidfd = None
            if self.master is not None:
                os.close(self.master)
                self.master = None
            self.pending = b''
        if self.child is not None and self.child.returncode is None:
            # Without a pin, closing the terminal is the only cleanup action.
            # Never signal a numeric PID or inferred authentication helper.
            self.child.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class PersistentCaller:
    """Keep a guarded real caller alive; signal only its recorded pidfd."""

    def __init__(self, uid):
        guest.guard()
        self.child = subprocess.Popen(
            ['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_caller.py')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            self.pidfd = os.pidfd_open(self.child.pid)
        except BaseException:
            # No identity pin exists: close the input, never fall back to a PID.
            self.child.stdin.close()
            self.child.stdout.close()
            self.child.wait(timeout=5)
            raise
        self.pending = b''
        try:
            self.send({'uid': uid, 'stream': True})
            ready = self.receive()
            guest.require(ready.get('uid') == uid and
                          isinstance(ready.get('name'), str) and ready['name'].startswith(':'),
                          'caller:stream-identity')
            self.name = ready['name']
        except BaseException:
            self.close()
            raise

    def send(self, operation):
        self.child.stdin.write(json.dumps(operation).encode() + b'\n')
        self.child.stdin.flush()

    def agent_subject(self):
        # Read only the directly spawned, pinned caller. Polkit registers
        # agents for process/session subjects and resolves broker bus-name
        # challenges to that same process. Include start time against PID reuse.
        guest.require(self.pidfd is not None and self.child.poll() is None,
                      'caller:agent-subject-exited')
        fields = Path(f'/proc/{self.child.pid}/stat').read_text().rsplit(')', 1)[1].split()
        start_time = fields[19]
        guest.require(start_time.isdecimal() and int(start_time) > 0 and
                      self.child.poll() is None, 'caller:agent-subject-identity')
        return f'{self.child.pid},{start_time}'

    def receive(self, timeout=100):
        deadline = time.monotonic() + timeout
        while b'\n' not in self.pending:
            remaining = deadline - time.monotonic()
            guest.require(remaining > 0, 'caller:stream-timeout')
            readable, _, _ = select.select([self.child.stdout], [], [], remaining)
            guest.require(bool(readable), 'caller:stream-timeout')
            chunk = os.read(self.child.stdout.fileno(), 65536)
            guest.require(bool(chunk), 'caller:stream-disconnected')
            self.pending += chunk
            guest.require(len(self.pending) <= 1048576, 'caller:stream-reply-size')
        line, self.pending = self.pending.split(b'\n', 1)
        return json.loads(line)

    def call(self, method, signature='()', args=()):
        self.send({'kind': 'call', 'method': method, 'signature': signature, 'args': args})
        return self.receive()

    def close(self):
        if self.pidfd is None:
            return
        try:
            try:
                self.child.stdin.close()
            except BrokenPipeError:
                pass
            try:
                self.child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    signal.pidfd_send_signal(self.pidfd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.child.wait(timeout=5)
        finally:
            self.child.stdout.close()
            os.close(self.pidfd)
            self.pidfd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def drop_identity(uid):
    guest.require(type(uid) is int and uid > 0, 'caller:uid')
    account = pwd.getpwuid(uid)
    os.initgroups(account.pw_name, account.pw_gid)
    os.setresgid(account.pw_gid, account.pw_gid, account.pw_gid)
    os.setresuid(uid, uid, uid)
    guest.require(os.getresuid() == (uid, uid, uid) and
                  os.getresgid() == (account.pw_gid,) * 3, 'caller:credentials')
    os.environ.clear()
    os.environ.update(PATH='/usr/bin:/bin', LANG='C.UTF-8', HOME=account.pw_dir)
    os.chdir('/')


def execute(connection, operation, Gio, GLib):
    if operation['kind'] == 'private-read':
        # Exact product paths only; never return private record contents.
        target = operation['target']
        guest.require(type(target) is int and target >= 1000, 'caller:target')
        try:
            with (Path('/var/lib/oh-no-parent-control/preferences') / f'{target}.json').open('rb'):
                return {'readable': True}
        except PermissionError:
            return {'readable': False}
    guest.require(operation['kind'] in ('call', 'account-type-write'), 'caller:operation')
    destination = interface = guest.BUS
    path = '/com/puffyslippers/OhNoParentControl1'
    if operation['kind'] == 'account-type-write':
        target = operation['target']
        guest.require(type(target) is int and target >= 1000, 'caller:target')
        destination = 'org.freedesktop.Accounts'
        path = f'/org/freedesktop/Accounts/User{target}'
        interface = 'org.freedesktop.Accounts.User'
        method, parameters = 'SetAccountType', GLib.Variant('(i)', (1,))
    else:
        method = operation['method']
        parameters = GLib.Variant(operation['signature'], operation['args'])
    try:
        result = connection.call_sync(
            destination, path, interface, method, parameters,
            None, Gio.DBusCallFlags.NONE, 90000, None)
        return {'result': result.unpack()}
    except GLib.Error as error:
        # Preserve the public error name, never arbitrary exception text.
        return {'error': Gio.DBusError.get_remote_error(error) or 'transport-error'}


def run_agent(subject, notify_fd):
    stage = 'guard'
    try:
        guest.guard()
        stage = 'session'
        os.setsid()
        stage = 'terminal'
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.environ.update(LANG='C', LC_ALL='C')
        stage = 'exec'
        os.execv('/usr/bin/pkttyagent', ['pkttyagent', '--process', subject,
                                      '--notify-fd', notify_fd])
    except Exception as error:
        if stage == 'exec' and isinstance(error, FileNotFoundError):
            stage = 'executable-missing'
        print('agent-wrapper:' + stage, file=sys.stderr, flush=True)
        raise SystemExit(1) from None


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--agent':
        run_agent(sys.argv[2], sys.argv[3])
        return
    guest.guard()
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib

    request = json.loads(sys.stdin.readline())
    drop_identity(request['uid'])
    connection = Gio.DBusConnection.new_for_address_sync(
        'unix:path=/run/dbus/system_bus_socket',
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
        Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
    try:
        name = connection.get_unique_name()
        actual = connection.call_sync(
            'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
            'GetConnectionUnixUser', GLib.Variant('(s)', (name,)),
            GLib.VariantType.new('(u)'), Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]
        guest.require(actual == request['uid'], 'caller:bus-credentials')
        if request.get('stream') is True:
            print(json.dumps({'uid': actual, 'name': name}), flush=True)
            for line in sys.stdin:
                print(json.dumps(execute(connection, json.loads(line), Gio, GLib)), flush=True)
        else:
            replies = [execute(connection, operation, Gio, GLib) for operation in request['operations']]
            print(json.dumps({'uid': actual, 'replies': replies}))
    finally:
        connection.close_sync(None)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('onpc-system: stage=caller outcome=failed category=caller-failed', file=sys.stderr)
        raise SystemExit(1) from None
