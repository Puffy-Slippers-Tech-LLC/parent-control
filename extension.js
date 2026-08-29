import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

import {MalcontentClient} from './malcontentClient.js';
import {ParentalControlsIntegration} from './parentalControlsIntegration.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';
import {RequestDialog, RequestPopover} from './requestDialog.js';

const LOG_PREFIX = '[request-more-time]';

export default class RequestMoreTimeExtension extends Extension {
    enable() {
        console.log(`${LOG_PREFIX} extension enabled`);
        this._client = new MalcontentClient();
        this._integration = new ParentalControlsIntegration(() => this._showDialog());
        this._integration.enable();
        this._indicator = new RemainingTimeIndicator(sourceActor =>
            this._showDialog(sourceActor));
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
        console.log(`${LOG_PREFIX} extension disabled`);
    }

    _showDialog(sourceActor = null) {
        if (this._dialog)
            return;

        console.log(`${LOG_PREFIX} request dialog opened`);
        const request = async durationSeconds => {
            // The panel entry point is available while time remains, so let
            // the timer service decide whether a proactive request is valid.
            if (!sourceActor && !this._integration?.isExhausted())
                throw new Error('Screen-time limit is no longer active');

            console.log(`${LOG_PREFIX} requesting ${durationSeconds} seconds`);
            const granted = await this._client.requestExtension(durationSeconds);
            console.log(`${LOG_PREFIX} request ${granted ? 'approved' : 'rejected'}`);
            if (granted) {
                this._indicator?.showGrantedTime(durationSeconds);
                try {
                    await this._integration.refreshState();
                } catch (error) {
                    console.warn(`${LOG_PREFIX} timer refresh failed: ${error.message}`);
                }
            }
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
