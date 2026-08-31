import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

function loadRequestOptions() {
    const [modulePath] = GLib.filename_from_uri(import.meta.url);
    const file = Gio.File.new_for_path(GLib.build_filenamev([
        GLib.path_get_dirname(modulePath),
        'request-options.json',
    ]));
    const [, contents] = file.load_contents(null);
    const options = JSON.parse(new TextDecoder().decode(contents));
    if (!Array.isArray(options.durations) || options.durations.length === 0)
        throw new Error('request-options.json has no durations');
    return options;
}

const OPTIONS = loadRequestOptions();

export const DURATIONS = Object.freeze(OPTIONS.durations.map(duration =>
    Object.freeze({...duration})));
export const DEFAULT_DURATION_SECONDS = OPTIONS.default_duration_seconds;
export const MIN_CUSTOM_MINUTES = OPTIONS.minimum_custom_minutes;
export const MAX_CUSTOM_MINUTES = OPTIONS.maximum_custom_minutes;
