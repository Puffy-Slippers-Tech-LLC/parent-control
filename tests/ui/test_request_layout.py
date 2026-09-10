"""Resolution and overflow regression coverage for both shared request views."""

import json
import math
from pathlib import Path
import tempfile

import pytest


pytestmark = pytest.mark.ui


@pytest.fixture
def request_display_scale(hermetic_ui_session, dpi_scale):
    """Set actual Wayland scaling on the fixture's private compositor only.

    GDK_SCALE is an X11 override and cannot exercise Wayland HiDPI. Use
    Mutter's documented DisplayConfig interface with a temporary configuration:
    https://gitlab.gnome.org/GNOME/mutter/-/blob/main/data/dbus-interfaces/org.gnome.Mutter.DisplayConfig.xml
    """
    from gi.repository import Gio, GLib

    connection = Gio.DBusConnection.new_for_address_sync(
        hermetic_ui_session.bus_address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None,
    )

    def call(method, parameters=None):
        return connection.call_sync(
            "org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig",
            "org.gnome.Mutter.DisplayConfig", method, parameters, None,
            Gio.DBusCallFlags.NONE, 3000, None,
        ).unpack()

    try:
        _serial, monitors, logical_monitors, _properties = call("GetCurrentState")
        assert len(monitors) == len(logical_monitors) == 1
        specification, modes, _properties = monitors[0]
        mode = next(mode for mode in modes if mode[-1].get("is-current"))
        # Use the compositor's exact supported value (fractional scales may
        # be represented as floats with slightly different precision).
        supported_scale = next(
            scale for scale in mode[5] if scale == pytest.approx(dpi_scale)
        )
        x, y, original_scale, transform, primary, _monitors, _properties = logical_monitors[0]

        def apply(scale):
            serial, *_state = call("GetCurrentState")
            call("ApplyMonitorsConfig", GLib.Variant(
                "(uua(iiduba(ssa{sv}))a{sv})",
                (serial, 1, [(x, y, scale, transform, primary,
                              [(specification[0], mode[0], {})])], {}),
            ))

        try:
            apply(supported_scale)
            yield
        finally:
            apply(original_scale)
    finally:
        connection.close_sync(None)


@pytest.mark.parametrize("overlay, dpi_scale",
                         ((False, 1), (True, 1), (False, 4 / 3), (True, 4 / 3)),
                         ids=("kiosk", "child-overlay", "kiosk-fractional", "child-fractional"))
def test_request_layout_keeps_text_readable_and_controls_reachable(
        launch_ui, request_display_scale, overlay, dpi_scale):
    # Retain rendered evidence independently of pytest's rotating temp roots.
    directory = Path(tempfile.mkdtemp(prefix="onpc-request-layout-"))
    process, log = launch_ui(
        "request_layout_preview", wait_for_application=False,
        environment_overrides={
            "ONPC_REQUEST_LAYOUT_DIRECTORY": str(directory),
            "ONPC_REQUEST_LAYOUT_OVERLAY": "1" if overlay else "0",
            "GSK_RENDERER": "gl",
        },
    )
    assert process.wait(timeout=60) == 0, log.read_text()
    print(f"Request layout evidence: {directory}")
    assert "Gtk-CRITICAL" not in log.read_text()
    records = json.loads((directory / "layout.json").read_text())
    assert len(records) == 24
    for record in records:
        width, height = record["size"]
        x, y, board_width, board_height = record["viewport"]
        assert x >= 0 and y >= 0, record
        assert x + board_width <= width and y + board_height <= height, record
        hud_x, hud_y, hud_width, hud_height = record["mute_button"]
        assert 0 <= hud_x < hud_x + hud_width <= width, record
        assert 0 <= hud_y < hud_y + hud_height <= height, record
        assert hud_width >= 66 and record["mute_pick"], record
        assert record["monitor_scale"] == math.ceil(dpi_scale), record
        assert record["surface_scale"] == pytest.approx(dpi_scale), record
        assert record["status_font"] >= 19, record
        assert record["board_width"] >= record["board_minimum"], record
        if not record["expanded"]:
            assert record["duration_pick"], record
        # Scrolling must expose the complete estimate, including its last line.
        _, footer_y, _, footer_height = record["footer_after_scroll"]
        assert footer_y >= 0, record
        assert footer_y + footer_height <= record["scroll_page"] + 1, record
        if width >= 1024 and height >= 768 and not record["expanded"]:
            assert record["scroll_upper"] <= record["scroll_page"] + 1, record
            first, second = record["durations"][:2]
            assert first[1] == second[1] and first[0] < second[0], record

    # More logical screen space must not zoom a smaller desktop to fill it.
    # Compare projected bounds as well as allocations: GTK may allocate the
    # same board size and then magnify its entire render tree with a transform.
    for expanded in (False, True):
        desktops = [record for record in records
                    if record["expanded"] == expanded
                    and record["size"][0] >= 1024
                    and record["size"][1] >= 768]
        reference = desktops[0]
        for record in desktops[1:]:
            assert record["viewport"][2] == pytest.approx(
                reference["viewport"][2], abs=1,
            ), record
            assert record["mute_button"][2:] == pytest.approx(
                reference["mute_button"][2:], abs=1,
            ), record
