"""Explicit Lunar 3.7.36/AppImageLauncher provider; no game or vendor login.

The supplied original AppImage owns an AppImageLauncher bypass parent and one
Electron application. Public AT-SPI content and the status-notifier/dbusmenu
interfaces supply results and normal Quit. Process metadata only binds owners.
"""
import hashlib
import os
from pathlib import Path
import pwd
import subprocess

from lunar_profile_guest import APPIMAGE, APPIMAGE_SHA256


def run(ui, operation, require, require_session):
    from gi.repository import Gio, GLib

    account = pwd.getpwnam('onpc-child-jordan')
    require(os.getuid() == os.geteuid() == account.pw_uid, 'ui:lunar-account')
    require_session(unlocked=True)
    require(not ui.input_uncertain, 'ui:uncertain-input')
    # Startup and public document discovery are functional waits, not measured
    # product latency. Leave room for a slow guest without delaying ready reads.
    ui.timeout = 180
    original = Path(account.pw_dir) / APPIMAGE
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def call(destination, path, interface, method, signature='', args=()):
        value = bus.call_sync(destination, path, interface, method,
            GLib.Variant('(' + signature + ')', args) if signature else None,
            None, Gio.DBusCallFlags.NO_AUTO_START, 5000, None).unpack()
        return value[0] if len(value) == 1 else value

    def bus_owner(name):
        owner = call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                     'org.freedesktop.DBus', 'GetNameOwner', 's', (name,))
        pid = call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                   'org.freedesktop.DBus', 'GetConnectionUnixProcessID', 's', (owner,))
        return owner, pid

    def identity(pid):
        try:
            return process_identity(pid)
        except FileNotFoundError:
            require(False, 'ui:incomplete-tree')

    def process_identity(pid):
        proc = Path('/proc') / str(pid)
        info = proc.stat()
        fields = (proc / 'stat').read_text().rpartition(') ')[2].split()
        require(info.st_uid == account.pw_uid, 'ui:lunar-owner')
        parent = Path('/proc') / fields[1]
        before = (parent / 'stat').read_text().rpartition(') ')[2].split()[19]
        require(parent.stat().st_uid == account.pw_uid, 'ui:lunar-owner')
        command = (parent / 'cmdline').read_bytes().split(b'\0')
        bypass = '/opt/appimagelauncher.AppDir/usr/lib/x86_64-linux-gnu/appimagelauncher/binfmt-bypass'
        require(str((parent / 'exe').readlink()) == bypass
                and command[:3] == [bypass.encode(), str(original).encode(), b'--no-sandbox']
                and command[3:] in ([b''], [b'--hidden', b'']), 'ui:lunar-original-owner')
        executable = (proc / 'exe').readlink()
        require(executable.parent.parent == Path('/tmp')
                and executable.parent.name.startswith('.mount_Lunar ')
                and executable.name == 'lunarclient', 'ui:lunar-executable')
        require((parent / 'stat').read_text().rpartition(') ')[2].split()[19] == before
                and (proc / 'stat').read_text().rpartition(') ')[2].split()[19] == fields[19],
                'ui:lunar-owner-changed')
        return pid, fields[19], int(fields[1])

    def applications():
        root = ui.api.get_desktop(0)
        require(root is not None, 'ui:incomplete-tree')
        apps = [root.get_child_at_index(index) for index in range(root.get_child_count())]
        require(len(apps) <= 64 and all(app is not None for app in apps), 'ui:incomplete-tree')
        matches = [app for app in apps if app.get_name() == 'lunarclient']
        require(len(matches) <= 1, 'ui:lunar-ambiguous-application')
        for app in matches:
            identity(app.get_process_id())
        return matches

    def tray():
        watcher = 'org.kde.StatusNotifierWatcher'
        owner, pid = bus_owner(watcher)
        require(Path('/proc', str(pid)).stat().st_uid == account.pw_uid, 'ui:lunar-tray-owner')
        entries = call(owner, '/StatusNotifierWatcher', 'org.freedesktop.DBus.Properties',
                       'Get', 'ss', (watcher, 'RegisteredStatusNotifierItems'))
        require(type(entries) in (tuple, list) and len(entries) <= 64
                and len(set(entries)) == len(entries), 'ui:lunar-tray-inventory')
        matches = []
        for entry in entries:
            if '@/' in entry:
                name, path = entry.split('@', 1)
            else:
                name, separator, suffix = entry.partition('/')
                path = '/' + suffix if separator else '/StatusNotifierItem'
            item_owner, item_pid = bus_owner(name)
            props = call(item_owner, path, 'org.freedesktop.DBus.Properties',
                         'GetAll', 's', ('org.kde.StatusNotifierItem',))
            if str(props.get('Id', '')).startswith('lunarclient_status_icon_'):
                require(props['Id'] == 'lunarclient_status_icon_1'
                        and props.get('Menu') == '/com/canonical/dbusmenu', 'ui:lunar-tray-binding')
                matches.append((item_owner, identity(item_pid), props['Menu']))
        require(bus_owner(watcher) == (owner, pid)
                and call(owner, '/StatusNotifierWatcher', 'org.freedesktop.DBus.Properties',
                         'Get', 'ss', (watcher, 'RegisteredStatusNotifierItems')) == entries,
                'ui:lunar-tray-changed')
        require(len(matches) <= 1, 'ui:lunar-ambiguous-tray')
        return matches

    def window(settings=False):
        settings_open = prompt_guard() is not None
        if settings_open != settings:
            return None
        apps = applications()
        if not apps:
            return None
        app = apps[0]
        pin = identity(app.get_process_id())
        nodes = list(ui.nodes(app, strict=True))
        frames = [node for node in nodes if node.get_role_name() == 'frame' and ui.showing(node)]
        # Startup briefly exposes the retiring splash and the new Home frame.
        # A read-only wait may reacquire them; no ambiguous tree can establish
        # readiness or authorize input. Persistent ambiguity times out.
        if len(frames) != 1:
            return None
        names = {(node.get_role_name(), node.get_name()) for node in nodes if ui.showing(node)}
        usable = ({('entry', 'Search settings...'), ('button', 'Lunar Client General')}
                  if settings else {('static', 'Welcome Back Astronaut'), ('static', 'Click to Login')})
        if not usable <= names:
            return None
        require(identity(app.get_process_id()) == pin, 'ui:lunar-owner-changed')
        items = tray()
        require(len(items) == 1 and items[0][1] == pin, 'ui:lunar-window-tray-owner')
        return True

    def absent():
        require_session(unlocked=True)
        prompt_guard()
        return not applications() and not tray()

    def prompt_guard():
        # Settings is an ordinary non-secret Chromium dialog. Recognize only
        # this owned, complete surface; the shared guard still rejects every
        # other modal, authentication title and password control.
        settings = []
        for app in applications():
            pin = identity(app.get_process_id())
            for node in ui.nodes(app, strict=True):
                if node.get_role_name() != 'dialog' or not ui.showing(node):
                    continue
                names = {(child.get_role_name(), child.get_name())
                         for child in ui.nodes(node, strict=True) if ui.showing(child)}
                if {('entry', 'Search settings...'),
                        ('button', 'Lunar Client General')} <= names:
                    settings.append(node)
            require(identity(app.get_process_id()) == pin, 'ui:lunar-owner-changed')
        require(len(settings) <= 1, 'ui:lunar-ambiguous-settings')
        surface = settings[0] if settings else None
        ui.handle_system_prompt(nonsecret_surface=surface)
        return surface

    def menu_action(label):
        def ready():
            prompt_guard()
            return tray()
        items = ui.wait(ready, 'lunar-tray', prompt_in_predicate=True)
        owner, pin, path = items[0]
        revision, layout = call(owner, path, 'com.canonical.dbusmenu', 'GetLayout', 'iias', (0, -1, []))
        entries = [entry for entry in layout[2] if entry[1].get('label') == label
                   and entry[1].get('visible', True) and entry[1].get('enabled', True)]
        require(len(entries) == 1, 'ui:lunar-menu-target')
        require_session(unlocked=True)
        prompt_guard()
        require(tray() == items and identity(pin[0]) == pin, 'ui:lunar-owner-changed')
        ui.input_uncertain = True
        call(owner, path, 'com.canonical.dbusmenu', 'Event', 'isvu',
             (entries[0][0], 'clicked', GLib.Variant('i', 0), 0))
        ui.input_uncertain = False

    if operation == 'lunar-observer-ready':
        # Activate the provider's ordinary accessibility service before reading
        # Chromium's document. This changes no launcher or product setting.
        prompt_guard()
        ui.input_uncertain = True
        call('org.a11y.Bus', '/org/a11y/bus', 'org.freedesktop.DBus.Properties',
             'Set', 'ssv', ('org.a11y.Status', 'ScreenReaderEnabled', GLib.Variant('b', True)))
        ui.input_uncertain = False
    elif operation == 'lunar-launch':
        ui.wait(absent, 'lunar-before-launch', prompt_in_predicate=True)
        require(original.is_file() and not original.is_symlink()
                and original.stat().st_uid == account.pw_uid
                and hashlib.sha256(original.read_bytes()).hexdigest() == APPIMAGE_SHA256,
                'ui:lunar-original-input')
        ui.prepare_launch_desktop()
        require(absent(), 'ui:lunar-before-launch')
        ui.input_uncertain = True
        subprocess.run(['/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', str(original), '--no-sandbox'],
            stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15)
        ui.input_uncertain = False
    elif operation == 'lunar-opened':
        ui.wait(window, 'lunar-usable', prompt_in_predicate=True)
    elif operation == 'lunar-settings':
        ui.wait(window, 'lunar-usable', prompt_in_predicate=True)
        menu_action('Settings')
    elif operation == 'lunar-settings-opened':
        ui.wait(lambda: window(settings=True), 'lunar-settings', prompt_in_predicate=True)
    elif operation == 'lunar-quit':
        menu_action('Quit Launcher')
    elif operation == 'lunar-closed':
        ui.wait(absent, 'lunar-complete-absence', prompt_in_predicate=True)
    else:
        require(False, 'ui:lunar-operation')
