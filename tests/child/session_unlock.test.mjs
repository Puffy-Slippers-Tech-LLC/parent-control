import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

const states = {DISABLED: 0, ACTIVE: 1, LIMIT_REACHED: 2};
const catalog = JSON.parse(readFileSync(new URL(
    '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url)));

function signals(properties = {}) {
    const handlers = new Map();
    let sequence = 0;
    return Object.assign(properties, {handlers,
        connect(signal, callback) { handlers.set(++sequence, {signal, callback}); return sequence; },
        connectSignal(signal, callback) { return this.connect(signal, callback); },
        disconnect(id) { handlers.delete(id); },
        disconnectSignal(id) { this.disconnect(id); },
        emit(signal, ...args) {
            for (const row of [...handlers.values()])
                if (row.signal === signal) row.callback(this, ...args);
        },
    });
}

// The real recovery controller with private event loop/native admission
// doubles. No live account, bus, display, setting, file write or subprocess.
function harness() {
    let elapsed = 0, owner = ':1.42', sequence = 0, holdUnlock = false, failUnlock = false;
    const idle = new Map(), timers = new Map(), records = [], failures = [], calls = [], causes = [];
    const nativeCallbacks = [];
    const manager = signals({state: states.LIMIT_REACHED, shouldLockSession: true,
        dailyLimitTime: 0, parentalControlsSessionLimitsEnabled: true,
        getCurrentTime: () => 1000 + elapsed / 1000});
    const mode = signals({isLocked: true, isGreeter: false});
    const session = signals({Active: false, IdleHint: true, get_name_owner: () => owner});
    const login = signals({preparingForSleep: false});
    const shield = signals({locked: true,
        deactivate(animate) {
            calls.push(animate);
            if (failUnlock) throw new Error('PRIVATE native failure');
            // Preserve GNOME's final gate. A returned call does not mean that
            // the guard allowed it, nor that the unlock animation finished.
            if (manager.shouldLockSession) return;
            const complete = () => {
                this.locked = false;
                mode.isLocked = false;
                this.emit('locked-changed');
                mode.emit('updated');
            };
            if (holdUnlock) nativeCallbacks.push(complete);
            else complete();
        },
    });
    const context = vm.createContext({TimeLimitsState: states,
        recordChildFailure: (error, operation) => causes.push({error, operation}), GLib: {
        get_monotonic_time: () => elapsed * 1000,
        idle_add(_priority, callback) { idle.set(++sequence, callback); return sequence; },
        timeout_add(_priority, delay, callback) {
            assert.equal(delay, 2000);
            timers.set(++sequence, callback);
            return sequence;
        },
        source_remove(id) { idle.delete(id); timers.delete(id); }, SOURCE_REMOVE: false,
    }});
    vm.runInContext(readFileSync(new URL('../../child/sessionUnlock.js', import.meta.url), 'utf8')
        .replace(/^import .*;\n/gm, '')
        .replace('export class SessionUnlockRecovery', 'globalThis.SessionUnlockRecovery = class'), context);
    const create = () => new context.SessionUnlockRecovery(manager, mode, shield, session, login,
        fields => records.push(JSON.parse(diagnosticEnvelope(catalog, 'child.unlock-recovery',
            JSON.parse(JSON.stringify(fields))))), () => failures.push('unavailable'));
    const controller = create();
    return {context, create, controller, manager, mode, session, login, shield,
        idle, timers, records, failures, calls, causes,
        unlock(sender = owner) { session.emit('Unlock', sender, []); },
        active() { session.Active = true; session.IdleHint = false; session.emit('g-properties-changed'); },
        available() {
            Object.assign(manager, {state: states.ACTIVE, shouldLockSession: false,
                dailyLimitTime: manager.getCurrentTime() + 300});
            manager.emit('notify::state');
        },
        setOwner(value) { owner = value; session.emit('notify::g-name-owner'); },
        advance(ms) { elapsed += ms; },
        hold(value = true) { holdUnlock = value; },
        completeNative() { nativeCallbacks.splice(0).forEach(callback => callback()); },
        fail(value = true) { failUnlock = value; },
        flush() {
            let iterations = 0;
            while (idle.size) {
                assert.ok(++iterations < 10, 'no idle feedback loop');
                const [id, callback] = idle.entries().next().value;
                idle.delete(id);
                callback();
            }
        },
    };
}

test('one authenticated request survives the native inactive-limit race without a second credential', () => {
    const h = harness();
    const original = h.shield.deactivate;
    h.shield.deactivate(false); // GNOME's original Unlock handler refuses.
    h.unlock();
    h.flush();
    assert.equal(h.shield.locked, true);
    assert.equal(h.calls.length, 1);
    h.active();
    h.advance(120);
    h.available();
    h.flush();
    assert.equal(h.calls.length, 2, 'only one continuation of the original native call');
    assert.equal(h.shield.locked, false);
    assert.equal(h.shield.deactivate, original, 'native method is never replaced');
    assert.deepEqual(h.records.map(row => row.fields.stage), ['armed', 'retry', 'unlocked']);
    assert.equal(h.records.at(-1).fields.elapsed_ms, 120);
    assert.equal(h.records.at(-1).fields.attempt, 1);
    assert.equal(h.timers.size, 0);
    h.controller.close();
});

test('a grant, startup and repeated state notifications alone never authorize an unlock', () => {
    const h = harness();
    h.active();
    h.available();
    for (let i = 0; i < 20; i++) h.manager.emit('notify::daily-limit-time');
    h.flush();
    assert.equal(h.calls.length, 0);
    assert.equal(h.shield.locked, true);
    assert.equal(h.records.length, 0);
    assert.equal(h.timers.size, 0);
    h.controller.close();
});

test('normal native unlock and non-parental locks never arm a continuation', () => {
    for (const kind of ['normal', 'disabled', 'greeter', 'sleep', 'unknown-state']) {
        const h = harness();
        if (kind === 'normal') { h.active(); h.available(); h.shield.deactivate(false); }
        if (kind === 'disabled') h.manager.parentalControlsSessionLimitsEnabled = false;
        if (kind === 'greeter') h.mode.isGreeter = true;
        if (kind === 'sleep') h.login.preparingForSleep = true;
        if (kind === 'unknown-state') h.manager.state = 999;
        h.unlock();
        h.flush();
        assert.equal(h.records.length, 0, kind);
        assert.equal(h.timers.size, 0, kind);
        h.controller.close();
    }
});

test('only current logind ownership can authorize or cancel the pending request', () => {
    const h = harness();
    for (const sender of [null, '', ':1.spoof']) h.unlock(sender);
    h.active();
    h.available();
    h.flush();
    assert.equal(h.calls.length, 0);
    h.controller.close();
    const next = harness();
    next.unlock();
    next.session.emit('Lock', ':1.spoof', []);
    next.active();
    next.available();
    next.flush();
    assert.equal(next.shield.locked, false);
    next.controller.close();
});

test('active session and verified finite native time are all required', () => {
    for (const missing of ['active', 'zero', 'expired', 'nan', 'infinite', 'state']) {
        const h = harness();
        h.unlock();
        h.active();
        h.available();
        if (missing === 'active') h.session.Active = undefined;
        if (missing === 'zero') h.manager.dailyLimitTime = 0;
        if (missing === 'expired') h.manager.dailyLimitTime = h.manager.getCurrentTime();
        if (missing === 'nan') h.manager.dailyLimitTime = NaN;
        if (missing === 'infinite') h.manager.dailyLimitTime = Infinity;
        if (missing === 'state') h.manager.state = 999;
        h.flush();
        assert.equal(h.calls.length, 0, missing);
        h.controller.close();
    }
});

test('a delayed per-session idle hint cannot overrule native active admission', () => {
    const h = harness();
    h.unlock();
    h.active();
    h.session.IdleHint = true;
    h.available();
    h.flush();
    assert.equal(h.calls.length, 1);
    assert.equal(h.shield.locked, false);
    h.controller.close();
});

test('new lock, sleep, owner change, departure, disabled limits and renewed exhaustion cancel before dispatch', () => {
    const actions = {
        'new-lock': h => h.session.emit('Lock', ':1.42', []),
        sleep: h => { h.login.preparingForSleep = true; h.login.emit('prepare-for-sleep', true); },
        'owner-changed': h => h.setOwner(':1.43'),
        'session-inactive': h => {
            h.session.Active = false; h.session.emit('g-properties-changed');
            h.session.Active = true; h.session.emit('g-properties-changed');
        },
        'limits-disabled': h => {
            h.manager.parentalControlsSessionLimitsEnabled = false;
            h.manager.emit('notify::daily-limit-enabled');
            h.manager.parentalControlsSessionLimitsEnabled = true;
        },
        greeter: h => { h.mode.isGreeter = true; h.mode.emit('updated'); },
        'time-exhausted': h => {
            h.manager.shouldLockSession = true; h.manager.emit('notify::should-lock-session');
            h.available();
        },
        closed: h => h.controller.close(),
    };
    for (const [reason, action] of Object.entries(actions)) {
        const h = harness();
        h.unlock();
        h.active();
        h.available();
        action(h);
        h.flush();
        assert.equal(h.calls.length, 0, reason);
        assert.equal(h.records.at(-1).fields.stage, 'cancelled', reason);
        assert.equal(h.records.at(-1).fields.reason, reason);
        assert.equal(h.timers.size, 0);
        h.controller.close();
    }
});

test('the monotonic deadline is checked at dispatch even if its timer has not run', () => {
    for (const elapsed of [2000, 5000]) {
        const h = harness();
        h.unlock();
        h.active();
        h.advance(elapsed);
        h.available();
        h.flush();
        assert.equal(h.calls.length, 0);
        assert.equal(h.records.at(-1).fields.stage, 'expired');
        assert.equal(h.timers.size, 0);
        h.available();
        h.flush();
        assert.equal(h.calls.length, 0, 'a later grant cannot revive expired authority');
        h.controller.close();
    }
});

test('a returned native method never counts as an unlocked desktop or permits another dispatch', () => {
    const h = harness();
    h.hold();
    h.unlock();
    h.active();
    h.available();
    h.flush();
    assert.equal(h.calls.length, 1);
    assert.equal(h.records.at(-1).fields.stage, 'retry');
    for (let i = 0; i < 10; i++) {
        h.manager.emit('notify::state');
        h.flush();
    }
    assert.equal(h.calls.length, 1, 'never repeatedly retries a refused or unfinished native unlock');
    h.advance(2000);
    const callbacks = [...h.timers.values()];
    h.timers.clear();
    callbacks.forEach(callback => callback());
    assert.equal(h.records.at(-1).fields.stage, 'observation-expired');
    assert.equal(h.shield.locked, true);
    h.completeNative();
    assert.equal(h.shield.locked, false, 'native completion can outlive our observation window');
    assert.equal(h.calls.length, 1);
    h.controller.close();
});

test('native unlock followed by direct relock consumes old authority before the recovery idle', () => {
    const h = harness();
    h.unlock();
    h.active();
    h.available();
    // An ordinary native unlock completes first. Direct ScreenSaver/shortcut
    // locks do not emit logind's Lock signal and may run before our idle.
    h.shield.deactivate(false);
    h.shield.locked = true;
    h.mode.isLocked = true;
    h.shield.emit('locked-changed');
    h.mode.emit('updated');
    h.flush();
    assert.equal(h.calls.length, 1, 'no second native unlock after relock');
    assert.equal(h.shield.locked, true);
    assert.equal(h.records.at(-1).fields.stage, 'unlocked');
    assert.equal(h.timers.size, 0);
    h.controller.close();
});

test('an observed native unlock animation relinquishes authority before an immediate direct relock', () => {
    const h = harness();
    h.unlock();
    h.active();
    h.available();
    h.mode.isLocked = false;
    h.mode.emit('updated');
    h.mode.isLocked = true;
    h.mode.emit('updated');
    h.flush();
    assert.equal(h.calls.length, 0);
    assert.equal(h.records.at(-1).fields.stage, 'native-owned');
    h.controller.close();
});

test('a lock after native handoff is reported as an interruption, not cancellation of native callbacks', () => {
    const h = harness();
    h.hold();
    h.unlock();
    h.active();
    h.available();
    h.flush();
    h.session.emit('Lock', ':1.42', []);
    assert.equal(h.records.at(-1).fields.stage, 'observed-interruption');
    assert.equal(h.records.at(-1).fields.reason, 'new-lock');
    // This is GNOME's existing noncancellable finish-message/animation path.
    // The controller neither cancels it nor dispatches any further unlock.
    h.completeNative();
    h.flush();
    assert.equal(h.shield.locked, false);
    assert.equal(h.calls.length, 1);
    h.controller.close();
});

test('a newer authenticated request replaces old authority and restarts only its own lifetime', () => {
    const h = harness();
    h.unlock();
    h.advance(1500);
    h.unlock();
    h.advance(800);
    h.active();
    h.available();
    h.flush();
    assert.equal(h.calls.length, 1);
    assert.equal(h.records.at(-1).fields.attempt, 2);
    assert.equal(h.records.at(-1).fields.elapsed_ms, 800);
    assert.equal(h.records.filter(row => row.fields.reason === 'superseded').length, 1);
    h.controller.close();
});

test('diagnostic exceptions do not prevent recovery, while native failures stop without retrying', () => {
    const h = harness();
    h.controller._observe = () => { throw new Error('PRIVATE log failure'); };
    h.controller._failure = () => { throw new Error('PRIVATE log failure'); };
    h.unlock();
    h.active();
    h.available();
    assert.doesNotThrow(() => h.flush());
    assert.equal(h.shield.locked, false);
    h.controller.close();
    const next = harness();
    next.unlock();
    next.active();
    next.available();
    next.fail();
    assert.doesNotThrow(() => next.flush());
    assert.equal(next.records.at(-1).fields.stage, 'failed');
    assert.deepEqual(next.failures, ['unavailable']);
    assert.equal(next.causes.at(-1).operation, 'unlock-dispatch');
    assert.equal(next.timers.size, 0);
    next.manager.emit('notify::state');
    next.flush();
    assert.equal(next.calls.length, 1);
    next.controller.close();
});

test('new lock during observation retires the request before the synchronous native call', () => {
    const h = harness();
    const record = h.controller._observe;
    h.controller._observe = fields => {
        record(fields);
        if (fields.stage === 'retry') h.session.emit('Lock', ':1.42', []);
    };
    h.unlock();
    h.active();
    h.available();
    h.flush();
    assert.equal(h.calls.length, 0);
    assert.equal(h.records.at(-1).fields.reason, 'new-lock');
    h.controller.close();
});

test('shutdown and partial constructor failure release every owned connection and source', () => {
    const h = harness();
    h.unlock();
    h.controller.close();
    h.controller.close();
    for (const object of [h.manager, h.mode, h.session, h.shield, h.login])
        assert.equal(object.handlers.size, 0);
    assert.equal(h.idle.size, 0);
    assert.equal(h.timers.size, 0);
    h.login.connect = () => { throw new Error('PRIVATE setup failure'); };
    assert.throws(() => h.create());
    assert.equal(h.causes.at(-1).operation, 'unlock-startup');
    for (const object of [h.manager, h.mode, h.session, h.shield, h.login])
        assert.equal(object.handlers.size, 0);
});

test('recovery diagnostics reject private data and unknown outcomes', () => {
    const h = harness();
    h.unlock();
    h.active();
    h.available();
    h.flush();
    const privateText = 'private@example.test /home/private password=secret';
    for (const {event, fields} of h.records) {
        assert.throws(() => diagnosticEnvelope(catalog, event, {...fields, message: privateText}));
        for (const key of Object.keys(fields))
            assert.throws(() => diagnosticEnvelope(catalog, event, {...fields, [key]: privateText}));
        assert.ok(!JSON.stringify(fields).includes(':1.42'));
    }
    h.controller.close();
});

test('extension readiness cannot attach recovery after disable or failed startup', async () => {
    for (const outcome of ['active', 'disabled', 'failed']) {
        const h = harness();
        h.controller.close();
        let resolveBinding, monitorClosed = false;
        Object.assign(h.context, {Extension: class {},
            Main: {timeLimitsManager: h.manager, sessionMode: h.mode, screenShield: h.shield},
            SessionDiagnostics: class {
                ready = new Promise(resolve => { resolveBinding = resolve; });
                close() { monitorClosed = true; }
            },
            ChildErrorHandler: class { report() {} close() {} },
            logInfo() {}, logWarning() {},
        });
        vm.runInContext(readFileSync(new URL('../../child/extension.js', import.meta.url), 'utf8')
            .replace(/^import .*;\n/gm, '')
            .replace('export default class OhNoParentControlExtension', 'globalThis.App = class'), h.context);
        const app = new h.context.App();
        app._stopRequest = () => {};
        app._startSessionMonitoring();
        if (outcome === 'disabled') app.disable();
        if (outcome === 'failed') {
            app._enable = () => { throw new Error('later startup failed'); };
            assert.throws(() => app.enable(), /Child App could not start/);
        }
        resolveBinding({session: h.session, login: h.login});
        for (let i = 0; i < 6; i++) await Promise.resolve();
        if (outcome === 'active') {
            assert.ok(app._sessionUnlock);
            h.unlock();
            h.active();
            h.available();
            h.flush();
            assert.equal(h.shield.locked, false);
            app.disable();
        } else {
            assert.equal(h.calls.length, 0);
        }
        assert.equal(monitorClosed, true);
        for (const object of [h.manager, h.mode, h.session, h.shield, h.login])
            assert.equal(object.handlers.size, 0);
    }
});

test('nested previews never bind to the real development session', () => {
    const context = vm.createContext({OhNoParentControlExtension: class {
        _startSessionMonitoring() { throw new Error('real session was accessed'); }
    }});
    vm.runInContext(readFileSync(new URL('../../child/previewExtension.js', import.meta.url), 'utf8')
        .replace(/^import .*;\n/gm, '')
        .replace('export default class PreviewExtension', 'globalThis.Preview = class'), context);
    assert.doesNotThrow(() => new context.Preview()._startSessionMonitoring());
});
