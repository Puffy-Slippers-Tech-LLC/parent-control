import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {appLogoPath, appName} from './branding.js';
import {
    isPreview,
    previewGenerationMarker,
    previewStartsWithRequestOpen,
} from './previewMode.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';
import {ChildErrorHandler} from './errorHandler.js';
import {logInfo, logWarning} from './logger.js';
import {canOpenRequest, requestCompletionState} from './indicatorLogic.mjs';

const INSTALLED_REQUEST_APP = '/usr/bin/oh-no-parent-control';
const SETTINGS_SCHEMA = 'com.puffyslippers.oh-no-parent-control.child';

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
        this._errors = new ChildErrorHandler(requestAppArgv);
        try {
            this._enable();
        } catch (error) {
            this._errors.report(error);
            // Keep GNOME's extension startup failure visible to the broker;
            // a reporting dialog cannot make a failed enforcer healthy.
            throw new Error('Child App could not start; see the error report.');
        }
    }

    _enable() {
        logInfo('extension enabled');
        this._preview = isPreview();
        this._appName = appName(this);
        this._settings = this.getSettings(SETTINGS_SCHEMA);
        this._requestProcess = null;
        this._openingRequest = false;
        this._indicator = new RemainingTimeIndicator(
            () => this._showRequest(),
            this._preview ? 45 * 60 : 0,
            this._preview,
            this._appName,
            previewGenerationMarker(),
            appLogoPath(this),
            this._settings,
            error => this._errors.report(error));
        if (previewStartsWithRequestOpen()) {
            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                this._showRequest();
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    disable() {
        this._errors?.close();
        this._stopRequest();
        this._indicator?.destroy();
        this._indicator = null;
        this._settings = null;
        logInfo('extension disabled');
    }

    _showRequest() {
        if (!canOpenRequest(Boolean(this._requestProcess), this._openingRequest))
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
                    this._errors.report(error);
                }
                this._requestProcess = null;
                const completion = requestCompletionState();
                this._indicator?.setRequestActive(completion.requestActive);
                if (completion.refreshEstimate)
                    this._indicator?.refreshEstimate();
            });
        } catch (error) {
            this._errors.report(error);
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
        } catch (_error) {
            logWarning('could not stop owned request overlay');
        }
        this._requestProcess = null;
    }
}
