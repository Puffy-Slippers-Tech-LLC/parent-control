/* Reminder decisions shared by Shell and isolated engineering tests. */
export function notificationPreferences(raw) {
    if (!raw || typeof raw.show_in_fullscreen !== 'boolean' ||
        !Array.isArray(raw.reminders) || raw.reminders.length > 64)
        throw new Error('Invalid notification preferences');
    const ids = new Set();
    for (const reminder of raw.reminders) {
        if (!reminder || typeof reminder.id !== 'string' || reminder.id.length > 64 ||
            !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(reminder.id) || ids.has(reminder.id) ||
            !['minute', 'second'].includes(reminder.unit) ||
            !Number.isSafeInteger(reminder.value) || reminder.value <= 0 ||
            reminderSeconds(reminder) > 0xFFFFFFFF || typeof reminder.text !== 'string' ||
            Array.from(reminder.text).length > 4096 || reminder.text.includes('\0'))
            throw new Error('Invalid notification preferences');
        ids.add(reminder.id);
    }
    return raw;
}

export function reminderSeconds(reminder) {
    return reminder.value * (reminder.unit === 'minute' ? 60 : 1);
}

export function reminderText(reminder, translations) {
    if (reminder.text.trim()) return reminder.text;
    const time = translations.text(reminder.unit === 'minute' ? 'MINUTE_COUNT' : 'SECOND_COUNT',
        {count: reminder.value});
    return translations.text('TIME_REMAINING_NOTIFICATION', {time});
}

export class ReminderSchedule {
    constructor() {
        this.previous = null;
        this.delivered = new Set();
    }

    update(reminders, remaining, active) {
        const previous = this.previous;
        this.previous = remaining;
        if (!active || !Number.isFinite(remaining) || remaining <= 0) return null;
        // Do not replay passed reminders at login or when preferences load.
        // If a delayed estimate crosses several, deliver only the nearest one.
        const crossed = reminders.filter(reminder => {
            const seconds = reminderSeconds(reminder);
            // Integer estimates may wobble by a second at query boundaries.
            // Additional usable time above that tolerance rearms the reminder.
            if (remaining > seconds + 2) this.delivered.delete(reminder.id);
            return !this.delivered.has(reminder.id) && remaining <= seconds && (previous === null
                ? remaining === seconds : previous > seconds);
        }).sort((a, b) => reminderSeconds(a) - reminderSeconds(b));
        for (const reminder of crossed) this.delivered.add(reminder.id);
        return crossed[0] ?? null;
    }

    nextDelay(reminders, remaining, fallback) {
        return reminders.reduce((delay, reminder) => {
            const until = remaining - reminderSeconds(reminder);
            return until > 0 ? Math.min(delay, until) : delay;
        }, fallback);
    }
}
