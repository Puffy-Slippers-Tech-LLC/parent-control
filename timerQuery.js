import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';
const ESTIMATE_REPLY_TYPE = '(ta{s(btttt)})';
const BUSY_RETRY_DELAYS_MS = Object.freeze([100, 250, 500, 1000, 2000]);

let _queue = Promise.resolve();

function enqueue(task) {
    const result = _queue.then(() => task(), () => task());
    _queue = result.catch(() => {});
    return result;
}

export function queryEstimatedTimes() {
    return enqueue(async () => {
        for (let attempt = 0; ; attempt++) {
            try {
                return await callEstimatedTimes();
            } catch (error) {
                const retryDelay = BUSY_RETRY_DELAYS_MS[attempt];
                if (!isDatabaseBusy(error) || retryDelay === undefined)
                    throw error;
                await wait(retryDelay);
            }
        }
    });
}

function callEstimatedTimes() {
    return new Promise((resolve, reject) => {
        Gio.DBus.system.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, 'GetEstimatedTimes',
            new GLib.Variant('(s)', ['login-session']),
            new GLib.VariantType(ESTIMATE_REPLY_TYPE),
            Gio.DBusCallFlags.NONE, -1, null,
            (connection, result) => {
                try {
                    const [, estimates] = connection.call_finish(result).deepUnpack();
                    resolve(estimates);
                } catch (error) {
                    reject(error);
                }
            });
    });
}

function isDatabaseBusy(error) {
    return Gio.DBusError.get_remote_error(error)?.endsWith('.Error.Busy') ?? false;
}

function wait(delayMs) {
    return new Promise(resolve => {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, delayMs, () => {
            resolve();
            return GLib.SOURCE_REMOVE;
        });
    });
}
