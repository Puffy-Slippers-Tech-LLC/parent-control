import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

import {calculateOwnDeadline, calculateOwnRemainingTime} from '../../child/timeCalculationClient.js';
import {timerErrorCategory, waitForRetry} from '../../child/timerQuery.js';
import {OVERLAY_BUS_NAME, OVERLAY_OBJECT_PATH, watchOverlayRefresh} from '../../child/overlayRefresh.js';

function assertEqual(actual, expected, message) {
    if (actual !== expected)
        throw new Error(`${message}: expected ${expected}, got ${actual}`);
}

async function checkOverlayRefresh() {
    const daemon = Gio.Subprocess.new(['dbus-daemon', '--session', '--nofork', '--print-address=1',
        `--address=unix:abstract=onpc-child-${GLib.uuid_string_random()}`], Gio.SubprocessFlags.STDOUT_PIPE);
    let bus, subscription, process;
    let identityChecks = 0, refreshes = 0;
    const interfaceName = 'com.puffyslippers.OhNoParentControl.ChildRequest1';
    const requestName = `bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
        'org.freedesktop.DBus', 'RequestName', new GLib.Variant('(su)', [${JSON.stringify(OVERLAY_BUS_NAME)}, 0]),
        null, Gio.DBusCallFlags.NONE, 2000, null)`;
    const signal = `bus.emit_signal(null, ${JSON.stringify(OVERLAY_OBJECT_PATH)},
        ${JSON.stringify(interfaceName)}, 'CountdownChanged', null)`;
    const launcher = new Gio.SubprocessLauncher({flags: Gio.SubprocessFlags.NONE});
    const launchOverlay = stayOpen => launcher.spawnv(['gjs', '-c', `
        const {Gio, GLib} = imports.gi;
        const bus = Gio.DBus.session;
        ${requestName};
        ${signal};
        bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', 'ReleaseName',
            new GLib.Variant('(s)', [${JSON.stringify(OVERLAY_BUS_NAME)}]),
            null, Gio.DBusCallFlags.NONE, 2000, null);
        if (${stayOpen}) new GLib.MainLoop(null, false).run();
    `]);
    const waitForChecks = async count => {
        const until = GLib.get_monotonic_time() + 5_000_000;
        while (identityChecks < count && GLib.get_monotonic_time() < until)
            await waitForRetry(10);
        assertEqual(identityChecks, count, 'overlay signal reached its identity check');
    };
    try {
        const output = new Gio.DataInputStream({base_stream: daemon.get_stdout_pipe()});
        const [address] = output.read_line_utf8(null);
        if (!address)
            throw new Error('The private session bus did not publish its address');
        launcher.setenv('DBUS_SESSION_BUS_ADDRESS', address, true);
        bus = Gio.DBusConnection.new_for_address_sync(address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            null, null);
        subscription = watchOverlayRefresh(bus, () => {
            identityChecks++;
            return process;
        }, () => refreshes++);

        process = launchOverlay(true);
        await waitForChecks(2);
        assertEqual(refreshes, 1, 'started overlay refreshes while its process is still running');

        // An independent process can own the application name, as happens
        // when the panel launched a secondary GApplication instance.
        const foreign = Gio.DBusConnection.new_for_address_sync(address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            null, null);
        try {
            foreign.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'RequestName', new GLib.Variant('(su)', [OVERLAY_BUS_NAME, 0]),
                null, Gio.DBusCallFlags.NONE, 2000, null);
            foreign.emit_signal(null, OVERLAY_OBJECT_PATH, interfaceName, 'CountdownChanged', null);
            await waitForChecks(4);
            assertEqual(refreshes, 1, 'another process owning the application name cannot refresh');
        } finally {
            foreign.close_sync(null);
        }

        process.force_exit();
        process.wait(null);
        process = launchOverlay(false);
        process.wait_check(null); // Deliver the queued signal after this process is reaped.
        await waitForChecks(5);
        assertEqual(refreshes, 1, 'an exited overlay cannot refresh');
    } finally {
        if (process?.get_identifier()) {
            process.force_exit();
            process.wait(null);
        }
        try {
            if (subscription)
                bus.signal_unsubscribe(subscription);
            bus?.close_sync(null);
        } finally {
            daemon.force_exit();
            daemon.wait(null);
        }
    }
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
    for (const iface of ['Child', 'Parent']) {
        assertEqual(timerErrorCategory(Gio.DBusError.new_for_dbus_error(
            `org.freedesktop.MalcontentTimer1.${iface}.Error.Busy`, 'private database path')),
        'busy', 'timer interface busy category');
        assertEqual(timerErrorCategory(Gio.DBusError.new_for_dbus_error(
            `org.freedesktop.MalcontentTimer1.${iface}.Error.IdentifyingUser`, 'private identity')),
        'other', 'identity failures remain outside transient recovery');
    }
    assertEqual(timerErrorCategory(Gio.DBusError.new_for_dbus_error(
        'org.freedesktop.MalcontentTimer1.Error.Busy', 'private database path')),
    'other', 'unregistered timer busy domain');
    assertEqual(timerErrorCategory(new Error('private JS exception')), 'other', 'plain JS error');
    assertEqual(timerErrorCategory(Gio.DBusError.new_for_dbus_error(
        'private.unknown.Error', 'private error text')), 'other', 'unknown remote name');
    assertEqual(timerErrorCategory(Gio.DBusError.new_for_dbus_error(
        'private.unknown.Error.Busy', 'private error text')), 'other', 'unknown Busy remote name');
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

    for (const invalid of [-1, NaN, Infinity, null, undefined, '100', 1e10]) {
        for (const endpoints of [[invalid, 0], [0, invalid]]) {
            await calculateOwnDeadline(...endpoints).then(
                () => { throw new Error('invalid countdown endpoint was accepted'); },
                error => assertEqual(error.message, 'Invalid countdown endpoint', 'deadline input validation'),
            );
        }
    }

    const start = GLib.get_monotonic_time();
    await waitForRetry(1);
    assertEqual(GLib.get_monotonic_time() >= start, true, 'GLib timeout completed');
    await checkOverlayRefresh();
    print('GJS child adapter tests passed');
}

await main();
