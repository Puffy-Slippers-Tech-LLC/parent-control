import assert from 'node:assert/strict';
import test from 'node:test';
import {createIndicator} from './support/indicator.mjs';

import {
    busyRetryDelay,
    canOpenRequest,
    displayState,
    effectiveAllowanceRemaining,
    formatRemainingTime,
    nextEstimateState,
    remainingSeconds,
    requestCompletionState,
    shouldPrepareSession,
} from '../../child/indicatorLogic.mjs';

test('layout refreshes cannot postpone the countdown tick', () => {
    // Execute the production scheduler with a deterministic GLib clock. No
    // Shell session or system-bus connection is created by this harness.
    let now = 0;
    let nextId = 0;
    const timers = new Map();
    const indicator = createIndicator({
        GLib: {
            PRIORITY_DEFAULT: 0,
            SOURCE_REMOVE: false,
            get_monotonic_time: () => now,
            source_remove: id => timers.delete(id),
            timeout_add_seconds: (_priority, delay, callback) => {
                timers.set(++nextId, {deadline: now + delay * 1_000_000, callback});
                return nextId;
            },
        },
    });
    Object.assign(indicator, {_timeoutId: 0, _timeoutDeadline: 0, _preview: true});
    let remaining = 56;
    indicator._sync = () => {
        remaining = 56 - Math.floor(now / 1_000_000);
        if (remaining > 0)
            indicator._schedule(1);
    };
    indicator._sync();
    for (now = 100_000; now <= 56_000_000; now += 100_000) {
        indicator._sync(); // Frequent layout / estimate notifications.
        for (const [id, timer] of [...timers]) {
            if (timer.deadline <= now) {
                timers.delete(id);
                timer.callback();
            }
        }
    }
    assert.equal(remaining, 0);
    assert.equal(nextId, 56, 'one tick per second survives repeated refreshes');
    assert.equal(timers.size, 0);

    indicator._schedule(60);
    indicator._schedule(1);
    assert.equal(timers.size, 1, 'an earlier deadline replaces the pending timer');
    assert.equal([...timers.values()][0].deadline, now + 1_000_000);
    indicator._clearTimeout();
    assert.equal(timers.size, 0);
    assert.equal(indicator._timeoutDeadline, 0);
});

test('formats minute, final-minute, zero, and multi-day remaining time', () => {
    assert.equal(formatRemainingTime(3661, false), '01:01');
    assert.equal(formatRemainingTime(59, false), '59');
    assert.equal(formatRemainingTime(0, true), '0');
    assert.equal(formatRemainingTime(49 * 60 * 60, false), '49:00');
});

test('tooltip follows hover, stays on the monitor, and hides during interaction', () => {
    const indicator = createIndicator({
        Main: {layoutManager: {
            findMonitorForActor: () => ({x: 0, y: 0, width: 800, height: 600}),
        }},
    });
    let position;
    Object.assign(indicator, {
        _requestButton: {
            hover: true, mapped: true, checked: false,
            get_transformed_position: () => [750, 570],
            get_transformed_size: () => [50, 30],
        },
        _tooltip: {
            visible: false,
            show() { this.visible = true; },
            hide() { this.visible = false; },
            get_preferred_width: () => [300, 300],
            get_preferred_height: () => [80, 80],
            set_position: (x, y) => { position = [x, y]; },
        },
    });
    indicator._syncTooltip();
    assert.equal(indicator._tooltip.visible, true);
    assert.deepEqual(position, [500, 482]);
    for (const state of [
        {hover: false}, {mapped: false}, {checked: true},
    ]) {
        Object.assign(indicator._requestButton, {hover: true, mapped: true, checked: false}, state);
        indicator._syncTooltip();
        assert.equal(indicator._tooltip.visible, false);
    }
    Object.assign(indicator._requestButton, {hover: true, mapped: true, checked: false});
    indicator._contextMenu = {isOpen: true};
    indicator._syncTooltip();
    assert.equal(indicator._tooltip.visible, false);
});

test('countdown preference interaction cannot activate the request overlay', () => {
    const indicator = createIndicator();
    let active = false;
    let requests = 0;
    let closes = 0;
    Object.assign(indicator, {
        _tooltip: {hide() {}},
        _contextMenu: {
            isOpen: true,
            close: () => closes++,
        },
        _contextMenuInputGuard: true,
        setRequestActive: value => { active = value; },
        _onRequest: () => requests++,
    });

    indicator._activateRequest();
    assert.deepEqual({active, requests, closes}, {active: false, requests: 0, closes: 0});

    indicator._contextMenu.isOpen = false;
    indicator._activateRequest();
    assert.deepEqual({active, requests, closes}, {active: false, requests: 0, closes: 0});

    indicator._contextMenu = null;
    indicator._beginRequestInput();
    indicator._activateRequest();
    assert.deepEqual({active, requests, closes}, {active: true, requests: 1, closes: 0});
});

