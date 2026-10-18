import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

const catalog = JSON.parse(readFileSync(new URL(
    '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url)));

function harness({brokenLogging = false} = {}) {
    const calls = [];
    const logs = [];
    class BusError extends Error {
        constructor(remote) { super('private error message'); this.remote = remote; }
    }
    const source = readFileSync(new URL('../../child/errorHandler.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace(/^export function /gm, 'function ')
        .replace('export class ChildErrorHandler', 'globalThis.ChildErrorHandler = class ChildErrorHandler');
    const context = vm.createContext({
        Error, TypeError, RangeError, ReferenceError, SyntaxError, URIError, EvalError,
        GLib: {Error: BusError},
        timerErrorCategory: () => 'other',
        Gio: {DBusError: {get_remote_error: error => error.remote},
            SubprocessFlags: {STDIN_PIPE: 1}, Subprocess: {new(argv, flags) {
            const process = {
                argv, flags, stopped: false,
                communicate_utf8_async(text, _cancel, callback) {
                    this.text = text;
                    this.done = () => callback(this, {});
                },
                communicate_utf8_finish() {},
                get_if_exited() { return !this.signal; },
                get_exit_status() { return this.exitCode ?? 0; },
                get_if_signaled() { return Boolean(this.signal); },
                get_term_sig() { return this.signal; },
                force_exit() { this.stopped = true; },
            };
            calls.push(process);
            return process;
        }}},
        logWarning: text => logs.push(text),
        logError(event, fields) {
            if (brokenLogging) throw Error('private logging failure');
            logs.push(JSON.parse(diagnosticEnvelope(catalog, event,
                JSON.parse(JSON.stringify(fields)))));
        },
    });
    vm.runInContext(source, context);
    return {handler: new context.ChildErrorHandler(() => ['/usr/bin/oh-no-parent-control']), calls, logs, BusError,
        record: context.recordChildFailure};
}

test('reports travel over stdin with Child App context and no private logging', () => {
    const {handler, calls, logs} = harness();
    handler.report(new Error('private@example.test /private/path'));
    assert.equal(calls.length, 1);
    assert.deepEqual(Array.from(calls[0].argv), [
        '/usr/bin/oh-no-parent-control', '--error-report-stdin', '--child-overlay',
    ]);
    assert.equal(calls[0].text, 'child-operation-failed');
    assert(!JSON.stringify(logs).includes('private'));
    assert.deepEqual(logs[0].fields, {operation: 'other', error_type: 'Error', category: 'other'});
});

test('failure provenance distinguishes operations and types without reading exception text', () => {
    const {handler, calls, logs} = harness();
    const error = new TypeError('private@example.test /home/private');
    for (const key of ['message', 'stack', 'name'])
        Object.defineProperty(error, key, {get() { throw Error('must not read'); }});
    handler.report(error, 'reminder-render');
    handler.report(new RangeError('private'), 'language');
    handler.report({message: 'private', name: 'TypeError'}, 'private-operation');
    assert.equal(calls.length, 1, 'an existing reporter does not discard later provenance');
    assert.deepEqual(logs.filter(log => log.event === 'child.failure').map(log => log.fields), [
        {operation: 'reminder-render', error_type: 'TypeError', category: 'other'},
        {operation: 'language', error_type: 'RangeError', category: 'other'},
        {operation: 'other', error_type: 'other', category: 'other'},
    ]);
    assert(!JSON.stringify(logs).includes('private'));
    handler.close();
    const before = logs.length;
    handler.report(error, 'startup');
    assert.equal(logs.length, before);
});

test('diagnostic failure cannot prevent opening the error reporter', () => {
    const {handler, calls} = harness({brokenLogging: true});
    assert.doesNotThrow(() => handler.report(new Error('private'), 'resume-refresh'));
    assert.equal(calls.length, 1);
});

test('native helper failures retain safe provenance without launching a reporting process', () => {
    const {record, calls, logs} = harness();
    const operations = ['session-monitor-attach', 'session-monitor-signal', 'session-monitor-observe',
        'session-monitor-cleanup', 'unlock-startup', 'unlock-signal', 'unlock-dispatch',
        'unlock-observe', 'unlock-cleanup', 'locked-focus'];
    for (const operation of operations) record(new TypeError('PRIVATE /home/private'), operation);
    assert.equal(calls.length, 0);
    assert.deepEqual(logs.map(log => log.fields.operation), operations);
    assert(logs.every(log => log.fields.error_type === 'TypeError'));
    assert(!JSON.stringify(logs).includes('PRIVATE'));
    assert(!JSON.stringify(logs).includes('/home/private'));
    assert.doesNotThrow(() => harness({brokenLogging: true}).record(new Error('PRIVATE'), 'unlock-dispatch'));
});

test('broker refusals retain reviewed categories without arbitrary remote error names', () => {
    const {handler, logs, BusError} = harness();
    for (const name of ['RebootRequired', 'AccessDenied', 'BackendFailure', 'private.error'])
        handler.report(new BusError(name.includes('.') ? name
            : `com.puffyslippers.OhNoParentControl1.Error.${name}`), 'language');
    assert.deepEqual(logs.filter(log => log.event === 'child.failure').map(log => log.fields.category),
        ['reboot-required', 'access-denied', 'backend-failure', 'other']);
    assert(!JSON.stringify(logs).includes('private'));
});

test('reporter failures preserve their own provenance without recursively launching reports', () => {
    const {handler, calls, logs} = harness();
    handler.report(new Error('private'), 'resume-refresh');
    calls[0].communicate_utf8_finish = () => { throw new TypeError('private'); };
    calls[0].done();
    assert.equal(calls.length, 1);
    assert.deepEqual(logs.filter(log => log.event === 'child.failure').at(-1).fields,
        {operation: 'report-communication', error_type: 'TypeError', category: 'other'});
});

test('completed reporter waits retain abnormal exit status without output or recursive reports', () => {
    const {handler, calls, logs} = harness();
    handler.report(new Error('private'), 'language');
    calls[0].exitCode = 1;
    calls[0].done();
    handler.report(new Error('private'), 'resume-refresh');
    calls[1].signal = 11;
    calls[1].done();
    handler.report(new Error('private'), 'startup');
    calls[2].done();
    assert.deepEqual(logs.filter(log => log.event === 'child.process-exit').map(log => log.fields), [
        {operation: 'report', kind: 'exited', code: 1},
        {operation: 'report', kind: 'signaled', code: 11},
    ]);
    assert.equal(calls.length, 3);
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
    assert.equal(calls[0].text, 'child-operation-failed');
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
        LockedSessionFocus: class { close() {} },
        SessionDiagnostics: class { ready = Promise.resolve(null); close() {} },
        global: {stage: {context: {get_backend: () => ({get_default_seat: () => ({})})}}},
        Main: {sessionMode: {}},
        ChildErrorHandler: class { report(error) { reports.push(error); } },
        logInfo() {},
        appName() { throw original; },
    });
    vm.runInContext(source, context);
    assert.throws(() => new context.ExtensionUnderTest().enable(),
        {message: 'Child App could not start; see the error report.'});
    assert.equal(reports[0], original);
});

test('production extension uses live state while the separate preview supplies fixtures', () => {
    const indicators = [];
    const contexts = [];
    let language = 'en';
    let previewLanguage = 'de';
    let requestDone;
    const context = vm.createContext({
        Extension: class { getSettings() { return {}; } },
        ChildErrorHandler: class { report(error) { throw error; } },
        GnomeApplicationUiAdapter: class { close() {} },
        ChildApplicationUi: class { close() {} },
        ReminderPreview: class { close() {} },
        WellbeingSuppression: class { close() {} },
        LockedSessionFocus: class { close() {} },
        SessionDiagnostics: class { ready = Promise.resolve(null); close() {} },
        global: {stage: {context: {get_backend: () => ({get_default_seat: () => ({})})}}},
        Main: {timeLimitsManager: {}, sessionMode: {}, layoutManager: {connectObject() {}}},
        TranslationContext: class {
            constructor(directory) {
                this.directory = directory;
                this.refreshes = 0;
                contexts.push(this);
            }
            apply(saved) { this.language = saved; }
            refresh(changed) { this.refreshes++; this.apply(language); changed(); }
        },
        RemainingTimeIndicator: class {
            constructor(...args) { indicators.push(args); this.languageRefreshes = 0; }
            refreshLanguage() { this.languageRefreshes++; }
            setRequestActive(active) { this.active = active; }
            refreshEstimate() {}
            refreshNotifications() {}
        },
        appName: () => 'Parent Control',
        appLogoPath: () => '/product-logo.png',
        logInfo() {},
        canOpenRequest: () => true,
        requestCompletionState: () => ({requestActive: false, refreshEstimate: true}),
        recordChildProcessExit() {},
        Gio: {SubprocessFlags: {NONE: 0}, Subprocess: {new() {
            return {wait_async(_cancel, done) { requestDone = () => done(this, {}); },
                wait_finish() {}};
        }}},
        GLib: {getenv() { throw new Error('Production must not read preview overrides'); }},
    });
    const source = readFileSync(new URL('../../child/extension.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export default class OhNoParentControlExtension',
            'globalThis.OhNoParentControlExtension = class OhNoParentControlExtension');
    vm.runInContext(source, context);
    const production = new context.OhNoParentControlExtension();
    production.enable();
    assert.deepEqual(Array.from(production._requestAppArgv()),
        ['/usr/bin/oh-no-parent-control', '--child-overlay']);
    assert.equal(indicators[0][1], 0);
    assert.equal(indicators[0][2], false);
    assert.equal(indicators[0][4], '');
    assert.equal(indicators[0][8], contexts[0]);
    assert.equal(contexts[0].refreshes, 1);
    assert.equal(production._indicator.languageRefreshes, 1);
    production._showRequest();
    language = 'fr';
    requestDone();
    assert.equal(contexts[0].language, 'fr');
    assert.equal(production._indicator.languageRefreshes, 2);
    assert.equal(production._indicator.active, false);

    context.GLib = {getenv: () => 'preview-app', shell_parse_argv: () => [true, ['preview-app']]};
    context.TextDecoder = TextDecoder;
    context.Gio.File = {new_for_path: () => ({load_contents: () =>
        [true, new TextEncoder().encode(previewLanguage)]})};
    context.previewStartsWithRequestOpen = () => false;
    context.previewGenerationMarker = () => 'generation-one';
    const previewSource = readFileSync(new URL('../../child/previewExtension.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export default class PreviewExtension', 'globalThis.PreviewExtension = class PreviewExtension');
    vm.runInContext(previewSource, context);
    const preview = new context.PreviewExtension();
    preview.enable();
    assert.deepEqual(Array.from(preview._requestAppArgv()), ['preview-app']);
    assert.equal(indicators[1][1], 45 * 60);
    assert.equal(indicators[1][2], true);
    assert.equal(indicators[1][4], 'generation-one');
    assert.equal(indicators[1][8], contexts[1]);
    assert.notEqual(contexts[0], contexts[1]);
    assert.equal(contexts[1].refreshes, 0);
    assert.equal(contexts[1].language, 'de');
    assert.equal(preview._indicator.languageRefreshes, 1);
    preview._showRequest();
    previewLanguage = 'ja';
    requestDone();
    assert.equal(contexts[1].language, 'ja');
    assert.equal(preview._indicator.languageRefreshes, 2);
    assert.equal(preview._indicator.active, false);
});

test('suppression startup/reporting and shutdown failures cannot disable the enforcer', () => {
    let destroyed = false;
    const context = vm.createContext({
        Extension: class { getSettings() { return {}; } },
        Main: {timeLimitsManager: {}, sessionMode: {}, layoutManager: {connectObject() {}}},
        LockedSessionFocus: class { close() {} },
        SessionDiagnostics: class { ready = Promise.resolve(null); close() {} },
        global: {stage: {context: {get_backend: () => ({get_default_seat: () => ({})})}}},
        ChildErrorHandler: class { report() { throw Error('report unavailable'); } close() {} },
        WellbeingSuppression: class { constructor() { throw Error('helper unavailable'); } },
        ReminderPreview: class { close() {} },
        ChildApplicationUi: class { close() {} },
        GnomeApplicationUiAdapter: class { close() {} },
        TranslationContext: class { refresh(done) { done(); } },
        appName: () => 'Product', appLogoPath: () => '/logo', logInfo() {}, logWarning() {},
    });
    vm.runInContext(readFileSync(new URL('../../child/extension.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export default class OhNoParentControlExtension', 'globalThis.Product = class'), context);
    const extension = new context.Product();
    const enforcer = {refreshLanguage() {}, refreshNotifications() {},
        destroy() { destroyed = true; }};
    extension._createIndicator = () => enforcer;
    extension.enable();
    assert.equal(extension._indicator, enforcer);
    assert(extension._applicationUi);
    extension._wellbeing = {close() { throw Error('suppression cleanup failed'); }};
    extension.disable();
    assert.equal(destroyed, true);
});
