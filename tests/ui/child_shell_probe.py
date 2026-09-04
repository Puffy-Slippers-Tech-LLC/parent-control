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


UUID = "oh-no-parent-control@tech.puffyslippers.com"
SHELL_NAME = "org.gnome.Shell"
EXTENSIONS_PATH = "/org/gnome/Shell"
EXTENSIONS_INTERFACE = "org.gnome.Shell.Extensions"
ACTIVE_STATE = 1
EXPECTED_ACCESSIBLE_NAMES = {
    "Request time, 00:45 left",
    "Request time, 00:44 left",
}
EVENTS = (
    "object:children-changed",
    "object:property-change:accessible-name",
    "object:state-changed:showing",
    "window:create",
)
LAST_EXTENSION_INFO: object = "not queried"
LAST_ACCESSIBLE_NAME = "not found"


def is_expected_accessible_name(name):
    return any(name.startswith(expected) for expected in EXPECTED_ACCESSIBLE_NAMES)


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
    desktop = Atspi.get_desktop(0)
    for application_index in range(desktop.get_child_count()):
        application = desktop.get_child_at_index(application_index)
        if "gnome-shell" not in (application.get_name() or "").lower():
            continue
        queue = [application]
        indicator_visible = False
        request_named = False
        while queue:
            node = queue.pop(0)
            if node is None:
                continue
            name = node.get_name()
            states = node.get_state_set()
            # Shell's Clutter bridge exposes VISIBLE for panel actors in the
            # devkit compositor, while SHOWING remains false for the whole
            # offscreen stage. VISIBLE is therefore the meaningful semantic
            # state for this isolated Shell surface.
            visible = states.contains(Atspi.StateType.VISIBLE)
            if name == "Screen Time Remaining" and visible:
                indicator_visible = True
            if is_expected_accessible_name(name):
                LAST_ACCESSIBLE_NAME = name
                request_named = True
            if indicator_visible and request_named:
                return node
            try:
                queue.extend(
                    node.get_child_at_index(index)
                    for index in range(max(0, node.get_child_count()))
                )
            except (AttributeError, GLib.Error):
                continue
    return None


def _accessibility_diagnostics() -> dict[str, object]:
    application_count = 0
    relevant_nodes = []
    desktop = Atspi.get_desktop(0)
    queue = [
        desktop.get_child_at_index(index)
        for index in range(desktop.get_child_count())
    ]
    application_count = desktop.get_child_count()
    while queue:
        node = queue.pop(0)
        if node is None:
            continue
        try:
            name = node.get_name()
            if (name and name in ("gnome-shell", "Screen Time Remaining")) \
                    or (name and name.startswith("Request time,")):
                states = node.get_state_set()
                relevant_nodes.append({
                    "name": name,
                    "showing": states.contains(Atspi.StateType.SHOWING),
                    "visible": states.contains(Atspi.StateType.VISIBLE),
                })
            queue.extend(
                node.get_child_at_index(index)
                for index in range(max(0, node.get_child_count()))
            )
        except (AttributeError, GLib.Error):
            continue
    return {
        "application_count": application_count,
        "relevant_nodes": relevant_nodes,
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
