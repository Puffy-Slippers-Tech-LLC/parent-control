"""Discover launchable desktop applications and safe app-filter targets."""

import os
import shlex

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

GENERIC_LAUNCHERS = {
    "/usr/bin/env", "/bin/sh", "/usr/bin/sh", "/bin/bash", "/usr/bin/bash",
    "/usr/bin/flatpak", "/usr/bin/snap",
}


def _target(app):
    flatpak_id = app.get_string("X-Flatpak") if hasattr(app, "get_string") else None
    if flatpak_id and "." in flatpak_id:
        try:
            arguments = shlex.split(app.get_commandline() or "")
        except ValueError:
            return None
        arch = branch = None
        for index, argument in enumerate(arguments):
            if argument.startswith("--arch="):
                arch = argument.partition("=")[2]
            elif argument == "--arch" and index + 1 < len(arguments):
                arch = arguments[index + 1]
            elif argument.startswith("--branch="):
                branch = argument.partition("=")[2]
            elif argument == "--branch" and index + 1 < len(arguments):
                branch = arguments[index + 1]
        return f"app/{flatpak_id}/{arch}/{branch}" if arch and branch else None
    executable = app.get_executable()
    if not executable:
        return None
    resolved = (os.path.realpath(executable) if os.path.isabs(executable)
                else GLib.find_program_in_path(executable))
    return None if resolved in GENERIC_LAUNCHERS else resolved


def list_apps():
    result = {}
    for app in Gio.AppInfo.get_all():
        if not app.should_show():
            continue
        desktop_id = app.get_id()
        target = _target(app)
        if not desktop_id or not desktop_id.endswith(".desktop") or not target:
            continue
        if desktop_id in result:
            result[desktop_id]["targets"] = sorted(set(
                [*result[desktop_id]["targets"], target]
            ))
            continue
        result[desktop_id] = {
            "id": desktop_id,
            "name": app.get_display_name() or app.get_name() or desktop_id,
            "description": app.get_description() or desktop_id,
            "icon": app.get_icon(),
            "targets": [target],
        }
    return sorted(result.values(), key=lambda app: app["name"].casefold())
