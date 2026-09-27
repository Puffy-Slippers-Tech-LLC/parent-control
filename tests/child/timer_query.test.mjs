import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {busyRetryDelay} from '../../child/indicatorLogic.mjs';

// Every test owns its VM, fake clock, bus and timers. No processes, real bus,
// filesystem writes or shared mutable state; compatible with child-node peers.
function harness(outcomes, {callDuration = 0, waitDuration = null} = {}) {
    const calls = [];
    const logs = [];
    const waits = [];
    let now = 0;
    class BusError extends Error {
        constructor(code, domain = 'dbus', remote = null) {
            super('private@example.test /home/private secret');
            Object.assign(this, {code, domain, remote});
        }
        matches(domain, code) { return this.domain === domain && this.code === code; }
    }
    const codes = Object.fromEntries([
        'NO_REPLY', 'NAME_HAS_NO_OWNER', 'SERVICE_UNKNOWN', 'TIMEOUT', 'TIMED_OUT',
        'ACCESS_DENIED', 'AUTH_FAILED', 'INVALID_ARGS', 'DISCONNECTED', 'FAILED',
    ].map(code => [code, code]));
    const context = vm.createContext({
        busyRetryDelay,
        logInfo: (event, fields) => logs.push({event, ...fields}),
        logWarning: (event, fields) => logs.push({event, ...fields}),
        GLib: {
            Error: BusError,
            Variant: class { constructor(type, value) { Object.assign(this, {type, value}); } },
            VariantType: class { constructor(type) { this.type = type; } },
            get_monotonic_time: () => now * 1000,
            timeout_add(_priority, delay, callback) {
                waits.push(delay);
                now += waitDuration ?? delay;
                queueMicrotask(callback);
            },
        },
        Gio: {
            DBusError: {...codes, get_remote_error: error => error.remote},
            IOErrorEnum: {TIMED_OUT: 'TIMED_OUT', CANCELLED: 'CANCELLED', INVALID_ARGUMENT: 'INVALID_ARGUMENT'},
            dbus_error_quark: () => 'dbus', io_error_quark: () => 'io',
            DBusCallFlags: {NONE: 0},
            DBus: {system: {call(...args) {
                calls.push(args.slice(0, -1));
                const outcome = outcomes.shift();
                now += Math.min(callDuration, args[7]);
                queueMicrotask(() => args.at(-1)({call_finish() {
                    if (typeof outcome === 'string')
                        throw new BusError(outcome);
                    if (outcome instanceof Error)
                        throw outcome;
                    if (outcome === null)
                        throw new BusError('BUSY', 'io', 'org.freedesktop.MalcontentTimer1.Error.Busy');
                    return {deepUnpack: () => [0, outcome]};
                }}, {}));
            }}},
        },
    });
    const source = readFileSync(new URL('../../child/timerQuery.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace(/^export /gm, '');
    vm.runInContext(source, context);
    return {query: context.queryEstimatedTimes, classify: context.timerErrorCategory,
        BusError, calls, logs, waits};
}

for (const [code, category] of [
    ['NO_REPLY', 'no-reply'], ['NAME_HAS_NO_OWNER', 'no-owner'],
    ['SERVICE_UNKNOWN', 'service-unknown'], ['TIMED_OUT', 'timeout'],
]) {
    test(`wake interruption ${code} reactivates the same timer and recovers`, async () => {
        const expected = {'': [true, 0, 123, 0, 0]};
        const h = harness([code, expected]);
        assert.equal(await h.query(), expected);
        assert.equal(h.calls.length, 2);
        assert.deepEqual(h.calls[0], h.calls[1]);
        assert.equal(h.calls[1][0], 'org.freedesktop.MalcontentTimer1');
        assert.equal(h.calls[1][3], 'GetEstimatedTimes');
        assert.equal(h.calls[1][4].type, '(s)');
        assert.deepEqual(Array.from(h.calls[1][4].value), ['login-session']);
        assert.equal(h.calls[1][7], 5000);
        assert.deepEqual(h.waits, [200]);
        assert.deepEqual(h.logs, [
            {event: 'child.timer-read-failed', category, attempt: 1, retry: true},
            {event: 'child.timer-recovered', attempts: 2},
        ]);
    });
}

test('persistent interruption is bounded, never becomes a zero estimate, and releases the queue', async () => {
    const expected = {'': [true, 0, 60, 0, 0]};
    const h = harness(['NO_REPLY', 'NO_REPLY', 'NO_REPLY', expected]);
    const failed = h.query();
    const next = h.query();
    await assert.rejects(failed, error => error.code === 'NO_REPLY');
    assert.equal(await next, expected);
    assert.equal(h.calls.length, 4);
    assert.deepEqual(h.waits, [200, 200]);
    assert.deepEqual(h.logs.at(-1), {
        event: 'child.timer-read-failed', category: 'no-reply', attempt: 3, retry: false,
    });
});

test('denial, invalid replies and unexpected exceptions are not retried or logged verbatim', async () => {
    for (const outcome of ['ACCESS_DENIED', 'INVALID_ARGS', 'FAILED', new Error('private')]) {
        const h = harness([outcome]);
        await assert.rejects(h.query());
        assert.equal(h.calls.length, 1);
        assert.equal(h.waits.length, 0);
        assert.equal(h.logs[0].retry, false);
        assert(!JSON.stringify(h.logs).includes('private'));
    }
});

test('busy backoff remains bounded and shares one timeout budget', async () => {
    const h = harness(Array(6).fill(null), {callDuration: 5000});
    await assert.rejects(h.query());
    assert(h.calls.length <= 6);
    assert(h.calls.every(call => call[7] > 0 && call[7] <= 5000));
    assert.equal(h.calls.reduce((total, call) => total + call[7], 0) +
        h.waits.reduce((total, delay) => total + delay, 0), 25000);
    assert.equal(h.logs.at(-1).retry, false);
});

test('an overdue retry never starts another read after the budget', async () => {
    const h = harness(['NO_REPLY'], {waitDuration: 26000});
    await assert.rejects(h.query(), error => error.code === 'NO_REPLY');
    assert.equal(h.calls.length, 1);
});

test('unknown remote names and exception contents are reduced to fixed categories', () => {
    const h = harness([]);
    assert.equal(h.classify(new h.BusError('UNKNOWN', 'io', 'private.secret.Error')), 'other');
    assert.equal(h.classify(new h.BusError('TIMED_OUT', 'io')), 'timeout');
    assert.equal(h.classify(new h.BusError('CANCELLED', 'io')), 'cancelled');
    assert.equal(h.classify({get message() { throw new Error('must not read'); }}), 'other');
});
