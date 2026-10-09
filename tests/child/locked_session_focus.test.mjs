import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

function harness() {
    const events = [], handlers = new Map();
    let sequence = 0, surface = null, grab = {}, notifyFailure = false;
    const mode = {isLocked: true, isGreeter: false};
    const device = {get_capabilities: () => 1};
    const seat = {
        connect_after(signal, callback) {
            assert.equal(signal, 'device-added');
            handlers.set(++sequence, callback);
            return sequence;
        },
        disconnect(id) { handlers.delete(id); },
        emit(value = device) {
            // Model the causal boundary: Mutter's ordinary handler restores
            // the remembered client before every registered after-handler.
            surface = 'retained-client';
            events.push('keyboard-enabled');
            for (const callback of [...handlers.values()]) callback(seat, value);
        },
    };
    const stage = {
        get_grab_actor: () => grab,
        notify(property) {
            assert.equal(property, 'is-grabbed');
            events.push('grab-notified');
            if (notifyFailure) throw Error('PRIVATE device identity');
            surface = null;
        },
    };
    const context = vm.createContext({Clutter: {InputCapabilities: {KEYBOARD: 1}},
        Extension: class {}, ChildErrorHandler: class { report() {} close() {} },
        logInfo() {}, logWarning() {}, LockedSessionFocus: null});
    vm.runInContext(readFileSync(new URL('../../child/lockedSessionFocus.js', import.meta.url), 'utf8')
        .replace(/^import .*;\n/gm, '')
        .replace('export class LockedSessionFocus', 'globalThis.LockedSessionFocus = class'), context);
    const observed = [];
    const create = () => new context.LockedSessionFocus(seat, stage, mode,
        outcome => observed.push(outcome));
    return {context, create, controller: create(), seat, stage, mode, events, observed, handlers,
        get surface() { return surface; },
        setGrab: value => { grab = value; }, failNotify: value => { notifyFailure = value; }};
}

test('locked reactivation repairs client focus after ordinary keyboard enable', () => {
    const h = harness();
    h.seat.emit();
    assert.deepEqual(h.events, ['keyboard-enabled', 'grab-notified']);
    assert.equal(h.surface, null);
    assert.deepEqual(h.observed, ['complete']);
    h.controller.close();
});

test('combined-capability keyboards qualify; pointer-only devices do not', () => {
    for (const capabilities of [1, 3, 2, 0]) {
        const h = harness();
        h.seat.emit({get_capabilities: () => capabilities});
        assert.equal(h.events.includes('grab-notified'), Boolean(capabilities & 1));
        h.controller.close();
    }
});

test('unlocked, greeter and absent-grab states preserve normal focus', () => {
    for (const state of ['unlocked', 'greeter', 'ungrabbed']) {
        const h = harness();
        if (state === 'unlocked') h.mode.isLocked = false;
        if (state === 'greeter') h.mode.isGreeter = true;
        if (state === 'ungrabbed') h.setGrab(null);
        h.seat.emit();
        assert.equal(h.surface, 'retained-client');
        assert.deepEqual(h.observed, []);
        h.controller.close();
    }
});

test('notification reentrancy cannot recursively notify the stage', () => {
    const h = harness();
    const notify = h.stage.notify;
    h.stage.notify = property => { h.seat.emit(); notify(property); };
    h.seat.emit();
    assert.equal(h.events.filter(value => value === 'grab-notified').length, 1);
    assert.equal(h.surface, null);
    h.controller.close();
});

test('notification failure releases the guard and emits only a closed outcome', () => {
    const h = harness();
    h.failNotify(true);
    h.seat.emit();
    h.failNotify(false);
    h.seat.emit();
    assert.deepEqual(h.observed, ['failed', 'complete']);
    const catalog = JSON.parse(readFileSync(new URL(
        '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url)));
    for (const outcome of h.observed) {
        const record = diagnosticEnvelope(catalog, 'child.lock-focus-sync', {outcome});
        assert.ok(!record.includes('PRIVATE'));
    }
    assert.throws(() => diagnosticEnvelope(catalog, 'child.lock-focus-sync', {outcome: 'PRIVATE'}));
    assert.equal(h.surface, null);
    h.controller.close();
});

test('close precedes disconnect callbacks and repeated lifecycles leave no handler', () => {
    const h = harness();
    const disconnect = h.seat.disconnect;
    h.seat.disconnect = id => { h.seat.emit(); disconnect(id); };
    h.controller.close();
    h.controller.close();
    assert.deepEqual(h.observed, []);
    assert.equal(h.handlers.size, 0);
    const next = h.create();
    h.seat.emit();
    assert.deepEqual(h.observed, ['complete']);
    next.close();
    assert.equal(h.handlers.size, 0);
});

test('extension failed startup and ordinary disable close the independently owned hook', () => {
    const h = harness();
    h.controller.close();
    vm.runInContext(readFileSync(new URL('../../child/extension.js', import.meta.url), 'utf8')
        .replace(/^import .*;\n/gm, '')
        .replace('export default class OhNoParentControlExtension', 'globalThis.App = class'), h.context);
    const app = new h.context.App();
    app._enable = () => {
        app._lockedSessionFocus = h.create();
        throw Error('later startup failed');
    };
    assert.throws(() => app.enable(), /Child App could not start/);
    assert.equal(h.handlers.size, 0);
    app._lockedSessionFocus = h.create();
    app._stopRequest = () => {};
    app.disable();
    app.disable();
    assert.equal(h.handlers.size, 0);
    h.seat.emit();
    assert.deepEqual(h.observed, []);
});
