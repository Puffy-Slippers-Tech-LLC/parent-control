import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const SURFACE_ID = 'child-screen-time-indicator';
const APPLICATION_ID = 'com.puffyslippers.OhNoParentControl.ChildUI';
const COUNTDOWN_ANIMATION_KEY = 'one-minute-countdown-animation';

/** GNOME mapping for the desktop-neutral Application UI transport.
 *
 * An adapter publishes listSurfaces(), elements(surfaceId), and close(). Element
 * descriptors contain stable id/type, current visible/enabled flags, and finite
 * UI operation callbacks. This adapter alone interprets Shell session/actors.
 */
export class GnomeApplicationUiAdapter {
    constructor(indicator) {
        this._indicator = indicator;
    }

    _state() {
        const indicator = this._indicator;
        if (!indicator || indicator._destroyed)
            return {available: false, visible: false, enabled: false};
        // Focus, allocation, clipping, hover and popup opening are not guards.
        let visible = !Main.sessionMode.isLocked && !Main.sessionMode.isGreeter &&
            indicator.container.visible;
        for (let actor = indicator._requestButton; visible && actor; actor = actor.get_parent())
            visible = actor.visible;
        return {available: true, visible,
            enabled: visible && indicator._requestButton.reactive &&
                !indicator._requestButton.checked};
    }

    listSurfaces() {
        const state = this._state();
        if (!state.available) return [];
        return [{id: SURFACE_ID, application_id: APPLICATION_ID,
            type: 'child-panel', visible: state.visible, enabled: state.enabled,
            modal: false, parent_id: null}];
    }

    elements(surfaceId) {
        const state = this._state();
        if (surfaceId !== SURFACE_ID || !state.available) return null;
        const indicator = this._indicator;
        const element = (id, type, operations, enabled = state.enabled) =>
            ({id, type, visible: state.visible, enabled, ...operations});
        return [
            element(SURFACE_ID, 'child-panel', {}),
            element('child-request-button', 'button', {
                getText: () => indicator._requestButton.accessible_name,
                activate: () => indicator._requestAccess(),
            }),
            element('child-remaining-time', 'label', {
                getText: () => indicator._label.text,
                getValue: () => this._remainingSeconds(),
            }),
            element('child-request-tooltip', 'label', {
                getText: () => indicator._tooltip.text,
            }),
            element('child-countdown-menu', 'menu', {
                activate: () => indicator._openContextMenu(),
            }),
            // The logical preference outlives the native transient popup.
            element('child-countdown-animation-toggle', 'boolean', {
                valueType: 'boolean',
                getText: () => indicator._text('COUNTDOWN_ANIMATION'),
                getValue: () => indicator._countdownAnimationsEnabled,
                setValue: enabled => indicator._setCountdownAnimationEnabled(enabled),
                activate: () => {
                    if (!indicator._setCountdownAnimationEnabled(!indicator._countdownAnimationsEnabled))
                        throw new Error('Could not save countdown animation preference');
                },
            }, state.enabled && Boolean(indicator._settings?.is_writable(COUNTDOWN_ANIMATION_KEY))),
        ];
    }

    _remainingSeconds() {
        const remaining = this._indicator._remainingSeconds(Main.timeLimitsManager.getCurrentTime());
        if (!Number.isSafeInteger(remaining))
            throw new Error('Remaining time is unavailable');
        // A past deadline represents zero remaining time, including hidden reads.
        return Math.max(0, remaining);
    }

    close() {
        this._indicator = null;
    }
}
