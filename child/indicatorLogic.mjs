/* Platform-neutral child-extension decisions.  Keep this module free of GNOME
 * imports so its time and state boundaries execute under Node as well as GJS. */

const BUSY_RETRY_DELAYS_MS = Object.freeze([100, 250, 500, 1000, 2000]);

export function remainingSeconds(endTime, currentTime) {
    return Math.ceil(endTime - currentTime);
}

export function displayState({calculatedEnd, currentTime, locked, greeter}) {
    const remaining = remainingSeconds(calculatedEnd, currentTime);
    const visible = !locked && !greeter && remaining > 0;
    return {
        remaining,
        visible,
        shouldLock: !locked && !greeter && remaining <= 0,
        countdown: visible && remaining < 60,
        spinRequestIcon: visible && remaining <= 10,
        nextUpdateSeconds: 1,
    };
}

export function formatRemainingTime(remaining, compact, includeSeconds = false) {
    if (includeSeconds) {
        const seconds = Math.max(0, Math.ceil(remaining));
        return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60]
            .map(value => String(value).padStart(2, '0')).join(':');
    }
    if (remaining > 60) {
        const totalMinutes = Math.floor(remaining / 60);
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        if (compact)
            return hours > 0 ? `${hours}h` : `${minutes}m`;
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
    }
    return `${remaining}`;
}

export function busyRetryDelay(remoteErrorName, attempt) {
    if (!remoteErrorName?.endsWith('.Error.Busy'))
        return undefined;
    return BUSY_RETRY_DELAYS_MS[attempt];
}

export function canOpenRequest(hasProcess, openingRequest) {
    return !hasProcess && !openingRequest;
}

export function requestCompletionState() {
    return {requestActive: false, refreshEstimate: true};
}

export function shouldPrepareSession({preview, destroyed, pending, prepared, locked, greeter}) {
    return !preview && !destroyed && !pending && !prepared && !locked && !greeter;
}
