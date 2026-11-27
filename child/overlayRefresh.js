import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export const OVERLAY_BUS_NAME = 'com.puffyslippers.OhNoParentControl.ChildRequest';
export const OVERLAY_OBJECT_PATH = '/com/puffyslippers/OhNoParentControl/ChildRequest';

export function watchOverlayRefresh(connection, currentProcess, refresh) {
    const dbus = 'org.freedesktop.DBus';
    return connection.signal_subscribe(OVERLAY_BUS_NAME,
        'com.puffyslippers.OhNoParentControl.ChildRequest1', 'CountdownChanged',
        OVERLAY_OBJECT_PATH, null, Gio.DBusSignalFlags.NONE,
        (bus, sender, _path, _interface, _signal, parameters) => {
            const process = currentProcess();
            if (!process?.get_identifier() || parameters.n_children() !== 0)
                return;

            // An overlay activated through GApplication may be a separate,
            // already-running primary instance. Verify the actual sender PID.
            bus.call(dbus, '/org/freedesktop/DBus', dbus, 'GetConnectionUnixProcessID',
                new GLib.Variant('(s)', [sender]), new GLib.VariantType('(u)'),
                Gio.DBusCallFlags.NONE, 5000, null, (bus, result) => {
                    let pid;
                    try {
                        [pid] = bus.call_finish(result).deepUnpack();
                    } catch (_error) {
                        return; // The sender can disconnect during lookup.
                    }
                    // Gio clears the identifier at exit, even before wait_async
                    // dispatches the extension's completion callback.
                    if (process === currentProcess() && process.get_identifier() === String(pid))
                        refresh();
                });
        });
}
