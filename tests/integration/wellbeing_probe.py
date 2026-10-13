"""Finite engineering client of the installed/public Wellbeing session service.

The component suite uses this same operation on its private bus. No settings are
written by the probe; only SetWindow acquires/releases the service's own lease.
"""
import json
import os
from pathlib import Path
import time
import uuid

BUS = 'com.puffyslippers.OhNoParentControl.Wellbeing'
PATH = '/com/puffyslippers/OhNoParentControl/Wellbeing'
SCHEMA = 'com.puffyslippers.oh-no-parent-control.child'
SCHEMAS = Path('/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/schemas')


class ProbeError(RuntimeError):
    pass


def require(condition, category):
    if not condition:
        raise ProbeError(category)


def qualify(address, schema_directory=SCHEMAS):
    from gi.repository import Gio, GLib
    connection = Gio.DBusConnection.new_for_address_sync(address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None)
    token = str(uuid.uuid4())
    owner = None
    attempted = False

    def call(destination, path, interface, method, arguments=None, *, activation=False):
        return connection.call_sync(destination, path, interface, method, arguments, None,
            Gio.DBusCallFlags.NONE if activation else Gio.DBusCallFlags.NO_AUTO_START, 3000, None)

    def wait(predicate, category, seconds=3):
        deadline = time.monotonic() + seconds
        while True:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if predicate():
                return
            require(time.monotonic() < deadline, category)
            time.sleep(.01)

    def original(settings):
        value = settings.get_user_value('show-banners')
        return 'default' if value is None else str(value.get_boolean()).lower()

    try:
        def current_owner():
            return call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                        'GetNameOwner', GLib.Variant('(s)', (BUS,))).unpack()[0]
        try:
            owner = current_owner()
        except GLib.Error as error:
            if Gio.DBusError.get_remote_error(error) != 'org.freedesktop.DBus.Error.NameHasNoOwner':
                raise
            # An already running public service needs no activation entry.
            # Only a genuinely absent owner exercises installed D-Bus activation.
            call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                 'StartServiceByName', GLib.Variant('(su)', (BUS, 0)), activation=True)
            owner = current_owner()
        require(owner.startswith(':'), 'wellbeing-probe:owner')
        def exported():
            try:
                return 'name="SetWindow"' in call(owner, PATH,
                    'org.freedesktop.DBus.Introspectable', 'Introspect').unpack()[0]
            except GLib.Error:
                return False
        wait(exported, 'wellbeing-probe:export-timeout')
        source = Gio.SettingsSchemaSource.new_from_directory(str(schema_directory),
            Gio.SettingsSchemaSource.get_default(), False)
        schema = source.lookup(SCHEMA, False)
        require(schema is not None, 'wellbeing-probe:schema')
        journal = Gio.Settings(settings_schema=schema)
        banners = Gio.Settings(schema_id='org.gnome.desktop.notifications.application',
            path='/org/gnome/desktop/notifications/application/gnome-wellbeing-panel/')
        require(journal.get_string('wellbeing-banner-backup') == '' and
                banners.is_writable('show-banners'), 'wellbeing-probe:settings-not-idle')
        before = original(banners)
        attempted = True  # A lost reply still requires cancellation/owner loss.
        call(owner, PATH, BUS, 'SetWindow', GLib.Variant('(sd)', (token, time.time() + 8)))
        wait(lambda: not banners.get_boolean('show-banners') and
             journal.get_string('wellbeing-banner-backup') == before,
             'wellbeing-probe:backup-or-suppression')
        call(owner, PATH, BUS, 'SetWindow', GLib.Variant('(sd)', (token, 0.0)))
        wait(lambda: original(banners) == before and journal.get_string('wellbeing-banner-backup') == '',
             'wellbeing-probe:restoration')
        attempted = False
        return {'original': before, 'backup_recorded': True, 'suppressed': True, 'restored': True}
    finally:
        try:
            if attempted and owner is not None:
                # Cancellation is safe after an uncertain acquisition; never
                # replay acquisition or adopt a replacement service owner.
                call(owner, PATH, BUS, 'SetWindow', GLib.Variant('(sd)', (token, 0.0)))
        finally:
            connection.close_sync(None)  # Owner loss also releases this lease.


if __name__ == '__main__':
    print(json.dumps(qualify(os.environ['DBUS_SESSION_BUS_ADDRESS']), sort_keys=True))
