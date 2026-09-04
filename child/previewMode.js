import GLib from 'gi://GLib';

export function isPreview() {
    return GLib.getenv('OH_NO_PARENT_CONTROL_PREVIEW') === '1';
}

export function previewStartsWithRequestOpen() {
    return isPreview() &&
        GLib.getenv('OH_NO_PARENT_CONTROL_PREVIEW_SCENARIO') !==
            'indicator-interaction';
}

// This is intentionally a source constant, rather than an environment value.
// The component reload test changes it only in its disposable payload copy and
// observes the new accessible marker after the next Shell generation starts.
export function previewGenerationMarker() {
    return isPreview() ? 'generation-one' : '';
}
