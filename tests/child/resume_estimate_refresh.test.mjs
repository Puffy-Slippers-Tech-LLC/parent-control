import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {busyRetryDelay} from '../../child/indicatorLogic.mjs';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

const catalog = JSON.parse(readFileSync(new URL(
    '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url)));

// Exercise the real timer client and controller together. Each case owns its
// fake bus, usage history, clock, signals and timers; no live/shared resources.
function harness({active = true, records = [[20, 40]], remaining = 100, now = 100} = {}) {
    const calls = [];
    const reports = [];
    const logs = [];
    const timers = new Map();
    const deferred = [];
    let nextTimer = 0;
    let hold = false;
    let failure = null;
    let failureMethod = null;
    const manager = {
        parentalControlsSessionLimitsEnabled: true, dailyLimitTime: active ? 200 : 0,
        handlers: new Map(), nextId: 0,
        connect(signal, callback) {
            const id = ++this.nextId;
            this.handlers.set(id, {signal, callback});
            return id;
        },
        disconnect(id) { this.handlers.delete(id); },
        emit(signal = 'notify::daily-limit-time') {
            for (const handler of [...this.handlers.values()])
                if (handler.signal === signal) handler.callback();
        },
    };
    class BusError extends Error {
        matches(_domain, code) { return code === failure; }
    }
    const context = vm.createContext({
        busyRetryDelay, logInfo() {}, logWarning(event, fields) {
            logs.push(JSON.parse(diagnosticEnvelope(catalog, event,
                JSON.parse(JSON.stringify(fields)))));
        },
        GLib: {
            Error: BusError,
            Variant: class { constructor(type, value) { Object.assign(this, {type, value}); } },
            VariantType: class { constructor(type) { this.type = type; } },
            get_real_time: () => now * 1_000_000, get_monotonic_time: () => now * 1_000_000,
            timeout_add(_priority, delay, callback) {
                const id = ++nextTimer;
                timers.set(id, {delay, callback});
                return id;
            },
            source_remove: id => timers.delete(id), SOURCE_REMOVE: false,
        },
        Gio: {
            Cancellable: class {
                cancel() { this.cancelled = true; }
                is_cancelled() { return Boolean(this.cancelled); }
            },
            Credentials: {new: () => ({get_unix_user: () => 1003})},
            DBusError: {get_remote_error: () => null, NO_REPLY: 'NO_REPLY', ACCESS_DENIED: 'ACCESS_DENIED'},
            IOErrorEnum: {}, dbus_error_quark: () => 'dbus', io_error_quark: () => 'io',
            DBusCallFlags: {NONE: 0},
            DBus: {system: {call(...args) {
                calls.push(args);
                const finish = () => args.at(-1)({call_finish() {
                    if (failure && (!failureMethod || failureMethod === args[3])) throw new BusError();
                    if (args[3] === 'RecordUsage') manager.emit();
                    return {deepUnpack: () => args[3] === 'QueryUsage' ? [records]
                        : args[3] === 'GetEstimatedTimes' ? [Math.floor(now), {'': [false, 0, Math.floor(now) + remaining]}]
                        : []};
                }}, {});
                if (hold) deferred.push(finish);
                else queueMicrotask(finish);
            }}},
        },
    });
    for (const file of ['timerQuery.js', 'resumeEstimateRefresh.js'])
        vm.runInContext(readFileSync(new URL('../../child/' + file, import.meta.url), 'utf8')
            .replace(/^import[\s\S]*?;\n/gm, '').replace(/^export /gm, '')
            .replace('class ResumeEstimateRefresh', 'globalThis.ResumeEstimateRefresh = class'), context);
    const bridge = new context.ResumeEstimateRefresh(manager, error => reports.push(error));
    return {bridge, calls, reports, logs, timers, manager, records,
        query: context.queryEstimatedTimes,
        setRemaining: value => { remaining = value; },
        setFailure: (value, method = null) => { failure = value; failureMethod = method; },
        setHold: value => { hold = value; },
        release: () => deferred.splice(0).forEach(finish => finish()),
        activity(active) { manager.dailyLimitTime = active ? now + remaining : 0; manager.emit(); },
        tick() {
            const [id, timer] = timers.entries().next().value;
            timers.delete(id);
            timer.callback();
        }};
}

const settle = async () => { for (let i = 0; i < 50; i++) await Promise.resolve(); };
const plain = value => JSON.parse(JSON.stringify(value));

test('continuous use and repeated native estimate notifications never restart the countdown', async () => {
    const h = harness();
    h.manager.emit();
    h.manager.dailyLimitTime++;
    h.manager.emit();
    await settle();
    assert.equal(h.calls.length, 0);
    assert.equal(h.timers.size, 0);
    h.bridge.close();
});

test('idle and resume replay exact self-read endpoints and ignore estimate echoes', async () => {
    const h = harness();
    h.activity(false);
    await settle();
    assert.deepEqual(h.calls.map(call => call[3]), ['QueryUsage', 'RecordUsage', 'GetEstimatedTimes']);
    assert.equal(h.calls[0][2], 'org.freedesktop.MalcontentTimer1.Parent');
    assert.deepEqual(plain(h.calls[0][4].value), [1003, 'login-session', '']);
    assert.deepEqual(plain(h.calls[1][4].value), [[[20, 40, 'login-session', '']]]);
    assert.equal([...h.timers.values()][0].delay, 50_000);
    h.activity(true);
    await settle();
    assert.equal(h.calls.length, 6);
    assert.equal(h.timers.size, 0);
    h.manager.emit();
    await settle();
    assert.equal(h.calls.length, 6, 'the replay signal must not create a feedback loop');
    h.bridge.close();
});

test('a completed single-second record retains its inclusive endpoints', async () => {
    const h = harness({active: false, records: [[40, 40]]});
    await settle();
    assert.deepEqual(plain(h.calls[1][4].value), [[[40, 40, 'login-session', '']]]);
    h.bridge.close();
});

test('shutdown after dispatch cannot unsend a write but prevents all successor work', async () => {
    const h = harness();
    h.setHold(true);
    h.activity(false);
    await settle();
    h.release();
    await settle();
    assert.deepEqual(h.calls.map(call => call[3]), ['QueryUsage', 'RecordUsage']);
    h.bridge.close();
    h.release();
    await settle();
    assert.equal(h.calls.length, 2);
    assert.equal(h.timers.size, 0);
    assert.equal(h.reports.length, 0);
});

test('idle refresh precedes the native deadline, including fractional time near exhaustion', async () => {
    for (const [remaining, now, delay] of [[1000, 100, 60_000], [20, 100, 10_000], [2, 100.75, 625]]) {
        const h = harness({active: false, remaining, now});
        await settle();
        assert.equal([...h.timers.values()][0].delay, delay);
        h.tick();
        await settle();
        assert.equal(h.calls.length, 6);
        h.bridge.close();
        assert.equal(h.timers.size, 0);
    }
});

test('an exhausted balance ignores delayed estimate echoes and restarts on native policy/day changes', async () => {
    const h = harness({active: false, remaining: 0});
    await settle();
    assert.equal(h.timers.size, 0);
    // Shell queries asynchronously after the replay signal. Its notification
    // can arrive after the controller has finished, not only during the write.
    h.manager.emit();
    await settle();
    assert.equal(h.calls.length, 3, 'an estimate echo must not start another replay');
    h.manager.emit('notify::daily-limit-enabled');
    await settle();
    assert.equal(h.calls.length, 6);
    assert.equal(h.timers.size, 0);
    h.setRemaining(120);
    h.manager.emit('notify::state');
    await settle();
    assert.equal(h.calls.length, 9, 'a new native day/state can restart maintenance');
    assert.equal([...h.timers.values()][0].delay, 60_000,
        'restored allowance must resume inactive deadline maintenance');
    h.bridge.close();
});

test('disabling limits discards a coalesced resume before active reenable', async () => {
    const h = harness();
    h.setHold(true);
    h.activity(false);
    await settle();
    h.activity(true);
    h.manager.parentalControlsSessionLimitsEnabled = false;
    h.manager.emit('notify::daily-limit-enabled');
    h.manager.parentalControlsSessionLimitsEnabled = true;
    h.manager.emit('notify::daily-limit-enabled');
    h.setHold(false);
    h.release();
    await settle();
    assert.equal(h.calls.length, 1, 'the obsolete boundary must not replay during active use');
    assert.equal(h.timers.size, 0);
    h.bridge.close();
});

test('empty, invalid and future history never produces an empty or fabricated usage write', async () => {
    for (const records of [[], [[101, 102]], [[40, 20]], [[-1, 20]]]) {
        const h = harness({active: false, records});
        await settle();
        assert.deepEqual(h.calls.map(call => call[3]), ['QueryUsage']);
        assert.equal(h.reports.length, 0);
        h.bridge.close();
    }
});

test('resume during an idle read cancels its write and coalesces the new boundary', async () => {
    const h = harness();
    h.setHold(true);
    h.activity(false);
    await settle();
    h.activity(true);
    h.manager.emit();
    assert.equal(h.calls.length, 1);
    h.setHold(false);
    h.release();
    await settle();
    assert.equal(h.calls[0][8].is_cancelled(), true);
    assert.deepEqual(h.calls.map(call => call[3]), ['QueryUsage', 'QueryUsage', 'RecordUsage', 'GetEstimatedTimes']);
    assert.equal(h.timers.size, 0);
    h.bridge.close();
});

test('a cancelled boundary waiting behind an estimate never dispatches its usage query', async () => {
    const h = harness();
    h.setHold(true);
    const estimate = h.query();
    h.activity(false);
    await settle();
    h.activity(true);
    h.setHold(false);
    h.release();
    await estimate;
    await settle();
    assert.deepEqual(h.calls.map(call => call[3]),
        ['GetEstimatedTimes', 'QueryUsage', 'RecordUsage', 'GetEstimatedTimes']);
    assert.equal(h.timers.size, 0);
    h.manager.emit();
    await settle();
    assert.equal(h.calls.length, 4);
    h.bridge.close();
});

test('shutdown or disabling limits during a read prevents late writes', async () => {
    for (const close of [true, false]) {
        const h = harness();
        h.setHold(true);
        h.activity(false);
        await settle();
        if (close) h.bridge.close();
        else {
            h.manager.parentalControlsSessionLimitsEnabled = false;
            h.manager.emit('notify::daily-limit-enabled');
        }
        h.setHold(false);
        h.release();
        await settle();
        assert.equal(h.calls.length, 1);
        assert.equal(h.calls[0][8].is_cancelled(), true);
        assert.equal(h.timers.size, 0);
        assert.equal(h.reports.length, 0);
        h.bridge.close();
        assert.equal(h.manager.handlers.size, 0);
    }
});

test('idle transient failures back off; denial and resume failures never replay late active usage', async () => {
    const idle = harness();
    idle.setFailure('NO_REPLY');
    idle.activity(false);
    await settle();
    assert.equal([...idle.timers.values()][0].delay, 1000);
    idle.tick(); await settle();
    assert.equal([...idle.timers.values()][0].delay, 2000);
    idle.tick(); await settle();
    assert.equal(idle.reports.length, 1);
    assert.deepEqual(idle.logs.filter(log => log.event === 'child.resume-refresh-failed')
        .map(log => log.fields), [1, 2, 3].map(failures => ({
            stage: 'query-usage', category: 'no-reply', active: false,
            limit_enabled: true, failures, retry: true, delay_ms: 1000 * 2 ** (failures - 1),
        })));
    idle.activity(true);
    await settle();
    assert.equal(idle.timers.size, 0);
    idle.bridge.close();

    const denied = harness();
    denied.setFailure('ACCESS_DENIED');
    denied.activity(false);
    await settle();
    assert.equal(denied.calls.length, 1);
    assert.equal(denied.timers.size, 0);
    assert.equal(denied.reports.length, 1);
    denied.bridge.close();
});

test('resume diagnostics identify the failing timer operation without recording usage or identity', async () => {
    for (const [method, stage] of [['QueryUsage', 'query-usage'], ['RecordUsage', 'record-usage'],
        ['GetEstimatedTimes', 'timer-estimate']]) {
        const h = harness({remaining: 0});
        h.activity(false);
        await settle();
        h.setFailure('ACCESS_DENIED', method);
        h.activity(true);
        await settle();
        const failure = h.logs.find(log => log.event === 'child.resume-refresh-failed');
        assert.deepEqual(failure.fields, {stage, category: 'access-denied', active: true,
            limit_enabled: true, failures: 1, retry: false, delay_ms: 0});
        assert.equal(h.reports.length, 1);
        assert.equal(h.timers.size, 0, 'diagnostics must not enable late active usage replays');
        assert(!JSON.stringify(h.logs).includes('1003'));
        assert(!JSON.stringify(h.logs).includes('login-session'));
        h.bridge.close();
    }
});
