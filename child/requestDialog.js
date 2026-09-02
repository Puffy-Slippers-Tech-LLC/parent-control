import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as BoxPointer from 'resource:///org/gnome/shell/ui/boxpointer.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {
    loadAllowSoftBlockedApps,
    loadLastCustomMinutes,
    loadLastSelectedDuration,
    saveRequestPreferences,
} from './requestPreferencesStore.js';
import {
    DEFAULT_DURATION_SECONDS,
    DURATIONS,
    MAX_CUSTOM_MINUTES,
    MIN_CUSTOM_MINUTES,
} from './requestOptions.js';
import {logError} from './logger.js';

export {DURATIONS} from './requestOptions.js';

function extensionAsset(name) {
    const [modulePath] = GLib.filename_from_uri(import.meta.url);
    const extensionDir = GLib.path_get_dirname(modulePath);
    const bundled = GLib.build_filenamev([extensionDir, name]);
    // The installed extension and packed archive include the branding asset
    // beside this module. The development preview instead runs the checkout
    // directly, where shared branding remains in data/.
    const path = GLib.file_test(bundled, GLib.FileTest.EXISTS) ? bundled
        : GLib.build_filenamev([extensionDir, '..', 'data', name]);
    return new Gio.FileIcon({file: Gio.File.new_for_path(path)});
}

// Zero is only the UI sentinel for this choice. The ActiveExtension backend
// write requires a positive duration, so calculate the interval explicitly.
export function secondsUntilEndOfLocalDay(now = GLib.DateTime.new_now_local()) {
    const tomorrow = now.add_days(1);
    const startOfTomorrow = GLib.DateTime.new_local(
        tomorrow.get_year(), tomorrow.get_month(), tomorrow.get_day_of_month(),
        0, 0, 0);

    // This uses local time, including daylight-saving transitions, and the
    // timer service requires a positive duration.
    return Math.max(1, startOfTomorrow.to_unix() - now.to_unix());
}