test('context-menu input cannot activate the request overlay', () => {
    const buttonHandlers = new Map();
    const indicatorHandlers = new Map();
    const actions = [];
    let focusedActor = null;
    let active = false;
    let requests = 0;
    const indicator = createIndicator({
        Clutter: {
            BUTTON_SECONDARY: 3,
            EVENT_PROPAGATE: 'propagate',
            EVENT_STOP: 'stop',
            KEY_Escape: 9,
            KEY_space: 65,
            KEY_Return: 36,
            KEY_KP_Enter: 104,
            KEY_ISO_Enter: 108,
            KEY_Menu: 135,
            KEY_F10: 76,
            EventType: {KEY_PRESS: 'key-press', BUTTON_PRESS: 'button-press'},
            ModifierType: {SHIFT_MASK: 1},
        },
        global: {stage: {get_key_focus: () => focusedActor}},
    });
    Object.assign(indicator, {
        _signals: [],
        reactive: false,
        connect(signal, callback) {
            indicatorHandlers.set(signal, callback);
            return indicatorHandlers.size;
        },
        _tooltip: {hide: () => actions.push('hide')},
        _requestButton: {
            reactive: true,
            connect(signal, callback) {
                buttonHandlers.set(signal, callback);
                return buttonHandlers.size;
            },
            fake_release() {
                actions.push('release');
                indicator._activateRequest();
            },
        },
        _contextMenuInputGuard: false,
        setRequestActive: value => { active = value; },
        _onRequest: () => requests++,
        _openContextMenu: () => actions.push('open'),
    });
    focusedActor = indicator._requestButton;

    indicator._installContextMenuHandler();
    const eventSource = {};
    const keyEvent = (symbol, state = 0) => ({
        type: () => 'key-press',
        get_key_symbol: () => symbol,
        get_state: () => state,
        // Captured key events need not report the actor that owns key focus.
        get_source: () => eventSource,
    });
    // Clutter omits non-reactive ancestors from both phases of key delivery.
    // Dispatch through the real signal connections, not the handler method:
    // wiring capture to the passive panel container must fail this regression.
    const capture = event => {
        for (const [actor, handlers] of [
            [indicator, indicatorHandlers],
            [indicator._requestButton, buttonHandlers],
        ]) {
            if (actor.reactive &&
                handlers.get('captured-event')?.(actor, event) === 'stop')
                return 'stop';
        }
        return 'propagate';
    };
    assert.equal(capture(keyEvent(135)), 'stop');
    assert.deepEqual(actions, ['hide', 'open']);
    indicator._activateRequest();
    assert.deepEqual({active, requests}, {active: false, requests: 0});

    actions.length = 0;
    assert.equal(capture(keyEvent(76, 1)), 'stop');
    assert.deepEqual(actions, ['hide', 'open']);
    indicator._activateRequest();
    assert.deepEqual({active, requests}, {active: false, requests: 0});

    actions.length = 0;
    assert.equal(buttonHandlers.get('popup-menu')(), 'stop');
    assert.deepEqual(actions, ['hide', 'open']);
    assert.deepEqual({active, requests}, {active: false, requests: 0});

    // The keyboard route must not manufacture a pointer release; the guard
    // still rejects any source-button click propagated by menu interaction.
    indicator._activateRequest();
    assert.deepEqual({active, requests}, {active: false, requests: 0});

    indicator._contextMenuInputGuard = false;
    actions.length = 0;
    assert.equal(buttonHandlers.get('button-press-event')(
        null, {get_button: () => 3}), 'stop');
    assert.deepEqual(actions, ['hide', 'release', 'open']);
    assert.deepEqual({active, requests}, {active: false, requests: 0});

    indicator._contextMenu = {destroy: () => actions.push('destroy')};
    indicator._destroyContextMenu();
    // Menu destruction is not an input boundary. A delayed click from the
    // closing key/release must remain suppressed regardless of main-loop
    // scheduling.
    indicator._activateRequest();
    assert.deepEqual({active, requests}, {active: false, requests: 0});

    // Captured activation keys from the popup item are not request input,
    // including when their delivery races with menu teardown. They must not
    // clear the guard and authorize a delayed click on the source button.
    const popupItem = {};
    focusedActor = popupItem;
    assert.equal(capture(keyEvent(65)), 'propagate');
    indicator._activateRequest();
    assert.deepEqual({active, requests}, {active: false, requests: 0});

    // Escape closes the menu and can then bubble to its source button. It is
    // not a new request input and must not disarm the context-menu guard.
    assert.equal(capture(keyEvent(9)), 'propagate');
    indicator._activateRequest();
    assert.deepEqual({active, requests}, {active: false, requests: 0});

    focusedActor = indicator._requestButton;
    assert.equal(capture(keyEvent(65)), 'propagate');
    indicator._activateRequest();
    assert.deepEqual({active, requests}, {active: true, requests: 1});

    assert.equal(capture({type: () => 'button-press'}), 'propagate');

    indicator._contextMenuInputGuard = true;
    assert.equal(buttonHandlers.get('button-press-event')(
        null, {get_button: () => 1}), 'propagate');
    indicator._activateRequest();
    assert.deepEqual({active, requests}, {active: true, requests: 2});
});

