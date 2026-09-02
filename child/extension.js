import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {AboutDialog} from './aboutDialog.js';
import {listApprovers} from './approverClient.js';
import {appName} from './branding.js';
import {isPreview} from './previewMode.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';
import {requestOwnAccess} from './requestAccessClient.js';
import {RequestPopover} from './requestDialog.js';
import {refreshSharedPreferences} from './sharedPreferencesClient.js';
import {logError, logInfo, logWarning} from './logger.js';

export default class OhNoParentControlExtension extends Extension {
    enable() {
        logInfo('extension enabled');
        this._preview = isPreview();
        this._appName = appName(this);
        this._indicator = new RemainingTimeIndicator(
            sourceActor => this._showDialog(sourceActor),
            this._preview ? 45 * 60 : 0,
            this._preview,
            this._appName);
        refreshSharedPreferences().catch(error =>
            logWarning(`could not preload preferences: ${error.message}`));
        if (this._preview) {
            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                this._showDialog(this._indicator);
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    disable() {
        this._dialog?.destroy();
        this._dialog = null;
        this._aboutDialog?.destroy();
        this._aboutDialog = null;
        this._indicator?.destroy();
        this._indicator = null;
        logInfo('extension disabled');
    }

    async _showDialog(sourceActor) {
        if (this._dialog || this._openingDialog)
            return;
        if (!sourceActor)
            return;

        this._openingDialog = true;
        try {
            await refreshSharedPreferences();
        } catch (error) {
            logWarning(`could not refresh preferences: ${error.message}`);
        } finally {
            this._openingDialog = false;
        }
        if (this._dialog)
            return;

        logInfo('request dialog opened');
        const request = async (
            durationSeconds, allowSoftBlockedApps, untilEndOfDay = false,
            approverUid) => {
            if (this._preview) {
                this._indicator?.showGrantedTime(durationSeconds);
                return true;
            }
            logInfo(`requesting ${durationSeconds} seconds of ` +
                (untilEndOfDay ? 'remaining time' : 'additional time'));

            const result = await requestOwnAccess(
                approverUid,
                untilEndOfDay ? 0 : durationSeconds,
                allowSoftBlockedApps);
            logInfo(`request=${result.correlationId} outcome=${result.outcome}`);
            if (result.outcome !== 'approved')
                return false;
            this._indicator?.showGrantedTime(result.grantedDurationSeconds);
            return true;
        };
        this._dialog = new RequestPopover(
            request, sourceActor, action => this._showAbout(action), this._appName);
        this._dialog.connect('destroy', () => {
            sourceActor?.setRequestActive?.(false);
            this._dialog = null;
        });
        if (!this._dialog.open()) {
            logError('could not open request dialog');
            this._dialog.destroy();
            return;
        }
        try {
            this._dialog.setApprovers(await listApprovers());
        } catch (error) {
            logWarning(`could not load approving administrators: ${error.message}`);
            this._dialog?.setApprovers([]);
        }
    }

    _showAbout(action) {
        if (action === 'help') {
            try {
                const [ok, contents] = GLib.file_get_contents(
                    '/usr/share/oh-no-parent-control/brand.json');
                if (ok) {
                    const brand = JSON.parse(new TextDecoder().decode(contents));
                    Gio.AppInfo.launch_default_for_uri(brand.app_url, null);
                }
            } catch (error) {
                logWarning(`could not open help: ${error.message}`);
            }
            return;
        }
        if (this._aboutDialog)
            return;
        this._aboutDialog = new AboutDialog(this);
        this._aboutDialog.connect('closed', () => this._aboutDialog = null);
        this._aboutDialog.open();
    }
}
