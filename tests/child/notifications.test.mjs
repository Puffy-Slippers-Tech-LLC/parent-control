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
        }
        addNotification(notification) { this.notification = notification; }
        destroy() { this.notification?.destroy(); super.destroy(); }
    }
    const sources = [], errors = [], callbacks = [], cancelled = [], banners = [];
    const context = vm.createContext({
        Gio: {FileIcon: class {constructor(params) { Object.assign(this, params); }},
            File: {new_for_path: path => path}, Cancellable: class {cancel() { cancelled.push(true); }},
            DBusCallFlags: {NONE: 0}, DBus: {system: {call: (...args) => callbacks.push(args.at(-1))}}},
        GLib: {VariantType: class {}},
        Clutter: {ActorAlign: {CENTER: 2}},
        Pango: {WrapMode: {WORD_CHAR: 2}, EllipsizeMode: {NONE: 0}},
        Main: {messageTray: {add: source => sources.push(source), get_children: () => banners}},
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
        error => errors.push(error), () => {});
    const reply = settings => callbacks.shift()({call_finish: () => ({deep_unpack: () => [JSON.stringify(settings)]})}, {});
    const policyReply = allowed => callbacks.shift()({call_finish: () => ({deep_unpack: () => [allowed]})}, {});
    return {notifier, sources, errors, callbacks, cancelled, banners, reply, policyReply};
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

test('compact reminder hides both headings and centers its small logo without changing other banners', () => {
    const h = harness();
    h.notifier.preferences = {show_in_fullscreen: true, reminders};
    h.notifier.present(reminders[2], false);
    const notification = h.notifier.current.notification;
    const actor = (style, children = []) => ({
        visible: true, y_align: 0, classes: new Set([style]),
        get_children: () => children,
        get_parent() { return this.parent; },
        remove_child(child) { children.splice(children.indexOf(child), 1); child.parent = null; },
        add_child(child) { children.push(child); child.parent = this; },
        has_style_class_name(name) { return this.classes.has(name); },
        add_style_class_name(name) { this.classes.add(name); },
        hide() { this.visible = false; },
    });
    const header = actor('message-header');
    const title = actor('message-title');
    const body = actor('message-body');
    body.clutter_text = {set_text(text) { this.text = text; }};
    const bin = actor('body-bin', [body]);
    const content = actor('message-content', [title, bin]);
    body.parent = bin;
    bin.parent = content;
    const icon = actor('message-icon');
    const owned = actor('notification-banner', [header, icon, content]);
    owned.notification = notification;
    const otherHeader = actor('message-header');
    const other = actor('notification-banner', [otherHeader]);
    other.notification = {};
    h.banners.push(actor('container', [other, owned]));
    notification.acknowledged = true;
    for (const callback of notification.handlers['notify::acknowledged']) callback();
    assert.equal(header.visible, false);
    assert.equal(title.visible, false);
    assert.equal(body.visible, true);
    assert.equal(body.parent, content);
    assert.equal(bin.visible, false);
    assert.equal(body.clutter_text.line_wrap, true);
    assert.equal(body.clutter_text.ellipsize, 0);
    notification.body = 'Save now\n' + 'verylongword'.repeat(30);
    for (const callback of notification.handlers['notify::body']) callback();
    assert.equal(body.clutter_text.text, notification.body);
    assert.equal(owned.x_expand, false);
    assert.equal(icon.y_align, 2);
    assert(owned.classes.has('screen-time-reminder'));
    assert.equal(otherHeader.visible, true);
    assert.equal(other.classes.has('screen-time-reminder'), false);
    const css = readFileSync(new URL('../../child/stylesheet.css', import.meta.url), 'utf8');
    assert.match(css, /\.screen-time-reminder \.message-icon\s*\{[^}]*icon-size: 20px;/);
    h.notifier.clear();
    owned.classes.delete('screen-time-reminder');
    for (const callback of notification.handlers['notify::acknowledged']) callback();
    assert.equal(owned.classes.has('screen-time-reminder'), false);
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
    assert(elements.every(element => !element.enabled && !element.activate && !element.setValue));
    Main.sessionMode.isLocked = true;
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