test('countdown animation setting gates the final-minute effects', () => {
    const indicator = createIndicator({
        Clutter: {AnimationMode: {LINEAR: 'linear'}},
        formatRemainingTime,
    });
    let clears = 0;
    let flashes = 0;
    let countdownStyles = 0;
    let spins = 0;
    let stops = 0;
    Object.assign(indicator, {
        _countdownAnimationsEnabled: false,
        _previewMarker: '',
        _requestIconSpinning: false,
        _buttonContent: {},
        _label: {
            text: '',
            add_style_pseudo_class: () => countdownStyles++,
        },
        _requestButton: {},
        _tooltip: {text: '', visible: false},
        _requestIcon: {ease: () => spins++},
        _clearCountdownWarning: () => clears++,
        _stopRequestIconSpin: () => stops++,
        _syncOrientation: () => false,
        _flashContent: () => flashes++,
    });

    indicator._updateLabel(9);
    assert.deepEqual(
        {clears, flashes, countdownStyles, spins, stops},
        {clears: 1, flashes: 0, countdownStyles: 0, spins: 0, stops: 1});

    indicator._countdownAnimationsEnabled = true;
    indicator._updateLabel(9);
    assert.deepEqual(
        {clears, flashes, countdownStyles, spins, stops},
        {clears: 1, flashes: 1, countdownStyles: 1, spins: 1, stops: 1});
});

test('display state changes cadence at the final minute and locks only at zero', () => {
    assert.deepEqual(displayState({calculatedEnd: 160, currentTime: 100, locked: false, greeter: false}), {
        remaining: 60, visible: true, shouldLock: false, countdown: false,
        spinRequestIcon: false, nextUpdateSeconds: 1,
    });
    assert.deepEqual(displayState({calculatedEnd: 159, currentTime: 100, locked: false, greeter: false}), {
        remaining: 59, visible: true, shouldLock: false, countdown: true,
        spinRequestIcon: false, nextUpdateSeconds: 1,
    });
    assert.equal(displayState({calculatedEnd: 100, currentTime: 100, locked: false, greeter: false}).shouldLock, true);
    assert.equal(displayState({calculatedEnd: 100, currentTime: 100, locked: true, greeter: false}).shouldLock, false);
});

test('calculates allowance and preserves a verified estimate on a transient failure', () => {
    assert.equal(effectiveAllowanceRemaining(['', 0, 160], 100, 140), 60);
    assert.equal(effectiveAllowanceRemaining(null, 100, 90), 0);
    const previous = {calculatedEnd: 900, statusLoaded: true};
    assert.deepEqual(nextEstimateState(previous, Number.NaN, 100), previous);
    assert.deepEqual(nextEstimateState(previous, 45, 100), {calculatedEnd: 145, statusLoaded: true});
});

test('classifies bounded busy retries and prevents duplicate request overlays', () => {
    assert.equal(busyRetryDelay('org.example.Error.Busy', 0), 100);
    assert.equal(busyRetryDelay('org.example.Error.Busy', 5), undefined);
    assert.equal(busyRetryDelay('org.example.Error.Failed', 0), undefined);
    assert.equal(canOpenRequest(false, false), true);
    assert.equal(canOpenRequest(true, false), false);
    assert.equal(canOpenRequest(false, true), false);
    assert.deepEqual(requestCompletionState(), {requestActive: false, refreshEstimate: true});
    assert.equal(remainingSeconds(100.1, 100), 1);
});

test('prepares a session only once it is usable', () => {
    const usable = {preview: false, destroyed: false, pending: false, prepared: false, locked: false, greeter: false};
    assert.equal(shouldPrepareSession(usable), true);
    assert.equal(shouldPrepareSession({...usable, locked: true}), false);
    assert.equal(shouldPrepareSession({...usable, prepared: true}), false);
});
