import GLib from 'gi://GLib';

import {calculateOwnRemainingTime} from '../../child/timeCalculationClient.js';
import {waitForRetry} from '../../child/timerQuery.js';

function assertEqual(actual, expected, message) {
    if (actual !== expected)
        throw new Error(`${message}: expected ${expected}, got ${actual}`);
}

async function main() {
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
