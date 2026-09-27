import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

const catalog = JSON.parse(readFileSync(new URL(
    '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url)));

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
