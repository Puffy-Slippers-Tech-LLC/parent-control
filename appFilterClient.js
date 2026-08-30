import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const LOG_PREFIX = '[oh-no-parent-control]';
const ACCOUNTS_BUS_NAME = 'org.freedesktop.Accounts';
const ACCOUNTS_OBJECT_PATH = '/org/freedesktop/Accounts';
const ACCOUNTS_INTERFACE = 'org.freedesktop.Accounts';
const PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties';
const APP_FILTER_INTERFACE = 'com.endlessm.ParentalControls.AppFilter';
const APP_FILTER_PROPERTY = 'AppFilter';

export class AppFilterClient {
    constructor(connection = Gio.DBus.system) {
        this._connection = connection;
    }

    async getBlockedTargets() {
        const userPath = await this._getUserObjectPath();
        const filter = await this._getAppFilter(userPath);
        const [isAllowlist, targets] = filter;

        if (!Array.isArray(targets))
            throw new Error('AppFilter returned an invalid target list');

        // The requested semantics are blocklist semantics. An allowlist cannot
        // be represented as a list of blocked targets without changing what
        // the filter allows, so treat it as having no blocklist targets.
        if (isAllowlist) {
            console.warn(
                `${LOG_PREFIX} current app filter is an allowlist; ` +
                'not converting it to a blocklist');
            return [];
        }

        return targets.filter(target =>
            typeof target === 'string' && target.length > 0);
    }

    async setBlockedTargets(blockedTargets, allowUserInteraction = false) {
        if (!Array.isArray(blockedTargets) ||
            blockedTargets.some(target => typeof target !== 'string'))
            throw new Error('Invalid blocked app targets');

        const userPath = await this._getUserObjectPath();
        const value = new GLib.Variant('(bas)', [false, blockedTargets]);
        await this._call(
            userPath,
            PROPERTIES_INTERFACE,
            'Set',
            new GLib.Variant('(ssv)', [
                APP_FILTER_INTERFACE,
                APP_FILTER_PROPERTY,
                value,
            ]),
            null,
            allowUserInteraction
                ? Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION
                : Gio.DBusCallFlags.NONE);
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

    async _getAppFilter(userPath) {
        const reply = await this._call(
            userPath,
            PROPERTIES_INTERFACE,
            'Get',
            new GLib.Variant('(ss)', [APP_FILTER_INTERFACE, APP_FILTER_PROPERTY]),
            new GLib.VariantType('(v)'));
        return reply.recursiveUnpack()[0];
    }

    _call(objectPath, interfaceName, methodName, parameters, replyType,
        flags = Gio.DBusCallFlags.NONE) {
        return new Promise((resolve, reject) => {
            this._connection.call(
                ACCOUNTS_BUS_NAME,
                objectPath,
                interfaceName,
                methodName,
                parameters,
                replyType,
                flags,
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
