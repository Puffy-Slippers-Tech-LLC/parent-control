import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

import {AppFilterClient} from './appFilterClient.js';
import {getBlockedTargets, loadAppPolicy} from './appPolicyStore.js';
import {MalcontentClient} from './malcontentClient.js';
import {ParentalApproval} from './parentalApproval.js';
import {ParentalControlsIntegration} from './parentalControlsIntegration.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';
import {RequestDialog, RequestPopover} from './requestDialog.js';

const LOG_PREFIX = '[request-more-time]';

export default class RequestMoreTimeExtension extends Extension {
    enable() {
        console.log(`${LOG_PREFIX} extension enabled`);
        this._client = new MalcontentClient(response => {
            const durationSeconds =
                this._integration?.observeNativeExtensionResponse(response) ?? 0;
            if (durationSeconds > 0)
                this._indicator?.showGrantedTime(durationSeconds);
        });
        this._approval = new ParentalApproval();
        this._appFilter = new AppFilterClient();
        this._integration = new ParentalControlsIntegration(() => this._showDialog());
        this._integration.enable();
        this._indicator = new RemainingTimeIndicator(
            sourceActor => this._showDialog(sourceActor),
            this._integration.getApprovedGrantRemaining());
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
        console.log(`${LOG_PREFIX} extension disabled`);
    }

    _showDialog(sourceActor = null) {
        if (this._dialog)
            return;

        console.log(`${LOG_PREFIX} request dialog opened`);
        const request = async (durationSeconds, clearAppRestrictions) => {
            // The panel entry point is available while time remains, so let
            // the timer service decide whether a proactive request is valid.
            if (!sourceActor && !this._integration?.isExhausted())
                throw new Error('Screen-time limit is no longer active');

            console.log(`${LOG_PREFIX} requesting ${durationSeconds} seconds`);

            // Authorize the combined meta-action once. Polkit evaluates the
            // Malcontent check for this same system-bus subject even though a
            // separate extension-agent process performs that check.
            this._integration?.ensurePolkitAgentPatched();
            const granted = await this._approval.withAuthorization(async () => {
                // Both backend actions are implied by the combined approval,
                // so neither call may open its own authentication dialog.
                const approved = await this._client.requestExtension(
                    durationSeconds);

                if (approved) {
                    // Record the authenticated Malcontent approval before any
                    // optional follow-up work can yield back to the lock screen.
                    this._integration?.recordApprovedGrant(durationSeconds);
                    this._indicator?.showGrantedTime(durationSeconds);

                    try {
                        const policy = loadAppPolicy();
                        const blockedTargets = getBlockedTargets(
                            policy, clearAppRestrictions);
                        await this._appFilter.setBlockedTargets(blockedTargets);
                        console.log(`${LOG_PREFIX} applied ${blockedTargets.length} app restrictions`);
                    } catch (error) {
                        // A time grant must remain successful even if the
                        // optional app-filter update fails.
                        console.warn(`${LOG_PREFIX} app filter update failed: ${error.message}`);
                    }
                }

                return approved;
            });

            console.log(`${LOG_PREFIX} request ${granted ? 'approved' : 'rejected'}`);
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
            console.error(`${LOG_PREFIX} could not open request dialog`);
            this._dialog.destroy();
        }
    }
}
