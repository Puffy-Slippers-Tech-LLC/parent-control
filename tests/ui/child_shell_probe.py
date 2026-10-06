#!/usr/bin/env python3
"""Wait for the isolated Shell, extension, and Application UI readiness."""

from __future__ import annotations

import os
import sys
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from tests.support.application_ui import ApplicationUI, UIClientError


UUID = "oh-no-parent-control@tech.puffyslippers.com"
SHELL_NAME = "org.gnome.Shell"
EXTENSIONS_PATH = "/org/gnome/Shell"
EXTENSIONS_INTERFACE = "org.gnome.Shell.Extensions"
ACTIVE_STATE = 1
EXPECTED_ACCESSIBLE_NAMES = {
    "Request time, 00:45",
    "Request time, 00:44",
}
EXPECTED_MARKER = os.environ.get("ONPC_CHILD_SHELL_EXPECTED_MARKER", "")
LAST_EXTENSION_INFO: object = "not queried"
LAST_ACCESSIBLE_NAME = "not found"
REQUEST_BUTTON_ID = "child-request-button"
APPLICATIONS = ApplicationUI()
UI = None


def is_expected_accessible_name(name):
    return any(name.startswith(expected) for expected in EXPECTED_ACCESSIBLE_NAMES) \
        and (not EXPECTED_MARKER or name.endswith(EXPECTED_MARKER))


def _extension_is_active(connection: Gio.DBusConnection) -> bool:
    global LAST_EXTENSION_INFO
    try:
        reply = connection.call_sync(
            SHELL_NAME,
            EXTENSIONS_PATH,
            EXTENSIONS_INTERFACE,
            "GetExtensionInfo",
            GLib.Variant("(s)", (UUID,)),
            GLib.VariantType.new("(a{sv})"),
            Gio.DBusCallFlags.NONE,
            1000,
            None,
        )
    except GLib.Error as error:
        LAST_EXTENSION_INFO = f"query failed: {error.message}"
        return False
    (properties,) = reply.unpack()
    LAST_EXTENSION_INFO = properties
    state = properties.get("state")
    if isinstance(state, GLib.Variant):
        state = state.unpack()
    return state == ACTIVE_STATE


def _find_indicator():
    global LAST_ACCESSIBLE_NAME, UI
    try:
        if UI is None:
            candidate = APPLICATIONS.client("child-panel")
            expected_pid = os.environ.get("ONPC_CHILD_SHELL_PID")
            if expected_pid is not None and candidate.pid != int(expected_pid):
                raise AssertionError("Child panel is not owned by the launched Shell")
            UI = candidate
        node = UI.getElementById(REQUEST_BUTTON_ID)
        if not node.visible:
            return None
        name = node.text
        if not is_expected_accessible_name(name):
            return None
        LAST_ACCESSIBLE_NAME = name
        return node
    except UIClientError as error:
        if error.code not in ("Unavailable", "OwnerChanged"):
            raise
        return None


def _application_ui_diagnostics() -> dict[str, object]:
    relevant_nodes = []
    for identity in (
        "child-screen-time-indicator", "child-remaining-time", REQUEST_BUTTON_ID,
        "child-request-tooltip", "child-countdown-menu",
        "child-countdown-animation-toggle",
    ):
        try:
            if UI is None:
                break
            node = UI.getElementById(identity)
            relevant_nodes.append({
                "id": identity,
                "visible": node.visible,
                "enabled": node.enabled,
            })
        except UIClientError:
            continue
    return {
        "identified_nodes": relevant_nodes,
    }


def _run() -> int:
    timeout_seconds = float(os.environ.get("ONPC_PREVIEW_READY_TIMEOUT_SECONDS", "30"))
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    loop = GLib.MainLoop()
    state = {"shell": False, "extension": False, "indicator": False}

    def inspect_state(*_args):
        state["extension"] = state["shell"] and _extension_is_active(connection)
        state["indicator"] = _find_indicator() is not None
        if all(state.values()):
            loop.quit()
        return GLib.SOURCE_CONTINUE

    def wake(*_args):
        GLib.idle_add(inspect_state)

    def shell_appeared(*_args):
        state["shell"] = True
        wake()

    def shell_vanished(*_args):
        state["shell"] = False
        wake()

    extension_signal = connection.signal_subscribe(
        SHELL_NAME,
        EXTENSIONS_INTERFACE,
        "ExtensionStateChanged",
        EXTENSIONS_PATH,
        UUID,
        Gio.DBusSignalFlags.NONE,
        wake,
    )
    shell_watch = Gio.bus_watch_name_on_connection(
        connection, SHELL_NAME, Gio.BusNameWatcherFlags.NONE,
        shell_appeared, shell_vanished,
    )
    deadline = time.monotonic() + timeout_seconds

    def on_deadline():
        if time.monotonic() >= deadline:
            loop.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    deadline_source = GLib.timeout_add(100, on_deadline)
    inspection_source = GLib.timeout_add(250, inspect_state)
    try:
        inspect_state()
        if not all(state.values()):
            loop.run()
    finally:
        for source in (deadline_source, inspection_source):
            current = GLib.MainContext.default().find_source_by_id(source)
            if current is not None:
                current.destroy()
        Gio.bus_unwatch_name(shell_watch)
        connection.signal_unsubscribe(extension_signal)

    if not all(state.values()):
        missing = ", ".join(name for name, ready in state.items() if not ready)
        print(f"Timed out waiting for child Shell readiness: {missing}", file=sys.stderr)
        print(f"Extension info: {LAST_EXTENSION_INFO!r}", file=sys.stderr)
        print(
            f"Redacted Application UI summary: {_application_ui_diagnostics()!r}",
            file=sys.stderr,
        )
        return 1
    print(f"Child Shell ready; public request text: {LAST_ACCESSIBLE_NAME}")
    return 0


def main() -> int:
    try:
        return _run()
    finally:
        APPLICATIONS.close()


if __name__ == "__main__":
    raise SystemExit(main())
