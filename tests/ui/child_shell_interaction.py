#!/usr/bin/env python3
"""Exercise the real child indicator and shared overlay through AT-SPI."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib

from dogtail.hermetic.mutter import MutterInputBackend

from child_shell_screenshot import capture_screenshot
from mutter_input import press_key as _press_key
from tests.support.automation import Automation


EVENTS = (
    "object:children-changed",
    "object:property-change:accessible-id",
    "object:state-changed:checked",
    "object:state-changed:focused",
    "object:state-changed:showing",
    "window:create",
    "window:destroy",
)
TIMEOUT_SECONDS = float(os.environ.get("ONPC_CHILD_INTERACTION_TIMEOUT_SECONDS", "15"))
EVENTS_PATH = Path(os.environ["ONPC_CHILD_OVERLAY_EVENTS_PATH"])
SNAPSHOT_PATH = Path(os.environ["ONPC_CHILD_OVERLAY_A11Y_PATH"])
X_KEYCODE_SPACE = 65
X_KEYCODE_MENU = 135
COUNTDOWN_ANIMATION_SCHEMA = "com.puffyslippers.oh-no-parent-control.child"
COUNTDOWN_ANIMATION_KEY = "one-minute-countdown-animation"
EXTENSION_UUID = "oh-no-parent-control@tech.puffyslippers.com"
REQUEST_BUTTON_ID = "child-request-button"
COUNTDOWN_ANIMATION_ID = "child-countdown-animation-toggle"
OVERLAY_WINDOW_ID = "kiosk-request-window"
OVERLAY_CANCEL_ID = "kiosk-request-cancel"
UI = Automation(Atspi, lambda: Atspi.get_desktop(0), query_errors=(GLib.Error,))


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
    node = UI.find(REQUEST_BUTTON_ID)
    return node if node is not None and _state(node, Atspi.StateType.SHOWING) else None


def _find_countdown_animation_item():
    node = UI.find(COUNTDOWN_ANIMATION_ID)
    return node if node is not None and _state(node, Atspi.StateType.SHOWING) else None


def _countdown_animation_setting():
    schema_dir = (
        Path(os.environ["XDG_DATA_HOME"]) / "gnome-shell" / "extensions" /
        EXTENSION_UUID / "schemas"
    )
    environment = {
        **os.environ,
        "GSETTINGS_SCHEMA_DIR": str(schema_dir),
    }
    result = subprocess.run(
        ["gsettings", "get", COUNTDOWN_ANIMATION_SCHEMA,
         COUNTDOWN_ANIMATION_KEY],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        raise AssertionError(
            "Could not read the private countdown animation setting: "
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip() == "true"


def _overlay_surfaces():
    windows = [node for node in UI.find_all(OVERLAY_WINDOW_ID)
               if _state(node, Atspi.StateType.SHOWING)]
    cancel = [node for node in UI.find_all(OVERLAY_CANCEL_ID)
              if _state(node, Atspi.StateType.SHOWING)]
    return windows, cancel


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
    for node in UI.nodes():
        try:
            identity = node.get_accessible_id() or ""
        except GLib.Error:
            continue
        if not identity.startswith(("child-", "kiosk-")):
            continue
        states = node.get_state_set()
        lines.append(
            f"id={identity!r} role={_node_role(node)!r} "
            f"visible={states.contains(Atspi.StateType.VISIBLE)} "
            f"showing={states.contains(Atspi.StateType.SHOWING)} "
            f"checked={states.contains(Atspi.StateType.CHECKED)}"
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
        # Atspi.Accessible proxies may be falsey even when they reference a
        # real actor. Predicates use None/False as their only not-ready values,
        # so retain a discovered accessible object without asking its truthiness.
        if value is not None and value is not False:
            result["value"] = value
            loop.quit()
        return GLib.SOURCE_CONTINUE

    def deadline_check():
        if time.monotonic() >= deadline:
            loop.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    # Event-triggered inspections must run once. Returning SOURCE_CONTINUE
    # here leaves an idle callback for every accessibility event, including
    # callbacks that query windows destroyed during the reopen scenario.
    # Coalesce events and remove the pending callback when this wait ends.
    pending_inspection = {"source": None}

    def inspect_event():
        pending_inspection["source"] = None
        inspect()
        return GLib.SOURCE_REMOVE

    def schedule_inspection(*_args):
        if pending_inspection["source"] is None:
            pending_inspection["source"] = GLib.idle_add(inspect_event)

    listener = Atspi.EventListener.new(schedule_inspection)
    registered = [event for event in EVENTS if listener.register(event)]
    inspection_source = GLib.timeout_add(50, inspect)
    deadline_source = GLib.timeout_add(100, deadline_check)
    try:
        inspect()
        if result["value"] is None:
            loop.run()
    finally:
        for source_id in (inspection_source, deadline_source, pending_inspection["source"]):
            if source_id is None:
                continue
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


def _prepare_indicator_input():
    # The owned public ID is the input recipient. No Shell state mutation or
    # overview shortcut is allowed to manufacture reachability.
    button = _wait(_find_request_button, "the ID-addressed Shell request indicator")
    UI.focus(REQUEST_BUTTON_ID)
    _wait(
        lambda: _state(_find_request_button(), Atspi.StateType.FOCUSED),
        "keyboard focus on the Shell request indicator",
    )
    return button


def _activate_repeatedly(count, input_backend):
    # Shell's St.Button does not expose an AT-SPI Action interface. Reacquire
    # its public ID, focus it semantically, and use its normal keyboard action.
    for _index in range(count):
        _prepare_indicator_input()
        _press_key(input_backend, X_KEYCODE_SPACE)


def _one_overlay(expected_launches):
    records = _launch_records()
    windows, cancel = _overlay_surfaces()
    if len(records) != expected_launches or len(windows) != 1 or len(cancel) != 1:
        return None
    if not _process_exists(records[-1]):
        return None
    return windows[0], cancel[0]


def _overlay_closed(expected_launches):
    records = _launch_records()
    windows, cancel = _overlay_surfaces()
    if len(records) != expected_launches or windows or cancel:
        return False
    return records and not _process_exists(records[-1])


def main():
    input_backend = None
    try:
        input_backend = MutterInputBackend()
        input_backend.connectMonitor()
        _wait(_find_request_button, "the Shell request action")
        windows, cancel = _overlay_surfaces()
        if _launch_records() or windows or cancel:
            raise AssertionError("The interaction preview opened an overlay before activation")
        print("interaction stage=initially-closed", flush=True)

        if _countdown_animation_setting():
            raise AssertionError("Countdown animation did not default to disabled")
        _prepare_indicator_input()
        _press_key(input_backend, X_KEYCODE_MENU)
        countdown_item = _wait(
            _find_countdown_animation_item,
            "the secondary-click countdown animation checkbox",
        )
        if _state(countdown_item, Atspi.StateType.CHECKED):
            raise AssertionError("Countdown animation checkbox did not default to unchecked")
        UI.focus(COUNTDOWN_ANIMATION_ID)
        _press_key(input_backend, X_KEYCODE_SPACE)
        _wait(
            lambda: _find_countdown_animation_item() is None,
            "the countdown animation menu to close after activation",
        )
        _wait(
            _countdown_animation_setting,
            "the countdown animation choice to persist",
        )
        print("interaction stage=countdown-preference-persisted", flush=True)

        # These actions arrive after the first spawn but before its GTK window
        # is exposed. They exercise the production single-flight guard while
        # the request surface is still opening.
        _prepare_indicator_input()
        # Retain real keyboard-opening coverage before a request app can own
        # focus, then exercise the same action directly during startup.
        _press_key(input_backend, X_KEYCODE_SPACE)
        _activate_repeatedly(5, input_backend)
        _wait(lambda: len(_launch_records()) == 1, "one opening request process")
        print("interaction stage=opening-single-flight", flush=True)
        _wait(lambda: _one_overlay(1), "one visible child request overlay")
        capture_screenshot(Path(os.environ["ONPC_CHILD_SHELL_SCREENSHOT_PATH"]))
        print("interaction stage=overlay-visible", flush=True)

        # Exercise the same guard after the shared request form is fully mapped.
        _activate_repeatedly(5, input_backend)
        windows, cancel = _overlay_surfaces()
        if len(_launch_records()) != 1 or len(windows) != 1 or len(cancel) != 1:
            raise AssertionError("Repeated activation created a duplicate request overlay")
        print("interaction stage=running-single-flight", flush=True)

        UI.activate(OVERLAY_CANCEL_ID)
        _wait(lambda: _overlay_closed(1), "the first overlay to close")
        print("interaction stage=first-overlay-closed", flush=True)
        _wait(
            lambda: not _state(_find_request_button(), Atspi.StateType.CHECKED),
            "the indicator to clear its active state",
        )

        _wait(_find_request_button, "the reusable Shell request action")
        _prepare_indicator_input()
        _press_key(input_backend, X_KEYCODE_SPACE)
        _wait(lambda: _one_overlay(2), "one reopened child request overlay")
        print("interaction stage=overlay-reopened", flush=True)
        records = _launch_records()
        if records[0] == records[1]:
            raise AssertionError("The reopened overlay did not use a new process")

        UI.activate(OVERLAY_CANCEL_ID)
        _wait(lambda: _overlay_closed(2), "the reopened overlay to close")
        print(
            "Child indicator interaction passed; launches=2 "
            "max_concurrent_overlays=1 reopened=true"
        )
        return 0
    except Exception as error:
        print(f"Child indicator interaction failed: {error}", file=sys.stderr)
        try:
            capture_screenshot(
                Path(os.environ["ONPC_CHILD_SHELL_SCREENSHOT_PATH"]).with_name("interaction-failure.png"),
                include_cursor=True,
            )
        except Exception:
            print("Child interaction failure screenshot unavailable", file=sys.stderr)
        print(f"Launch records: {_launch_records()!r}", file=sys.stderr)
        print(f"Redacted accessibility snapshot:\n{_snapshot()}", file=sys.stderr)
        return 1
    finally:
        if input_backend is not None:
            input_backend.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
