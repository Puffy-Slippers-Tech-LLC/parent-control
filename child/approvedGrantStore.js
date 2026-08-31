import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const DIRECTORY_NAME = 'oh-no-parent-control';
const FILE_NAME = 'approved-grant';
const FORMAT_VERSION = 1;

function getStoreFile() {
    const directory = GLib.build_filenamev([
        GLib.get_user_data_dir(),
        DIRECTORY_NAME,
    ]);
    return Gio.File.new_for_path(GLib.build_filenamev([directory, FILE_NAME]));
}

function nowSeconds() {
    return Math.floor(GLib.get_real_time() / GLib.USEC_PER_SEC);
}

function removeStoreFile() {
    try {
        getStoreFile().delete(null);
    } catch (error) {
        if (!error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND))
            console.warn(`[oh-no-parent-control] could not remove expired grant: ${error.message}`);
    }
}

export function saveApprovedGrant(durationSeconds) {
    if (!Number.isSafeInteger(durationSeconds) || durationSeconds <= 0)
        throw new Error('Invalid approved grant duration');

    const issuedAt = nowSeconds();
    const grant = {
        version: FORMAT_VERSION,
        issuedAt,
        durationSeconds,
        expiresAt: issuedAt + durationSeconds,
    };

    try {
        const file = getStoreFile();
        GLib.mkdir_with_parents(file.get_parent().get_path(), 0o700);
        file.replace_contents(
            new TextEncoder().encode(JSON.stringify(grant)),
            null,
            false,
            Gio.FileCreateFlags.REPLACE_DESTINATION,
            null);
        return true;
    } catch (error) {
        // The authenticated Malcontent grant remains valid even if local
        // persistence is unavailable. Keep the in-process guard active.
        console.warn(`[oh-no-parent-control] could not persist approved grant: ${error.message}`);
        return false;
    }
}

export function loadApprovedGrantRemaining() {
    let grant;
    try {
        const [, contents] = getStoreFile().load_contents(null);
        grant = JSON.parse(new TextDecoder().decode(contents));
    } catch (error) {
        if (!error.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND)) {
            console.warn(`[oh-no-parent-control] could not load approved grant: ${error.message}`);
            removeStoreFile();
        }
        return 0;
    }

    const valid = grant?.version === FORMAT_VERSION &&
        Number.isSafeInteger(grant.issuedAt) && grant.issuedAt > 0 &&
        Number.isSafeInteger(grant.durationSeconds) && grant.durationSeconds > 0 &&
        Number.isSafeInteger(grant.expiresAt) &&
        grant.expiresAt === grant.issuedAt + grant.durationSeconds;
    if (!valid) {
        console.warn('[oh-no-parent-control] discarded invalid approved grant record');
        removeStoreFile();
        return 0;
    }

    const remaining = grant.expiresAt - nowSeconds();
    if (remaining <= 0) {
        removeStoreFile();
        return 0;
    }

    // A wall-clock rollback must not turn a persisted grant into more time
    // than the parent approved. The in-process monotonic deadline applies the
    // same upper bound after this value is loaded.
    return Math.min(remaining, grant.durationSeconds);
}

export function clearApprovedGrant() {
    removeStoreFile();
}
