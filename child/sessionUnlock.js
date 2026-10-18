import GLib from 'gi://GLib';
import {TimeLimitsState} from 'resource:///org/gnome/shell/misc/timeLimitsManager.js';
import {recordChildFailure} from './errorHandler.js';

const REQUEST_LIFETIME_MS = 2000;
const OBSERVATION_LIFETIME_MS = 2000;

// GNOME 50 can discard logind's Unlock while its inactive limit state is
// stale. Continue only that trusted request, once, through the same public
// ScreenShield.deactivate() entry point used by GNOME's own logind handler.
// No method replacement, private-state write, credential or policy mutation.
export class SessionUnlockRecovery {
    constructor(manager, mode, shield, session, login, observe, failure) {
        this._manager = manager;
        this._mode = mode;
        this._shield = shield;
        this._session = session;
        this._login = login;
        this._observe = observe;
        this._failure = failure;
        this._disconnect = [];
        this._closed = false;
        this._number = 0;
        this._request = null;
        this._idle = 0;
        this._timeout = 0;
        try {
            if (typeof shield?.deactivate !== 'function')
                throw new Error('Native unlock entry point unavailable');
            for (const signal of ['notify::state', 'notify::should-lock-session',
                'notify::daily-limit-time', 'notify::daily-limit-enabled'])
                this._connect(manager, signal, () => this._changed());
            this._connect(mode, 'updated', () => this._changed());
            this._connect(shield, 'locked-changed', () => this._changed());
            this._connect(session, 'g-properties-changed', () => this._changed());
            this._connect(session, 'notify::g-name-owner', () => this._finish('cancelled', 'owner-changed'));
            this._connect(login, 'prepare-for-sleep', (_login, sleeping) => {
                if (sleeping)
                    this._finish('cancelled', 'sleep');
            });
            this._connect(session, 'Lock', (_session, sender) => {
                if (this._trusted(sender))
                    this._finish('cancelled', 'new-lock');
            }, true);
            this._connect(session, 'Unlock', (_session, sender) => {
                if (this._trusted(sender))
                    this._unlockRequested(sender);
            }, true);
        } catch (error) {
            recordChildFailure(error, 'unlock-startup');
            this.close();
            throw error;
        }
    }

    _connect(object, signal, callback, dbus = false) {
        const safe = (...args) => {
            if (this._closed)
                return;
            try { callback(...args); } catch (error) {
                this._finish('failed', 'unavailable');
                this._failed(error, 'unlock-signal');
            }
        };
        const id = dbus ? object.connectSignal(signal, safe) : object.connect(signal, safe);
        this._disconnect.push(() => dbus ? object.disconnectSignal(id) : object.disconnect(id));
    }

    _trusted(sender) {
        return Boolean(sender) && sender === this._session.get_name_owner();
    }

    _unlockRequested(owner) {
        this._finish('cancelled', 'superseded');
        this._number = this._number % 2147483647 + 1;
        // Ordinary successful unlocks and non-parental locks need no recovery.
        if (!this._shield.locked || !this._mode.isLocked || this._mode.isGreeter ||
            this._login.preparingForSleep ||
            this._manager.parentalControlsSessionLimitsEnabled !== true ||
            this._manager.shouldLockSession !== true ||
            this._manager.state !== TimeLimitsState.LIMIT_REACHED)
            return;
        this._request = {number: this._number, owner,
            started: GLib.get_monotonic_time(), activeSeen: this._session.Active === true,
            cleared: false, retried: false, dispatched: false};
        this._record('armed', 'native-lock');
        this._armTimeout(REQUEST_LIFETIME_MS);
        this._changed();
    }

