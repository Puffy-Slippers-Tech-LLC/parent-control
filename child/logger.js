import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {diagnosticEnvelope} from './diagnosticEvents.mjs';

const BUS_NAME = 'com.puffyslippers.OhNoParentControl1';
const OBJECT_PATH = '/com/puffyslippers/OhNoParentControl1';
const INTERFACE = BUS_NAME;
let catalog = null;
let lastEstimate = null;
let lastEstimateAt = 0;

function write(level, event, fields = {}) {
    try {
        if (catalog === null) {
            const file = Gio.File.new_for_uri(import.meta.url).get_parent()
                .get_child('diagnostic_catalog.json');
            const [loaded, bytes] = file.load_contents(null);
            if (!loaded)
                return;
            catalog = JSON.parse(new TextDecoder().decode(bytes));
        }
        // Do not record a second-by-second activity history. Keep transitions
        // to/from zero and periodic verification while estimates are healthy.
        if (event === 'child.estimate') {
            const now = GLib.get_monotonic_time() / 1000000;
            const remaining = fields.remaining;
            if (lastEstimate !== null && remaining > 0 && lastEstimate > 0 &&
                remaining <= lastEstimate && now - lastEstimateAt < 300)
                return;
            lastEstimate = remaining;
            lastEstimateAt = now;
        }
        const text = diagnosticEnvelope(catalog, event, fields);
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

export const logDebug = (event, fields) => write('DEBUG', event, fields);
export const logInfo = (event, fields) => write('INFO', event, fields);
export const logWarning = (event, fields) => write('WARNING', event, fields);
export const logError = (event, fields) => write('ERROR', event, fields);
