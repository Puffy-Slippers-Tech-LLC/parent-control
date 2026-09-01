import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import GLib from 'gi://GLib';

import {AppFilterClient} from './appFilterClient.js';
import {getBlockedTargets, loadAppPolicy} from './appPolicyStore.js';
import {MalcontentClient} from './malcontentClient.js';
import {ParentalApproval} from './parentalApproval.js';
import {ParentalControlsIntegration} from './parentalControlsIntegration.js';
import {isPreview} from './previewMode.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';
import {RequestDialog, RequestPopover} from './requestDialog.js';
import {SessionLimitsClient} from './sessionLimitsClient.js';
import {refreshSharedPreferences} from './sharedPreferencesClient.js';
import {logError, logInfo, logWarning} from './logger.js';

export default class OhNoParentControlExtension extends Extension {
    enable() {
        logInfo('extension enabled');
        this._preview = isPreview();
        this._client = this._preview ? null : new MalcontentClient(response => {
            const durationSeconds =
                this._integration?.observeNativeExtensionResponse(response) ?? 0;
            if (durationSeconds > 0)
                this._indicator?.showGrantedTime(durationSeconds);
        });
        this._approval = this._preview ? null : new ParentalApproval();
        this._appFilter = this._preview ? null : new AppFilterClient();
        this._sessionLimits = this._preview ? null : new SessionLimitsClient();
        this._integration = this._preview ? null : new ParentalControlsIntegration(
            () => this._showDialog());
        this._integration?.enable();
        this._indicator = new RemainingTimeIndicator(
            sourceActor => this._showDialog(sourceActor),
            this._preview ? 45 * 60 : this._integration.getApprovedGrantRemaining(),
            this._preview);
        refreshSharedPreferences().catch(error =>
            logWarning(`could not preload preferences: ${error.message}`));
        if (this._preview) {
            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                this._showDialog();
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    disable() {
        this._dialog?.destroy();
        this._dialog = null;
        this._indicator?.destroy();
        this._indicator = null;
        this._integration?.destroy();
        this._integration = null;
        this._client?.destroy();
        this._client = null;
        this._approval = null;
        this._appFilter = null;
        this._sessionLimits = null;
        logInfo('extension disabled');
    }

    async _showDialog(sourceActor = null) {
        if (this._dialog || this._openingDialog)
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
            durationSeconds, allowSoftBlockedApps, untilEndOfDay = false) => {
            if (this._preview) {
                this._indicator?.showGrantedTime(durationSeconds);
                return true;
            }
            // The panel entry point is available while time remains, so let
            // the timer service decide whether a proactive request is valid.
            if (!sourceActor && !this._integration?.isExhausted())
                throw new Error('Screen-time limit is no longer active');

            logInfo(`requesting ${durationSeconds} seconds of ` +
                (untilEndOfDay ? 'remaining time' : 'additional time'));

            // Both privileged writes go through AccountsService for the same
            // system-bus subject, so the combined meta-action can authorize
            // them with one dialog.
            this._integration?.ensurePolkitAgentPatched();
            const granted = await this._approval.withAuthorization(async () => {
                let grantedDurationSeconds;
                if (untilEndOfDay) {
                    await this._sessionLimits.replaceActiveExtension(
                        durationSeconds);
                    grantedDurationSeconds = durationSeconds;
                } else {
                    grantedDurationSeconds =
                        await this._sessionLimits.addActiveExtension(
                            durationSeconds);
                }

                // Record the authenticated backend write before any optional
                // follow-up work can yield back to the lock screen.
                this._integration?.recordApprovedGrant(grantedDurationSeconds);
                this._indicator?.showGrantedTime(grantedDurationSeconds);

                try {
                    const policy = loadAppPolicy();
                    const blockedTargets = getBlockedTargets(
                        policy, allowSoftBlockedApps);
                    // The combined action implies this permission, so this
                    // must never initiate another auth dialog.
                    await this._appFilter.setBlockedTargets(blockedTargets);
                    logInfo(`applied ${blockedTargets.length} app restrictions`);
                } catch (error) {
                    // A time grant must remain successful even if the
                    // optional app-filter update fails.
                    logWarning(`app filter update failed: ${error.message}`);
                }

                return true;
            });

            logInfo(`request ${granted ? 'approved' : 'rejected'}`);
            return granted;
        };
        this._dialog = sourceActor
            ? new RequestPopover(request, sourceActor)
            : new RequestDialog(request);
        this._dialog.connect('destroy', () => {
            sourceActor?.setRequestActive?.(false);
            this._dialog = null;
        });
        if (!this._dialog.open()) {
            logError('could not open request dialog');
            this._dialog.destroy();
        }
    }
}
