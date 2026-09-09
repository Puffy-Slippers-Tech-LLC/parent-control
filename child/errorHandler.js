import Gio from 'gi://Gio';

import {logWarning} from './logger.js';

// One reporting window per extension instance. Exception text travels only on
// the child's private stdin pipe, never in process arguments or log records.
export class ChildErrorHandler {
    constructor(requestArgv) {
        this._requestArgv = requestArgv;
        this._process = null;
        this._closed = false;
    }

    report(error) {
        logWarning('child operation failed; error report available');
        if (this._closed || this._process)
            return;
        try {
            const argv = [...this._requestArgv(), '--error-report-stdin'];
            if (!argv.includes('--child-overlay'))
                argv.push('--child-overlay');
            const process = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDIN_PIPE);
            this._process = process;
            const text = `${error?.name ?? 'Error'}: ${error?.message ?? 'Unknown error'}`;
            process.communicate_utf8_async(text.slice(0, 3500), null, (owned, result) => {
                try {
                    owned.communicate_utf8_finish(result);
                } catch (_error) {
                    logWarning('child error reporter communication failed');
                } finally {
                    if (this._process === owned)
                        this._process = null;
                }
            });
        } catch (_error) {
            logWarning('child error reporter unavailable');
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
                logWarning('child error reporter cleanup failed');
            }
        }
    }
}
