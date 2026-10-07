import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {WellbeingLeases, wellbeingWindowEnd} from '../../child/wellbeingLogic.mjs';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

function harness(original = 'default') {
    let wall = 100, monotonic = 0, backup = '', value = original, failRestore = false;
    const writes = [];
    const settings = {
        backup: () => backup, original: () => value,
        saveBackup: next => { backup = next; writes.push(['backup', next]); },
        suppress: () => { value = 'false'; writes.push(['value', value]); },
        restore: next => {
            if (failRestore) throw Error('locked');
            value = next; writes.push(['value', next]);
        },
        sync: () => writes.push(['sync']),
    };
    const create = () => new WellbeingLeases(settings, () => wall, () => monotonic);
    return {create, leases: create(), writes, get backup() { return backup; },
        get value() { return value; }, userChange: next => { value = next; },
        lock: next => { failRestore = next; },
        advance: (real, mono = real) => { wall += real; monotonic += mono; }};
}

test('window follows native deadline, any reminder and exact boundaries', () => {
    const manager = {dailyLimitTime: 200, getCurrentTime: () => 0,
        parentalControlsSessionLimitsEnabled: true, dailyLimitEnabled: true};
    for (const show_in_fullscreen of [true, false]) {
        const prefs = {reminders: [{value: 20, unit: 'minute'}], show_in_fullscreen};
        for (const remaining of [66, 65, 64, 60, 56, 55, 40, 0, NaN]) {
            manager.dailyLimitTime = remaining;
            assert.equal(wellbeingWindowEnd(manager, prefs, false),
                remaining > 55 && remaining <= 65 ? remaining - 55 : 0);
        }
        manager.dailyLimitTime = 62; // Login/resume inside the window.
        assert.equal(wellbeingWindowEnd(manager, prefs, false), 7);
        assert.equal(wellbeingWindowEnd(manager, prefs, true), 0);
        assert.equal(wellbeingWindowEnd(manager, {reminders: []}, false), 0);
        assert.equal(wellbeingWindowEnd(manager, null, false), 0);
        manager.parentalControlsSessionLimitsEnabled = false;
        assert.equal(wellbeingWindowEnd(manager, prefs, false), 0);
        manager.parentalControlsSessionLimitsEnabled = true;
    }
});

test('durable backup precedes suppression, and all original values survive user edits', () => {
    for (const original of ['default', 'true', 'false']) {
        const h = harness(original);
        h.leases.set(':1.2', 110);
        assert.deepEqual(h.writes.slice(0, 4),
            [['backup', original], ['sync'], ['value', 'false'], ['sync']]);
        h.userChange('true');
        h.advance(10);
        h.leases.expire();
        assert.equal(h.value, original);
        assert.equal(h.backup, '');
        assert.equal(h.leases.leases.size, 0);
    }
});

test('overlapping sessions share one snapshot; cancellation only releases its owner', () => {
    const h = harness();
    h.leases.set(':1.2', 110);
    h.advance(2);
    h.leases.set(':1.3', 111);
    h.leases.set(':1.2', 0);
    assert.equal(h.value, 'false');
    assert.equal(h.backup, 'default');
    h.leases.set(':1.3', 0);
    assert.equal(h.value, 'default');
    assert.equal(h.backup, '');
});

test('suspend/forward jump expires by wall time; backward jump cannot prolong a lease', () => {
    for (const [wall, mono] of [[100, 1], [-100, 10]]) {
        const h = harness();
        h.leases.set('sender', 110);
        h.advance(wall, mono);
        h.leases.expire();
        assert.equal(h.value, 'default');
    }
});

test('crash recovery, orderly shutdown and restoration failure preserve recovery state', () => {
    const h = harness('true');
    h.leases.set('sender', 110);
    h.lock(true);
    assert.throws(() => h.create().restore());
    assert.equal(h.backup, 'true');
    h.lock(false);
    h.create().restore();
    assert.equal(h.value, 'true');
    assert.equal(h.backup, '');
    const fresh = h.create();
    fresh.set('sender', 110);
    fresh.close();
    assert.equal(h.value, 'true');
});

