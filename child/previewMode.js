import GLib from 'gi://GLib';

export function isPreview() {
    return GLib.getenv('OH_NO_PARENT_CONTROL_PREVIEW') === '1';
}

export function previewStartsWithRequestOpen() {
    return isPreview() &&
        GLib.getenv('OH_NO_PARENT_CONTROL_PREVIEW_SCENARIO') !==
            'indicator-interaction';
}
