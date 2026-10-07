// Presentation only: these values never participate in time/app enforcement.
// GNOME Shell 50's private PARENTAL_CONTROLS_LIMIT_UPCOMING_NOTIFICATION_TIME_SECONDS.
export const NATIVE_WARNING_SECONDS = 60;
export const WINDOW_MARGIN_SECONDS = 5;
export function wellbeingWindowEnd(manager, preferences, blocked) {
    const remaining = manager.dailyLimitTime - manager.getCurrentTime();
    return !blocked && manager.parentalControlsSessionLimitsEnabled &&
        manager.dailyLimitEnabled && preferences?.reminders?.length > 0 &&
        Number.isFinite(remaining) && remaining > NATIVE_WARNING_SECONDS - WINDOW_MARGIN_SECONDS &&
        remaining <= NATIVE_WARNING_SECONDS + WINDOW_MARGIN_SECONDS
        ? manager.dailyLimitTime - (NATIVE_WARNING_SECONDS - WINDOW_MARGIN_SECONDS) : 0;
}

/** One user-wide settings owner, with independent bounded leases per bus sender. */
export class WellbeingLeases {
    constructor(settings, wallTime, monotonicTime, observe = () => {}) {
        this.settings = settings;
        this.wallTime = wallTime;
        this.monotonicTime = monotonicTime;
        this.leases = new Map();
        this.observe = observe;
    }

    event(stage, outcome) {
        try { this.observe(stage, outcome); } catch (_error) { /* best effort */ }
    }

    step(stage, action) {
        try {
            const result = action();
            if (stage !== 'recovery-read') this.event(stage, 'complete');
            return result;
        } catch (error) {
            this.event(stage, 'failed');
            throw error;
        }
    }

    restore() {
        const backup = this.step('recovery-read', () => this.settings.backup());
        if (backup === '') return;
        if (!['default', 'true', 'false'].includes(backup)) {
            this.event('recovery-record', 'invalid');
            throw new Error('Invalid Wellbeing recovery record');
        }
        this.step('banner-restore', () => { this.settings.restore(backup); this.settings.sync(); });
        this.step('recovery-clear', () => { this.settings.saveBackup(''); this.settings.sync(); });
    }

    set(sender, end) {
        const duration = end - this.wallTime();
        if (!Number.isFinite(end) || (end !== 0 &&
            (duration <= 0 || duration > 2 * WINDOW_MARGIN_SECONDS))) {
            this.event('window', 'invalid');
            throw new Error('Invalid Wellbeing window');
        }
        this.expire();
        if (end === 0) {
            this.event('lease-release', this.leases.delete(sender) ? 'complete' : 'absent');
            if (!this.leases.size) this.restore();
            return;
        }
        if (!this.leases.size) {
            // Persist recovery before the first write to another application's key.
            // A failed write leaves the recovery record available for retry.
            const original = this.step('banner-read', () => this.settings.original());
            this.event('original-value', original);
            this.step('recovery-save', () => { this.settings.saveBackup(original); this.settings.sync(); });
            this.step('banner-suppress', () => { this.settings.suppress(); this.settings.sync(); });
        }
        this.event('lease-acquire', this.leases.has(sender) ? 'renewed' : 'complete');
        this.leases.set(sender, {end, monotonicEnd: this.monotonicTime() + duration});
    }

    expire() {
        for (const [sender, lease] of this.leases) {
            if (this.wallTime() >= lease.end || this.monotonicTime() >= lease.monotonicEnd) {
                this.event('lease-expire', this.wallTime() >= lease.end ? 'wall' : 'monotonic');
                this.leases.delete(sender);
            }
        }
        if (!this.leases.size) this.restore();
    }

    close() {
        this.event('shutdown', 'complete');
        this.leases.clear();
        this.restore();
    }
}
