import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {ReminderSchedule, notificationPreferences, reminderSeconds, reminderText} from '../../child/notificationLogic.mjs';
import {createIndicator} from './support/indicator.mjs';

// All state is private to each test: no Shell, sockets, processes or files written.
const reminders = [
    {id: 'ten', value: 10, unit: 'minute', text: ''},
    {id: 'five', value: 5, unit: 'minute', text: ''},
    {id: 'one', value: 1, unit: 'minute', text: ''},
    {id: 'seconds', value: 15, unit: 'second', text: ''},
];
const translations = {text: (key, values) => key === 'TIME_REMAINING_NOTIFICATION'
    ? `${values.time} left` : key === 'TIME_REMAINING_SAVE_GAMES_NOTIFICATION'
        ? `${values.time} left, save your games!`
        : key === 'COMPACT_SECONDS' ? `${values.count}s`
        : key === 'REMINDER_AUTO_CLOSE' ? 'This notification will close in 5 seconds.'
        : key === 'PREFERENCES' ? 'Preferences' : key === 'DISMISS' ? 'Dismiss'
        : `${values.count} ${key === 'MINUTE_COUNT' ? 'minute' : 'second'}${values.count === 1 ? '' : 's'}`};

test('thresholds are deduplicated and rearmed by renewed usable time', () => {
    const schedule = new ReminderSchedule();
    const delivered = [];
    for (const remaining of [601, 600, 600, 601, 600, 599, 301, 300, 61, 60, 16, 15, 14, 0]) {
        const reminder = schedule.update(reminders, remaining, true);
        if (reminder) delivered.push(reminder.id);
    }
    assert.deepEqual(delivered, ['ten', 'five', 'one', 'seconds']);
    assert.equal(schedule.update(reminders, 180, true), null);
    assert.equal(schedule.update(reminders, 60, true).id, 'one');
});

test('startup, missed ticks, empty configuration and locked samples do not flood notifications', () => {
    assert.equal(new ReminderSchedule().update(reminders, 44, true), null);
    assert.equal(new ReminderSchedule().update(reminders, 60, true).id, 'one');
    const schedule = new ReminderSchedule();
    schedule.update(reminders, 700, true);
    assert.equal(schedule.update(reminders, 14, true).id, 'seconds');
    assert.equal(schedule.update(reminders, 13, true), null);
    assert.equal(schedule.update(reminders, 60, false), null);
    assert.equal(schedule.update([], 15, true), null);
});

test('custom minute/second thresholds schedule earlier ticks and literal custom text bypasses translation', () => {
    const schedule = new ReminderSchedule();
    const custom = {id: 'custom', value: 75, unit: 'second', text: ''};
    assert.equal(reminderSeconds(custom), 75);
    assert.equal(schedule.nextDelay([custom], 90, 30), 15);
    assert.equal(schedule.nextDelay([custom], 75, 15), 15);
    assert.equal(reminderText(custom, translations, true), '75 seconds left');
    assert.equal(reminderText({...custom, unit: 'minute', value: 15, text: '\t\n\u2003'}, translations),
        '15 minutes left');
    assert.equal(reminderText({...custom, text: ' <b>Save now</b> '}, {text() { assert.fail(); }}),
        ' <b>Save now</b> ');
});

test('default wording respects singulars and the strict subminute soft-app boundary', () => {
    for (const allow of [false, true]) {
        assert.equal(reminderText(reminders[0], translations, allow), '10 minutes left');
        assert.equal(reminderText(reminders[2], translations, allow), '1 minute left');
        assert.equal(reminderText({...reminders[3], value: 60}, translations, allow), '60 seconds left');
        for (const value of [1, 15, 59]) {
            const time = `${value} second${value === 1 ? '' : 's'}`;
            assert.equal(reminderText({...reminders[3], value}, translations, allow),
                `${time} left${allow ? ', save your games!' : ''}`);
        }
        assert.equal(reminderText({...reminders[3], text: 'Save my work'}, translations, allow), 'Save my work');
    }
});