// The in-session panel popup uses this form.
class RequestForm {
    constructor(onRequest, onClose, onMenu, onMenuToggle,
        appName = 'Parent Control') {
        this._onRequest = onRequest;
        this._onClose = onClose;
        this._onMenu = onMenu;
        this._onMenuToggle = onMenuToggle;
        this._destroyed = false;
        this._working = false;
        this._selected = this._loadSelectedDuration();
        this._choiceButtons = [];
        this._lastCustomMinutes = loadLastCustomMinutes();
        this._appFilterToggle = null;
        this._approvers = [];
        this._selectedApprover = null;
        this._approverButton = null;
        this._approverChoices = null;
        this._approverChoiceButtons = [];

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
            gicon: extensionAsset('app_logo.png'),
            y_align: Clutter.ActorAlign.CENTER,
        }));
        const headerCopy = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'oh-no-parent-control-header-copy',
            x_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
        });
        headerCopy.add_child(new St.Label({
            style_class: 'oh-no-parent-control-title',
            text: appName,
        }));
        headerCopy.add_child(new St.Label({
            style_class: 'oh-no-parent-control-subtitle',
            text: 'Choose how much extra time you need',
        }));
        header.add_child(headerCopy);
        this._menuButton = new St.Button({
            child: new St.Icon({icon_name: 'view-more-symbolic', icon_size: 16}),
            style_class: 'oh-no-parent-control-header-menu-button',
            can_focus: true,
            reactive: true,
            track_hover: true,
            accessible_name: 'Menu',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._menuButton.connect('clicked', () => this._onMenuToggle?.());
        header.add_child(this._menuButton);
        this.actor.add_child(header);

        this._overflowMenu = new St.BoxLayout({
            vertical: true,
            style_class: 'oh-no-parent-control-overflow-menu',
            x_align: Clutter.ActorAlign.END,
            visible: false,
        });
        for (const [label, action] of [['Help', 'help'], ['About', 'about']]) {
            const button = new St.Button({
                label,
                style_class: 'oh-no-parent-control-overflow-menu-item',
                can_focus: true,
                reactive: true,
                track_hover: true,
                x_align: Clutter.ActorAlign.FILL,
            });
            button.connect('clicked', () => {
                this._overflowMenu.hide();
                this._onMenu?.(action);
            });
            this._overflowMenu.add_child(button);
        }
        this.actor.add_child(this._overflowMenu);

        this._buildApproverSelector();

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
            Clutter.InputContentPurpose.NUMBER);
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
        this.actor.add_child(this._appFilterToggle);
        this._select(this._selected);
    }

    _buildApproverSelector() {
        const selector = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'oh-no-parent-control-approver-selector',
            x_expand: true,
        });
        const row = new St.BoxLayout({
            style_class: 'oh-no-parent-control-approver-row',
            x_expand: true,
        });
        row.add_child(new St.Label({
            style_class: 'oh-no-parent-control-approver-label',
            text: 'Approver',
            x_align: Clutter.ActorAlign.START,
            y_align: Clutter.ActorAlign.CENTER,
        }));
        const buttonContent = new St.BoxLayout({
            style_class: 'oh-no-parent-control-account-selector-content',
            x_expand: true,
        });
        this._approverLabel = new St.Label({
            text: 'Loading approving administrators…',
            x_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
        });
        buttonContent.add_child(this._approverLabel);
        buttonContent.add_child(new St.Icon({
            icon_name: 'pan-down-symbolic',
            style_class: 'oh-no-parent-control-account-selector-arrow',
            y_align: Clutter.ActorAlign.CENTER,
        }));
        this._approverButton = new St.Button({
            style_class: 'oh-no-parent-control-account-selector',
            child: buttonContent,
            can_focus: true,
            reactive: false,
            x_expand: true,
            x_align: Clutter.ActorAlign.FILL,
        });
        this._approverButton.connect('clicked', () =>
            this._approverChoices.visible = !this._approverChoices.visible);
        row.add_child(this._approverButton);
        selector.add_child(row);
        this._approverChoices = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'oh-no-parent-control-account-choices',
            x_expand: true,
            visible: false,
        });
        selector.add_child(this._approverChoices);
        this.actor.add_child(selector);
    }

    setApprovers(approvers) {
        if (!Array.isArray(approvers) || approvers.some(([uid, label]) =>
            !Number.isSafeInteger(uid) || uid < 0 || typeof label !== 'string' || !label))
            throw new Error('Invalid approving administrators');
        this._approvers = approvers;
        this._selectedApprover = approvers[0]?.[0] ?? null;
        this._approverChoiceButtons = [];
        while (this._approverChoices.get_first_child())
            this._approverChoices.get_first_child().destroy();
        for (const [uid, label] of approvers) {
            const choice = new St.Button({
                style_class: 'oh-no-parent-control-account-choice',
                label,
                can_focus: true,
                reactive: true,
                toggle_mode: true,
                x_expand: true,
                x_align: Clutter.ActorAlign.FILL,
            });
            choice.connect('clicked', () => this._selectApprover(uid));
            this._approverChoices.add_child(choice);
            this._approverChoiceButtons.push([uid, choice]);
        }
        this._approverButton.reactive = approvers.length > 0;
        if (approvers.length > 0)
            this._selectApprover(approvers[0][0]);
        else
            this._approverLabel.text = 'No approving administrators are available';
        this._approverChoices.visible = false;
    }

    _selectApprover(uid) {
        const approver = this._approvers.find(([candidate]) => candidate === uid);
        if (!approver)
            return;
        this._selectedApprover = uid;
        for (const [candidate, choice] of this._approverChoiceButtons)
            choice.set_checked(candidate === uid);
        this._approverLabel.text = approver[1];
        this._approverChoices.visible = false;
    }

    selectedApprover() {
        return this._approvers.find(([uid]) => uid === this._selectedApprover) ?? null;
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

    toggleOverflowMenu() {
        this._overflowMenu.visible = !this._overflowMenu.visible;
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
            if (!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(text) ||
                !Number.isFinite(minutes) ||
                minutes < MIN_CUSTOM_MINUTES || minutes > MAX_CUSTOM_MINUTES) {
                this._showError(
                    `Enter a number from ${MIN_CUSTOM_MINUTES} to ${MAX_CUSTOM_MINUTES} minutes.`);
                return;
            }
            this._lastCustomMinutes = minutes;
            // ActiveExtension stores whole seconds, so decimal-minute values
            // are rounded to the nearest representable duration.
            seconds = Math.round(minutes * 60);
        }

        const untilEndOfDay = seconds === 0;
        if (untilEndOfDay)
            seconds = secondsUntilEndOfLocalDay();

        const allowSoftBlockedApps = this._appFilterToggle.checked;
        const approver = this.selectedApprover();
        if (!approver) {
            this._showError('Choose an approving administrator.');
            return;
        }
        this._errorLabel?.hide();
        this._setWorking(true);
        try {
            const granted = await this._onRequest(
                seconds,
                allowSoftBlockedApps,
                untilEndOfDay,
                approver[0]);
            if (granted) {
                saveRequestPreferences(
                    this._selected, this._lastCustomMinutes,
                    allowSoftBlockedApps);
                this._onClose?.();
                return;
            }
            this._showError();
        } catch (error) {
            logError(error.message);
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
        this._approverButton.reactive = !working && this._approvers.length > 0;
    }

    destroy() {
        this._destroyed = true;
        this._onRequest = null;
        this._onClose = null;
        this._onMenu = null;
        this._onMenuToggle = null;
        this._menuButton = null;
        this._overflowMenu = null;
        this._appFilterToggle = null;
        this._approverButton = null;
        this._approverLabel = null;
        this._approverChoices = null;
        this._approvers = [];
        this._approverChoiceButtons = [];
    }
}

export class RequestPopover extends PopupMenu.PopupMenu {
    constructor(onRequest, sourceActor, onMenu, appName) {
        super(sourceActor, 0.5, St.Side.TOP);

        const item = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false,
            style_class: 'oh-no-parent-control-popup-item',
        });
        this._form = new RequestForm(
            onRequest,
            () => this.close(BoxPointer.PopupAnimation.FULL),
            onMenu,
            () => this._toggleOverflowMenu(),
            appName);
        this._form.addPopupActions();
        item.add_child(this._form.actor);
        this.addMenuItem(item);

        Main.uiGroup.add_child(this.actor);
        Main.panel.menuManager.addMenu(this);
        this.connect('menu-closed', () => {
            if (!this._keepOpen) {
                this.destroy();
                return;
            }
            this._keepOpen = false;
            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                if (this._form)
                    this.open();
                return GLib.SOURCE_REMOVE;
            });
        });
    }

    _toggleOverflowMenu() {
        // PopupMenu closes when a header button is clicked. Reopen after its
        // click handling completes so this in-dialog control is not mistaken
        // for a request-popover dismissal.
        this._keepOpen = true;
        this._form.toggleOverflowMenu();
    }

    open() {
        super.open(BoxPointer.PopupAnimation.FULL);
        this._form.focusSelectedChoice();
        return this.isOpen;
    }

    setApprovers(approvers) {
        this._form?.setApprovers(approvers);
    }

    destroy() {
        this._form?.destroy();
        this._form = null;
        super.destroy();
    }
}
