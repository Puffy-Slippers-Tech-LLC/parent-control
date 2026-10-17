import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

const catalog = JSON.parse(readFileSync(new URL(
    '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url)));
const states = {DISABLED: 0, ACTIVE: 1, LIMIT_REACHED: 2};

// Private signal doubles and clock only. No real bus, graphical session,
// settings, subprocess or mutable file participates in these observations.
function signals(properties = {}) {
    const handlers = new Map();
    let nextId = 0;
    return Object.assign(properties, {
        handlers,
        connect(signal, callback) { handlers.set(++nextId, {signal, callback}); return nextId; },
        connectSignal(signal, callback) { return this.connect(signal, callback); },
        disconnect(id) { handlers.delete(id); },
        disconnectSignal(id) { this.disconnect(id); },
        emit(signal, ...args) {
            for (const handler of [...handlers.values()])
                if (handler.signal === signal) handler.callback(this, ...args);
        },
    });
}

function harness({hold = false, unavailable = false} = {}) {
    let now = 1000, owner = ':1.42', resolveSession;
    const records = [], failures = [], timers = new Map();
    let nextTimer = 0;
    const manager = signals({state: states.LIMIT_REACHED, shouldLockSession: true,
        parentalControlsSessionLimitsEnabled: true, dailyLimitTime: 0,
        getCurrentTime: () => now});
    const mode = signals({isLocked: true, isGreeter: false});
    const session = signals({Active: false, IdleHint: true, LockedHint: true,
        Id: 'PRIVATE-session', User: 'PRIVATE-user', get_name_owner: () => owner,
        get_object_path: () => '/org/freedesktop/login1/session/PRIVATE'});
    const login = signals({getCurrentSessionProxy: () => hold
        ? new Promise(resolve => { resolveSession = resolve; })
        : Promise.resolve(unavailable ? null : session)});
    const context = vm.createContext({TimeLimitsState: states,
        Gio: {DBus: {system: {}}, DBusProxy: {makeProxyWrapper(xml) {
            for (const property of ['Active', 'IdleHint', 'LockedHint'])
                assert.ok(xml.includes(`property name="${property}" type="b" access="read"`));
            assert.ok(!xml.includes('<method'), 'the observation proxy declares no mutating method');
            return {newAsync: async (_bus, name, path) => {
                assert.equal(name, 'org.freedesktop.login1');
                assert.equal(path, session.get_object_path());
                return session;
            }};
        }}}, GLib: {
        get_monotonic_time: () => now * 1_000_000,
        timeout_add(_priority, delay, callback) {
            assert.equal(delay, 1000);
            timers.set(++nextTimer, callback);
            return nextTimer;
        },
        source_remove: id => timers.delete(id), SOURCE_REMOVE: false,
    }});
    vm.runInContext(readFileSync(new URL('../../child/sessionDiagnostics.js', import.meta.url), 'utf8')
        .replace(/^import .*;\n/gm, '')
        .replace('export class SessionDiagnostics', 'globalThis.SessionDiagnostics = class'), context);
    const monitor = new context.SessionDiagnostics(manager, mode, fields => {
        records.push(JSON.parse(diagnosticEnvelope(catalog, 'child.session-state',
            JSON.parse(JSON.stringify(fields)))));
    }, () => failures.push('failed'), login);
    return {monitor, context, manager, mode, session, login, records, failures, timers,
        release: () => resolveSession(session),
        setOwner(value) { owner = value; session.emit('notify::g-name-owner'); },
        advance(seconds) { now += seconds; },
        settle() {
            now += 1;
            const callbacks = [...timers.values()];
            timers.clear();
            for (const callback of callbacks) callback();
        },
        unlock(sender = owner) { session.emit('Unlock', sender, []); },
    };
}

test('a successful authentication followed by a native refusal remains distinguishable from an unlock', async () => {
    const h = harness();
    await h.monitor.ready;
    // GNOME 50.6 _updateState() retains LIMIT_REACHED after a grant while
    // inactive. Its ScreenShield.deactivate() refuses the first Unlock.
    // Becoming active then clears the native decision, without another Unlock.
    h.unlock();
    h.session.Active = true;
    h.session.IdleHint = false;
    h.session.emit('g-properties-changed');
    Object.assign(h.manager, {state: states.ACTIVE, shouldLockSession: false,
        dailyLimitTime: 1290});
    h.manager.emit('notify::state');
    h.settle();
    const first = h.records.find(row => row.fields.reason === 'unlock-request').fields;
    assert.equal(first.native_should_lock, true);
    assert.equal(first.native_state, 'limit-reached');
    assert.equal(first.session_active, false);
    const settled = h.records.at(-1).fields;
    assert.equal(settled.reason, 'unlock-settled');
    assert.equal(settled.attempt, 1);
    assert.equal(settled.locked, true);
    assert.equal(settled.native_should_lock, false);
    assert.equal(settled.native_remaining, 289);
    assert.equal(settled.elapsed_ms, 1000);
    // A second successful credential is a separate observed request. The
    // observer itself has neither retried nor unlocked anything.
    h.mode.isLocked = false;
    h.session.LockedHint = false;
    h.unlock();
    h.settle();
    assert.equal(h.records.at(-1).fields.attempt, 2);
    assert.equal(h.records.at(-1).fields.locked, false);
    assert.deepEqual(h.failures, []);
    h.monitor.close();
});

test('time restored alone never produces an unlock request or changes native state', async () => {
    const h = harness();
    await h.monitor.ready;
    h.manager.dailyLimitTime = 1300;
    h.manager.emit('notify::daily-limit-time');
    assert.equal(h.mode.isLocked, true);
    assert.equal(h.manager.shouldLockSession, true);
    assert.equal(h.manager.state, states.LIMIT_REACHED);
    assert.equal(h.records.length, 1, 'a changing duration alone is not another state transition');
    assert.equal(h.timers.size, 0);
    h.monitor.close();
});

test('only the current logind owner can cause a recorded Lock or Unlock', async () => {
    const h = harness();
    await h.monitor.ready;
    for (const sender of [null, '', ':1.untrusted']) {
        h.unlock(sender);
        h.session.emit('Lock', sender, []);
    }
    assert.equal(h.records.length, 1);
    assert.equal(h.timers.size, 0);
    h.unlock();
    assert.equal(h.timers.size, 1);
    h.setOwner(null);
    assert.equal(h.records.at(-1).fields.session_available, false);
    assert.equal(h.timers.size, 0);
    h.monitor.close();
});

test('observation is bounded and a new request, lock, sleep or owner loss retires its timer', async () => {
    for (const action of ['request', 'lock', 'sleep', 'owner']) {
        const h = harness();
        await h.monitor.ready;
        h.unlock();
        const firstTimer = [...h.timers.keys()][0];
        if (action === 'request') h.unlock();
        if (action === 'lock') h.session.emit('Lock', ':1.42', []);
        if (action === 'sleep') h.login.emit('prepare-for-sleep', true);
        if (action === 'owner') h.setOwner(':1.43');
        assert.equal(h.timers.has(firstTimer), false);
        assert.equal(h.timers.size, action === 'request' ? 1 : 0);
        h.monitor.close();
        assert.equal(h.timers.size, 0);
        for (const object of [h.manager, h.mode, h.session, h.login])
            assert.equal(object.handlers.size, 0);
    }
});

test('duration ticks are suppressed; a lock decision change with no mode transition is retained', async () => {
    const h = harness();
    await h.monitor.ready;
    for (let tick = 0; tick < 90; tick++) {
        h.advance(1);
        h.manager.emit('notify::daily-limit-time');
        h.session.emit('g-properties-changed');
    }
    assert.equal(h.records.length, 1);
    h.manager.shouldLockSession = false;
    h.manager.emit('notify::should-lock-session');
    assert.equal(h.records.length, 2);
    assert.equal(h.records.at(-1).fields.locked, true);
    h.monitor.close();
});

test('diagnostics contain only catalogue fields, bounded durations and closed states', async () => {
    const h = harness();
    await h.monitor.ready;
    h.manager.state = 999;
    h.manager.dailyLimitTime = Infinity;
    h.unlock();
    h.advance(1e10);
    h.settle();
    const fields = h.records.at(-1).fields;
    assert.equal(fields.native_state, 'unknown');
    assert.equal(fields.native_remaining, 0);
    assert.equal(fields.elapsed_ms, 4294967295);
    const secret = 'private@example.test /home/private password=secret';
    for (const row of h.records) {
        assert.ok(!JSON.stringify(row).includes('PRIVATE'));
        assert.throws(() => diagnosticEnvelope(catalog, row.event, {...row.fields, message: secret}));
        for (const key of Object.keys(row.fields))
            assert.throws(() => diagnosticEnvelope(catalog, row.event, {...row.fields, [key]: secret}));
    }
    h.monitor.close();
});

test('unavailable or late session discovery and partial startup leave no observers behind', async () => {
    const missing = harness({unavailable: true});
    await missing.monitor.ready;
    assert.deepEqual(missing.failures, ['failed']);
    const late = harness({hold: true});
    late.monitor.close();
    late.release();
    await late.monitor.ready;
    assert.deepEqual(late.records, []);
    assert.deepEqual(late.failures, []);
    const partial = harness({hold: true});
    partial.mode.connect = () => { throw new Error('PRIVATE'); };
    partial.release();
    await partial.monitor.ready;
    assert.equal(partial.manager.handlers.size, 0);
    assert.deepEqual(partial.failures, ['failed']);
});

test('logging and property-read failures cannot escape into native signal dispatch', async () => {
    const h = harness();
    await h.monitor.ready;
    h.monitor._observe = () => { throw new Error('PRIVATE'); };
    h.monitor._failure = () => { throw new Error('PRIVATE'); };
    assert.doesNotThrow(() => h.unlock());
    h.session.get_name_owner = () => { throw new Error('PRIVATE'); };
    assert.doesNotThrow(() => h.session.emit('Unlock', ':1.42', []));
    assert.doesNotThrow(() => h.settle());
    h.monitor.close();
});

test('extension failure and disable retire the observer independently of the indicator', async () => {
    const h = harness();
    await h.monitor.ready;
    h.unlock();
    Object.assign(h.context, {Extension: class {},
        ChildErrorHandler: class { report() {} close() {} }, logInfo() {}, logWarning() {}});
    vm.runInContext(readFileSync(new URL('../../child/extension.js', import.meta.url), 'utf8')
        .replace(/^import .*;\n/gm, '')
        .replace('export default class OhNoParentControlExtension', 'globalThis.App = class'), h.context);
    const app = new h.context.App();
    app._enable = () => {
        app._sessionDiagnostics = h.monitor;
        throw new Error('later startup failed');
    };
    assert.throws(() => app.enable(), /Child App could not start/);
    assert.equal(h.timers.size, 0);
    for (const object of [h.manager, h.mode, h.session, h.login])
        assert.equal(object.handlers.size, 0);
    const next = harness();
    await next.monitor.ready;
    next.unlock();
    app._sessionDiagnostics = next.monitor;
    app._stopRequest = () => {};
    app.disable();
    app.disable();
    assert.equal(next.timers.size, 0);
    for (const object of [next.manager, next.mode, next.session, next.login])
        assert.equal(object.handlers.size, 0);
});