function harness() {
    class SignalObject {
        constructor(params) { Object.assign(this, params); this.handlers = {}; }
        connect(name, fn) { (this.handlers[name] ??= []).push(fn); }
        connectObject(name, fn) { this.connect(name, fn); }
        destroy() { this.destroyed = true; for (const fn of this.handlers.destroy ?? []) fn(this); }
    }
    class Source extends SignalObject {
        constructor(params) {
            super(params);
            assert.deepEqual(Object.keys(params).sort(), ['icon', 'title']);
            this.policy = {showBanners: true};
            sources.push(this);
        }
        addNotification(notification) { this.notification = notification; }
        destroy() { this.notification?.destroy(); super.destroy(); }
    }
    const sources = [], errors = [], callbacks = [], cancelled = [], banners = [], chrome = [];
    const timers = new Map();
    let now = 0, serial = 0, preferencesOpened = 0;
    class Actor extends SignalObject {
        constructor(params = {}) {
            super({width: 100, visible: true, ...params});
            this.children = [];
            this.clutter_text = {};
        }
        add_child(child) { this.children.push(child); child.parent = this; }
        set_style(style) { this.style = style; }
        set_request_mode(mode) { this.request_mode = mode; }
        get_style() { return this.style; }
        set_position(x, y) { this.x = x; this.y = y; }
        get_preferred_width() {
            let root = this;
            while (root.parent) root = root.parent;
            assert.ok(chrome.includes(root), 'measure themed controls only after stage attachment');
            return [this.width, this.width];
        }
        set_text_direction(value) { this.direction = value; }
        get_text_direction() { return this.direction; }
        get_transformed_position() { return [this.x ?? 0, this.y ?? 0]; }
        get_transformed_size() { return [this.width, 40]; }
        get_preferred_height() { return [20, 20]; }
        get_pango_context() { return {get_font_map: () => ({add_font_file: () => true})}; }
    }
    const file = path => ({get_path: () => path, get_parent: () => file(path + '/..'),
        get_child: name => file(path + '/' + name), query_exists: () => true});
    const sessionMode = new SignalObject({isLocked: false, isGreeter: false});
    const primaryMonitor = {index: 0, x: 0, y: 0, width: 1920, height: 1080, inFullscreen: false};
    const topWindowGroup = {};
    const layers = [{}, topWindowGroup];
    const addChrome = actor => {
        chrome.push(actor);
        if (actor.style_class === 'screen-time-reminder') banners.push(actor);
    };
    const layoutManager = new SignalObject({primaryMonitor, monitors: [primaryMonitor],
        addChrome: (actor, params) => {
            assert.equal(params.trackFullscreen, false);
            layers.splice(layers.indexOf(topWindowGroup), 0, actor);
            addChrome(actor);
        }, addTopChrome: (actor, params) => {
            assert.equal(params.trackFullscreen, false);
            layers.push(actor);
            addChrome(actor);
        }, removeChrome: actor => {
            layers.splice(layers.indexOf(actor), 1);
            chrome.splice(chrome.indexOf(actor), 1);
            if (banners.includes(actor)) banners.splice(banners.indexOf(actor), 1);
        }});
    const context = vm.createContext({
        Gio: {FileIcon: class {constructor(params) { Object.assign(this, params); }
                get_file() { return file(this.file); }},
            File: {new_for_path: path => path}, Cancellable: class {cancel() { cancelled.push(true); }},
            DBusCallFlags: {NONE: 0}, DBus: {system: {call: (...args) => callbacks.push(args.at(-1))}}},
        GLib: {VariantType: class {}, get_monotonic_time: () => now,
            timeout_add: (_priority, _interval, callback) => { timers.set(++serial, callback); return serial; },
            source_remove: id => timers.delete(id), SOURCE_REMOVE: false, SOURCE_CONTINUE: true},
        Clutter: {ActorAlign: {CENTER: 2, START: 1}, Orientation: {VERTICAL: 1}, BinLayout: class {},
            RequestMode: {HEIGHT_FOR_WIDTH: 0, WIDTH_FOR_HEIGHT: 1},
            TextDirection: {LTR: 0, RTL: 1}},
        St: {BoxLayout: Actor, Label: Actor, Icon: Actor, Button: Actor, Widget: Actor,
            ThemeContext: {get_for_stage: () => ({scale_factor: 1})}},
        describeControl: () => {},
        global: {stage: {}, display: new SignalObject()},
        Pango: {WrapMode: {WORD_CHAR: 2}, EllipsizeMode: {NONE: 0}},
        Main: {sessionMode, layoutManager},
        MessageTray: {Source, Notification: SignalObject, Urgency: {CRITICAL: 3, HIGH: 2}, PrivacyScope: {USER: 0}},
        ReminderSchedule, notificationPreferences, reminderSeconds, reminderText,
    });
    const bannerSource = readFileSync(new URL('../../child/reminderBanner.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export function showReminderBanner', 'function showReminderBanner');
    vm.runInContext(bannerSource, context);
    const source = readFileSync(new URL('../../child/remainingTimeNotifications.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export class RemainingTimeNotifications', 'globalThis.RemainingTimeNotifications = class');
    vm.runInContext(source, context);
    const notifier = new context.RemainingTimeNotifications('Product', '/logo.png', translations,
        error => errors.push(error), () => {}, () => preferencesOpened++);
    const reply = settings => callbacks.shift()({call_finish: () => ({deep_unpack: () => [JSON.stringify(settings)]})}, {});
    const policyReply = allowed => callbacks.shift()({call_finish: () => ({deep_unpack: () => [allowed]})}, {});
    const advance = milliseconds => {
        now += milliseconds * 1000;
        for (const [id, callback] of [...timers]) if (!callback()) timers.delete(id);
    };
    return {notifier, sources, errors, callbacks, cancelled, banners, chrome, layers, topWindowGroup, reply, policyReply,
        advance, timers, sessionMode, layoutManager, context, preferencesOpened: () => preferencesOpened};
}

test('production notification uses Shell urgency, logo, literal text and owned replacement/cleanup', () => {
    const h = harness();
    h.notifier.refresh();
    h.notifier.refresh();
    assert.equal(h.callbacks.length, 1);
    h.reply({show_in_fullscreen: true, reminders});
    h.notifier.update(61, true);
    h.notifier.update(60, true);
    const first = h.sources[0];
    assert.equal(first.notification.urgency, 3);
    assert.equal(first.notification.gicon.file, '/logo.png');
    assert.equal(first.notification.useBodyMarkup, false);
    assert.equal(first.notification.body, '1 minute left');
    assert.equal(first.notification.title, '');
    assert.equal(first.icon.file, '/logo.png');
    assert.equal(first.notification.privacyScope, 0);
    h.notifier.update(16, true);
    h.policyReply(false);
    h.notifier.update(15, true);
    h.policyReply(false);
    assert.equal(first.destroyed, true);
    assert.equal(h.sources.length, 2);
    h.notifier.refresh();
    h.reply({show_in_fullscreen: false, reminders});
    assert.equal(h.notifier.current.notification.urgency, 2);
    assert.equal(h.notifier.current.urgency, 'high');
    h.notifier.update(14, false);
    assert.equal(h.sources[1].destroyed, true);
    assert.equal(h.notifier.current, null);
    h.notifier.close();
    h.notifier.close();
    assert.equal(h.cancelled.length, 1);
    assert.deepEqual(h.errors, []);
});

test('default banners follow live time without replacement and custom text stays literal', () => {
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: true, reminders: [reminders[0]]};
    h.notifier.update(601, true);
    h.notifier.update(600, true);
    const notification = h.notifier.current.notification;
    for (const [seconds, expected] of [[599, '10 minutes left'], [540, '9 minutes left'],
        [60, '1 minute left'], [59, '59 seconds left']]) {
        h.notifier.update(seconds, true);
        assert.equal(notification.body, expected);
        assert.equal(h.notifier.current.notification, notification);
        assert.equal(h.notifier.current.seconds, seconds);
    }
    h.policyReply(true);
    h.notifier.update(58, true);
    assert.equal(notification.body, '58 seconds left, save your games!');
    h.notifier.refresh();
    h.reply({show_in_fullscreen: true, reminders: [reminders[0]]});
    assert.equal(notification.body, '58 seconds left, save your games!');
    assert.equal(h.sources.length, 1);
    h.notifier.update(1, true);
    assert.equal(notification.body, '1 second left, save your games!');
    h.notifier.update(0, true);
    assert.equal(h.notifier.current, null);

    const custom = {...reminders[0], text: ' <b>Save now</b> '};
    const literal = harness();
    literal.notifier.preferences = {show_in_fullscreen: true, reminders: [custom]};
    literal.notifier.update(600, true);
    literal.notifier.update(59, true);
    assert.equal(literal.notifier.current.notification.body, custom.text);
    assert.equal(literal.callbacks.length, 0);
});

test('second defaults schedule live ticks and delayed policy replies use the latest balance', () => {
    const h = harness();
    const seconds = {...reminders[3], value: 75};
    h.notifier.preferences = {show_in_fullscreen: true, reminders: [seconds]};
    h.notifier.update(75, true);
    assert.equal(h.notifier.nextDelay(75, 15), 1);
    h.notifier.update(74, true);
    assert.equal(h.notifier.current.notification.body, '74 seconds left');
    h.notifier.update(59, true);
    h.notifier.update(57, true);
    h.policyReply(true);
    assert.equal(h.notifier.current.notification.body, '57 seconds left, save your games!');
    assert.equal(h.sources.length, 1);
    h.notifier.clear();
    assert.equal(h.notifier.nextDelay(57, 30), 30);

    const delayed = harness();
    delayed.notifier.preferences = {show_in_fullscreen: true, reminders: [reminders[3]]};
    delayed.notifier.update(15, true);
    assert.equal(delayed.notifier.nextDelay(15, 10), 1);
    delayed.notifier.update(12, true);
    delayed.policyReply(false);
    assert.equal(delayed.notifier.current.notification.body, '12 seconds left');
});

test('minute banners expire after five seconds and subminute banners persist until dismissed', () => {
    for (const seconds of [59, 60, 61]) {
        const h = harness();
        h.notifier.preferences = {show_in_fullscreen: true, reminders};
        h.notifier.schedule.previous = seconds;
        h.notifier.present(reminders[2], false);
        const current = h.notifier.current;
        assert.equal(current.countdown(), seconds >= 60 ? 5 : null);
        h.advance(4900);
        assert.equal(h.notifier.current, current);
        h.advance(100);
        assert.equal(h.notifier.current, seconds >= 60 ? null : current);
        if (seconds < 60) {
            h.advance(60000);
            assert.equal(h.notifier.current, current);
            current.dismiss();
        }
        assert.equal(h.notifier.current, null);
        assert.equal(h.banners.length, 0);
        assert.equal(h.timers.size, 0);
    }
});

test('new banners retire previous timers and Preferences uses the shared overlay action', () => {
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: true, reminders};
    h.notifier.present(reminders[2], false);
    const old = h.notifier.current;
    h.advance(3000);
    h.notifier.schedule.previous = 15;
    h.notifier.present(reminders[3], false);
    const current = h.notifier.current;
    assert.equal(old.source.destroyed, true);
    assert.equal(h.timers.size, 0);
    h.advance(10000);
    old.dismiss();
    assert.equal(h.notifier.current, current);
    current.preferences();
    assert.equal(h.notifier.current, null);
    assert.equal(h.preferencesOpened(), 1);
});

