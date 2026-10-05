import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export const APPLICATION_UI_NAME = 'com.puffyslippers.OhNoParentControl.ChildUI';
export const APPLICATION_UI_PATH = '/com/puffyslippers/OhNoParentControl/ApplicationUI';
const INTERFACE = 'com.puffyslippers.OhNoParentControl.ApplicationUI1';
const ID = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const MAX_BYTES = 256 * 1024;
const XML = `<node><interface name="${INTERFACE}">
    <method name="ListSurfaces"><arg type="s" direction="out" name="surfaces_json"/></method>
    <method name="Call">
        <arg type="s" direction="in" name="surface_id"/>
        <arg type="s" direction="in" name="element_id"/>
        <arg type="s" direction="in" name="operation"/>
        <arg type="s" direction="in" name="arguments_json"/>
        <arg type="s" direction="out" name="result_json"/>
    </method>
</interface></node>`;

class UiError extends Error {
    constructor(code) {
        super('Application UI operation refused');
        this.code = code;
    }
}

function encodeResult(result) {
    const encoded = JSON.stringify(result, (_key, value) => {
        if (typeof value === 'number' && !Number.isFinite(value))
            throw new UiError('Failed');
        return value;
    });
    if (typeof encoded !== 'string' ||
        new TextEncoder().encode(encoded).length > MAX_BYTES)
        throw new UiError('Failed');
    return encoded;
}

/** Desktop-neutral same-user transport over a finite product UI adapter. */
export class ChildApplicationUi {
    constructor(adapter) {
        this._adapter = adapter;
        this._closed = false;
        this._active = false;
        this._pending = 0;
        this._ownerId = 0;
        this._cancellable = new Gio.Cancellable();
        this._uid = Gio.Credentials.new().get_unix_user();
        this._connection = Gio.DBus.session;
        this._exported = Gio.DBusExportedObject.wrapJSObject(XML, this);
        try {
            this._exported.export(this._connection, APPLICATION_UI_PATH);
            this._ownerId = Gio.bus_own_name_on_connection(
                this._connection, APPLICATION_UI_NAME, Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                () => { if (!this._closed) this._active = true; },
                () => this.close());
        } catch (error) {
            this.close();
            throw error;
        }
    }

    ListSurfacesAsync(_parameters, invocation) {
        this._dispatch(invocation, () => this._adapter.listSurfaces());
    }

    CallAsync(parameters, invocation) {
        // Bound retained messages before queuing asynchronous authorization.
        if (parameters[0].length > 256 || parameters[1].length > 256 ||
            parameters[2].length > 32 || parameters[3].length > MAX_BYTES) {
            invocation.return_dbus_error(`${INTERFACE}.InvalidArgument`,
                'Application UI operation refused');
            return;
        }
        this._dispatch(invocation, () => this._call(...parameters));
    }

