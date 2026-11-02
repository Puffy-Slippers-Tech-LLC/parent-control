"""Real-caller broker operations shared by guarded installed test areas.

Raw account data stays in memory or private runner artifacts. Refusals use
fixed categories so pytest cannot expose backend replies in diagnostics.
"""

import json
import os
from pathlib import Path

import system_guest as guest


def batch(uid, operations, *, allow_root=False, category='caller:reply'):
    raw = guest.commands.run(
        ['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_caller.py')],
        input=json.dumps({'uid': uid, 'operations': operations, 'allow_root': allow_root}).encode(),
        timeout=180, merge_stderr=False)
    try:
        reply = json.loads(raw)
    except (ValueError, UnicodeError):
        raise guest.GuestError(category) from None
    guest.require(isinstance(reply, dict) and type(reply.get('uid')) is int
                  and reply['uid'] == uid and isinstance(reply.get('replies'), list)
                  and len(reply['replies']) == len(operations)
                  and all(isinstance(item, dict) for item in reply['replies']), category)
    return reply['replies']


def call(uid, method, signature='()', args=(), *, allow_root=False, category='caller:reply'):
    return batch(uid, [{'kind': 'call', 'method': method, 'signature': signature, 'args': args}],
                 allow_root=allow_root, category=category)[0]


def accepted(reply, *, category='authorization:expected-success'):
    guest.require(isinstance(reply, dict) and 'result' in reply, category)
    return reply['result']


def account_property(uid, interface, prop):
    return json.loads(guest.run([
        'busctl', '--system', '--json=short', 'get-property',
        'org.freedesktop.Accounts', f'/org/freedesktop/Accounts/User{uid}',
        interface, prop]))['data']


def account_properties(uid, interface, properties, *, connection=None):
    """Read a fresh, typed group from one AccountsService observation.

    Callers supply only the properties they compare. Do not cache this result
    across mutations or use it as a broker/customer acceptance observation.
    """
    if connection is not None:
        from gi.repository import Gio, GLib
        reply = connection.call_sync(
            'org.freedesktop.Accounts', f'/org/freedesktop/Accounts/User{uid}',
            'org.freedesktop.DBus.Properties', 'GetAll', GLib.Variant('(s)', (interface,)),
            GLib.VariantType.new('(a{sv})'), Gio.DBusCallFlags.NONE, 90000, None)
        values = reply.get_child_value(0)
        selected = {name: values.lookup_value(name, GLib.VariantType.new(signature))
                    for name, signature in properties.items()}
        guest.require(all(value is not None for value in selected.values()),
                      'accounts:properties-reply')
        # Match busctl's JSON array shape for structs, including ActiveExtension
        # and AppFilter. Only fresh observations use this connection.
        return json.loads(json.dumps({name: value.unpack() for name, value in selected.items()}))
    reply = json.loads(guest.run([
        'busctl', '--system', '--json=short', 'call', 'org.freedesktop.Accounts',
        f'/org/freedesktop/Accounts/User{uid}', 'org.freedesktop.DBus.Properties',
        'GetAll', 's', interface]))
    guest.require(reply.get('type') == 'a{sv}' and isinstance(reply.get('data'), list)
                  and len(reply['data']) == 1 and isinstance(reply['data'][0], dict),
                  'accounts:properties-reply')
    values = reply['data'][0]
    guest.require(all(isinstance(values.get(name), dict)
                      and values[name].get('type') == signature and 'data' in values[name]
                      for name, signature in properties.items()), 'accounts:properties-reply')
    return {name: values[name]['data'] for name in properties}


def session_limits(uid, *, connection=None):
    """One fresh native-limit observation, shared by lifecycle assertions."""
    properties = {'LimitType': 'u', 'DailyLimit': 'u', 'ActiveExtension': '(tu)'}
    values = account_properties(uid, 'com.endlessm.ParentalControls.SessionLimits', properties,
                                connection=connection)
    return tuple(values[name] for name in properties)


def account_state(uid, *, connection=None):
    """Snapshot preferences, limits and app filter without putting them in assertions."""
    if connection is None:
        guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                   '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
                   'FindUserById', 'x', str(uid)])
    else:
        from gi.repository import Gio, GLib
        path = connection.call_sync(
            'org.freedesktop.Accounts', '/org/freedesktop/Accounts',
            'org.freedesktop.Accounts', 'FindUserById', GLib.Variant('(x)', (uid,)),
            GLib.VariantType.new('(o)'), Gio.DBusCallFlags.NONE, 90000, None).unpack()[0]
        guest.require(path == f'/org/freedesktop/Accounts/User{uid}', 'accounts:state-target')
    record = Path('/var/lib/oh-no-parent-control/preferences') / f'{uid}.json'
    return (
        record.read_bytes() if record.exists() else None,
        *session_limits(uid, connection=connection),
        (account_property(uid, 'com.endlessm.ParentalControls.AppFilter', 'AppFilter')
         if connection is None else account_properties(
             uid, 'com.endlessm.ParentalControls.AppFilter', {'AppFilter': '(bas)'},
             connection=connection)['AppFilter']),
    )


def account_states(uids):
    """Read one fresh multi-account snapshot without per-property processes.

    This root observer owns one private bus connection only for this read. It
    neither shares a tested caller's identity nor retains values across writes.
    Individual subprocess-boundary observations keep account_state's default.
    """
    # The module's installed envelope has already run guest.guard(). Keep this
    # read-only boundary root-only without rehashing its payload per snapshot.
    guest.require(os.geteuid() == 0, 'root-required')
    uids = tuple(uids)
    guest.require(bool(uids) and len(set(uids)) == len(uids)
                  and all(type(uid) is int and 0 <= uid <= 0xffffffff for uid in uids),
                  'accounts:state-targets')
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio
    connection = Gio.DBusConnection.new_for_address_sync(
        'unix:path=/run/dbus/system_bus_socket',
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
        Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
    try:
        return {uid: account_state(uid, connection=connection) for uid in uids}
    finally:
        connection.close_sync(None)
