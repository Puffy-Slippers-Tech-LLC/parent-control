import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Pango from 'gi://Pango';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {describeControl, setAutomationId} from './accessibility.js';
import {queryEstimatedTimes, timerErrorCategory} from './timerQuery.js';
import {calculateOwnRemainingTime} from './timeCalculationClient.js';
import {prepareOwnSession} from './sessionPreparationClient.js';
import {RemainingTimeNotifications} from './remainingTimeNotifications.js';
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
const COUNTDOWN_ANIMATION_KEY = 'one-minute-countdown-animation';

function applyTextLanguage(text, language) {
    const attributes = text.get_attributes()?.copy() ?? new Pango.AttrList();
    attributes.change(Pango.attr_language_new(language));
    text.set_attributes(attributes);
}

function retainLabelLanguage(label, language) {
    label._onpcTextLanguage = language;
    if (!label._onpcLanguageStyleId) {
        // St replaces its text attributes on allocation and hover restyling.
        // Run after that default handler, preserving the freshly applied style.
        // Signals belong to this label, including short-lived popup labels;
        // callbacks do not retain the indicator or its disposed menu actors.
        label._onpcLanguageStyleId = label.connect_after('style-changed', actor =>
            applyTextLanguage(actor.get_clutter_text(), actor._onpcTextLanguage));
        label.connect('destroy', actor => {
            actor.disconnect(actor._onpcLanguageStyleId);
            delete actor._onpcLanguageStyleId;
            delete actor._onpcTextLanguage;
        });
    }
    applyTextLanguage(label.get_clutter_text(), language);
}

