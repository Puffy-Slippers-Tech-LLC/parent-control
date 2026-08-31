import {getSharedPreferences} from './sharedPreferencesClient.js';

const FORMAT_VERSION = 1;
const VALID_STATES = new Set(['allowed', 'permanent', 'conditional']);

export function isValidAppTarget(target) {
    if (typeof target !== 'string')
        return false;
    if (target.startsWith('/'))
        return true;

    const parts = target.split('/');
    if (parts.length === 4 && parts[0] === 'app' &&
        parts.slice(1).every(part => part.length > 0))
        return true;
    return /^[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)+$/.test(target);
}

function normalizeEntry(entry) {
    if (!entry || typeof entry !== 'object' || !VALID_STATES.has(entry.state))
        return null;

    const targets = Array.isArray(entry.targets)
        ? [...new Set(entry.targets.filter(isValidAppTarget))]
        : [];
    return {state: entry.state, targets};
}

export function loadAppPolicy() {
    const apps = {};
    for (const [id, entry] of Object.entries(getSharedPreferences().apps ?? {})) {
        const normalized = normalizeEntry(entry);
        if (id && normalized)
            apps[id] = normalized;
    }
    return {version: FORMAT_VERSION, apps};
}

export function getBlockedTargets(policy, allowSoftBlockedApps) {
    const targets = [];
    for (const entry of Object.values(policy?.apps ?? {})) {
        if (entry.state === 'permanent' ||
            (entry.state === 'conditional' && !allowSoftBlockedApps))
            targets.push(...entry.targets);
    }
    return [...new Set(targets)].sort();
}
