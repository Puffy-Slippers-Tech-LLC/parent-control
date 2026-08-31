import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as BoxPointer from 'resource:///org/gnome/shell/ui/boxpointer.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {
    MAX_CUSTOM_MINUTES,
    MIN_CUSTOM_MINUTES,
    loadAllowSoftBlockedApps,
    loadLastCustomMinutes,
    loadLastSelectedDuration,
    saveAllowSoftBlockedApps,
    saveLastCustomMinutes,
    saveLastSelectedDuration,
} from './requestPreferencesStore.js';

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

const DEFAULT_DURATION_SECONDS = 30 * 60;

// A zero-duration RequestExtension asks the extension agent to choose a
// duration; it is not a guaranteed end-of-day grant. Send the actual interval
// to local midnight for this choice instead.
export function secondsUntilEndOfLocalDay(now = GLib.DateTime.new_now_local()) {
    const tomorrow = now.add_days(1);
    const startOfTomorrow = GLib.DateTime.new_local(
        tomorrow.get_year(), tomorrow.get_month(), tomorrow.get_day_of_month(),
        0, 0, 0);

    // This uses local time, including daylight-saving transitions, and the
    // timer service requires a positive duration.
    return Math.max(1, startOfTomorrow.to_unix() - now.to_unix());
}

