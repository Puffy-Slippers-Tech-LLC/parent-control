import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const ACCOUNTS_BUS_NAME = 'org.freedesktop.Accounts';
const ACCOUNTS_OBJECT_PATH = '/org/freedesktop/Accounts';
const ACCOUNTS_INTERFACE = 'org.freedesktop.Accounts';
const PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties';
const SESSION_LIMITS_INTERFACE =
    'com.endlessm.ParentalControls.SessionLimits';
const ACTIVE_EXTENSION_PROPERTY = 'ActiveExtension';

export class SessionLimitsClient {
    constructor(connection = Gio.DBus.system) {
        this._connection = connection;
    }

    async replaceActiveExtension(durationSeconds) {
        if (!Number.isSafeInteger(durationSeconds) ||
            durationSeconds <= 0 || durationSeconds > 0xffffffff)
            throw new Error('Invalid extension duration');

        const userPath = await this._getUserObjectPath();
        const issuedAt = Math.floor(
            GLib.get_real_time() / GLib.USEC_PER_SEC);
        const value = new GLib.Variant(
            '(tu)', [issuedAt, durationSeconds]);

        // ActiveExtension is (start time, duration). Replacing the property
        // makes durationSeconds the new total from this approval instant; it
        // does not add it to the previous active extension.
        await this._call(
            userPath,
            PROPERTIES_INTERFACE,
            'Set',
            new GLib.Variant('(ssv)', [
                SESSION_LIMITS_INTERFACE,
                ACTIVE_EXTENSION_PROPERTY,
                value,
            ]),
            null);

        return issuedAt;
    }

    async _getUserObjectPath() {
        const reply = await this._call(
            ACCOUNTS_OBJECT_PATH,
            ACCOUNTS_INTERFACE,
            'FindUserByName',
            new GLib.Variant('(s)', [GLib.get_user_name()]),
            new GLib.VariantType('(o)'));
        return reply.deepUnpack()[0];
    }

    _call(objectPath, interfaceName, methodName, parameters, replyType) {
        return new Promise((resolve, reject) => {
            this._connection.call(
                ACCOUNTS_BUS_NAME,
                objectPath,
                interfaceName,
                methodName,
                parameters,
                replyType,
                Gio.DBusCallFlags.NONE,
                -1,
                null,
                (connection, result) => {
                    try {
                        resolve(connection.call_finish(result));
                    } catch (error) {
                        reject(error);
                    }
                });
        });
    }
}
