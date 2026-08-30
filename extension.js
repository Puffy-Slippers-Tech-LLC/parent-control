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

            // The Malcontent extension agent owns the real
            // SessionLimits.Extend polkit action. ALLOW_INTERACTIVE_AUTHORIZATION
            // must be present on this request so that agent can ask the parent;
            // preauthorizing a separate action for GNOME Shell does not grant
            // authorization to the agent process.
            this._integration?.ensurePolkitAgentPatched();
            const granted = await this._client.requestExtensionInteractive(
                durationSeconds);

            if (granted) {
                // Record the authenticated Malcontent approval before any
                // optional follow-up work can yield back to the lock screen.
                this._integration?.recordApprovedGrant(durationSeconds);
                this._indicator?.showGrantedTime(durationSeconds);
            }

            if (granted) {
                try {
                    const policy = loadAppPolicy();
                    const blockedTargets = getBlockedTargets(
                        policy, clearAppRestrictions);
                    // Changing an AccountsService app filter is privileged.
                    // Permit Polkit interaction here so the requested policy
                    // transition cannot silently fail for a restricted user.
                    await this._appFilter.setBlockedTargets(blockedTargets, true);
                    console.log(`${LOG_PREFIX} applied ${blockedTargets.length} app restrictions`);
                } catch (error) {
                    // A time grant must remain successful even if the optional
                    // app-filter update requires separate authorization.
                    console.warn(`${LOG_PREFIX} app filter update failed: ${error.message}`);
                }
            }

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
