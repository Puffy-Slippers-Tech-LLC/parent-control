import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {queryEstimatedTimes, replayOwnUsage, timerErrorCategory} from './timerQuery.js';
import {logWarning} from './logger.js';

// GNOME 50 retains its parental-controls wall-clock deadline across inactivity.
// Its public dailyLimitTime getter is zero while inactive. Refresh that cache
// through Malcontent's overlap-merging API, never through private Shell state.
// The daemon's change signal is broadcast across accounts. A peer's write can
// therefore replace an active native deadline with an estimate which omits
// ongoing use. Checkpoint that observed activity when the deadline increases.
// See Screen-Time.md for the API contract.
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
        this.resumeFailures = new Map();
        this.resumeReported = false;
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
        const previousDeadline = this.deadline;
        this.enabled = this.manager.parentalControlsSessionLimitsEnabled;
        this.deadline = Number(this.manager.dailyLimitTime);
        this.active = this.deadline > 0;
        if (this.active && !wasActive)
            this.activeSince = {
                realtime: GLib.get_real_time(),
                monotonic: GLib.get_monotonic_time(),
            };
        else if (!this.active)
            this.activeSince = null;
        if (this.enabled !== wasEnabled) {
            this.resumeFailures.clear();
            this.resumeReported = false;
            this.reported = false;
        }
        if (this.enabled !== wasEnabled || this.active !== wasActive ||
            recheckInactive && this.enabled && !this.active) {
            this.cancelTimer();
            this.cancellable?.cancel();
            this.again = false;
            this.failures = 0;
            if (this.enabled && (!this.active || wasEnabled && wasActive === false))
                this.refresh();
        } else if (this.enabled && this.active && this.deadline > previousDeadline) {
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
        let stage = 'usage-queue';
        try {
            const replayed = await replayOwnUsage(cancellable, value => { stage = value; },
                () => this.activeSince);
            if (cancellable.is_cancelled()) return;
            if (replayed) {
                stage = 'timer-estimate';
                const estimates = await queryEstimatedTimes();
                if (cancellable.is_cancelled()) return;
                stage = 'estimate-processing';
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
            if (replayed && this.active) {
                this.resumeFailures.clear();
                this.resumeReported = false;
            }
            retry = !this.active && delay > 0;
        } catch (error) {
            if (cancellable.is_cancelled()) return;
            this.failures++;
            const category = timerErrorCategory(error);
            const transient = ['busy', 'no-reply', 'no-owner', 'service-unknown', 'timeout']
                .includes(category);
            // Keep active failures bounded to notifications; do not turn
            // timer-service trouble into periodic usage writes.
            retry = transient && !this.active;
            // A single temporary boundary failure can retain a finite native
            // deadline. Keep per-stage evidence across idle successes: a
            // resume-only QueryUsage/RecordUsage defect need not affect the
            // independent countdown reads or idle maintenance at all.
            const activeFailure = transient && this.active &&
                ['query-usage', 'record-usage'].includes(stage) &&
                Number.isFinite(Number(this.manager.dailyLimitTime));
            const failures = activeFailure
                ? Math.min(0x7fffffff, (this.resumeFailures.get(stage) ?? 0) + 1)
                : Math.min(0x7fffffff, this.failures);
            if (activeFailure) this.resumeFailures.set(stage, failures);
            const deferred = activeFailure && failures < 3;
            delay = Math.min(60_000, 1000 * 2 ** Math.min(this.failures - 1, 6));
            try {
                if (deferred) {
                    logWarning('child.resume-refresh-deferred', {stage, category});
                } else {
                    logWarning('child.resume-refresh-failed', {
                        stage, category, active: Boolean(this.active),
                        limit_enabled: Boolean(this.enabled),
                        failures, retry,
                        delay_ms: retry ? delay : 0,
                    });
                }
            } catch (_error) { /* preserve retry and error-report behavior */ }
            if (activeFailure) {
                if (!deferred && !this.resumeReported) {
                    this.resumeReported = true;
                    this.report(error);
                }
            } else if (!retry || this.failures >= 3) this.report(error);
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
