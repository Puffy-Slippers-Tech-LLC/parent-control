import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {createIndicator} from './support/indicator.mjs';
import {diagnosticEnvelope} from '../../child/diagnosticEvents.mjs';

const diagnosticCatalog = JSON.parse(readFileSync(new URL(
    '../../common/oh_no_parent_control_ui/diagnostic_catalog.json', import.meta.url)));

import {
    busyRetryDelay,
    canOpenRequest,
    displayState,
    formatRemainingTime,
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
    Object.assign(indicator, {_timeoutId: 0, _timeoutDeadline: 0, _preview: false,
        _refreshEstimate() { assert.fail('display ticks must not read timing sources'); }});
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

test('tooltip clock includes seconds through minute and hour boundaries', () => {
    for (const [seconds, expected] of [
        [3743, '01:02:23'], [3720, '01:02:00'], [3719, '01:01:59'],
        [3600, '01:00:00'], [3599, '00:59:59'], [60, '00:01:00'],
        [59, '00:00:59'], [0, '00:00:00'], [-1, '00:00:00'],
        [49 * 3600, '49:00:00'],
    ]) {
        assert.equal(formatRemainingTime(seconds, false, true), expected);
    }
});

test('dock tooltip counts down each second while the minute label stays stable', () => {
    const indicator = createIndicator({formatRemainingTime});
    Object.assign(indicator, {
        _label: {}, _tooltip: {visible: false}, _requestButton: {},
        _clearCountdownWarning() {}, _syncOrientation: () => false,
        _updateRequestIcon() {},
        _text: (key, values) => `${key}:${values.time}`,
    });
    for (const currentTime of [100, 101, 102]) {
        const state = displayState({calculatedEnd: 3843, currentTime,
            locked: false, greeter: false});
        assert.equal(state.nextUpdateSeconds, 1);
        indicator._updateLabel(state.remaining);
        assert.equal(indicator._label.text, '01:02');
        assert.equal(indicator._tooltip.text, `PANEL_TOOLTIP:01:02:${123 - currentTime}`);
    }
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
        _requestButton: {checked: false},
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

test('ordinary panel activation requests the overlay without preferences', () => {
    const indicator = createIndicator();
    const requests = [];
    Object.assign(indicator, {
        _requestButton: {checked: false},
        _tooltip: {hide() {}},
        setRequestActive: value => { indicator._requestButton.checked = value; },
        _onRequest: preferences => requests.push(preferences),
    });

    indicator._activateRequest();
    assert.deepEqual(requests, [false]);
    indicator._activateRequest();
    assert.deepEqual(requests, [false], 'an active overlay is not launched twice');
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

test('language refresh relabels the hidden dock tooltip before its next hover', () => {
    const descriptions = [];
    class Attributes {
        constructor(values = {}) { this.values = {...values}; }
        copy() { return new Attributes(this.values); }
        change(attribute) { this.values[attribute.type] = attribute.value; }
    }
    class Text {
        constructor(attributes = null) { this.attributes = attributes; }
        get_children() { return []; }
        get_attributes() { return this.attributes; }
        set_attributes(attributes) { this.attributes = attributes; }
        set_text_direction(direction) { this.direction = direction; }
    }
    const originalAttributes = new Attributes({weight: 'bold', language: 'en'});
    const menuText = new Text(originalAttributes);
    const tooltipText = new Text();
    class Label {
        constructor(text) { this.textActor = text; this.handlers = new Map(); }
        get_children() { return [this.textActor]; }
        get_clutter_text() { return this.textActor; }
        connect_after(signal, callback) { return this.connect(signal, callback); }
        connect(signal, callback) {
            const id = this.handlers.size + 1;
            this.handlers.set(id, {signal, callback});
            return id;
        }
        disconnect(id) { this.handlers.delete(id); }
        emit(signal) {
            for (const handler of [...this.handlers.values()])
                if (handler.signal === signal) handler.callback(this);
        }
    }
    const menuLabel = new Label(menuText);
    const indicator = createIndicator({
        St: {Label},
        Clutter: {Text, TextDirection: {RTL: 'rtl', LTR: 'ltr'}},
        Pango: {Language: {from_string: value => value}, AttrList: Attributes,
            attr_language_new: value => ({type: 'language', value})},
        formatRemainingTime,
        describeControl: (_actor, _id, _name, description) => descriptions.push(description),
    });
    let language = 'en';
    Object.assign(indicator, {
        _translations: {language, text: (key, values) => `${language}:${key}:${values.time ?? ''}`},
        get_children: () => [indicator._requestButton],
        _requestButton: {get_children: () => [], set_text_direction(value) { this.direction = value; }},
        _label: {},
        _tooltip: {visible: false, text: '', get_children: () => [tooltipText],
            set_text_direction(value) { this.direction = value; },
            set_style(value) { this.style = value; }},
        _previewMarker: '',
        _clearCountdownWarning() {},
        _syncOrientation: () => false,
        _updateRequestIcon() {},
        _sync() { this._updateLabel(2700); },
        _contextMenu: {actor: {get_children: () => [menuLabel]}},
    });
    indicator.refreshLanguage();
    assert.equal(indicator._tooltip.text, 'en:PANEL_TOOLTIP:00:45:00');
    language = 'de';
    indicator.refreshLanguage();
    assert.equal(indicator._tooltip.text, 'de:PANEL_TOOLTIP:00:45:00');
    assert.equal(indicator._requestButton.accessible_name, 'de:PANEL_REQUEST_TIME:00:45');
    assert.equal(descriptions.at(-1), 'de:PANEL_DESCRIPTION:');
    assert.equal(indicator._tooltip.visible, false);
    indicator._translations.direction = 'rtl';
    language = 'ar';
    indicator._translations.language = language;
    indicator.refreshLanguage();
    assert.equal(indicator._tooltip.direction, 'rtl');
    assert.equal(indicator._tooltip.style, 'text-align: right;');
    assert.equal(indicator._requestButton.direction, 'rtl');
    assert.equal(indicator._tooltip.text, 'ar:PANEL_TOOLTIP:00:45:00');
    assert.deepEqual(menuText.attributes.values, {weight: 'bold', language: 'ar'});
    assert.equal(tooltipText.attributes.values.language, 'ar');
    assert.equal(originalAttributes.values.language, 'en');
    assert.notEqual(menuText.attributes, originalAttributes);
    indicator._translations.direction = 'ltr';
    indicator._translations.language = 'ta';
    indicator.refreshLanguage();
    assert.equal(indicator._tooltip.direction, 'ltr');
    assert.equal(indicator._tooltip.style, 'text-align: left;');
    assert.deepEqual(menuText.attributes.values, {weight: 'bold', language: 'ta'});
    // Shell replaces the complete attribute list when a new menu is allocated
    // or hovered. Retain the current language after the new CSS style arrives.
    menuText.attributes = new Attributes({foreground: 'white', underline: true});
    menuLabel.emit('style-changed');
    assert.deepEqual(menuText.attributes.values,
        {foreground: 'white', underline: true, language: 'ta'});
    indicator._translations.language = 'en';
    indicator.refreshLanguage();
    assert.deepEqual(menuText.attributes.values,
        {foreground: 'white', underline: true, language: 'en'});
    assert.equal(menuLabel.handlers.size, 2); // One pair across every refresh.
    menuLabel.emit('destroy');
    assert.equal([...menuLabel.handlers.values()].some(h => h.signal === 'style-changed'), false);
    assert.equal(menuLabel._onpcTextLanguage, undefined);
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

test('countdown hides on lock and greeter and resumes only with time remaining', () => {
    const sessionMode = {isLocked: false, isGreeter: false};
    let now = 100;
    let shown;
    let locks = 0;
    let displayed;
    let scheduled;
    const indicator = createIndicator({
        displayState,
        GLib: {get_monotonic_time: () => now * 1_000_000},
        Main: {sessionMode, timeLimitsManager: {
            getCurrentTime: () => now, dailyLimitEnabled: true,
        }},
        logInfo() {},
    });
    Object.assign(indicator, {
        _preview: false, _deadlineUsec: 220_000_000, _statusLoaded: true,
        _refreshSerial: 0, _deadlineSerial: 0,
        _recordCountdownState() {}, _prepareSession() {},
        _clearTimeout() { scheduled = null; }, _stopRequestIconSpin() {},
        _setShown(value) { shown = value; },
        _updateLabel(value) { displayed = value; },
        _schedule(value) { scheduled = value; },
        _lockSession() { locks++; },
    });
    indicator._sync();
    assert.equal(shown, true);
    assert.equal(displayed, 120);
    for (const mode of ['isLocked', 'isGreeter']) {
        sessionMode[mode] = true;
        indicator._sessionPrepared = true;
        indicator._sync();
        assert.equal(shown, false, mode);
        assert.equal(scheduled, null, mode);
        assert.equal(indicator._sessionPrepared, false, mode);
        assert.equal(locks, 0, 'an unavailable desktop must not request another lock');
        now += 10;
        sessionMode[mode] = false;
        indicator._sync();
        assert.equal(shown, true, mode);
        assert.equal(displayed, 220 - now, 'return preserves the original countdown deadline');
        assert.equal(scheduled, 1);
    }
    now = 220;
    sessionMode.isLocked = true;
    indicator._sync();
    assert.equal(shown, false);
    assert.equal(locks, 0);
    sessionMode.isLocked = false;
    indicator._sync();
    assert.equal(shown, false, 'return cannot restore an expired countdown');
    assert.equal(locks, 1);
});

test('panel API becomes unavailable at lock or greeter before actors are hidden', () => {
    // Isolated implementation check of the production adapter. This does not
    // create or claim a public locked/GDM preview or an installed session.
    const sessionMode = {isLocked: false, isGreeter: false};
    const manager = {dailyLimitEnabled: true, dailyLimitTime: 140,
        getCurrentTime: () => 100};
    const context = vm.createContext({Main: {sessionMode, timeLimitsManager: manager},
        GLib: {get_monotonic_time: () => 5_000_000}});
    const source = readFileSync(
        new URL('../../child/gnomeApplicationUiAdapter.js', import.meta.url), 'utf8')
        .replace(/^import[^\n]+\n/gm, '')
        .replace('export class GnomeApplicationUiAdapter',
            'globalThis.GnomeApplicationUiAdapter = class GnomeApplicationUiAdapter');
    vm.runInContext(source, context, {filename: 'gnomeApplicationUiAdapter.js'});
    const indicator = {
        container: {visible: true},
        _settings: {is_writable: () => true},
        _requestButton: {visible: true, reactive: true, checked: false,
            get_parent: () => indicator.container, get_accessible: () => ({get_description: () => ''})},
    };
    const adapter = new context.GnomeApplicationUiAdapter(indicator);
    const assertAvailability = available => {
        const [surface] = adapter.listSurfaces();
        assert.equal(surface.visible, available);
        assert.equal(surface.enabled, available);
        const controls = adapter.elements(surface.id);
        assert.equal(controls.length, 6);
        assert.ok(controls.every(control => control.visible === available));
        assert.ok(controls.every(control => control.enabled === available));
    };
    assertAvailability(true);
    for (const mode of ['isLocked', 'isGreeter']) {
        sessionMode[mode] = true;
        assertAvailability(false);
        // Actor visibility is deliberately stale at the session transition.
        assert.equal(indicator.container.visible, true);
        sessionMode[mode] = false;
        assertAvailability(true);
    }
    assert.equal(adapter.nativeAllowanceDeadline(), 45_000_000);
    manager.dailyLimitTime = 90;
    assert.equal(adapter.nativeAllowanceDeadline(), 5_000_000, 'expired native time remains zero');
    for (const unavailable of [0, Number.NaN, Number.POSITIVE_INFINITY]) {
        manager.dailyLimitTime = unavailable;
        assert.throws(() => adapter.nativeAllowanceDeadline(), /unavailable/);
    }
    manager.dailyLimitTime = 140;
    manager.dailyLimitEnabled = false;
    assert.throws(() => adapter.nativeAllowanceDeadline(), /unavailable/);
    manager.dailyLimitEnabled = true;
    adapter.close();
    assert.throws(() => adapter.nativeAllowanceDeadline(), /unavailable/);
});

test('locking waits for the latest balance through coalesced reads and refresh failure', async () => {
    let now = 100;
    let locks = 0;
    let shown;
    let displayed;
    const replies = [], reports = [], retries = new Map();
    let nextId = 0;
    const indicator = createIndicator({
        displayState, remainingSeconds,
        Main: {sessionMode: {isLocked: false, isGreeter: false}, timeLimitsManager: {
            getCurrentTime: () => now, dailyLimitEnabled: true, dailyLimitTime: 700,
        }},
        GLib: {get_monotonic_time: () => now * 1_000_000,
            PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
            timeout_add(_priority, _delay, callback) {
                retries.set(++nextId, callback);
                return nextId;
            }, source_remove: id => retries.delete(id)},
        queryEstimatedTimes: async () => ({'': [false, 0, 700]}),
        calculateOwnDeadline: () => new Promise((resolve, reject) => replies.push({resolve, reject})),
        timerErrorCategory: () => 'other', logInfo() {}, logWarning() {},
    });
    Object.assign(indicator, {
        _preview: false, _deadlineUsec: 0, _statusLoaded: true,
        _refreshSerial: 0, _deadlineSerial: 0,
        _recordCountdownState() {}, _recordCountdownRefresh() {}, _prepareSession() {},
        _clearTimeout() {}, _stopRequestIconSpin() {}, _schedule() {},
        _setShown(value) { shown = value; },
        _updateLabel(value) { displayed = value; },
        _lockSession() { locks++; }, _onError: error => reports.push(error),
    });

    const pending = indicator._refreshEstimate();
    await new Promise(setImmediate);
    indicator._sync(); // Native state changed while the old cached balance is zero.
    assert.equal(locks, 0, 'an old zero cannot lock while its replacement is pending');
    indicator.refreshEstimate(); // A newer change supersedes the pending read.
    replies.shift().resolve(100_000_000);
    await pending;
    assert.equal(locks, 0, 'the gap before a coalesced replacement cannot lock');
    await new Promise(setImmediate);
    indicator._sync();
    assert.equal(locks, 0);
    replies.shift().resolve(160_000_000);
    await new Promise(setImmediate);
    assert.equal(locks, 0, 'fresh usable time preserves the desktop');
    assert.equal(shown, true);
    assert.equal(displayed, 60);

    now = 160;
    indicator._sync();
    assert.equal(locks, 1, 'normal expiry locks without another balance read');
    assert.equal(replies.length, 0);

    const failed = indicator._refreshEstimate();
    await new Promise(setImmediate);
    replies.shift().reject(new Error('balance unavailable'));
    await failed;
    indicator._sync();
    assert.equal(locks, 1, 'a failed refresh cannot confirm the old expired balance');
    assert.equal(reports.length, 1);
    assert.equal(retries.size, 1, 'existing recovery remains scheduled');
    const [id, retry] = [...retries][0];
    retries.delete(id);
    retry();
    await new Promise(setImmediate);
    replies.shift().resolve(160_000_000);
    await new Promise(setImmediate);
    assert.equal(locks, 2, 'a fresh zero balance locks after successful recovery');
});

function refreshHarness({loaded = true} = {}) {
    let now = 100_000_000;
    let timerEnd = 340;
    let deadline = 340_123_456;
    let failure = null;
    const calls = [], reports = [], logs = [], timers = new Map(), delays = [];
    let nextId = 0;
    const manager = {getCurrentTime: () => now / 1_000_000, dailyLimitTime: 340};
    const indicator = createIndicator({
        GLib: {get_monotonic_time: () => now, PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
            timeout_add: (_priority, delay, callback) => {
                delays.push(delay);
                timers.set(++nextId, callback);
                return nextId;
            }, source_remove: id => timers.delete(id)},
        queryEstimatedTimes: async () => {
            if (failure === 'timer-estimate') throw new Error('source unavailable');
            return {'': [false, 0, timerEnd]};
        },
        calculateOwnDeadline: async (...args) => {
            calls.push(args);
            if (failure === 'broker-calculation') throw new Error('broker unavailable');
            return deadline;
        },
        remainingSeconds,
        timerErrorCategory: () => 'other',
        Main: {sessionMode: {isLocked: false, isGreeter: false}, timeLimitsManager: manager},
        logInfo() {}, logWarning: (event, fields) => logs.push({event, ...fields}),
    });
    Object.assign(indicator, {_deadlineUsec: loaded ? 150_000_000 : 0, _statusLoaded: loaded,
        _onError: error => reports.push(error), _sync() {}});
    return {indicator, manager, calls, reports, logs, timers, delays,
        time: value => { now = value * 1_000_000; },
        timer: value => { timerEnd = value; },
        deadline: value => { deadline = value; },
        fail: value => { failure = value; }};
}

test('passes raw observations and retains the broker deadline through fresh usage estimates', async () => {
    const h = refreshHarness();
    for (const now of [100, 160, 220, 340, 341]) {
        h.time(now);
        h.timer(now + 240); // Fresh completed-use estimates omit the ongoing interval.
        await h.indicator._refreshEstimate();
        assert.deepEqual(h.calls.at(-1), [340, now + 240,
            'com.puffyslippers.OhNoParentControl1']);
        assert.equal(h.indicator._deadlineUsec, 340_123_456);
        assert.equal(h.indicator._remainingSeconds(), Math.ceil(340.123456 - now));
        assert.equal(h.indicator._statusLoaded, true);
    }
    h.manager.dailyLimitTime = 0; // Inactivity is passed through for broker selection.
    await h.indicator._refreshEstimate();
    assert.equal(h.calls.at(-1)[0], 0);
    h.deadline(700_000_000);
    await h.indicator._refreshEstimate();
    assert.equal(h.indicator._deadlineUsec, 700_000_000);
});

test('temporary failures retain the original deadline or initial unavailable state with finite recovery', async () => {
    for (const loaded of [true, false]) {
        for (const stage of ['timer-estimate', 'broker-calculation']) {
            const h = refreshHarness({loaded});
            h.fail(stage);
            await h.indicator._refreshEstimate();
            for (let attempt = 0; attempt < 3; attempt++) {
                const [id, callback] = [...h.timers][0];
                h.timers.delete(id);
                callback();
                await new Promise(setImmediate);
            }
            assert.deepEqual(h.delays, [1000, 3000, 10000]);
            assert.equal(h.timers.size, 0, 'recovery stops after three retries');
            assert.equal(h.indicator._deadlineUsec, loaded ? 150_000_000 : 0);
            assert.equal(h.indicator._statusLoaded, loaded);
            assert.equal(h.reports.length, 4);
            assert.ok(h.logs.every(log => log.stage === stage && log.loaded === loaded));
            h.time(110);
            if (loaded) assert.equal(h.indicator._remainingSeconds(), 40);
            h.fail(null);
            await h.indicator._refreshEstimate();
            assert.equal(h.indicator._deadlineUsec, 340_123_456);
            assert.equal(h.indicator._statusLoaded, true);
            assert.equal(h.indicator._refreshRetries, 0);
        }
    }
});

test('delayed and invalidated replies cannot restart time or replace newer policy', async () => {
    let now = 100_000_000;
    const replies = [];
    const indicator = createIndicator({
        GLib: {get_monotonic_time: () => now},
        queryEstimatedTimes: async () => ({'': [false, 0, 200]}),
        calculateOwnDeadline: () => new Promise(resolve => replies.push(resolve)),
        remainingSeconds, logInfo() {},
        Main: {timeLimitsManager: {getCurrentTime: () => 100, dailyLimitTime: 200}},
    });
    Object.assign(indicator, {_deadlineUsec: 150_000_000, _statusLoaded: true, _sync() {}});
    const first = indicator._refreshEstimate();
    await new Promise(setImmediate);
    now = 105_000_000;
    replies.shift()(200_000_000);
    await first;
    assert.equal(indicator._remainingSeconds(), 95, 'reply latency consumes time');

    const obsolete = indicator._refreshEstimate();
    await new Promise(setImmediate);
    indicator.refreshEstimate(); // A source/policy change invalidates the in-flight reply.
    indicator._brokerOwnerChanged(':1.99'); // Replacement coalesces into the same fresh read.
    replies.shift()(999_000_000);
    await obsolete;
    assert.equal(indicator._deadlineUsec, 200_000_000, 'obsolete reply was rejected');
    await new Promise(setImmediate);
    assert.equal(replies.length, 1, 'one replacement read handles the burst');
    replies.shift()(180_000_000);
    await new Promise(setImmediate);
    assert.equal(indicator._deadlineUsec, 180_000_000);

    const pending = indicator._refreshEstimate();
    await new Promise(setImmediate);
    indicator._destroyed = true;
    replies.shift()(999_000_000);
    await pending;
    assert.equal(indicator._deadlineUsec, 180_000_000, 'disposed indicators reject late replies');
});

test('broker replacement cannot duplicate or strand an already pending lock request', () => {
    const callbacks = [];
    const events = [];
    let refreshes = 0;
    const connection = {call_finish() {}};
    const indicator = createIndicator({
        Gio: {DBus: {session: {call(...args) { callbacks.push(args.at(-1)); }}},
            DBusCallFlags: {NONE: 0}},
        Main: {sessionMode: {isLocked: false, isGreeter: false},
            timeLimitsManager: {dailyLimitEnabled: true}},
        SCREEN_SAVER_NAME: 'org.gnome.ScreenSaver',
        SCREEN_SAVER_PATH: '/org/gnome/ScreenSaver',
        SCREEN_SAVER_INTERFACE: 'org.gnome.ScreenSaver',
        logInfo: event => events.push(event), logWarning() {},
    });
    Object.assign(indicator, {_statusLoaded: true, _deadlineSerial: 0, _refreshSerial: 0,
        _deadlineUsec: 0, _remainingSeconds: () => 0, _schedule() {}, _sync() {}});
    indicator.refreshEstimate = () => refreshes++;
    indicator._brokerOwner = ':1.10';
    indicator._lockSession();
    assert.equal(indicator._lockPending, true);
    indicator._brokerOwnerChanged('');
    indicator._lockSession();
    indicator._brokerOwnerChanged(':1.11');
    indicator._lockSession();
    assert.equal(callbacks.length, 1, 'owner loss and recovery cannot replay pending input');
    assert.equal(refreshes, 2, 'both ownership changes demand fresh entitlement');
    callbacks.shift()(connection, {});
    assert.equal(indicator._lockPending, false, 'the original completion releases its request');
    assert.deepEqual(events, ['child.lock-requested', 'child.locked']);
    indicator._cancelLockDecision(); // a later freshly confirmed exhaustion
    indicator._lockSession();
    assert.equal(callbacks.length, 1, 'a later real expiry is not stranded');
    indicator._destroyed = true;
    callbacks.shift()(connection, {});
    indicator._lockSession();
    assert.equal(callbacks.length, 0, 'disposed sessions cannot receive another lock');
});

function lockHarness() {
    let now = 100_000_000;
    let nextId = 0;
    let resolveEstimate;
    const timers = new Map();
    const requests = [];
    const reports = [];
    const mode = {isLocked: false, isGreeter: false};
    const manager = {dailyLimitEnabled: true, dailyLimitTime: 100,
        getCurrentTime: () => now / 1e6};
    const indicator = createIndicator({
        GLib: {get_monotonic_time: () => now, source_remove: id => timers.delete(id),
            timeout_add_seconds: (_priority, delay, callback) => {
                timers.set(++nextId, {at: now + delay * 1e6, callback});
                return nextId;
            }},
        Main: {sessionMode: mode, timeLimitsManager: manager},
        Gio: {DBus: {session: {call(...args) { requests.push(args); }}},
            DBusCallFlags: {NONE: 0}}, logInfo() {}, logWarning() {},
        displayState, remainingSeconds,
        queryEstimatedTimes: () => new Promise(resolve => { resolveEstimate = resolve; }),
        calculateOwnDeadline: async () => 100_000_000,
    });
    Object.assign(indicator, {_statusLoaded: true, _deadlineSerial: 1, _refreshSerial: 1,
        _deadlineUsec: now, _timeoutId: 0, _timeoutDeadline: 0,
        _prepareSession() {}, _recordCountdownState() {}, _recordCountdownRefresh() {},
        _stopRequestIconSpin() {}, _setShown() {}, _updateLabel() {},
        _onError: error => reports.push(error)});
    return {indicator, requests, reports, timers, mode, manager,
        advance: seconds => { now += seconds * 1e6; },
        estimates: () => resolveEstimate({'': [0, 0, 100]}),
        tick() {
            const [id, timer] = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
            now = Math.max(now, timer.at);
            timers.delete(id);
            timer.callback();
        },
        reply(error = null) {
            requests.at(-1).at(-1)({call_finish() { if (error) throw error; }}, {});
        }};
}

test('temporary lock failure retries one request at a time within the original window', () => {
    const h = lockHarness();
    h.indicator._lockSession();
    assert.equal(h.requests[0][7], 15000);
    h.indicator._lockSession();
    assert.equal(h.requests.length, 1);
    h.reply(new Error('temporary'));
    h.indicator._lockSession();
    assert.equal(h.requests.length, 1, 'unrelated sync cannot skip retry spacing');
    h.advance(1);
    h.indicator._lockSession();
    assert.equal(h.requests.length, 2);
    h.reply();
    h.advance(13);
    h.indicator._lockSession();
    assert.equal(h.requests[2][7], 1000, 'the call timeout consumes only the original remaining window');
    h.reply(new Error('timeout'));
    h.advance(1);
    h.indicator._lockSession();
    assert.equal(h.requests.length, 3, 'expiry of the retry window cannot rearm itself');
});

test('slow initial and invalidated successful reads establish current exhaustion enforcement', async () => {
    for (const loaded of [false, true]) {
        const h = lockHarness();
        h.indicator._statusLoaded = loaded;
        const pending = h.indicator._refreshEstimate();
        h.advance(26);
        h.estimates();
        await pending;
        assert.equal(h.requests.length, 1, 'a slow successful read still dispatches the first lock');
        assert.equal(h.requests[0][7], 15000);
        h.mode.isLocked = true;
        h.reply();
        assert.equal(h.timers.size, 0);
    }
});

test('scheduled immediate lock refusals report once when the unchanged window ends', () => {
    const h = lockHarness();
    h.indicator._sync();
    const failure = new Error('temporary');
    for (let attempt = 0; attempt < 15; attempt++) {
        assert.equal(h.requests.length, attempt + 1);
        h.reply(failure);
        h.tick();
    }
    assert.equal(h.requests.length, 15);
    assert.deepEqual(h.reports, [failure]);
    h.indicator._sync();
    assert.equal(h.reports.length, 1);
    assert.equal(h.timers.size, 0);
});

test('final timeout reports, while secure recovery and renewal cancel scheduled retry and reports', () => {
    const timeout = lockHarness();
    timeout.indicator._sync();
    timeout.advance(15);
    timeout.reply(new Error('timeout'));
    assert.equal(timeout.reports.length, 1);
    for (const secure of [false, true]) {
        const h = lockHarness();
        h.indicator._sync();
        h.reply(new Error('temporary'));
        if (secure)
            h.mode.isLocked = true;
        else
            h.indicator._deadlineUsec += 1200e6;
        h.indicator._sync();
        h.advance(20);
        h.indicator._sync();
        assert.equal(h.requests.length, 1);
        assert.equal(h.reports.length, 0);
        assert.equal(h.indicator._lockDecision, null);
    }
});

test('renewal and invalidation retire pending lock callbacks without duplicating in-flight input', () => {
    const h = lockHarness();
    h.indicator._lockSession();
    h.indicator._cancelLockDecision();
    h.indicator._remainingSeconds = () => 1200;
    h.reply(new Error('temporary'));
    h.advance(2);
    h.indicator._lockSession();
    assert.equal(h.requests.length, 1, 'renewed time prevents stale retries');
    h.indicator._remainingSeconds = () => 0;
    h.indicator._deadlineSerial = 0;
    h.indicator._lockSession();
    assert.equal(h.requests.length, 1, 'unverified entitlement cannot dispatch');
    h.indicator._deadlineSerial = 1;
    for (const change of [() => { h.mode.isLocked = true; },
        () => { h.mode.isLocked = false; h.manager.dailyLimitEnabled = false; },
        () => { h.manager.dailyLimitEnabled = true; h.indicator._destroyed = true; }]) {
        change();
        h.indicator._lockSession();
        assert.equal(h.requests.length, 1);
    }
});

test('grant confirmation requests a fresh deadline without adding its original duration', () => {
    const indicator = createIndicator();
    Object.assign(indicator, {_deadlineUsec: 150_000_000});
    let refreshes = 0;
    indicator.refreshEstimate = () => refreshes++;
    indicator.showGrantedTime(300);
    indicator.showGrantedTime(0);
    assert.equal(refreshes, 2);
    assert.equal(indicator._deadlineUsec, 150_000_000);
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

function preparationHarness() {
    const timers = new Map(), delays = [], reports = [], records = [];
    let brokenLog = null;
    const mode = {isLocked: false, isGreeter: false};
    class BusError extends Error {}
    let nextId = 0, calls = 0;
    let failure = new BusError('private details');
    failure.remote = 'com.puffyslippers.OhNoParentControl1.Error.Busy';
    const indicator = createIndicator({
        shouldPrepareSession, busyRetryDelay,
        Main: {sessionMode: mode},
        Gio: {DBusError: {get_remote_error: error => error.remote}},
        GLib: {Error: BusError, get_monotonic_time: () => 0,
            PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
            timeout_add(_priority, delay, callback) {
                delays.push(delay);
                timers.set(++nextId, callback);
                return nextId;
            }, source_remove: id => timers.delete(id)},
        prepareOwnSession: async () => { calls++; if (failure) throw failure; return false; },
        logInfo(event, fields) {
            if (event === brokenLog) throw new Error('private logging failure');
            records.push(JSON.parse(diagnosticEnvelope(diagnosticCatalog, event,
                JSON.parse(JSON.stringify(fields)))));
        }, logWarning() {}, logDebug() {},
    });
    Object.assign(indicator, {_onError: error => reports.push(error), _signals: [],
        _clearTimeout() {}, _clearFlash() {}, _destroyContextMenu() {}});
    return {indicator, timers, delays, reports, records, mode, calls: () => calls,
        breakLogging: event => { brokenLog = event; },
        fail: value => { failure = value; },
        failRemote: remote => {
            failure = new BusError('private details');
            failure.remote = remote;
            return failure;
        },
        async retry() {
            const [id, callback] = [...timers][0];
            timers.delete(id);
            callback();
            await new Promise(setImmediate);
        }};
}

test('session preparation waits out extension recovery without reporting transient contention', async () => {
    const h = preparationHarness();
    await h.indicator._prepareSession();
    for (let tick = 0; tick < 20; tick++)
        await h.indicator._prepareSession();
    assert.equal(h.calls(), 1, 'display updates cannot bypass the pending retry');
    assert.equal(h.timers.size, 1);
    assert.deepEqual(h.records.find(row => row.event === 'child.session-prepare-retry').fields,
        {attempt: 1, retry: 1, delay_ms: 100});
    h.breakLogging('child.session-prepare-retry');
    await h.retry();
    h.fail(null);
    await h.retry();
    assert.equal(h.indicator._sessionPrepared, true);
    assert.equal(h.indicator._sessionPrepareRetries, 0);
    assert.deepEqual(h.reports, []);
    assert.deepEqual(h.delays, [100, 250]);
    assert.equal(h.timers.size, 0);
    assert.ok(!JSON.stringify(h.records).includes('private'));
    assert.throws(() => diagnosticEnvelope(diagnosticCatalog, 'child.session-prepare-retry',
        {attempt: 1, retry: 1, delay_ms: 100, message: 'private'}));
    assert.throws(() => diagnosticEnvelope(diagnosticCatalog, 'child.session-prepare-retry',
        {attempt: 1, retry: 6, delay_ms: 100}));
});

test('session preparation reports persistent contention and non-busy errors', async () => {
    const h = preparationHarness();
    await h.indicator._prepareSession();
    while (h.timers.size) await h.retry();
    assert.equal(h.calls(), 6);
    assert.deepEqual(h.delays, [100, 250, 500, 1000, 2000]);
    assert.equal(h.reports.length, 1);
    const errors = preparationHarness();
    const foreignBusy = errors.failRemote('org.example.Error.Busy');
    await errors.indicator._prepareSession();
    assert.equal(errors.reports.at(-1), foreignBusy, 'only the exact broker Busy error is retried');
    assert.equal(errors.timers.size, 0);
    const denied = new Error('private denial');
    errors.fail(denied);
    await errors.indicator._prepareSession();
    assert.equal(errors.reports.at(-1), denied);
    assert.equal(errors.indicator._sessionPrepared, undefined);
    assert.equal(errors.timers.size, 0);
});

test('preparation retry respects locking and disposal, including in-flight replies', async () => {
    const h = preparationHarness();
    await h.indicator._prepareSession();
    h.mode.isLocked = true;
    await h.retry();
    assert.equal(h.calls(), 1);
    h.mode.isLocked = false;
    await h.indicator._prepareSession();
    h.indicator._disposeResources();
    assert.equal(h.timers.size, 0);
    await h.indicator._prepareSession();
    assert.equal(h.calls(), 2);

    const late = preparationHarness();
    const pending = late.indicator._prepareSession();
    late.indicator._disposeResources();
    await pending;
    assert.equal(late.timers.size, 0);
    assert.deepEqual(late.reports, []);
});