    _changed() {
        const request = this._request;
        if (!request)
            return;
        // Consume success immediately, before another direct ScreenSaver or
        // shortcut lock can occur. Waiting until an idle would let the earlier
        // authorization unlock that newly locked desktop a second time.
        if (!this._shield.locked) {
            this._finish('unlocked', 'none');
            return;
        }
        if (!request.dispatched && !this._mode.isLocked && !this._mode.isGreeter) {
            // Native deactivation has already started its own animation. It
            // owns completion, so this request must never initiate another.
            this._finish('native-owned', 'native-unlocking');
            return;
        }
        // Observe transitions synchronously, even when several notifications
        // coalesce before the idle callback. Later exhaustion invalidates the
        // original request; a subsequent grant cannot resurrect it.
        if (this._manager.shouldLockSession === false)
            request.cleared = true;
        else if (request.cleared) {
            this._finish('cancelled', 'time-exhausted');
            return;
        }
        if (this._session.Active === true)
            request.activeSeen = true;
        if (this._session.Active === false && request.activeSeen) {
            this._finish('cancelled', 'session-inactive');
            return;
        }
        if (this._mode.isGreeter || this._login.preparingForSleep ||
            this._manager.parentalControlsSessionLimitsEnabled !== true) {
            this._finish('cancelled', this._mode.isGreeter ? 'greeter'
                : this._login.preparingForSleep ? 'sleep' : 'limits-disabled');
            return;
        }
        if (this._idle)
            return;
        this._idle = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._idle = 0;
            try { this._continue(); } catch (error) {
                this._finish('failed', 'unavailable');
                this._failed(error, 'unlock-dispatch');
            }
            return GLib.SOURCE_REMOVE;
        });
    }

    _continue() {
        const request = this._request;
        if (!request || this._closed)
            return;
        if (request.retried)
            return;
        // Recheck at dispatch; timers can run late or in a different order
        // after a busy main loop. No timeout callback extends authorization.
        if (GLib.get_monotonic_time() - request.started >= REQUEST_LIFETIME_MS * 1000) {
            this._finish('expired', 'deadline');
            return;
        }
        if (this._session.get_name_owner() !== request.owner) {
            this._finish('cancelled', 'owner-changed');
            return;
        }
        if (!this._shield.locked) {
            this._finish('unlocked', 'none');
            return;
        }
        if (this._mode.isGreeter || this._login.preparingForSleep ||
            this._manager.parentalControlsSessionLimitsEnabled !== true ||
            this._session.Active !== true ||
            !this._mode.isLocked)
            return;
        // dailyLimitTime is zero while GNOME considers the user inactive.
        // Its native decision is authoritative; a per-session IdleHint can
        // lag or differ from the aggregate user activity GNOME actually uses.
        const deadline = Number(this._manager.dailyLimitTime);
        if (this._manager.shouldLockSession !== false ||
            this._manager.state !== TimeLimitsState.ACTIVE ||
            !Number.isFinite(deadline) || deadline <= this._manager.getCurrentTime())
            return;
        // Consume before dispatch to withstand synchronous native signals.
        // Invoke the public native entry point in this main-loop turn, with
        // no extra bus hop. It may queue its OWN asynchronous message/animation
        // completion; no public API can cancel that native operation. From
        // handoff onward we observe, never claim to retract its callbacks.
        request.retried = true;
        this._record('retry', 'none');
        if (this._request === request && !this._closed) {
            request.dispatched = true;
            this._armTimeout(OBSERVATION_LIFETIME_MS);
            this._shield.deactivate(false);
        }
        // A returned call is not proof of an unlock; observe actual state.
        this._changed();
    }

    _record(stage, reason, request = this._request) {
        if (!request)
            return;
        try {
            const remaining = Number(this._manager.dailyLimitTime) - this._manager.getCurrentTime();
            this._observe({stage, reason, attempt: request.number,
                elapsed_ms: Math.max(0, Math.min(4294967295,
                    Math.floor((GLib.get_monotonic_time() - request.started) / 1000))),
                native_should_lock: Boolean(this._manager.shouldLockSession),
                locked: Boolean(this._shield.locked),
                session_active: Boolean(this._session.Active),
                native_remaining: Number.isFinite(remaining)
                    ? Math.max(0, Math.min(4294967295, Math.ceil(remaining))) : 0});
        } catch (error) {
            this._failed(error, 'unlock-observe');
        }
    }

    _failed(error, operation) {
        recordChildFailure(error, operation);
        try { this._failure(); } catch (_error) { /* diagnostics only */ }
    }

    _armTimeout(delay) {
        if (this._timeout)
            GLib.source_remove(this._timeout);
        this._timeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delay, () => {
            this._timeout = 0;
            this._finish('expired', 'deadline');
            return GLib.SOURCE_REMOVE;
        });
    }

    _finish(stage, reason) {
        const request = this._request;
        this._request = null;
        for (const name of ['_idle', '_timeout']) {
            if (this[name])
                GLib.source_remove(this[name]);
            this[name] = 0;
        }
        if (request?.dispatched) {
            if (stage === 'cancelled') stage = 'observed-interruption';
            if (stage === 'expired') stage = 'observation-expired';
        }
        this._record(stage, reason, request);
    }

    close() {
        this._closed = true;
        this._finish('cancelled', 'closed');
        for (const disconnect of this._disconnect.splice(0).reverse()) {
            try { disconnect(); } catch (error) {
                recordChildFailure(error, 'unlock-cleanup');
            }
        }
    }
}
