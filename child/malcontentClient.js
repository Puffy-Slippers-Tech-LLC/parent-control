import Gio from 'gi://Gio';

const BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';

export class MalcontentClient {
    constructor(onUnsolicitedResponse = null) {
        this._connection = Gio.DBus.system;
        this._onUnsolicitedResponse = onUnsolicitedResponse;
        this._signalId = this._connection.signal_subscribe(
            BUS_NAME, INTERFACE, 'ExtensionResponse', OBJECT_PATH, null,
            Gio.DBusSignalFlags.NONE,
            (_connection, _sender, _path, _interface, _signal, parameters) =>
                this._onResponse(parameters));
    }

    destroy() {
        if (this._signalId)
            this._connection.signal_unsubscribe(this._signalId);
        this._signalId = 0;
        this._onUnsolicitedResponse = null;
    }

    _onResponse(parameters) {
        const [granted, cookie, extraData] = parameters.deepUnpack();
        this._onUnsolicitedResponse?.({
            granted,
            cookie,
            extraData,
        });
    }
}
