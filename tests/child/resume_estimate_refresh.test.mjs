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
    let holdNextWrite = false;
    let failure = null;
    let failureMethod = null;
    let clockOffset = 0;
    let shiftAfterRead = null;
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
        constructor(code, iface) {
            super('private@example.test /home/private secret');
            Object.assign(this, {code, iface});
        }
        matches(_domain, code) { return code === this.code; }
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
            get_real_time() {
                const value = (now + clockOffset) * 1_000_000;
                if (shiftAfterRead !== null) [clockOffset, shiftAfterRead] = [shiftAfterRead, null];
                return value;
            },
            get_monotonic_time: () => now * 1_000_000,
            timeout_add(_priority, delay, callback) {
                const id = ++nextTimer;
                timers.set(id, {delay, callback});
                return id;
            },
            source_remove: id => timers.delete(id), SOURCE_REMOVE: false,
        },
        Gio: {
            Cancellable: class {
                handlers = new Map();
                lastId = 0;
                cancel() {
                    this.cancelled = true;
                    for (const handler of this.handlers.values()) handler();
                }
                is_cancelled() { return Boolean(this.cancelled); }
                set_error_if_cancelled() {
                    if (this.cancelled) throw new BusError('CANCELLED');
                }
                connect(handler) {
                    const id = ++this.lastId;
                    this.handlers.set(id, handler);
                    return id;
                }
                disconnect(id) { this.handlers.delete(id); }
            },
            Credentials: {new: () => ({get_unix_user: () => 1003})},
            DBusError: {
                ...Object.fromEntries(['NO_REPLY', 'NAME_HAS_NO_OWNER', 'SERVICE_UNKNOWN',
                    'TIMED_OUT', 'ACCESS_DENIED'].map(code => [code, code])),
                get_remote_error: error => error.code === 'BUSY'
                    ? `${error.iface}.Error.Busy`
                    : error.code === 'IDENTIFYING_USER' ? `${error.iface}.Error.IdentifyingUser`
                    : error.code === 'UNREVIEWED_BUSY' ? 'private.secret.Error.Busy' : null,
            },
            IOErrorEnum: {CANCELLED: 'CANCELLED'}, dbus_error_quark: () => 'dbus', io_error_quark: () => 'io',
            DBusCallFlags: {NONE: 0},
            DBus: {system: {call(...args) {
                calls.push(args);
                const finish = () => args.at(-1)({call_finish() {
                    if (failure && (!failureMethod || failureMethod === args[3])) throw new BusError(failure, args[2]);
                    if (args[3] === 'RecordUsage') manager.emit();
                    return {deepUnpack: () => args[3] === 'QueryUsage' ? [records]
                        : args[3] === 'GetEstimatedTimes' ? [Math.floor(now), {'': [false, 0, Math.floor(now) + remaining]}]
                        : []};
                }}, {});
                if (holdNextWrite && args[3] === 'RecordUsage') {
                    holdNextWrite = false;
                    const token = args[8];
                    let resolved = false;
                    const complete = () => {
                        if (resolved) return;
                        resolved = true;
                        token.disconnect(handler);
                        if (token.is_cancelled()) {
                            args.at(-1)({call_finish() { throw new BusError('CANCELLED'); }}, {});
                        } else finish();
                    };
                    const handler = token.connect(() => queueMicrotask(complete));
                    deferred.push(complete);
                } else if (hold) deferred.push(finish);
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
        setNow: value => { now = value; },
        setClockOffset: value => { clockOffset = value; },
        // Change the wall clock after the next read, between selection and dispatch.
        setClockOffsetAfterRead: value => { shiftAfterRead = value; },
        setRemaining: value => { remaining = value; },
        setFailure: (value, method = null) => { failure = value; failureMethod = method; },
        setHold: value => { hold = value; },
        holdNextWrite: () => { holdNextWrite = true; },
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
const usageWrites = h => h.calls.filter(call => call[3] === 'RecordUsage')
    .map(call => plain(call[4].value)[0]);

async function exhaustCheckpointRetries(h) {
    for (const delay of [100, 250, 500, 1000, 2000]) {
        assert.deepEqual([...h.timers.values()].map(timer => timer.delay), [delay]);
        h.tick();
        await settle();
    }
    assert.equal(h.timers.size, 0);
}

function checkpoint(h, now) {
    h.setNow(now);
    h.manager.dailyLimitTime++;
    h.manager.emit();
}

test('closing the resume refresh cancels estimate backoff and releases the timer queue', async () => {
    const h = harness({active: false});
    h.setFailure('NO_REPLY', 'GetEstimatedTimes');
    await settle();
    assert.deepEqual([...h.timers.values()].map(timer => timer.delay), [200]);
    h.setFailure(null);
    const next = h.query();
    h.bridge.close();
    await settle();
    assert.equal(h.timers.size, 0);
    assert.equal(h.calls.filter(args => args[3] === 'GetEstimatedTimes').length, 2);
    assert.equal((await next)[''][2], 200);
    assert.equal(h.reports.length, 0);
});

test('continuous use and unchanged native notifications do not write usage', async () => {
    const h = harness();
    h.manager.emit();
    h.manager.dailyLimitTime--;
    h.manager.emit();
    await settle();
    assert.equal(h.calls.length, 0);
    assert.equal(h.timers.size, 0);
    h.bridge.close();
});

test('idle replays self-read endpoints; resume checkpoints observed activity and ignores echoes', async () => {
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
    assert.deepEqual(plain(h.calls[4][4].value), [[[100, 100, 'login-session', '']]]);
    assert.equal(h.timers.size, 0);
    h.manager.emit();
    await settle();
    assert.equal(h.calls.length, 6, 'the replay signal must not create a feedback loop');
    h.bridge.close();
});

test('a peer estimate reset checkpoints ongoing use through queue and read delays', async () => {
    const h = harness({records: []});
    h.setHold(true);
    const estimate = h.query();
    await settle();
    h.setNow(125);
    h.manager.dailyLimitTime = 225;
    h.manager.emit();
    await settle();
    assert.deepEqual(h.calls.map(call => call[3]), ['GetEstimatedTimes']);
    h.setNow(130);
    h.release();
    await estimate;
    await settle();
    assert.equal(h.calls.at(-1)[3], 'QueryUsage');
    h.setNow(135);
    h.setHold(false);
    h.release();
    await settle();
    assert.deepEqual(plain(h.calls.find(call => call[3] === 'RecordUsage')[4].value),
        [[[100, 135, 'login-session', '']]]);
    assert.equal(h.calls.length, 4);
    assert.equal(h.timers.size, 0);
    h.manager.emit();
    await settle();
    assert.equal(h.calls.length, 4, 'checkpoint echoes must not create a write loop');
    h.bridge.close();
});

test('a new active interval excludes time spent inactive from corrective checkpoints', async () => {
    const h = harness();
    h.setNow(120);
    h.activity(false);
    await settle();
    h.setNow(170);
    h.activity(true);
    await settle();
    h.setNow(180);
    h.manager.dailyLimitTime += 10;
    h.manager.emit();
    await settle();
    assert.deepEqual(plain(h.calls.at(-2)[4].value), [[[170, 180, 'login-session', '']]]);
    h.bridge.close();
});

test('a busy checkpoint retries its exact timestamps across inactivity while estimates proceed', async () => {
    const h = harness();
    h.setFailure('BUSY', 'RecordUsage');
    checkpoint(h, 130);
    await settle();
    const observed = [[100, 130, 'login-session', '']];
    assert.deepEqual(usageWrites(h), [observed]);
    assert.deepEqual([...h.timers.values()].map(timer => timer.delay), [100]);
    assert.equal((await h.query())[''][2], 230);
    h.setNow(140);
    h.setFailure(null);
    h.activity(false);
    await settle();
    assert.deepEqual(h.calls.map(call => call[3]), [
        'QueryUsage', 'RecordUsage', 'GetEstimatedTimes', 'QueryUsage', 'RecordUsage', 'GetEstimatedTimes',
    ]);
    assert.deepEqual(usageWrites(h), [observed, observed]);
    assert.deepEqual([...h.timers.values()].map(timer => timer.delay), [50_000]);
    assert.equal(h.reports.length, 0);
    h.bridge.close();
});

test('an exhausted checkpoint is included with later disjoint activity and cleared on acknowledgement', async () => {
    const h = harness();
    h.setFailure('BUSY', 'RecordUsage');
    checkpoint(h, 130);
    await settle();
    await exhaustCheckpointRetries(h);
    const older = [100, 130, 'login-session', ''];
    assert.deepEqual(usageWrites(h), Array(6).fill([older]));
    assert.equal(h.logs.at(-1).event, 'child.resume-refresh-deferred');

    h.setFailure('BUSY', 'QueryUsage');
    h.activity(false);
    await settle();
    h.setFailure(null);
    h.setHold(true);
    h.setNow(160);
    h.activity(true);
    await settle();
    h.setNow(165);
    h.setHold(false);
    h.release();
    await settle();
    assert.deepEqual(usageWrites(h).at(-1), [older, [160, 165, 'login-session', '']]);
    checkpoint(h, 170);
    await settle();
    assert.deepEqual(usageWrites(h).at(-1), [[160, 170, 'login-session', '']]);
    assert.equal(h.reports.length, 0);
    h.bridge.close();
});

test('a new activity period interrupts old backoff and keeps the prior observed interval', async () => {
    const h = harness();
    h.setFailure('BUSY', 'RecordUsage');
    checkpoint(h, 130);
    await settle();
    h.setFailure('BUSY', 'QueryUsage');
    h.activity(false);
    await settle();
    assert.deepEqual([...h.timers.values()].map(timer => timer.delay), [1000]);
    h.setFailure(null);
    h.setHold(true);
    h.setNow(132);
    h.activity(true);
    await settle();
    h.setNow(133);
    h.setHold(false);
    h.release();
    await settle();
    const older = [100, 130, 'login-session', ''];
    assert.deepEqual(usageWrites(h), [[older], [older, [132, 133, 'login-session', '']]]);
    assert.equal(h.timers.size, 0);
    h.bridge.close();
});

test('an in-flight checkpoint releases the refresh on lock and retains the submitted interval', async () => {
    const h = harness({records: []});
    h.holdNextWrite();
    checkpoint(h, 130);
    await settle();
    const older = [[100, 130, 'login-session', '']];
    assert.deepEqual(usageWrites(h), [older]);

    h.setNow(130.5);
    h.activity(false);
    await settle();
    assert.deepEqual(usageWrites(h), [older, older]);
    h.setNow(131);
    h.activity(true);
    await settle();
    checkpoint(h, 132);
    await settle();
    h.setNow(133);
    h.activity(false);
    await settle();
    assert.deepEqual(usageWrites(h), [older, older,
        [[131, 131, 'login-session', '']], [[131, 132, 'login-session', '']]]);
    h.release();
    await settle();
    assert.equal(usageWrites(h).length, 4, 'a late result must not start additional work');
    assert.equal(h.reports.length, 0);
    h.bridge.close();
});

test('a briefly future checkpoint stays inside the bounded retry window after a small rollback', async () => {
    const h = harness();
    h.setFailure('BUSY', 'RecordUsage');
    checkpoint(h, 130.05);
    await settle();
    const observed = [[100, 130, 'login-session', '']];
    assert.deepEqual(usageWrites(h), [observed]);

    h.setFailure(null);
    h.setClockOffset(-0.3);
    h.setNow(130.15);
    h.tick();
    await settle();
    assert.deepEqual(usageWrites(h), [observed]);
    assert.deepEqual([...h.timers.values()].map(timer => timer.delay), [250]);
    h.setNow(130.4);
    h.tick();
    await settle();
    assert.deepEqual(usageWrites(h), [observed, observed]);
    assert.equal(h.timers.size, 0);
    h.bridge.close();
});

test('a timed-out checkpoint keeps its interval for the next refresh', async () => {
    const observed = [[100, 130, 'login-session', '']];
    for (const code of ['TIMED_OUT', 'NO_REPLY']) {
        const h = harness();
        h.setFailure(code, 'RecordUsage');
        checkpoint(h, 130);
        await settle();
        assert.deepEqual(usageWrites(h), [observed]);
        assert.equal(h.timers.size, 0, 'a timed-out write is not retried during active use');
        assert.equal(h.reports.length, 0);
        h.setFailure(null);
        h.setNow(140);
        h.activity(false);
        await settle();
        assert.deepEqual(usageWrites(h), [observed, observed]);
        assert.equal(h.bridge.checkpoints.size, 0);
        h.bridge.close();
    }
});

test('a rollback that outlasts the retry window keeps the observation for the next refresh', async () => {
    const h = harness();
    h.setClockOffsetAfterRead(-0.5);
    checkpoint(h, 130.2);
    await settle();
    await exhaustCheckpointRetries(h);
    assert.deepEqual(usageWrites(h), [], 'a future endpoint must never be sent');
    assert.equal(h.reports.length, 0);
    h.setNow(140);
    h.activity(false);
    await settle();
    assert.deepEqual(usageWrites(h), [[[100, 130, 'login-session', '']]]);
    assert.equal(h.bridge.checkpoints.size, 0);
    h.bridge.close();
});

test('a same-second resume keeps the recovery batch free of zero-length intervals', async () => {
    const h = harness();
    h.setFailure('BUSY', 'RecordUsage');
    checkpoint(h, 130);
    await settle();
    h.setFailure('BUSY', 'QueryUsage');
    h.activity(false);
    await settle();
    h.setFailure(null);
    h.setNow(140);
    h.activity(true);
    await settle();
    assert.deepEqual(usageWrites(h), Array(2).fill([[100, 130, 'login-session', '']]));
    h.bridge.close();
});

test('clock corrections retire old pending checkpoints and leave shifted native history intact', async () => {
    for (const offset of [-50, 300]) {
        const h = harness({records: []});
        h.setFailure('BUSY', 'RecordUsage');
        checkpoint(h, 130);
        await settle();
        // Test correction during the immediate backoff and after exhaustion.
        if (offset > 0) await exhaustCheckpointRetries(h);
        const oldAttempts = usageWrites(h).length;
        h.setFailure(null);
        h.setClockOffset(offset);
        if (offset < 0) h.tick();
        else checkpoint(h, 140);
        await settle();
        assert.equal(usageWrites(h).length, oldAttempts);

        h.setNow(185);
        const shifted = [100 + offset, 185 + offset];
        h.records.push(shifted);
        h.activity(false);
        await settle();
        assert.deepEqual(usageWrites(h).slice(oldAttempts), [[[
            ...shifted, 'login-session', '',
        ]]]);
        assert.equal(h.reports.length, 0);
        h.bridge.close();
    }
});

test('successive small clock corrections are measured from the start of observed activity', async () => {
    const h = harness({now: 100.6, records: []});
    h.setFailure('BUSY', 'RecordUsage');
    h.setClockOffset(0.7);
    checkpoint(h, 130.6);
    await settle();
    assert.deepEqual(usageWrites(h), [[[100, 131, 'login-session', '']]]);

    h.setFailure(null);
    h.setClockOffset(1.6);
    h.setNow(130.7);
    h.tick();
    await settle();
    assert.deepEqual(usageWrites(h), [[[100, 131, 'login-session', '']]]);
    assert.equal(h.timers.size, 0);

    h.setNow(140);
    h.records.push([102, 141]);
    h.activity(false);
    await settle();
    assert.deepEqual(usageWrites(h).at(-1), [[102, 141, 'login-session', '']]);
    assert.equal(h.reports.length, 0);
    h.bridge.close();
});

test('an older prefix remains eligible when a newer Busy checkpoint crosses its clock tolerance', async () => {
    const h = harness();
    h.setFailure('BUSY', 'RecordUsage');
    checkpoint(h, 130);
    await settle();
    await exhaustCheckpointRetries(h);
    const older = [[100, 130, 'login-session', '']];
    assert.deepEqual(usageWrites(h), Array(6).fill(older));

    h.setClockOffset(0.8);
    checkpoint(h, 149.3);
    await settle();
    assert.deepEqual(usageWrites(h).at(-1), [[100, 150, 'login-session', '']]);
    h.setFailure(null);
    h.setClockOffset(-0.4);
    h.setNow(149.4);
    h.tick();
    await settle();
    assert.equal(usageWrites(h).length, 8);
    assert.deepEqual(usageWrites(h).at(-1), older);
    assert.equal(h.timers.size, 0);
    h.bridge.close();
});

test('disabling limits or closing the controller cancels a pending checkpoint retry', async () => {
    for (const close of [false, true]) {
        const h = harness();
        h.setFailure('BUSY', 'RecordUsage');
        checkpoint(h, 130);
        await settle();
        assert.equal(h.timers.size, 1);
        if (close) h.bridge.close();
        else {
            h.manager.parentalControlsSessionLimitsEnabled = false;
            h.manager.emit('notify::daily-limit-enabled');
        }
        await settle();
        assert.equal(h.timers.size, 0);
        assert.equal(usageWrites(h).length, 1);
        assert.equal(h.reports.length, 0);
        if (!close) {
            // The native getter can stay positive for a Wellbeing-only limit.
            h.setFailure(null);
            h.setNow(160);
            h.manager.parentalControlsSessionLimitsEnabled = true;
            h.manager.emit('notify::daily-limit-enabled');
            checkpoint(h, 170);
            await settle();
            assert.deepEqual(usageWrites(h).at(-1), [[160, 170, 'login-session', '']]);
        }
        h.bridge.close();
    }
});

test('a subsecond backward clock correction during resume cannot send a reversed interval', async () => {
    const h = harness({now: 100.1});
    h.activity(false);
    await settle();
    const before = h.calls.length;
    h.setHold(true);
    h.activity(true);
    await settle();
    h.setNow(100.2);
    h.setClockOffset(-0.5);
    h.setHold(false);
    h.release();
    await settle();
    assert.deepEqual(h.calls.slice(before).map(call => call[3]), ['QueryUsage']);
    assert.equal(h.reports.length, 0);
    h.bridge.close();
});

for (const offset of [300, -150]) {
    test(`a ${offset}-second clock correction cannot double-charge earlier checkpoints`, async () => {
        const h = harness();
        h.setNow(150);
        h.manager.dailyLimitTime += 50;
        h.manager.emit();
        await settle();
        const writes = () => h.calls.filter(call => call[3] === 'RecordUsage')
            .map(call => plain(call[4].value)[0][0]);
        assert.deepEqual(writes(), [[100, 150, 'login-session', '']]);
        h.setNow(200);
        h.setClockOffset(offset);
        h.manager.dailyLimitTime += 50;
        h.manager.emit();
        await settle();
        assert.deepEqual(writes(), [[100, 150, 'login-session', '']],
            'the merged usage must remain the original 51 inclusive seconds');
        assert.equal(h.timers.size, 0);
        assert.equal(h.reports.length, 0);
        // Native activity transitions establish a fresh wall-clock boundary.
        h.activity(false);
        await settle();
        h.activity(true);
        await settle();
        assert.deepEqual(writes().at(-1), [200 + offset, 200 + offset, 'login-session', '']);
        h.bridge.close();
    });
}

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

test('temporary resume failures preserve the active deadline without reporting or replaying late usage', async () => {
    for (const [code, category] of [['BUSY', 'busy'], ['NO_REPLY', 'no-reply'],
        ['NAME_HAS_NO_OWNER', 'no-owner'], ['SERVICE_UNKNOWN', 'service-unknown'],
        ['TIMED_OUT', 'timeout']]) {
        for (const [method, stage] of [['QueryUsage', 'query-usage'], ['RecordUsage', 'record-usage']]) {
            const h = harness({remaining: 0});
            h.activity(false);
            await settle();
            h.setRemaining(292);
            h.setFailure(code, method);
            h.activity(true);
            const deadline = h.manager.dailyLimitTime;
            await settle();
            assert.equal(h.reports.length, 0, `${method} ${code} must not open a reporter`);
            assert.equal(h.timers.size, 0, 'active use must never schedule another replay');
            assert.equal(h.manager.dailyLimitTime, deadline);
            assert.deepEqual(h.logs.at(-1), {
                v: 1, event: 'child.resume-refresh-deferred', operation: 0, fields: {stage, category},
            });
            const calls = h.calls.length;
            h.manager.emit();
            h.manager.emit('notify::state');
            await settle();
            assert.equal(h.calls.length, calls, 'active notifications must not retry usage writes');
            h.setFailure(null);
            h.activity(false);
            await settle();
            assert.deepEqual(h.calls.slice(calls).map(call => call[3]),
                ['QueryUsage', 'RecordUsage', 'GetEstimatedTimes']);
            assert.deepEqual(plain(h.calls.at(-2)[4].value), [[[20, 40, 'login-session', '']]]);
            assert.equal(h.reports.length, 0);
            assert.equal(h.timers.size, 1, 'next inactivity must resume normal maintenance');
            h.bridge.close();
        }
    }
});

test('persistent idle contention reports once, then recovers through the normal backoff', async () => {
    for (const method of ['QueryUsage', 'RecordUsage']) {
        const h = harness();
        h.setFailure('BUSY', method);
        h.activity(false);
        await settle();
        for (const delay of [1000, 2000, 4000]) {
            assert.equal([...h.timers.values()][0].delay, delay);
            h.tick();
            await settle();
        }
        assert.equal(h.reports.length, 1);
        assert.equal(h.calls.filter(call => call[3] === 'RecordUsage').length,
            method === 'RecordUsage' ? 4 : 0);
        assert.equal(h.calls.filter(call => call[3] === 'GetEstimatedTimes').length, 0);
        assert.equal(h.logs.some(log => log.event === 'child.resume-refresh-deferred'), false);
        assert(h.logs.every(log => log.fields.category === 'busy'));
        h.setFailure(null);
        h.tick();
        await settle();
        assert.deepEqual(h.calls.slice(-3).map(call => call[3]),
            ['QueryUsage', 'RecordUsage', 'GetEstimatedTimes']);
        assert.equal(h.reports.length, 1);
        assert.equal(h.bridge.failures, 0);
        assert.equal(h.bridge.reported, false);
        h.bridge.close();
    }
});

test('native identity failures report immediately at every timer stage, including a finite active deadline', async () => {
    for (const active of [false, true]) {
        for (const [method, stage] of [['QueryUsage', 'query-usage'], ['RecordUsage', 'record-usage'],
            ['GetEstimatedTimes', 'timer-estimate']]) {
            const h = harness({remaining: 0});
            if (active) {
                h.activity(false);
                await settle();
                h.setRemaining(292);
            }
            const before = h.calls.length;
            h.setFailure('IDENTIFYING_USER', method);
            h.activity(active);
            await settle();
            assert.equal(h.calls.slice(before).filter(call => call[3] === method).length, 1);
            assert.equal(h.reports.length, 1, `${method} identity failure must open a reporter`);
            assert.equal(h.reports[0].code, 'IDENTIFYING_USER');
            assert.equal(h.timers.size, 0, 'identity failures must not schedule recovery');
            assert.deepEqual(h.logs.at(-1).fields, {
                stage, category: 'other', active, limit_enabled: true,
                failures: 1, retry: false, delay_ms: 0,
            });
            assert.equal(h.logs.some(log => log.event === 'child.resume-refresh-deferred'), false);
            assert(!JSON.stringify(h.logs).includes('private'));
            assert(!JSON.stringify(h.logs).includes('IdentifyingUser'));
            h.bridge.close();
        }
    }
});

test('resume-only failures escalate across healthy idle refreshes and reset after active recovery', async () => {
    for (const method of ['QueryUsage', 'RecordUsage']) {
        const h = harness();
        for (let occurrence = 1; occurrence <= 4; occurrence++) {
            h.setFailure(null);
            h.activity(false);
            await settle();
            h.setFailure('BUSY', method);
            h.activity(true);
            await settle();
            assert.equal(h.reports.length, occurrence < 3 ? 0 : 1,
                `${method} occurrence ${occurrence} must escalate once from the third failure`);
            assert.equal(h.timers.size, 0, 'escalation must never schedule an active usage replay');
            if (occurrence >= 3) assert.deepEqual(h.logs.at(-1).fields, {
                stage: method === 'QueryUsage' ? 'query-usage' : 'record-usage',
                category: 'busy', active: true, limit_enabled: true,
                failures: occurrence, retry: false, delay_ms: 0,
            });
        }
        h.setFailure(null);
        h.activity(false);
        await settle();
        h.activity(true);
        await settle();
        for (let occurrence = 1; occurrence <= 3; occurrence++) {
            h.setFailure(null);
            h.activity(false);
            await settle();
            h.setFailure('NO_REPLY', method);
            h.activity(true);
            await settle();
            assert.equal(h.reports.length, occurrence < 3 ? 1 : 2,
                'a complete successful active refresh must begin a fresh failure incident');
            assert.equal(h.timers.size, 0);
        }
        h.bridge.close();
    }
});

test('resume escalation counts each stage independently and opens at most one report per incident', async () => {
    const h = harness();
    for (const [index, method] of ['QueryUsage', 'RecordUsage', 'QueryUsage',
        'RecordUsage', 'QueryUsage', 'RecordUsage'].entries()) {
        h.setFailure(null);
        h.activity(false);
        await settle();
        h.setFailure(index % 2 ? 'NO_REPLY' : 'BUSY', method);
        h.activity(true);
        await settle();
        assert.equal(h.reports.length, index < 4 ? 0 : 1);
        assert.equal(h.timers.size, 0);
    }
    h.bridge.close();
});

test('a limit lifecycle change rearms reporting without requiring a successful refresh', async () => {
    const h = harness();
    h.setFailure('BUSY', 'QueryUsage');
    for (let occurrence = 1; occurrence <= 3; occurrence++) {
        h.activity(false);
        await settle();
        h.activity(true);
        await settle();
    }
    assert.equal(h.reports.length, 1);
    h.manager.parentalControlsSessionLimitsEnabled = false;
    h.manager.emit('notify::daily-limit-enabled');
    h.manager.parentalControlsSessionLimitsEnabled = true;
    h.manager.emit('notify::daily-limit-enabled');
    for (let occurrence = 1; occurrence <= 3; occurrence++) {
        h.activity(false);
        await settle();
        h.activity(true);
        await settle();
        assert.equal(h.reports.length, occurrence < 3 ? 1 : 2);
        assert.equal(h.logs.at(-1).event,
            occurrence < 3 ? 'child.resume-refresh-deferred' : 'child.resume-refresh-failed');
        assert.equal(h.timers.size, 0);
    }
    h.bridge.close();
});

test('an exhausted estimate read reports immediately after its bounded retries', async () => {
    const h = harness({remaining: 0});
    h.activity(false);
    await settle();
    h.setRemaining(292);
    h.setFailure('NO_REPLY', 'GetEstimatedTimes');
    h.activity(true);
    await settle();
    for (const delay of [200, 1000, 3000, 5000]) {
        assert.equal([...h.timers.values()][0].delay, delay);
        h.tick();
        await settle();
    }
    assert.equal(h.reports.length, 1);
    assert.equal(h.timers.size, 0);
    assert.deepEqual(h.logs.at(-1).fields, {
        stage: 'timer-estimate', category: 'no-reply', active: true, limit_enabled: true,
        failures: 1, retry: false, delay_ms: 0,
    });
    h.bridge.close();
});

test('an unreviewed Busy error or invalid native deadline cannot defer a resume report', async () => {
    for (const [code, deadline, category] of [
        ['UNREVIEWED_BUSY', 200, 'other'], ['BUSY', Infinity, 'busy'],
    ]) {
        const h = harness();
        h.activity(false);
        await settle();
        h.setFailure(code, 'QueryUsage');
        h.manager.dailyLimitTime = deadline;
        h.manager.emit();
        await settle();
        assert.equal(h.reports.length, 1);
        assert.equal(h.timers.size, 0);
        assert.deepEqual(h.logs.at(-1).fields, {
            stage: 'query-usage', category, active: true, limit_enabled: true,
            failures: 1, retry: false, delay_ms: 0,
        });
        assert(!JSON.stringify(h.logs).includes('private'));
        h.bridge.close();
    }
});
