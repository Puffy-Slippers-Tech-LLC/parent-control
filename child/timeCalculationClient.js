import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'com.puffyslippers.OhNoParentControl1';
const OBJECT_PATH = '/com/puffyslippers/OhNoParentControl1';
const INTERFACE = BUS_NAME;

export function calculateOwnRemainingTime(dailyAllowanceRemainingSeconds) {
    if (!Number.isSafeInteger(dailyAllowanceRemainingSeconds) ||
        dailyAllowanceRemainingSeconds < 0 ||
        dailyAllowanceRemainingSeconds > 0xffffffff)
        return Promise.reject(new Error('Invalid remaining-time value'));

    return new Promise((resolve, reject) => {
        Gio.DBus.system.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, 'CalculateOwnRemainingTime',
            new GLib.Variant('(u)', [dailyAllowanceRemainingSeconds]),
            new GLib.VariantType('(u)'), Gio.DBusCallFlags.NONE, -1, null,
            (connection, result) => {
                try {
                    resolve(connection.call_finish(result).deepUnpack()[0]);
                } catch (error) {
                    reject(error);
                }
            });
    });
}

// Native and timer observations are both absolute realtime seconds. Convert
// units only; source selection and live-grant arithmetic belong to the broker.
export function calculateOwnDeadline(nativeEnd, timerEnd, owner = BUS_NAME) {
    const endpoints = [nativeEnd, timerEnd].map(value => value * 1_000_000);
    if ([nativeEnd, timerEnd].some(value => typeof value !== 'number') ||
        endpoints.some(value => !Number.isSafeInteger(value) || value < 0))
        return Promise.reject(new Error('Invalid countdown endpoint'));
    return new Promise((resolve, reject) => {
        Gio.DBus.system.call(
            owner, OBJECT_PATH, INTERFACE, 'CalculateOwnDeadline',
            new GLib.Variant('(tt)', endpoints), new GLib.VariantType('(t)'),
            Gio.DBusCallFlags.NONE, 5000, null,
            (connection, result) => {
                try {
                    const deadline = connection.call_finish(result).deepUnpack()[0];
                    if (!Number.isSafeInteger(deadline) || deadline < 0)
                        throw new Error('Invalid countdown deadline');
                    resolve(deadline);
                } catch (error) {
                    reject(error);
                }
            });
    });
}
