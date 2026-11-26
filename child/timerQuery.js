import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {busyRetryDelay} from './indicatorLogic.mjs';
import {logInfo, logWarning} from './logger.js';

const BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';
const CHILD_BUSY_ERROR = `${INTERFACE}.Error.Busy`;
const ESTIMATE_REPLY_TYPE = '(ta{s(btttt)})';
const QUERY_BUDGET_MS = 25000;
const CALL_TIMEOUT_MS = 5000;
const CLOCK_TOLERANCE_USEC = 1_000_000;
const REACTIVATION_RETRY_DELAYS_MS = [200, 1000, 3000, 5000];
let _queue = Promise.resolve();

function enqueue(task) {
    const result = _queue.then(() => task(), () => task());
    _queue = result.catch(() => {});
    return result;
}

export function queryEstimatedTimes(cancellable = null) {
    return enqueue(async () => {
        const started = GLib.get_monotonic_time() / 1000;
        const deadline = started + QUERY_BUDGET_MS;
        let lastError;
        for (let attempt = 0; ; attempt++) {
            cancellable?.set_error_if_cancelled();
            const remaining = Math.floor(deadline - GLib.get_monotonic_time() / 1000);
            if (remaining <= 0)
                throw lastError;
            try {
                const estimates = await callEstimatedTimes(Math.min(CALL_TIMEOUT_MS, remaining),
                    cancellable);
                cancellable?.set_error_if_cancelled();
                if (attempt > 0)
                    logInfo('child.timer-recovered', {attempts: attempt + 1});
                return estimates;
            } catch (error) {
                cancellable?.set_error_if_cancelled();
                lastError = error;
                const category = timerErrorCategory(error);
                const retryDelay = category === 'busy'
                    ? busyRetryDelay(CHILD_BUSY_ERROR, attempt)
                    : (['no-reply', 'no-owner', 'service-unknown', 'timeout'].includes(category)
                        ? REACTIVATION_RETRY_DELAYS_MS[attempt] : undefined);
                const retry = retryDelay !== undefined &&
                    deadline - GLib.get_monotonic_time() / 1000 > retryDelay;
                logWarning('child.timer-read-failed', {
                    category, attempt: attempt + 1, retry,
                });
                if (!retry)
                    throw error;
                // Re-address the well-known name: the previous daemon may have
                // exited at its idle deadline or while the desktop was asleep.
                await waitForRetry(retryDelay, cancellable);
            }
        }
    });
}

function clockRebased(previousOffset, currentOffset) {
    return Math.abs(currentOffset - previousOffset) > CLOCK_TOLERANCE_USEC;
}

// Checkpoint at dispatch, including time spent in the queue and reading usage.
async function selectUsageRecord(cancellable, observeStage, activeSince) {
    observeStage('query-usage');
    const uid = Gio.Credentials.new().get_unix_user();
    const [records] = await callTimer('org.freedesktop.MalcontentTimer1.Parent',
        'QueryUsage', new GLib.Variant('(uss)', [uid, 'login-session', '']),
        '(a(tt))', CALL_TIMEOUT_MS, cancellable);
    if (cancellable.is_cancelled()) return null;
    observeStage('select-record');
    const realtime = GLib.get_real_time();
    const monotonic = GLib.get_monotonic_time();
    const offset = realtime - monotonic;
    const now = Math.floor(realtime / 1_000_000);
    const since = activeSince();
    if (since === null) {
        const refresh = records.findLast(([start, end]) =>
            Number.isSafeInteger(start) && Number.isSafeInteger(end) &&
            start >= 0 && end >= start && end <= now);
        return {refresh, offset};
    }

    if (![since.realtime, since.monotonic].every(value =>
        Number.isSafeInteger(value) && value >= 0) || since.monotonic > monotonic)
        throw new Error('Invalid active usage boundary');
    // Remapping observed wall-clock intervals after a clock correction could
    // charge activity twice. Leave that boundary to Shell. Allow one second
    // of skew, matching the timer API's timestamp precision.
    const start = Math.floor(since.realtime / 1_000_000);
    const startOffset = since.realtime - since.monotonic;
    if (start > now || clockRebased(startOffset, offset)) return {offset};
    // Preserve the one-shot resume refresh, but only positive spans enter
    // recovery batches. Malcontent 0.14 cannot construct a same-second span.
    if (start === now) return {refresh: [start, now], offset};
    return {observed: {start, end: now, startOffset, captureOffset: offset}, offset};
}

