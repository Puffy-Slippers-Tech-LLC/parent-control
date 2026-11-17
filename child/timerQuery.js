import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {busyRetryDelay} from './indicatorLogic.mjs';
import {logInfo, logWarning} from './logger.js';

const BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';
const ESTIMATE_REPLY_TYPE = '(ta{s(btttt)})';
const QUERY_BUDGET_MS = 25000;
const CALL_TIMEOUT_MS = 5000;
let _queue = Promise.resolve();

function enqueue(task) {
    const result = _queue.then(() => task(), () => task());
    _queue = result.catch(() => {});
    return result;
}

export function queryEstimatedTimes() {
    return enqueue(async () => {
        const started = GLib.get_monotonic_time() / 1000;
        const deadline = started + QUERY_BUDGET_MS;
        let lastError;
        for (let attempt = 0; ; attempt++) {
            const remaining = Math.floor(deadline - GLib.get_monotonic_time() / 1000);
            if (remaining <= 0)
                throw lastError;
            try {
                const estimates = await callEstimatedTimes(Math.min(CALL_TIMEOUT_MS, remaining));
                if (attempt > 0)
                    logInfo('child.timer-recovered', {attempts: attempt + 1});
                return estimates;
            } catch (error) {
                lastError = error;
                const category = timerErrorCategory(error);
                const retryDelay = category === 'busy'
                    ? busyRetryDelay('org.freedesktop.MalcontentTimer1.Child.Error.Busy', attempt)
                    : (['no-reply', 'no-owner', 'service-unknown', 'timeout'].includes(category) &&
                        attempt < 2 ? 200 : undefined);
                const retry = retryDelay !== undefined &&
                    deadline - GLib.get_monotonic_time() / 1000 > retryDelay;
                logWarning('child.timer-read-failed', {
                    category, attempt: attempt + 1, retry,
                });
                if (!retry)
                    throw error;
                // Re-address the well-known name: the previous daemon may have
                // exited at its idle deadline or while the desktop was asleep.
                await waitForRetry(retryDelay);
            }
        }
    });
}

// Malcontent merges overlapping records. Inactive refreshes replay a completed
// self-read interval; active refreshes checkpoint only activity actually observed
// by the controller. Date the checkpoint at dispatch, including queue/read time.
export function replayOwnUsage(cancellable, observeStage = () => {}, activeSince = () => null) {
    return enqueue(async () => {
        if (cancellable.is_cancelled()) return false;
        observeStage('query-usage');
        const uid = Gio.Credentials.new().get_unix_user();
        const [records] = await callTimer('org.freedesktop.MalcontentTimer1.Parent',
            'QueryUsage', new GLib.Variant('(uss)', [uid, 'login-session', '']),
            '(a(tt))', CALL_TIMEOUT_MS, cancellable);
        if (cancellable.is_cancelled()) return false;
        observeStage('select-record');
        const realtime = GLib.get_real_time();
        const monotonic = GLib.get_monotonic_time();
        const now = Math.floor(realtime / 1_000_000);
        const since = activeSince();
        if (since !== null) {
            if (![since.realtime, since.monotonic].every(value =>
                Number.isSafeInteger(value) && value >= 0) || since.monotonic > monotonic)
                throw new Error('Invalid active usage boundary');
            // Completed checkpoints are wall-clock intervals. Remapping them
            // after a clock correction could charge the same activity twice.
            // Leave that boundary to Shell until its clocks agree again or a
            // new active interval begins. Allow the API's one-second precision.
            if (Math.abs((realtime - since.realtime) - (monotonic - since.monotonic)) > 1_000_000)
                return false;
        }
        const record = since === null ? records.findLast(([start, end]) =>
            Number.isSafeInteger(start) && Number.isSafeInteger(end) &&
            start >= 0 && end >= start && end <= now)
            : [Math.floor(since.realtime / 1_000_000), now];
        if (!record || record[1] < record[0]) return false;
        observeStage('record-usage');
        await callTimer(INTERFACE, 'RecordUsage', new GLib.Variant('(a(ttss))',
            [[[record[0], record[1], 'login-session', '']]]), '()', CALL_TIMEOUT_MS, cancellable);
        return true;
    });
}

async function callEstimatedTimes(timeoutMs) {
    const [, estimates] = await callTimer(INTERFACE, 'GetEstimatedTimes',
        new GLib.Variant('(s)', ['login-session']), ESTIMATE_REPLY_TYPE, timeoutMs);
    return estimates;
}

function callTimer(iface, method, parameters, replyType, timeoutMs, cancellable = null) {
    return new Promise((resolve, reject) => {
        Gio.DBus.system.call(
            BUS_NAME, OBJECT_PATH, iface, method, parameters,
            new GLib.VariantType(replyType), Gio.DBusCallFlags.NONE, timeoutMs, cancellable,
            (connection, result) => {
                try {
                    resolve(connection.call_finish(result).deepUnpack());
                } catch (error) {
                    reject(error);
                }
            });
    });
}

// Only fixed categories leave this boundary. Never serialize messages, stacks,
// arbitrary remote names, or any values embedded in an exception.
export function timerErrorCategory(error) {
    if (!(error instanceof GLib.Error))
        return 'other';
    const remote = Gio.DBusError.get_remote_error(error);
    // The daemon registers separate error domains for its Child and Parent
    // interfaces. Estimates/replay use Child; QueryUsage uses Parent.
    if (remote === 'org.freedesktop.MalcontentTimer1.Child.Error.Busy' ||
        remote === 'org.freedesktop.MalcontentTimer1.Parent.Error.Busy')
        return 'busy';
    for (const [code, category] of [
        [Gio.DBusError.NO_REPLY, 'no-reply'],
        [Gio.DBusError.NAME_HAS_NO_OWNER, 'no-owner'],
        [Gio.DBusError.SERVICE_UNKNOWN, 'service-unknown'],
        [Gio.DBusError.TIMEOUT, 'timeout'],
        [Gio.DBusError.TIMED_OUT, 'timeout'],
        [Gio.DBusError.ACCESS_DENIED, 'access-denied'],
        [Gio.DBusError.AUTH_FAILED, 'access-denied'],
        [Gio.DBusError.INVALID_ARGS, 'invalid-argument'],
        [Gio.DBusError.DISCONNECTED, 'disconnected'],
        [Gio.DBusError.FAILED, 'failed'],
    ]) {
        if (error.matches(Gio.dbus_error_quark(), code))
            return category;
    }
    for (const [code, category] of [
        [Gio.IOErrorEnum.TIMED_OUT, 'timeout'],
        [Gio.IOErrorEnum.CANCELLED, 'cancelled'],
        [Gio.IOErrorEnum.INVALID_ARGUMENT, 'invalid-argument'],
    ]) {
        if (error.matches(Gio.io_error_quark(), code))
            return category;
    }
    return 'other';
}

export function waitForRetry(delayMs) {
    return new Promise(resolve => {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, delayMs, () => {
            resolve();
            return GLib.SOURCE_REMOVE;
        });
    });
}