test('fullscreen preference controls delivery without changing persistence or touching other chrome', () => {
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: false, reminders};
    h.layoutManager.primaryMonitor.inFullscreen = true;
    h.notifier.present(reminders[2], false);
    const current = h.notifier.current;
    assert.equal(current.card.visible, false);
    assert.equal(h.timers.size, 0);
    h.layoutManager.primaryMonitor.inFullscreen = false;
    for (const sync of h.context.global.display.handlers['in-fullscreen-changed']) sync();
    assert.equal(current.card.visible, true);
    assert.equal(current.countdown(), 5);
    h.sessionMode.isLocked = true;
    for (const sync of h.sessionMode.handlers.updated) sync();
    assert.equal(h.notifier.current, null);
    assert.equal(h.timers.size, 0);
});

test('external-only fullscreen reminder stays above application layers without changing app focus', () => {
    for (const enabled of [false, true]) {
        const h = harness();
        const external = h.layoutManager.primaryMonitor;
        external.inFullscreen = true;
        const game = {get_monitor: () => 0};
        h.context.global.display.focus_window = game;
        h.notifier.preferences = {show_in_fullscreen: enabled, reminders};
        h.notifier.present(reminders[2], false);
        const current = h.notifier.current;
        assert.equal(current.card.visible, enabled);
        assert.equal(current.countdown(), enabled ? 5 : null);
        assert(h.layers.indexOf(current.card) > h.layers.indexOf(h.topWindowGroup));
        const tooltip = h.chrome.find(actor => actor.style_class === 'dash-label screen-time-tooltip');
        assert(h.layers.indexOf(tooltip) > h.layers.indexOf(current.card));
        assert.equal(h.context.global.display.focus_window, game);
        current.dismiss();
        assert.equal(h.chrome.length, 0);
        assert.equal(h.layers.length, 2);
        assert.equal(h.timers.size, 0);
    }
});

