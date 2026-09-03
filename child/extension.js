import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {appName} from './branding.js';
import {isPreview} from './previewMode.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';
import {logError, logInfo, logWarning} from './logger.js';

const INSTALLED_REQUEST_APP = '/usr/bin/oh-no-parent-control';

function requestAppArgv() {
    const override = GLib.getenv('OH_NO_PARENT_CONTROL_REQUEST_APP');
    if (override) {
        const [ok, argv] = GLib.shell_parse_argv(override);
        if (!ok || !argv.length)
            throw new Error('OH_NO_PARENT_CONTROL_REQUEST_APP is not a command');
        return argv;
    }
    return [INSTALLED_REQUEST_APP, '--child-overlay'];
}

export default class OhNoParentControlExtension extends Extension {
    enable() {
        logInfo('extension enabled');
        this._preview = isPreview();
        this._appName = appName(this);
        this._requestProcess = null;
        this._openingRequest = false;
        this._indicator = new RemainingTimeIndicator(
            () => this._showRequest(),
            this._preview ? 45 * 60 : 0,
            this._preview,
            this._appName);
        if (this._preview) {
            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                this._showRequest();
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    disable() {
        this._stopRequest();
        this._indicator?.destroy();
        this._indicator = null;
        logInfo('extension disabled');
    }

    _showRequest() {
        if (this._requestProcess || this._openingRequest)
            return;

        this._openingRequest = true;
        this._indicator?.setRequestActive(true);
        try {
            const argv = requestAppArgv();
            logInfo('request overlay opened');
            this._requestProcess = Gio.Subprocess.new(
                argv, Gio.SubprocessFlags.NONE);
            this._requestProcess.wait_async(null, (process, result) => {
                try {
                    process.wait_finish(result);
                } catch (error) {
                    logWarning(`request overlay exited: ${error.message}`);
                }
                this._requestProcess = null;
                this._indicator?.setRequestActive(false);
                this._indicator?.refreshEstimate();
            });
        } catch (error) {
            logError(`could not open request overlay: ${error.message}`);
            this._indicator?.setRequestActive(false);
        } finally {
            this._openingRequest = false;
        }
    }

    _stopRequest() {
        if (!this._requestProcess)
            return;
        try {
            this._requestProcess.force_exit();
        } catch (error) {
            logWarning(`could not stop request overlay: ${error.message}`);
        }
        this._requestProcess = null;
    }
}
