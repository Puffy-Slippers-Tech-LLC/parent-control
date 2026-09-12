import Gio from 'gi://Gio';

import {logWarning} from './logger.js';

// One reporting window per extension instance. Exception content is never
// copied into a pipe, command argument, diagnostic event, or feedback report.
export class ChildErrorHandler {
    constructor(requestArgv) {
        this._requestArgv = requestArgv;
        this._process = null;
        this._closed = false;
    }

    report(error) {
        logWarning('child.error');
        if (this._closed || this._process)
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
                } catch (_error) {
                    logWarning('child.report-communication-failed');
                } finally {
                    if (this._process === owned)
                        this._process = null;
                }
            });
        } catch (_error) {
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
            } catch (_error) {
                logWarning('child.report-cleanup-failed');
            }
        }
    }
}