test('invalid or expired requests never write settings', () => {
    for (const end of [NaN, Infinity, -1, 99, 100, 111]) {
        const h = harness();
        assert.throws(() => h.leases.set('sender', end));
        assert.deepEqual(h.writes, []);
    }
});

test('lease diagnostics cover suppression, expiry, recovery failure and retry without identities', () => {
    const h = harness();
    const events = [];
    h.leases.observe = (stage, outcome) => events.push([stage, outcome]);
    h.leases.set('PRIVATE-SENDER/TOKEN', 110);
    assert.ok(events.some(([stage, outcome]) => stage === 'banner-suppress' && outcome === 'complete'));
    h.lock(true);
    h.advance(-100, 10);
    assert.throws(() => h.leases.expire());
    assert.ok(events.some(([stage, outcome]) => stage === 'lease-expire' && outcome === 'monotonic'));
    assert.ok(events.some(([stage, outcome]) => stage === 'banner-restore' && outcome === 'failed'));
    assert.equal(h.backup, 'default');
    h.lock(false);
    h.leases.expire();
    assert.ok(events.some(([stage, outcome]) => stage === 'recovery-clear' && outcome === 'complete'));
    assert.ok(!JSON.stringify(events).includes('PRIVATE'));
    assert.ok(!JSON.stringify(events).includes('locked'));
    h.leases.observe = () => { throw Error('logging unavailable'); };
    h.leases.set('PRIVATE-SENDER/TOKEN', 10);
    h.leases.close();
    assert.equal(h.value, 'default');
});

function clientHarness() {
    const events = [];
    const callbacks = [], requests = [], errors = [], timers = new Map(), handlers = new Map();
    const destinations = [], flags = [], watches = new Map();
    let sequence = 0;
    const signalObject = {
        connect: (signal, callback) => { handlers.set(++sequence, callback); return sequence; },
        disconnect: id => handlers.delete(id),
    };
    const manager = {...signalObject, dailyLimitTime: 165, getCurrentTime: () => 100,
        dailyLimitEnabled: true, parentalControlsSessionLimitsEnabled: true};
    const session = {...signalObject, isLocked: false, isGreeter: false};
    let preferences = {reminders: [{}]};
    const context = vm.createContext({wellbeingWindowEnd,
        Gio: {DBusCallFlags: {NONE: 0, NO_AUTO_START: 1}, BusNameWatcherFlags: {NONE: 0},
            bus_watch_name_on_connection: (_bus, _name, _flags, appeared, vanished) => {
                watches.set(++sequence, {appeared, vanished}); return sequence;
            }, bus_unwatch_name: id => watches.delete(id), DBus: {session: {call(...args) {
            requests.push(args[4].value[1]); callbacks.push(args.at(-1));
            destinations.push(args[0]); flags.push(args[6]);
        }}}},
        GLib: {PRIORITY_DEFAULT: 0, SOURCE_CONTINUE: true,
            uuid_string_random: () => '00000000-0000-0000-0000-000000000001',
            Variant: class { constructor(_type, value) { this.value = value; } },
            timeout_add: (_priority, _delay, callback) => {
                timers.set(++sequence, callback); return sequence;
            }, source_remove: id => timers.delete(id)},
    });
    vm.runInContext(readFileSync(new URL('../../child/wellbeingSuppression.js', import.meta.url), 'utf8')
        .replace(/^import .*;\n/gm, '')
        .replace('export class WellbeingSuppression', 'globalThis.Client = class'), context);
    const client = new context.Client(manager, session, () => preferences, error => errors.push(error),
        (stage, outcome) => events.push({stage, outcome}));
    return {client, manager, session, requests, errors, events, timers, handlers, watches, destinations, flags,
        owner: value => {
            for (const watch of watches.values()) {
                if (value) watch.appeared(null, null, value);
                else watch.vanished();
            }
        },
        preferences: value => { preferences = value; },
        reply: (fail = false) => callbacks.shift()({call_finish() {
            if (fail) throw Error('helper unavailable');
        }}, {})};
}

