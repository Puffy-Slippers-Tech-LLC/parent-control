import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'com.puffyslippers.OhNoParentControl1';
const OBJECT_PATH = '/com/puffyslippers/OhNoParentControl1';
const INTERFACE = BUS_NAME;

export function calculateRemainingTime(
    dailyAllowanceRemainingSeconds,
    oneTimeGrantRemainingSeconds,
    additionalOneTimeGrantSeconds) {
    const values = [
        dailyAllowanceRemainingSeconds,
        oneTimeGrantRemainingSeconds,
        additionalOneTimeGrantSeconds,
    ];
    if (values.some(value => !Number.isSafeInteger(value) ||
        value < 0 || value > 0xffffffff))
        return Promise.reject(new Error('Invalid remaining-time value'));

    return new Promise((resolve, reject) => {
        Gio.DBus.system.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, 'CalculateRemainingTime',
            new GLib.Variant('(uuuu)', [
                Number(new Gio.Credentials().get_unix_user()), ...values,
            ]),
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
