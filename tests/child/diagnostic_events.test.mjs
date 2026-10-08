import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

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
