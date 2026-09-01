import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {queryEstimatedTimes} from './timerQuery.js';
import {calculateRemainingTime} from './timeCalculationClient.js';

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

        // ActiveExtension is (start time, duration). Replacing the property
        // replaces any previous extension; Malcontent still preserves unused
        // daily allowance and permits access until the later expiry.
        await this._replaceActiveExtensionAt(
            userPath, issuedAt, durationSeconds);

        return issuedAt;
    }

    async addActiveExtension(additionalSeconds) {
        if (!Number.isSafeInteger(additionalSeconds) ||
            additionalSeconds <= 0 || additionalSeconds > 0xffffffff)
            throw new Error('Invalid additional extension duration');

        // ActiveExtension starts at the write time rather than when the daily
        // allowance runs out. Preserve the timer daemon's current effective
        // remainder so the selected duration is genuinely additional time.
        const userPath = await this._getUserObjectPath();
        const estimates = await queryEstimatedTimes();
        const currentSessionEnd = Number(estimates['']?.[2] ?? 0);
        const issuedAt = Math.floor(
            GLib.get_real_time() / GLib.USEC_PER_SEC);
        // GetEstimatedTimes already represents the later of the daily and
        // current ActiveExtension expiries. Passing that effective allowance
        // through the broker-owned formula preserves either one, then adds the
        // newly approved time.
        const effectiveRemaining = Number.isFinite(currentSessionEnd)
            ? Math.max(0, Math.ceil(currentSessionEnd - issuedAt))
            : 0;
        const durationSeconds = await calculateRemainingTime(
            effectiveRemaining, 0, additionalSeconds);
        if (!Number.isSafeInteger(durationSeconds) || durationSeconds > 0xffffffff)
            throw new Error('Combined extension duration is too large');

        await this._replaceActiveExtensionAt(
            userPath, issuedAt, durationSeconds);
        return durationSeconds;
    }

    async _replaceActiveExtensionAt(userPath, issuedAt, durationSeconds) {
        const value = new GLib.Variant(
            '(tu)', [issuedAt, durationSeconds]);

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
