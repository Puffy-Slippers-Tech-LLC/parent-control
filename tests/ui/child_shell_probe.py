#!/usr/bin/env python3
"""Wait for the isolated Shell, extension, and semantic indicator readiness."""

from __future__ import annotations

import os
import sys
import time

import gi

gi.require_version("Atspi", "2.0")
gi.require_version("Gio", "2.0")
from gi.repository import Atspi, Gio, GLib

from tests.support.automation import Automation, AutomationError


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
EVENTS = (
    "object:children-changed",
    "object:property-change:accessible-name",
    "object:state-changed:showing",
    "window:create",
)
LAST_EXTENSION_INFO: object = "not queried"
LAST_ACCESSIBLE_NAME = "not found"
REQUEST_BUTTON_ID = "child-request-button"
UI = Automation(Atspi, lambda: Atspi.get_desktop(0), query_errors=(GLib.Error,))


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
    global LAST_ACCESSIBLE_NAME
    try:
        node = UI.find(REQUEST_BUTTON_ID)
        if node is None:
            return None
        # Shell's Clutter bridge exposes VISIBLE for panel actors in the
        # devkit compositor, while SHOWING remains false for the whole
        # offscreen stage. Resolve the product control by ID first; its name is
        # only a post-lookup meaning/result check.
        if not node.get_state_set().contains(Atspi.StateType.VISIBLE):
            return None
        name = node.get_name() or ""
        if not is_expected_accessible_name(name):
            return None
        LAST_ACCESSIBLE_NAME = name
        return node
    except (AutomationError, AttributeError, GLib.Error):
        return None


def _accessibility_diagnostics() -> dict[str, object]:
    relevant_nodes = []
    for identity in (
        "child-screen-time-indicator", "child-remaining-time", REQUEST_BUTTON_ID,
        "child-request-tooltip", "child-countdown-menu",
        "child-countdown-animation-toggle",
    ):
        try:
            matches = UI.find_all(identity)
            relevant_nodes.extend({
                "id": identity,
                "showing": node.get_state_set().contains(Atspi.StateType.SHOWING),
                "visible": node.get_state_set().contains(Atspi.StateType.VISIBLE),
            } for node in matches)
        except (AutomationError, AttributeError, GLib.Error):
            continue
    return {
        "identified_nodes": relevant_nodes,
    }


def main() -> int:
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

    listener = Atspi.EventListener.new(wake)
    registered_events = [event for event in EVENTS if listener.register(event)]
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
        for event in registered_events:
            listener.deregister(event)

    if not all(state.values()):
        missing = ", ".join(name for name, ready in state.items() if not ready)
        print(f"Timed out waiting for child Shell readiness: {missing}", file=sys.stderr)
        print(f"Extension info: {LAST_EXTENSION_INFO!r}", file=sys.stderr)
        print(
            f"Redacted accessibility summary: {_accessibility_diagnostics()!r}",
            file=sys.stderr,
        )
        return 1
    print(f"Child Shell ready; accessible request name: {LAST_ACCESSIBLE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
