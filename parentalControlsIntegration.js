import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {TimeLimitsState} from 'resource:///org/gnome/shell/misc/timeLimitsManager.js';

import {runExclusiveTimerUpdate} from './timerQuery.js';

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
        this._relockSourceId = 0;
    }

    enable() {
        this._connect(Main.timeLimitsManager, 'notify::state', () => this._sync());
        this._connect(Main.sessionMode, 'updated', () => this._sync());
        this._connect(Main.screenShield, 'active-changed', () => {
            this._sync();
            if (!Main.screenShield.active)
                this._scheduleRelockCheck();
        });
        this._sync();
    }

    isExhausted() {
        const shield = this._findShield();
        return Main.sessionMode.currentMode === 'unlock-dialog' &&
            Main.timeLimitsManager.state === TimeLimitsState.LIMIT_REACHED &&
            shield !== null && shield.get_parent() !== null;
    }

    async refreshState() {
        // Malcontent 0.14 can omit EstimatedTimesChanged after granting an
        // extension.  Refresh GNOME Shell's cached estimates explicitly so
        // UnlockDialog replaces the shield with the password prompt without
        // requiring a user switch to provoke another state calculation.
        await runExclusiveTimerUpdate(() => Main.timeLimitsManager._updateEstimatedTimes());
        this._sync();
    }

    destroy() {
        for (const [object, id] of this._signals) {
            if (!id)
                continue;
            try {
                object.disconnect(id);
            } catch (error) {
                console.debug(`${LOG_PREFIX} signal already disconnected: ${error.message}`);
            }
        }
        this._signals = [];
        this._unwatchDialog();
        if (this._syncSourceId) {
            GLib.source_remove(this._syncSourceId);
            this._syncSourceId = 0;
        }
        if (this._relockSourceId) {
            GLib.source_remove(this._relockSourceId);
            this._relockSourceId = 0;
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
        this._relockIfLimitWasBypassed();
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
            label: 'Request Time',
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
        if (this._dialogSignalId) {
            try {
                this._watchedDialog?._promptBox?.disconnect(this._dialogSignalId);
            } catch (error) {
                console.debug(`${LOG_PREFIX} prompt already disconnected: ${error.message}`);
            }
        }
        this._dialogSignalId = 0;
        this._watchedDialog = null;
    }

    _relockIfLimitWasBypassed() {
        const screenShield = Main.screenShield;
        if (Main.timeLimitsManager.state !== TimeLimitsState.LIMIT_REACHED ||
            !screenShield || screenShield.locked)
            return;

        // GDM can unlock an existing session without recreating this session's
        // UnlockDialog. The time-limit state remains LIMIT_REACHED, so GNOME's
        // state-transition dispatcher does not request another lock. Re-lock
        // when this Shell next observes the now-unlocked session.
        screenShield.lock(false);
        console.log(`${LOG_PREFIX} re-locked session after exhausted-limit bypass`);
    }

    _scheduleRelockCheck() {
        if (this._relockSourceId)
            return;

        // ScreenShield emits active-changed before its unlock animation has
        // finished clearing `locked`. Recheck once that transition completes.
        this._relockSourceId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
            this._relockSourceId = 0;
            this._relockIfLimitWasBypassed();
            return GLib.SOURCE_REMOVE;
        });
    }

    _removeButton() {
        if (this._button)
            this._button.destroy();
        this._button = null;
        this._shield = null;
    }
}
