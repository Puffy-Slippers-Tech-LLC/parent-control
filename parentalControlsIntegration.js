import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {TimeLimitsState} from 'resource:///org/gnome/shell/misc/timeLimitsManager.js';

const LOG_PREFIX = '[request-more-time]';

// This is the only module which knows GNOME Shell's private unlock-dialog
// hierarchy. It intentionally targets GNOME Shell 50.
export class ParentalControlsIntegration {
    constructor(onRequest) {
        this._onRequest = onRequest;
        this._button = null;
        this._shield = null;
        this._signals = [];
        this._watchedDialog = null;
        this._dialogSignalId = 0;
        this._syncSourceId = 0;
    }

    enable() {
        this._connect(Main.timeLimitsManager, 'notify::state', () => this._sync());
        this._connect(Main.sessionMode, 'updated', () => this._sync());
        this._connect(Main.screenShield, 'active-changed', () => this._sync());
        this._sync();
    }

    isExhausted() {
        const shield = this._findShield();
        return Main.sessionMode.currentMode === 'unlock-dialog' &&
            Main.timeLimitsManager.state === TimeLimitsState.LIMIT_REACHED &&
            shield !== null && shield.get_parent() !== null;
    }

    destroy() {
        for (const [object, id] of this._signals) {
            if (id && object.signal_handler_is_connected(id))
                object.disconnect(id);
        }
        this._signals = [];
        this._unwatchDialog();
        if (this._syncSourceId) {
            GLib.source_remove(this._syncSourceId);
            this._syncSourceId = 0;
        }
        this._removeButton();
        this._onRequest = null;
    }

    _connect(object, signal, callback) {
        this._signals.push([object, object.connect(signal, callback)]);
    }

    _findShield() {
        const authPrompt = Main.screenShield?._dialog?._authPrompt;
        const shield = authPrompt?._parentalControlsShield;
        if (shield?.get_style_class_name() === 'parental-controls-shield')
            return shield;
        return null;
    }

    _sync() {
        this._watchDialog();
        const shield = this._findShield();
        const shouldShow = this.isExhausted() && shield !== null;

        if (!shouldShow) {
            this._removeButton();
            return;
        }

        if (this._button && this._shield === shield)
            return;

        this._removeButton();
        this._shield = shield;
        this._button = new St.Button({
            style_class: 'parental-controls-shield-button request-more-time-button',
            label: 'Request More Time',
            can_focus: true,
            reactive: true,
            x_align: Clutter.ActorAlign.CENTER,
        });
        this._button.connect('clicked', () => this._onRequest?.());
        this._button.connect('destroy', () => {
            this._button = null;
            this._shield = null;
        });
        shield.add_child(this._button);
        console.log(`${LOG_PREFIX} showing request button`);
    }

    _watchDialog() {
        const dialog = Main.screenShield?._dialog ?? null;
        if (dialog === this._watchedDialog)
            return;

        this._unwatchDialog();
        if (!dialog?._promptBox)
            return;

        this._watchedDialog = dialog;
        this._dialogSignalId = dialog._promptBox.connect('child-added', () => {
            // AuthPrompt adds itself before setAuthBlocked() creates and inserts
            // the shield. Resync after that synchronous setup has completed.
            if (this._syncSourceId)
                return;
            this._syncSourceId = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                this._syncSourceId = 0;
                this._sync();
                return GLib.SOURCE_REMOVE;
            });
        });
    }

    _unwatchDialog() {
        if (this._dialogSignalId &&
            this._watchedDialog?._promptBox?.signal_handler_is_connected(this._dialogSignalId))
            this._watchedDialog._promptBox.disconnect(this._dialogSignalId);
        this._dialogSignalId = 0;
        this._watchedDialog = null;
    }

    _removeButton() {
        if (this._button)
            this._button.destroy();
        this._button = null;
        this._shield = null;
    }
}
