import GLib from 'gi://GLib';

/* Read the product's shared branding record. */

export function appName(extension) {
    const bundled = extension.dir.get_child('brand.json').get_path();
    const installed = '/usr/share/oh-no-parent-control/brand.json';
    const source = GLib.build_filenamev([extension.path, '..', 'data', 'brand.json']);
    const path = GLib.file_test(bundled, GLib.FileTest.EXISTS) ? bundled
        : GLib.file_test(installed, GLib.FileTest.EXISTS) ? installed : source;
    const [success, contents] = GLib.file_get_contents(path);
    if (!success)
        throw new Error('could not read brand.json');
    const name = JSON.parse(new TextDecoder().decode(contents)).app_name;
    if (typeof name !== 'string' || !name)
        throw new Error('app_name must be a non-empty string');
    return name;
}
