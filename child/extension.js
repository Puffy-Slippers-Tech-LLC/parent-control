import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import Gio from 'gi://Gio';

import {appLogoPath, appName} from './branding.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';
import {ChildErrorHandler} from './errorHandler.js';
import {logInfo, logWarning} from './logger.js';
import {canOpenRequest, requestCompletionState} from './indicatorLogic.mjs';
import {TranslationContext} from './localization.js';
import {ChildApplicationUi} from './applicationUi.js';
import {GnomeApplicationUiAdapter} from './gnomeApplicationUiAdapter.js';
import {ReminderPreview} from './reminderPreview.js';

const INSTALLED_REQUEST_APP = '/usr/bin/oh-no-parent-control';
const SETTINGS_SCHEMA = 'com.puffyslippers.oh-no-parent-control.child';

export default class OhNoParentControlExtension extends Extension {
    _requestAppArgv() {
        return [INSTALLED_REQUEST_APP, '--child-overlay'];
    }

    enable() {
        this._errors = new ChildErrorHandler(() => this._requestAppArgv());
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
        logInfo('child.enabled');
        this._appName = appName(this);
        this._settings = this.getSettings(SETTINGS_SCHEMA);
        this._requestProcess = null;
        this._openingRequest = false;
        this._translations = new TranslationContext(this.path);
        this._indicator = this._createIndicator();
        try {
            this._reminderPreview = new ReminderPreview(this._appName, appLogoPath(this));
        } catch (_error) {
            // Preview availability must not disable countdown or locking.
            this._errors.report(new Error('Reminder preview could not start'));
        }
        this._applicationUiAdapter = new GnomeApplicationUiAdapter(this._indicator, this._reminderPreview);
        try {
            this._applicationUi = new ChildApplicationUi(this._applicationUiAdapter);
        } catch (_error) {
            this._applicationUiAdapter.close();
            // A UI transport failure must not disable screen-time enforcement.
            this._errors.report(new Error('Child Application UI could not start'));
        }
        this._refreshLanguage();
    }

    _refreshLanguage() {
        this._translations?.refresh(() => {
            this._indicator?.refreshLanguage();
            this._indicator?.refreshNotifications();
        }, error => {
            this._errors?.report(error);
            this._indicator?.refreshNotifications();
        });
    }

    _createIndicator() {
        return new RemainingTimeIndicator(
            () => this._showRequest(),
            0,
            false,
            this._appName,
            '',
            appLogoPath(this),
            this._settings,
            error => this._errors.report(error), this._translations,
            () => this._refreshLanguage());
    }

    disable() {
        this._reminderPreview?.close();
        this._reminderPreview = null;
        this._applicationUi?.close();
        this._applicationUi = null;
        this._applicationUiAdapter?.close();
        this._applicationUiAdapter = null;
        if (this._translations) this._translations.closed = true;
        this._translations = null;
        this._errors?.close();
        this._stopRequest();
        this._indicator?.destroy();
        this._indicator = null;
        this._settings = null;
        logInfo('child.disabled');
    }

    _showRequest() {
        if (!canOpenRequest(Boolean(this._requestProcess), this._openingRequest))
            return;

        this._openingRequest = true;
        this._indicator?.setRequestActive(true);
        try {
            const argv = this._requestAppArgv();
            logInfo('child.overlay-opened');
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
                this._refreshLanguage();
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
            logWarning('child.overlay-stop-failed');
        }
        this._requestProcess = null;
    }
}
