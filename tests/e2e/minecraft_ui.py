"""Supplied system Flatpak Minecraft launcher: signed-out entry and UI18 exit.

CEF exposes English public semantics without usable automation IDs. Flatpak's
live instance metadata binds its proxied AT-SPI owner; process presence is never
an app-access result. Normal window closure uses the shared guarded worker.
"""
import configparser
import os
from pathlib import Path
import pwd
import re
import subprocess

from lunar_profile_guest import MINECRAFT, MINECRAFT_COMMIT


def run(ui, operation, require, require_session):
    from gi.repository import Gio, GLib

    account = pwd.getpwnam('onpc-child-jordan')
    require(os.getuid() == os.geteuid() == account.pw_uid, 'ui:minecraft-account')
    require_session(unlocked=True)
    require(not ui.input_uncertain, 'ui:uncertain-input')
    ui.timeout = 180

    def owner(app):
        pid = app.get_process_id()
        require(type(pid) is int and pid > 0, 'ui:minecraft-owner')
        process = Path('/proc') / str(pid)
        try:
            before = (process / 'stat').read_text().rpartition(') ')[2].split()
            require(process.stat().st_uid == account.pw_uid, 'ui:minecraft-owner')
            try:
                raw = (process / 'root/.flatpak-info').read_text()
            except FileNotFoundError:
                raw = None
            after = (process / 'stat').read_text().rpartition(') ')[2].split()
            require(before[0] != 'Z' and after[0] != 'Z' and before[19] == after[19],
                    'ui:minecraft-owner-changed')
        except FileNotFoundError:
            require(False, 'ui:incomplete-tree')
        if raw is None:
            return None
        require(0 < len(raw) <= 65536, 'ui:minecraft-owner')
        info = configparser.ConfigParser(interpolation=None)
        info.read_string(raw)
        if info.get('Application', 'name') != MINECRAFT:
            return None
        instance = info['Instance']
        require(app.get_name() == 'Chromium'
                and info.get('Application', 'runtime') ==
                    'runtime/org.freedesktop.Platform/x86_64/25.08'
                and instance.get('arch') == 'x86_64' and instance.get('branch') == 'stable'
                and instance.get('app-commit') == MINECRAFT_COMMIT
                and instance.get('app-path') == '/var/lib/flatpak/app/' + MINECRAFT
                    + '/x86_64/stable/' + MINECRAFT_COMMIT + '/files'
                and re.fullmatch(r'[0-9]+', instance.get('instance-id', ''))
                and instance.get('flatpak-version') == '1.16.6', 'ui:minecraft-system-owner')
        require((process / 'root/.flatpak-info').read_text() == raw,
                'ui:minecraft-owner-changed')
        return [pid, before[19], instance['instance-id']]

    def applications():
        root = ui.api.get_desktop(0)
        require(root is not None, 'ui:incomplete-tree')
        count = root.get_child_count()
        require(0 <= count <= 64, 'ui:incomplete-tree')
        apps = [root.get_child_at_index(index) for index in range(count)]
        require(all(app is not None for app in apps), 'ui:incomplete-tree')
        matches = []
        for app in apps:
            pin = owner(app)
            if pin is not None:
                matches.append((app, pin))
        require(len(matches) <= 1, 'ui:minecraft-ambiguous-application')
        return matches

    def absent():
        require_session(unlocked=True)
        ui.handle_system_prompt()
        return not applications()

    def window(*, closing=False):
        require_session(unlocked=True)
        ui.handle_system_prompt()
        matches = applications()
        if not matches:
            return None
        app, pin = matches[0]
        nodes = list(ui.nodes(app, strict=True))
        require(not any(node.get_role_name() == 'password text' for node in nodes),
                'ui:minecraft-password-surface')
        frames = [node for node in nodes if node.get_role_name() == 'frame' and ui.showing(node)]
        if len(frames) != 1:
            return None
        names = {(node.get_role_name(), node.get_name()) for node in nodes if ui.showing(node)}
        if not {('document web', 'Minecraft Launcher'), ('button', 'SIGN IN'),
                ('toggle button', 'English - United States'), ('static', '3.43.21')} <= names:
            return None
        if closing and not ui.has_state(frames[0], ui.api.StateType.ACTIVE):
            return None
        require(owner(app) == pin, 'ui:minecraft-owner-changed')
        sources = Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack()
        require([list(source) for source in sources] == [['xkb', 'us']],
                'ui:minecraft-keyboard')
        return {'owner': pin, 'window': [frames[0].bus, frames[0].path],
                'provider': {'version': '3.43.21', 'flatpak': '1.16.6',
                             'locale': 'en-US', 'keyboard': [['xkb', 'us']]}}

    if operation == 'minecraft-observer-ready':
        ui.handle_system_prompt()
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        ui.input_uncertain = True
        bus.call_sync('org.a11y.Bus', '/org/a11y/bus', 'org.freedesktop.DBus.Properties',
            'Set', GLib.Variant('(ssv)', ('org.a11y.Status', 'ScreenReaderEnabled',
                                        GLib.Variant('b', True))),
            None, Gio.DBusCallFlags.NO_AUTO_START, 5000, None)
        ui.input_uncertain = False
    elif operation in ('minecraft-launch', 'minecraft-command-blocked'):
        ui.wait(absent, 'minecraft-before-launch', prompt_in_predicate=True)
        ui.prepare_launch_desktop()
        require(absent(), 'ui:minecraft-before-launch')
        ui.input_uncertain = True
        blocked = operation == 'minecraft-command-blocked'
        result = subprocess.run(['/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            *(['--wait', '--pipe'] if blocked else []),
            '--service-type=exec', '/usr/bin/flatpak', 'run', '--branch=stable',
            '--arch=x86_64', '--command=minecraft', MINECRAFT],
            stdin=subprocess.DEVNULL, capture_output=True, check=not blocked, timeout=15)
        if blocked:
            denial = ('Running app/' + MINECRAFT + '/x86_64/stable is not allowed '
                      'by the policy set by your administrator').encode()
            require(result.returncode == 1 and len(result.stdout) + len(result.stderr) <= 65536
                    and denial in result.stderr, 'ui:minecraft-execution-denial')
            ui.input_uncertain = False
            return {'denial': 'administrator-policy'}
        ui.input_uncertain = False
    elif operation in ('minecraft-opened', 'minecraft-close-ready'):
        return ui.wait(lambda: window(closing=operation == 'minecraft-close-ready'),
                       'minecraft-usable', prompt_in_predicate=True)
    elif operation == 'minecraft-closed':
        ui.wait(absent, 'minecraft-complete-absence', prompt_in_predicate=True)
    else:
        require(False, 'ui:minecraft-operation')