test('reminder follows the focused app monitor and uses its fullscreen state', () => {
    const h = harness();
    const internal = h.layoutManager.primaryMonitor;
    const external = {index: 1, x: 1920, y: -200, width: 2560, height: 1440, inFullscreen: true};
    h.layoutManager.monitors.push(external);
    let gameMonitor = 1;
    h.context.global.display.focus_window = {get_monitor: () => gameMonitor};
    h.notifier.preferences = {show_in_fullscreen: false, reminders};
    h.notifier.present(reminders[2], false);
    const current = h.notifier.current;
    assert.equal(current.card.visible, false);
    assert.equal(current.countdown(), null);
    assert.equal(current.card.x, external.x + (external.width - current.card.width) / 2);
    assert.equal(current.card.y, external.y + 8);

    // Changing the preference shows the same warning on the game display.
    h.notifier.refresh();
    h.reply({show_in_fullscreen: true, reminders});
    for (const sync of current.notification.handlers['notify::urgency']) sync();
    assert.equal(current.card.visible, true);
    assert.equal(current.countdown(), 5);
    h.advance(1000);

    // A focused window can move between monitors without changing focus.
    gameMonitor = 0;
    for (const sync of h.context.global.display.handlers['window-entered-monitor']) sync();
    assert.equal(current.card.x, internal.x + (internal.width - current.card.width) / 2);
    assert.equal(current.countdown(), 4);
    gameMonitor = 1;
    for (const sync of h.context.global.display.handlers['notify::focus-window']) sync();
    assert.equal(current.card.x, external.x + (external.width - current.card.width) / 2);
    assert.equal(current.countdown(), 4);

    const tooltip = h.chrome.find(actor => actor.style_class === 'dash-label screen-time-tooltip');
    const control = current.card.children.at(-1).children[0];
    Object.assign(control, {x: external.x + external.width - 50, y: external.y + 100,
        mapped: true, hover: true});
    control.handlers['notify::hover'][0]();
    assert.equal(tooltip.visible, true);
    assert(tooltip.x >= external.x);
    assert(tooltip.x + tooltip.width <= external.x + external.width);
    assert(tooltip.y >= external.y);
    current.dismiss();
    assert.deepEqual(h.errors, []);
});

