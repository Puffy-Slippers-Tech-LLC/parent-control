import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

import {queryEstimatedTimes} from './timerQuery.js';
import {calculateOwnRemainingTime} from './timeCalculationClient.js';
import {prepareOwnSession} from './sessionPreparationClient.js';
import {logDebug, logInfo, logWarning} from './logger.js';
import {
    displayState,
    effectiveAllowanceRemaining,
    formatRemainingTime,
    nextEstimateState,
    remainingSeconds,
    shouldPrepareSession,
} from './indicatorLogic.mjs';
const ROLE = 'screenTimeRemaining';
const TIMER_BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const TIMER_OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const TIMER_INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';
const SCREEN_SAVER_NAME = 'org.gnome.ScreenSaver';
const SCREEN_SAVER_PATH = '/org/gnome/ScreenSaver';
const SCREEN_SAVER_INTERFACE = 'org.gnome.ScreenSaver';

export const RemainingTimeIndicator = GObject.registerClass(
class RemainingTimeIndicator extends PanelMenu.Button {
    _init(onRequest, approvedGrantRemaining = 0, preview = false,
        appName = 'Parent Control') {
        super._init(0.0, 'Screen Time Remaining');
        // Drop the default panel menu. A second menu with this source actor
        // steals hover and press from the request popover, including the
        // header overflow control.
        this.setMenu(null);

        this._onRequest = onRequest;
        this._preview = preview;

        const content = new St.BoxLayout({
            style_class: 'screen-time-remaining-content',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._label = new St.Label({
            style_class: 'screen-time-remaining-label',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._requestIcon = new St.Widget({
            style_class: 'screen-time-request-icon',
            layout_manager: new Clutter.BinLayout(),
        });
        this._requestIcon.set_pivot_point(0.5, 0.5);
        this._requestIconSpinning = false;
        this._requestIcon.add_child(new St.Icon({
            icon_name: 'hourglass-symbolic',
            style_class: 'screen-time-request-hourglass',
        }));
        this._requestIcon.add_child(new St.Label({
            text: '+',
            style_class: 'screen-time-request-plus',
            x_align: Clutter.ActorAlign.END,
            y_align: Clutter.ActorAlign.START,
        }));

        this._buttonContent = new St.BoxLayout({
            style_class: 'screen-time-request-button-content',
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._buttonContent.add_child(this._label);
        this._buttonContent.add_child(this._requestIcon);
        this._requestButton = new St.Button({
            style_class: 'screen-time-request-button',
            child: this._buttonContent,
            can_focus: true,
            reactive: true,
            track_hover: true,
            accessible_name: appName,
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._requestButton.connect('clicked', () => {
            this.setRequestActive(true);
            this._onRequest?.(this);
        });
        content.add_child(this._requestButton);
        this.add_child(content);
        this.reactive = false;
        this.can_focus = false;
        this.track_hover = false;

        this._signals = [];
        this._timeoutId = 0;
        this._layoutSyncId = 0;
        this._flashTimeoutId = 0;
        this._destroyed = false;
        this._activeExtensionEnd = approvedGrantRemaining > 0
            ? Main.timeLimitsManager.getCurrentTime() + approvedGrantRemaining
            : 0;
        this._calculatedEnd = this._activeExtensionEnd;
        this._statusLoaded = false;
        this._lockPending = false;
        this._refreshPending = false;
        this._refreshAgain = false;
        this._sessionPreparePending = false;
        this._sessionPrepared = false;
        this._vertical = null;
        this._timerSignalId = this._preview ? 0 : Gio.DBus.system.signal_subscribe(
            TIMER_BUS_NAME, TIMER_INTERFACE, 'EstimatedTimesChanged',
            TIMER_OBJECT_PATH, null, Gio.DBusSignalFlags.NONE,
            () => this._refreshEstimate());

        // Register the indicator while the panel is being initialized.  The
        // time-limits manager obtains its estimate asynchronously at login, so
        // waiting for a positive remaining time before adding the actor can
        // leave it outside the initialized panel layout.
        Main.panel.addToStatusArea(ROLE, this, 1, 'center');
        this.container.hide();

        this._connect(Main.timeLimitsManager, 'notify::state', () => this._sync());
        this._connect(Main.timeLimitsManager, 'notify::daily-limit-time',
            () => this._refreshEstimate());
        this._connect(Main.timeLimitsManager, 'notify::daily-limit-enabled',
            () => this._refreshEstimate());
        this._connect(Main.sessionMode, 'updated', () => this._sync());
        this._connect(this.container, 'notify::width', () => this._queueLayoutSync());
        this._connect(this.container, 'notify::height', () => this._queueLayoutSync());
        // Panel extensions may rewrite nested BoxLayout orientations while
        // rebuilding. Reconcile our layout without inspecting their private
        // actor data.
        this._connect(this._buttonContent, 'notify::vertical',
            () => this._queueLayoutSync());

        this._sync();
        this._queueLayoutSync();
        if (!this._preview)
            this._refreshEstimate();
    }

    setRequestActive(active) {
        this._requestButton?.set_checked(active);
    }

    _connect(object, signal, callback) {
        this._signals.push([object, object.connect(signal, callback)]);
    }

    destroy() {
        this._destroyed = true;
        this._onRequest = null;

        for (const [object, id] of this._signals) {
            if (!id)
                continue;
            try {
                object.disconnect(id);
            } catch (error) {
                logDebug(`signal already disconnected: ${error.message}`);
            }
        }
        this._signals = [];

        this._clearTimeout();
        if (this._layoutSyncId) {
            GLib.source_remove(this._layoutSyncId);
            this._layoutSyncId = 0;
        }
        this._clearFlash();

        if (this._timerSignalId)
            Gio.DBus.system.signal_unsubscribe(this._timerSignalId);
        this._timerSignalId = 0;

        super.destroy();
    }

    _clearTimeout() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
    }

    _queueLayoutSync() {
        if (this._destroyed || this._layoutSyncId)
            return;

        this._layoutSyncId = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._layoutSyncId = 0;
            if (!this._destroyed)
                this._sync();
            return GLib.SOURCE_REMOVE;
        });
    }

    _clearFlash() {
        if (this._flashTimeoutId) {
            GLib.source_remove(this._flashTimeoutId);
            this._flashTimeoutId = 0;
        }
        this._buttonContent?.remove_style_pseudo_class('flash');
    }

    _clearCountdownWarning() {
        this._clearFlash();
        this._label?.remove_style_pseudo_class('countdown');
        this._stopRequestIconSpin();
    }

    _stopRequestIconSpin() {
        this._requestIcon?.remove_all_transitions();
        if (this._requestIcon) {
            this._requestIcon.rotation_angle_z = 0;
            this._requestIconSpinning = false;
        }
    }

    _remainingSeconds(currentTime) {
        return remainingSeconds(this._calculatedEnd, currentTime);
    }

    refreshEstimate() {
        if (this._preview || this._destroyed)
            return;
        this._refreshEstimate();
    }

    async _refreshEstimate() {
        if (this._destroyed)
            return;
        if (this._refreshPending) {
            this._refreshAgain = true;
            return;
        }

        this._refreshPending = true;
        try {
            const estimates = await queryEstimatedTimes();
            if (this._destroyed)
                return;

            const estimate = estimates[''];
            const currentTime = Main.timeLimitsManager.getCurrentTime();
            const managerLimit = Number(
                Main.timeLimitsManager.dailyLimitTime ?? 0);
            const effectiveAllowance = effectiveAllowanceRemaining(
                estimate, currentTime, managerLimit);
            const calculated = await calculateOwnRemainingTime(
                effectiveAllowance);
            if (this._destroyed)
                return;
            const next = nextEstimateState(
                {calculatedEnd: this._calculatedEnd, statusLoaded: this._statusLoaded},
                calculated, currentTime);
            this._calculatedEnd = next.calculatedEnd;
            this._statusLoaded = next.statusLoaded;
            logInfo('timer estimate loaded; ' +
                `calculated remaining=${calculated}`);
        } catch (error) {
            if (!this._destroyed) {
                // A transient daemon/database failure says nothing about the
                // last successful estimate. Preserve it until a supported
                // D-Bus query supplies a replacement.
                logWarning('timer query failed; keeping previous estimate: ' +
                    error.message);
            }
        } finally {
            this._refreshPending = false;
            if (!this._destroyed) {
                this._sync();
                if (this._refreshAgain) {
                    this._refreshAgain = false;
                    this._refreshEstimate();
                }
            }
        }
    }

    async _prepareSession() {
        if (!shouldPrepareSession({
            preview: this._preview,
            destroyed: this._destroyed,
            pending: this._sessionPreparePending,
            prepared: this._sessionPrepared,
            locked: Main.sessionMode.isLocked,
            greeter: Main.sessionMode.isGreeter,
        }))
            return;

        this._sessionPreparePending = true;
        try {
            const reconciled = await prepareOwnSession();
            if (this._destroyed)
                return;
            this._sessionPrepared = true;
            logInfo(reconciled
                ? 'restored expired-grant application policy for session entry'
                : 'session entry application policy already current');
        } catch (error) {
            if (!this._destroyed)
                logWarning(`could not prepare application policy for session entry: ${error.message}`);
        } finally {
            this._sessionPreparePending = false;
        }
    }

    showGrantedTime(durationSeconds) {
        const now = Main.timeLimitsManager.getCurrentTime();
        if (durationSeconds > 0) {
            this._activeExtensionEnd = now + durationSeconds;
        } else {
            const tomorrow = GLib.DateTime.new_from_unix_local(now)
                .add_days(1);
            this._activeExtensionEnd = GLib.DateTime.new_local(
                tomorrow.get_year(), tomorrow.get_month(), tomorrow.get_day_of_month(),
                0, 0, 0).to_unix();
        }
        // The grant duration was produced by the broker-owned shared formula.
        this._calculatedEnd = this._activeExtensionEnd;
        this._sync();
    }

    _sync() {
        if (this._destroyed)
            return;

        const manager = Main.timeLimitsManager;
        const currentTime = manager.getCurrentTime();
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            this._sessionPrepared = false;
        else
            this._prepareSession();
        if (this._activeExtensionEnd <= currentTime)
            this._activeExtensionEnd = 0;
        const state = displayState({
            calculatedEnd: this._calculatedEnd,
            currentTime,
            locked: Main.sessionMode.isLocked,
            greeter: Main.sessionMode.isGreeter,
        });
        const remainingSecs = state.remaining;
        // Ubuntu uses a primary session mode named "ubuntu", while upstream
        // GNOME commonly uses "user".  Test the session semantics instead of
        // assuming the distribution-specific primary mode name.
        const visible = state.visible;

        if (!visible || remainingSecs <= 0) {
            this._clearTimeout();
            this._stopRequestIconSpin();
            this._setShown(false);
            if (!this._preview && this._statusLoaded &&
                manager.dailyLimitEnabled && state.shouldLock)
                this._lockSession();
            return;
        }

        this._setShown(true);
        this._updateLabel(remainingSecs);
        this._schedule(state.nextUpdateSeconds);
    }

    _lockSession() {
        if (this._destroyed || this._lockPending)
            return;

        this._lockPending = true;
        Gio.DBus.session.call(
            SCREEN_SAVER_NAME, SCREEN_SAVER_PATH, SCREEN_SAVER_INTERFACE, 'Lock',
            null, null, Gio.DBusCallFlags.NONE, -1, null,
            (connection, result) => {
                try {
                    connection.call_finish(result);
                    logInfo('locked managed desktop because no time remains');
                } catch (error) {
                    if (!this._destroyed)
                        logWarning(`could not lock managed desktop: ${error.message}`);
                } finally {
                    this._lockPending = false;
                }
            });
    }

    _setShown(shown) {
        if (shown && !this.container.visible)
            logInfo('showing remaining time indicator');
        this.container.visible = shown;
    }

    _compactLabel() {
        const [width, height] = this.container.get_transformed_size();
        return height > width;
    }

    _syncOrientation() {
        const vertical = this._compactLabel();
        // Another panel extension can mutate the BoxLayout after our cached
        // orientation was set, so always compare against the actor too.
        if (this._buttonContent.vertical !== vertical)
            this._buttonContent.vertical = vertical;

        if (this._vertical !== vertical) {
            this._vertical = vertical;
            const method = vertical
                ? 'add_style_class_name'
                : 'remove_style_class_name';
            this._requestButton[method]('screen-time-request-button-vertical');
            this._buttonContent[method]('screen-time-request-button-content-vertical');
            this._label[method]('screen-time-remaining-label-vertical');
        }

        return vertical;
    }

    _updateLabel(remainingSecs) {
        if (remainingSecs >= 60)
            this._clearCountdownWarning();

        const compact = this._syncOrientation();
        this._label.text = formatRemainingTime(remainingSecs, compact);

        if (remainingSecs < 60) {
            this._label.add_style_pseudo_class('countdown');
            this._flashContent();
        }

        this._updateRequestIcon(remainingSecs);
        this._requestButton.accessible_name =
            `Request time, ${this._label.text}`;
    }

    _updateRequestIcon(remainingSecs) {
        if (remainingSecs > 10) {
            this._stopRequestIconSpin();
            return;
        }

        if (this._requestIconSpinning)
            return;

        this._requestIconSpinning = true;
        this._requestIcon.ease({
            rotation_angle_z: 360,
            duration: 1000,
            mode: Clutter.AnimationMode.LINEAR,
            repeatCount: -1,
            // This is an urgent countdown state, not decorative motion. Keep
            // the rotation running when ordinary Shell animations are off;
            // otherwise 360 degrees collapses to the unchanged end frame.
            animationRequired: true,
        });
    }

    _flashContent() {
        this._clearFlash();
        this._buttonContent.add_style_pseudo_class('flash');
        this._flashTimeoutId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT, 350, () => {
                this._flashTimeoutId = 0;
                this._buttonContent?.remove_style_pseudo_class('flash');
                return GLib.SOURCE_REMOVE;
            });
    }

    _schedule(delay) {
        this._clearTimeout();

        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, delay, () => {
            this._timeoutId = 0;
            if (!this._preview)
                this._refreshEstimate();
            this._sync();
            return GLib.SOURCE_REMOVE;
        });
    }
});