export const RemainingTimeIndicator = GObject.registerClass(
class RemainingTimeIndicator extends PanelMenu.Button {
    _init(onRequest, approvedGrantRemaining = 0, preview = false,
        appName = 'Oh No! Parent Control', previewMarker = '', logoPath = '', settings = null,
        onError = null, translations = null, onLanguageRefresh = null) {
        super._init(0.0, appName);
        setAutomationId(this, 'child-screen-time-indicator');
        // Drop the default panel menu. A second menu with this source actor
        // steals hover and press from the request popover, including the
        // header overflow control.
        this.setMenu(null);

        this._onRequest = onRequest;
        this._onError = onError;
        this._translations = translations;
        this._onLanguageRefresh = onLanguageRefresh;
        this._appName = appName;
        this._preview = preview;
        this._previewMarker = preview ? previewMarker : '';
        this._settings = settings;
        this._signals = [];
        this._countdownAnimationsEnabled =
            this._settings?.get_boolean(COUNTDOWN_ANIMATION_KEY) ?? false;

        const content = new St.BoxLayout({
            style_class: 'screen-time-remaining-content',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._label = new St.Label({
            style_class: 'screen-time-remaining-label',
            y_align: Clutter.ActorAlign.CENTER,
        });
        setAutomationId(this._label, 'child-remaining-time');

        if (!logoPath)
            throw new Error('could not read app logo');
        this._requestIcon = new St.Icon({
            gicon: new Gio.FileIcon({file: Gio.File.new_for_path(logoPath)}),
            style_class: 'screen-time-request-logo',
            icon_size: 28,
            y_align: Clutter.ActorAlign.CENTER,
            // Keep the rounded-square mark visible while it spins in the
            // final ten seconds; St clips painted overflow by default.
            clip_to_allocation: false,
        });
        this._requestIcon.set_pivot_point(0.5, 0.5);
        this._requestIconSpinning = false;

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
        describeControl(
            this._requestButton,
            'child-request-button',
            appName,
            this._text('PANEL_DESCRIPTION'));
        this._requestButton.connect('clicked', () => this._activateRequest());
        content.add_child(this._requestButton);
        this.add_child(content);
        this._tooltip = new St.Label({
            style_class: 'dash-label screen-time-tooltip',
            reactive: false,
            visible: false,
        });
        setAutomationId(this._tooltip, 'child-request-tooltip');
        Main.layoutManager.addChrome(this._tooltip);
        this._connect(this._requestButton, 'notify::hover', () => this._syncTooltip());
        this._connect(this._requestButton, 'notify::mapped', () => this._syncTooltip());
        this._installContextMenuHandler();
        this.reactive = false;
        this.can_focus = false;
        this.track_hover = false;

        this._timeoutId = 0;
        this._timeoutDeadline = 0;
        this._layoutSyncId = 0;
        this._flashTimeoutId = 0;
        this._contextMenuDestroyId = 0;
        this._contextMenuInputGuard = false;
        this._destroyed = false;
        this._notifications = this._preview ? null : new RemainingTimeNotifications(
            appName, logoPath, translations, onError, () => this._sync());
        this._activeExtensionEnd = approvedGrantRemaining > 0
            ? Main.timeLimitsManager.getCurrentTime() + approvedGrantRemaining
            : 0;
        this._calculatedEnd = this._activeExtensionEnd;
        this._statusLoaded = false;
        this._lockPending = false;
        this._expiryDiagnostic = null;
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
        this._connect(Main.sessionMode, 'updated', () => {
            this._sync();
            if (!Main.sessionMode.isLocked && !Main.sessionMode.isGreeter)
                this._onLanguageRefresh?.();
        });
        this._connect(this.container, 'notify::width', () => this._queueLayoutSync());
        this._connect(this.container, 'notify::height', () => this._queueLayoutSync());
        // Panel extensions may rewrite nested BoxLayout orientations while
        // rebuilding. Reconcile our layout without inspecting their private
        // actor data.
        this._connect(this._buttonContent, 'notify::orientation',
            () => this._queueLayoutSync());
        this._actorDestroyId = this.connect('destroy', () => this._disposeResources());

        if (this._settings) {
            this._connect(
                this._settings,
                `changed::${COUNTDOWN_ANIMATION_KEY}`,
                () => this._syncCountdownAnimationSetting());
        }

        this.refreshLanguage();
        this._queueLayoutSync();
        if (!this._preview)
            this._refreshEstimate();
    }

    setRequestActive(active) {
        if (!this._destroyed) {
            this._requestButton?.set_checked(active);
            if (active)
                this._tooltip.hide();
        }
    }

    _text(key, values = {}) {
        return this._translations?.text(key, values) ?? '';
    }

    refreshLanguage() {
        if (this._destroyed) return;
        const direction = this._translations?.direction === 'rtl'
            ? Clutter.TextDirection.RTL : Clutter.TextDirection.LTR;
        const language = Pango.Language.from_string(this._translations?.language ?? 'en');
        const applyDirection = actor => {
            actor.set_text_direction?.(direction);
            if (actor instanceof St.Label) {
                retainLabelLanguage(actor, language);
            } else if (actor instanceof Clutter.Text) {
                // A private language attribute keeps fallback fonts from splitting
                // combining clusters. Preserve styling without changing Shell's
                // shared Pango context or session language.
                applyTextLanguage(actor, language);
            }
            for (const child of actor.get_children()) applyDirection(child);
        };
        // Only our actors change direction; the host Shell keeps its session locale.
        applyDirection(this);
        applyDirection(this._tooltip);
        if (this._contextMenu) applyDirection(this._contextMenu.actor);
        this._tooltip.set_style(this._translations?.direction === 'rtl'
            ? 'text-align: right;' : 'text-align: left;');
        describeControl(this._requestButton, 'child-request-button', this._appName,
            this._text('PANEL_DESCRIPTION'));
        if (this._countdownAnimationItem) {
            this._countdownAnimationItem.label.text = this._text('COUNTDOWN_ANIMATION');
            describeControl(this._countdownAnimationItem, 'child-countdown-animation-toggle',
                this._text('COUNTDOWN_ANIMATION'), this._text('COUNTDOWN_ANIMATION_DESCRIPTION'));
        }
        this._sync();
    }

    _activateRequest() {
        // Menu closure and focus restoration are not a new request. Keep the
        // guard until a fresh activation press reaches the request button.
        if (this._contextMenuInputGuard || this._contextMenu?.isOpen)
            return;
        this._requestAccess();
    }

    _requestAccess() {
        if (this._destroyed || this._requestButton.checked)
            return;
        this._contextMenu?.close();
        this._tooltip.hide();
        this.setRequestActive(true);
        this._onRequest?.(this);
    }

    _syncTooltip() {
        if (!this._tooltip || this._destroyed)
            return;
        if (!this._requestButton.hover || !this._requestButton.mapped ||
            this._requestButton.checked || this._contextMenu?.isOpen) {
            this._tooltip.hide();
            return;
        }

        const monitor = Main.layoutManager.findMonitorForActor(this._requestButton);
        if (!monitor) {
            this._tooltip.hide();
            return;
        }
        this._tooltip.show();
        const [x, y] = this._requestButton.get_transformed_position();
        const [width, height] = this._requestButton.get_transformed_size();
        const [, tooltipWidth] = this._tooltip.get_preferred_width(-1);
        const [, tooltipHeight] = this._tooltip.get_preferred_height(tooltipWidth);
        const gap = 8;
        let tooltipX = x + (width - tooltipWidth) / 2;
        let tooltipY = y + height + gap;
        if (height > width) {
            tooltipX = x < monitor.x + monitor.width / 2
                ? x + width + gap : x - tooltipWidth - gap;
            tooltipY = y + (height - tooltipHeight) / 2;
        } else if (tooltipY + tooltipHeight > monitor.y + monitor.height) {
            tooltipY = y - tooltipHeight - gap;
        }
        this._tooltip.set_position(
            Math.max(monitor.x, Math.min(tooltipX, monitor.x + monitor.width - tooltipWidth)),
            Math.max(monitor.y, Math.min(tooltipY, monitor.y + monitor.height - tooltipHeight)));
    }

    _installContextMenuHandler() {
        // Keeping a second PopupMenuManager attached to this panel actor while
        // its menu is closed prevents St.Button's normal pointer and keyboard
        // activation. Create the manager only for the lifetime of an opened
        // secondary-click menu.
        this._connect(this._requestButton,
            'button-press-event', (_button, event) => {
                this._tooltip.hide();
                if (event.get_button() !== Clutter.BUTTON_SECONDARY) {
                    this._beginRequestInput();
                    return Clutter.EVENT_PROPAGATE;
                }
                this._releaseForContextMenu();
                this._openContextMenu();
                return Clutter.EVENT_STOP;
            });
        // Capture on the reactive button before its default key handling.
        // Clutter omits non-reactive actors from event delivery, including
        // this passive panel container. A handler there never sees the fresh
        // request press and leaves the context-menu guard permanently armed.
        this._connect(this._requestButton, 'captured-event', (_actor, event) =>
            this._captureRequestKey(event));
        this._connect(this._requestButton, 'popup-menu', () => {
            this._tooltip.hide();
            // The keyboard popup-menu signal has no pointer grab to cancel.
            this._contextMenuInputGuard = true;
            this._openContextMenu();
            return Clutter.EVENT_STOP;
        });
    }

    _captureRequestKey(event) {
        if (event.type() !== Clutter.EventType.KEY_PRESS)
            return Clutter.EVENT_PROPAGATE;
        const keySymbol = event.get_key_symbol();
        // Clutter's captured key-event source is not reliably the actor that
        // owns keyboard focus. Use Shell's public key-focus state to identify
        // the actual recipient. In particular, Space on the countdown toggle
        // must not arm a later synthetic/delayed click on the request button.
        if (global.stage.get_key_focus() !== this._requestButton)
            return Clutter.EVENT_PROPAGATE;
        const opensContextMenu = keySymbol === Clutter.KEY_Menu ||
            (keySymbol === Clutter.KEY_F10 &&
             Boolean(event.get_state() & Clutter.ModifierType.SHIFT_MASK));
        if (opensContextMenu) {
            this._contextMenuInputGuard = true;
            this._tooltip.hide();
            this._openContextMenu();
            return Clutter.EVENT_STOP;
        }
        if ([
            Clutter.KEY_space,
            Clutter.KEY_Return,
            Clutter.KEY_KP_Enter,
            Clutter.KEY_ISO_Enter,
        ].includes(keySymbol))
            this._beginRequestInput();
        return Clutter.EVENT_PROPAGATE;
    }

    _releaseForContextMenu() {
        // Cancel the pointer gesture; only a new request press may disarm
        // the guard, not the menu's closing input or focus restoration.
        this._contextMenuInputGuard = true;
        this._requestButton.fake_release();
    }

    _beginRequestInput() {
        // A new primary pointer press or activation-key press addressed to the
        // source button separates a deliberate request from the tail of the
        // context-menu input. Merely destroying the menu is not such a
        // boundary: its Escape/key release can be dispatched after the menu's
        // accessibility nodes disappear.
        if (!this._contextMenu?.isOpen)
            this._contextMenuInputGuard = false;
    }

    _openContextMenu() {
        this._contextMenuInputGuard = true;
        this._tooltip.hide();
        if (this._contextMenu) {
            this._contextMenu.open();
            return;
        }

        this._contextMenuManager = new PopupMenu.PopupMenuManager(this);
        this._contextMenu = new PopupMenu.PopupMenu(
            this._requestButton, 0.5, St.Side.TOP);
        setAutomationId(this._contextMenu.actor, 'child-countdown-menu');
        this._contextMenu.actor.hide();
        Main.uiGroup.add_child(this._contextMenu.actor);
        this._contextMenuManager.addMenu(this._contextMenu);
        this._contextMenu.connect('open-state-changed', (_menu, open) => {
            logDebug('child.animation-menu', {open});
            if (!open && !this._destroyed && !this._contextMenuDestroyId) {
                this._contextMenuDestroyId = GLib.idle_add(
                    GLib.PRIORITY_DEFAULT_IDLE, () => {
                        this._contextMenuDestroyId = 0;
                        this._destroyContextMenu();
                        return GLib.SOURCE_REMOVE;
                    });
            }
        });

        this._countdownAnimationItem = new PopupMenu.PopupSwitchMenuItem(
            this._text('COUNTDOWN_ANIMATION'), this._countdownAnimationsEnabled);
        describeControl(
            this._countdownAnimationItem,
            'child-countdown-animation-toggle',
            this._text('COUNTDOWN_ANIMATION'),
            this._text('COUNTDOWN_ANIMATION_DESCRIPTION'));
        this._countdownAnimationItem.connect('toggled', (_item, enabled) =>
            this._setCountdownAnimationEnabled(enabled));
        this._contextMenu.addMenuItem(this._countdownAnimationItem);
        this.refreshLanguage();
        this._contextMenu.open();
    }

    _setCountdownAnimationEnabled(enabled) {
        if (this._destroyed || !this._settings?.set_boolean(COUNTDOWN_ANIMATION_KEY, enabled)) {
            logWarning('child.animation-save-failed');
            this._onError?.(new Error('Could not save countdown animation preference'));
            this._syncCountdownAnimationSetting();
            return false;
        }
        this._syncCountdownAnimationSetting();
        logInfo('child.animation', {enabled});
        return true;
    }

    _destroyContextMenu() {
        this._contextMenu?.destroy();
        this._contextMenu = null;
        this._contextMenuManager = null;
        this._countdownAnimationItem = null;
        if (this._destroyed)
            this._contextMenuInputGuard = false;
    }

    _syncCountdownAnimationSetting() {
        if (!this._settings || this._destroyed)
            return;
        const enabled = this._settings.get_boolean(COUNTDOWN_ANIMATION_KEY);
        this._countdownAnimationsEnabled = enabled;
        if (this._countdownAnimationItem?.state !== enabled)
            this._countdownAnimationItem?.setToggleState(enabled);
        if (!enabled)
            this._clearCountdownWarning();
        this._sync();
    }

    _connect(object, signal, callback) {
        this._signals.push([object, object.connect(signal, callback)]);
    }

    destroy() {
        if (this._destroyed)
            return;
        this._disposeResources();
        super.destroy();
    }

    _disposeResources() {
        if (this._destroyed)
            return;
        this._destroyed = true;
        this._notifications?.close();
        this._notifications = null;
        this._onRequest = null;
        this._onLanguageRefresh = null;
        this._translations = null;

        for (const [object, id] of this._signals) {
            if (!id)
                continue;
            try {
                object.disconnect(id);
            } catch (_error) {
                logDebug('child.signal-disconnected');
            }
        }
        this._signals = [];

        this._tooltip?.destroy();
        this._tooltip = null;
        this._clearTimeout();
        if (this._layoutSyncId) {
            GLib.source_remove(this._layoutSyncId);
            this._layoutSyncId = 0;
        }
        this._clearFlash();

        if (this._contextMenuDestroyId) {
            GLib.source_remove(this._contextMenuDestroyId);
            this._contextMenuDestroyId = 0;
        }
        this._destroyContextMenu();
        this._settings = null;

        if (this._timerSignalId)
            Gio.DBus.system.signal_unsubscribe(this._timerSignalId);
        this._timerSignalId = 0;
        this._actorDestroyId = 0;
        logDebug('child.indicator-stopped');
    }

    _clearTimeout() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
        this._timeoutDeadline = 0;
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

    refreshNotifications() {
        this._notifications?.refresh();
    }

    async _refreshEstimate() {
        if (this._destroyed)
            return;
        if (this._refreshPending) {
            this._refreshAgain = true;
            return;
        }

        this._refreshPending = true;
        let stage = 'timer-estimate';
        try {
            const estimates = await queryEstimatedTimes();
            if (this._destroyed)
                return;

            stage = 'allowance-calculation';
            const estimate = estimates[''];
            const currentTime = Main.timeLimitsManager.getCurrentTime();
            const managerLimit = Number(
                Main.timeLimitsManager.dailyLimitTime ?? 0);
            const effectiveAllowance = effectiveAllowanceRemaining(
                estimate, currentTime, managerLimit);
            stage = 'broker-calculation';
            const calculated = await calculateOwnRemainingTime(
                effectiveAllowance);
            if (this._destroyed)
                return;
            const next = nextEstimateState(
                {calculatedEnd: this._calculatedEnd, statusLoaded: this._statusLoaded},
                calculated, currentTime);
            this._calculatedEnd = next.calculatedEnd;
            this._statusLoaded = next.statusLoaded;
            logInfo('child.estimate', {remaining: calculated});
        } catch (error) {
            if (!this._destroyed) {
                // A transient daemon/database failure says nothing about the
                // last successful estimate. Preserve it until a supported
                // D-Bus query supplies a replacement.
                logWarning('child.refresh-failed', {
                    stage, category: timerErrorCategory(error),
                    loaded: this._statusLoaded,
                    locked: Main.sessionMode.isLocked,
                    greeter: Main.sessionMode.isGreeter,
                });
                this._onError?.(error);
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
            logInfo('child.prepared', {reconciled});
        } catch (error) {
            if (!this._destroyed) {
                logWarning('child.prepare-failed');
                this._onError?.(error);
            }
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
        this._notifications?.update(remainingSecs,
            state.visible && this._statusLoaded && manager.dailyLimitEnabled);
        // Ubuntu uses a primary session mode named "ubuntu", while upstream
        // GNOME commonly uses "user".  Test the session semantics instead of
        // assuming the distribution-specific primary mode name.
        const visible = state.visible;

        // Login-time expiry can overlap Shell's own lock transition. Keep a
        // small, deduplicated state witness; no account or session identifiers
        // are needed to distinguish an unloaded limit from an existing lock.
        if (!this._preview && remainingSecs <= 0) {
            const diagnostic = `loaded=${this._statusLoaded} ` +
                `limitEnabled=${manager.dailyLimitEnabled} ` +
                `locked=${Main.sessionMode.isLocked} ` +
                `greeter=${Main.sessionMode.isGreeter} pending=${this._lockPending}`;
            if (diagnostic !== this._expiryDiagnostic) {
                this._expiryDiagnostic = diagnostic;
                logInfo('child.expiry', {
                    loaded: this._statusLoaded, limit_enabled: manager.dailyLimitEnabled,
                    locked: Main.sessionMode.isLocked, greeter: Main.sessionMode.isGreeter,
                    pending: this._lockPending,
                });
            }
        } else {
            this._expiryDiagnostic = null;
        }

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
        this._schedule(this._notifications?.nextDelay(remainingSecs, state.nextUpdateSeconds) ??
            state.nextUpdateSeconds);
    }

    _lockSession() {
        if (this._destroyed || this._lockPending)
            return;

        this._lockPending = true;
        logInfo('child.lock-requested');
        Gio.DBus.session.call(
            SCREEN_SAVER_NAME, SCREEN_SAVER_PATH, SCREEN_SAVER_INTERFACE, 'Lock',
            null, null, Gio.DBusCallFlags.NONE, -1, null,
            (connection, result) => {
                try {
                    connection.call_finish(result);
                    logInfo('child.locked');
                } catch (error) {
                    if (!this._destroyed) {
                        logWarning('child.lock-failed');
                        this._onError?.(error);
                    }
                } finally {
                    this._lockPending = false;
                }
            });
    }

    _setShown(shown) {
        if (shown && !this.container.visible)
            logInfo('child.indicator-shown');
        if (!shown) {
            this._tooltip.hide();
            this._contextMenu?.close();
        }
        this.container.visible = shown;
    }

    _compactLabel() {
        const [width, height] = this.container.get_transformed_size();
        return height > width;
    }

    _syncOrientation() {
        const vertical = this._compactLabel();
        const orientation = vertical
            ? Clutter.Orientation.VERTICAL
            : Clutter.Orientation.HORIZONTAL;
        // Another panel extension can mutate the BoxLayout after our cached
        // orientation was set, so always compare against the actor too.
        if (this._buttonContent.orientation !== orientation)
            this._buttonContent.orientation = orientation;

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
        if (remainingSecs >= 60 || !this._countdownAnimationsEnabled)
            this._clearCountdownWarning();

        const compact = this._syncOrientation();
        this._label.text = formatRemainingTime(remainingSecs, compact);
        if (compact && remainingSecs > 60) {
            const minutes = Math.floor(remainingSecs / 60);
            this._label.text = this._text(minutes >= 60 ? 'COMPACT_HOURS' : 'COMPACT_MINUTES',
                {count: minutes >= 60 ? Math.floor(minutes / 60) : minutes});
        }
        const time = remainingSecs > 60
            ? formatRemainingTime(remainingSecs, false)
            : this._text('SECOND_COUNT', {count: remainingSecs});
        this._tooltip.text = this._text('PANEL_TOOLTIP', {time});
        if (this._tooltip.visible)
            this._syncTooltip();

        if (remainingSecs < 60 && this._countdownAnimationsEnabled) {
            this._label.add_style_pseudo_class('countdown');
            this._flashContent();
        }

        this._updateRequestIcon(remainingSecs);
        const marker = this._previewMarker ? `, ${this._previewMarker}` : '';
        this._requestButton.accessible_name =
            this._text('PANEL_REQUEST_TIME', {time: this._label.text}) + marker;
    }

    _updateRequestIcon(remainingSecs) {
        if (!this._countdownAnimationsEnabled || remainingSecs > 10) {
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
        const deadline = GLib.get_monotonic_time() + delay * 1_000_000;
        // Layout notifications and completed estimate queries also call _sync.
        // They must not postpone a pending tick, especially while the final
        // minute's flashing style repeatedly changes the actor allocation.
        if (this._timeoutId && this._timeoutDeadline <= deadline)
            return;
        this._clearTimeout();

        this._timeoutDeadline = deadline;
        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, delay, () => {
            this._timeoutId = 0;
            this._timeoutDeadline = 0;
            if (!this._preview)
                this._refreshEstimate();
            this._sync();
            return GLib.SOURCE_REMOVE;
        });
    }
});
