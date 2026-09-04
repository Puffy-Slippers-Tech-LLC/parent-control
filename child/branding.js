import GLib from 'gi://GLib';

/* Read the product's shared branding record. */

function brandingAssetPath(extension, filename) {
    if (!filename || filename.includes('/') || filename.includes('\\'))
        throw new Error('branding asset filename must be a plain filename');
    const bundled = extension.dir.get_child(filename).get_path();
    const installed = `/usr/share/oh-no-parent-control/${filename}`;
    const source = GLib.build_filenamev([extension.path, '..', 'data', filename]);
    return GLib.file_test(bundled, GLib.FileTest.EXISTS) ? bundled
        : GLib.file_test(installed, GLib.FileTest.EXISTS) ? installed : source;
}

export function appName(extension) {
    const path = brandingAssetPath(extension, 'brand.json');
    const [success, contents] = GLib.file_get_contents(path);
    if (!success)
        throw new Error('could not read brand.json');
    const name = JSON.parse(new TextDecoder().decode(contents)).app_name;
    if (typeof name !== 'string' || !name)
        throw new Error('app_name must be a non-empty string');
    return name;
}

export function appLogoPath(extension) {
    const path = brandingAssetPath(extension, 'app_logo.png');
    if (!GLib.file_test(path, GLib.FileTest.IS_REGULAR))
        throw new Error('could not read app_logo.png');
    return path;
}
