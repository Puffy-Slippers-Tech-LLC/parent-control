#!/usr/bin/python3
"""Guarded guest caller: drop credentials before opening a fresh system bus.

The controller sends one JSON batch over stdin. Replies stay in the controller's
private diagnostics until its normal redaction pass. No product module is loaded.
"""

import json
import os
from pathlib import Path
import pwd
import sys

import system_guest as guest


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
    guest.require(operation['kind'] == 'call', 'caller:operation')
    try:
        result = connection.call_sync(
            guest.BUS, '/com/puffyslippers/OhNoParentControl1', guest.BUS,
            operation['method'], GLib.Variant(operation['signature'], operation['args']),
            None, Gio.DBusCallFlags.NONE, 90000, None)
        return {'result': result.unpack()}
    except GLib.Error as error:
        # Preserve the public error name, never arbitrary exception text.
        return {'error': Gio.DBusError.get_remote_error(error) or 'transport-error'}


def main():
    guest.guard()
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib

    request = json.load(sys.stdin)
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
