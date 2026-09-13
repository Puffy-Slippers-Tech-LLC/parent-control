"""Set overview state on the explicitly owned nested Shell, without key toggles."""

import os
import re
from pathlib import Path

from gi.repository import Gio, GLib


def set_overview(active, wait):
    root = Path(os.environ['ONPC_CHILD_SHELL_ARTIFACT_DIR'])
    expected = f'unix:path={root / "runtime/session-bus"}'
    address = os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')
    # dbus-daemon appends its generated identity to --print-address output.
    # Accept that identity, but no alternative address or unrelated bus options.
    if not re.fullmatch(re.escape(expected) + r'(?:,guid=[0-9a-f]{32})?', address):
        raise ValueError('overview control requires the owned nested-Shell bus')
    connection = Gio.DBusConnection.new_for_address_sync(
        address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
        Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
    try:
        def call(method, parameters):
            return connection.call_sync(
                'org.gnome.Shell', '/org/gnome/Shell', 'org.freedesktop.DBus.Properties',
                method, parameters, None, Gio.DBusCallFlags.NONE, 3000, None)

        call('Set', GLib.Variant('(ssv)', ('org.gnome.Shell', 'OverviewActive',
                                         GLib.Variant('b', active))))

        def reached():
            value = call('Get', GLib.Variant('(ss)', ('org.gnome.Shell', 'OverviewActive')))
            return value.unpack()[0] == active

        wait(reached, 'the requested private Shell overview state')
        print(f'interaction overview={"shown" if active else "hidden"}', flush=True)
    finally:
        connection.close_sync(None)
