import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

import {queryEstimatedTimes} from './timerQuery.js';

const LOG_PREFIX = '[request-more-time]';
const ROLE = 'screenTimeRemaining';
const TIMER_BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const TIMER_OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const TIMER_INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';

export const RemainingTimeIndicator = GObject.registerClass(
class RemainingTimeIndicator extends PanelMenu.Button {
    _init(onRequest, approvedGrantRemaining = 0) {
        super._init(0.0, 'Screen Time Remaining', true);

        this._onRequest = onRequest;

        const content = new St.BoxLayout({
            style_class: 'screen-time-remaining-content',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._label = new St.Label({
            style_class: 'screen-time-remaining-label',
            y_align: Clutter.ActorAlign.CENTER,
        });
        content.add_child(this._label);

        this._urgencyVisual = new St.Widget({
            style_class: 'screen-time-urgency-visual',
            layout_manager: new Clutter.BinLayout(),
            visible: false,
        });
        this._bomb = new St.Label({
            // The bomb glyph supplies the rounded body and curved fuse; the
            // overlaid spark below remains animated as the countdown ticks.
            text: '💣',
            style_class: 'screen-time-bomb',
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._spark = new St.Label({
            text: '✦',
            style_class: 'screen-time-bomb-spark',
            x_align: Clutter.ActorAlign.END,
            y_align: Clutter.ActorAlign.START,
        });
        this._explosion = new St.Label({
            text: '✹',
            style_class: 'screen-time-explosion',
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.CENTER,
            visible: false,
        });
        this._urgencyVisual.add_child(this._bomb);
        this._urgencyVisual.add_child(this._spark);
        this._urgencyVisual.add_child(this._explosion);
        content.add_child(this._urgencyVisual);

        const iconBox = new St.Widget({
            style_class: 'screen-time-request-icon',
            layout_manager: new Clutter.BinLayout(),
        });
        iconBox.add_child(new St.Icon({
            icon_name: 'hourglass-symbolic',
            style_class: 'screen-time-request-hourglass',
        }));
        iconBox.add_child(new St.Label({
            text: '+',
            style_class: 'screen-time-request-plus',
            x_align: Clutter.ActorAlign.END,
            y_align: Clutter.ActorAlign.START,
        }));

        this._requestButton = new St.Button({
            style_class: 'screen-time-request-button',
            child: iconBox,
            can_focus: true,
            reactive: true,
            track_hover: true,
            accessible_name: 'Request more time',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._requestTooltip = new St.Label({
            style_class: 'dash-label',
            text: 'Request time',
            visible: false,
        });
        Main.uiGroup.add_child(this._requestTooltip);
        this._requestButton.connect('notify::hover', () => this._syncRequestTooltip());
        this._requestButton.connect('clicked', () => {
            this._requestTooltip.hide();
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
        this._flashTimeoutId = 0;
        this._destroyed = false;
        this._grantedUntil = approvedGrantRemaining > 0
            ? Main.timeLimitsManager.getCurrentTime() + approvedGrantRemaining
            : 0;
        this._sessionEnd = 0;
        this._refreshPending = false;
        this._timerSignalId = Gio.DBus.system.signal_subscribe(
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
        this._connect(Main.timeLimitsManager, 'notify::daily-limit-time', () => this._sync());
        this._connect(Main.timeLimitsManager, 'notify::daily-limit-enabled', () => this._sync());
        this._connect(Main.sessionMode, 'updated', () => this._sync());
        this._connect(Main.panel, 'notify::width', () => this._sync());
        this._connect(Main.panel, 'notify::height', () => this._sync());

        this._sync();
        this._refreshEstimate();
    }

    setRequestActive(active) {
        this._requestButton?.set_checked(active);
    }

    _syncRequestTooltip() {
        if (!this._requestButton.hover) {
            this._requestTooltip.hide();
            return;
        }

        const [buttonX, buttonY] = this._requestButton.get_transformed_position();
        const [buttonWidth, buttonHeight] = this._requestButton.get_transformed_size();
        const [tooltipWidth] = this._requestTooltip.get_preferred_size();
        const monitor = Main.layoutManager.findMonitorForActor(this._requestButton);
        const tooltipX = Math.clamp(
            Math.floor(buttonX + (buttonWidth - tooltipWidth) / 2),
            monitor.x,
            monitor.x + monitor.width - tooltipWidth);

        this._requestTooltip.set_position(tooltipX, buttonY + buttonHeight + 6);
        this._requestTooltip.show();
    }

    _connect(object, signal, callback) {
        this._signals.push([object, object.connect(signal, callback)]);
    }

    destroy() {
        this._destroyed = true;
        this._onRequest = null;
        this._requestTooltip?.destroy();
        this._requestTooltip = null;

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

        this._clearTimeout();
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

    _clearFlash() {
        if (this._flashTimeoutId) {
            GLib.source_remove(this._flashTimeoutId);
            this._flashTimeoutId = 0;
        }
        this._label?.remove_style_pseudo_class('flash');
    }

    _clearCountdownWarning() {
        this._clearFlash();
        this._label?.remove_style_pseudo_class('countdown');
        this._clearUrgencyVisual();
    }

    _clearUrgencyVisual() {
        for (const actor of [this._urgencyVisual, this._bomb, this._spark,
            this._explosion])
            actor?.remove_style_pseudo_class('expanded');
        this._bomb?.show();
        this._spark?.show();
        this._explosion?.hide();
        this._urgencyVisual?.hide();
    }

    _remainingSeconds() {
        const manager = Main.timeLimitsManager;
        const managerLimit = Number(manager.dailyLimitTime ?? 0);
        const limitTime = Math.max(managerLimit, this._sessionEnd);
        return Math.ceil(limitTime - manager.getCurrentTime());
    }

    async _refreshEstimate() {
        if (this._destroyed || this._refreshPending)
            return;

        this._refreshPending = true;
        try {
            const estimates = await queryEstimatedTimes();
            if (this._destroyed)
                return;

            const estimate = estimates[''];
            this._sessionEnd = estimate ? Number(estimate[2]) : 0;
            console.log(`${LOG_PREFIX} timer estimate loaded; session end=${this._sessionEnd}`);
        } catch (error) {
            if (!this._destroyed) {
                // A transient daemon/database failure says nothing about the
                // last successful estimate. Preserve it until a supported
                // D-Bus query supplies a replacement.
                console.warn(`${LOG_PREFIX} timer query failed; keeping previous estimate: ` +
                    error.message);
            }
        } finally {
            this._refreshPending = false;
            if (!this._destroyed)
                this._sync();
        }
    }

    showGrantedTime(durationSeconds) {
        const now = Main.timeLimitsManager.getCurrentTime();
        if (durationSeconds > 0) {
            this._grantedUntil = now + durationSeconds;
        } else {
            const tomorrow = GLib.DateTime.new_from_unix_local(now)
                .add_days(1);
            this._grantedUntil = GLib.DateTime.new_local(
                tomorrow.get_year(), tomorrow.get_month(), tomorrow.get_day_of_month(),
                0, 0, 0).to_unix();
        }
        this._sync();
    }

    _sync() {
        if (this._destroyed)
            return;

        const manager = Main.timeLimitsManager;
        const managerRemaining = this._remainingSeconds();
        const grantedRemaining = Math.ceil(
            this._grantedUntil - manager.getCurrentTime());
        // Ubuntu uses a primary session mode named "ubuntu", while upstream
        // GNOME commonly uses "user".  Test the session semantics instead of
        // assuming the distribution-specific primary mode name.
        const visible = !Main.sessionMode.isLocked &&
            !Main.sessionMode.isGreeter &&
            (managerRemaining > 0 || grantedRemaining > 0);
        const remainingSecs = grantedRemaining > 0
            ? grantedRemaining
            : managerRemaining;

        if (grantedRemaining <= 0)
            this._grantedUntil = 0;

        if (!visible || remainingSecs <= 0) {
            this._clearTimeout();
            this._setShown(false);
            return;
        }

        this._placeBesideClock();
        this._setShown(true);
        this._updateLabel(remainingSecs);
        this._schedule(remainingSecs);
    }

    _placeBesideClock() {
        const clock = Main.panel.statusArea.dateMenu?.container;
        const centerBox = Main.panel._centerBox;
        if (!clock || !centerBox)
            return;

        const clockPosition = centerBox.get_children().indexOf(clock);
        if (clockPosition < 0)
            return;

        const currentParent = this.container.get_parent();
        const currentPosition = currentParent === centerBox
            ? centerBox.get_children().indexOf(this.container)
            : -1;
        const wantedPosition = clockPosition + 1;

        if (currentParent === centerBox && currentPosition === wantedPosition)
            return;

        currentParent?.remove_child(this.container);
        centerBox.insert_child_at_index(this.container, wantedPosition);
    }

    _setShown(shown) {
        if (shown && !this.container.visible)
            console.log(`${LOG_PREFIX} showing remaining time indicator`);
        this.container.visible = shown;
    }

    _compactLabel() {
        // Use the panel's rendered orientation, not a particular dock
        // extension's setting. That setting can remain LEFT while another
        // extension places the visible panel along the top or bottom.
        return Main.panel.height > Main.panel.width;
    }

    _updateLabel(remainingSecs) {
        if (remainingSecs >= 60)
            this._clearCountdownWarning();

        const compact = this._compactLabel();
        if (remainingSecs > 60) {
            const totalMinutes = Math.floor(remainingSecs / 60);
            const hours = Math.floor(totalMinutes / 60);
            const minutes = totalMinutes % 60;
            const time = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
            this._label.text = compact ? time : `${time} left`;
        } else if (remainingSecs === 1) {
            this._label.text = compact ? '1' : '1 left';
        } else {
            this._label.text = compact ? `${remainingSecs}` : `${remainingSecs} left`;
        }

        if (remainingSecs < 60) {
            this._label.add_style_pseudo_class('countdown');
            this._flashLabel();
        }

        this._updateUrgencyVisual(remainingSecs);
    }

    _updateUrgencyVisual(remainingSecs) {
        if (remainingSecs > 10) {
            this._clearUrgencyVisual();
            return;
        }

        this._urgencyVisual.show();
        if (remainingSecs <= 3) {
            this._bomb.hide();
            this._spark.hide();
            this._explosion.show();
            this._explosion.text = ['✹', '✷', '✸'][3 - remainingSecs];
            this._setExpanded(this._explosion, remainingSecs % 2 === 1);
            return;
        }

        this._explosion.hide();
        this._bomb.show();
        this._spark.show();
        const expanded = remainingSecs % 2 === 0;
        this._setExpanded(this._bomb, expanded);
        this._spark.text = expanded ? '✶' : '✦';
        this._setExpanded(this._spark, expanded);
    }

    _setExpanded(actor, expanded) {
        actor.remove_style_pseudo_class('expanded');
        if (expanded)
            actor.add_style_pseudo_class('expanded');
    }

    _flashLabel() {
        this._clearFlash();
        this._label.add_style_pseudo_class('flash');
        this._flashTimeoutId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT, 350, () => {
                this._flashTimeoutId = 0;
                this._label?.remove_style_pseudo_class('flash');
                return GLib.SOURCE_REMOVE;
            });
    }

    _schedule(remainingSecs) {
        this._clearTimeout();

        let delay;
        if (remainingSecs > 60) {
            const remainder = remainingSecs % 60;
            delay = remainder === 0 ? 60 : remainder;
        } else {
            delay = 1;
        }

        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, delay, () => {
            this._timeoutId = 0;
            this._refreshEstimate();
            this._sync();
            return GLib.SOURCE_REMOVE;
        });
    }
});
