import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

import {
    busyRetryDelay,
    canOpenRequest,
    displayState,
    effectiveAllowanceRemaining,
    formatRemainingTime,
    nextEstimateState,
    remainingSeconds,
    requestCompletionState,
    shouldPrepareSession,
} from '../../child/indicatorLogic.mjs';

test('layout refreshes cannot postpone the countdown tick', () => {
    // Execute the production scheduler with a deterministic GLib clock. No
    // Shell session or system-bus connection is created by this harness.
    const source = readFileSync(new URL('../../child/remainingTimeIndicator.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export const RemainingTimeIndicator', 'globalThis.RemainingTimeIndicator');
    let now = 0;
    let nextId = 0;
    const timers = new Map();
    const context = vm.createContext({
        GObject: {registerClass: klass => klass},
        PanelMenu: {Button: class {}},
        GLib: {
            PRIORITY_DEFAULT: 0,
            SOURCE_REMOVE: false,
            get_monotonic_time: () => now,
            source_remove: id => timers.delete(id),
            timeout_add_seconds: (_priority, delay, callback) => {
                timers.set(++nextId, {deadline: now + delay * 1_000_000, callback});
                return nextId;
            },
        },
    });
    vm.runInContext(source, context);
    const indicator = new context.RemainingTimeIndicator();
    Object.assign(indicator, {_timeoutId: 0, _timeoutDeadline: 0, _preview: true});
    let remaining = 56;
    indicator._sync = () => {
        remaining = 56 - Math.floor(now / 1_000_000);
        if (remaining > 0)
            indicator._schedule(1);
    };
    indicator._sync();
    for (now = 100_000; now <= 56_000_000; now += 100_000) {
        indicator._sync(); // Frequent layout / estimate notifications.
        for (const [id, timer] of [...timers]) {
            if (timer.deadline <= now) {
                timers.delete(id);
                timer.callback();
            }
        }
    }
    assert.equal(remaining, 0);
    assert.equal(nextId, 56, 'one tick per second survives repeated refreshes');
    assert.equal(timers.size, 0);

    indicator._schedule(60);
    indicator._schedule(1);
    assert.equal(timers.size, 1, 'an earlier deadline replaces the pending timer');
    assert.equal([...timers.values()][0].deadline, now + 1_000_000);
    indicator._clearTimeout();
    assert.equal(timers.size, 0);
    assert.equal(indicator._timeoutDeadline, 0);
});

test('formats minute, final-minute, zero, and multi-day remaining time', () => {
    assert.equal(formatRemainingTime(3661, false), '01:01 left');
    assert.equal(formatRemainingTime(59, false), '59 left');
    assert.equal(formatRemainingTime(0, true), '0');
    assert.equal(formatRemainingTime(49 * 60 * 60, false), '49:00 left');
});

test('display state changes cadence at the final minute and locks only at zero', () => {
    assert.deepEqual(displayState({calculatedEnd: 160, currentTime: 100, locked: false, greeter: false}), {
        remaining: 60, visible: true, shouldLock: false, countdown: false,
        spinRequestIcon: false, nextUpdateSeconds: 1,
    });
    assert.deepEqual(displayState({calculatedEnd: 159, currentTime: 100, locked: false, greeter: false}), {
        remaining: 59, visible: true, shouldLock: false, countdown: true,
        spinRequestIcon: false, nextUpdateSeconds: 1,
    });
    assert.equal(displayState({calculatedEnd: 100, currentTime: 100, locked: false, greeter: false}).shouldLock, true);
    assert.equal(displayState({calculatedEnd: 100, currentTime: 100, locked: true, greeter: false}).shouldLock, false);
});

test('calculates allowance and preserves a verified estimate on a transient failure', () => {
    assert.equal(effectiveAllowanceRemaining(['', 0, 160], 100, 140), 60);
    assert.equal(effectiveAllowanceRemaining(null, 100, 90), 0);
    const previous = {calculatedEnd: 900, statusLoaded: true};
    assert.deepEqual(nextEstimateState(previous, Number.NaN, 100), previous);
    assert.deepEqual(nextEstimateState(previous, 45, 100), {calculatedEnd: 145, statusLoaded: true});
});

test('classifies bounded busy retries and prevents duplicate request overlays', () => {
    assert.equal(busyRetryDelay('org.example.Error.Busy', 0), 100);
    assert.equal(busyRetryDelay('org.example.Error.Busy', 5), undefined);
    assert.equal(busyRetryDelay('org.example.Error.Failed', 0), undefined);
    assert.equal(canOpenRequest(false, false), true);
    assert.equal(canOpenRequest(true, false), false);
    assert.equal(canOpenRequest(false, true), false);
    assert.deepEqual(requestCompletionState(), {requestActive: false, refreshEstimate: true});
    assert.equal(remainingSeconds(100.1, 100), 1);
});

test('prepares a session only once it is usable', () => {
    const usable = {preview: false, destroyed: false, pending: false, prepared: false, locked: false, greeter: false};
    assert.equal(shouldPrepareSession(usable), true);
    assert.equal(shouldPrepareSession({...usable, locked: true}), false);
    assert.equal(shouldPrepareSession({...usable, prepared: true}), false);
});
