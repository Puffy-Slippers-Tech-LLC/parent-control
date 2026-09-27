import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

import {calculateOwnRemainingTime} from '../../child/timeCalculationClient.js';
import {timerErrorCategory, waitForRetry} from '../../child/timerQuery.js';

function assertEqual(actual, expected, message) {
    if (actual !== expected)
        throw new Error(`${message}: expected ${expected}, got ${actual}`);
}

async function main() {
    for (const [name, category] of [
        ['NoReply', 'no-reply'], ['NameHasNoOwner', 'no-owner'],
        ['ServiceUnknown', 'service-unknown'], ['TimedOut', 'timeout'],
        ['Timeout', 'timeout'], ['AccessDenied', 'access-denied'],
        ['InvalidArgs', 'invalid-argument'], ['Failed', 'failed'],
    ]) {
        const error = Gio.DBusError.new_for_dbus_error(
            `org.freedesktop.DBus.Error.${name}`, 'private error text');
        assertEqual(timerErrorCategory(error), category, 'real Gio D-Bus category');
    }
    assertEqual(timerErrorCategory(new GLib.Error(
        Gio.io_error_quark(), Gio.IOErrorEnum.TIMED_OUT, 'private timeout')),
    'timeout', 'local Gio timeout');
    assertEqual(timerErrorCategory(Gio.DBusError.new_for_dbus_error(
        'org.freedesktop.MalcontentTimer1.Error.Busy', 'private database path')),
    'busy', 'timer busy category');
    assertEqual(timerErrorCategory(new Error('private JS exception')), 'other', 'plain JS error');
    assertEqual(timerErrorCategory(Gio.DBusError.new_for_dbus_error(
        'private.unknown.Error', 'private error text')), 'other', 'unknown remote name');
    // Validation runs before the adapter makes a system-bus call, so this tests
    // the real GJS/Gio client safely without requiring product services.
    await calculateOwnRemainingTime(-1).then(
        () => { throw new Error('negative value was accepted'); },
        error => assertEqual(error.message, 'Invalid remaining-time value', 'Gio adapter validates input'),
    );
    await calculateOwnRemainingTime(0x1_0000_0000).then(
        () => { throw new Error('overflow value was accepted'); },
        error => assertEqual(error.message, 'Invalid remaining-time value', 'Gio adapter rejects overflow'),
    );

    const start = GLib.get_monotonic_time();
    await waitForRetry(1);
    assertEqual(GLib.get_monotonic_time() >= start, true, 'GLib timeout completed');
    print('GJS child adapter tests passed');
}

await main();
