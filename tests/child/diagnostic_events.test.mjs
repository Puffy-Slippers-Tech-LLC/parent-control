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