    _dispatch(invocation, operation) {
        if (this._closed || this._pending >= 32) {
            invocation.return_dbus_error(`${INTERFACE}.Unavailable`,
                'Application UI operation refused');
            return;
        }
        this._pending++;
        // Credentials are resolved by the session bus, never caller-supplied.
        // The callback rechecks lifecycle and current control state after this
        // asynchronous boundary before it can deliver an input.
        try {
            this._connection.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'GetConnectionUnixUser',
                new GLib.Variant('(s)', [invocation.get_sender()]),
                new GLib.VariantType('(u)'), Gio.DBusCallFlags.NONE, 3000,
                this._cancellable, (connection, result) => {
                    try {
                        const [uid] = connection.call_finish(result).deep_unpack();
                        if (uid !== this._uid) throw new UiError('Denied');
                        if (this._closed || !this._active || !this._adapter)
                            throw new UiError('Unavailable');
                        invocation.return_value(new GLib.Variant('(s)',
                            [encodeResult(operation())]));
                    } catch (error) {
                        const code = error instanceof UiError ? error.code :
                            (this._closed ? 'Unavailable' : 'Failed');
                        invocation.return_dbus_error(`${INTERFACE}.${code}`,
                            'Application UI operation refused');
                    } finally {
                        this._pending--;
                    }
                });
        } catch (_error) {
            this._pending--;
            invocation.return_dbus_error(`${INTERFACE}.Unavailable`,
                'Application UI operation refused');
        }
    }

    _call(surfaceId, elementId, operation, argumentsJson) {
        if (!ID.test(surfaceId)) throw new UiError('InvalidArgument');
        const elements = this._adapter.elements(surfaceId);
        if (!elements) throw new UiError('Unavailable');
        if (elementId.length > 256 || operation.length > 32)
            throw new UiError('InvalidArgument');
        if (argumentsJson.length > MAX_BYTES ||
            new TextEncoder().encode(argumentsJson).length > MAX_BYTES)
            throw new UiError('InvalidArgument');
        let args;
        try { args = JSON.parse(argumentsJson); } catch (_error) {
            throw new UiError('InvalidArgument');
        }
        if (!args || typeof args !== 'object' || Array.isArray(args))
            throw new UiError('InvalidArgument');
        const keys = Object.keys(args);
        if (operation === 'inventory') {
            if (elementId !== '' || keys.some(key => !['offset', 'limit', 'revision'].includes(key)))
                throw new UiError('InvalidArgument');
            const offset = Object.hasOwn(args, 'offset') ? args.offset : 0;
            const limit = Object.hasOwn(args, 'limit') ? args.limit : 128;
            if (!Number.isSafeInteger(offset) || offset < 0 || offset > elements.length ||
                !Number.isSafeInteger(limit) || limit < 1 || limit > 256 ||
                (Object.hasOwn(args, 'revision') &&
                 (typeof args.revision !== 'string' || !/^[a-f0-9]{64}$/.test(args.revision))) ||
                (offset > 0 && !Object.hasOwn(args, 'revision')))
                throw new UiError('InvalidArgument');
            const inventory = elements
                .sort((left, right) => left.id < right.id ? -1 : left.id > right.id ? 1 : 0)
                .map(element => this._metadata(surfaceId, element, false));
            const revision = GLib.compute_checksum_for_string(
                GLib.ChecksumType.SHA256, encodeResult(inventory), -1);
            if (Object.hasOwn(args, 'revision') && args.revision !== revision)
                throw new UiError('Unavailable');
            const end = Math.min(offset + limit, inventory.length);
            return {elements: inventory.slice(offset, end),
                next_offset: end < inventory.length ? end : null, revision};
        }
        const setterKey = operation === 'setValue' ? 'value' :
            operation === 'setText' ? 'text' : null;
        if (setterKey ? keys.length !== 1 || keys[0] !== setterKey : keys.length !== 0)
            throw new UiError('InvalidArgument');
        if (!ID.test(elementId)) throw new UiError('InvalidArgument');
        const matches = elements.filter(element => element.id === elementId);
        if (matches.length !== 1) throw new UiError('Unavailable');
        const element = matches[0];
        if (operation === 'getElementById') return this._metadata(surfaceId, element, true);
        if (!Object.hasOwn(element, operation) || typeof element[operation] !== 'function')
            throw new UiError('Unsupported');
        if (['setValue', 'setText', 'activate'].includes(operation)) {
            if (!element.visible || !element.enabled) throw new UiError('Unavailable');
            if (operation === 'setValue' && typeof args.value !== element.valueType)
                throw new UiError('InvalidArgument');
            if (operation === 'setText' && typeof args.text !== 'string')
                throw new UiError('InvalidArgument');
        }
        switch (operation) {
        case 'getValue': return element.getValue();
        case 'getText': return element.getText();
        case 'setValue':
            if (!element.setValue(args.value)) throw new UiError('Failed');
            return null;
        case 'setText':
            if (!element.setText(args.text)) throw new UiError('Failed');
            return null;
        case 'activate':
            element.activate();
            return null;
        default: throw new UiError('Unsupported');
        }
    }

    _metadata(surfaceId, element, values) {
        const operations = ['getElementById', ...['getValue', 'setValue', 'getText',
            'setText', 'activate'].filter(operation => typeof element[operation] === 'function')];
        const metadata = {id: element.id, surface_id: surfaceId,
            application_id: APPLICATION_UI_NAME, type: element.type,
            visible: element.visible, enabled: element.enabled, operations};
        if (values && element.getValue) metadata.value = element.getValue();
        if (values && element.getText) metadata.text = element.getText();
        return metadata;
    }

    close() {
        if (this._closed) return;
        this._closed = true;
        this._active = false;
        this._cancellable.cancel();
        this._exported.unexport();
        if (this._ownerId) Gio.bus_unown_name(this._ownerId);
        this._ownerId = 0;
        this._adapter?.close();
        this._adapter = null;
    }
}
