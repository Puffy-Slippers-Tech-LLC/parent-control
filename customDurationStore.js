import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const DIRECTORY_NAME = 'oh-no-parent-control';
const CUSTOM_MINUTES_FILE_NAME = 'last-custom-minutes';
const SELECTED_DURATION_FILE_NAME = 'last-selected-duration';

function getStoreFile(fileName) {
    const directory = GLib.build_filenamev([
        GLib.get_user_data_dir(),
        DIRECTORY_NAME,
    ]);
    return Gio.File.new_for_path(GLib.build_filenamev([directory, fileName]));
}

function load(fileName) {
    try {
        const [, contents] = getStoreFile(fileName).load_contents(null);
        return new TextDecoder().decode(contents).trim();
    } catch (error) {
        if (!error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND))
            console.warn(`[oh-no-parent-control] could not load stored value: ${error.message}`);
        return null;
    }
}

function save(fileName, value) {
    try {
        const file = getStoreFile(fileName);
        GLib.mkdir_with_parents(file.get_parent().get_path(), 0o700);
        file.replace_contents(
            new TextEncoder().encode(value),
            null,
            false,
            Gio.FileCreateFlags.REPLACE_DESTINATION,
            null);
    } catch (error) {
        console.warn(`[oh-no-parent-control] could not save stored value: ${error.message}`);
    }
}

export function loadLastCustomMinutes() {
    const minutes = Number(load(CUSTOM_MINUTES_FILE_NAME));
    return Number.isSafeInteger(minutes) && minutes > 0 ? minutes : 1;
}

export function saveLastCustomMinutes(minutes) {
    if (!Number.isSafeInteger(minutes) || minutes <= 0)
        return;

    save(CUSTOM_MINUTES_FILE_NAME, String(minutes));
}

export function loadLastSelectedDuration() {
    const duration = load(SELECTED_DURATION_FILE_NAME);
    return duration === 'custom' || /^\d+$/.test(duration ?? '') ? duration : null;
}

export function saveLastSelectedDuration(seconds) {
    if (seconds !== null && (!Number.isSafeInteger(seconds) || seconds < 0))
        return;

    save(SELECTED_DURATION_FILE_NAME, seconds === null ? 'custom' : String(seconds));
}
