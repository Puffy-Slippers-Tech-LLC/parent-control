"""Real-caller broker operations shared by guarded installed test areas.

Raw account data stays in memory or private runner artifacts. Refusals use
fixed categories so pytest cannot expose backend replies in diagnostics.
"""

import json
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


def account_properties(uid, interface, properties):
    """Read a fresh, typed group from one AccountsService observation.

    Callers supply only the properties they compare. Do not cache this result
    across mutations or use it as a broker/customer acceptance observation.
    """
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


def session_limits(uid):
    """One fresh native-limit observation, shared by lifecycle assertions."""
    properties = {'LimitType': 'u', 'DailyLimit': 'u', 'ActiveExtension': '(tu)'}
    values = account_properties(uid, 'com.endlessm.ParentalControls.SessionLimits', properties)
    return tuple(values[name] for name in properties)


def account_state(uid):
    """Snapshot preferences, limits and app filter without putting them in assertions."""
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
               'FindUserById', 'x', str(uid)])
    record = Path('/var/lib/oh-no-parent-control/preferences') / f'{uid}.json'
    return (
        record.read_bytes() if record.exists() else None,
        *session_limits(uid),
        account_property(uid, 'com.endlessm.ParentalControls.AppFilter', 'AppFilter'),
    )
