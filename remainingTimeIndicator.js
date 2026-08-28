import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

const LOG_PREFIX = '[request-more-time]';
const ROLE = 'screenTimeRemaining';
const TIMER_BUS_NAME = 'org.freedesktop.MalcontentTimer1';
const TIMER_OBJECT_PATH = '/org/freedesktop/MalcontentTimer1';
const TIMER_INTERFACE = 'org.freedesktop.MalcontentTimer1.Child';

export const RemainingTimeIndicator = GObject.registerClass(
class RemainingTimeIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Screen Time Remaining', true);

        this._label = new St.Label({
            style_class: 'screen-time-remaining-label',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this.add_child(this._label);

        this.reactive = false;
        this.can_focus = false;
        this.track_hover = false;

        this._signals = [];
        this._timeoutId = 0;
        this._destroyed = false;
        this._grantedUntil = 0;
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

        this._sync();
        this._refreshEstimate();
    }

    _connect(object, signal, callback) {
        this._signals.push([object, object.connect(signal, callback)]);
    }

    destroy() {
        this._destroyed = true;

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

    _remainingSeconds() {
        const manager = Main.timeLimitsManager;
        const managerLimit = Number(manager.dailyLimitTime ?? 0);
        const limitTime = Math.max(managerLimit, this._sessionEnd);
        return Math.ceil(limitTime - manager.getCurrentTime());
    }

    _refreshEstimate() {
        if (this._destroyed || this._refreshPending)
            return;

        this._refreshPending = true;
        Gio.DBus.system.call(
            TIMER_BUS_NAME, TIMER_OBJECT_PATH, TIMER_INTERFACE,
            'GetEstimatedTimes', new GLib.Variant('(s)', ['login-session']),
            new GLib.VariantType('(ta{s(btttt)})'),
            Gio.DBusCallFlags.NONE, -1, null, (connection, result) => {
                this._refreshPending = false;
                if (this._destroyed)
                    return;

                try {
                    const [, estimates] = connection.call_finish(result).deepUnpack();
                    const estimate = estimates[''];
                    this._sessionEnd = estimate ? Number(estimate[2]) : 0;
                    console.log(`${LOG_PREFIX} timer estimate loaded; session end=${this._sessionEnd}`);
                } catch (error) {
                    this._sessionEnd = 0;
                    console.warn(`${LOG_PREFIX} timer query failed: ${error.message}`);
                }
                this._sync();
            });
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

    _updateLabel(remainingSecs) {
        if (remainingSecs >= 60) {
            const totalMinutes = Math.floor(remainingSecs / 60);
            const hours = Math.floor(totalMinutes / 60);
            const minutes = totalMinutes % 60;
            this._label.text =
                `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')} left`;
        } else if (remainingSecs === 1) {
            this._label.text = '1 second left';
        } else {
            this._label.text = `${remainingSecs} seconds left`;
        }
    }

    _schedule(remainingSecs) {
        this._clearTimeout();

        let delay;
        if (remainingSecs >= 60) {
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
