import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';
const LOG_PREFIX = '[request-more-time]';

export class MalcontentClient {
    constructor() {
        this._connection = Gio.DBus.system;
        this._pending = new Map();
        this._signalId = this._connection.signal_subscribe(
            BUS_NAME, INTERFACE, 'ExtensionResponse', OBJECT_PATH, null,
            Gio.DBusSignalFlags.NONE,
            (_connection, _sender, _path, _interface, _signal, parameters) =>
                this._onResponse(parameters));
    }

    requestExtension(durationSeconds) {
        if (!Number.isSafeInteger(durationSeconds) || durationSeconds < 0)
            return Promise.reject(new Error('Invalid extension duration'));

        return new Promise((resolve, reject) => {
            this._connection.call(
                BUS_NAME, OBJECT_PATH, INTERFACE, 'RequestExtension',
                new GLib.Variant('(ssta{sv})', ['login-session', '', durationSeconds, {}]),
                new GLib.VariantType('(o)'),
                Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION,
                -1, null,
                (connection, result) => {
                    try {
                        const [cookie] = connection.call_finish(result).deepUnpack();
                        this._pending.set(cookie, {resolve, reject});
                        console.log(`${LOG_PREFIX} request submitted`);
                    } catch (error) {
                        console.error(`${LOG_PREFIX} request failed: ${error.message}`);
                        reject(error);
                    }
                });
        });
    }

    destroy() {
        if (this._signalId)
            this._connection.signal_unsubscribe(this._signalId);
        this._signalId = 0;
        for (const {reject} of this._pending.values())
            reject(new Error('Extension disabled'));
        this._pending.clear();
    }

    _onResponse(parameters) {
        const [granted, cookie] = parameters.deepUnpack();
        const pending = this._pending.get(cookie);
        if (!pending)
            return;
        this._pending.delete(cookie);
        pending.resolve(granted);
    }
}
