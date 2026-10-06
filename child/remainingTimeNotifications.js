import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import {ReminderSchedule, notificationPreferences, reminderSeconds, reminderText} from './notificationLogic.mjs';
import {showReminderBanner} from './reminderBanner.js';

const BUS = 'com.puffyslippers.OhNoParentControl1';

/** Own only this extension's Shell notifications, never other apps' banners. */
export class RemainingTimeNotifications {
    constructor(title, logoPath, translations, onError, changed) {
        this.title = title;
        this.icon = new Gio.FileIcon({file: Gio.File.new_for_path(logoPath)});
        this.translations = translations;
        this.onError = onError;
        this.changed = changed;
        this.schedule = new ReminderSchedule();
        this.preferences = null;
        this.source = null;
        this.current = null;
        this.closed = false;
        this.pending = false;
        this.delivery = 0;
        this.cancellable = new Gio.Cancellable();
    }

    refresh() {
        if (this.closed || this.pending) return;
        this.pending = true;
        Gio.DBus.system.call(BUS, '/com/puffyslippers/OhNoParentControl1', BUS,
            'GetOwnNotifications', null, new GLib.VariantType('(s)'), Gio.DBusCallFlags.NONE,
            5000, this.cancellable, (connection, result) => {
                this.pending = false;
                if (this.closed) return;
                try {
                    const [encoded] = connection.call_finish(result).deep_unpack();
                    const preferences = notificationPreferences(JSON.parse(encoded));
                    // Delivery belongs to a threshold as well as an ID. Editing
                    // a delivered reminder must not suppress its new, later
                    // threshold; text/language edits must not replay it.
                    const previous = new Map(this.preferences?.reminders.map(reminder =>
                        [reminder.id, reminderSeconds(reminder)]) ?? []);
                    const unchanged = new Set(preferences.reminders.filter(reminder =>
                        previous.get(reminder.id) === reminderSeconds(reminder))
                        .map(reminder => reminder.id));
                    this.schedule.delivered = new Set([...this.schedule.delivered]
                        .filter(id => unchanged.has(id)));
                    this.preferences = preferences;
                    if (this.deliveryReminder && !preferences.reminders.some(reminder =>
                        JSON.stringify(reminder) === JSON.stringify(this.deliveryReminder)))
                        this.clear();
                    if (this.current) {
                        const saved = this.preferences.reminders.find(reminder =>
                            reminder.id === this.current.reminder.id);
                        if (!saved || JSON.stringify(saved) !== JSON.stringify(this.current.reminder))
                            this.clear();
                        else {
                            this.current.urgency = this.preferences.show_in_fullscreen ? 'critical' : 'high';
                            this.current.notification.urgency = this.preferences.show_in_fullscreen
                                ? MessageTray.Urgency.CRITICAL : MessageTray.Urgency.HIGH;
                            this.current.notification.body = reminderText(saved, this.translations,
                                this.current.allowSoftApps);
                        }
                    }
                    this.changed();
                } catch (error) {
                    // Preserve the last saved configuration on read failure.
                    this.onError?.(error);
                }
            });
    }

    update(remaining, active) {
        if (this.closed) return;
        if (!active) {
            this.clear();
            this.schedule.previous = null;
            return;
        }
        if (!this.preferences) return;
        if (this.schedule.previous !== null && remaining > this.schedule.previous + 2)
            this.clear(); // A renewed allowance makes the previous warning stale.
        const reminder = this.schedule.update(this.preferences.reminders, remaining, active);
        if (!reminder) return;
        try {
            this.show(reminder);
        } catch (error) {
            // Notification failures must never interrupt countdown or locking.
            this.clear();
            this.onError?.(error);
        }
    }

    nextDelay(remaining, fallback) {
        return this.preferences
            ? this.schedule.nextDelay(this.preferences.reminders, remaining, fallback) : fallback;
    }

    show(reminder) {
        this.clear();
        if (reminderSeconds(reminder) >= 60 || reminder.text.trim()) {
            this.present(reminder, false);
            return;
        }
        this.deliveryReminder = reminder;
        const delivery = this.delivery;
        Gio.DBus.system.call(BUS, '/com/puffyslippers/OhNoParentControl1', BUS,
            'GetOwnSessionAllowsSoftApps', null, new GLib.VariantType('(b)'),
            Gio.DBusCallFlags.NONE, 5000, this.cancellable, (connection, result) => {
                if (this.closed || delivery !== this.delivery) return;
                this.deliveryReminder = null;
                let allowSoftApps = false;
                try {
                    [allowSoftApps] = connection.call_finish(result).deep_unpack();
                } catch (error) {
                    this.onError?.(error);
                }
                try {
                    this.present(reminder, allowSoftApps);
                } catch (error) {
                    this.clear();
                    this.onError?.(error);
                }
            });
    }

    present(reminder, allowSoftApps) {
        const body = reminderText(reminder, this.translations, allowSoftApps);
        const urgency = this.preferences.show_in_fullscreen ? 'critical' : 'high';
        const {source, notification} = showReminderBanner(this.title, this.icon, body,
            urgency === 'critical' ? MessageTray.Urgency.CRITICAL : MessageTray.Urgency.HIGH);
        this.source = source;
        source.connect('destroy', () => {
            if (this.source === source) this.source = null;
        });
        this.current = {notification, reminder, urgency, allowSoftApps, seconds: reminderSeconds(reminder)};
        notification.connect('destroy', () => {
            if (this.current?.notification === notification) this.current = null;
        });
    }

    clear() {
        this.delivery++;
        this.deliveryReminder = null;
        const source = this.source;
        this.source = null;
        this.current = null;
        source?.destroy();
    }

    close() {
        if (this.closed) return;
        this.closed = true;
        this.cancellable.cancel();
        this.clear();
        this.translations = null;
        this.onError = null;
        this.changed = null;
    }
}