test('monitor changes recover from stale app indices, missing displays and absent focus', () => {
    const h = harness();
    const external = {index: 0, x: -2560, y: 120, width: 2560, height: 1440, inFullscreen: true};
    h.layoutManager.monitors = [external];
    // Shell may update the active list before the old primary/focus reference.
    h.context.global.display.focus_window = {get_monitor: () => 1};
    h.notifier.preferences = {show_in_fullscreen: true, reminders};
    h.notifier.schedule.previous = 15;
    h.notifier.present(reminders[3], false);
    const current = h.notifier.current;
    assert.equal(current.card.visible, true);
    assert.equal(current.card.x, external.x + (external.width - current.card.width) / 2);
    h.layoutManager.monitors = [];
    for (const sync of h.layoutManager.handlers['monitors-changed']) sync();
    assert.equal(current.card.visible, false);
    assert.equal(current.countdown(), null);
    h.context.global.display.focus_window = null;
    h.layoutManager.monitors = [external];
    h.layoutManager.primaryMonitor = external;
    for (const sync of h.layoutManager.handlers['monitors-changed']) sync();
    assert.equal(current.card.visible, true);
    assert.equal(current.card.x, external.x + (external.width - current.card.width) / 2);
    current.dismiss();
    assert.equal(h.chrome.length, 0);
    assert.deepEqual(h.errors, []);
});