test('client diagnostics validate against the catalogue and distinguish failed/stale replies', () => {
    const h = clientHarness();
    h.owner(':1.PRIVATE');
    h.reply();
    h.reply(true);
    h.client.update();
    h.reply();
    h.client.close();
    h.reply();
    assert.ok(h.events.some(event => event.outcome === 'stale'));
    assert.ok(h.events.some(event => event.stage === 'acquire-request' && event.outcome === 'failed'));
    assert.ok(h.events.some(event => event.stage === 'release-request' && event.outcome === 'complete'));
    const catalog = JSON.parse(readFileSync(new URL(
        '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url), 'utf8'));
    for (const fields of h.events) {
        const envelope = diagnosticEnvelope(catalog, 'child.wellbeing', fields);
        assert.ok(!envelope.includes('PRIVATE'));
        assert.ok(!envelope.includes('helper unavailable'));
    }
});

test('client serializes cancellation behind an in-flight write and releases signal/timer owners', () => {
    const h = clientHarness();
    assert.deepEqual(h.requests, [110]);
    h.client.close();
    assert.deepEqual(h.requests, [110]);
    h.reply();
    assert.deepEqual(h.requests, [110, 0]);
    h.reply();
    assert.equal(h.handlers.size, 0);
    assert.equal(h.timers.size, 0);
    assert.equal(h.watches.size, 0);
    assert.equal(h.flags.at(-1), 1);
});

test('renewal, missing reminders and lock cancel independently of broker countdown', () => {
    for (const change of [h => { h.manager.dailyLimitTime = 300; },
        h => h.preferences({reminders: []}), h => { h.session.isLocked = true; }]) {
        const h = clientHarness();
        h.reply(); change(h); h.client.update(); h.reply();
        assert.deepEqual(h.requests, [110, 0]);
        h.client.close();
    }
});

test('helper failure is contained, retries are bounded by ticks and uncertain writes are cancelled', () => {
    const h = clientHarness();
    h.reply(true);
    assert.equal(h.requests.length, 1);
    h.client.update(); h.reply(true);
    assert.equal(h.errors.length, 1);
    h.client.close(); h.reply();
    assert.deepEqual(h.requests, [110, 110, 0]);
});

test('a restarted helper reacquires the same eligible deadline under its new owner', () => {
    const h = clientHarness();
    h.owner(':1.1'); h.reply(); h.reply();
    assert.deepEqual(h.requests, [110, 110]);
    h.owner(null);
    h.reply(true); // Activation attempt during the restart gap.
    h.owner(':1.2'); h.reply();
    assert.equal(h.requests.at(-1), 110);
    assert.equal(h.destinations.at(-1), ':1.2');
    const count = h.requests.length;
    h.client.update();
    assert.equal(h.requests.length, count);
    h.client.close(); h.reply();
});

test('late replies from an old owner cannot acknowledge a replacement lease', () => {
    for (const fail of [false, true]) {
        const h = clientHarness();
        h.owner(':1.1'); h.reply(); // Initial activation reply is stale.
        h.owner(':1.2');
        h.reply(fail); // Old pinned owner's response arrives after replacement.
        assert.equal(h.destinations.at(-1), ':1.2');
        assert.equal(h.requests.at(-1), 110);
        h.reply();
        h.client.close(); h.reply();
    }
});

test('owner replacement reevaluates expiry and cancellation before reacquiring', () => {
    for (const change of [h => { h.manager.dailyLimitTime = 150; },
        h => h.preferences({reminders: []}), h => { h.session.isLocked = true; }]) {
        const h = clientHarness();
        h.owner(':1.1'); h.reply(); h.reply();
        change(h);
        h.owner(':1.2');
        assert.equal(h.requests.at(-1), 0);
        h.reply(); h.client.close();
    }
});

test('shutdown during owner replacement cancels uncertain writes and detaches the watch', () => {
    const h = clientHarness();
    h.owner(':1.1'); h.reply();
    h.owner(':1.2'); h.client.close();
    h.reply();
    assert.equal(h.requests.at(-1), 0);
    assert.equal(h.flags.at(-1), 1);
    h.reply(true);
    const count = h.requests.length;
    h.owner(':1.3'); h.client.update(); h.client.close();
    assert.equal(h.requests.length, count);
    assert.equal(h.watches.size, 0);
    assert.equal(h.handlers.size, 0);
    assert.equal(h.timers.size, 0);
});
