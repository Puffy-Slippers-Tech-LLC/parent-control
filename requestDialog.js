import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as BoxPointer from 'resource:///org/gnome/shell/ui/boxpointer.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

export const DURATIONS = Object.freeze([
    {label: '5 minutes', seconds: 5 * 60},
    {label: '15 minutes', seconds: 15 * 60},
    {label: '30 minutes', seconds: 30 * 60},
    {label: '1 hour', seconds: 60 * 60},
    {label: '2 hours', seconds: 2 * 60 * 60},
    {label: '4 hours', seconds: 4 * 60 * 60},
    {label: 'Rest of the day', seconds: 0},
    {label: 'Custom value', seconds: null},
]);

const CUSTOM_STEP_MINUTES = 15;

// Both the login modal and panel popup use this form.
class RequestForm {
    constructor(onRequest, onClose) {
        this._onRequest = onRequest;
        this._onClose = onClose;
        this._working = false;
        this._selected = DURATIONS[1].seconds;
        this._choiceButtons = [];

        this.actor = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'request-more-time-content',
        });
        this.actor.add_child(new St.Label({
            style_class: 'request-more-time-title',
            text: 'Request Time',
        }));
        for (const [index, duration] of DURATIONS.entries()) {
            const button = new St.Button({
                style_class: 'request-more-time-choice',
                can_focus: true,
                reactive: true,
                track_hover: true,
                toggle_mode: true,
                x_expand: true,
                x_align: Clutter.ActorAlign.FILL,
                label: duration.label,
            });
            button.connect('clicked', () => this._select(duration.seconds));
            button.connect('key-press-event', (_actor, event) =>
                this._handleChoiceKeyPress(index, event));
            this.actor.add_child(button);
            this._choiceButtons.push([button, duration.seconds]);
        }

        this._customRow = new St.BoxLayout({
            style_class: 'request-more-time-custom-row',
            x_align: Clutter.ActorAlign.CENTER,
        });
        this._customEntry = new St.Entry({
            style_class: 'request-more-time-custom-entry',
            can_focus: true,
            text: String(CUSTOM_STEP_MINUTES),
        });
        this._customEntry.clutter_text.set_input_purpose(
            Clutter.InputContentPurpose.DIGITS);
        this._customEntry.clutter_text.connect('key-press-event', (_actor, event) => {
            const key = event.get_key_symbol();
            if (key === Clutter.KEY_Return || key === Clutter.KEY_KP_Enter) {
                this.request();
                return Clutter.EVENT_STOP;
            }
            if (key === Clutter.KEY_Up || key === Clutter.KEY_Down) {
                this._adjustCustomMinutes(key === Clutter.KEY_Up
                    ? CUSTOM_STEP_MINUTES
                    : -CUSTOM_STEP_MINUTES);
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
        this._customRow.add_child(this._customEntry);
        this._customRow.add_child(new St.Label({
            text: 'minutes (↑/↓: ±15 minutes)',
            y_align: Clutter.ActorAlign.CENTER,
        }));
        this.actor.add_child(this._customRow);
        this._select(this._selected);
    }

    _handleChoiceKeyPress(index, event) {
        const key = event.get_key_symbol();
        if (key === Clutter.KEY_Return || key === Clutter.KEY_KP_Enter) {
            this.request();
            return Clutter.EVENT_STOP;
        }

        if (key !== Clutter.KEY_Up && key !== Clutter.KEY_Down)
            return Clutter.EVENT_PROPAGATE;

        const nextIndex = Math.clamp(index + (key === Clutter.KEY_Up ? -1 : 1),
            0, this._choiceButtons.length - 1);
        const [button, seconds] = this._choiceButtons[nextIndex];
        this._select(seconds);
        if (seconds !== null)
            button.grab_key_focus();
        return Clutter.EVENT_STOP;
    }

    focusSelectedChoice() {
        const selected = this._choiceButtons.find(([, seconds]) =>
            seconds === this._selected);
        selected?.[0].grab_key_focus();
    }

    addPopupActions() {
        const actions = new St.BoxLayout({
            style_class: 'request-more-time-popup-actions',
            x_expand: true,
        });
        const cancelButton = new St.Button({
            style_class: 'button request-more-time-popup-button',
            label: 'Cancel',
            can_focus: true,
            x_expand: true,
            x_align: Clutter.ActorAlign.FILL,
        });
        cancelButton.connect('clicked', () => this._onClose?.());
        actions.add_child(cancelButton);

        const requestButton = new St.Button({
            style_class: 'button request-more-time-popup-button suggested-action',
            label: 'Request',
            can_focus: true,
            x_expand: true,
            x_align: Clutter.ActorAlign.FILL,
        });
        requestButton.connect('clicked', () => this.request());
        actions.add_child(requestButton);
        this.actor.add_child(actions);
    }

    _select(seconds) {
        this._selected = seconds;
        for (const [button, value] of this._choiceButtons)
            button.set_checked(value === seconds);
        this._errorLabel?.hide();
        this._customRow.visible = seconds === null;
        if (seconds === null)
            this._customEntry.grab_key_focus();
    }

    _adjustCustomMinutes(change) {
        const current = Number.parseInt(this._customEntry.get_text(), 10);
        const minutes = Math.max(1,
            (Number.isSafeInteger(current) ? current : 0) + change);
        this._customEntry.set_text(String(minutes));
    }

    async request() {
        if (!this._onRequest || this._working)
            return;

        let seconds = this._selected;
        if (seconds === null) {
            const text = this._customEntry.get_text().trim();
            const minutes = Number(text);
            if (!/^\d+$/.test(text) || !Number.isSafeInteger(minutes) ||
                minutes <= 0 || !Number.isSafeInteger(minutes * 60)) {
                this._showError('Enter a positive whole number of minutes.');
                return;
            }
            seconds = minutes * 60;
        }

        this._errorLabel?.hide();
        this._setWorking(true);
        try {
            const granted = await this._onRequest(seconds);
            if (granted) {
                this._onClose?.();
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

    _showError(message = 'Your request could not be approved.') {
        if (!this._errorLabel) {
            this._errorLabel = new St.Label({
                style_class: 'request-more-time-error',
                text: message,
            });
            this.actor.add_child(this._errorLabel);
        }
        this._errorLabel.text = message;
        this._errorLabel.show();
    }

    _setWorking(working) {
        this._working = working;
        for (const [button] of this._choiceButtons)
            button.reactive = !working;
        this._customEntry.reactive = !working;
    }

    destroy() {
        this._onRequest = null;
        this._onClose = null;
    }
}

export const RequestDialog = GObject.registerClass(
class RequestDialog extends ModalDialog.ModalDialog {
    _init(onRequest) {
        super._init({styleClass: 'request-more-time-dialog'});
        this._form = new RequestForm(onRequest, () => this.close());
        this.contentLayout.add_child(this._form.actor);
        this.setButtons([
            {label: 'Cancel', action: () => this.close(), key: Clutter.KEY_Escape},
            {
                label: 'Request',
                default: true,
                action: () => this._form.request(),
                key: Clutter.KEY_Return,
            },
        ]);
    }

    destroy() {
        this._form?.destroy();
        this._form = null;
        super.destroy();
    }
});

export class RequestPopover extends PopupMenu.PopupMenu {
    constructor(onRequest, sourceActor) {
        super(sourceActor, 0.5, St.Side.TOP);

        const item = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false,
            style_class: 'request-more-time-popup-item',
        });
        this._form = new RequestForm(onRequest, () =>
            this.close(BoxPointer.PopupAnimation.FULL));
        this._form.addPopupActions();
        item.add_child(this._form.actor);
        this.addMenuItem(item);

        Main.uiGroup.add_child(this.actor);
        Main.panel.menuManager.addMenu(this);
        this.connect('menu-closed', () => this.destroy());
    }

    open() {
        super.open(BoxPointer.PopupAnimation.FULL);
        this._form.focusSelectedChoice();
        return this.isOpen;
    }

    destroy() {
        this._form?.destroy();
        this._form = null;
        super.destroy();
    }
}
