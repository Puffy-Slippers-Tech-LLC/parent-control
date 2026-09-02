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
