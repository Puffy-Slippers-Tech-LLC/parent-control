import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function harness() {
    const calls = [];
    const logs = [];
    const source = readFileSync(new URL('../../child/errorHandler.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export class ChildErrorHandler', 'globalThis.ChildErrorHandler = class ChildErrorHandler');
    const context = vm.createContext({
        Gio: {SubprocessFlags: {STDIN_PIPE: 1}, Subprocess: {new(argv, flags) {
            const process = {
                argv, flags, stopped: false,
                communicate_utf8_async(text, _cancel, callback) {
                    this.text = text;
                    this.done = () => callback(this, {});
                },
                communicate_utf8_finish() {},
                force_exit() { this.stopped = true; },
            };
            calls.push(process);
            return process;
        }}},
        logWarning: text => logs.push(text),
    });
    vm.runInContext(source, context);
    return {handler: new context.ChildErrorHandler(() => ['/usr/bin/oh-no-parent-control']), calls, logs};
}

test('reports travel over stdin with Child App context and no private logging', () => {
    const {handler, calls, logs} = harness();
    handler.report(new Error('private@example.test /private/path'));
    assert.equal(calls.length, 1);
    assert.deepEqual(Array.from(calls[0].argv), [
        '/usr/bin/oh-no-parent-control', '--error-report-stdin', '--child-overlay',
    ]);
    assert.equal(calls[0].text, 'Error: private@example.test /private/path');
    assert(!logs.join('').includes('private'));
});

test('duplicate failures preserve the owned reporter and cleanup signals only that process', () => {
    const {handler, calls} = harness();
    handler.report(new Error('first'));
    handler.report(new Error('second'));
    assert.equal(calls.length, 1);
    const unrelated = {stopped: false};
    handler.close();
    assert(calls[0].stopped);
    assert(!unrelated.stopped);
    calls[0].done();
    handler.report(new Error('after disable'));
    assert.equal(calls.length, 1);
});

test('a completed reporter releases ownership and long diagnostics are bounded', () => {
    const {handler, calls} = harness();
    handler.report(new Error('x'.repeat(10000)));
    assert.equal(calls[0].text.length, 3500);
    calls[0].done();
    handler.report(new Error('next'));
    assert.equal(calls.length, 2);
    assert(!calls[0].stopped);
});

test('failed extension startup remains failed with a public exception and a private report', () => {
    const original = new Error('private initialization details');
    const reports = [];
    const source = readFileSync(new URL('../../child/extension.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export default class OhNoParentControlExtension',
            'globalThis.ExtensionUnderTest = class OhNoParentControlExtension');
    const context = vm.createContext({
        Extension: class {},
        ChildErrorHandler: class { report(error) { reports.push(error); } },
        logInfo() {},
        isPreview() { throw original; },
    });
    vm.runInContext(source, context);
    assert.throws(() => new context.ExtensionUnderTest().enable(),
        {message: 'Child App could not start; see the error report.'});
    assert.equal(reports[0], original);
});
