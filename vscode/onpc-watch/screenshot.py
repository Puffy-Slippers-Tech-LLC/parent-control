"""Save a Watch PNG and publish an actionable desktop notification."""

from datetime import datetime
from pathlib import Path
import sys

from gi.repository import Gio, GLib


def main():
    png = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
    if len(png) > 32 * 1024 * 1024 or not png.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Invalid screenshot PNG')
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
    folder = Path(pictures or str(Path.home() / 'Pictures')) / 'Screenshots'
    folder.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime('Screenshot From %Y-%m-%d %H-%M-%S')
    number = 0
    while True:
        target = folder / f'{stem}{f" ({number})" if number else ""}.png'
        try:
            with target.open('xb') as stream:
                stream.write(png)
            break
        except FileExistsError:
            number += 1

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    loop = GLib.MainLoop()
    notification = None
    startup_id = ''

    def signal(connection, sender, object_path, interface, name, parameters):
        nonlocal startup_id
        values = parameters.unpack()
        if values[0] != notification:
            return
        if name == 'ActivationToken':
            startup_id = values[1]
        elif name == 'ActionInvoked' and values[1] == 'default':
            try:
                connection.call_sync(
                    'org.freedesktop.FileManager1', '/org/freedesktop/FileManager1',
                    'org.freedesktop.FileManager1', 'ShowItems',
                    GLib.Variant('(ass)', ([target.as_uri()], startup_id)),
                    None, Gio.DBusCallFlags.NONE, 10000, None)
            except GLib.Error as error:
                print(f'Screenshot saved to {target}; cannot reveal it: {error}', file=sys.stderr)
            loop.quit()
        elif name == 'NotificationClosed':
            loop.quit()

    subscription = bus.signal_subscribe(
        'org.freedesktop.Notifications', 'org.freedesktop.Notifications', None,
        '/org/freedesktop/Notifications', None, Gio.DBusSignalFlags.NONE, signal)
    try:
        notification, = bus.call_sync(
            'org.freedesktop.Notifications', '/org/freedesktop/Notifications',
            'org.freedesktop.Notifications', 'Notify',
            GLib.Variant('(susssasa{sv}i)', (
                'ONPC Watch', 0, 'camera-photo', 'Screenshot captured',
                'Click to show in Files', ['default', 'Show in Files'],
                {'image-path': GLib.Variant('s', target.as_uri())}, 5000)),
            GLib.VariantType.new('(u)'), Gio.DBusCallFlags.NONE, 10000, None).unpack()
        # Keep the action available in notification history until dismissed.
        loop.run()
    except GLib.Error as error:
        raise RuntimeError(f'Screenshot saved to {target}; notification failed: {error}') from error
    finally:
        bus.signal_unsubscribe(subscription)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
