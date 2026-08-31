import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'com.puffyslippers.OhNoParentControl1';
const OBJECT_PATH = '/com/puffyslippers/OhNoParentControl1';
const INTERFACE = BUS_NAME;
const MAX_MESSAGE_LENGTH = 4096;

function write(level, message) {
    const text = String(message).slice(0, MAX_MESSAGE_LENGTH);
    try {
        Gio.DBus.system.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, 'LogEvent',
            new GLib.Variant('(sss)', ['child', level, text]),
            new GLib.VariantType('()'), Gio.DBusCallFlags.NONE, 5000, null,
            (connection, result) => {
                try {
                    connection.call_finish(result);
                } catch (_error) {
                    // Logging is best-effort when the broker is unavailable.
                }
            });
    } catch (_error) {
        // Logging must not interfere with the shell extension.
    }
}

export const logDebug = message => write('DEBUG', message);
export const logInfo = message => write('INFO', message);
export const logWarning = message => write('WARNING', message);
export const logError = message => write('ERROR', message);
