import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {getLoginManager} from 'resource:///org/gnome/shell/misc/loginManager.js';
import {TimeLimitsState} from 'resource:///org/gnome/shell/misc/timeLimitsManager.js';

const SETTLE_MS = 1000;
const UINT32_MAX = 4294967295;
// Shell's own session proxy omits IdleHint and LockedHint. Use the public
// logind interface directly rather than treating absent properties as false.
const SessionProxy = Gio.DBusProxy.makeProxyWrapper(`<node>
  <interface name="org.freedesktop.login1.Session">
    <signal name="Lock"/>
    <signal name="Unlock"/>
    <property name="Active" type="b" access="read"/>
    <property name="IdleHint" type="b" access="read"/>
    <property name="LockedHint" type="b" access="read"/>
  </interface>
</node>`);

// Observe the existing native admission path. In particular, an Unlock signal
// is not a successful unlock: ScreenShield may reject it while the native
// parental-controls state still says LIMIT_REACHED. Never retry that signal,
// change policy, or touch private Shell state from diagnostics.
export class SessionDiagnostics {
    constructor(manager, mode, observe, failure, login = getLoginManager()) {
        this._manager = manager;
        this._mode = mode;
        this._observe = observe;
        this._failure = failure;
        this._disconnect = [];
        this._closed = false;
        this._attempt = 0;
        this._unlockStarted = null;
        this._timer = 0;
        this.ready = this._attach(login).catch(() => {
            if (!this._closed) {
                this.close();
                this._failed();
            }
        });
    }

    _connect(object, signal, callback, dbus = false) {
        const safe = (...args) => {
            if (this._closed)
                return;
            try { callback(...args); } catch (_error) { this._failed(); }
        };
        const id = dbus ? object.connectSignal(signal, safe) : object.connect(signal, safe);
        this._disconnect.push(() => dbus ? object.disconnectSignal(id) : object.disconnect(id));
    }

    async _attach(login) {
        const current = await login.getCurrentSessionProxy();
        if (this._closed)
            return;
        if (!current)
            throw new Error('Session diagnostics unavailable');
        const session = await SessionProxy.newAsync(Gio.DBus.system,
            'org.freedesktop.login1', current.get_object_path());
        if (this._closed)
            return;
        this._session = session;
        for (const signal of ['notify::state', 'notify::should-lock-session',
            'notify::daily-limit-time', 'notify::daily-limit-enabled'])
            this._connect(this._manager, signal, () => this._record('native'));
        this._connect(this._mode, 'updated', () => this._record('mode'));
        this._connect(session, 'g-properties-changed', () => this._record('session'));
        this._connect(session, 'notify::g-name-owner', () => {
            this._record('owner-changed', true);
            this._cancelObservation();
        });
        this._connect(login, 'prepare-for-sleep', (_login, sleeping) => {
            this._record(sleeping ? 'sleep' : 'wake', true);
            if (sleeping)
                this._cancelObservation();
        });
        for (const signal of ['Lock', 'Unlock']) {
            this._connect(session, signal, (_session, sender) => {
                if (this._closed || !sender || sender !== session.get_name_owner())
                    return;
                this._cancelObservation();
                if (signal === 'Lock') {
                    this._record('lock-request', true);
                    return;
                }
                this._attempt = this._attempt % 2147483647 + 1;
                this._unlockStarted = GLib.get_monotonic_time();
                this._record('unlock-request', true);
                this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, SETTLE_MS, () => {
                    this._timer = 0;
                    this._record('unlock-settled', true);
                    this._unlockStarted = null;
                    return GLib.SOURCE_REMOVE;
                });
            }, true);
        }
        this._record('initial', true);
        return {session, login};
    }

    _record(reason, force = false) {
        if (this._closed)
            return;
        try {
            const manager = this._manager;
            const nativeState = {
                [TimeLimitsState.DISABLED]: 'disabled',
                [TimeLimitsState.ACTIVE]: 'active',
                [TimeLimitsState.LIMIT_REACHED]: 'limit-reached',
            }[manager.state] ?? 'unknown';
            const remaining = Number(manager.dailyLimitTime) - manager.getCurrentTime();
            const state = {
                native_state: nativeState,
                native_should_lock: Boolean(manager.shouldLockSession),
                limit_enabled: Boolean(manager.parentalControlsSessionLimitsEnabled),
                session_available: Boolean(this._session.get_name_owner()),
                session_active: Boolean(this._session.Active),
                session_idle: Boolean(this._session.IdleHint),
                session_locked: Boolean(this._session.LockedHint),
                locked: Boolean(this._mode.isLocked),
                greeter: Boolean(this._mode.isGreeter),
            };
            const key = JSON.stringify(state);
            if (!force && key === this._lastState)
                return;
            this._lastState = key;
            const elapsed = this._unlockStarted === null ? 0
                : (GLib.get_monotonic_time() - this._unlockStarted) / 1000;
            this._observe({reason, attempt: this._attempt, ...state,
                native_remaining: Number.isFinite(remaining)
                    ? Math.max(0, Math.min(UINT32_MAX, Math.ceil(remaining))) : 0,
                elapsed_ms: Math.max(0, Math.min(UINT32_MAX, Math.floor(elapsed)))});
        } catch (_error) {
            this._failed();
        }
    }

    _failed() {
        try { this._failure(); } catch (_error) { /* diagnostics only */ }
    }

    _cancelObservation() {
        if (this._timer)
            GLib.source_remove(this._timer);
        this._timer = 0;
        this._unlockStarted = null;
    }

    close() {
        this._closed = true;
        this._cancelObservation();
        for (const disconnect of this._disconnect.splice(0).reverse()) {
            try { disconnect(); } catch (_error) { /* finish owned cleanup */ }
        }
    }
}
