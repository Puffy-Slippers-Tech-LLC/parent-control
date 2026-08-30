import Gio from 'gi://Gio';
import GioUnix from 'gi://GioUnix';
import GLib from 'gi://GLib';

function desktopDirectories() {
    const directories = [
        GLib.build_filenamev([GLib.get_user_data_dir(), 'applications']),
        ...GLib.get_system_data_dirs().map(directory =>
            GLib.build_filenamev([directory, 'applications'])),
        '/var/lib/flatpak/exports/share/applications',
        GLib.build_filenamev([GLib.get_home_dir(), '.local/share/flatpak/exports/share/applications']),
        '/var/lib/snapd/desktop/applications',
    ];
    return [...new Set(directories)];
}

function scanDesktopFiles(directory, results) {
    const root = Gio.File.new_for_path(directory);
    let enumerator;
    try {
        enumerator = root.enumerate_children(
            'standard::name,standard::type', Gio.FileQueryInfoFlags.NONE, null);
    } catch (error) {
        return;
    }

    let info;
    while ((info = enumerator.next_file(null))) {
        const child = root.get_child(info.get_name());
        if (info.get_file_type() === Gio.FileType.DIRECTORY)
            scanDesktopFiles(child.get_path(), results);
        else if (info.get_name().endsWith('.desktop')) {
            const app = GioUnix.DesktopAppInfo.new_from_filename(child.get_path());
            if (app)
                results.push(app);
        }
    }
    enumerator.close(null);
}

function resolveExecutable(app) {
    const executable = app.get_executable?.();
    if (!executable)
        return null;
    const resolved = GLib.path_is_absolute(executable)
        ? GLib.canonicalize_filename(executable, null)
        : GLib.find_program_in_path(executable);

    // Blocking a generic launcher would unintentionally block many unrelated
    // apps. Desktop entries which only expose a wrapper are omitted unless a
    // Flatpak ID supplies an app-specific target above.
    const genericLaunchers = new Set([
        '/usr/bin/env', '/bin/sh', '/usr/bin/sh', '/bin/bash', '/usr/bin/bash',
        '/usr/bin/flatpak', '/usr/bin/snap',
    ]);
    return genericLaunchers.has(resolved) ? null : resolved;
}

function appTargets(app) {
    const flatpakId = app.get_string?.('X-Flatpak');
    if (flatpakId?.includes('.'))
        return [flatpakId];

    const executable = resolveExecutable(app);
    return executable ? [executable] : [];
}

export function listLaunchableApps() {
    const candidates = [...Gio.AppInfo.get_all()];
    for (const directory of desktopDirectories())
        scanDesktopFiles(directory, candidates);

    const apps = new Map();
    for (const app of candidates) {
        if (!app.should_show?.())
            continue;
        const id = app.get_id?.();
        const name = app.get_display_name?.() ?? app.get_name?.();
        const targets = appTargets(app);
        if (!id || !name || targets.length === 0)
            continue;

        const existing = apps.get(id);
        if (existing) {
            existing.targets = [...new Set([...existing.targets, ...targets])];
            continue;
        }
        apps.set(id, {
            id,
            name,
            description: app.get_description?.() ?? '',
            icon: app.get_icon?.() ?? null,
            targets,
        });
    }
    return [...apps.values()].sort((a, b) =>
        a.name.localeCompare(b.name, undefined, {sensitivity: 'base'}));
}
