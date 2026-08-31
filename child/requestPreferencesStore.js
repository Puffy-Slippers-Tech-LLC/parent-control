import {
    MAX_CUSTOM_MINUTES,
    MIN_CUSTOM_MINUTES,
} from './requestOptions.js';
import {
    getSharedPreferences,
    updateSharedRequestPreferences,
} from './sharedPreferencesClient.js';
import {logWarning} from './logger.js';

function request() {
    return getSharedPreferences().request;
}

function saveRequest(overrides) {
    const value = {...request(), ...overrides};
    updateSharedRequestPreferences(
        value.last_selected_duration,
        value.last_custom_minutes,
        value.allow_soft_blocked_apps).catch(error =>
        logWarning(`could not save request preferences: ${error.message}`));
}

export function loadLastCustomMinutes() {
    const minutes = Number(request().last_custom_minutes);
    return Number.isFinite(minutes) &&
        minutes >= MIN_CUSTOM_MINUTES && minutes <= MAX_CUSTOM_MINUTES
        ? minutes
        : MIN_CUSTOM_MINUTES;
}

export function saveLastCustomMinutes(minutes) {
    if (!Number.isFinite(minutes) ||
        minutes < MIN_CUSTOM_MINUTES || minutes > MAX_CUSTOM_MINUTES)
        return;

    saveRequest({last_custom_minutes: minutes});
}

export function loadLastSelectedDuration() {
    const duration = request().last_selected_duration;
    return duration === 'custom' || /^\d+$/.test(duration ?? '') ? duration : null;
}

export function saveLastSelectedDuration(seconds) {
    if (seconds !== null && (!Number.isSafeInteger(seconds) || seconds < 0))
        return;

    saveRequest({last_selected_duration: seconds === null ? 'custom' : String(seconds)});
}

export function loadAllowSoftBlockedApps() {
    return request().allow_soft_blocked_apps === true;
}

export function saveAllowSoftBlockedApps(allow) {
    saveRequest({allow_soft_blocked_apps: Boolean(allow)});
}

export function saveRequestPreferences(seconds, customMinutes, allowSoft) {
    if (seconds !== null && (!Number.isSafeInteger(seconds) || seconds < 0))
        return;
    if (!Number.isFinite(customMinutes) ||
        customMinutes < MIN_CUSTOM_MINUTES || customMinutes > MAX_CUSTOM_MINUTES)
        return;
    saveRequest({
        last_selected_duration: seconds === null ? 'custom' : String(seconds),
        last_custom_minutes: customMinutes,
        allow_soft_blocked_apps: Boolean(allowSoft),
    });
}
