"""Discover desktop launchers for the managed account, not the administrator."""

from __future__ import annotations

import configparser
import os
import pwd
import shlex
import shutil
import re
from pathlib import Path

from .core import UserAccount


GENERIC_LAUNCHERS = {
    "/usr/bin/env", "/bin/sh", "/usr/bin/sh", "/bin/bash", "/usr/bin/bash",
    "/usr/bin/flatpak", "/usr/bin/snap",
}
SYSTEM_APPLICATION_DIRS = (
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
    Path("/var/lib/snapd/desktop/applications"),
)


def suggested_patterns(target: str) -> tuple[str, ...]:
    """Offer a conservative version-stable AppImage filename pattern."""
    if not target.endswith(".AppImage"):
        return ()
    directory, basename = os.path.split(target)
    stem = basename.removesuffix(".AppImage")
    # Replace a dotted version wherever it occurs as a filename component. An
    # updater identifier is often a GUID following a stable label (for example
    # ``-ow_e1eda9...``); replace that identifier too while retaining the label
    # so the suggestion does not match every AppImage in the directory.
    suggested = re.sub(
        r"(?:(?<=^)|(?<=[-_]))v?\d+(?:\.\d+)+(?=$|[-_])", "*", stem,
    )
    with_guid = re.sub(r"(?<=[-_])[0-9A-Fa-f]{8,}(?=$|[-_])", "*", suggested)
    if with_guid == suggested:
        # An unstructured updater suffix (such as ``-abc``) is volatile as a
        # whole. This preserves the existing conservative suggestion.
        suggested = re.sub(r"([_-]\*)(?:[-_][A-Za-z0-9]+)$", r"\1", suggested)
    else:
        suggested = with_guid
    suggested += ".AppImage"
    if suggested == basename:
        return ()
    return (os.path.join(os.path.realpath(directory), suggested),)


def _bool(entry, key):
    return entry.get(key, "").strip().lower() in {"1", "true", "yes"}


def _desktop_id(directory: Path, filename: Path) -> str:
    relative = filename.relative_to(directory)
    return "-".join(relative.parts)


def _launcher_files(directory: Path):
    if not directory.is_dir():
        return
    for root, directories, filenames in os.walk(directory, followlinks=False):
        directories.sort()
        for name in sorted(filenames):
            if not name.endswith(".desktop"):
                continue
            filename = Path(root, name)
            if filename.is_file() and not filename.is_symlink():
                yield filename


def _flatpak_target(entry, arguments):
    flatpak_id = entry.get("X-Flatpak", "")
    if not flatpak_id or "." not in flatpak_id:
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


def _executable_target(entry, home: Path):
    try:
        arguments = shlex.split(entry["Exec"])
    except (KeyError, ValueError):
        return None
    if not arguments:
        return None
    flatpak_target = _flatpak_target(entry, arguments)
    if flatpak_target:
        return flatpak_target
    executable = arguments[0]
    if os.path.isabs(executable):
        resolved = os.path.realpath(executable)
    else:
        working_directory = entry.get("Path", "")
        candidates = []
        if working_directory and os.path.isabs(working_directory):
            candidates.append(Path(working_directory, executable))
        candidates.extend((home / ".local/bin" / executable, home / "bin" / executable))
        resolved = next(
            (os.path.realpath(candidate) for candidate in candidates if candidate.is_file()),
            shutil.which(executable) or "",
        )
    if not resolved or resolved in GENERIC_LAUNCHERS or not os.path.isfile(resolved):
        return None
    return resolved


def _application(filename: Path, desktop_id: str, home: Path):
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(filename, encoding="utf-8")
        entry = parser["Desktop Entry"]
    except (OSError, UnicodeError, configparser.Error, KeyError):
        return None
    if (entry.get("Type") != "Application" or _bool(entry, "Hidden") or
            _bool(entry, "NoDisplay")):
        return None
    target = _executable_target(entry, home)
    if not target:
        return None
    return {
        "id": desktop_id,
        "name": entry.get("Name") or desktop_id,
        "description": entry.get("Comment") or desktop_id,
        "icon": entry.get("Icon", ""),
        "targets": (target,),
        "suggested_patterns": suggested_patterns(target) if target.startswith("/") else (),
    }


def list_apps(user: UserAccount):
    """Return the launchable applications visible to *user*.

    App filters use executable paths (or Flatpak refs), rather than desktop
    IDs.  Reading the target user's XDG application directories is therefore
    both necessary for per-user AppImages and sufficient to create a filter
    Malcontent can enforce.
    """
    try:
        account = pwd.getpwnam(user.username)
    except KeyError:
        return ()
    if account.pw_uid != user.uid:
        return ()
    home = Path(account.pw_dir)
    directories = (
        home / ".local/share/applications",
        home / ".local/share/flatpak/exports/share/applications",
        *SYSTEM_APPLICATION_DIRS,
    )
    result = {}
    for directory in directories:
        for filename in _launcher_files(directory) or ():
            desktop_id = _desktop_id(directory, filename)
            if desktop_id in result:
                continue
            application = _application(filename, desktop_id, home)
            if application:
                result[desktop_id] = application
    return tuple(sorted(result.values(), key=lambda app: app["name"].casefold()))