test('critical reminders stay above override-redirect games through external-only monitor changes', () => {
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: true, reminders};
    h.layoutManager.primaryMonitor.inFullscreen = true;
    h.notifier.schedule.previous = 15;
    h.notifier.present(reminders[3], false);
    const current = h.notifier.current;
    const tooltip = h.chrome.find(actor => actor.style_class === 'dash-label screen-time-tooltip');
    assert.equal(current.card.visible, true);
    assert.ok(h.layers.indexOf(current.card) > h.layers.indexOf(h.topWindowGroup));
    assert.ok(h.layers.indexOf(tooltip) > h.layers.indexOf(current.card));
    const monitorsChanged = () => {
        for (const sync of h.layoutManager.handlers['monitors-changed']) sync();
    };
    h.layoutManager.primaryMonitor = null;
    h.layoutManager.monitors = [];
    monitorsChanged();
    assert.equal(current.card.visible, false);
    h.layoutManager.primaryMonitor = {x: 1920, y: 120, width: 2560, height: 1440, inFullscreen: true};
    h.layoutManager.monitors = [h.layoutManager.primaryMonitor];
    monitorsChanged();
    assert.equal(current.card.visible, true);
    assert.equal(current.card.x, 1920 + (2560 - current.card.width) / 2);
    assert.equal(current.card.y, 128);
    h.advance(6000);
    assert.equal(h.notifier.current, current);
    h.notifier.clear();
    assert.equal(h.layers.length, 2);
    assert.equal(h.layers[1], h.topWindowGroup);
    assert.equal(h.chrome.length, 0);
    assert.equal(h.timers.size, 0);
});

test('preview source destruction releases its sender watch without recursive destruction', () => {
    const h = harness();
    let unwatched = 0;
    h.context.Gio.bus_watch_name_on_connection = () => 1;
    h.context.Gio.bus_unwatch_name = () => unwatched++;
    h.context.Gio.BusNameWatcherFlags = {NONE: 0};
    h.context.GLib.Variant = class {};
    const source = readFileSync(new URL('../../child/reminderPreview.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export class ReminderPreview', 'globalThis.Preview = class');
    vm.runInContext(source, h.context);
    const preview = Object.assign(Object.create(h.context.Preview.prototype), {
        title: 'Product', icon: new h.context.Gio.FileIcon({file: '/logo.png'}),
        translations, openPreferences: () => {}, serial: 0, watch: 0,
        _dispatch: (_invocation, operation) => operation('sender'),
    });
    preview.PreviewTimedAsync(['Save now', 0, 60], {});
    const current = preview.current;
    let destructions = 0;
    current.source.connect('destroy', () => destructions++);
    current.dismiss();
    assert.equal(destructions, 1);
    assert.equal(unwatched, 1);
    assert.equal(preview.current, null);
    assert.equal(h.banners.length, 0);
    assert.equal(h.timers.size, 0);
    h.context.TranslationContext = class {
        apply(language) { this.language = language; }
        text(key) {
            assert.equal(this.language, 'zh-Hans');
            return {PREFERENCES: '偏好设置', DISMISS: '关闭',
                REMINDER_AUTO_CLOSE: '此通知将在 5 秒后关闭。', COMPACT_SECONDS: '5 秒'}[key];
        }
    };
    preview.PreviewLocalizedAsync(['还剩 20 秒', 0, 20, 'zh-Hans'], {});
    const texts = actor => [actor.text, ...actor.children.flatMap(texts),
        ...(actor.child ? texts(actor.child) : [])];
    assert(!texts(preview.current.card).includes('偏好设置'));
    assert(!texts(preview.current.card).includes('关闭'));
    assert.equal(preview.translations, translations);
    const tooltip = h.chrome.find(actor => actor.style_class === 'dash-label screen-time-tooltip');
    const controls = preview.current.card.children.at(-1).children;
    for (const [index, expected] of ['偏好设置', '关闭'].entries()) {
        controls[index].mapped = true;
        controls[index].hover = true;
        controls[index].handlers['notify::hover'][0]();
        assert.equal(tooltip.text, expected);
        assert.equal(tooltip.visible, true);
        controls[index].hover = false;
        controls[index].handlers['notify::hover'][0]();
        assert.equal(tooltip.visible, false);
    }
    preview.current.dismiss();
    assert.equal(tooltip.destroyed, true);
    assert.equal(h.chrome.length, 0);
});

test('subminute delivery queries current policy and ignores stale replies', () => {
    for (const allowed of [false, true]) {
        const h = harness();
        h.notifier.preferences = {show_in_fullscreen: true, reminders};
        h.notifier.update(16, true);
        h.notifier.update(15, true);
        assert.equal(h.sources.length, 0);
        h.policyReply(allowed);
        assert.equal(h.notifier.current.notification.body,
            `15 seconds left${allowed ? ', save your games!' : ''}`);
        h.notifier.refresh();
        h.reply({show_in_fullscreen: true, reminders});
        assert.equal(h.notifier.current.notification.body,
            `15 seconds left${allowed ? ', save your games!' : ''}`);
    }
    for (const stop of [h => h.notifier.update(0, false),
        h => h.notifier.update(180, true), h => h.notifier.close()]) {
        const h = harness();
        h.notifier.preferences = {show_in_fullscreen: true, reminders};
        h.notifier.update(16, true);
        h.notifier.update(15, true);
        stop(h);
        h.policyReply(true);
        assert.equal(h.sources.length, 0);
    }
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: true, reminders};
    h.notifier.update(16, true);
    h.notifier.update(15, true);
    h.callbacks.shift()({call_finish() { throw new Error('unavailable'); }}, {});
    assert.equal(h.notifier.current.notification.body, '15 seconds left');
    assert.equal(h.errors.length, 1);
});

