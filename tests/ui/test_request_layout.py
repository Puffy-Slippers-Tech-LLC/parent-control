"""Resolution and overflow regression coverage for both shared request views."""

import json
import math
from pathlib import Path
import tempfile

import pytest


pytestmark = pytest.mark.ui


@pytest.mark.parametrize("overlay, dpi_scale",
                         ((False, 1), (True, 1), (False, 1.25), (True, 1.25)),
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
    assert len(records) == 45
    for record in records:
        width, height = record["size"]
        x, y, board_width, board_height = record["viewport"]
        assert x >= 0 and y >= 0, record
        assert x + board_width <= width and y + board_height <= height, record
        assert not record["mute_visible"] and record["muted"], record
        hud_x, hud_y, hud_width, hud_height = record["menu_button"]
        assert 0 <= hud_x < hud_x + hud_width <= width, record
        assert 0 <= hud_y < hud_y + hud_height <= height, record
        assert hud_width >= 66 and record["menu_pick"], record
        assert record["monitor_scale"] == math.ceil(dpi_scale), record
        assert record["surface_scale"] == pytest.approx(dpi_scale), record
        assert record["status_font"] >= 12.5, record
        assert record["board_width"] >= record["board_minimum"], record
        assert record["board_width"] + record["board_margin"] <= record["viewport_allocation"][0], record
        # Check the actual form as well as its surrounding frame: centering
        # at natural width leaves controls squashed inside a wider viewport.
        assert record["board_width"] + record["board_margin"] == pytest.approx(
            record["viewport_allocation"][0], abs=1,
        ), record
        opening = record["gateway_opening"]
        assert x >= opening[0][0] and x + board_width <= opening[1][0], record
        opening_top = max(point[1] for point in opening[:2])
        opening_bottom = min(point[1] for point in opening[2:])
        assert y >= opening_top + 0.06 * (opening_bottom - opening_top), record
        assert y + board_height <= opening_bottom - 0.06 * (opening_bottom - opening_top), record
        if not record["expanded"] and height >= 768:
            assert record["duration_pick"], record
        # Scrolling must expose the complete estimate, including its last line.
        _, footer_y, _, footer_height = record["footer_after_scroll"]
        assert footer_y >= 0, record
        assert footer_y + footer_height <= record["scroll_page"] + 1, record
        if "scrollbar" in record:
            scroll_x, scroll_y, scroll_width, scroll_height = record["scrollbar"]
            assert x < scroll_x < scroll_x + scroll_width <= x + board_width - 12, record
            assert y + 12 <= scroll_y < scroll_y + scroll_height <= y + board_height - 12, record
            assert record["scrollbar_pick"], record
        if width >= 1536 and height >= 960 and not record["expanded"]:
            assert record["scroll_upper"] <= record["scroll_page"] + 1, record
            first, second = record["durations"][:2]
            assert first[1] == second[1] and first[0] < second[0], record

    # Taller desktops allocate wider rows inside a proportionate gateway.
    # Fonts and corner controls retain their native size; extra horizontal
    # space alone must not zoom the form or stretch the gateway.
    for expanded in (False, True):
        desktops = [record for record in records
                    if record["expanded"] == expanded
                    and record["size"][0] >= 1600
                    and record["size"][1] >= 768]
        reference = desktops[0]
        for record in desktops[1:]:
            if record["size"][1] <= 1200:
                assert record["viewport"][2] == pytest.approx(
                    reference["viewport"][2], abs=1,
                ), record
            else:
                assert record["viewport_allocation"][0] > reference["viewport_allocation"][0], record
                # Allow the intended perspective but no extra rendering zoom.
                assert record["viewport"][2] <= record["viewport_allocation"][0] * 1.04, record
            assert record["status_font"] == reference["status_font"], record
            assert record["menu_button"][2:] == pytest.approx(
                reference["menu_button"][2:], abs=1,
            ), record

    for custom in (False, True):
        laptop = next(record for record in records if record["size"] == [1920, 1200]
                      and record["custom"] == custom and not record["expanded"])
        ultrawide = next(record for record in records if record["size"] == [3840, 1600]
                         and record["custom"] == custom and not record["expanded"])
        assert ultrawide["viewport_allocation"][0] >= laptop["viewport_allocation"][0] * 1.30
        for record in (laptop, ultrawide):
            opening = record["gateway_opening"]
            opening_width = opening[1][0] - opening[0][0]
            assert record["viewport"][2] >= opening_width * 0.90, record
