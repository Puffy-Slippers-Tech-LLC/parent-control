import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const DIRECTORY_NAME = 'oh-no-parent-control';
const FILE_NAME = 'app-policy.json';
const FORMAT_VERSION = 1;
const VALID_STATES = new Set(['allowed', 'permanent', 'conditional']);

export function isValidAppTarget(target) {
    if (typeof target !== 'string')
        return false;
    if (target.startsWith('/'))
        return true;

    const parts = target.split('/');
    return parts.length === 4 && parts[0] === 'app' &&
        parts.slice(1).every(part => part.length > 0);
}

function getPolicyFile() {
    return Gio.File.new_for_path(GLib.build_filenamev([
        GLib.get_user_data_dir(), DIRECTORY_NAME, FILE_NAME,
    ]));
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
    try {
        const [, contents] = getPolicyFile().load_contents(null);
        const parsed = JSON.parse(new TextDecoder().decode(contents));
        if (parsed?.version !== FORMAT_VERSION ||
            !parsed.apps || typeof parsed.apps !== 'object')
            throw new Error('unsupported app-policy format');

        const apps = {};
        for (const [id, entry] of Object.entries(parsed.apps)) {
            const normalized = normalizeEntry(entry);
            if (id && normalized)
                apps[id] = normalized;
        }
        return {version: FORMAT_VERSION, apps};
    } catch (error) {
        if (!error.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND))
            console.warn(`[oh-no-parent-control] could not load app policy: ${error.message}`);
        return {version: FORMAT_VERSION, apps: {}};
    }
}

export function saveAppPolicy(apps) {
    const normalizedApps = {};
    for (const [id, entry] of Object.entries(apps ?? {})) {
        const normalized = normalizeEntry(entry);
        if (id && normalized && normalized.state !== 'allowed')
            normalizedApps[id] = normalized;
    }

    const file = getPolicyFile();
    GLib.mkdir_with_parents(file.get_parent().get_path(), 0o700);
    file.replace_contents(
        new TextEncoder().encode(JSON.stringify({
            version: FORMAT_VERSION,
            apps: normalizedApps,
        }, null, 2)),
        null, false, Gio.FileCreateFlags.REPLACE_DESTINATION, null);
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
