#!/usr/bin/env python3
"""Exercise the real child panel and shared overlay through Application UI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

from gi.repository import GLib

from tests.support.application_ui import ApplicationUI, UIClientError
from child_shell_screenshot import capture_screenshot


TIMEOUT_SECONDS = float(os.environ.get("ONPC_CHILD_INTERACTION_TIMEOUT_SECONDS", "15"))
EVENTS_PATH = Path(os.environ["ONPC_CHILD_OVERLAY_EVENTS_PATH"])
SNAPSHOT_PATH = Path(os.environ["ONPC_CHILD_OVERLAY_A11Y_PATH"])
COUNTDOWN_ANIMATION_SCHEMA = "com.puffyslippers.oh-no-parent-control.child"
COUNTDOWN_ANIMATION_KEY = "one-minute-countdown-animation"
EXTENSION_UUID = "oh-no-parent-control@tech.puffyslippers.com"
REQUEST_BUTTON_ID = "child-request-button"
COUNTDOWN_ANIMATION_ID = "child-countdown-animation-toggle"
OVERLAY_WINDOW_ID = "kiosk-request-window"
OVERLAY_CANCEL_ID = "kiosk-request-cancel"
SHELL_PID = int(os.environ["ONPC_CHILD_SHELL_PID"])
APPLICATIONS = ApplicationUI()
UI = None
OVERLAY = None


def _panel():
    global UI
    if UI is None:
        candidate = APPLICATIONS.client("child-panel")
        if candidate.pid != SHELL_PID:
            raise AssertionError("Child panel is not owned by the launched Shell")
        UI = candidate
    return UI


def _find_request_button():
    node = _panel().getElementById(REQUEST_BUTTON_ID)
    return node if node.visible and node.enabled else None


def _countdown_animation_setting():
    schema_dir = (Path(os.environ["XDG_DATA_HOME"]) / "gnome-shell" / "extensions" /
                  EXTENSION_UUID / "schemas")
    result = subprocess.run(
        ["gsettings", "get", COUNTDOWN_ANIMATION_SCHEMA, COUNTDOWN_ANIMATION_KEY],
        text=True, capture_output=True, check=False,
        env={**os.environ, "GSETTINGS_SCHEMA_DIR": str(schema_dir)},
    )
    if result.returncode != 0:
        raise AssertionError("Could not read the private countdown animation setting: "
                             + result.stderr.strip())
    return result.stdout.strip() == "true"


def _overlay_automation():
    global OVERLAY
    active = [pid for pid in _launch_records() if _process_exists(pid)]
    if len(active) > 1:
        raise AssertionError("More than one request overlay process is running")
    if not active:
        return None
    # Reconstruct only at the deliberate, recorded new-process boundary.
    if OVERLAY is None or OVERLAY.pid != active[0]:
        if OVERLAY is not None:
            if _process_exists(OVERLAY.pid):
                raise AssertionError("Previous request overlay owner is still running")
            APPLICATIONS.forget("child-request")
        candidate = APPLICATIONS.client("child-request")
        if candidate.pid != active[0]:
            raise AssertionError("Request overlay has the wrong launch owner")
        OVERLAY = candidate
    return OVERLAY


def _overlay_surfaces():
    overlay = _overlay_automation()
    if overlay is None:
        return [], []
    windows = [surface for surface in overlay.listSurfaces()
               if surface["id"] == OVERLAY_WINDOW_ID and surface["visible"]]
    if not windows:
        return [], []
    cancel = overlay.getElementById(OVERLAY_CANCEL_ID)
    return windows, [cancel] if cancel.visible else []


def _complete_language_setup(overlay):
    if any(surface["id"] == "language-dialog" for surface in overlay.listSurfaces()):
        overlay.activate("language-continue", surface_id="language-dialog")
        _wait(lambda: not any(surface["id"] == "language-dialog"
                              for surface in overlay.listSurfaces()),
              "the initial language choice to commit")
    _wait(lambda: overlay.getElementById(OVERLAY_CANCEL_ID).enabled,
          "the shared request form to become available")


def _activate_overlay_cancel():
    overlay = _overlay_automation()
    if overlay is None:
        raise AssertionError("The live request overlay was not published")
    _complete_language_setup(overlay)
    overlay.activate(OVERLAY_CANCEL_ID)


def _launch_records():
    if not EVENTS_PATH.exists():
        return []
    records = []
    for line in EVENTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        event, separator, pid = line.partition("\t")
        if event != "request-launch" or not separator or not pid.isdigit():
            raise AssertionError("Malformed redacted request-launch event")
        records.append(int(pid))
    return records


def _process_exists(pid):
    return Path(f"/proc/{pid}").exists()


def _snapshot():
    try:
        records = _panel().inventory()
        text = "\n".join(
            f"id={item['id']!r} type={item['type']!r} "
            f"visible={item['visible']} enabled={item['enabled']}"
            for item in records) + "\n"
    except UIClientError as error:
        text = "Application UI inventory unavailable: " + error.code + "\n"
    SNAPSHOT_PATH.write_text(text, encoding="utf-8")
    return text


def _wait(predicate, description):
    """Retry read-only observations; every mutation is outside this helper."""
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            value = predicate()
        except UIClientError as error:
            if error.uncertain or error.code != "Unavailable":
                raise
            value = None
        if value is not None and value is not False:
            return value
        for _ in range(32):
            if not GLib.MainContext.default().iteration(False):
                break
        time.sleep(min(.05, max(0, deadline - time.monotonic())))
    raise AssertionError(f"Timed out waiting for {description}.\n"
                         f"Launch records: {_launch_records()!r}\n"
                         f"Redacted Application UI snapshot:\n{_snapshot()}")


def _one_overlay(expected_launches):
    records = _launch_records()
    windows, cancel = _overlay_surfaces()
    if len(records) != expected_launches or len(windows) != 1 or len(cancel) != 1:
        return None
    return (windows[0], cancel[0]) if _process_exists(records[-1]) else None


def _overlay_closed(expected_launches):
    records = _launch_records()
    # Cancel unregisters the UI endpoint before the process finishes exiting.
    # Wait for the recorded owner to exit before observing surface absence;
    # querying its pinned client during shutdown correctly raises OwnerChanged.
    if (len(records) != expected_launches or not records
            or _process_exists(records[-1])):
        return False
    windows, cancel = _overlay_surfaces()
    return not windows and not cancel


def _open_overlay(expected_launches):
    _wait(_find_request_button, "the reusable Shell request action")
    _panel().activate(REQUEST_BUTTON_ID)
    _wait(lambda: _one_overlay(expected_launches), "one child request overlay")


def _review_language_changes(oracles):
    """Finite expected text stays in the case; controls use the common facade."""
    for launches, (language, expected) in enumerate(oracles.items(), start=1):
        _open_overlay(launches)
        overlay = _overlay_automation()
        _complete_language_setup(overlay)
        overlay.setValue("kiosk-menu-button", "preferences")
        _wait(lambda: any(surface["id"] == "language-dialog"
                          for surface in overlay.listSurfaces()), "the language chooser")
        overlay.setValue("language-list", language, surface_id="language-dialog")
        overlay.activate("language-continue", surface_id="language-dialog")
        _wait(lambda: overlay.getText("kiosk-request-submit") == expected["request"],
              "the overlay applies its committed translation")
        overlay.activate(OVERLAY_CANCEL_ID)
        _wait(lambda: _overlay_closed(launches), "the language-review overlay closes")
        panel_pattern = re.escape(expected["panel"]).replace(
            re.escape("%(time)s"), r"\d{2}:\d{2}") + ", generation-one"
        _wait(lambda: re.fullmatch(panel_pattern, _panel().getText(REQUEST_BUTTON_ID)),
              "the panel reloads its own language after the overlay exits")
        actual = _panel().getElementById(REQUEST_BUTTON_ID).snapshot()["description"]
        assert actual == expected["description"], (language, "panel description", expected["description"], actual)
        actual = _panel().getText(COUNTDOWN_ANIMATION_ID)
        assert actual == expected["countdown"], (language, "countdown label", expected["countdown"], actual)
        capture_screenshot(Path(os.environ["ONPC_CHILD_SHELL_SCREENSHOT_PATH"]).with_name(
            "language-" + language + ".png"))
        print("Child panel localization reviewed: " + language, flush=True)


def _reminder_preview():
    _open_overlay(1)
    overlay = _overlay_automation()
    _complete_language_setup(overlay)
    overlay.setValue('kiosk-menu-button', 'preferences')
    overlay.setValue('preferences-tabs', 'reminders', surface_id='language-dialog')
    _wait(lambda: overlay.getElementById('reminder-fifteen-seconds-edit',
          surface_id='language-dialog').enabled, 'reminders loaded')
    overlay.setValue('reminder-show-in-fullscreen', False, surface_id='language-dialog')
    overlay.activate('reminder-fifteen-seconds-edit', surface_id='language-dialog')
    overlay.setText('reminder-text', '  Save <games> & work!  ', surface_id='reminder-editor-dialog')
    overlay.activate('reminder-editor-preview', surface_id='reminder-editor-dialog')

    def preview_body(expected):
        return (any(s['id'] == 'child-reminder-preview' and s['visible'] for s in _panel().listSurfaces())
                and _panel().getText('child-reminder-preview-message',
                                    surface_id='child-reminder-preview') == expected)

    _wait(lambda: preview_body('  Save <games> & work!  '), 'real Shell literal reminder preview')
    assert _panel().getValue('child-reminder-preview-message', surface_id='child-reminder-preview') == 'critical'
    assert _panel().getText('child-reminder-preview', surface_id='child-reminder-preview') == ''
    overlay.setText('reminder-text', '   ', surface_id='reminder-editor-dialog')
    overlay.activate('reminder-editor-preview', surface_id='reminder-editor-dialog')
    _wait(lambda: preview_body('15 seconds left'), 'real Shell default reminder preview')
    overlay.activate('reminder-editor-cancel', surface_id='reminder-editor-dialog')
    _wait(lambda: not any(s['id'] == 'child-reminder-preview' for s in _panel().listSurfaces()),
          'editor cancellation dismisses the real preview')
    assert overlay.getText('reminder-fifteen-seconds-text', surface_id='language-dialog') == '15 seconds left'
    overlay.activate('language-cancel', surface_id='language-dialog')
    _activate_overlay_cancel()
    _wait(lambda: _overlay_closed(1), 'preview overlay closes')
    print('Real Shell reminder preview and unsaved draft cancellation passed', flush=True)


def main():
    try:
        _wait(_find_request_button, "the Shell request action")
        inventory = _panel().inventory()
        assert {item["id"] for item in inventory} >= {
            "child-screen-time-indicator", REQUEST_BUTTON_ID, "child-remaining-time",
            "child-request-tooltip", "child-countdown-menu", COUNTDOWN_ANIMATION_ID,
        }
        windows, cancel = _overlay_surfaces()
        if _launch_records() or windows or cancel:
            raise AssertionError("The interaction preview opened an overlay before activation")
        print("interaction stage=initially-closed", flush=True)
        if os.environ.get('ONPC_CHILD_REMINDER_PREVIEW') == '1':
            _reminder_preview()
            return 0
        localization = os.environ.get("ONPC_CHILD_LOCALIZATION_ORACLES")
        if localization:
            _review_language_changes(json.loads(localization))
            print("Child panel localization cycle passed", flush=True)
            return 0

        if _countdown_animation_setting() or _panel().getValue(COUNTDOWN_ANIMATION_ID):
            raise AssertionError("Countdown animation did not default to disabled")
        _panel().setValue(COUNTDOWN_ANIMATION_ID, True)
        _wait(_countdown_animation_setting, "the countdown animation choice to persist")
        _wait(lambda: _panel().getValue(COUNTDOWN_ANIMATION_ID) is True,
              "the public animation preference result")
        windows, cancel = _overlay_surfaces()
        if _launch_records() or windows or cancel:
            raise AssertionError("Changing the countdown preference opened a request overlay")
        print("interaction stage=countdown-preference-persisted", flush=True)

        _open_overlay(1)
        capture_screenshot(Path(os.environ["ONPC_CHILD_SHELL_SCREENSHOT_PATH"]))
        print("interaction stage=overlay-visible", flush=True)
        _activate_overlay_cancel()
        _wait(lambda: _overlay_closed(1), "the first overlay to close")
        print("interaction stage=first-overlay-closed", flush=True)
        _open_overlay(2)
        print("interaction stage=overlay-reopened", flush=True)
        records = _launch_records()
        if records[0] == records[1]:
            raise AssertionError("The reopened overlay did not use a new process")
        _activate_overlay_cancel()
        _wait(lambda: _overlay_closed(2), "the reopened overlay to close")
        print("Child indicator interaction passed; launches=2 "
              "max_concurrent_overlays=1 reopened=true")
        return 0
    except Exception as error:
        print(f"Child indicator interaction failed: {error}", file=sys.stderr)
        # Keep the failing operation visible without recording UI values,
        # source lines or locals. Owner loss during a close observation must
        # be distinguished from a failed or uncertain Cancel mutation.
        frames = traceback.extract_tb(error.__traceback__, limit=12)
        print("Interaction failure frames: " + " -> ".join(
            f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
            for frame in frames), file=sys.stderr)
        if isinstance(error, UIClientError):
            print(f"Interaction UI failure code={error.code} "
                  f"uncertain={error.uncertain}", file=sys.stderr)
        print(f"Interaction Shell process exists={_process_exists(SHELL_PID)}",
              file=sys.stderr)
        if OVERLAY is not None:
            print(f"Interaction pinned overlay process exists="
                  f"{_process_exists(OVERLAY.pid)}", file=sys.stderr)
        try:
            capture_screenshot(
                Path(os.environ["ONPC_CHILD_SHELL_SCREENSHOT_PATH"]).with_name("interaction-failure.png"),
                include_cursor=True,
            )
        except Exception:
            print("Child interaction failure screenshot unavailable", file=sys.stderr)
        print(f"Launch records: {_launch_records()!r}", file=sys.stderr)
        print(f"Redacted Application UI snapshot:\n{_snapshot()}", file=sys.stderr)
        return 1
    finally:
        APPLICATIONS.close()


if __name__ == "__main__":
    raise SystemExit(main())
