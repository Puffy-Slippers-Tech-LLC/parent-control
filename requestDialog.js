import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';

export const DURATIONS = Object.freeze([
    {label: '15 minutes', seconds: 15 * 60},
    {label: '30 minutes', seconds: 30 * 60},
    {label: '1 hour', seconds: 60 * 60},
    // Malcontent 0.14 defines zero as an extension through local end-of-day.
    {label: 'Until end of day', seconds: 0},
]);

export const RequestDialog = GObject.registerClass(
class RequestDialog extends ModalDialog.ModalDialog {
    _init(onRequest) {
        super._init({styleClass: 'request-more-time-dialog'});
        this._onRequest = onRequest;
        this._working = false;
        this._selected = DURATIONS[1].seconds;
        this._choiceButtons = [];

        const content = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'request-more-time-content',
        });
        this.contentLayout.add_child(content);
        content.add_child(new St.Label({
            style_class: 'request-more-time-title',
            text: 'Request More Time',
        }));
        content.add_child(new St.Label({text: 'How much additional time?'}));

        for (const duration of DURATIONS) {
            const button = new St.Button({
                style_class: 'request-more-time-choice',
                can_focus: true,
                reactive: true,
                toggle_mode: true,
                x_expand: true,
                x_align: Clutter.ActorAlign.FILL,
                label: duration.label,
            });
            button.connect('clicked', () => this._select(duration.seconds));
            content.add_child(button);
            this._choiceButtons.push([button, duration.seconds]);
        }
        this._select(this._selected);

        this.setButtons([
            {label: 'Cancel', action: () => this.close(), key: Clutter.KEY_Escape},
            {label: 'Request', default: true, action: () => this._request()},
        ]);
    }

    _select(seconds) {
        this._selected = seconds;
        for (const [button, value] of this._choiceButtons)
            button.set_checked(value === seconds);
    }

    async _request() {
        if (!this._onRequest || this._working)
            return;
        this._setWorking(true);
        try {
            const granted = await this._onRequest(this._selected);
            if (granted) {
                this.close();
                return;
            }
            this._showError();
        } catch (error) {
            console.error(`[request-more-time] ${error.message}`);
            this._showError();
        } finally {
            this._setWorking(false);
        }
    }

    _showError() {
        if (!this._errorLabel) {
            this._errorLabel = new St.Label({
                style_class: 'request-more-time-error',
                text: 'Your request could not be approved.',
            });
            this.contentLayout.add_child(this._errorLabel);
        }
        this._errorLabel.show();
    }

    _setWorking(working) {
        this._working = working;
        for (const [button] of this._choiceButtons)
            button.reactive = !working;
    }

    destroy() {
        this._onRequest = null;
        super.destroy();
    }
});
