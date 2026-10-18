import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';
import {createIndicator} from './support/indicator.mjs';

const catalog = JSON.parse(readFileSync(new URL(
    '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url)));

test('reminder diagnostics reject content, identities and invalid state', () => {
    const events = {
        'child.display': {width: 2560, height: 1440, scale: 1, theme_scale: 1, text_scale: 1},
        'child.reminder-settings': {count: 4, fullscreen: true},
        'child.reminder-trigger': {threshold: 60, remaining: 59, critical: true},
        'child.reminder-presentation': {closed: false, visible: true, mapped: true,
            fullscreen: true, critical: true, inhibited: true},
    };
    const privateText = 'private@example.test /home/private';
    for (const [event, fields] of Object.entries(events)) {
        assert.doesNotThrow(() => diagnosticEnvelope(catalog, event, fields));
        assert.throws(() => diagnosticEnvelope(catalog, event, {...fields, text: privateText}));
        for (const key of Object.keys(fields))
            assert.throws(() => diagnosticEnvelope(catalog, event, {...fields, [key]: privateText}));
    }
    for (const scale of [0, -1, 17, NaN, Infinity, true])
        assert.throws(() => diagnosticEnvelope(catalog, 'child.display', {...events['child.display'], scale}));
    assert.equal(JSON.parse(diagnosticEnvelope(catalog, 'child.display', {
        ...events['child.display'], scale: 1.25})).fields.scale, 1.25);
    assert.throws(() => diagnosticEnvelope(catalog, 'child.reminder-settings', {count: 65, fullscreen: true}));
    for (const remaining of [0, -1, 0x100000000, Infinity, NaN])
        assert.throws(() => diagnosticEnvelope(catalog, 'child.reminder-trigger', {
            threshold: 60, remaining, critical: true,
        }));
});

test('child evidence is validated before serialization', () => {
    assert.deepEqual(JSON.parse(diagnosticEnvelope(catalog, 'child.estimate', {remaining: 14662})),
        {v: 1, event: 'child.estimate', operation: 0, fields: {remaining: 14662}});
    const secret = 'private@example.test /home/child/private-file';
    for (const fields of [{remaining: secret}, {remaining: 5, secret},
        {remaining: NaN}, {remaining: Infinity}, {remaining: -1}, {remaining: true}])
        assert.throws(() => diagnosticEnvelope(catalog, 'child.estimate', fields));
    assert.throws(() => diagnosticEnvelope(catalog, secret));
    assert.throws(() => diagnosticEnvelope(catalog, 'service.ready'));
});

test('timer failure diagnostics accept only reviewed categories and bounded state', () => {
    const fields = {stage: 'timer-estimate', category: 'no-reply', loaded: true,
        locked: true, greeter: false};
    assert.deepEqual(JSON.parse(diagnosticEnvelope(catalog, 'child.refresh-failed', fields)).fields, fields);
    const secret = 'private@example.test /home/private';
    for (const changed of [{...fields, stage: secret}, {...fields, category: secret},
        {...fields, loaded: secret}, {...fields, message: secret}])
        assert.throws(() => diagnosticEnvelope(catalog, 'child.refresh-failed', changed));
    for (const attempt of [0, 7, NaN, Infinity, secret])
        assert.throws(() => diagnosticEnvelope(catalog, 'child.timer-read-failed', {
            category: 'no-reply', attempt, retry: true,
        }));
    assert.doesNotThrow(() => diagnosticEnvelope(catalog, 'child.timer-recovered', {attempts: 3}));
    // Old retained archives keep their original field-free event contract.
    assert.doesNotThrow(() => diagnosticEnvelope(catalog, 'child.estimate-failed'));
});

test('failure diagnostics reject unreviewed provenance and private metadata', () => {
    const examples = {
        'child.failure': {operation: 'resume-refresh', error_type: 'GLib.Error', category: 'timeout'},
        'child.resume-refresh-failed': {stage: 'record-usage', category: 'busy', active: true,
            limit_enabled: true, failures: 1, retry: false, delay_ms: 0},
        'child.resume-refresh-deferred': {stage: 'query-usage', category: 'busy'},
    };
    for (const [event, fields] of Object.entries(examples)) {
        assert.doesNotThrow(() => diagnosticEnvelope(catalog, event, fields));
        assert.throws(() => diagnosticEnvelope(catalog, event, {...fields, message: '/home/private'}));
        for (const key of Object.keys(fields))
            assert.throws(() => diagnosticEnvelope(catalog, event, {...fields, [key]: '/home/private'}));
    }
    for (const failures of [0, 0x80000000, Infinity])
        assert.throws(() => diagnosticEnvelope(catalog, 'child.resume-refresh-failed', {
            ...examples['child.resume-refresh-failed'], failures}));
    assert.doesNotThrow(() => diagnosticEnvelope(catalog, 'child.error'));
    assert.throws(() => diagnosticEnvelope(catalog, 'child.resume-refresh-deferred', {
        stage: 'query-usage', category: 'access-denied',
    }));
    assert.throws(() => diagnosticEnvelope(catalog, 'child.resume-refresh-deferred', {
        stage: 'timer-estimate', category: 'busy',
    }));
});

test('countdown diagnostics preserve operands without recording every tick or raw deadlines', () => {
    let now = 1_000_000;
    const logs = [];
    const indicator = createIndicator({
        GLib: {get_monotonic_time: () => now},
        logInfo: (event, fields) => logs.push(JSON.parse(diagnosticEnvelope(
            catalog, event, JSON.parse(JSON.stringify(fields))))),
    });
    const wall = 1_791_743_000;
    const sample = elapsed => {
        now = 1_000_000 + elapsed * 1_000_000;
        indicator._calculatedEnd = wall + 240;
        indicator._recordCountdownRefresh({estimate: [false, 0, wall + elapsed + 239],
            currentTime: wall + elapsed, managerLimit: wall + 240,
            effectiveAllowance: 240 - elapsed, calculated: 240 - elapsed,
            refreshStarted: now - 375_000, brokerStarted: now - 125_000});
    };
    for (let elapsed = 0; elapsed <= 90; elapsed++)
        sample(elapsed);
    assert.equal(logs.length, 2);
    assert.deepEqual(logs.map(log => log.fields.reason), ['initial', 'periodic']);
    assert.deepEqual(logs[1].fields, {reason: 'periodic', source: 'native',
        timer_available: true, native_available: true, timer_remaining: 239,
        native_remaining: 180, allowance: 180, remaining: 180, previous_remaining: 180,
        elapsed_ms: 60000, refresh_ms: 375, broker_ms: 125});
    indicator._recordCountdownRefresh({estimate: [false, 0, wall + 90 + 150],
        currentTime: wall + 90, managerLimit: 0, effectiveAllowance: 150,
        calculated: 150, refreshStarted: now, brokerStarted: now});
    assert.equal(logs.at(-1).fields.reason, 'source-changed');
    assert.equal(logs.at(-1).fields.native_available, false);
    assert.equal(logs.at(-1).fields.source, 'timer');
    const privateText = 'private@example.test /home/private';
    for (const {event, fields} of logs) {
        assert.throws(() => diagnosticEnvelope(catalog, event, {...fields, deadline: wall}));
        for (const key of Object.keys(fields))
            assert.throws(() => diagnosticEnvelope(catalog, event, {...fields, [key]: privateText}));
        assert.ok(!JSON.stringify(fields).includes(String(wall)));
    }
});

test('countdown state records inactivity and lock transitions without per-second history', () => {
    const logs = [];
    const sessionMode = {isLocked: false, isGreeter: false};
    const manager = {dailyLimitTime: 340, dailyLimitEnabled: true};
    const indicator = createIndicator({Main: {sessionMode},
        logInfo: (event, fields) => logs.push(JSON.parse(diagnosticEnvelope(
            catalog, event, JSON.parse(JSON.stringify(fields)))))});
    Object.assign(indicator, {_statusLoaded: true, _calculatedEnd: 340});
    for (let now = 100; now <= 110; now++)
        indicator._recordCountdownState(manager, now);
    assert.equal(logs.length, 1);
    manager.dailyLimitTime = 0;
    indicator._recordCountdownState(manager, 110);
    manager.dailyLimitTime = 340;
    indicator._recordCountdownState(manager, 132);
    sessionMode.isLocked = true;
    indicator._recordCountdownState(manager, 340);
    assert.deepEqual(logs.map(log => log.fields.native_available), [true, false, true, true]);
    assert.deepEqual(logs.map(log => log.fields.remaining), [240, 230, 208, 0]);
    assert.equal(logs.at(-1).fields.locked, true);
    // Logging failures cannot interrupt the same verified countdown path.
    const failing = createIndicator({Main: {sessionMode}, logInfo() { throw new Error('private'); }});
    Object.assign(failing, {_statusLoaded: true, _calculatedEnd: 340});
    assert.doesNotThrow(() => failing._recordCountdownState(manager, 340));
    assert.doesNotThrow(() => failing._recordCountdownRefresh({estimate: [], currentTime: 340,
        managerLimit: 340, effectiveAllowance: 0, calculated: 0,
        refreshStarted: 0, brokerStarted: 0}));
});