test('failed reads retain custom preferences, late replies are ignored and emission failures stay bounded', () => {
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: false, reminders: []};
    h.notifier.refresh();
    h.callbacks.shift()({call_finish() { throw new Error('unavailable'); }}, {});
    assert.equal(h.notifier.preferences.reminders.length, 0);
    assert.equal(h.errors.length, 1);
    h.notifier.refresh();
    h.reply({show_in_fullscreen: true, reminders: [{}]});
    assert.equal(h.notifier.preferences.reminders.length, 0);
    assert.equal(h.errors.length, 2);
    h.notifier.refresh();
    h.notifier.close();
    h.reply({show_in_fullscreen: true, reminders});
    assert.equal(h.notifier.preferences.reminders.length, 0);
    const other = harness();
    other.notifier.preferences = {show_in_fullscreen: true, reminders};
    other.notifier.show = () => { throw new Error('Shell unavailable'); };
    other.notifier.update(16, true);
    other.notifier.update(15, true);
    other.notifier.update(15, true);
    assert.equal(other.errors.length, 1);
});

test('renewed usable time clears a stale warning and preference deletion drops retained delivery state', () => {
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: true, reminders};
    h.notifier.update(61, true);
    h.notifier.update(60, true);
    const first = h.sources[0];
    h.notifier.update(180, true);
    assert.equal(first.destroyed, true);
    assert.equal(h.notifier.current, null);
    h.notifier.update(60, true);
    assert.equal(h.sources.length, 2);
    h.notifier.refresh();
    h.reply({show_in_fullscreen: false, reminders: []});
    assert.equal(h.notifier.current, null);
    assert.equal(h.notifier.schedule.delivered.size, 0);
});

