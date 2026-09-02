import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'com.puffyslippers.OhNoParentControl1';
const OBJECT_PATH = '/com/puffyslippers/OhNoParentControl1';
const MAX_REQUEST_SECONDS = 24 * 60 * 60;
const MIN_REQUEST_SECONDS = 6;
// GDBus accepts G_MAXINT as a practical no-timeout value. GJS does not expose
// that C macro through GLib, so keep its exact signed 32-bit value here.
const REQUEST_TIMEOUT_MS = 0x7fffffff;

export function requestOwnAccess(
    approverUid, durationSeconds, allowSoftBlockedApps) {
    if (!Number.isSafeInteger(approverUid) ||
        approverUid < 0 || approverUid > 0xffffffff)
        return Promise.reject(new Error('Invalid approving administrator'));
    if (!Number.isSafeInteger(durationSeconds) ||
        !(durationSeconds === 0 ||
          durationSeconds >= MIN_REQUEST_SECONDS &&
          durationSeconds <= MAX_REQUEST_SECONDS))
        return Promise.reject(new Error('Invalid requested duration'));
    if (typeof allowSoftBlockedApps !== 'boolean')
        return Promise.reject(new Error('Invalid app-access choice'));

    return new Promise((resolve, reject) => {
        Gio.DBus.system.call(
            BUS_NAME,
            OBJECT_PATH,
            BUS_NAME,
            'RequestOwnAccess',
            new GLib.Variant('(uub)', [
                approverUid,
                durationSeconds,
                allowSoftBlockedApps,
            ]),
            new GLib.VariantType('(ssu)'),
            Gio.DBusCallFlags.NONE,
            REQUEST_TIMEOUT_MS,
            null,
            (connection, result) => {
                try {
                    const [correlationId, outcome, grantedDurationSeconds] =
                        connection.call_finish(result).deepUnpack();
                    if (typeof correlationId !== 'string' || !correlationId ||
                        !['approved', 'denied', 'cancelled'].includes(outcome) ||
                        !Number.isSafeInteger(grantedDurationSeconds) ||
                        grantedDurationSeconds < 0 ||
                        grantedDurationSeconds > 0xffffffff ||
                        (outcome === 'approved') !== (grantedDurationSeconds > 0)) {
                        throw new Error('Broker returned an invalid request result');
                    }
                    resolve({correlationId, outcome, grantedDurationSeconds});
                } catch (error) {
                    reject(error);
                }
            });
    });
}
