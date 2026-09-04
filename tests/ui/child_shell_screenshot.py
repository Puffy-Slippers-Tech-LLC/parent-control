#!/usr/bin/env python3
"""Capture only the private nested GNOME Shell through its public D-Bus API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib


SHELL_NAME = "org.gnome.Shell"
SCREENSHOT_PATH = "/org/gnome/Shell/Screenshot"
SCREENSHOT_INTERFACE = "org.gnome.Shell.Screenshot"
MEDIA_KEYS_NAME = "org.gnome.SettingsDaemon.MediaKeys"


def capture_screenshot(destination: Path) -> None:
    """Write a PNG from the nested Shell bound to this private session bus."""
    artifact_root = Path(os.environ["ONPC_CHILD_SHELL_ARTIFACT_DIR"]).resolve()
    destination = destination.resolve()
    if destination.suffix != ".png" or artifact_root not in destination.parents:
        raise ValueError("Screenshot destination must be a PNG inside the test artifact root")
    destination.parent.mkdir(parents=True, exist_ok=True)

    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    # Shell's public Screenshot interface permits the GNOME Settings Daemon
    # media-keys client and the desktop portal. The isolated session starts
    # neither service, so this one-shot client owns the documented media-keys
    # name on the private bus only. It exports no methods and releases the
    # connection immediately after the capture.
    request = connection.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "RequestName",
        GLib.Variant("(su)", (MEDIA_KEYS_NAME, 0)),
        GLib.VariantType.new("(u)"),
        Gio.DBusCallFlags.NONE,
        1_000,
        None,
    )
    (request_result,) = request.unpack()
    if request_result not in {1, 4}:
        raise RuntimeError("Private screenshot client could not own its public caller name")
    reply = connection.call_sync(
        SHELL_NAME,
        SCREENSHOT_PATH,
        SCREENSHOT_INTERFACE,
        "Screenshot",
        GLib.Variant("(bbs)", (False, False, str(destination))),
        GLib.VariantType.new("(bs)"),
        Gio.DBusCallFlags.NONE,
        10_000,
        None,
    )
    success, recorded_path = reply.unpack()
    if not success or Path(recorded_path) != destination or not destination.is_file():
        raise RuntimeError("Nested Shell Screenshot call did not create the requested PNG")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: child_shell_screenshot.py <artifact-png>", file=sys.stderr)
        return 2
    try:
        capture_screenshot(Path(sys.argv[1]))
    except (GLib.Error, OSError, RuntimeError, ValueError) as error:
        print(f"Nested Shell screenshot failed: {error}", file=sys.stderr)
        return 1
    print("nested-shell screenshot outcome=success error_category=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
