import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';
const LOG_PREFIX = '[oh-no-parent-control]';

export class MalcontentClient {
    constructor(onUnsolicitedResponse = null) {
        this._connection = Gio.DBus.system;
        this._onUnsolicitedResponse = onUnsolicitedResponse;
        this._pending = new Map();
        this._earlyResponses = new Map();
        this._awaitingResponseCookies = new Set();
        this._submissionsInFlight = 0;
        this._signalId = this._connection.signal_subscribe(
            BUS_NAME, INTERFACE, 'ExtensionResponse', OBJECT_PATH, null,
            Gio.DBusSignalFlags.NONE,
            (_connection, _sender, _path, _interface, _signal, parameters) =>
                this._onResponse(parameters));
    }

    submitExtension(durationSeconds, flags = Gio.DBusCallFlags.NONE) {
        if (!Number.isSafeInteger(durationSeconds) || durationSeconds < 0)
            return Promise.reject(new Error('Invalid extension duration'));

        return new Promise((resolve, reject) => {
            this._submissionsInFlight++;
            this._connection.call(
                BUS_NAME, OBJECT_PATH, INTERFACE, 'RequestExtension',
                new GLib.Variant('(ssta{sv})', ['login-session', '', durationSeconds, {}]),
                new GLib.VariantType('(o)'),
                flags,
                -1, null,
                (connection, result) => {
                    this._submissionsInFlight--;
                    try {
                        const [cookie] = connection.call_finish(result).deepUnpack();
                        // Mark ownership before resolving the submission
                        // promise. A fast ExtensionResponse can otherwise be
                        // mistaken for an unsolicited native request before
                        // waitForResponse() installs its pending entry.
                        this._awaitingResponseCookies.add(cookie);
                        console.log(`${LOG_PREFIX} request submitted`);
                        resolve(cookie);
                    } catch (error) {
                        console.error(`${LOG_PREFIX} request failed: ${error.message}`);
                        reject(error);
                    }
                });
        });
    }

    requestExtension(durationSeconds) {
        return this.submitExtension(durationSeconds).then(cookie =>
            this.waitForResponse(cookie));
    }

    requestExtensionInteractive(durationSeconds) {
        return this.submitExtension(
            durationSeconds,
            Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION).then(cookie =>
            this.waitForResponse(cookie));
    }

    waitForResponse(cookie) {
        if (this._earlyResponses.has(cookie)) {
            const {granted, extraData} = this._earlyResponses.get(cookie);
            this._earlyResponses.delete(cookie);
            this._awaitingResponseCookies.delete(cookie);
            this._logRejection(granted, extraData);
            return Promise.resolve(granted);
        }

        return new Promise((resolve, reject) => {
            this._pending.set(cookie, {resolve, reject});
        });
    }

    destroy() {
        if (this._signalId)
            this._connection.signal_unsubscribe(this._signalId);
        this._signalId = 0;
        for (const {reject} of this._pending.values())
            reject(new Error('Extension disabled'));
        this._pending.clear();
        this._earlyResponses.clear();
        this._awaitingResponseCookies.clear();
        this._submissionsInFlight = 0;
        this._onUnsolicitedResponse = null;
    }

    _onResponse(parameters) {
        const [granted, cookie, extraData] = parameters.deepUnpack();
        const pending = this._pending.get(cookie);
        if (!pending) {
            // RequestExtension returns its cookie asynchronously, but the
            // service may emit ExtensionResponse before that method reply is
            // dispatched. Keep responses only while one of our submissions
            // is awaiting its cookie, then consume it in waitForResponse().
            if (this._submissionsInFlight > 0 ||
                this._awaitingResponseCookies.has(cookie)) {
                this._earlyResponses.set(cookie, {granted, extraData});
            } else {
                this._onUnsolicitedResponse?.({
                    granted,
                    cookie,
                    extraData,
                });
            }
            return;
        }
        this._pending.delete(cookie);
        this._awaitingResponseCookies.delete(cookie);
        this._logRejection(granted, extraData);
        pending.resolve(granted);
    }

    _logRejection(granted, extraData) {
        if (granted)
            return;

        let errorName = extraData?.['error-name'];
        if (typeof errorName?.deepUnpack === 'function')
            errorName = errorName.deepUnpack();
        console.warn(`${LOG_PREFIX} extension response denied` +
            (errorName ? `: ${errorName}` : ' by the authorization agent'));
    }
}
