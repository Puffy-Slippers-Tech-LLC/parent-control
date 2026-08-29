import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';
const ESTIMATE_REPLY_TYPE = '(ta{s(btttt)})';

let _queue = Promise.resolve();

function enqueue(task) {
    const result = _queue.then(() => task(), () => task());
    _queue = result.catch(() => {});
    return result;
}

export function queryEstimatedTimes() {
    return enqueue(() => new Promise((resolve, reject) => {
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
    }));
}

export function runExclusiveTimerUpdate(task) {
    return enqueue(() => Promise.resolve(task()));
}
