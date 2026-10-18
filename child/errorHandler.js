import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {logError, logWarning} from './logger.js';
import {timerErrorCategory} from './timerQuery.js';

const OPERATIONS = new Set([
    'startup', 'wellbeing', 'reminder-preview', 'ui-transport', 'language',
    'request-activate', 'request-wait', 'request-start', 'countdown-preference',
    'resume-refresh', 'countdown-refresh', 'session-prepare', 'session-lock',
    'reminder-settings', 'reminder-render', 'reminder-policy',
    'report-start', 'report-communication', 'report-cleanup',
    'session-monitor-attach', 'session-monitor-signal', 'session-monitor-observe',
    'session-monitor-cleanup', 'unlock-startup', 'unlock-signal', 'unlock-dispatch',
    'unlock-observe', 'unlock-cleanup', 'locked-focus',
]);
const BROKER_ERRORS = new Map([
    ['AccessDenied', 'access-denied'], ['InvalidRequest', 'invalid-request'],
    ['Busy', 'busy'], ['RateLimited', 'rate-limited'], ['BackendFailure', 'backend-failure'],
    ['RollbackFailure', 'rollback-failure'], ['RebootRequired', 'reboot-required'], ['Failed', 'failed'],
].map(([name, category]) => [`com.puffyslippers.OhNoParentControl1.Error.${name}`, category]));

function errorType(error) {
    // Inspect only built-in types; names, messages and stacks can contain PII.
    if (error instanceof GLib.Error) return 'GLib.Error';
    for (const type of [TypeError, RangeError, ReferenceError, SyntaxError, URIError, EvalError, Error])
        if (error instanceof type) return type.name;
    return 'other';
}

function errorCategory(error) {
    if (error instanceof GLib.Error) {
        const known = BROKER_ERRORS.get(Gio.DBusError.get_remote_error(error));
        if (known) return known;
    }
    return timerErrorCategory(error);
}

// Also used by optional native helpers: logging must not open a reporter or
// change the native operation, even when the diagnostic transport is broken.
export function recordChildFailure(error, operation = 'other') {
    try {
        logError('child.failure', {
            operation: OPERATIONS.has(operation) ? operation : 'other',
            error_type: errorType(error), category: errorCategory(error),
        });
    } catch (_error) { /* diagnostics must not prevent recovery */ }
}

// Waiting/communicating successfully does not mean the child process succeeded.
// Record only bounded exit metadata, never its output or command arguments.
export function recordChildProcessExit(process, operation) {
    try {
        let kind = 'other';
        let code = 256;
        if (process.get_if_exited()) {
            kind = 'exited';
            code = process.get_exit_status();
        } else if (process.get_if_signaled()) {
            kind = 'signaled';
            code = process.get_term_sig();
        }
        if (kind === 'exited' && code === 0) return;
        logError('child.process-exit', {
            operation: ['request', 'report'].includes(operation) ? operation : 'other',
            kind, code: Number.isInteger(code) && code >= 0 && code <= 255 ? code : 256,
        });
    } catch (_error) { /* diagnostics cannot interrupt process cleanup */ }
}

// One reporting window per extension instance. Exception content is never
// copied into a pipe, command argument, diagnostic event, or feedback report.
export class ChildErrorHandler {
    constructor(requestArgv) {
        this._requestArgv = requestArgv;
        this._process = null;
        this._closed = false;
    }

    _recordFailure(error, operation) {
        recordChildFailure(error, operation);
    }

    report(error, operation = 'other') {
        if (this._closed)
            return;
        this._recordFailure(error, operation);
        logWarning('child.error');
        if (this._process)
            return;
        try {
            const argv = [...this._requestArgv(), '--error-report-stdin'];
            if (!argv.includes('--child-overlay'))
                argv.push('--child-overlay');
            const process = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDIN_PIPE);
            this._process = process;
            process.communicate_utf8_async('child-operation-failed', null, (owned, result) => {
                try {
                    owned.communicate_utf8_finish(result);
                    if (!this._closed)
                        recordChildProcessExit(owned, 'report');
                } catch (error) {
                    this._recordFailure(error, 'report-communication');
                    logWarning('child.report-communication-failed');
                } finally {
                    if (this._process === owned)
                        this._process = null;
                }
            });
        } catch (error) {
            this._recordFailure(error, 'report-start');
            logWarning('child.report-unavailable');
        }
    }

    close() {
        this._closed = true;
        const owned = this._process;
        this._process = null;
        if (owned) {
            try {
                owned.force_exit();
            } catch (error) {
                this._recordFailure(error, 'report-cleanup');
                logWarning('child.report-cleanup-failed');
            }
        }
    }
}
