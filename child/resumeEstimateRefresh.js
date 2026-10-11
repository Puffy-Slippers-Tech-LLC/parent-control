import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {queryEstimatedTimes, replayOwnUsage, timerErrorCategory} from './timerQuery.js';

// GNOME 50 retains its parental-controls wall-clock deadline across inactivity.
// Its public dailyLimitTime getter is zero while inactive. Refresh that cache
// through Malcontent's overlap-merging API, never through private Shell state.
// Continuous use must keep the native deadline: the daemon does not yet know
// about the ongoing active interval. See Screen-Time.md for the API contract.
export class ResumeEstimateRefresh {
    constructor(manager, onError) {
        this.manager = manager;
        this.onError = onError;
        this.connections = [];
        this.closed = false;
        this.pending = false;
        this.again = false;
        this.timer = 0;
        this.failures = 0;
        try {
            for (const signal of ['notify::daily-limit-time', 'notify::daily-limit-enabled', 'notify::state'])
                this.connections.push(manager.connect(signal,
                    () => this.update(signal !== 'notify::daily-limit-time')));
            this.update();
        } catch (error) {
            this.close();
            throw error;
        }
    }

    update(recheckInactive = false) {
        if (this.closed) return;
        const wasEnabled = this.enabled;
        const wasActive = this.active;
        this.enabled = this.manager.parentalControlsSessionLimitsEnabled;
        this.active = Number(this.manager.dailyLimitTime) > 0;
        if (this.enabled !== wasEnabled || this.active !== wasActive ||
            recheckInactive && this.enabled && !this.active) {
            this.cancelTimer();
            this.cancellable?.cancel();
            this.again = false;
            this.failures = 0;
            if (this.enabled && (!this.active || wasEnabled && wasActive === false))
                this.refresh();
        }
        // Estimate notifications can be our own delayed replay echo. Only a
        // policy/state change rearms an exhausted inactive balance; native
        // state transitions also cover the next day's restored allowance.
    }

    async refresh() {
        if (this.closed || !this.enabled) return;
        if (this.pending) {
            this.again = true;
            return;
        }
        this.pending = true;
        const cancellable = new Gio.Cancellable();
        this.cancellable = cancellable;
        let delay = 1000;
        let retry = false;
        try {
            const replayed = await replayOwnUsage(cancellable);
            if (cancellable.is_cancelled()) return;
            if (replayed) {
                const estimates = await queryEstimatedTimes();
                if (cancellable.is_cancelled()) return;
                const remaining = Number(estimates['']?.[2]) - GLib.get_real_time() / 1_000_000;
                // Refresh before an idle cached deadline expires. Use subsecond
                // scheduling near exhaustion, accounting for fractional time.
                if (Number.isFinite(remaining))
                    delay = remaining <= 0 ? 0 : Math.max(100, Math.min(60_000, remaining * 500));
            }
            // No actual history means no write; retry after Shell saves its
            // completed interval. A genuine zero balance needs no heartbeat.
            this.failures = 0;
            this.reported = false;
            retry = !this.active && delay > 0;
        } catch (error) {
            if (cancellable.is_cancelled()) return;
            this.failures++;
            const transient = ['busy', 'no-reply', 'no-owner', 'service-unknown', 'timeout']
                .includes(timerErrorCategory(error));
            // Never replay late retries during active use: they would omit
            // ongoing, uncheckpointed usage and extend the native deadline.
            retry = transient && !this.active;
            delay = Math.min(60_000, 1000 * 2 ** Math.min(this.failures - 1, 6));
            if (!retry || this.failures >= 3) this.report(error);
        } finally {
            this.pending = false;
            if (!this.closed && this.enabled) {
                if (this.again) {
                    this.again = false;
                    this.refresh();
                } else if (retry && !cancellable.is_cancelled()) {
                    this.timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.ceil(delay), () => {
                        this.timer = 0;
                        this.refresh();
                        return GLib.SOURCE_REMOVE;
                    });
                }
            }
        }
    }

    cancelTimer() {
        if (this.timer) GLib.source_remove(this.timer);
        this.timer = 0;
    }

    report(error) {
        if (this.closed || this.reported) return;
        this.reported = true;
        try { this.onError?.(error); } catch (_error) { /* reporting is isolated */ }
    }

    close() {
        if (this.closed) return;
        this.closed = true;
        this.cancelTimer();
        this.cancellable?.cancel();
        for (const id of this.connections) this.manager.disconnect(id);
        this.connections = [];
        this.onError = null;
    }
}