test('editing a delivered threshold rearms its new time without replaying text-only edits', () => {
    const h = harness();
    const one = [{id: 'save', value: 1, unit: 'minute', text: ''}];
    h.notifier.preferences = {show_in_fullscreen: true, reminders: one};
    h.notifier.update(61, true);
    h.notifier.update(60, true);
    assert.equal(h.sources.length, 1);

    // Equivalent units and new text retain delivery for the same threshold.
    h.notifier.refresh();
    h.reply({show_in_fullscreen: true, reminders: [
        {id: 'save', value: 60, unit: 'second', text: 'Save now'},
    ]});
    assert.equal(h.notifier.schedule.delivered.has('save'), true);
    h.notifier.update(61, true);
    h.notifier.update(60, true);
    assert.equal(h.sources.length, 1);

    h.notifier.refresh();
    h.reply({show_in_fullscreen: true, reminders: [
        {id: 'save', value: 15, unit: 'second', text: 'Save now'},
    ]});
    assert.equal(h.notifier.schedule.delivered.has('save'), false);
    h.notifier.update(16, true);
    h.notifier.update(15, true);
    assert.equal(h.sources.length, 2);
    assert.equal(h.notifier.current.notification.body, 'Save now');
    assert.equal(h.notifier.current.seconds, 15);
    h.notifier.update(15, true);
    assert.equal(h.sources.length, 2);
});

test('notification UI adapter exposes actual current text and canonical urgency with lifecycle guards', () => {
    const Main = {sessionMode: {isLocked: false, isGreeter: false}};
    const context = vm.createContext({Main});
    const source = readFileSync(new URL('../../child/gnomeApplicationUiAdapter.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export class GnomeApplicationUiAdapter', 'globalThis.Adapter = class');
    vm.runInContext(source, context);
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: false, reminders};
    h.notifier.update(16, true);
    h.notifier.update(15, true);
    h.policyReply(false);
    const indicator = {_notifications: h.notifier,
        container: {visible: true}, _requestButton: {visible: true, reactive: true, get_parent: () => null}};
    const adapter = new context.Adapter(indicator);
    assert.equal(adapter.listSurfaces().at(-1).id, 'child-time-notification');
    const elements = adapter.elements('child-time-notification');
    assert.equal(elements.find(element => element.id === 'child-time-notification-message').getText(),
        h.notifier.current.notification.body);
    assert.equal(elements.find(element => element.id === 'child-time-notification-message').getValue(), 15);
    assert.equal(elements.find(element => element.id === 'child-time-notification-urgency').getValue(), 'high');
    assert(elements.find(element => element.id === 'child-time-notification-close').activate);
    assert(elements.find(element => element.id === 'child-time-notification-preferences').activate);
    Main.sessionMode.isLocked = true;
    h.notifier.current.card.visible = false;
    assert(adapter.elements('child-time-notification').every(element => !element.visible));
    h.notifier.clear();
    assert.equal(adapter.elements('child-time-notification'), null);
    adapter.close();
    assert.equal(adapter.listSurfaces().length, 0);
});

test('production indicator schedules custom thresholds and still locks at zero', () => {
    let remaining = 90;
    const updates = [], delays = [];
    const indicator = createIndicator({Main: {sessionMode: {isLocked: false, isGreeter: false},
        timeLimitsManager: {getCurrentTime: () => 0, dailyLimitEnabled: true}},
        displayState: ({calculatedEnd}) => ({remaining: calculatedEnd, visible: calculatedEnd > 0,
            shouldLock: calculatedEnd <= 0, nextUpdateSeconds: 30})});
    const schedule = new ReminderSchedule();
    Object.assign(indicator, {_statusLoaded: true, _sessionPrepared: true, _activeExtensionEnd: 0,
        _preview: true, _notifications: {update: (...args) => updates.push(args),
            nextDelay: (time, fallback) => schedule.nextDelay([{value: 75, unit: 'second'}], time, fallback)},
        _prepareSession() {}, _setShown() {}, _updateLabel() {}, _schedule: delay => delays.push(delay),
        _clearTimeout() {}, _stopRequestIconSpin() {}, _lockSession() { updates.push('lock'); }});
    indicator._calculatedEnd = remaining;
    indicator._sync();
    assert.deepEqual(delays, [15]);
    indicator._preview = false;
    indicator._calculatedEnd = 0;
    // Avoid diagnostics unrelated to this isolated scheduling contract.
    indicator._expiryDiagnostic = 'loaded=true limitEnabled=true locked=false greeter=false pending=undefined';
    indicator._sync();
    assert.deepEqual(updates, [[90, true], [0, false], 'lock']);
});
