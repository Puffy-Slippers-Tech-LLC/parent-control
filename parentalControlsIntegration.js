import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {TimeLimitsState} from 'resource:///org/gnome/shell/misc/timeLimitsManager.js';

import {
    clearApprovedGrant,
    loadApprovedGrantRemaining,
    saveApprovedGrant,
} from './approvedGrantStore.js';

const LOG_PREFIX = '[request-more-time]';
const SESSION_LIMITS_EXTEND_ACTION =
    'org.freedesktop.Malcontent.SessionLimits.Extend';
const COMBINED_APPROVAL_ACTION =
    'org.gnome.shell.extensions.request-more-time.ApproveTimeAndApps';
const NATIVE_REQUEST_TIMEOUT_SECONDS = 2 * 60;

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
        this._nativeIgnoreButton = null;
        this._nativeIgnoreShield = null;
        this._nativeIgnoreSignalId = 0;
        this._nativeRequestDeadlineMonotonicSeconds = 0;
        this._nativeRequestCookie = null;
        this._nativeCookieSourceId = 0;
        this._syncSourceId = 0;
        this._relockSourceId = 0;
        this._grantExpirySourceId = 0;
        this._grantExpiresMonotonicSeconds = 0;
        this._grantExpiresRealSeconds = 0;
        this._polkitAgent = null;
        this._polkitOriginalInitiate = null;
        this._polkitInitiateHandlerId = 0;
        this._timeLimitsOriginalUpdateState = null;
        this._timeLimitsWrappedUpdateState = null;

        const persistedGrantRemaining = loadApprovedGrantRemaining();
        if (persistedGrantRemaining > 0) {
            this._setApprovedGrantRemaining(persistedGrantRemaining);
            console.log(`${LOG_PREFIX} restored approved grant; ` +
                `remaining=${persistedGrantRemaining}`);
        }
    }

    enable() {
        this._patchTimeLimitsManager();
        this._connect(Main.timeLimitsManager, 'notify::state', () => this._sync());
        this._connect(Main.sessionMode, 'updated', () => this._sync());
        this._connect(Main.screenShield, 'active-changed', () => {
            this._sync();
            if (!Main.screenShield.active)
                this._scheduleRelockCheck();
        });
        this.ensurePolkitAgentPatched();
        this._recalculateTimeLimits();
        this._sync();
    }

    ensurePolkitAgentPatched() {
        return this._patchPolkitAgent();
    }

    isExhausted() {
        const shield = this._findShield();
        return !this._hasActiveApprovedGrant() &&
            Main.sessionMode.currentMode === 'unlock-dialog' &&
            Main.timeLimitsManager.state === TimeLimitsState.LIMIT_REACHED &&
            shield !== null && shield.get_parent() !== null;
    }

    recordApprovedGrant(durationSeconds) {
        if (!Number.isSafeInteger(durationSeconds) || durationSeconds <= 0)
            throw new Error('Invalid approved grant duration');

        // ExtensionResponse is Malcontent's authoritative, authenticated
        // approval. Keep GNOME's state calculation and this extension's
        // additional GDM-bypass protection from contradicting that approval
        // if the daemon temporarily publishes a stale estimate.
        // Check both clocks: monotonic time prevents wall-clock rollback from
        // extending access, while real time ensures suspend counts against the
        // approved duration.
        // Persist before yielding again so a Shell/session restart cannot lose
        // the authenticated approval and let a stale LIMIT_REACHED cache lock
        // the child again.
        saveApprovedGrant(durationSeconds);
        this._setApprovedGrantRemaining(durationSeconds);
        this._recalculateTimeLimits();
        this._sync();
    }

    observeNativeExtensionResponse({granted, cookie, extraData}) {
        const nowMonotonicSeconds =
            GLib.get_monotonic_time() / GLib.USEC_PER_SEC;
        if (this._nativeRequestDeadlineMonotonicSeconds <= nowMonotonicSeconds)
            return 0;

        // ExtensionResponse is broadcast on the system bus. Pair it with the
        // exact cookie owned by this Shell's native shield so an approval for
        // another session can never create a local grant here.
        const nativeCookie = this._nativeRequestCookie ??
            this._nativeIgnoreShield?._requestExtensionCookie;
        if (typeof nativeCookie !== 'string' || cookie !== nativeCookie)
            return 0;

        this._clearNativeCookieCapture();
        this._nativeRequestDeadlineMonotonicSeconds = 0;
        if (!granted) {
            console.log(`${LOG_PREFIX} native Ignore request rejected`);
            return 0;
        }

        let durationSeconds = extraData?.['duration-secs'];
        if (typeof durationSeconds?.deepUnpack === 'function')
            durationSeconds = durationSeconds.deepUnpack();
        durationSeconds = Number(durationSeconds);
        if (!Number.isSafeInteger(durationSeconds) || durationSeconds <= 0) {
            console.warn(`${LOG_PREFIX} native Ignore approval omitted a valid duration`);
            return 0;
        }

        this.recordApprovedGrant(durationSeconds);
        console.log(`${LOG_PREFIX} captured native Ignore approval; ` +
            `duration=${durationSeconds}`);
        return durationSeconds;
    }

    getApprovedGrantRemaining() {
        if (!this._hasActiveApprovedGrant())
            return 0;

        const monotonicRemaining = this._grantExpiresMonotonicSeconds -
            GLib.get_monotonic_time() / GLib.USEC_PER_SEC;
        const realRemaining = this._grantExpiresRealSeconds -
            GLib.get_real_time() / GLib.USEC_PER_SEC;
        return Math.max(0, Math.ceil(Math.min(monotonicRemaining, realRemaining)));
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
        if (this._grantExpirySourceId) {
            GLib.source_remove(this._grantExpirySourceId);
            this._grantExpirySourceId = 0;
        }
        this._clearNativeCookieCapture();
        this._grantExpiresMonotonicSeconds = 0;
        this._grantExpiresRealSeconds = 0;
        this._unpatchTimeLimitsManager();
        if (this._polkitInitiateHandlerId) {
            try {
                this._polkitAgent?.disconnect(this._polkitInitiateHandlerId);
            } catch (error) {
                console.debug(`${LOG_PREFIX} polkit initiate handler already disconnected: ${error.message}`);
            }
            if (this._polkitAgent && this._polkitOriginalInitiate)
                this._polkitAgent.connect(
                    'initiate', this._polkitOriginalInitiate.bind(this._polkitAgent));
        }
        if (this._polkitAgent?._requestMoreTimePolkitPatch === this)
            delete this._polkitAgent._requestMoreTimePolkitPatch;
        this._polkitInitiateHandlerId = 0;
        this._polkitAgent = null;
        this._polkitOriginalInitiate = null;
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
        this._watchNativeIgnoreButton(shield);
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
        this._unwatchNativeIgnoreButton();
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

    _watchNativeIgnoreButton(shield) {
        const ignoreButton = shield?._ignoreButton ?? null;
        if (ignoreButton === this._nativeIgnoreButton)
            return;

        this._unwatchNativeIgnoreButton();
        if (!ignoreButton)
            return;

        this._nativeIgnoreButton = ignoreButton;
        this._nativeIgnoreShield = shield;
        this._nativeIgnoreSignalId = ignoreButton.connect('clicked', () => {
            this._clearNativeCookieCapture();
            this._nativeRequestDeadlineMonotonicSeconds =
                GLib.get_monotonic_time() / GLib.USEC_PER_SEC +
                NATIVE_REQUEST_TIMEOUT_SECONDS;
            this._scheduleNativeCookieCapture();
            console.log(`${LOG_PREFIX} observing native Ignore request`);
        });
    }

    _scheduleNativeCookieCapture() {
        this._nativeCookieSourceId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT, 25, () => {
                const nowMonotonicSeconds =
                    GLib.get_monotonic_time() / GLib.USEC_PER_SEC;
                if (this._nativeRequestDeadlineMonotonicSeconds <=
                    nowMonotonicSeconds) {
                    this._nativeCookieSourceId = 0;
                    this._nativeRequestCookie = null;
                    return GLib.SOURCE_REMOVE;
                }

                const cookie = this._nativeIgnoreShield?._requestExtensionCookie;
                if (typeof cookie !== 'string')
                    return GLib.SOURCE_CONTINUE;

                this._nativeRequestCookie = cookie;
                this._nativeCookieSourceId = 0;
                return GLib.SOURCE_REMOVE;
            });
    }

    _clearNativeCookieCapture() {
        if (this._nativeCookieSourceId)
            GLib.source_remove(this._nativeCookieSourceId);
        this._nativeCookieSourceId = 0;
        this._nativeRequestCookie = null;
    }

    _unwatchNativeIgnoreButton() {
        if (this._nativeIgnoreSignalId) {
            try {
                this._nativeIgnoreButton?.disconnect(this._nativeIgnoreSignalId);
            } catch (error) {
                console.debug(`${LOG_PREFIX} native Ignore button already disconnected: ` +
                    error.message);
            }
        }
        this._nativeIgnoreSignalId = 0;
        this._nativeIgnoreButton = null;
        this._nativeIgnoreShield = null;
    }

    _relockIfLimitWasBypassed() {
        const screenShield = Main.screenShield;
        if (Main.timeLimitsManager.state !== TimeLimitsState.LIMIT_REACHED ||
            !screenShield || screenShield.locked || this._hasActiveApprovedGrant())
            return;

        // GDM can unlock an existing session without recreating this session's
        // UnlockDialog. The time-limit state remains LIMIT_REACHED, so GNOME's
        // state-transition dispatcher does not request another lock. Re-lock
        // when this Shell next observes the now-unlocked session.
        screenShield.lock(false);
        console.log(`${LOG_PREFIX} re-locked session after exhausted-limit bypass`);
    }

    _patchTimeLimitsManager() {
        const manager = Main.timeLimitsManager;
        const originalUpdateState = manager?._updateState;
        if (!manager || typeof originalUpdateState !== 'function') {
            console.warn(`${LOG_PREFIX} time-limits manager cannot apply grant overlay`);
            return false;
        }
        if (manager._requestMoreTimeGrantOverlay) {
            console.warn(`${LOG_PREFIX} time-limits grant overlay is already installed`);
            return false;
        }

        const wrappedUpdateState = (...args) => {
            this._overlayApprovedGrantEstimate();
            return originalUpdateState.apply(manager, args);
        };
        this._timeLimitsOriginalUpdateState = originalUpdateState;
        this._timeLimitsWrappedUpdateState = wrappedUpdateState;
        manager._updateState = wrappedUpdateState;
        manager._requestMoreTimeGrantOverlay = wrappedUpdateState;
        console.log(`${LOG_PREFIX} installed authenticated grant overlay`);
        return true;
    }

    _unpatchTimeLimitsManager() {
        const manager = Main.timeLimitsManager;
        if (manager?._updateState === this._timeLimitsWrappedUpdateState)
            manager._updateState = this._timeLimitsOriginalUpdateState;
        if (manager?._requestMoreTimeGrantOverlay ===
            this._timeLimitsWrappedUpdateState)
            delete manager._requestMoreTimeGrantOverlay;

        this._timeLimitsOriginalUpdateState = null;
        this._timeLimitsWrappedUpdateState = null;
        this._refreshTimeLimitsEstimate();
    }

    _overlayApprovedGrantEstimate() {
        if (!this._hasActiveApprovedGrant())
            return;

        const manager = Main.timeLimitsManager;
        const estimates = manager?._estimatedTimes;
        const approvedEnd = Math.ceil(this._grantExpiresRealSeconds);
        if (!Number.isSafeInteger(approvedEnd))
            return;

        if (!Array.isArray(estimates) || estimates.length < 4) {
            const now = Math.floor(GLib.get_real_time() / GLib.USEC_PER_SEC);
            manager._estimatedTimes = [true, now, approvedEnd,
                approvedEnd, approvedEnd];
            console.debug(`${LOG_PREFIX} supplied timer estimate from approved grant; ` +
                `approved=${approvedEnd}`);
            return;
        }

        const reportedEnd = Number(estimates[2]);
        if (approvedEnd <= (Number.isFinite(reportedEnd) ? reportedEnd : 0))
            return;

        const overlaidEstimates = estimates.slice();
        overlaidEstimates[2] = approvedEnd;
        manager._estimatedTimes = overlaidEstimates;
        console.debug(`${LOG_PREFIX} overlaid stale timer estimate; ` +
            `reported=${reportedEnd}, approved=${approvedEnd}`);
    }

    _recalculateTimeLimits() {
        const manager = Main.timeLimitsManager;
        if (!manager || manager.state === TimeLimitsState.DISABLED)
            return;

        try {
            manager._updateState();
        } catch (error) {
            console.warn(`${LOG_PREFIX} could not recalculate time limits: ${error.message}`);
        }
    }

    _refreshTimeLimitsEstimate() {
        const refresh = Main.timeLimitsManager?._updateEstimatedTimes;
        if (typeof refresh !== 'function')
            return;

        Promise.resolve(refresh.call(Main.timeLimitsManager)).catch(error =>
            console.warn(`${LOG_PREFIX} timer refresh after grant failed: ${error.message}`));
    }

    _hasActiveApprovedGrant() {
        const beforeMonotonicDeadline = this._grantExpiresMonotonicSeconds >
            GLib.get_monotonic_time() / GLib.USEC_PER_SEC;
        const beforeRealDeadline = this._grantExpiresRealSeconds >
            GLib.get_real_time() / GLib.USEC_PER_SEC;
        if (!beforeMonotonicDeadline || !beforeRealDeadline) {
            this._grantExpiresMonotonicSeconds = 0;
            this._grantExpiresRealSeconds = 0;
            clearApprovedGrant();
            return false;
        }
        return true;
    }

    _setApprovedGrantRemaining(remainingSeconds) {
        this._grantExpiresMonotonicSeconds =
            GLib.get_monotonic_time() / GLib.USEC_PER_SEC + remainingSeconds;
        this._grantExpiresRealSeconds =
            GLib.get_real_time() / GLib.USEC_PER_SEC + remainingSeconds;
        this._scheduleGrantExpiry();
    }

    _scheduleGrantExpiry() {
        if (this._grantExpirySourceId)
            GLib.source_remove(this._grantExpirySourceId);

        const monotonicRemaining = this._grantExpiresMonotonicSeconds -
            GLib.get_monotonic_time() / GLib.USEC_PER_SEC;
        const realRemaining = this._grantExpiresRealSeconds -
            GLib.get_real_time() / GLib.USEC_PER_SEC;
        const remainingSeconds = Math.max(1, Math.ceil(
            Math.min(monotonicRemaining, realRemaining)));
        // Use bounded wakeups so an unusually large custom duration does not
        // overflow GLib's guint interval.
        const delaySeconds = Math.min(remainingSeconds, 60 * 60);
        this._grantExpirySourceId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT, delaySeconds, () => {
                this._grantExpirySourceId = 0;
                if (this._hasActiveApprovedGrant()) {
                    this._scheduleGrantExpiry();
                } else {
                    console.log(`${LOG_PREFIX} approved time expired`);
                    this._refreshTimeLimitsEstimate();
                    this._sync();
                }
                return GLib.SOURCE_REMOVE;
            });
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

    _patchPolkitAgent() {
        const agent = Main.componentManager?._allComponents?.polkitAgent;
        if (!agent) {
            console.warn(`${LOG_PREFIX} polkit agent is not loaded yet; ` +
                'lock-screen approval may be deferred until it appears');
            return false;
        }
        if (agent._requestMoreTimePolkitPatch === this)
            return true;

        const originalInitiate = agent._onInitiate;
        if (typeof originalInitiate !== 'function') {
            console.warn(`${LOG_PREFIX} polkit agent has no _onInitiate method`);
            return false;
        }

        const wrappedInitiate = (
            nativeAgent, actionId, message, iconName, cookie, userNames) => {
            const isLockScreenRequest =
                actionId === SESSION_LIMITS_EXTEND_ACTION ||
                actionId === COMBINED_APPROVAL_ACTION;

            if (Main.sessionMode.isLocked && !isLockScreenRequest) {
                Main.sessionMode.connectObject('updated', () => {
                    Main.sessionMode.disconnectObject(agent);
                    wrappedInitiate(
                        nativeAgent, actionId, message, iconName,
                        cookie, userNames);
                }, agent);
                return;
            }

            originalInitiate.call(
                agent, nativeAgent, actionId, message, iconName,
                cookie, userNames);
        };

        let handlerId = GObject.signal_handler_find(agent, {signalId: 'initiate'});
        while (handlerId) {
            GObject.signal_handler_disconnect(agent, handlerId);
            handlerId = GObject.signal_handler_find(agent, {signalId: 'initiate'});
        }

        this._polkitAgent = agent;
        this._polkitOriginalInitiate = originalInitiate;
        this._polkitInitiateHandlerId = agent.connect('initiate', wrappedInitiate);
        // Track the owner rather than leaving a boolean behind. Extensions can
        // be disabled and re-enabled while the Shell's component survives;
        // a stale marker would otherwise suppress this lock-screen exception
        // and Polkit would defer the prompt until after unlock.
        agent._requestMoreTimePolkitPatch = this;
        console.log(`${LOG_PREFIX} patched polkit agent for lock-screen app approval`);
        return true;
    }
}