function discardRebasedCheckpoints(checkpoints, offset) {
    // Shell can save the same activity on the corrected clock. Check both
    // captured offsets so several small steps cannot evade the tolerance.
    for (const interval of checkpoints) {
        if (clockRebased(interval.startOffset, offset) || clockRebased(interval.captureOffset, offset))
            checkpoints.delete(interval);
    }
}

function recordUsage(records, cancellable, timeoutMs) {
    const payload = Array.from(records, ([start, end]) => [start, end, 'login-session', '']);
    return callTimer(INTERFACE, 'RecordUsage', new GLib.Variant('(a(ttss))', [payload]),
        '()', timeoutMs, cancellable);
}

export async function replayOwnUsage(cancellable, pending, observeStage, activeSince) {
    let batch;
    let deadline;
    let lastBusy;
    for (let attempt = 0; ; attempt++) {
        const result = await enqueue(async () => {
            if (cancellable.is_cancelled()) return false;
            if (!batch) {
                const selection = await selectUsageRecord(cancellable, observeStage, activeSince);
                if (!selection || cancellable.is_cancelled()) return false;
                discardRebasedCheckpoints(pending, selection.offset);
                batch = new Set(pending);
                if (selection.observed) batch.add(selection.observed);
                if (!batch.size) {
                    if (!selection.refresh) return false;
                    observeStage('record-usage');
                    await recordUsage([selection.refresh], cancellable, CALL_TIMEOUT_MS);
                    return true;
                }
                deadline = GLib.get_monotonic_time() / 1000 + QUERY_BUDGET_MS;
            }

            const realtime = GLib.get_real_time();
            const monotonic = GLib.get_monotonic_time();
            const remaining = Math.floor(deadline - monotonic / 1000);
            const offset = realtime - monotonic;
            discardRebasedCheckpoints(pending, offset);
            discardRebasedCheckpoints(batch, offset);
            if (!batch.size) return false;
            const now = Math.floor(realtime / 1_000_000);
            // A small rollback can briefly put an endpoint in the future.
            // Let it become eligible within this same bounded retry window.
            if (remaining <= 0 || [...batch].some(({end}) => end > now)) return undefined;
            const records = new Map();
            // Combine prefixes only on the wire. An earlier observation can
            // still be usable when the longer one's clock mapping changes.
            for (const {start, end} of batch)
                records.set(start, Math.max(end, records.get(start) ?? end));
            observeStage('record-usage');
            try {
                await recordUsage(records, cancellable, Math.min(CALL_TIMEOUT_MS, remaining));
            } catch (error) {
                const remote = error instanceof GLib.Error ? Gio.DBusError.get_remote_error(error) : null;
                const busy = remote === CHILD_BUSY_ERROR;
                const interrupted = cancellable.is_cancelled() && error instanceof GLib.Error &&
                    error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED);
                if (busy || interrupted) {
                    // Cancellation releases the refresh promptly. The daemon
                    // may still commit, so retain the exact submitted spans.
                    for (const interval of batch)
                        pending.add(interval);
                }
                if (!busy) throw error;
                lastBusy = error;
                return undefined;
            }
            for (const interval of batch)
                pending.delete(interval);
            return true;
        });
        if (cancellable.is_cancelled()) return false;
        if (result !== undefined) return result;
        const delay = busyRetryDelay(CHILD_BUSY_ERROR, attempt);
        if (delay === undefined || deadline - GLib.get_monotonic_time() / 1000 <= delay) {
            if (lastBusy) throw lastBusy;
            return false;
        }
        // Estimates can run during backoff. The next observed activity
        // boundary cancels this wait and can submit the retained work.
        await waitForRetry(delay, cancellable);
    }
}

async function callEstimatedTimes(timeoutMs, cancellable) {
    const [, estimates] = await callTimer(INTERFACE, 'GetEstimatedTimes',
        new GLib.Variant('(s)', ['login-session']), ESTIMATE_REPLY_TYPE, timeoutMs, cancellable);
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
    if (remote === CHILD_BUSY_ERROR ||
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

export async function waitForRetry(delayMs, cancellable = null) {
    let timer = 0;
    let handler = 0;
    try {
        await new Promise(resolve => {
            timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delayMs, () => {
                timer = 0;
                resolve();
                return GLib.SOURCE_REMOVE;
            });
            if (cancellable)
                handler = cancellable.connect(() => resolve());
        });
    } finally {
        if (timer)
            GLib.source_remove(timer);
        if (handler)
            cancellable.disconnect(handler);
    }
}
