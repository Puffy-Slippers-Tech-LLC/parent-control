#!/usr/bin/env python3
"""Exercise the real child indicator and shared overlay through AT-SPI."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib

from dogtail.hermetic.mutter import MutterInputBackend

from child_shell_probe import is_expected_accessible_name


EVENTS = (
    "object:children-changed",
    "object:property-change:accessible-name",
    "object:state-changed:checked",
    "object:state-changed:focused",
    "object:state-changed:showing",
    "window:create",
    "window:destroy",
)
TIMEOUT_SECONDS = float(os.environ.get("ONPC_CHILD_INTERACTION_TIMEOUT_SECONDS", "15"))
EVENTS_PATH = Path(os.environ["ONPC_CHILD_OVERLAY_EVENTS_PATH"])
SNAPSHOT_PATH = Path(os.environ["ONPC_CHILD_OVERLAY_A11Y_PATH"])
X_KEYCODE_ESCAPE = 9
X_KEYCODE_SPACE = 65
X_KEYCODE_SUPER_L = 133


def _children(node):
    try:
        return [
            node.get_child_at_index(index)
            for index in range(max(0, node.get_child_count()))
        ]
    except (AttributeError, GLib.Error):
        return []


def _applications():
    desktop = Atspi.get_desktop(0)
    return [
        desktop.get_child_at_index(index)
        for index in range(desktop.get_child_count())
    ]


def _walk(root):
    queue = [root]
    while queue:
        node = queue.pop(0)
        if node is None:
            continue
        yield node
        queue.extend(_children(node))


def _node_name(node):
    try:
        return node.get_name() or ""
    except GLib.Error:
        return ""


def _node_role(node):
    try:
        return node.get_role_name() or "unknown"
    except GLib.Error:
        return "unknown"


def _state(node, state_type):
    try:
        return node.get_state_set().contains(state_type)
    except GLib.Error:
        return False


def _find_request_button():
    for application in _applications():
        if "gnome-shell" not in _node_name(application).lower():
            continue
        for node in _walk(application):
            if is_expected_accessible_name(_node_name(node)):
                return node
    return None


def _overlay_surfaces():
    surfaces = []
    for application in _applications():
        if "gnome-shell" in _node_name(application).lower():
            continue
        nodes = list(_walk(application))
        cancel_nodes = [
            node for node in nodes
            if _node_name(node) == "CANCEL" and _node_role(node) == "button"
        ]
        if not cancel_nodes:
            continue
        windows = [
            node for node in nodes
            if _node_role(node) in {"frame", "window"}
            and _state(node, Atspi.StateType.VISIBLE)
        ]
        surfaces.append((application, cancel_nodes, windows))
    return surfaces


def _launch_records():
    if not EVENTS_PATH.exists():
        return []
    records = []
    for line in EVENTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        event, separator, pid = line.partition("\t")
        if event != "request-launch" or not separator or not pid.isdigit():
            raise AssertionError(f"Malformed redacted request-launch event: {line!r}")
        records.append(int(pid))
    return records


def _process_exists(pid):
    return Path(f"/proc/{pid}").exists()


def _snapshot():
    lines = []
    for app_index, application in enumerate(_applications()):
        is_shell = "gnome-shell" in _node_name(application).lower()
        is_overlay = bool([
            node for node in _walk(application) if _node_name(node) == "CANCEL"
        ])
        if not is_shell and not is_overlay:
            continue
        lines.append(
            f"application[{app_index}] name={_node_name(application)!r} "
            f"role={_node_role(application)!r}"
        )
        for node in _walk(application):
            name = _node_name(node)
            if not name:
                continue
            if is_shell and name != "Screen Time Remaining" \
                    and not name.startswith("Request time,") \
                    and not _state(node, Atspi.StateType.FOCUSED):
                continue
            if is_shell and not (
                    name == "Screen Time Remaining"
                    or name.startswith("Request time,")
            ):
                name = "[Shell surface]"
            if is_overlay and name not in {"CANCEL", "REQUEST"}:
                name = "[Request surface]"
            states = node.get_state_set()
            try:
                extents = node.get_extents(Atspi.CoordType.SCREEN)
                geometry = f"{extents.x},{extents.y} {extents.width}x{extents.height}"
            except GLib.Error:
                geometry = "unavailable"
            lines.append(
                f"  name={name!r} role={_node_role(node)!r} "
                f"visible={states.contains(Atspi.StateType.VISIBLE)} "
                f"showing={states.contains(Atspi.StateType.SHOWING)} "
                f"checked={states.contains(Atspi.StateType.CHECKED)} "
                f"geometry={geometry}"
            )
    text = "\n".join(lines) + "\n"
    SNAPSHOT_PATH.write_text(text, encoding="utf-8")
    return text


def _wait(predicate, description):
    loop = GLib.MainLoop()
    result = {"value": None}
    deadline = time.monotonic() + TIMEOUT_SECONDS

    def inspect(*_args):
        try:
            value = predicate()
        except (AttributeError, GLib.Error):
            value = None
        if value:
            result["value"] = value
            loop.quit()
        return GLib.SOURCE_CONTINUE

    def deadline_check():
        if time.monotonic() >= deadline:
            loop.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    listener = Atspi.EventListener.new(lambda *_args: GLib.idle_add(inspect))
    registered = [event for event in EVENTS if listener.register(event)]
    inspection_source = GLib.timeout_add(50, inspect)
    deadline_source = GLib.timeout_add(100, deadline_check)
    try:
        inspect()
        if result["value"] is None:
            loop.run()
    finally:
        for source_id in (inspection_source, deadline_source):
            source = GLib.MainContext.default().find_source_by_id(source_id)
            if source is not None:
                source.destroy()
        for event in registered:
            listener.deregister(event)
    if result["value"] is None:
        raise AssertionError(
            f"Timed out waiting for {description}.\n"
            f"Launch records: {_launch_records()!r}\n"
            f"Redacted accessibility snapshot:\n{_snapshot()}"
        )
    return result["value"]


def _prepare_indicator_input(input_backend):
    # Super transfers input to Shell's overview even while the child overlay
    # is active. AT-SPI then puts keyboard focus on the real indicator, and
    # virtual Space presses exercise its supported keyboard activation path
    # without relying on screen coordinates.
    _press_key(input_backend, X_KEYCODE_SUPER_L)
    time.sleep(0.75)
    button = _wait(_find_request_button, "the indicator in Shell's overview")
    if not button.grab_focus():
        raise AssertionError("The Shell request indicator did not accept key focus")
    _wait(
        lambda: _state(_find_request_button(), Atspi.StateType.FOCUSED),
        "keyboard focus on the Shell request indicator",
    )
    time.sleep(0.25)
    return button


def _activate_repeatedly(count, input_backend):
    for _index in range(count):
        _press_key(input_backend, X_KEYCODE_SPACE)
        time.sleep(0.05)


def _leave_overview(input_backend):
    _press_key(input_backend, X_KEYCODE_ESCAPE)
    time.sleep(0.5)


def _press_key(input_backend, keycode):
    input_backend.generateKeycodePress(keycode)
    time.sleep(0.1)
    input_backend.generateKeycodeRelease(keycode)
    # Nested Shell's devkit compositor publishes the virtual keyboard release
    # to Shell actors when the RemoteDesktop session closes. Use that supported
    # lifecycle boundary for each key, then create the next virtual device.
    input_backend.disconnect()
    time.sleep(0.1)
    input_backend.connectMonitor()


def _one_overlay(expected_launches):
    records = _launch_records()
    surfaces = _overlay_surfaces()
    if len(records) != expected_launches or len(surfaces) != 1:
        return None
    _application, cancel_nodes, windows = surfaces[0]
    if len(cancel_nodes) != 1 or len(windows) != 1:
        return None
    if not _process_exists(records[-1]):
        return None
    return surfaces[0]


def _overlay_closed(expected_launches):
    records = _launch_records()
    if len(records) != expected_launches or _overlay_surfaces():
        return False
    return records and not _process_exists(records[-1])


def main():
    input_backend = None
    try:
        input_backend = MutterInputBackend()
        input_backend.connectMonitor()
        request_button = _wait(_find_request_button, "the Shell request action")
        if _launch_records() or _overlay_surfaces():
            raise AssertionError("The interaction preview opened an overlay before activation")
        print("interaction stage=initially-closed", flush=True)

        # These actions arrive after the first spawn but before its GTK window
        # is exposed. They exercise the production single-flight guard while
        # the request surface is still opening.
        _prepare_indicator_input(input_backend)
        _activate_repeatedly(6, input_backend)
        _leave_overview(input_backend)
        _wait(lambda: len(_launch_records()) == 1, "one opening request process")
        print("interaction stage=opening-single-flight", flush=True)
        overlay = _wait(lambda: _one_overlay(1), "one visible child request overlay")
        print("interaction stage=overlay-visible", flush=True)

        # Exercise the same guard after the shared request form is fully mapped.
        _prepare_indicator_input(input_backend)
        _activate_repeatedly(5, input_backend)
        _leave_overview(input_backend)
        if len(_launch_records()) != 1 or len(_overlay_surfaces()) != 1:
            raise AssertionError("Repeated activation created a duplicate request overlay")
        print("interaction stage=running-single-flight", flush=True)

        _application, cancel_nodes, _windows = overlay
        if not cancel_nodes[0].do_action(0):
            raise AssertionError("The shared overlay Cancel action was not accepted")
        _wait(lambda: _overlay_closed(1), "the first overlay to close")
        print("interaction stage=first-overlay-closed", flush=True)
        _wait(
            lambda: not _state(_find_request_button(), Atspi.StateType.CHECKED),
            "the indicator to clear its active state",
        )

        request_button = _wait(_find_request_button, "the reusable Shell request action")
        _prepare_indicator_input(input_backend)
        _activate_repeatedly(1, input_backend)
        _leave_overview(input_backend)
        second_overlay = _wait(lambda: _one_overlay(2), "one reopened child request overlay")
        print("interaction stage=overlay-reopened", flush=True)
        records = _launch_records()
        if records[0] == records[1]:
            raise AssertionError("The reopened overlay did not use a new process")

        _application, cancel_nodes, _windows = second_overlay
        if not cancel_nodes[0].do_action(0):
            raise AssertionError("The reopened overlay Cancel action was not accepted")
        _wait(lambda: _overlay_closed(2), "the reopened overlay to close")
        print(
            "Child indicator interaction passed; launches=2 "
            "max_concurrent_overlays=1 reopened=true"
        )
        return 0
    except Exception as error:
        print(f"Child indicator interaction failed: {error}", file=sys.stderr)
        print(f"Launch records: {_launch_records()!r}", file=sys.stderr)
        print(f"Redacted accessibility snapshot:\n{_snapshot()}", file=sys.stderr)
        return 1
    finally:
        if input_backend is not None:
            input_backend.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