// Both the login modal and panel popup use this form.
class RequestForm {
    constructor(onRequest, onClose, onPreferences) {
        this._onRequest = onRequest;
        this._onClose = onClose;
        this._onPreferences = onPreferences;
        this._destroyed = false;
        this._working = false;
        this._selected = this._loadSelectedDuration();
        this._choiceButtons = [];
        this._lastCustomMinutes = loadLastCustomMinutes();
        this._appFilterToggle = null;

        this.actor = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'oh-no-parent-control-content',
        });

        const header = new St.BoxLayout({
            style_class: 'oh-no-parent-control-header',
            x_expand: true,
        });
        header.add_child(new St.Icon({
            style_class: 'oh-no-parent-control-header-icon',
            icon_name: 'alarm-symbolic',
            y_align: Clutter.ActorAlign.CENTER,
        }));
        const headerCopy = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'oh-no-parent-control-header-copy',
            y_align: Clutter.ActorAlign.CENTER,
        });
        headerCopy.add_child(new St.Label({
            style_class: 'oh-no-parent-control-title',
            text: 'Oh No! Parent Control',
        }));
        headerCopy.add_child(new St.Label({
            style_class: 'oh-no-parent-control-subtitle',
            text: 'Choose how much extra time you need',
        }));
        header.add_child(headerCopy);
        this.actor.add_child(header);

        const choices = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'oh-no-parent-control-choices',
        });
        for (const [index, duration] of DURATIONS.entries()) {
            const button = new St.Button({
                style_class: 'oh-no-parent-control-choice',
                can_focus: true,
                reactive: true,
                track_hover: true,
                toggle_mode: true,
                x_expand: true,
                x_align: Clutter.ActorAlign.FILL,
                label: duration.label,
            });
            button.connect('clicked', () => {
                this._select(duration.seconds);
                if (duration.seconds === null)
                    global.stage.set_key_focus(this._customEntry.clutter_text);
                else
                    button.grab_key_focus();
            });
            button.connect('key-press-event', (_actor, event) =>
                this._handleChoiceKeyPress(index, event));
            choices.add_child(button);
            this._choiceButtons.push([button, duration.seconds]);
        }
        this.actor.add_child(choices);

        this._customRow = new St.BoxLayout({
            style_class: 'oh-no-parent-control-custom-row',
            x_align: Clutter.ActorAlign.CENTER,
        });
        this._customEntry = new St.Entry({
            style_class: 'oh-no-parent-control-custom-entry',
            can_focus: true,
            reactive: true,
            text: String(this._lastCustomMinutes),
        });
        this._customEntry.clutter_text.set_editable(true);
        this._customEntry.clutter_text.set_selectable(true);
        this._customEntry.clutter_text.set_input_purpose(
            Clutter.InputContentPurpose.DIGITS);
        this._customEntry.clutter_text.set_max_length(
            String(MAX_CUSTOM_MINUTES).length);
        this._customEntry.clutter_text.connect('key-press-event', (_actor, event) => {
            const key = event.get_key_symbol();
            if (key === Clutter.KEY_Return || key === Clutter.KEY_KP_Enter) {
                this.request();
                return Clutter.EVENT_STOP;
            }
            if (key === Clutter.KEY_Up || key === Clutter.KEY_Down) {
                this._selectAdjacentChoice(DURATIONS.length - 1,
                    key === Clutter.KEY_Up ? -1 : 1);
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
        this._customEntry.clutter_text.connect('key-focus-in', () =>
            this._customEntry.clutter_text.set_selection(0, -1));
        this._customRow.add_child(this._customEntry);
        this._customRow.add_child(new St.Label({
            style_class: 'oh-no-parent-control-custom-hint',
            text: 'minutes',
            y_align: Clutter.ActorAlign.CENTER,
        }));
        this.actor.add_child(this._customRow);

        const appFilterControls = new St.BoxLayout({
            style_class: 'oh-no-parent-control-app-filter-controls',
            x_expand: true,
        });
        const appFilterToggleContent = new St.BoxLayout({
            style_class: 'oh-no-parent-control-app-filter-toggle-content',
            x_expand: true,
        });
        appFilterToggleContent.add_child(new St.Label({
            style_class: 'oh-no-parent-control-app-filter-label',
            text: 'Allow soft blocked apps',
            x_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
        }));
        const switchTrack = new St.BoxLayout({
            style_class: 'oh-no-parent-control-switch-track',
            y_align: Clutter.ActorAlign.CENTER,
        });
        switchTrack.add_child(new St.Widget({
            style_class: 'oh-no-parent-control-switch-handle',
        }));
        appFilterToggleContent.add_child(switchTrack);

        this._appFilterToggle = new St.Button({
            style_class: 'oh-no-parent-control-app-filter-toggle',
            child: appFilterToggleContent,
            can_focus: true,
            reactive: true,
            toggle_mode: true,
            x_expand: true,
            x_align: Clutter.ActorAlign.FILL,
        });
        this._appFilterToggle.accessible_name =
            'Allow soft blocked apps';
        this._appFilterToggle.set_checked(loadAllowSoftBlockedApps());
        this._appFilterToggle.connect('notify::checked', toggle =>
            saveAllowSoftBlockedApps(toggle.checked));
        appFilterControls.add_child(this._appFilterToggle);

        this._preferencesButton = new St.Button({
            style_class: 'oh-no-parent-control-preferences-button',
            child: new St.Icon({
                style_class: 'oh-no-parent-control-preferences-icon',
                icon_name: 'emblem-system-symbolic',
            }),
            can_focus: true,
            reactive: true,
            track_hover: true,
            y_align: Clutter.ActorAlign.FILL,
        });
        this._preferencesButton.accessible_name = 'Open app access preferences';
        this._preferencesButton.connect('clicked', () => {
            try {
                this._onPreferences?.();
            } catch (error) {
                console.error(`[oh-no-parent-control] could not open preferences: ${error.message}`);
            }
        });
        appFilterControls.add_child(this._preferencesButton);
        this.actor.add_child(appFilterControls);
        this._select(this._selected);
    }

    _loadSelectedDuration() {
        const savedDuration = loadLastSelectedDuration();
        if (savedDuration === null)
            return DEFAULT_DURATION_SECONDS;
        const seconds = savedDuration === 'custom' ? null : Number(savedDuration);
        return DURATIONS.some(duration => duration.seconds === seconds)
            ? seconds
            : DEFAULT_DURATION_SECONDS;
    }

    _handleChoiceKeyPress(index, event) {
        const key = event.get_key_symbol();
        if (key === Clutter.KEY_Return || key === Clutter.KEY_KP_Enter) {
            this.request();
            return Clutter.EVENT_STOP;
        }

        if (key !== Clutter.KEY_Up && key !== Clutter.KEY_Down)
            return Clutter.EVENT_PROPAGATE;

        this._selectAdjacentChoice(index, key === Clutter.KEY_Up ? -1 : 1);
        return Clutter.EVENT_STOP;
    }

    _selectAdjacentChoice(index, direction) {
        const nextIndex = (index + direction + this._choiceButtons.length) %
            this._choiceButtons.length;
        const [button, seconds] = this._choiceButtons[nextIndex];
        this._select(seconds);
        if (seconds !== null)
            button.grab_key_focus();
    }

    focusSelectedChoice() {
        const selected = this.getSelectedChoice();
        selected?.[0].grab_key_focus();
    }

    setPreferencesVisible(visible) {
        this._preferencesButton.visible = visible;
    }

    getSelectedChoice() {
        return this._choiceButtons.find(([, seconds]) =>
            seconds === this._selected);
    }

    addPopupActions() {
        const actions = new St.BoxLayout({
            style_class: 'oh-no-parent-control-popup-actions',
            x_expand: true,
        });
        const cancelButton = new St.Button({
            style_class: 'button oh-no-parent-control-popup-button',
            label: 'Cancel',
            can_focus: true,
            x_expand: true,
            x_align: Clutter.ActorAlign.FILL,
        });
        cancelButton.connect('clicked', () => this._onClose?.());
        actions.add_child(cancelButton);

        const requestButton = new St.Button({
            style_class: 'button oh-no-parent-control-popup-button suggested-action',
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
            global.stage.set_key_focus(this._customEntry.clutter_text);
    }

    async request() {
        if (!this._onRequest || this._working)
            return;

        let seconds = this._selected;
        if (seconds === null) {
            const text = this._customEntry.get_text().trim();
            const minutes = Number(text);
            if (!/^\d+$/.test(text) || !Number.isSafeInteger(minutes) ||
                minutes < MIN_CUSTOM_MINUTES || minutes > MAX_CUSTOM_MINUTES) {
                this._showError(
                    `Enter a whole number from ${MIN_CUSTOM_MINUTES} to ${MAX_CUSTOM_MINUTES} minutes.`);
                return;
            }
            this._lastCustomMinutes = minutes;
            seconds = minutes * 60;
        }

        if (seconds === 0)
            seconds = secondsUntilEndOfLocalDay();

        this._errorLabel?.hide();
        this._setWorking(true);
        try {
            const granted = await this._onRequest(
                seconds,
                this._appFilterToggle.checked);
            if (granted) {
                saveLastSelectedDuration(this._selected);
                if (this._selected === null)
                    saveLastCustomMinutes(this._lastCustomMinutes);
                this._onClose?.();
                return;
            }
            this._showError();
        } catch (error) {
            console.error(`[oh-no-parent-control] ${error.message}`);
            this._showError();
        } finally {
            this._setWorking(false);
        }
    }

    _showError(message = 'Your request could not be approved.') {
        if (this._destroyed)
            return;

        if (!this._errorLabel) {
            this._errorLabel = new St.Label({
                style_class: 'oh-no-parent-control-error',
                text: message,
            });
            this.actor.add_child(this._errorLabel);
        }
        this._errorLabel.text = message;
        this._errorLabel.show();
    }

    _setWorking(working) {
        if (this._destroyed)
            return;

        this._working = working;
        for (const [button] of this._choiceButtons)
            button.reactive = !working;
        this._customEntry.reactive = !working;
        this._appFilterToggle.reactive = !working;
        this._preferencesButton.reactive = !working;
    }

    destroy() {
        this._destroyed = true;
        this._onRequest = null;
        this._onClose = null;
        this._onPreferences = null;
        this._appFilterToggle = null;
        this._preferencesButton = null;
    }
}

export const RequestDialog = GObject.registerClass(
class RequestDialog extends ModalDialog.ModalDialog {
    _init(onRequest, onPreferences) {
        super._init({styleClass: 'oh-no-parent-control-dialog'});
        Main.sessionMode.connectObject('updated', () => this._syncParent(), this);
        this._syncParent();
        this._form = new RequestForm(
            onRequest, () => this.close(), onPreferences);
        this._form.setPreferencesVisible(!Main.sessionMode.isLocked);
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
        this.setInitialKeyFocus(this._form.getSelectedChoice()?.[0]);
    }

    _syncParent() {
        const lockDialogGroup = Main.screenShield?._lockDialogGroup;
        const wantedParent = Main.sessionMode.isLocked && lockDialogGroup
            ? lockDialogGroup
            : Main.layoutManager.modalDialogGroup;
        this._form?.setPreferencesVisible(!Main.sessionMode.isLocked);
        const currentParent = this.get_parent();
        if (!wantedParent || currentParent === wantedParent)
            return;

        currentParent?.remove_child(this);
        wantedParent.add_child(this);
    }

    destroy() {
        Main.sessionMode.disconnectObject(this);
        this._form?.destroy();
        this._form = null;
        super.destroy();
    }
});

export class RequestPopover extends PopupMenu.PopupMenu {
    constructor(onRequest, sourceActor, onPreferences) {
        super(sourceActor, 0.5, St.Side.TOP);

        const item = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false,
            style_class: 'oh-no-parent-control-popup-item',
        });
        this._form = new RequestForm(
            onRequest,
            () => this.close(BoxPointer.PopupAnimation.FULL),
            onPreferences);
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
